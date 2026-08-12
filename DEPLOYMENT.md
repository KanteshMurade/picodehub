# Deploying PiCodeHub for free

## What changed in the code
- `dbshim.py` (new) — routes all `conn.execute("SELECT ...", (...))` calls to MongoDB instead of sqlite3.
- `auth.py` — rewritten to use `dbshim`, plus email verification via Resend.
- `app.py` — register no longer logs the user in immediately; it sends a verification email. New routes: `/api/verify-email/<token>`, `/api/resend-verification`. Login blocks unverified accounts. Reads `PORT` from env for Render.
- `static/js/catalog.js` — register flow now shows "check your email"; login shows a resend-verification link if blocked.
- `requirements.txt` — added `pymongo`, `requests`, `python-dotenv`, `gunicorn`.
- `Procfile`, `.env.example`, `.gitignore` — new, for Render.

**Not changed / important limitation:** USB flashing (`pyserial`) still assumes the board is plugged into the same machine running Flask. That's fine locally, but once this is live on Render, the *server* can no longer see boards plugged into visitors' computers. We agreed to fix this with the WebSerial API — that's a separate, frontend-only change I can do next; it doesn't block deploying everything else today.

---

## Step 1 — MongoDB Atlas (free, forever, 512MB)
1. Go to https://www.mongodb.com/cloud/atlas/register and create a free account.
2. Create a new **free (M0)** cluster — any provider/region is fine.
3. **Database Access** → add a database user (username + password). Save the password.
4. **Network Access** → add IP address `0.0.0.0/0` (allow from anywhere) — required since Render's IP isn't fixed on the free tier.
5. Click **Connect → Drivers → Python**, copy the connection string. It looks like:
   `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
6. Replace `<user>` and `<password>` with your real values — this is your `MONGODB_URI`.

## Step 2 — Resend (free, 3,000 emails/month)
1. Sign up at https://resend.com.
2. **API Keys** → create a key → this is `RESEND_API_KEY`.
3. For `RESEND_FROM`, you can use `onboarding@resend.dev` for testing (works immediately, no domain setup). To send from your own domain later, verify it under **Domains** in Resend.

## Step 3 — Push the code to GitHub
```bash
cd pch
git init
git add .
git commit -m "PiCodeHub: MongoDB + email verification"
git branch -M main
git remote add origin https://github.com/<your-username>/picodehub.git
git push -u origin main
```
(`.env` is git-ignored — never commit real secrets.)

## Step 4 — Render (free web service)
1. Go to https://render.com, sign up, click **New → Web Service**.
2. Connect your GitHub repo.
3. Settings:
   - **Root directory**: `pch` (since your Flask app lives inside `pch/`)
   - **Build command**: `bash build.sh`
   - **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 2` (Render also auto-detects the Procfile, which already has this)
   - **Instance type**: Free
   - **Note:** `build.sh` installs `arduino-cli` plus the board cores (ESP32, Arduino AVR, ESP8266, RP2040) and libraries (DHT, Adafruit GFX/SSD1306, MAX3010x, ESP32Servo) that this catalog's projects actually need — without this, every compile fails with "arduino-cli executable not found" or "library not found". The build will take noticeably longer (5–10 extra minutes) the first time because it's downloading real toolchains, not just Python packages. That's expected — subsequent deploys reuse the same build cache if you haven't changed `build.sh`.
4. Add these **Environment Variables** (Render dashboard → Environment):
   ```
   MONGODB_URI       = mongodb+srv://...           (from Step 1)
   MONGODB_DB        = picodehub
   PICODEHUB_SECRET_KEY = <any long random string>
   PICODEHUB_ADMIN_USER = admin
   PICODEHUB_ADMIN_PASS = <a real password, not admin123>
   PICODEHUB_ADMIN_EMAIL = you@example.com
   RESEND_API_KEY    = re_...                       (from Step 2)
   RESEND_FROM       = PiCodeHub <onboarding@resend.dev>
   SITE_URL          = https://<your-app-name>.onrender.com
   ```
   (You won't know the exact Render URL until after the first deploy — deploy once, copy the URL Render gives you, paste it into `SITE_URL`, and redeploy. Otherwise verification email links will point to the wrong place.)
5. Click **Create Web Service**. Render builds and deploys automatically on every push to `main`.

**Free tier note:** Render's free web services spin down after ~15 minutes of no traffic and take ~30–50 seconds to wake up on the next visit. That's normal for free hosting — fine for a portfolio/demo project, not ideal for real paying customers long-term.

**Important — Compile works, Upload/Flash does not, on Render (or any remote host):** `build.sh` fixes compilation ("Verify") by installing `arduino-cli` and the needed cores/libraries on Render's server. But "Upload" (flashing a physical board) still cannot work once this is hosted remotely — the Flask server has no USB port, and it can't see a board plugged into a visitor's own computer. That's a hosting limitation, not a bug: uploading only ever worked when `app.py` ran on the same machine the board was physically plugged into (e.g. running it locally on your own laptop). If you need real flashing to work for remote users, the only fix is moving the upload step into the browser via the Web Serial API — a separate, larger change.

## Step 5 — First login
- Visit your Render URL. The admin account from your env vars is created automatically and is already verified (no email needed for it).
- Log in at `/admin` with `PICODEHUB_ADMIN_USER` / `PICODEHUB_ADMIN_PASS`.
- Test registration with a real email address you can check — you should get a "Verify your PiCodeHub account" email from Resend within seconds.

## Where does Netlify fit in?
It doesn't, for this project — Netlify hosts static sites, and PiCodeHub is a server-rendered Flask app (Jinja templates + APIs), so it all lives on Render as one service. You'd only reach for Netlify if you later split off a separate JS-only frontend.

## Local development
```bash
cd pch
cp .env.example .env   # fill in your real values
pip install -r requirements.txt
python app.py
```

## Still to do: WebSerial for flashing
Once this is live and you're happy with accounts/DB/email, say the word and I'll swap the flashing UI to use the browser's WebSerial API — that's what actually lets a visitor's browser talk to a board plugged into *their* computer through your cloud-hosted site.
