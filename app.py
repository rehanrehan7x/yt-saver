"""Video Saver - download YouTube videos as MP4 or audio as MP3 (yt-dlp)."""
from __future__ import annotations

import glob, logging, os, re, shutil, tempfile, threading, webbrowser
from urllib.parse import quote, urlparse

import yt_dlp
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
log = logging.getLogger("ytsaver")

YT_HOST = re.compile(r"^(?:[a-z0-9-]+\.)*(?:youtube\.com|youtu\.be)$", re.I)
VIDEO_ID = re.compile(r"[\w-]{11}")
MAX_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", 3 * 3600))
STANDARD_HEIGHTS = [2160, 1440, 1080, 720, 480, 360, 240, 144]

# Secret files on hosts are often read-only; yt-dlp wants to write cookies back.
COOKIES = None
_src = os.environ.get("YT_COOKIES_FILE")
if _src and os.path.isfile(_src):
    COOKIES = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    shutil.copyfile(_src, COOKIES)


class YTError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def ffmpeg_path() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 20, "retries": 3}
    runtimes = {n: {} for n in ("deno", "node", "bun") if shutil.which(n)}
    if runtimes:
        opts["js_runtimes"] = runtimes
    if COOKIES:
        opts["cookiefile"] = COOKIES
    return opts


def friendly(exc: Exception) -> YTError:
    raw = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).replace("ERROR: ", "")
    low = raw.lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return YTError("YouTube is blocking this server (common on cloud hosts). "
                       "Run the app on your own computer, or add a cookies file.", 429)
    if "private video" in low:
        return YTError("This video is private.")
    if "age" in low and "restrict" in low:
        return YTError("This video is age-restricted. A cookies file from a logged-in browser is needed.")
    if "unavailable" in low or "removed" in low or "not available" in low:
        return YTError("This video isn't available (removed, private, or blocked in this country).", 404)
    return YTError(f"Couldn't read this video: {raw[:160]}", 502)


def clean_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise YTError("Paste a YouTube link.")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").lower()
    if not YT_HOST.match(host):
        raise YTError("That isn't a YouTube link.")
    return raw


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return "ok"


@app.post("/api/info")
def api_info():
    try:
        url = clean_url((request.get_json(silent=True) or {}).get("url", ""))
        with yt_dlp.YoutubeDL({**base_opts(), "skip_download": True}) as ydl:
            data = ydl.extract_info(url, download=False)
    except YTError as exc:
        return jsonify(error=str(exc)), exc.status
    except yt_dlp.utils.DownloadError as exc:
        err = friendly(exc)
        return jsonify(error=str(err)), err.status
    except Exception:  # noqa: BLE001
        app.logger.exception("info failed")
        return jsonify(error="Something went wrong looking up this video."), 500

    if not data or not VIDEO_ID.fullmatch(data.get("id") or ""):
        return jsonify(error="That link doesn't point to a single video."), 400
    if data.get("is_live"):
        return jsonify(error="Live streams can't be downloaded."), 400
    if (data.get("duration") or 0) > MAX_SECONDS:
        return jsonify(error=f"Videos longer than {MAX_SECONDS // 3600} hours aren't supported."), 400

    top = max((f.get("height") or 0 for f in data.get("formats", [])
               if f.get("vcodec") not in (None, "none")), default=0)
    heights = [h for h in STANDARD_HEIGHTS if h <= top] or [top or 720]
    return jsonify(id=data["id"], title=data.get("title") or data["id"],
                   channel=data.get("uploader") or "", duration=data.get("duration") or 0,
                   thumbnail=data.get("thumbnail"), heights=heights)


@app.get("/download")
def download():
    vid = request.args.get("id", "")
    fmt = request.args.get("fmt", "mp4")
    height = request.args.get("height", type=int) or 720
    if not VIDEO_ID.fullmatch(vid) or fmt not in ("mp4", "mp3") or not 100 <= height <= 4320:
        return jsonify(error="Bad request."), 400

    tmp = tempfile.mkdtemp(prefix="ytsaver_")
    ff = ffmpeg_path()
    opts = {**base_opts(), "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
            "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {MAX_SECONDS} & !is_live")}
    if ff:
        opts["ffmpeg_location"] = ff
    if fmt == "mp3":
        if ff:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        else:
            opts["format"] = "bestaudio[ext=m4a]/bestaudio"
    elif ff:
        # Prefer H.264 + AAC: plays everywhere (VP9/AV1 in MP4 often won't play on Windows).
        opts["format"] = (f"bestvideo[height<={height}][vcodec^=avc1]+bestaudio[ext=m4a]/"
                          f"best[height<={height}][vcodec^=avc1][ext=mp4]/"
                          f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                          f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best")
        opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = f"best[height<={height}][ext=mp4]/best[height<={height}]/best"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
        files = [f for f in glob.glob(os.path.join(tmp, f"{vid}.*")) if not f.endswith((".part", ".ytdl"))]
        if not info or not files:
            raise YTError("This video can't be downloaded (live, too long, or restricted).")
        path = max(files, key=os.path.getsize)
    except YTError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error=str(exc)), exc.status
    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        err = friendly(exc)
        return jsonify(error=str(err)), err.status
    except Exception:  # noqa: BLE001
        shutil.rmtree(tmp, ignore_errors=True)
        app.logger.exception("download failed")
        return jsonify(error="Something went wrong downloading this video."), 500

    ext = os.path.splitext(path)[1]
    title = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", info.get("title") or vid).strip()[:100] or vid

    def stream_then_clean_up():
        try:
            with open(path, "rb") as f:
                while chunk := f.read(1 << 16):
                    yield chunk
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    resp = Response(stream_then_clean_up(),
                    mimetype="audio/mpeg" if ext == ".mp3" else "video/mp4" if ext == ".mp4" else "application/octet-stream")
    resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(title + ext)}; filename=\"{vid}{ext}\""
    resp.headers["Content-Length"] = str(os.path.getsize(path))
    resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    app.run(host=host, port=port, debug=False, threaded=True)
