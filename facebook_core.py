"""Facebook public videos and Reels, through yt-dlp. Public videos only: no login, no cookies."""
from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qs, urljoin, urlparse

import html

import requests
import yt_dlp
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Optional: a Netscape cookies.txt from a spare Facebook account. Facebook often shows a login wall to server IPs;
# with cookies it usually serves public videos normally. Set FB_COOKIES_FILE on Render (Secret Files).
COOKIES = None
_src = os.environ.get("FB_COOKIES_FILE")
if _src and os.path.exists(_src):
    COOKIES = os.path.join(tempfile.gettempdir(), "fb_cookies.txt")
    shutil.copyfile(_src, COOKIES)

FB_HOST = re.compile(r"^(?:[\w-]+\.)?facebook\.com$|^fb\.watch$", re.I)
MAX_BYTES = 500 * 1024 * 1024
MP3_MAX_SECONDS = 3600                      # MP3 conversion is limited to one hour of video
PHOTO_HOST = re.compile(r"(?:^|\.)(?:fbcdn\.net|fbsbx\.com)$", re.I)   # where Facebook keeps its pictures


class FBError(Exception):
    def __init__(self, message: str, status: int = 400, detail: str = ""):
        super().__init__(message)
        self.status = status
        self.detail = detail          # what yt-dlp really said, for the server log and the diagnostic page


class _Log:
    """Remembers what yt-dlp says, so a failure can be explained instead of guessed."""
    def __init__(self):
        self.lines: list[str] = []

    def debug(self, msg):
        if not str(msg).startswith("[debug]"):
            self.lines.append(str(msg))

    info = debug

    def warning(self, msg):
        self.lines.append("WARNING: " + str(msg))

    def error(self, msg):
        self.lines.append("ERROR: " + str(msg))

    def text(self, limit: int = 700) -> str:
        return re.sub(r"\x1b\[[0-9;]*m", "", " | ".join(self.lines))[-limit:]


def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def normalize(raw: str) -> str:
    """Take the first link in the text, make it https and check that it really is a Facebook address."""
    raw = (raw or "").strip()
    # the link must start at the beginning of the text or after a space, so "evil.com/facebook.com/x" is not accepted
    m = re.search(r"(?<![\w.@/-])(?:https?://)?(?:[\w-]+\.)*(?:facebook\.com|fb\.watch)/[^\s\"'<>]+", raw, re.I)
    if not m:
        raise FBError("Paste the link of a public Facebook video or Reel.")
    url = m.group(0)
    if not url.lower().startswith("http"):
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    if not FB_HOST.match(host):
        raise FBError("That isn't a Facebook link.")
    return url


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CRAWLER_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
_SHORT = re.compile(r"/share/|^https?://fb\.watch/", re.I)


def _is_fb(url: str) -> bool:
    return bool(FB_HOST.match((urlparse(url).hostname or "").lower()))


def resolve_link(url: str) -> str:
    """Share links (facebook.com/share/r/...) and fb.watch links are only addresses that redirect to the real video page.
    yt-dlp is limited to Facebook extractors here, so we follow those redirects ourselves, one hop at a time,
    and only ever visit Facebook addresses."""
    if not _SHORT.search(url):
        return url
    current = url
    try:
        for _ in range(5):
            if not _is_fb(current):
                return url
            r = requests.get(current, headers={"User-Agent": UA}, allow_redirects=False, timeout=12, stream=True)
            r.close()
            loc = r.headers.get("Location")
            if r.status_code in (301, 302, 303, 307, 308) and loc:
                nxt = urljoin(current, loc)
                if "/login" in urlparse(nxt).path:          # Facebook asked for a login: the real target is in ?next=
                    target = parse_qs(urlparse(nxt).query).get("next", [""])[0]
                    if not target:
                        break
                    nxt = target
                current = nxt
                continue
            break
        if "/share/" in current and _is_fb(current):        # no redirect: ask for the page the way Facebook's own crawler does
            with requests.get(current, headers={"User-Agent": CRAWLER_UA}, timeout=12, stream=True) as g:
                head = next(g.iter_content(200_000), b"").decode("utf-8", "ignore")
            m = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)', head)
            if m:
                current = m.group(1).replace("&amp;", "&")
    except requests.RequestException:
        return url
    return current if _is_fb(current) else url


