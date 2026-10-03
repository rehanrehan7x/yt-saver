"""Video Saver - download YouTube videos as MP4 or audio as MP3 (yt-dlp)."""
from __future__ import annotations

import glob, json, logging, mimetypes, os, re, shutil, tempfile, threading, webbrowser
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse

import yt_dlp
import instagram_core as ig
import instagram_core as ig
import pinterest_core as core
import requests
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


SITE_NAME = os.environ.get("SITE_NAME", "MaxDownloader")
CONTACT = os.environ.get("CONTACT_EMAIL", "your-email@example.com")

FAQ = [
    ("Is MaxDownloader free to use?",
     "Yes. You don't need an account, and there are no watermarks or sign-up steps. Paste a link, choose a format and download."),
    ("How do I download a YouTube video?",
     "Copy the video link from YouTube, paste it into the box at the top of this page, press Get video, choose MP4 or MP3, then press Download."),
    ("Which formats and qualities are available?",
     "Video is saved as MP4, in every quality the video offers from 144p up to 4K. Audio-only downloads are saved as MP3. For MP4 files that play on every device, choose 1080p or lower."),
    ("Do I need to install any app or extension?",
     "No. MaxDownloader runs in your browser on Windows, Mac, Android, iPhone and Linux."),
    ("Is it legal to download YouTube videos?",
     "It depends on the video and where you live. Download only videos you own, videos with a Creative Commons or public-domain licence, or videos you have permission to save. YouTube's terms of service restrict other downloads."),
    ("Why is my download taking a while?",
     "Our server fetches the file first and then sends it to you, so long or high-quality videos take longer. Choosing a lower quality such as 480p makes it faster."),
    ("Can I download playlists or live streams?",
     "Not at the moment. MaxDownloader handles one regular video at a time."),
]

PAGES = [
    dict(path="/", fmt="mp4", nav="Home",
         title="MaxDownloader: Free YouTube Video Downloader (MP4 & MP3)",
         h1="Free YouTube Video Downloader",
         desc="Download YouTube videos as MP4 or MP3 for free with MaxDownloader. No sign-up, no software to install. Paste a link, pick a quality and save.",
         lede="Paste a YouTube link, choose MP4 video or MP3 audio, and download. Free, fast and no sign-up.",
         intro="MaxDownloader is a simple online tool for saving videos you are allowed to keep, such as your own uploads, Creative Commons videos and public-domain clips. It works in any modern browser, so there is nothing to install."),
    dict(path="/youtube-to-mp4", fmt="mp4", nav="YouTube to MP4",
         title="YouTube to MP4 Downloader (HD & 4K) | MaxDownloader",
         h1="YouTube to MP4 Downloader",
         desc="Convert and download YouTube videos to MP4 in HD, Full HD or 4K with MaxDownloader. Free, no registration, works on phone and PC.",
         lede="Save a YouTube video as an MP4 file in the quality you choose, from 144p up to 4K.",
         intro="MP4 is the most widely supported video format, so files saved here open on phones, tablets, laptops and TVs. Pick 1080p or lower for the best compatibility, or a higher quality if your player supports it."),
    dict(path="/youtube-to-mp3", fmt="mp3", nav="YouTube to MP3",
         title="YouTube to MP3 Converter: Free & Fast | MaxDownloader",
         h1="YouTube to MP3 Converter",
         desc="Convert YouTube videos to MP3 audio for free. MaxDownloader saves the sound as a 192 kbps MP3 file. No sign-up and no app needed.",
         lede="Turn a YouTube video into an MP3 audio file. Ideal for lectures, podcasts and your own music.",
         intro="Need only the sound? This converter extracts the audio from the video and saves it as a 192 kbps MP3 you can play anywhere. Only convert audio you have the right to keep."),
]

PAGES.append(dict(
    path="/pindownloader", kind="pin", nav="Pinterest Downloader",
    title="Pinterest Video & Image Downloader: Free, HD | MaxDownloader",
    desc="Download Pinterest videos, images and GIFs in original quality for free. Paste a pin link (pin.it works too) and save. No sign-up, no watermark.",
    h1="Pinterest Video & Image Downloader",
    lede="Paste a Pinterest link and get the full-size photo, video or GIF. Not the thumbnail.",
    intro="Pinterest doesn't give you a download button for most pins. Paste the pin's link here and we fetch the original file for you: the largest version of a photo, the MP4 of a video, or the actual .gif of an animated pin.",
))
PAGES.append(dict(
    path="/pinterest-gif-downloader", kind="pin", nav="Pinterest GIF",
    title="Pinterest GIF Downloader: Save GIFs for Free | MaxDownloader",
    desc="Download GIFs from Pinterest as real .gif files for free. Paste a pin link, press Download. No sign-up, no app, works on phone and PC.",
    h1="Pinterest GIF Downloader",
    lede="Save an animated pin as a real .gif file you can send, upload or keep.",
    intro="When a pin is an animated GIF, this page downloads the original .gif file, not a still image or a screen recording. If the pin is a normal photo or video, you'll get that instead and it will be labelled so you know.",
))
for _pg in PAGES:
    _pg["title"] = _pg["title"].replace("MaxDownloader", SITE_NAME)

