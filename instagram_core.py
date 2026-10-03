"""Instagram helper: public reels / videos / photos and profile pictures."""
from __future__ import annotations

import glob, json, logging, os, re, shutil, tempfile, threading, time
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

LOOKUP_BUDGET = 40  # seconds for one whole lookup (Render cuts requests off near 100s)
PROXY = os.environ.get("IG_PROXY") or None  # e.g. http://user:pass@host:port (optional)
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0 Safari/537.36")

APP_UA = ("Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; samsung; SM-G991B; o1s; "
          "exynos2100; en_US; 458229237)")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

LOGIN_MSG = ("Instagram is limiting our server right now, so we couldn't fetch this. "
             "Please try again in a few minutes. Private posts can't be downloaded.")


def _load_cookie_rows(path: str) -> list[tuple]:
    """Parse a Netscape cookies.txt ourselves (keeps #HttpOnly_ cookies like sessionid)."""
    rows = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#HttpOnly_"):
                    line = line[len("#HttpOnly_"):]
                elif not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    rows.append((parts[0], parts[2], parts[5], parts[6], parts[4]))  # domain, path, name, value, expiry
    except OSError:
        pass
    return rows


def _session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": DESKTOP_UA, "Accept-Language": "en-US,en;q=0.9"})
    if PROXY:
        sess.proxies = {"http": PROXY, "https": PROXY}
    if COOKIES:
        for domain, path, name, value, _exp in _load_cookie_rows(COOKIES):
            sess.cookies.set(name, value, domain=domain, path=path)
    return sess


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
    """Return ("post", (kind, code)), ("story", username) or ("profile", username)."""
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
            if len(parts) >= 2 and parts[1].lower() != "highlights" and USERNAME.match(parts[1]):
                return "story", parts[1].lower()
            raise IGError("Highlights aren't supported yet. Paste a story link or a username.")
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


def _get_text(url: str, ua: str, timeout: int = 12) -> str:
    try:
        r = _session().get(url, headers={"User-Agent": ua}, timeout=timeout)
    except requests.RequestException as exc:
        raise IGError("Couldn't reach Instagram. Please try again.", 502) from exc
    if r.status_code == 404:
        raise IGError("This post or profile wasn't found.", 404)
    return r.text


def _fetch_html(url: str) -> BeautifulSoup:
    return BeautifulSoup(_get_text(url, BOT_UA), "html.parser")


def _request(url: str, params=None, ua: str = APP_UA, extra=None, web: bool = False):
    sess = _session()
    headers = {"User-Agent": DESKTOP_UA if web else ua, "x-ig-app-id": "936619743392459", "Accept": "*/*"}
    token = sess.cookies.get("csrftoken")
    if token:
        headers["x-csrftoken"] = token
    if web:  # match what instagram.com itself sends, so web cookies are accepted
        headers.update({"x-requested-with": "XMLHttpRequest", "x-asbd-id": "129477",
                        "x-ig-www-claim": "0", "referer": "https://www.instagram.com/"})
    if extra:
        headers.update(extra)
    return sess.get(url, params=params, headers=headers, timeout=12)


def _api_get(url: str, params=None, ua: str = APP_UA, extra=None, web: bool = False):
    """GET an Instagram JSON endpoint. Returns (status, data) and logs the HTTP code."""
    short = url.split("?")[0].replace("https://", "")
    try:
        r = _request(url, params, ua, extra, web)
    except requests.RequestException as exc:
        log.warning("IG api %s failed: %r", short, exc)
        return None, None
    log.warning("IG api %s -> HTTP %s", short, r.status_code)
    try:
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError:
        return r.status_code, None


def _shortcode_to_id(code: str) -> int:
    code = code[:11] if len(code) > 28 else code
    n = 0
    for ch in code:
        n = n * 64 + ALPHABET.index(ch)
    return n


