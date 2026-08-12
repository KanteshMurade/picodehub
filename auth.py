"""
PiCodeHub auth & commerce layer.

Adds on top of the existing local Arduino-CLI workbench:
  - User accounts (register/login) with a single is_admin flag for the
    admin panel.
  - Email verification (Resend) before a new account can log in.
  - Purchases: a user must "buy" a project before they can flash it.
  - Custom project requests: the Rs.500 "build my idea" catalog item.
    A user buys it, submits free-text requirements, and an admin can
    respond with a message and/or a file that only that user (or an
    admin) can download.

Storage: MongoDB Atlas, accessed through dbshim.py — a tiny layer that
keeps the exact same conn.execute("...", (...)) calling convention this
file and app.py already used with sqlite3, so almost nothing else in
the codebase had to change.
"""

import os
import secrets
import time
import datetime as _dt
from functools import wraps

import requests
from flask import session, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

from dbshim import get_db, get_raw_db, _next_id  # noqa: F401  (re-exported for app.py)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOM_FILES_DIR = os.path.join(BASE_DIR, "custom_uploads")
os.makedirs(CUSTOM_FILES_DIR, exist_ok=True)

CUSTOM_PROJECT_ID = "custom_project"
CUSTOM_PROJECT_PRICE = 500

# How long an email-verification link stays valid, in seconds.
VERIFY_TOKEN_TTL = 60 * 60 * 24  # 24 hours

# How long a password-reset link stays valid, in seconds.
RESET_TOKEN_TTL = 60 * 60  # 1 hour

# ---------------------------------------------------------------------------
# Email verification (Resend)
# ---------------------------------------------------------------------------

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_FROM = os.environ.get("RESEND_FROM", "PiCodeHub <onboarding@resend.dev>")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.environ.get("BREVO_FROM_EMAIL", "")
BREVO_FROM_NAME = os.environ.get("BREVO_FROM_NAME", "PiCodeHub")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000")


def _send_email(to_email, subject, html):
    """Send via Brevo if configured (preferred -- free tier sends to any
    recipient, not just your own address), else fall back to Resend, else
    just log to console in dev mode."""
    if BREVO_API_KEY and BREVO_FROM_EMAIL:
        try:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html,
                },
                timeout=10,
            )
            if resp.status_code < 300:
                return True
            print(f"[Brevo] Failed to send email to {to_email}: {resp.status_code} {resp.text}")
            return False
        except requests.RequestException as e:
            print(f"[Brevo] Failed to send email to {to_email}: {e}")
            return False

    if RESEND_API_KEY:
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM, "to": [to_email], "subject": subject, "html": html},
                timeout=10,
            )
            return resp.status_code < 300
        except requests.RequestException as e:
            print(f"[Resend] Failed to send email to {to_email}: {e}")
            return False

    print("=" * 70)
    print(f"[DEV MODE - no email provider configured] Would send email to {to_email}")
    print(f"Subject: {subject}")
    print(html)
    print("=" * 70)
    return True


def create_verification_token(user_id):
    token = secrets.token_urlsafe(32)
    get_raw_db().email_verifications.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": time.time(),
        "used": False,
    })
    return token


def send_verification_email(user_id, email, username):
    token = create_verification_token(user_id)
    link = f"{SITE_URL.rstrip('/')}/api/verify-email/{token}"
    html = (
        f"<h2>Welcome to PiCodeHub, {username}!</h2>"
        f"<p>Please confirm your email address to activate your account:</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>This link expires in 24 hours.</p>"
    )
    return _send_email(email, "Verify your PiCodeHub account", html)


def verify_token(token):
    """Returns (ok, message). On success, marks the user verified."""
    doc = get_raw_db().email_verifications.find_one({"token": token})
    if not doc:
        return False, "Invalid or already-used verification link."
    if doc.get("used"):
        return False, "This verification link was already used."
    if time.time() - doc["created_at"] > VERIFY_TOKEN_TTL:
        return False, "This verification link has expired. Please register again or request a new one."
    get_raw_db().users.update_one({"id": doc["user_id"]}, {"$set": {"is_verified": True}})
    get_raw_db().email_verifications.update_one({"token": token}, {"$set": {"used": True}})
    return True, "Email verified! You can now log in."


def resend_verification(email):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return False, "No account with that email."
    if row.get("is_verified"):
        return False, "This account is already verified."
    send_verification_email(row["id"], row["email"], row["username"])
    return True, "Verification email sent."


# ---------------------------------------------------------------------------
# Forgot / reset password (Brevo/Resend)
# ---------------------------------------------------------------------------

def create_reset_token(user_id):
    token = secrets.token_urlsafe(32)
    get_raw_db().password_resets.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": time.time(),
        "used": False,
    })
    return token


def send_reset_email(user_id, email, username):
    token = create_reset_token(user_id)
    link = f"{SITE_URL.rstrip('/')}/api/reset-password/{token}"
    html = (
        f"<h2>Reset your PiCodeHub password</h2>"
        f"<p>Hi {username}, we received a request to reset your password.</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>"
    )
    return _send_email(email, "Reset your PiCodeHub password", html)


