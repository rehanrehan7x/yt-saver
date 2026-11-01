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

Instagram (optional)
- Works best on your own computer. Instagram often blocks cloud servers.
- For better results export cookies from a logged-in browser (use a spare account, not your main one)
  and set IG_COOKIES_FILE to the cookies.txt path (on Render: a Secret File, /etc/secrets/ig_cookies.txt).

Instagram
- Public reels, photos and profile pictures only. Instagram often blocks cloud servers.
- Optional: export an Instagram cookies.txt from a spare account, add it as a Render Secret File and set
  IG_COOKIES_FILE=/etc/secrets/ig_cookies.txt. Use a throwaway account; Instagram may restrict it.

Making Instagram reliable on Render
- The app first tries several no-login methods. If Instagram still blocks the server, add ONE of:
  1) Cookies from a spare Instagram account: Render > Environment > Secret Files > ig_cookies.txt,
     then env var IG_COOKIES_FILE=/etc/secrets/ig_cookies.txt
  2) A residential proxy: env var IG_PROXY=http://user:pass@host:port (paid service)
- Private accounts: only the profile picture can be saved. Their posts cannot.