def _api_media(kind: str, code: str) -> list[Media]:
    """Logged-in method (needs cookies): works for photos, carousels and videos."""
    if not COOKIES:
        return []
    try:
        media_id = _shortcode_to_id(code)
    except ValueError:
        return []
    status, items = None, []
    for host, web in (("www.instagram.com", True), ("i.instagram.com", False)):
        status, data = _api_get(f"https://{host}/api/v1/media/{media_id}/info/", web=web)
        items = (data or {}).get("items") or []
        if items or status == 404:
            break
    if not items:
        if status == 404:
            raise IGError("This post isn't available. It may be private or deleted.", 404)
        return []
    item = items[0]
    nodes = item.get("carousel_media") or [item]
    out = []
    for i, n in enumerate(nodes):
        suffix = f"_{i + 1}" if len(nodes) > 1 else ""
        video = ((n.get("video_versions") or [{}])[0]).get("url")
        image = (((n.get("image_versions2") or {}).get("candidates") or [{}])[0]).get("url")
        if video:
            out.append(Media("video", image, f"{code}{suffix}.mp4", video, "Reel" if kind == "reel" else "Video", "og", i))
        elif image:
            out.append(Media("image", image, f"{code}{suffix}.jpg", image, "Photo", "og", i))
    return out


def _unescape(v: str) -> str:
    for _ in range(3):
        v = v.replace("\\\\", "\\")
    return v.replace("\\u0026", "&").replace("\\/", "/").replace("&amp;", "&")


def _grab(html: str, key: str) -> str:
    m = re.search(r'"?' + key + r'\\*"\s*:\s*\\*"([^"]+?)\\*"', html)
    return _unescape(m.group(1)) if m else ""