def _friendly(exc: Exception, cap: "_Log | None" = None) -> FBError:
    raw = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).replace("ERROR: ", "")
    detail = (raw[:300] + (" | " + cap.text() if cap else "")).strip()
    log.warning("Facebook: yt-dlp said: %s", detail)
    err = _classify(raw.lower())
    err.detail = detail
    return err


def _classify(low: str) -> FBError:
    if any(k in low for k in ("http error 429", "http error 403", "too many requests", "rate-limit", "rate limit")):
        return FBError("Facebook is limiting our server right now. Please try again in a few minutes.", 503)
    if any(k in low for k in ("login", "log in", "private", "registered users", "not available", "cannot parse data")):
        return FBError("This video is private, removed, or needs a Facebook login. Only public videos can be downloaded.", 404)
    if "unsupported url" in low or "no suitable extractor" in low:
        return FBError("That doesn't look like a Facebook video link.", 400)
    return FBError("Couldn't read this video. Check that it is public and that you pasted the whole link.", 502)


def _base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": False, "noplaylist": True, "socket_timeout": 20, "retries": 2,
            "allowed_extractors": ["facebook.*"]}
    if COOKIES:
        opts["cookiefile"] = COOKIES
    proxy = os.environ.get("FB_PROXY")
    if proxy:
        opts["proxy"] = proxy
    return opts


def lookup(raw: str) -> dict:
    url = resolve_link(normalize(raw))
    cap = _Log()
    try:
        with yt_dlp.YoutubeDL({**_base_opts(), "skip_download": True, "logger": cap}) as ydl:
            data = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        err = _friendly(exc, cap)
        if err.status == 400 and "/share/" in url:
            err = FBError("We couldn't open this share link. Open it in your browser, then paste the address of the video page "
                          "(it contains /reel/ or /watch/).", 400, err.detail)
        raise err from exc
    if not data:
        raise FBError("Couldn't read this video.", 502)
    if data.get("_type") == "playlist":
        entries = [e for e in (data.get("entries") or []) if e]
        if not entries:
            raise FBError("No video found at this link.", 404)
        data = entries[0]
    formats = data.get("formats") or []
    heights = sorted({int(f["height"]) for f in formats
                      if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)[:5]
    if not formats and not data.get("url"):
        raise FBError("No downloadable video was found at this link.", 404)
    return {"id": str(data.get("id") or ""), "title": data.get("title") or "Facebook video",
            "uploader": data.get("uploader") or "", "duration": data.get("duration") or 0,
            "thumbnail": data.get("thumbnail"), "heights": heights, "url": url}


def _codecs(ff: str, path: str):
    """(video codec, pixel format, audio codec) of a file, read from ffmpeg's own description of it."""
    text = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True, timeout=30).stderr
    v = re.search(r"Video: (\w+)([^\n]*)", text)
    a = re.search(r"Audio: (\w+)", text)
    pix = re.search(r"\b(?:yuvj?\d{3}p\w*|gbrp\w*|rgb\w*|bgr\w*|nv\d+\w*|p0\d+\w*|gray\w*)\b", v.group(2)) if v else None
    return (v.group(1) if v else ""), (pix.group(0) if pix else ""), (a.group(1) if a else "")


def ensure_playable(path: str, ff: str) -> str:
    """Facebook gives video and sound as separate streams, often VP9 or AV1 with Opus. Joined into an MP4 that opens in
    browsers but not in the normal players on Windows, TVs and phones. Make sure the file is H.264 + AAC."""
    try:
        vcodec, pix, acodec = _codecs(ff, path)
        final = os.path.splitext(path)[0] + ".mp4"
        if not vcodec or (vcodec == "h264" and pix == "yuv420p" and acodec in ("", "aac") and path == final):
            return path                                                  # already plays everywhere (or it is audio only)
        copy_video = vcodec == "h264" and pix == "yuv420p"               # only the sound needs converting: fast
        tmp = final + ".tmp.mp4"
        cmd = [ff, "-y", "-i", path, "-map", "0:v:0", "-map", "0:a:0?"]
        cmd += ["-c:v", "copy"] if copy_video else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp]
        run = subprocess.run(cmd, capture_output=True, timeout=240)
        if run.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp, final)
            return final
        if os.path.exists(tmp):
            os.remove(tmp)
    except (subprocess.TimeoutExpired, OSError):
        for leftover in glob.glob(os.path.splitext(path)[0] + "*.tmp.mp4"):
            os.remove(leftover)
    return path