def request_password_reset(email):
    """Returns (ok, message). Always returns a generic success-style message
    so we don't leak whether an email is registered."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        send_reset_email(row["id"], row["email"], row["username"])
    return True, "If an account exists with that email, a password reset link has been sent."


def check_reset_token(token):
    """Returns (ok, message, user_id_or_None) without consuming the token."""
    doc = get_raw_db().password_resets.find_one({"token": token})
    if not doc:
        return False, "Invalid or already-used reset link.", None
    if doc.get("used"):
        return False, "This reset link was already used.", None
    if time.time() - doc["created_at"] > RESET_TOKEN_TTL:
        return False, "This reset link has expired. Please request a new one.", None
    return True, "", doc["user_id"]


def reset_password_with_token(token, new_password):
    """Returns (ok, message). Validates + consumes the token and sets the
    new password."""
    if not new_password or len(new_password) < 6:
        return False, "Password must be at least 6 characters."
    ok, message, user_id = check_reset_token(token)
    if not ok:
        return False, message
    get_raw_db().users.update_one(
        {"id": user_id}, {"$set": {"password_hash": generate_password_hash(new_password)}}
    )
    get_raw_db().password_resets.update_one({"token": token}, {"$set": {"used": True}})
    return True, "Your password has been reset. You can now log in with your new password."


def change_password(user_id, current_password, new_password):
    """Returns (ok, message). Used by the logged-in 'change password' flow
    in the profile menu, requires the current password for confirmation."""
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return False, "User not found."
    if not check_password_hash(row["password_hash"], current_password or ""):
        return False, "Current password is incorrect."
    get_raw_db().users.update_one(
        {"id": user_id}, {"$set": {"password_hash": generate_password_hash(new_password)}}
    )
    return True, "Password changed successfully."


# ---------------------------------------------------------------------------
# DB init / seeding
# ---------------------------------------------------------------------------

def init_db():
    conn = get_db()

    # Uniqueness / lookup indexes (MongoDB equivalent of sqlite's UNIQUE
    # constraints + the WHERE-clause lookups the app does constantly).
    db = get_raw_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("email", unique=True)
    db.purchases.create_index([("user_id", 1), ("project_id", 1)], unique=True)

    # Seed the CMS collections once, from the same content that used to
    # be hardcoded in catalog.js, so the site looks the same on first run.
    if not conn.execute("SELECT id FROM categories LIMIT 1").fetchone():
        for name, icon, desc in [
            ("Security", "fa-shield-halved", "RFID readers, keypad locks, access logs & biometrics"),
            ("Health", "fa-heart-pulse", "Electrocardiograms, pulse rate sensors, blood oxygen"),
            ("Sensors", "fa-gauge-high", "AQI gas monitors, soil moisture, ambient light, ultrasonic"),
            ("Automation", "fa-bolt", "Smart street lights, relay AC controllers, home energy"),
            ("IoT", "fa-network-wired", "WiFi MQTT dashboards, web socket server telemetry"),
            ("AI", "fa-brain", "Machine vision, optical card scanning, edge intelligence"),
            ("Pico", "fa-cube", "RP2040 micro-controllers, custom USB HID keypads & rotaries"),
            ("Other", "fa-microchip", "OLED desk companions, animated pixel displays & timers"),
        ]:
            conn.execute("INSERT INTO categories (name, icon, description) VALUES (?, ?, ?)", (name, icon, desc))

    if not conn.execute("SELECT id FROM components LIMIT 1").fetchone():
        for name, ctype, specs, icon in [
            ("ESP32 DevKit V1", "Microcontroller", "Dual-Core 240MHz, WiFi + BLE, 4MB Flash", "fa-wifi"),
            ("Arduino Uno R3", "Microcontroller", "ATmega328P 16MHz, 32KB Flash, 14 Digital IOs", "fa-microchip"),
            ("Raspberry Pi Pico", "Microcontroller", "RP2040 Dual ARM Cortex M0+, 2MB Flash, USB HID", "fa-cube"),
            ("RC522 RFID Reader", "Security Module", "13.56 MHz SPI Reader, ISO/IEC 14443 A/MIFARE", "fa-id-card"),
            ("AD8232 ECG Sensor", "Biomedical Module", "Single-Lead Heart Rate Monitor, Analog Output", "fa-heart-pulse"),
            ("MQ-135 Gas Sensor", "Air Quality", "NH3, NOx, Alcohol, CO2, Smoke Gas Detector", "fa-wind"),
            ("SSD1306 OLED (0.96\")", "Display", "128x64 Monochrome I2C Graphics Screen", "fa-tv"),
            ("HC-SR04 Ultrasonic", "Distance Sensor", "2cm - 400cm Non-contact distance measurement", "fa-ruler"),
            ("SG90 Micro Servo", "Actuator Motor", "9g 1.8kg.cm torque 180 degree PWM control", "fa-gear"),
        ]:
            conn.execute("INSERT INTO components (name, type, specs, icon) VALUES (?, ?, ?, ?)", (name, ctype, specs, icon))

    if not conn.execute("SELECT id FROM tutorials LIMIT 1").fetchone():
        import json as _json
        seed_tutorials = [
            ("ESP32 & NodeMCU Driver Setup Guide (CH340 / CP2102)", "Beginner", "5 mins",
             "Step-by-step instructions for establishing serial communication between your workstation and ESP32 board over USB.",
             ["Plug your ESP32 dev board into your USB port.",
              "Identify your USB-to-Serial UART IC (CH340G or Silicon Labs CP2102).",
              "Download and install the matching Windows/Linux driver.",
              "Verify device enumeration in Windows Device Manager or Linux /dev/ttyUSB0.",
              "Open the Live Compiler, select ESP32 Dev Module, and select the target COM port."]),
            ("Arduino CLI & Multi-Core Compiler Integration", "Intermediate", "8 mins",
             "How PiCodeHub compiles AVR, ESP32, and RP2040 code directly inside your browser session.",
             ["The backend automatically detects your local arduino-cli tool chain.",
              "Board core configurations (esp32:esp32, arduino:avr, rp2040:rp2040) map automatically.",
              "Compilation generates hex/bin firmware binaries in temporary workshop buffers.",
              "Serial streaming monitors live board telemetry at 115200 baud."]),
            ("Wiring Best Practices for I2C and SPI Sensors", "Beginner", "6 mins",
             "Learn how to prevent noise, ground loops, and bus conflicts when connecting OLED displays and RFID modules.",
             ["Always tie all common ground lines (GND) together.",
              "Ensure ESP32 3.3V logic pins are not exposed to 5V inputs without level shifters.",
              "Keep I2C SDA and SCL signal wire lengths under 20cm to avoid capacitance drops.",
              "Use 10k Ohm pull-up resistors on shared sensor buses when necessary."]),
        ]
        for title, level, time_, summary, steps in seed_tutorials:
            conn.execute(
                "INSERT INTO tutorials (title, level, time, summary, steps_json) VALUES (?, ?, ?, ?, ?)",
                (title, level, time_, summary, _json.dumps(steps)),
            )

    if not conn.execute("SELECT id FROM resources LIMIT 1").fetchone():
        for name, size, desc, rtype in [
            ("CH340G USB Serial Driver", "1.2 MB", "Required for Arduino Uno CH340 clones and ESP8266 NodeMCU.", "ZIP Driver"),
            ("CP210x USB to UART Bridge Driver", "2.4 MB", "Driver package for ESP32 DevKit V1 and NodeMCU boards.", "ZIP Driver"),
            ("ESP32 Pinout Cheat Sheet PDF", "850 KB", "Full GPIO pin map, ADC channels, I2C, SPI, and PWM timer mapping.", "PDF Diagram"),
            ("Arduino Uno R3 Reference Schematic", "420 KB", "Official ATmega328P schematic diagram and board pin layout.", "PDF Diagram"),
            ("Baud Rate & Serial Protocol Guide", "310 KB", "Reference card for 9600, 115200, 230400 bps serial streams.", "PDF Guide"),
        ]:
            conn.execute(
                "INSERT INTO resources (name, size, description, type) VALUES (?, ?, ?, ?)",
                (name, size, desc, rtype),
            )

    # Bootstrap a default admin account if none exists yet, so there's
    # always a way into the admin panel on a fresh install.
    if not conn.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1").fetchone():
        default_admin_user = os.environ.get("PICODEHUB_ADMIN_USER", "admin")
        default_admin_pass = os.environ.get("PICODEHUB_ADMIN_PASS", "admin123")
        default_admin_email = os.environ.get("PICODEHUB_ADMIN_EMAIL", "admin@picodehub.local")
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (default_admin_user,)).fetchone()
        if not existing:
            get_raw_db().users.insert_one({
                "id": _next_id("users"),
                "username": default_admin_user,
                "email": default_admin_email,
                "password_hash": generate_password_hash(default_admin_pass),
                "is_admin": 1,
                "is_verified": True,
                "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            })
            print("=========================================================")
            print(f"  Default admin account created -> {default_admin_user} / {default_admin_pass}")
            print("  Change this password after first login!")
            print("=========================================================")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, email, is_admin, is_verified FROM users WHERE id = ?", (uid,)
    ).fetchone()
    return dict(row) if row else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"ok": False, "error": "Please log in first."}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.get("is_admin"):
            return jsonify({"ok": False, "error": "Admin access required."}), 403
        return fn(*args, **kwargs)
    return wrapper


def user_owns_project(user_id, project_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM purchases WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    ).fetchone()
    return row is not None


def user_purchased_ids(user_id):
    conn = get_db()
    rows = conn.execute("SELECT project_id FROM purchases WHERE user_id = ?", (user_id,)).fetchall()
    return {r["project_id"] for r in rows}