IG_PAGES = [
    dict(path="/instagram-downloader", nav="Instagram Downloader", ph="Paste Instagram link or @username here",
         title="Instagram Downloader: Reels, Photos & Profile Pictures | MaxDownloader",
         h1="Instagram Downloader",
         desc="Download Instagram reels, videos, photos and profile pictures (DP) for free. Paste a public link or username. No sign-up, no app.",
         lede="Paste the link of a public reel, video or photo, or just a username to get the profile picture.",
         intro="Works with public posts and public profiles. Paste a post or reel link to download the video or photos, or type a username to get the profile picture in the largest size Instagram offers."),
    dict(path="/instagram-reels-downloader", nav=None, ph="Paste Instagram reel link here",
         title="Instagram Reels Downloader: Save Reels as MP4 | MaxDownloader",
         h1="Instagram Reels Downloader",
         desc="Download Instagram reels as MP4 video for free. Paste the reel link and save it. No watermark overlay, no sign-up.",
         lede="Copy a reel's link, paste it here and save the video as an MP4 file.",
         intro="Open the reel in Instagram, tap Share, then Copy link. Paste it above and we fetch the video file for you. Only public reels work."),
    dict(path="/instagram-photo-downloader", nav=None, ph="Paste Instagram photo link here",
         title="Instagram Photo Downloader: Save Pictures in Full Size | MaxDownloader",
         h1="Instagram Photo Downloader",
         desc="Download Instagram photos and carousel images in full size for free. Paste a public post link and save each picture.",
         lede="Paste a public photo post and save the picture in full size.",
         intro="For posts with several photos, each picture appears as its own card with a Download button. Only public posts work."),
    dict(path="/instagram-dp-downloader", nav=None, ph="Paste @username or profile link here",
         title="Instagram DP Downloader: View & Save Profile Picture | MaxDownloader",
         h1="Instagram DP Downloader",
         desc="Download an Instagram profile picture (DP) in full size for free. Type a username or paste a profile link.",
         lede="Type a username or paste a profile link to save the profile picture in the biggest size available.",
         intro="Profile pictures are public, so this works for most accounts. You'll get the largest version Instagram serves, which is usually 320 pixels or bigger."),
]
for _g in IG_PAGES:
    _g["kind"] = "ig"
    _g["title"] = _g["title"].replace("MaxDownloader", SITE_NAME)
PAGES.extend(IG_PAGES)

IG_FAQ = [
    ("Can I download Instagram reels, photos and profile pictures?",
     "Yes, as long as they are public. Paste a reel or post link, or type a username for the profile picture."),
    ("Can I download from a private account?",
     "No. Private accounts and their posts can't be downloaded."),
    ("Can I download stories or highlights?",
     "Not at the moment. Only reels, videos, photos and profile pictures are supported."),
    ("Why does it say Instagram wants a login?",
     "Instagram often asks servers to log in before showing a post. Wait a minute and try again, or try a different link."),
    ("What size is the profile picture?",
     "We fetch the largest version Instagram makes available for that account."),
    ("Is it okay to reuse what I download?",
     "Photos and videos belong to their creators. Save them for personal use, and get permission and give credit before sharing or posting someone else's work."),
]

PIN_FAQ = [
    ("Can I download a GIF from Pinterest?",
     "Yes. Paste the link of the animated pin and press Find media. If the pin is a GIF it is labelled GIF and downloads as a .gif file."),
    ("How do I download a Pinterest video or image?",
     "Open the pin, copy its link (or the pin.it short link), paste it into the box on this page and press Find media. Then press Download on the result."),
    ("Do you save the original quality?",
     "Yes. For photos we fetch the largest version available, and for video pins we fetch the best MP4 we can find, not the thumbnail."),
    ("Can I download several pins at once?",
     "Yes. Paste up to 20 links, one per line or all together, and each one gets its own Download button."),
    ("Does it work with pin.it links?",
     "Yes. Short pin.it links from the Pinterest app's Share button are supported."),
    ("Can I download private pins or boards?",
     "No. Only public individual pins work. Whole boards and private content are not supported."),
    ("Is it okay to reuse downloaded pins?",
     "Pins belong to their creators. Save them for personal reference, and always get permission and give credit before sharing or publishing someone else's work."),
]

