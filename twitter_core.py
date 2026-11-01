"""X (Twitter) helper: videos, GIFs and photos of public tweets.

Uses the same public data X serves for embedded tweets (the "syndication" endpoint). If that fails for a video,
yt-dlp is tried. Protected accounts, deleted tweets and sensitive-content tweets are not available this way.
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

log = logging.getLogger("xsaver")

HOSTS = re.compile(r"^(?:www\.|mobile\.)?(?:twitter\.com|x\.com|fxtwitter\.com|vxtwitter\.com|fixupx\.com)$", re.I)
CDN_HOST = re.compile(r"(?:^|\.)twimg\.com$", re.I)
ID_RE = re.compile(r"/(?:status|statuses)/(\d{5,25})")
BOT_UA = "Googlebot"
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0 Safari/537.36")
MAX_BYTES = 600 * 1024 * 1024


class XError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Item:
    kind: str                     # "video", "gif" or "photo"
    thumbnail: str | None
    filename: str
    label: str
    size: str = ""
    variants: list = field(default_factory=list)   # videos: [{"url", "label", "size", "bitrate"}]
    url: str | None = None                          # photos: original-size url
    index: int = 0


@dataclass
class XInfo:
    tweet_id: str
    title: str
    items: list[Item] = field(default_factory=list)

    def public(self) -> dict:
        return {"title": self.title, "items": [
            {"index": it.index, "kind": it.kind, "label": it.label, "thumbnail": it.thumbnail, "filename": it.filename,
             "size": it.size, "qualities": [v["label"] for v in it.variants]} for it in self.items]}


# ---------------------------------------------------------------- the embed token (a JavaScript number in base 36)
def _js_radix(value: float, radix: int = 36) -> str:
    """Number.prototype.toString(radix) as V8 does it, for positive numbers below 2**53."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    integer = math.floor(value)
    fraction = value - integer
    delta = max(math.nextafter(0.0, 1.0), 0.5 * (math.nextafter(value, math.inf) - value))
    digits: list[int] = []
    if fraction >= delta:
        while True:
            fraction *= radix
            delta *= radix
            digit = int(fraction)
            digits.append(digit)
            fraction -= digit
            if fraction > 0.5 or (fraction == 0.5 and (digit & 1)):
                if fraction + delta > 1:
                    while True:  # round up, carrying into earlier digits
                        if not digits:
                            integer += 1
                            break
                        last = digits.pop()
                        if last + 1 < radix:
                            digits.append(last + 1)
                            break
                    break
            if not fraction >= delta:
                break
    whole, n = "", int(integer)
    while True:
        n, rem = divmod(n, radix)
        whole = chars[rem] + whole
        if n <= 0:
            break
    return whole + ("." + "".join(chars[d] for d in digits) if digits else "")


def syndication_token(tweet_id: str) -> str:
    # ((Number(id) / 1e15) * Math.PI).toString(36).replace(/(0+|\.)/g, '')
    return re.sub(r"0+|\.", "", _js_radix((int(tweet_id) / 1e15) * math.pi, 36))


