import pyotp
import os, time
from flask import Flask, render_template_string, request
from instagrapi import Client
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

HTML = """
<!doctype html>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Instagram Unliker</title>
<style>
 body{font-family:system-ui;margin:24px;max-width:820px}
 input,button{padding:8px;font-size:16px}
 textarea{width:100%;height:300px}
 .box{border:1px solid #ddd;padding:16px;border-radius:10px}
 .muted{color:#666}
 .row{display:flex;gap:12px;flex-wrap:wrap}
 .row>div{flex:1;min-width:260px}
</style>
<h2>Instagram Unliker</h2>
<p class="muted">We do not store credentials or sessions. Use at your own risk. Keep batches small (20–50).</p>
<div class="box">
  <form method="post">
    <h3>Login</h3>
    <div class="row">
      <div>
        <label>Use sessionid (recommended):</label><br>
        <input name="sid" style="width:520px" placeholder="Paste your sessionid from browser cookies">
      </div>
    </div>
    <p class="muted">— OR —</p>
    <div class="row">
      <div><label>Username</label><br><input name="user" style="width:260px"></div>
      <div><label>Password</label><br><input name="pass" type="password" style="width:260px"></div>
      <div><label>TOTP Secret (if 2FA)</label><br><input name="totp" placeholder="Base32 key, optional" style="width:260px"></div>
    </div>
    <h3>Options</h3>
    <div class="row">
      <div><label>Unlike up to</label><br><input name="count" type="number" value="30" min="1" max="200"></div>
      <div><label>Delay (seconds)</label><br><input name="delay" type="number" value="1" min="0" step="0.5"></div>
    </div>
    <br>
    <button type="submit">Start</button>
  </form>
</div>
{% if log %}
  <h3>Log</h3>
  <textarea readonly>{{ log }}</textarea>
{% endif %}
<p class="muted">Tip: sessionid is in DevTools → Application/Storage → Cookies → https://www.instagram.com → sessionid.</p>
"""


def iter_liked_media_ids(client, limit):
    ids, max_id = [], None
    while len(ids) < limit:
        params = {"max_id": max_id} if max_id else {}
        data = client.private_request("feed/liked/", params=params)
        items = (data or {}).get("items", []) or []
        if not items: break
        for item in items:
            media = item.get("media", item) or {}
            pk = str(media.get("pk") or media.get("id") or "").strip()
            if pk:
                ids.append(pk)
                if len(ids) >= limit: break
        max_id = (data or {}).get("next_max_id")
        if not max_id: break
    return ids

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev")
    limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute", "100 per day"])

    @app.after_request
    def no_cache(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/", methods=["GET","POST"])
    @limiter.limit("6/minute")
    def index():
        log = ""
        if request.method == "POST":
            sid = (request.form.get("sid") or "").strip()
            try: count = min(max(int(request.form.get("count", 30)), 1), 200)
            except: count = 30
            try: delay = max(float(request.form.get("delay", 1.0)), 0.0)
            except: delay = 1.0

            if not sid or len(sid) < 20:
                log += "Error: Invalid sessionid.\n"
                return render_template_string(HTML, log=log)

            try:
                c = Client(); c.delay_range = [1, 3]
                log += "Logging in with sessionid…\n"
                c.login_by_sessionid(sid)   # ephemeral: we don’t dump settings

                log += "Fetching liked posts…\n"
                ids = iter_liked_media_ids(c, count)
                if not ids:
                    log += "No liked posts found.\n"
                else:
                    log += f"Found {len(ids)}. Unliking up to {count}…\n"
                    removed = 0
                    for mid in ids:
                        try:
                            c.media_unlike(mid)
                            removed += 1
                            log += f"{removed}: Unliked {mid}\n"
                            time.sleep(delay)
                        except Exception as e:
                            log += f"Stopped due to rate limit/API error: {e}\n"
                            break
                    log += f"Done. Unliked {removed} posts.\n"
            except Exception as e:
                log += f"Error: {e}\n"

        return render_template_string(HTML, log=log)
    return app

app = create_app()

if __name__ == "__main__":
    # For local testing

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