LEGAL = {
    "privacy": ("Privacy Policy", """<p>MaxDownloader does not require an account and does not ask for your name or email.</p>
<h2>What we process</h2><p>When you paste a link, our server contacts YouTube to read the video details and, if you download, to fetch the file. The file is kept only for the few moments it takes to send it to your browser, then deleted. We do not keep copies of videos.</p>
<h2>Logs</h2><p>Like most websites, our hosting provider may record technical data such as IP address, browser type and requested page for security and troubleshooting.</p>
<h2>Cookies and third parties</h2><p>We do not set tracking cookies. Fonts are loaded from Google Fonts, which may receive your IP address. If we add analytics or advertising in future, this page will be updated.</p>
<h2>Contact</h2><p>Questions about privacy: <a href="mailto:{contact}">{contact}</a>.</p>"""),
    "terms": ("Terms of Use", """<p>By using MaxDownloader you agree to these terms.</p>
<h2>Permitted use</h2><p>The service is for personal, lawful use. You may download only content you own, content under a licence that allows it (such as Creative Commons or public domain), or content you have permission to save.</p>
<h2>Your responsibility</h2><p>You are responsible for complying with copyright law and the terms of the platform the content comes from. MaxDownloader does not host any videos and is not affiliated with or endorsed by YouTube or Google.</p>
<h2>No warranty</h2><p>The service is provided "as is" without warranties. It may change or be unavailable at any time, and we are not liable for any loss arising from its use.</p>
<h2>Contact</h2><p><a href="mailto:{contact}">{contact}</a></p>"""),
    "dmca": ("Copyright / DMCA", """<p>MaxDownloader does not store or host any video or audio. Files are fetched on request from the original platform and deleted after delivery.</p>
<p>If you are a copyright owner and believe the service is being used to infringe your work, email <a href="mailto:{contact}">{contact}</a> with: the link to the content, proof that you own the rights, your contact details, and a statement that you are acting in good faith. We will review the request promptly and can block the specific content from being processed.</p>"""),
    "contact": ("Contact Us", """<p>Questions, feedback or a copyright request? Email us at <a href="mailto:{contact}">{contact}</a>.</p><p>We usually reply within a few days.</p>"""),
}


def site_url() -> str:
    return (os.environ.get("SITE_URL") or request.url_root).rstrip("/")


def make_tool_view(page):
    def view():
        canonical = site_url() + page["path"]
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebApplication", "name": SITE_NAME, "url": canonical,
             "applicationCategory": "MultimediaApplication", "operatingSystem": "Any",
             "description": page["desc"],
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}]}
        return render_template("index.html", page=page, faq=FAQ, pages=PAGES, canonical=canonical,
                               title=page["title"], desc=page["desc"],
                               jsonld=json.dumps(ld).replace("</", "<\\/"))
    view.__name__ = "tool_" + (page["path"].strip("/").replace("-", "_") or "home")
    return view


def make_legal_view(slug, title, body):
    def view():
        return render_template("legal.html", pages=PAGES, heading=title, body=body.format(contact=CONTACT),
                               canonical=f"{site_url()}/{slug}", title=f"{title} | {SITE_NAME}",
                               desc=f"{title} for {SITE_NAME}.")
    view.__name__ = "legal_" + slug
    return view


for _p in [x for x in PAGES if not x.get("kind")]:
    app.add_url_rule(_p["path"], view_func=make_tool_view(_p))
for _slug, (_t, _b) in LEGAL.items():
    app.add_url_rule(f"/{_slug}", view_func=make_legal_view(_slug, _t, _b))


@app.get("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /download\nDisallow: /pin/download\nDisallow: /ig/download\nDisallow: /ig/\n\nSitemap: {site_url()}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    base = site_url()
    paths = [p["path"] for p in PAGES] + [f"/{s}" for s in LEGAL]
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{base}{x}</loc></url>" for x in paths) + "</urlset>")
    return Response(xml, mimetype="application/xml")


@app.context_processor
def inject_site():
    return {"site_name": SITE_NAME}


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
            "concurrent_fragment_downloads": 4, "http_chunk_size": 10 * 1024 * 1024,
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


# ---------------- Pinterest downloader (/pindownloader) ----------------
MAX_LINKS_PER_REQUEST = 20


def pin_lookup_one(raw: str) -> dict:
    raw = raw.strip()
    try:
        info = core.get_pin_info(raw)
    except core.PinError as exc:
        return {"input": raw, "ok": False, "error": str(exc)}
    except Exception:  # noqa: BLE001
        app.logger.exception("Pin lookup failed for %s", raw)
        return {"input": raw, "ok": False, "error": "Something went wrong looking up this pin."}
    return {"input": raw, "ok": True, **info.public()}


def make_pin_view(page):
    def view():
        canonical = site_url() + page["path"]
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebApplication", "name": f"{SITE_NAME} {page['nav']}", "url": canonical,
             "applicationCategory": "MultimediaApplication", "operatingSystem": "Any", "description": page["desc"],
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in PIN_FAQ]}]}
        return render_template("pin.html", page=page, pages=PAGES, faq=PIN_FAQ, canonical=canonical,
                               title=page["title"], desc=page["desc"],
                               jsonld=json.dumps(ld).replace("</", "<\\/"))
    view.__name__ = "pin_" + page["path"].strip("/").replace("-", "_")
    return view


