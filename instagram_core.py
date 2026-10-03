"""Instagram helper: public reels / videos / photos and profile pictures."""
from __future__ import annotations

import glob, logging, os, re, shutil, tempfile, threading, time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
import yt_dlp
from bs4 import BeautifulSoup

log = logging.getLogger("igsaver")

BOT_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
WEB_UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0 Mobile Safari/537.36")
CDN_HOST = re.compile(r"(?:^|\.)(?:cdninstagram\.com|fbcdn\.net)$", re.I)
IG_HOST = re.compile(r"^(?:www\.|m\.)?(?:instagram\.com|instagr\.am)$", re.I)
USERNAME = re.compile(r"^@?([A-Za-z0-9._]{1,30})$")
CODE = re.compile(r"^[\w-]{5,30}$")
IMG_EXT = {"jpg", "jpeg", "png", "webp"}
MAX_BYTES = 500 * 1024 * 1024

COOKIES = None
_src = os.environ.get("IG_COOKIES_FILE")
if _src and os.path.isfile(_src):
    COOKIES = os.path.join(tempfile.gettempdir(), "ig_cookies.txt")
    shutil.copyfile(_src, COOKIES)

LOGIN_MSG = ("Instagram wants a login to show this (very common for cloud servers). "
             "Private accounts can't be downloaded. Try again later, or run the app on your own computer.")


class IGError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Media:
    kind: str            # "video", "image" or "dp"
    thumbnail: str | None
    filename: str
    url: str | None      # direct CDN url when known
    label: str
    via: str             # "ytdlp", "og" or "api"
    index: int = 0


@dataclass
class IGInfo:
    key: str
    kind: str            # "post" or "profile"
    title: str
    canonical: str
    media: list[Media] = field(default_factory=list)
    post_url: str = ""

    def public(self) -> dict:
        return {"title": self.title, "kind": self.kind, "canonical": self.canonical,
                "items": [{"index": m.index, "kind": m.kind, "label": m.label, "thumbnail": m.thumbnail,
                           "filename": m.filename} for m in self.media]}


def parse_input(raw: str):
    """Return ("post", (kind, code)) or ("profile", username)."""
    raw = (raw or "").strip()
    if not raw:
        raise IGError("Paste an Instagram link or a username.")
    if re.match(r"^(?:https?://)?(?:www\.|m\.)?(?:instagram\.com|instagr\.am)/", raw, re.I):
        if not raw.lower().startswith("http"):
            raw = "https://" + raw
        u = urlparse(raw)
        if not IG_HOST.match(u.hostname or ""):
            raise IGError("That isn't an Instagram link.")
        parts = [p for p in u.path.split("/") if p]
        if not parts:
            raise IGError("Paste the link of a post, reel or profile.")
        if parts[0].lower() == "stories":
            raise IGError("Stories aren't supported. Paste a post, reel or profile link.")
        for i, p in enumerate(parts):
            if p.lower() in ("p", "reel", "reels", "tv") and i + 1 < len(parts):
                code = parts[i + 1]
                if not CODE.match(code):
                    raise IGError("That post link looks incomplete.")
                kind = "reel" if p.lower() in ("reel", "reels") else ("tv" if p.lower() == "tv" else "p")
                return "post", (kind, code)
        if len(parts) == 1 and USERNAME.match(parts[0]) and parts[0].lower() not in ("explore", "accounts", "direct", "about", "legal"):
            return "profile", parts[0].lower()
        raise IGError("Paste the link of a post, reel or profile.")
    m = USERNAME.match(raw)
    if m:
        return "profile", m.group(1).lower()
    raise IGError("That doesn't look like an Instagram link or username.")


def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def _friendly(exc: Exception) -> IGError:
    low = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).lower()
    if "login" in low or "log in" in low or "rate-limit" in low or "rate limit" in low or "401" in low or "403" in low:
        return IGError(LOGIN_MSG, 429)
    if "private" in low:
        return IGError("This account or post is private.", 403)
    if "not found" in low or "404" in low or "unavailable" in low or "removed" in low:
        return IGError("This post isn't available. It may have been deleted.", 404)
    return IGError("Couldn't read this Instagram link.", 502)


def _meta(soup, name):
    tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
    return (tag.get("content") or "").strip() if tag else ""


