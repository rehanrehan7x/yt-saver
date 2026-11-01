"""YouTube thumbnails. Uses YouTube's public image server (i.ytimg.com) only: no yt-dlp, no login, no cookies."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

import requests

ID_RE = re.compile(r"^[\w-]{11}$")
YT_HOST = re.compile(r"^(?:[\w-]+\.)?youtube(?:-nocookie)?\.com$", re.I)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAX_BYTES = 6 * 1024 * 1024

# key used in the image address, label for people, width, height
SIZES = [
    ("maxresdefault", "Maximum quality (HD)", 0, 0),
    ("sddefault", "SD (640 x 480)", 640, 480),
    ("hqdefault", "High (480 x 360)", 480, 360),
    ("mqdefault", "Medium (320 x 180)", 320, 180),
    ("default", "Small (120 x 90)", 120, 90),
]
KEYS = {s[0] for s in SIZES}


class ThumbError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def video_id(raw: str) -> str:
    """Pull the 11-character video ID out of a YouTube link, or accept a bare ID."""
    raw = (raw or "").strip()
    if not raw:
        raise ThumbError("Paste a YouTube video link first.")
    if ID_RE.match(raw):
        return raw
    m = re.search(r"(?:https?://)?[^\s\"'<>]+", raw)
    text = m.group(0) if m else raw
    if not text.lower().startswith("http"):
        text = "https://" + text
    u = urlparse(text)
    host = (u.hostname or "").lower()
    vid = ""
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif YT_HOST.match(host):
        parts = [p for p in u.path.split("/") if p]
        if parts and parts[0] in ("embed", "shorts", "live", "v", "e") and len(parts) > 1:
            vid = parts[1]
        else:
            vid = (parse_qs(u.query).get("v") or [""])[0]
    else:
        raise ThumbError("That isn't a YouTube link.")
    if not ID_RE.match(vid):
        raise ThumbError("That YouTube link looks incomplete. Paste the full video link.")
    return vid


def image_url(vid: str, key: str) -> str:
    return f"https://i.ytimg.com/vi/{vid}/{key}.jpg"


def _exists(url: str) -> bool:
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=6, allow_redirects=False)
        if r.status_code in (405, 501):
            with requests.get(url, headers={"User-Agent": UA}, timeout=8, stream=True) as g:
                return g.status_code == 200
        return r.status_code == 200
    except requests.RequestException:
        return False


def lookup(raw: str) -> dict:
    vid = video_id(raw)
    with ThreadPoolExecutor(max_workers=len(SIZES)) as pool:
        found = list(pool.map(lambda s: _exists(image_url(vid, s[0])), SIZES))
    items = [{"key": k, "label": label, "width": w, "height": h, "preview": image_url(vid, k),
              "filename": f"youtube-{vid}-{k}.jpg"}
             for (k, label, w, h), ok in zip(SIZES, found) if ok]
    if not items:
        raise ThumbError("No thumbnail found. The video may be private, deleted, or the link may be wrong.", 404)
    return {"id": vid, "items": items}


def fetch(vid: str, key: str) -> tuple[bytes, str]:
    if not ID_RE.match(vid or "") or key not in KEYS:
        raise ThumbError("That thumbnail doesn't exist.", 404)
    try:
        with requests.get(image_url(vid, key), headers={"User-Agent": UA}, timeout=12, stream=True) as r:
            if r.status_code != 200:
                raise ThumbError("That thumbnail size isn't available for this video.", 404)
            data, size = [], 0
            for chunk in r.iter_content(1 << 16):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ThumbError("The image is too large.", 413)
                data.append(chunk)
            return b"".join(data), r.headers.get("Content-Type", "image/jpeg")
    except requests.RequestException as exc:
        raise ThumbError("Couldn't reach YouTube's image server. Try again in a moment.", 502) from exc