def _find_nodes(obj):
    if isinstance(obj, dict):
        side = obj.get("edge_sidecar_to_children")
        if isinstance(side, dict):
            for e in side.get("edges", []):
                n = e.get("node") if isinstance(e, dict) else None
                if isinstance(n, dict) and (n.get("video_url") or n.get("display_url")):
                    yield n
            return
        if obj.get("video_url") or obj.get("display_url"):
            yield obj
            return
        for v in obj.values():
            yield from _find_nodes(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_nodes(v)


def _nodes_from_html(html: str) -> list[dict]:
    blobs = []
    m = re.search(r'"contextJSON"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
    if m:
        try:
            blobs.append(json.loads(json.loads('"' + m.group(1) + '"')))
        except ValueError:
            pass
    for m in re.finditer(r"__additionalDataLoaded\(\s*'[^']*'\s*,\s*(\{.*?\})\s*\)\s*;", html, re.S):
        try:
            blobs.append(json.loads(m.group(1)))
        except ValueError:
            pass
    for blob in blobs:
        nodes = list(_find_nodes(blob))[:10]
        if nodes:
            return nodes
    video, image = _grab(html, "video_url"), _grab(html, "display_url")
    return [{"video_url": video, "display_url": image}] if (video or image) else []


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
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 10, "retries": 0,
            "extractor_retries": 0}
    if COOKIES:
        opts["cookiefile"] = COOKIES
    if PROXY:
        opts["proxy"] = PROXY
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


def _embed_media(kind: str, code: str) -> list[Media]:
    """No-login method: the public embed page of a post lists its media."""
    html = _get_text(f"https://www.instagram.com/{'reel' if kind == 'reel' else 'p'}/{code}/embed/captioned/", DESKTOP_UA)
    nodes = _nodes_from_html(html)
    out = []
    for i, n in enumerate(nodes):
        suffix = f"_{i + 1}" if len(nodes) > 1 else ""
        video, image = n.get("video_url"), n.get("display_url")
        if video:
            out.append(Media("video", image or None, f"{code}{suffix}.mp4", video,
                             "Reel" if kind == "reel" else "Video", "og", i))
        elif image:
            out.append(Media("image", image, f"{code}{suffix}.jpg", image, "Photo", "og", i))
    return out


def _resolve_post(kind: str, code: str) -> IGInfo:
    # With a logged-in cookie or proxy, yt-dlp is the most reliable; otherwise try the no-login methods first.
    steps = [_api_media, _ytdlp_media, _embed_media, _og_media] if (COOKIES or PROXY) else [_embed_media, _og_media, _ytdlp_media]
    media: list[Media] = []
    errors: list[IGError] = []
    deadline = time.time() + LOOKUP_BUDGET
    for step in steps:
        if time.time() > deadline - 5:
            log.warning("IG %s: time budget used up, skipping %s", code, step.__name__)
            continue
        t0 = time.time()
        try:
            media = step(kind, code)
            log.warning("IG %s: %s -> %d item(s) in %.1fs", code, step.__name__, len(media), time.time() - t0)
        except IGError as exc:
            errors.append(exc)
            log.warning("IG %s: %s failed in %.1fs: %s", code, step.__name__, time.time() - t0, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("IG %s: %s crashed in %.1fs: %r", code, step.__name__, time.time() - t0, exc)
        if media:
            break
    if not media:
        hard = [e for e in errors if e.status in (403, 404)]
        raise (hard[0] if hard else IGError(LOGIN_MSG, 429))
    for i, m in enumerate(media):
        m.index = i
    canonical = f"https://www.instagram.com/{kind}/{code}/"
    return IGInfo(key=f"post:{code}", kind="post", title=f"Instagram {media[0].label.lower()} {code}",
                  canonical=canonical, media=media, post_url=canonical)


def _lookup_user(username: str) -> dict:
    """Find an account's id, name and picture. Tries several endpoints; {} if all are blocked."""
    attempts = [("https://www.instagram.com/api/v1/users/web_profile_info/", True,
                 {"referer": f"https://www.instagram.com/{username}/"}),
                ("https://i.instagram.com/api/v1/users/web_profile_info/", False, {})]
    for url, web, extra in attempts:
        status, data = _api_get(url, {"username": username}, extra=extra, web=web)
        if status == 404:
            raise IGError("No Instagram account with that username.", 404)
        user = ((data or {}).get("data") or {}).get("user") or {}
        if user:
            return {"id": str(user.get("id") or user.get("pk") or ""), "name": user.get("full_name") or "",
                    "pic": user.get("profile_pic_url_hd") or user.get("profile_pic_url")}
    _, data = _api_get("https://www.instagram.com/web/search/topsearch/",
                       {"context": "blended", "query": username, "include_reel": "true"}, web=True)
    for entry in (data or {}).get("users") or []:
        u = entry.get("user") or {}
        if (u.get("username") or "").lower() == username:
            return {"id": str(u.get("pk") or u.get("id") or ""), "name": u.get("full_name") or "",
                    "pic": u.get("profile_pic_url")}
    return {}


def _resolve_profile(username: str) -> IGInfo:
    user = _lookup_user(username)
    pic, name, uid = user.get("pic"), user.get("name", ""), user.get("id")
    if uid and COOKIES:  # try for the full-size picture
        for host, web in (("www.instagram.com", True), ("i.instagram.com", False)):
            _, data = _api_get(f"https://{host}/api/v1/users/{uid}/info/", web=web)
            hd = (((data or {}).get("user") or {}).get("hd_profile_pic_url_info") or {}).get("url")
            if hd:
                pic = hd
                break
    if not pic:  # public embed page of the profile
        try:
            html = _get_text(f"https://www.instagram.com/{username}/embed/", DESKTOP_UA)
            pic = _grab(html, "profile_pic_url_hd") or _grab(html, "profile_pic_url")
        except IGError as exc:
            if exc.status == 404:
                raise
    if not pic:  # the profile page itself (we are logged in, so it carries the data)
        try:
            html = _get_text(f"https://www.instagram.com/{username}/", DESKTOP_UA)
            pic = _grab(html, "profile_pic_url_hd") or _grab(html, "profile_pic_url")
            if not pic:
                pic = _meta(BeautifulSoup(html, "html.parser"), "og:image")
        except IGError as exc:
            if exc.status == 404:
                raise
    if not pic:  # social-preview tags (works for private accounts too, usually smaller)
        try:
            pic = _meta(_fetch_html(f"https://www.instagram.com/{username}/"), "og:image")
        except IGError as exc:
            if exc.status == 404:
                raise
    if not pic:
        raise IGError(LOGIN_MSG, 429)
    title = f"{name} (@{username})" if name else f"@{username}"
    media = [Media("dp", pic, f"{username}_profile.jpg", pic, "Profile photo", "api", 0)]
    return IGInfo(key=f"profile:{username}", kind="profile", title=title,
                  canonical=f"https://www.instagram.com/{username}/", media=media)


def _resolve_story(username: str) -> IGInfo:
    if not COOKIES:
        raise IGError("Story downloads aren't available on this server right now.", 503)
    uid = _lookup_user(username).get("id")
    if not uid:
        raise IGError(LOGIN_MSG, 429)
    items = []
    for host, web in (("www.instagram.com", True), ("i.instagram.com", False)):
        _, data = _api_get(f"https://{host}/api/v1/feed/reels_media/", {"reel_ids": uid}, web=web)
        data = data or {}
        reel = (data.get("reels") or {}).get(str(uid)) or ((data.get("reels_media") or [None])[0]) or {}
        items = reel.get("items") or []
        if items:
            break
    media = []
    for i, it in enumerate(items):
        video = ((it.get("video_versions") or [{}])[0]).get("url")
        image = (((it.get("image_versions2") or {}).get("candidates") or [{}])[0]).get("url")
        if video:
            media.append(Media("video", image, f"{username}_story_{i + 1}.mp4", video, "Story", "og", len(media)))
        elif image:
            media.append(Media("image", image, f"{username}_story_{i + 1}.jpg", image, "Story", "og", len(media)))
    if not media:
        raise IGError("No active stories right now. Stories vanish after 24 hours, and private accounts can't be downloaded.", 404)
    n = len(media)
    return IGInfo(key=f"story:{username}", kind="story", title=f"@{username}: {n} active {'story' if n == 1 else 'stories'}",
                  canonical=f"https://www.instagram.com/stories/{username}/", media=media)


_cache: dict[str, tuple[float, IGInfo]] = {}
_lock = threading.Lock()


def resolve(raw: str, mode: str = "auto") -> IGInfo:
    kind, ident = parse_input(raw)
    if kind == "profile" and mode == "story":
        kind = "story"
    key = f"post:{ident[1]}" if kind == "post" else f"{kind}:{ident}"
    ttl = 240 if kind == "story" else 600
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    if kind == "post":
        info = _resolve_post(*ident)
    elif kind == "story":
        info = _resolve_story(ident)
    else:
        info = _resolve_profile(ident)
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
    if PROXY:
        opts["proxy"] = PROXY
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(info.post_url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise _friendly(exc) from exc
    files = [f for f in glob.glob(os.path.join(out_dir, "*")) if not f.endswith((".part", ".ytdl"))]
    if not files:
        raise IGError("Couldn't download this video.", 502)
    return max(files, key=os.path.getsize)


def _cookie_status() -> dict:
    rows = _load_cookie_rows(COOKIES) if COOKIES else []
    names = sorted({r[2] for r in rows})
    return {"file_loaded": bool(COOKIES), "cookie_count": len(rows), "names": names,
            "has_sessionid": "sessionid" in names, "has_csrftoken": "csrftoken" in names,
            "has_ds_user_id": "ds_user_id" in names}


def debug_report(raw: str) -> dict:
    """Shows which step fails and why. Never prints cookie values."""
    rep = {"cookies": _cookie_status(), "proxy_set": bool(PROXY), "probes": []}

    def probe(label, url, **kw):
        try:
            r = _request(url, **kw)
            text = r.text or ""
            entry = {"step": label, "http": r.status_code, "bytes": len(text), "start": re.sub(r"\s+", " ", text[:160])}
            if "embed" in label:
                entry["has_media_keys"] = {k: (k in text) for k in ("contextJSON", "video_url", "display_url", "profile_pic_url")}
        except requests.RequestException as exc:
            entry = {"step": label, "error": repr(exc)[:160]}
        rep["probes"].append(entry)

    kind, ident = parse_input(raw)
    if kind == "post":
        k, code = ident
        try:
            mid = _shortcode_to_id(code)
            probe("web media api", f"https://www.instagram.com/api/v1/media/{mid}/info/", web=True)
            probe("app media api", f"https://i.instagram.com/api/v1/media/{mid}/info/")
        except ValueError:
            rep["probes"].append({"step": "media api", "error": "bad shortcode"})
        probe("embed page", f"https://www.instagram.com/{'reel' if k == 'reel' else 'p'}/{code}/embed/captioned/", ua=DESKTOP_UA, web=True)
        probe("preview page (og)", f"https://www.instagram.com/{k}/{code}/", ua=BOT_UA)
    else:
        probe("web profile api", "https://www.instagram.com/api/v1/users/web_profile_info/", params={"username": ident}, web=True)
        probe("app profile api", "https://i.instagram.com/api/v1/users/web_profile_info/", params={"username": ident})
        probe("search api", "https://www.instagram.com/web/search/topsearch/", params={"context": "blended", "query": ident}, web=True)
        probe("profile embed page", f"https://www.instagram.com/{ident}/embed/", ua=DESKTOP_UA, web=True)
        probe("profile page", f"https://www.instagram.com/{ident}/", ua=DESKTOP_UA, web=True)
        probe("preview page (og)", f"https://www.instagram.com/{ident}/", ua=BOT_UA)
    return rep