def _fetch_html(url: str) -> BeautifulSoup:
    try:
        r = requests.get(url, headers={"User-Agent": BOT_UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=20)
    except requests.RequestException as exc:
        raise IGError("Couldn't reach Instagram. Please try again.", 502) from exc
    if r.status_code == 404:
        raise IGError("This post or profile wasn't found.", 404)
    return BeautifulSoup(r.text, "html.parser")


def _classify(entry: dict):
    url = entry.get("url") or ""
    ext = (entry.get("ext") or "").lower()
    formats = entry.get("formats") or []
    has_video = any(f.get("vcodec") not in (None, "none") for f in formats)
    if ext in IMG_EXT or (not has_video and re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", url, re.I)):
        src = url or (formats[-1].get("url") if formats else None) or entry.get("thumbnail")
        return "image", src
    return "video", None


def _ytdlp_media(kind: str, code: str) -> list[Media]:
    url = f"https://www.instagram.com/{kind}/{code}/"
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20, "retries": 2}
    if COOKIES:
        opts["cookiefile"] = COOKIES
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise _friendly(exc) from exc
    entries = [e for e in (data.get("entries") or [data]) if e]
    out = []
    for i, e in enumerate(entries):
        k, src = _classify(e)
        many = len(entries) > 1
        suffix = f"_{i + 1}" if many else ""
        if k == "image":
            out.append(Media("image", e.get("thumbnail") or src, f"{code}{suffix}.jpg", src, "Photo", "ytdlp", i))
        else:
            out.append(Media("video", e.get("thumbnail"), f"{code}{suffix}.mp4", None,
                             "Reel" if kind == "reel" else "Video", "ytdlp", i))
    return out


def _og_media(kind: str, code: str) -> list[Media]:
    soup = _fetch_html(f"https://www.instagram.com/{kind}/{code}/")
    video = _meta(soup, "og:video:secure_url") or _meta(soup, "og:video")
    image = _meta(soup, "og:image")
    if video:
        return [Media("video", image or None, f"{code}.mp4", video, "Reel" if kind == "reel" else "Video", "og")]
    if image:
        return [Media("image", image, f"{code}.jpg", image, "Photo", "og")]
    raise IGError(LOGIN_MSG, 429)


def _resolve_post(kind: str, code: str) -> IGInfo:
    err = None
    media: list[Media] = []
    try:
        media = _ytdlp_media(kind, code)
    except IGError as exc:
        err = exc
    if not media:
        try:
            media = _og_media(kind, code)
        except IGError as exc:
            raise (err if err and err.status in (403, 404) else exc)
    for i, m in enumerate(media):
        m.index = i
    canonical = f"https://www.instagram.com/{kind}/{code}/"
    return IGInfo(key=f"post:{code}", kind="post", title=f"Instagram {media[0].label.lower()} {code}",
                  canonical=canonical, media=media, post_url=canonical)


def _resolve_profile(username: str) -> IGInfo:
    pic, name = None, ""
    try:
        r = requests.get("https://i.instagram.com/api/v1/users/web_profile_info/", params={"username": username},
                         headers={"User-Agent": WEB_UA, "x-ig-app-id": "936619743392459"}, timeout=20)
        if r.status_code == 404:
            raise IGError("No Instagram account with that username.", 404)
        if r.status_code == 200:
            user = (r.json().get("data") or {}).get("user") or {}
            pic = user.get("profile_pic_url_hd") or user.get("profile_pic_url")
            name = user.get("full_name") or ""
    except IGError:
        raise
    except (requests.RequestException, ValueError):
        pass
    if not pic:
        pic = _meta(_fetch_html(f"https://www.instagram.com/{username}/"), "og:image")
    if not pic:
        raise IGError(LOGIN_MSG, 429)
    title = f"{name} (@{username})" if name else f"@{username}"
    media = [Media("dp", pic, f"{username}_profile.jpg", pic, "Profile photo", "api", 0)]
    return IGInfo(key=f"profile:{username}", kind="profile", title=title,
                  canonical=f"https://www.instagram.com/{username}/", media=media)


_cache: dict[str, tuple[float, IGInfo]] = {}
_lock = threading.Lock()


def resolve(raw: str) -> IGInfo:
    kind, ident = parse_input(raw)
    key = f"post:{ident[1]}" if kind == "post" else f"profile:{ident}"
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
    info = _resolve_post(*ident) if kind == "post" else _resolve_profile(ident)
    with _lock:
        if len(_cache) > 300:
            _cache.clear()
        _cache[key] = (time.time(), info)
    return info


def _direct(url: str, out_dir: str, filename: str) -> str:
    if not CDN_HOST.search(urlparse(url).hostname or ""):
        raise IGError("Blocked an unexpected download address.", 400)
    path = os.path.join(out_dir, filename)
    try:
        with requests.get(url, headers={"User-Agent": WEB_UA}, stream=True, timeout=30) as r:
            r.raise_for_status()
            size = 0
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise IGError("File is too large.", 413)
                    f.write(chunk)
    except requests.RequestException as exc:
        raise IGError("Instagram wouldn't serve the file. Try again in a moment.", 502) from exc
    return path


def download_item(info: IGInfo, index: int, out_dir: str) -> str:
    if not 0 <= index < len(info.media):
        raise IGError("That item doesn't exist.", 404)
    m = info.media[index]
    if m.url and m.via in ("og", "api") or (m.kind == "image" and m.url):
        return _direct(m.url, out_dir, m.filename)
    opts = {"quiet": True, "no_warnings": True, "socket_timeout": 20, "retries": 2,
            "outtmpl": os.path.join(out_dir, os.path.splitext(m.filename)[0] + ".%(ext)s"),
            "playlist_items": str(index + 1), "merge_output_format": "mp4"}
    ff = _ffmpeg()
    opts["format"] = "bv*+ba/b" if ff else "best[ext=mp4]/best"
    if ff:
        opts["ffmpeg_location"] = ff
    if COOKIES:
        opts["cookiefile"] = COOKIES
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(info.post_url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise _friendly(exc) from exc
    files = [f for f in glob.glob(os.path.join(out_dir, "*")) if not f.endswith((".part", ".ytdl"))]
    if not files:
        raise IGError("Couldn't download this video.", 502)
    return max(files, key=os.path.getsize)