# ---------------------------------------------------------------- input
def parse_input(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise XError("Paste the link of a tweet.")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").lower()
    if host == "t.co":
        raise XError("Short t.co links aren't supported. Open the tweet and copy its address from the browser.")
    if not HOSTS.match(host):
        raise XError("That isn't a Twitter or X link.")
    m = ID_RE.search(urlparse(raw).path)
    if not m:
        raise XError("Paste the link of a single tweet. It contains /status/ followed by numbers.")
    return m.group(1)


# ---------------------------------------------------------------- fetching and parsing
def _fetch_tweet(tweet_id: str) -> dict:
    try:
        r = requests.get("https://cdn.syndication.twimg.com/tweet-result",
                         params={"id": tweet_id, "token": syndication_token(tweet_id), "lang": "en"},
                         headers={"User-Agent": BOT_UA}, timeout=12)
    except requests.RequestException as exc:
        raise XError("Couldn't reach X. Please try again in a moment.", 502) from exc
    log.warning("X syndication %s -> HTTP %s", tweet_id, r.status_code)
    if r.status_code == 404:
        raise XError("This tweet wasn't found. It may have been deleted.", 404)
    if r.status_code != 200 or not r.content:
        raise XError("X didn't return this tweet right now. Please try again later.", 502)
    try:
        return r.json()
    except ValueError as exc:
        raise XError("X didn't return this tweet right now. Please try again later.", 502) from exc


def _resolution(url: str) -> tuple[int, int]:
    m = re.search(r"/(\d{2,5})x(\d{2,5})/", url)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", name or "") or "tweet"


def _parse(data: dict, tweet_id: str) -> XInfo:
    if data.get("__typename") == "TweetTombstone" or data.get("tombstone"):
        raise XError("This tweet isn't available. It may be deleted, from a protected account, or marked sensitive.", 404)
    user = data.get("user") or {}
    handle = _safe(user.get("screen_name", ""))
    text = re.sub(r"\s+", " ", (data.get("text") or "")).strip()
    title = f"@{handle}: {text[:80]}{'…' if len(text) > 80 else ''}" if handle != "tweet" else (text[:90] or f"Tweet {tweet_id}")
    media = data.get("mediaDetails") or []
    items: list[Item] = []
    for m in media:
        kind = m.get("type")
        n = len(items) + 1
        suffix = f"_{n}" if len(media) > 1 else ""
        base = m.get("media_url_https") or ""
        if kind == "photo" and base:
            ext = os.path.splitext(urlparse(base).path)[1].lstrip(".").lower() or "jpg"
            info = m.get("original_info") or {}
            size = f"{info['width']}\u00d7{info['height']}" if info.get("width") and info.get("height") else ""
            items.append(Item("photo", f"{base}?format={ext}&name=medium", f"{handle}_{tweet_id}{suffix}.{ext}", "Photo", size,
                              url=f"{base}?format={ext}&name=orig"))
        elif kind in ("video", "animated_gif"):
            raw = [v for v in ((m.get("video_info") or {}).get("variants") or [])
                   if v.get("content_type") == "video/mp4" and v.get("url")]
            raw.sort(key=lambda v: v.get("bitrate") or 0, reverse=True)
            variants = []
            for v in raw:
                w, h = _resolution(v["url"])
                variants.append({"url": v["url"], "label": f"{min(w, h)}p" if w and h else "Best", "bitrate": v.get("bitrate") or 0,
                                 "size": f"{w}\u00d7{h}" if w and h else ""})
            if variants:
                items.append(Item("gif" if kind == "animated_gif" else "video", base or None,
                                  f"{handle}_{tweet_id}{suffix}.mp4", "GIF" if kind == "animated_gif" else "Video",
                                  variants[0]["size"], variants))
    for i, it in enumerate(items):
        it.index = i
    return XInfo(tweet_id, title, items)


def _ytdlp_info(tweet_id: str) -> XInfo:
    """Fallback for videos when the embed data isn't available."""
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 15, "retries": 0}) as ydl:
            data = ydl.extract_info(f"https://x.com/i/status/{tweet_id}", download=False)
    except Exception as exc:  # noqa: BLE001
        raise XError("Couldn't read this tweet. It may be private, deleted or contain no video.", 502) from exc
    entries = [e for e in (data.get("entries") or [data]) if e]
    items = []
    for i, e in enumerate(entries):
        variants = []
        for f in sorted((e.get("formats") or []), key=lambda f: (f.get("height") or 0, f.get("tbr") or 0), reverse=True):
            if f.get("ext") == "mp4" and f.get("vcodec") not in (None, "none") and f.get("protocol") in ("https", "http") and f.get("url"):
                h = f.get("height") or 0
                variants.append({"url": f["url"], "label": f"{h}p" if h else "Best", "bitrate": int((f.get("tbr") or 0) * 1000),
                                 "size": f"{f.get('width')}\u00d7{h}" if f.get("width") and h else ""})
        if variants:
            suffix = f"_{len(items) + 1}" if len(entries) > 1 else ""
            items.append(Item("video", e.get("thumbnail"), f"{_safe(e.get('uploader_id') or e.get('uploader'))}_{tweet_id}{suffix}.mp4",
                              "Video", variants[0]["size"], variants, index=len(items)))
    return XInfo(tweet_id, (data.get("title") or f"Tweet {tweet_id}")[:90], items)


_cache: dict[str, tuple[float, XInfo]] = {}
_lock = threading.Lock()


def resolve(raw: str) -> XInfo:
    tweet_id = parse_input(raw)
    with _lock:
        hit = _cache.get(tweet_id)
        if hit and time.time() - hit[0] < 300:
            return hit[1]
    info, error = None, None
    try:
        info = _parse(_fetch_tweet(tweet_id), tweet_id)
    except XError as exc:
        error = exc
    if info is not None and not info.items and error is None:
        # X answered normally and the tweet simply has no media (it may be text only, or quote another tweet).
        raise XError("This tweet has no video, GIF or photo to download. If it quotes another tweet, paste the quoted tweet's link instead.", 404)
    if (info is None or not info.items) and not (error and error.status == 404):
        try:
            fallback = _ytdlp_info(tweet_id)
            if fallback.items:
                info = fallback
        except XError as exc:
            error = error or exc
    if info is None or not info.items:
        if error:
            raise error
        raise XError("This tweet has no video, GIF or photo we can download.", 404)
    with _lock:
        if len(_cache) > 300:
            _cache.clear()
        _cache[tweet_id] = (time.time(), info)
    return info


# ---------------------------------------------------------------- files
def _check_cdn(url: str) -> None:
    if not CDN_HOST.search(urlparse(url).hostname or ""):
        raise XError("Blocked an unexpected download address.", 400)


def download_item(info: XInfo, index: int, variant: int, out_dir: str) -> str:
    if not 0 <= index < len(info.items):
        raise XError("That item doesn't exist.", 404)
    it = info.items[index]
    if it.kind == "photo":
        url = it.url
    else:
        if not 0 <= variant < len(it.variants):
            variant = 0
        url = it.variants[variant]["url"]
    _check_cdn(url)
    path = os.path.join(out_dir, it.filename)
    try:
        with requests.get(url, headers={"User-Agent": WEB_UA}, stream=True, timeout=30) as r:
            r.raise_for_status()
            size = 0
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise XError("File is too large.", 413)
                    f.write(chunk)
    except requests.RequestException as exc:
        raise XError("X wouldn't serve the file. Try again in a moment.", 502) from exc
    return path


def fetch_preview(info: XInfo, index: int) -> tuple[bytes, str]:
    if not 0 <= index < len(info.items):
        raise XError("That item doesn't exist.", 404)
    url = info.items[index].thumbnail
    if not url:
        raise XError("No preview available.", 404)
    _check_cdn(url)
    data = b""
    try:
        with requests.get(url, headers={"User-Agent": WEB_UA}, stream=True, timeout=15) as r:
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                raise XError("Preview unavailable.", 502)
            for chunk in r.iter_content(1 << 16):
                data += chunk
                if len(data) > 15 * 1024 * 1024:
                    raise XError("Preview too large.", 413)
    except requests.RequestException as exc:
        raise XError("Preview unavailable.", 502) from exc
    return data, ctype