for _p in [x for x in PAGES if x.get("kind") == "pin"]:
    app.add_url_rule(_p["path"], view_func=make_pin_view(_p))


@app.post("/api/pin/lookup")
def pin_lookup():
    payload = request.get_json(silent=True) or {}
    links = [x for x in (payload.get("urls") or []) if isinstance(x, str) and x.strip()]
    if not links:
        return jsonify(error="Paste at least one pin link."), 400
    if len(links) > MAX_LINKS_PER_REQUEST:
        return jsonify(error=f"Please paste {MAX_LINKS_PER_REQUEST} links or fewer at a time."), 400
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(pin_lookup_one, links))
    return jsonify(results=results)


@app.get("/pin/download")
def pin_download():
    raw = request.args.get("url", "")
    tmp_dir = tempfile.mkdtemp(prefix="pinsaver_")
    try:
        info = core.get_pin_info(raw)
        path = core.download_media(info, tmp_dir)
    except core.PinError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=str(exc)), exc.status
    except Exception:  # noqa: BLE001
        shutil.rmtree(tmp_dir, ignore_errors=True)
        app.logger.exception("Pin download failed for %s", raw)
        return jsonify(error="Something went wrong downloading this pin."), 500

    filename = os.path.basename(path)

    def stream_then_clean_up():
        try:
            with open(path, "rb") as f:
                while chunk := f.read(1 << 16):
                    yield chunk
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    resp = Response(stream_then_clean_up(), mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")
    resp.headers.add("Content-Disposition", "attachment", filename=filename)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Length"] = str(os.path.getsize(path))
    return resp


# ---------------- Instagram downloader ----------------
def make_ig_view(page):
    def view():
        canonical = site_url() + page["path"]
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebApplication", "name": f"{SITE_NAME} {page['h1']}", "url": canonical,
             "applicationCategory": "MultimediaApplication", "operatingSystem": "Any", "description": page["desc"],
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in IG_FAQ]}]}
        return render_template("ig.html", page=page, pages=PAGES, faq=IG_FAQ, canonical=canonical,
                               title=page["title"], desc=page["desc"],
                               jsonld=json.dumps(ld).replace("</", "<\\\\/"))
    view.__name__ = "ig_" + page["path"].strip("/").replace("-", "_")
    return view


for _p in IG_PAGES:
    app.add_url_rule(_p["path"], view_func=make_ig_view(_p))


@app.post("/api/ig/lookup")
def ig_lookup():
    raw = (request.get_json(silent=True) or {}).get("url", "")
    try:
        return jsonify(ig.resolve(raw).public())
    except ig.IGError as exc:
        return jsonify(error=str(exc)), exc.status
    except Exception:  # noqa: BLE001
        app.logger.exception("IG lookup failed for %s", raw)
        return jsonify(error="Something went wrong looking this up."), 500


@app.get("/ig/download")
def ig_download():
    raw = request.args.get("u", "")
    index = request.args.get("i", type=int, default=0)
    tmp_dir = tempfile.mkdtemp(prefix="igsaver_")
    try:
        path = ig.download_item(ig.resolve(raw), index, tmp_dir)
    except ig.IGError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(error=str(exc)), exc.status
    except Exception:  # noqa: BLE001
        shutil.rmtree(tmp_dir, ignore_errors=True)
        app.logger.exception("IG download failed for %s", raw)
        return jsonify(error="Something went wrong downloading this file."), 500

    filename = os.path.basename(path)

    def stream_then_clean_up():
        try:
            with open(path, "rb") as f:
                while chunk := f.read(1 << 16):
                    yield chunk
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    resp = Response(stream_then_clean_up(), mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream")
    resp.headers.add("Content-Disposition", "attachment", filename=filename)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Length"] = str(os.path.getsize(path))
    return resp


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    app.run(host=host, port=port, debug=False, threaded=True)
