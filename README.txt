Video Saver (YouTube)
=====================
Paste a YouTube link, choose MP4 (with quality) or MP3, and download.

Windows: install Python 3.10+ (tick "Add to PATH"), then double-click run.bat.
Other OS: python3 -m venv venv && source venv/bin/activate
          pip install -r requirements.txt && python app.py
Opens at http://127.0.0.1:5000

Tips
- Install Node.js (nodejs.org) for best YouTube compatibility; yt-dlp uses it.
- If downloads start failing, update:  pip install -U yt-dlp
- ffmpeg is bundled (imageio-ffmpeg), nothing else to install.
- Only download videos you own, that are Creative Commons / public domain, or
  that you have permission to save. YouTube's terms restrict other downloads.

Render
- Build: pip install -r requirements.txt   Start: see render.yaml   Health: /healthz
- YouTube often blocks cloud IPs ("confirm you're not a bot"). If so, run locally,
  or export a cookies.txt from a logged-in browser, add it as a Render Secret File
  and set env var YT_COOKIES_FILE to its path (e.g. /etc/secrets/cookies.txt).

Settings (env vars): PORT, HOST, NO_BROWSER=1, MAX_DURATION_SECONDS (default 10800)