def download(raw: str, quality: str, out_dir: str) -> str:
    """quality: "best", "mp3" or a height such as "720"."""
    url = resolve_link(normalize(raw))
    ff = _ffmpeg()
    opts = {**_base_opts(), "outtmpl": os.path.join(out_dir, "facebook-video-%(id)s.%(ext)s"),
            "merge_output_format": "mp4", "max_filesize": MAX_BYTES}
    if ff:
        opts["ffmpeg_location"] = ff
    if quality == "mp3":
        if not ff:
            raise FBError("MP3 conversion isn't available on this server right now.", 503)
        opts["match_filter"] = yt_dlp.utils.match_filter_func(f"duration <=? {MP3_MAX_SECONDS}")
        opts["format"] = "ba/b"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    elif quality.isdigit() and 100 <= int(quality) <= 4320:
        h = int(quality)
        opts["format"] = f"bv*[height<={h}]+ba/b[height<={h}]/b" if ff else f"b[height<={h}]/b"
    else:
        opts["format"] = "bv*+ba/b" if ff else "b"
    if quality != "mp3":
        opts["format_sort"] = ["vcodec:h264", "res", "acodec:aac"]          # most players understand H.264 + AAC
    cap = _Log()
    opts["logger"] = cap
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise _friendly(exc, cap) from exc
    files = [f for f in glob.glob(os.path.join(out_dir, "*")) if not f.endswith((".part", ".ytdl"))]
    if not files:
        if quality == "mp3":
            raise FBError("This video is longer than an hour, so it can't be converted to MP3 here.", 413)
        raise FBError("Couldn't download this video.", 502)
    best = max(files, key=os.path.getsize)
    return best if quality == "mp3" or not ff else ensure_playable(best, ff)


def photo_lookup(raw: str) -> dict:
    """Public photo posts. Facebook shows link-preview data (og: tags) to its own crawler, which is what we read.
    The picture is the largest one Facebook offers there, which is often smaller than the original upload."""
    url = resolve_link(normalize(raw))
    try:
        r = requests.get(url, headers={"User-Agent": CRAWLER_UA, "Accept-Language": "en"}, timeout=15)
    except requests.RequestException as exc:
        raise FBError("Couldn't reach Facebook. Please try again in a moment.", 502) from exc
    if not _is_fb(r.url):
        raise FBError("That link doesn't lead to a Facebook page.", 400)
    if r.status_code in (403, 429):
        raise FBError("Facebook is limiting our server right now. Please try again in a few minutes.", 503)
    if r.status_code == 404:
        raise FBError("This post was not found. It may have been removed or may be private.", 404)
    soup = BeautifulSoup(r.text[:600_000], "html.parser")
    meta = lambda prop: [html.unescape(t.get("content", "")) for t in soup.find_all("meta", attrs={"property": prop}) if t.get("content")]
    if meta("og:video") or meta("og:video:url") or meta("og:video:secure_url"):
        raise FBError("This post is a video. Use the Facebook Video Downloader for it.", 400)
    images, seen = [], set()
    for src in meta("og:image"):
        if src in seen or not src.lower().startswith("https://") or not PHOTO_HOST.search(urlparse(src).hostname or ""):
            continue
        seen.add(src)
        images.append({"url": src, "index": len(images), "filename": f"facebook-photo-{len(images) + 1}.jpg"})
    if not images:
        raise FBError("No public photo was found at this link. The post may be private, or Facebook may be asking for a login.", 404)
    title = (meta("og:title") or ["Facebook photo"])[0][:120]
    return {"title": title, "images": images, "url": url}


def photo_fetch(src: str):
    """Open a Facebook picture for streaming. Only Facebook's own picture servers are allowed."""
    host = (urlparse(src).hostname or "").lower()
    if not src.lower().startswith("https://") or not PHOTO_HOST.search(host):
        raise FBError("That isn't a Facebook picture.", 400)
    try:
        r = requests.get(src, headers={"User-Agent": UA}, timeout=20, stream=True)
    except requests.RequestException as exc:
        raise FBError("Couldn't download the picture. Please try again.", 502) from exc
    if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
        r.close()
        raise FBError("Facebook no longer serves this picture. Look the post up again.", 410)
    return r
