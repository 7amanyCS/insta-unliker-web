import os
import time
# Safe import: don't crash if pyotp isn't installed
try:
    import pyotp
except ImportError:
    pyotp = None

from flask import Flask, request, render_template_string
from instagrapi import Client

HTML = """
<!DOCTYPE html>
<html>
<head><title>Insta Unliker</title></head>
<body>
  <h1>Insta Unliker</h1>
  <form method="post">
    <p>Session ID: <input type="text" name="sid"></p>
    <p>Username: <input type="text" name="user"></p>
    <p>Password: <input type="password" name="pass"></p>
    <p>TOTP Secret: <input type="text" name="totp" placeholder="If you use an authenticator app"></p>
    <p>Count: <input type="number" name="count" value="30" min="1" max="200"></p>
    <p>Delay: <input type="number" name="delay" value="1.0" step="0.1" min="0"></p>
    <p><input type="submit" value="Start"></p>
  </form>
  <pre>{{ log }}</pre>
</body>
</html>
"""

app = Flask(__name__)


def iter_liked_media_ids(client: Client, count: int = 30):
    """Fetch up to `count` liked media IDs."""
    ids = []
    for m in client.user_liked_medias(amount=count):
        ids.append(m.id)
    return ids


@app.route("/", methods=["GET", "POST"])
def index():
    log = ""
    if request.method == "POST":
        sid   = (request.form.get("sid") or "").strip()
        user  = (request.form.get("user") or "").strip()
        pw    = (request.form.get("pass") or "").strip()
        totps = (request.form.get("totp") or "").strip()

        # sanitize count & delay
        try:
            count = int(request.form.get("count", 30))
            count = max(1, min(count, 200))
        except Exception:
            count = 30
        try:
            delay = float(request.form.get("delay", 1.0))
            delay = max(0.0, delay)
        except Exception:
            delay = 1.0

        try:
            c = Client()
            c.delay_range = [1, 3]

            if sid:
                log += "Logging in with sessionid…\n"
                c.login_by_sessionid(sid)
            elif user and pw:
                log += "Logging in with username/password…\n"
                if totps:
                    if not pyotp:
                        log += "Error: TOTP secret provided but 'pyotp' is not installed on the server.\n"
                        return render_template_string(HTML, log=log)
                    code = pyotp.TOTP(totps).now()
                    log += "Using TOTP 2FA…\n"
                    c.login(user, pw, verification_code=code)
                else:
                    c.login(user, pw)
            else:
                log += "Error: Provide sessionid OR username/password.\n"
                return render_template_string(HTML, log=log)

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


if __name__ == "__main__":
    # For local testing
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

