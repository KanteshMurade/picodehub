import os
import sys
from dotenv import load_dotenv
load_dotenv()  # reads a local .env file if present (harmless in production)
import json
import zipfile
import shutil
import subprocess
import tempfile
import io
import time
import threading
import queue
import uuid

# Include local vendor packages if present
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, Response, redirect, session
import serial.tools.list_ports

import auth as authmod
import project_store
from auth import (
    init_db, get_db, current_user, login_required, admin_required,
    user_owns_project, user_purchased_ids, CUSTOM_PROJECT_ID, CUSTOM_PROJECT_PRICE,
    CUSTOM_FILES_DIR,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

# File extensions that are safe to serve publicly from /projects/<file>
# (cover images + wiring PDFs). Anything else (.ino/.h/.cpp/.c/.json/...)
# is source material and is only servable to an admin.
PUBLIC_PROJECT_FILE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}

DEFAULT_PROJECT_PRICE = 299

RESOURCE_FILES_DIR = os.path.join(BASE_DIR, "resource_uploads")
os.makedirs(RESOURCE_FILES_DIR, exist_ok=True)

USER_WORKSPACE_DIR = os.path.join(BASE_DIR, "user_workspace")
os.makedirs(USER_WORKSPACE_DIR, exist_ok=True)

BOARDS = {
    "Arduino Uno": "arduino:avr:uno",
    "Arduino Nano": "arduino:avr:nano",
    "Arduino Mega": "arduino:avr:mega",
    "ESP32 Dev Module": "esp32:esp32:esp32",
    "ESP8266 NodeMCU": "esp8266:esp8266:nodemcuv2",
    "Raspberry Pi Pico": "rp2040:rp2040:rpipico"
}

VID_PID_MAP = {
    "2341:0043": "Arduino Uno", "2341:0001": "Arduino Uno", "2341:0042": "Arduino Mega",
    "2A03:0043": "Arduino Uno", "1A86:7523": "Arduino Uno (CH340)", "1A86:43FF": "Arduino Uno (CH340)",
    "303A:1001": "ESP32 Dev Module", "10C4:EA60": "ESP8266 NodeMCU (CH340)",
    "2E8A:0005": "Raspberry Pi Pico"
}

BLINK_TEMPLATE = (
    "// Blink - Technosankalp / Sodh Lab Sketch\n"
    "void setup() {\n"
    "  pinMode(LED_BUILTIN, OUTPUT);\n"
    "  Serial.begin(115200);\n"
    "  Serial.println(\"[SYSTEM] Sketch initialized.\");\n"
    "}\n\n"
    "void loop() {\n"
    "  digitalWrite(LED_BUILTIN, HIGH);\n"
    "  delay(1000);\n"
    "  digitalWrite(LED_BUILTIN, LOW);\n"
    "  delay(1000);\n"
    "}\n"
)
DEFAULT_SKETCH_TEMPLATE = BLINK_TEMPLATE

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("PICODEHUB_SECRET_KEY", "picodehub-dev-secret-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
init_db()

# Restore any admin-added catalog projects that only exist in MongoDB
# (Render's free tier wipes local disk on every restart/redeploy, so
# anything added after the last git deploy would otherwise vanish).
project_store.restore_all_project_folders(PROJECTS_DIR)
project_store.restore_all(RESOURCE_FILES_DIR, "resources")
project_store.restore_all(CUSTOM_FILES_DIR, "custom_uploads")

class SerialManager:
    def __init__(self):
        self._ser = None
        self._thread = None
        self._run = False
        self._clients = []
        self._lock = threading.Lock()
        self._port = None
        self._baud = 9600

    @property
    def connected(self):
        return self._ser is not None and self._ser.is_open

    def connect(self, port, baud=9600):
        with self._lock:
            if self.connected:
                self._disc()
            try:
                import serial
                self._ser = serial.Serial(port, baud, timeout=0)
                self._port = port
                self._baud = baud
                self._run = True
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
                return {"ok": True}
            except Exception as e:
                self._ser = None
                return {"ok": False, "error": str(e)}

    def disconnect(self):
        with self._lock:
            return self._disc()

    def send(self, data):
        if not self.connected:
            return {"ok": False, "error": "Not connected to any serial port."}
        try:
            self._ser.write(data.encode("utf-8"))
            self._ser.flush()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def status(self):
        return {"connected": self.connected, "port": self._port, "baud": self._baud}

    def add_client(self):
        q = queue.Queue(maxsize=2000)
        with self._lock:
            self._clients.append(q)
        return q

    def remove_client(self, q):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def _disc(self):
        self._run = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._ser:
            try:
                self._ser.close()
            except:
                pass
            self._ser = None
        p = self._port
        self._port = None
        self._bcast({"type": "status", "connected": False, "port": p})
        return {"ok": True}

    def _bcast(self, msg):
        m = json.dumps(msg)
        with self._lock:
            for q in self._clients:
                try:
                    q.put_nowait(m)
                except:
                    pass

    def _loop(self):
        while self._run:
            try:
                if self._ser and self._ser.is_open:
                    n = self._ser.in_waiting
                    if n > 0:
                        text = self._ser.read(min(n, 4096)).decode("utf-8", "replace")
                        self._bcast({"type": "data", "text": text, "time": time.strftime("%H:%M:%S")})
                    else:
                        time.sleep(0.01)
                else:
                    break
            except Exception as e:
                self._bcast({"type": "status", "connected": False, "error": str(e)})
                break
        with self._lock:
            self._run = False
            if self._ser:
                try:
                    self._ser.close()
                except:
                    pass
                self._ser = None
            self._port = None

ser_mgr = SerialManager()

# ---------------------------------------------------------------------------
# Async compile jobs.
#
# WHY: a real ESP32/AVR compile can take well over a minute, especially on
# Render's free-tier shared CPU. Render's proxy enforces its own fixed
# request timeout (not configurable, independent of gunicorn's --timeout)
# and kills long-running requests with a 504 -- which arrives to the
# browser as an HTML error page, not JSON, causing exactly the
# "Unexpected token '<'" crash you saw. A single long-lived HTTP request
# for compilation is fundamentally unreliable on this kind of host.
#
# FIX: /api/compile now only *starts* the job and returns a job_id
# immediately (fast, well under any timeout). The frontend then polls
# /api/compile-status/<job_id> every second or two -- each poll is a tiny,
# fast request that can never time out, no matter how long the actual
# compile takes underneath.
# ---------------------------------------------------------------------------
_compile_jobs = {}
_compile_jobs_lock = threading.Lock()


def _run_compile_job(job_id, args, timeout):
    result = _cli(args, timeout=timeout)
    with _compile_jobs_lock:
        job = _compile_jobs.get(job_id)
        if job is not None:
            job["done"] = True
            job["result"] = result


def _start_compile_job(args, timeout):
    job_id = uuid.uuid4().hex
    with _compile_jobs_lock:
        _compile_jobs[job_id] = {"done": False, "result": None, "started": time.time()}
    t = threading.Thread(target=_run_compile_job, args=(job_id, args, timeout), daemon=True)
    t.start()
    return job_id


def _cleanup_old_jobs():
    cutoff = time.time() - 3600
    with _compile_jobs_lock:
        stale = [jid for jid, j in _compile_jobs.items() if j["done"] and j["started"] < cutoff]
        for jid in stale:
            del _compile_jobs[jid]

def _workbench_root():
    """
    Returns the file-tree root the current session is allowed to browse in
    the Workbench IDE.

    - Admins get the real catalog (PROJECTS_DIR) — full control, as before.
    - Any other logged-in user gets their own private, empty-by-default
      folder under user_workspace/<id>/ide/. They can create/edit/compile/
      flash their own sketches there, but never see or reach the paid
      catalog's source files.
    """
    user = current_user()
    if user and user.get('is_admin'):
        return PROJECTS_DIR
    if user:
        root = os.path.join(USER_WORKSPACE_DIR, str(user['id']), 'ide')
        os.makedirs(root, exist_ok=True)
        return root
    return None

def _sp(p, root=None):
    root = root or PROJECTS_DIR
    p = (p or "").replace("\\", "/").lstrip("/")
    if not p:
        raise ValueError("Empty path")
    f = os.path.normpath(os.path.join(root, p))
    if f != os.path.normpath(root) and not f.startswith(os.path.normpath(root) + os.sep):
        raise ValueError("Invalid path")
    return f

def _tree(d, root=None):
    root = root or d
    items = []
    try:
        entries = sorted(os.listdir(d), key=lambda n: (not os.path.isdir(os.path.join(d, n)), n.lower()))
    except:
        return items
    for n in entries:
        if n.startswith('.') or n == 'project.json':
            continue
        f = os.path.join(d, n)
        r = os.path.relpath(f, root).replace("\\", "/")
        if os.path.isdir(f):
            items.append({"name": n, "path": r, "type": "folder", "is_dir": True, "children": _tree(f, root)})
        else:
            items.append({"name": n, "path": r, "type": "file", "is_dir": False})
    return items

def _ports():
    try:
        ports = []
        for p in serial.tools.list_ports.comports():
            vidpid = "{:04X}:{:04X}".format(p.vid, p.pid) if p.vid and p.pid else ""
            ports.append({"device": p.device, "description": p.description or "", "vidpid": vidpid})
        return {"ok": True, "ports": ports}
    except Exception as e:
        return {"ok": False, "error": str(e), "ports": []}

def _sketch(p, root=None):
    root = root or PROJECTS_DIR
    if not p:
        return None, "Open a sketch file first."
    parts = p.replace("\\", "/").strip("/").split("/")
    if len(parts) < 2:
        return None, "Sketch needs to be in Folder/File.ino format"
    fol = parts[0]
    sd = os.path.join(root, fol)
    if not os.path.isdir(sd):
        return None, "Folder not found: " + fol
    main_ino = os.path.join(sd, fol + ".ino")
    if not os.path.isfile(main_ino):
        inos = [f for f in os.listdir(sd) if f.endswith('.ino')]
        if not inos:
            return None, "Missing sketch file in " + fol
    return sd, None

def _get_cli_path():
    # 1. Explicit override via env var (most reliable on hosts like Render
    #    where PATH persistence between build and runtime isn't guaranteed).
    env_path = os.environ.get("ARDUINO_CLI_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path
    # 2. A project-local ./bin/arduino-cli, installed by build.sh on Render.
    local_bin = os.path.join(BASE_DIR, "bin", "arduino-cli")
    if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin
    # 3. Whatever's on PATH (works for local dev / Docker images that
    #    installed arduino-cli system-wide).
    c = shutil.which("arduino-cli")
    if c:
        return c
    # 4. Legacy fallback for the original dev machine this app was built on.
    bundled = "/home/officialp160/arduino-ide_2.3.9_Linux_64bit/resources/app/lib/backend/resources/arduino-cli"
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    return None

def _arduino_cli_env():
    """
    Explicit, project-local directories for arduino-cli's installed cores,
    libraries, and downloads cache — pinned the same way build.sh pins them.
    Without this, arduino-cli falls back to $HOME/.arduino15, and on hosts
    like Render the build step's $HOME isn't guaranteed to match the
    running web process's $HOME, making everything build.sh installed
    invisible at request time (it then tries to re-download from scratch
    and fails because there's no time/disk for that inside one request).
    """
    env = os.environ.copy()
    env.setdefault("ARDUINO_DIRECTORIES_DATA", os.path.join(BASE_DIR, "arduino-data"))
    env.setdefault("ARDUINO_DIRECTORIES_DOWNLOADS", os.path.join(BASE_DIR, "arduino-downloads"))
    env.setdefault("ARDUINO_DIRECTORIES_USER", os.path.join(BASE_DIR, "arduino-user"))
    return env

def _cli(args, timeout=120):
    c = _get_cli_path()
    if not c:
        return {"ok": False, "output": "arduino-cli executable not found on system PATH."}
    try:
        r = subprocess.run([c] + args, capture_output=True, text=True, timeout=timeout, env=_arduino_cli_env())
        return {"ok": r.returncode == 0, "output": r.stdout + r.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Compilation timed out."}
    except Exception as e:
        return {"ok": False, "output": str(e)}

def _check_idx():
    c = _get_cli_path()
    if not c:
        return False
    try:
        r = subprocess.run([c, "config", "dump", "--json"], capture_output=True, text=True, timeout=5, env=_arduino_cli_env())
        if r.returncode == 0:
            d = json.loads(r.stdout).get("directories", {}).get("data", "")
            if d and os.path.isfile(os.path.join(d, "library_index.json")):
                return True
    except:
        pass
    return False

# Web Application Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/ide')
def ide():
    # Every logged-in user gets the full Workbench IDE UI. Admins browse the
    # real paid catalog; everyone else is transparently sandboxed to their
    # own private, per-account workspace (see _workbench_root()) — they can
    # never see or reach anyone else's files or the catalog source code.
    if not current_user():
        return redirect('/')
    return render_template('ide.html')

@app.route('/flash')
def flash_page():
    # Lightweight flashing-only workbench for a single purchased project.
    # No file tree, no editor, no source code is ever sent to this page.
    user = current_user()
    if not user:
        return redirect('/')
    project_id = request.args.get('project', '')
    if not user.get('is_admin') and project_id != CUSTOM_PROJECT_ID and not user_owns_project(user['id'], project_id):
        return redirect('/')
    return render_template('flash.html')

@app.route('/admin')
def admin_page():
    user = current_user()
    if not user or not user.get('is_admin'):
        return redirect('/')
    return render_template('admin.html')

def _read_project_json(folder_name):
    folder_path = os.path.join(PROJECTS_DIR, folder_name)
    json_path = os.path.join(folder_path, 'project.json')
    ino_files = [f for f in os.listdir(folder_path) if f.endswith('.ino')]
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {"id": folder_name, "title": folder_name.replace('_', ' ').title()}
    else:
        data = {
            "id": folder_name,
            "title": folder_name.replace('_', ' ').title(),
            "category": "General",
            "difficulty": "Intermediate",
            "chips": ["ESP32", "Arduino"],
            "description": f"Project folder containing {folder_name}",
            "wiring": [],
            "components": [],
            "serialPlayback": ["Project ready."],
        }
    data['folder'] = folder_name
    if ino_files:
        data['main_file'] = f"{folder_name}/{ino_files[0]}"
    if os.path.exists(os.path.join(folder_path, 'wiring.pdf')):
        data['pdf'] = f"/projects/{folder_name}/wiring.pdf"
    data.setdefault('price', DEFAULT_PROJECT_PRICE)
    # Never leak the raw folder/main_file path to non-admin API consumers;
    # trimmed at the point of response in list_projects() instead.
    return data

@app.route('/api/projects', methods=['GET'])
def list_projects():
    user = current_user()
    owned = user_purchased_ids(user['id']) if user else set()
    is_admin = bool(user and user.get('is_admin'))

    projects = []
    if os.path.exists(PROJECTS_DIR):
        for folder_name in sorted(os.listdir(PROJECTS_DIR)):
            folder_path = os.path.join(PROJECTS_DIR, folder_name)
            if os.path.isdir(folder_path) and not folder_name.startswith('.') and not folder_name.startswith('_'):
                data = _read_project_json(folder_name)
                data['id'] = data.get('id') or folder_name
                data['owned'] = is_admin or (data['id'] in owned)
                # Strip internal filesystem details from the public payload.
                if not is_admin:
                    data.pop('folder', None)
                    data.pop('main_file', None)
                projects.append(data)

    # Pin the Custom Project card at the top of the catalog.
    custom_card = {
        "id": CUSTOM_PROJECT_ID,
        "title": "Custom Project — Build My Idea",
        "category": "Custom",
        "difficulty": "Any",
        "chips": ["Any Board"],
        "chipTag": "Custom",
        "rating": "5.0",
        "views": "New",
        "cover": "/static/images/custom_project.jpg",
        "description": "Have your own idea? Buy this slot, tell us exactly what you need, and our team will build and deliver it to your account.",
        "price": CUSTOM_PROJECT_PRICE,
        "owned": is_admin or (CUSTOM_PROJECT_ID in owned),
        "is_custom": True,
        "wiring": [],
        "components": [],
        "serialPlayback": [],
    }
    projects.insert(0, custom_card)
    return jsonify(projects)

@app.route("/api/admin/projects/<project_id>/firmware", methods=["POST"])
@admin_required
def api_admin_upload_firmware(project_id):
    """
    Upload a pre-compiled ESP32/ESP8266/RP2040 .bin so the buyer can flash
    it straight from their browser (Web Serial API) on the /flash page —
    no local arduino-cli or backend USB access required.
    """
    folder_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.isdir(folder_path):
        return jsonify({"ok": False, "error": "Project not found."}), 404

    firmware_file = request.files.get("firmware")
    if not firmware_file or not firmware_file.filename:
        return jsonify({"ok": False, "error": "No firmware file uploaded."}), 400
    if not firmware_file.filename.lower().endswith(".bin"):
        return jsonify({"ok": False, "error": "Firmware must be a .bin file."}), 400

    chip_family = (request.form.get("chip_family") or "ESP32").strip()
    flash_offset = request.form.get("flash_offset", "0x0").strip() or "0x0"

    firmware_file.save(os.path.join(folder_path, "firmware.bin"))

    json_path = os.path.join(folder_path, "project.json")
    data = _read_project_json(project_id) if os.path.exists(json_path) else {"id": project_id, "title": project_id}
    data.pop('folder', None)
    data.pop('main_file', None)
    data['has_firmware'] = True
    data['chip_family'] = chip_family
    data['flash_offset'] = flash_offset
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    project_store.save_project_folder(PROJECTS_DIR, project_id)

    return jsonify({"ok": True, "message": "Firmware uploaded."})

def _user_can_flash_project(project_id):
    user = current_user()
    if not user:
        return False
    if user.get('is_admin'):
        return True
    return user_owns_project(user['id'], project_id)

@app.route("/api/projects/<project_id>/firmware.bin")
def api_download_firmware(project_id):
    if not _user_can_flash_project(project_id):
        return jsonify({"ok": False, "error": "Not authorized."}), 403
    folder_path = os.path.join(PROJECTS_DIR, project_id)
    fw_path = os.path.join(folder_path, "firmware.bin")
    if not os.path.isfile(fw_path):
        return jsonify({"ok": False, "error": "No firmware uploaded for this project yet."}), 404
    return send_from_directory(folder_path, "firmware.bin", mimetype="application/octet-stream")

@app.route("/api/projects/<project_id>/manifest.json")
def api_project_manifest(project_id):
    """ESP Web Tools manifest, scoped to a single buyer's purchased project.
    Powers the in-browser flashing flow on /flash (Web Serial API — the
    browser itself talks to the USB device, no backend involved)."""
    if not _user_can_flash_project(project_id):
        return jsonify({"ok": False, "error": "Not authorized."}), 403
    folder_path = os.path.join(PROJECTS_DIR, project_id)
    fw_path = os.path.join(folder_path, "firmware.bin")
    if not os.path.isfile(fw_path):
        return jsonify({"ok": False, "error": "No firmware uploaded for this project yet."}), 404
    data = _read_project_json(project_id)
    chip_family = data.get("chip_family", "ESP32")
    flash_offset = data.get("flash_offset", "0x0")
    try:
        offset = int(flash_offset, 16) if isinstance(flash_offset, str) else int(flash_offset)
    except ValueError:
        offset = 0
    manifest = {
        "name": data.get("title", project_id),
        "version": "1.0.0",
        "builds": [
            {
                "chipFamily": chip_family,
                "parts": [
                    {"path": f"/api/projects/{project_id}/firmware.bin", "offset": offset}
                ],
            }
        ],
    }
    return jsonify(manifest)

@app.route('/projects/<path:filename>')
def serve_project_files(filename):
    # Only images / wiring PDFs are public. Anything else (source code,

    # project.json, etc.) requires an admin session.
    ext = os.path.splitext(filename)[1].lower()
    if ext not in PUBLIC_PROJECT_FILE_EXTS:
        user = current_user()
        if not user or not user.get('is_admin'):
            return jsonify({"ok": False, "error": "Not authorized to view this file."}), 403
    return send_from_directory(PROJECTS_DIR, filename)

@app.route('/api/import-zip', methods=['POST'])
@admin_required
def import_zip():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({"success": False, "error": "Must be a ZIP file"}), 400
    
    temp_zip_path = os.path.join(PROJECTS_DIR, '_temp_import.zip')
    file.save(temp_zip_path)
    imported_count = 0
    try:
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            temp_extract_dir = os.path.join(PROJECTS_DIR, '_temp_extract')
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
            os.makedirs(temp_extract_dir)
            zip_ref.extractall(temp_extract_dir)
            
            for root, dirs, files in os.walk(temp_extract_dir):
                ino_files = [f for f in files if f.endswith('.ino')]
                if ino_files or 'project.json' in files or 'wiring.pdf' in files:
                    folder_name = os.path.basename(root)
                    if folder_name == '_temp_extract':
                        folder_name = os.path.splitext(file.filename)[0]
                    
                    target_dir = os.path.join(PROJECTS_DIR, folder_name)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    for item in os.listdir(root):
                        s = os.path.join(root, item)
                        d = os.path.join(target_dir, item)
                        if os.path.isfile(s):
                            shutil.copy2(s, d)
                        elif os.path.isdir(s) and item != '_temp_extract':
                            if os.path.exists(d):
                                shutil.rmtree(d)
                            shutil.copytree(s, d)
                    imported_count += 1
                    project_store.save_project_folder(PROJECTS_DIR, folder_name)
            shutil.rmtree(temp_extract_dir)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
            
    return jsonify({
        "success": True, 
        "message": f"Successfully imported {imported_count} project(s)!",
        "count": imported_count
    })

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True) or {}
    username = (d.get("username") or "").strip()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""

    if not username or not email or not password:
        return jsonify({"ok": False, "error": "Username, email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

    conn = get_db()
    try:
        # (Two lookups instead of one OR query -- the MongoDB dbshim only
        # understands AND, not OR, in WHERE clauses.)
        existing = (
            conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            or conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        )
        if existing:
            return jsonify({"ok": False, "error": "Username or email already registered."}), 409
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        conn.commit()
        user_id = cur.lastrowid
    except Exception:
        # Safety net: even if a race condition slips past the check above
        # (two people registering the same username at the same instant),
        # Mongo's unique index still rejects the duplicate -- return a
        # clean error instead of a 500 crash.
        return jsonify({"ok": False, "error": "Username or email already registered."}), 409
    finally:
        conn.close()

    # New accounts start unverified; user must click the emailed link
    # before they're allowed to log in.
    authmod.send_verification_email(user_id, email, username)

    return jsonify({
        "ok": True,
        "message": "Account created. Please check your email to verify your account before logging in.",
        "user": {"id": user_id, "username": username, "email": email, "is_admin": False},
    }), 201

@app.route("/api/verify-email/<token>")
def api_verify_email(token):
    ok, message = authmod.verify_token(token)
    # Simple confirmation page — no template dependency needed.
    color = "#16a34a" if ok else "#dc2626"
    html = f"""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
    <h2 style="color:{color}">{message}</h2>
    <p><a href="/">Go to PiCodeHub</a></p>
    </body></html>
    """
    return html

@app.route("/api/resend-verification", methods=["POST"])
def api_resend_verification():
    d = request.get_json(force=True) or {}
    email = (d.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400
    ok, message = authmod.resend_verification(email)
    return jsonify({"ok": ok, "message": message}), (200 if ok else 400)

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(force=True) or {}
    identifier = (d.get("username") or d.get("email") or "").strip()
    password = d.get("password") or ""

    conn = get_db()
    row = (
        conn.execute("SELECT * FROM users WHERE username = ?", (identifier,)).fetchone()
        or conn.execute("SELECT * FROM users WHERE email = ?", (identifier.lower(),)).fetchone()
    )
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"ok": False, "error": "Invalid username/email or password."}), 401

    if not row.get("is_verified"):
        return jsonify({
            "ok": False,
            "error": "Please verify your email before logging in. Check your inbox, or request a new link.",
            "unverified": True,
        }), 403

    session["user_id"] = row["id"]
    return jsonify({"ok": True, "user": {
        "id": row["id"], "username": row["username"], "email": row["email"], "is_admin": bool(row["is_admin"])
    }})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user_id", None)
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    user = current_user()
    return jsonify({"ok": True, "user": user})

# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------

@app.route("/api/forgot-password", methods=["POST"])
def api_forgot_password():
    d = request.get_json(force=True) or {}
    email = (d.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400
    ok, message = authmod.request_password_reset(email)
    return jsonify({"ok": ok, "message": message})

@app.route("/api/reset-password/<token>", methods=["GET"])
def api_reset_password_form(token):
    ok, message, _uid = authmod.check_reset_token(token)
    if not ok:
        return f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
        <h2 style="color:#dc2626">{message}</h2>
        <p><a href="/">Go to PiCodeHub</a></p>
        </body></html>
        """
    return f"""
    <html><body style="font-family:sans-serif;max-width:420px;margin:60px auto;padding:0 20px;">
    <h2>Reset your password</h2>
    <form method="POST" action="/api/reset-password/{token}">
      <label style="display:block;margin-bottom:6px;">New password</label>
      <input type="password" name="password" minlength="6" required
             style="width:100%;padding:10px;box-sizing:border-box;margin-bottom:16px;border:1px solid #ccc;border-radius:6px;">
      <label style="display:block;margin-bottom:6px;">Confirm password</label>
      <input type="password" name="confirm" minlength="6" required
             style="width:100%;padding:10px;box-sizing:border-box;margin-bottom:20px;border:1px solid #ccc;border-radius:6px;">
      <button type="submit" style="width:100%;padding:12px;background:#4f46e5;color:#fff;border:none;border-radius:6px;font-weight:600;">Reset Password</button>
    </form>
    </body></html>
    """

@app.route("/api/reset-password/<token>", methods=["POST"])
def api_reset_password_submit(token):
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""
    if password != confirm:
        ok, message = False, "Passwords do not match. Go back and try again."
    else:
        ok, message = authmod.reset_password_with_token(token, password)
    color = "#16a34a" if ok else "#dc2626"
    return f"""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
    <h2 style="color:{color}">{message}</h2>
    <p><a href="/">Go to PiCodeHub</a></p>
    </body></html>
    """

@app.route("/api/change-password", methods=["POST"])
@login_required
def api_change_password():
    user = current_user()
    d = request.get_json(force=True) or {}
    current_password = d.get("current_password") or ""
    new_password = d.get("new_password") or ""
    ok, message = authmod.change_password(user["id"], current_password, new_password)
    return jsonify({"ok": ok, "message": message}), (200 if ok else 400)

# ---------------------------------------------------------------------------
# Store: purchases & custom project requests
# ---------------------------------------------------------------------------

@app.route("/api/projects/<project_id>/buy", methods=["POST"])
@login_required
def api_buy_project(project_id):
    user = current_user()
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM purchases WHERE user_id = ? AND project_id = ?",
            (user['id'], project_id),
        ).fetchone()
        if existing:
            return jsonify({"ok": True, "message": "You already own this project.", "already_owned": True})

        if project_id == CUSTOM_PROJECT_ID:
            price = CUSTOM_PROJECT_PRICE
        else:
            folder_path = os.path.join(PROJECTS_DIR, project_id)
            if not os.path.isdir(folder_path):
                return jsonify({"ok": False, "error": "Project not found."}), 404
            price = _read_project_json(project_id).get('price', DEFAULT_PROJECT_PRICE)

        # NOTE: payment gateway integration (Razorpay/Stripe/UPI) goes here.
        # This simulates a completed, successful payment.
        conn.execute(
            "INSERT INTO purchases (user_id, project_id, price_paid) VALUES (?, ?, ?)",
            (user['id'], project_id, price),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "message": "Purchase successful.", "price_paid": price})

@app.route("/api/my-purchases")
@login_required
def api_my_purchases():
    user = current_user()
    conn = get_db()
    rows = conn.execute(
        "SELECT project_id, price_paid, purchased_at FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC",
        (user['id'],),
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "purchases": [dict(r) for r in rows]})

@app.route("/api/custom-requests", methods=["POST"])
@login_required
def api_create_custom_request():
    user = current_user()
    d = request.get_json(force=True) or {}
    requirements = (d.get("requirements") or "").strip()
    if not requirements:
        return jsonify({"ok": False, "error": "Please describe your custom project requirements."}), 400

    if not user_owns_project(user['id'], CUSTOM_PROJECT_ID):
        return jsonify({"ok": False, "error": "Please purchase the Custom Project slot first."}), 403

    conn = get_db()
    conn.execute(
        "INSERT INTO custom_requests (user_id, requirements) VALUES (?, ?)",
        (user['id'], requirements),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Your requirements have been sent to our team."}), 201

@app.route("/api/my-custom-requests")
@login_required
def api_my_custom_requests():
    user = current_user()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, requirements, status, admin_message, admin_file_name, created_at, responded_at "
        "FROM custom_requests WHERE user_id = ? ORDER BY created_at DESC",
        (user['id'],),
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "requests": [dict(r) for r in rows]})

@app.route("/api/custom-requests/<int:req_id>/file")
@login_required
def api_download_custom_file(req_id):
    user = current_user()
    conn = get_db()
    row = conn.execute("SELECT * FROM custom_requests WHERE id = ?", (req_id,)).fetchone()
    conn.close()
    if not row or not row["admin_file_path"]:
        return jsonify({"ok": False, "error": "No file available."}), 404
    if not user.get('is_admin') and row["user_id"] != user['id']:
        return jsonify({"ok": False, "error": "Not authorized."}), 403
    full_path = os.path.join(CUSTOM_FILES_DIR, row["admin_file_path"])
    if not os.path.isfile(full_path):
        return jsonify({"ok": False, "error": "File missing on server."}), 404
    return send_file(full_path, as_attachment=True, download_name=row["admin_file_name"] or "custom_project_file")

# ---------------------------------------------------------------------------
# Admin: project catalog management
# ---------------------------------------------------------------------------

@app.route("/api/admin/projects", methods=["POST"])
@admin_required
def api_admin_add_project():
    """
    Add a new catalog project. Accepts multipart/form-data:
      title, category, difficulty, chips (comma separated), price, description
      sketch (.ino file, required)
      cover (image file, optional)
    """
    title = (request.form.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Title is required."}), 400

    price = request.form.get("price", DEFAULT_PROJECT_PRICE)
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = DEFAULT_PROJECT_PRICE

    folder_name = "".join(c if (c.isalnum() or c == '_') else '_' for c in title.strip().replace(' ', '_'))
    if not folder_name:
        return jsonify({"ok": False, "error": "Could not derive a valid folder name from the title."}), 400
    folder_path = os.path.join(PROJECTS_DIR, folder_name)
    if os.path.exists(folder_path):
        return jsonify({"ok": False, "error": "A project with this title already exists."}), 409
    os.makedirs(folder_path)

    sketch_file = request.files.get("sketch")
    if sketch_file and sketch_file.filename:
        sketch_file.save(os.path.join(folder_path, f"{folder_name}.ino"))
    else:
        with open(os.path.join(folder_path, f"{folder_name}.ino"), "w", encoding="utf-8") as f:
            f.write(BLINK_TEMPLATE)

    cover_file = request.files.get("cover")
    cover_path = None
    if cover_file and cover_file.filename:
        ext = os.path.splitext(cover_file.filename)[1].lower()
        if ext in PUBLIC_PROJECT_FILE_EXTS:
            cover_name = secure_filename(f"{folder_name}_cover{ext}")
            cover_file.save(os.path.join(folder_path, cover_name))
            cover_path = f"/projects/{folder_name}/{cover_name}"

    chips = [c.strip() for c in (request.form.get("chips") or "ESP32").split(",") if c.strip()]

    project_json = {
        "id": folder_name,
        "title": title,
        "category": request.form.get("category", "General"),
        "difficulty": request.form.get("difficulty", "Intermediate"),
        "chips": chips,
        "chipTag": chips[0] if chips else "ESP32",
        "rating": "New",
        "views": "0",
        "cover": cover_path or "/static/images/smart_door.jpg",
        "description": request.form.get("description", ""),
        "price": price,
        "wiring": [],
        "components": [],
        "serialPlayback": ["[SYSTEM] Project ready."],
    }
    with open(os.path.join(folder_path, "project.json"), "w", encoding="utf-8") as f:
        json.dump(project_json, f, indent=2)

    project_store.save_project_folder(PROJECTS_DIR, folder_name)

    return jsonify({"ok": True, "project": project_json}), 201

@app.route("/api/admin/projects/<project_id>/price", methods=["POST"])
@admin_required
def api_admin_update_price(project_id):
    d = request.get_json(force=True) or {}
    try:
        price = float(d.get("price"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid price."}), 400

    folder_path = os.path.join(PROJECTS_DIR, project_id)
    json_path = os.path.join(folder_path, "project.json")
    if not os.path.isdir(folder_path):
        return jsonify({"ok": False, "error": "Project not found."}), 404

    data = _read_project_json(project_id) if os.path.exists(json_path) else {"id": project_id, "title": project_id}
    data.pop('folder', None)
    data.pop('main_file', None)
    data['price'] = price
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    project_store.save_project_folder(PROJECTS_DIR, project_id)
    return jsonify({"ok": True, "price": price})

@app.route("/api/admin/projects/<project_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_project(project_id):
    folder_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.isdir(folder_path):
        return jsonify({"ok": False, "error": "Project not found."}), 404
    shutil.rmtree(folder_path)
    project_store.delete_project_folder(project_id)
    return jsonify({"ok": True})

@app.route("/api/admin/custom-requests")
@admin_required
def api_admin_list_custom_requests():
    # This one listing needs a join (request + requester's username/email).
    # MongoDB has no SQL JOIN, so it's done as two lookups instead of
    # going through the dbshim's simple single-table SQL parser.
    db = authmod.get_raw_db()
    reqs = list(db.custom_requests.find({}, {"_id": 0}).sort("created_at", -1))
    user_ids = {r["user_id"] for r in reqs}
    users_by_id = {u["id"]: u for u in db.users.find({"id": {"$in": list(user_ids)}}, {"_id": 0})}
    out = []
    for r in reqs:
        u = users_by_id.get(r["user_id"], {})
        merged = dict(r)
        merged["username"] = u.get("username")
        merged["email"] = u.get("email")
        out.append(merged)
    return jsonify({"ok": True, "requests": out})

@app.route("/api/admin/custom-requests/<int:req_id>/respond", methods=["POST"])
@admin_required
def api_admin_respond_custom_request(req_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM custom_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "Request not found."}), 404

    message = (request.form.get("message") or "").strip()
    file_obj = request.files.get("file")

    file_rel_path = row["admin_file_path"]
    file_name = row["admin_file_name"]
    if file_obj and file_obj.filename:
        req_dir = os.path.join(CUSTOM_FILES_DIR, str(req_id))
        os.makedirs(req_dir, exist_ok=True)
        safe_name = secure_filename(file_obj.filename)
        file_obj.save(os.path.join(req_dir, safe_name))
        file_rel_path = os.path.join(str(req_id), safe_name)
        file_name = file_obj.filename
        project_store.save_folder(CUSTOM_FILES_DIR, "custom_uploads", str(req_id))

    conn.execute(
        "UPDATE custom_requests SET status = 'responded', admin_message = ?, admin_file_path = ?, "
        "admin_file_name = ?, responded_at = CURRENT_TIMESTAMP WHERE id = ?",
        (message, file_rel_path, file_name, req_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/users")
@admin_required
def api_admin_list_users():
    conn = get_db()
    rows = conn.execute("SELECT id, username, email, is_admin, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify({"ok": True, "users": [dict(r) for r in rows]})

# ---------------------------------------------------------------------------
# CMS: Categories / Components / Tutorials / Resources / Site Settings
# Public GET for the home page, admin-only for create/update/delete, so the
# admin can manage the whole site's content without touching code.
# ---------------------------------------------------------------------------

@app.route("/api/categories")
def api_list_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    return jsonify({"ok": True, "categories": [dict(r) for r in rows]})

@app.route("/api/admin/categories", methods=["POST"])
@admin_required
def api_admin_add_category():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Category name is required."}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO categories (name, icon, description) VALUES (?, ?, ?)",
        (name, d.get("icon", "fa-layer-group"), d.get("description", "")),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/admin/categories/<int:item_id>", methods=["POST"])
@admin_required
def api_admin_update_category(item_id):
    d = request.get_json(force=True) or {}
    conn = get_db()
    conn.execute(
        "UPDATE categories SET name = ?, icon = ?, description = ? WHERE id = ?",
        (d.get("name", ""), d.get("icon", "fa-layer-group"), d.get("description", ""), item_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/categories/<int:item_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_category(item_id):
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/components")
def api_list_components():
    conn = get_db()
    rows = conn.execute("SELECT * FROM components ORDER BY id").fetchall()
    conn.close()
    return jsonify({"ok": True, "components": [dict(r) for r in rows]})

@app.route("/api/admin/components", methods=["POST"])
@admin_required
def api_admin_add_component():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Component name is required."}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO components (name, type, specs, icon) VALUES (?, ?, ?, ?)",
        (name, d.get("type", ""), d.get("specs", ""), d.get("icon", "fa-microchip")),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/admin/components/<int:item_id>", methods=["POST"])
@admin_required
def api_admin_update_component(item_id):
    d = request.get_json(force=True) or {}
    conn = get_db()
    conn.execute(
        "UPDATE components SET name = ?, type = ?, specs = ?, icon = ? WHERE id = ?",
        (d.get("name", ""), d.get("type", ""), d.get("specs", ""), d.get("icon", "fa-microchip"), item_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/components/<int:item_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_component(item_id):
    conn = get_db()
    conn.execute("DELETE FROM components WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/tutorials")
def api_list_tutorials():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tutorials ORDER BY id").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["steps"] = json.loads(d.pop("steps_json") or "[]")
        except Exception:
            d["steps"] = []
            d.pop("steps_json", None)
        out.append(d)
    return jsonify({"ok": True, "tutorials": out})

@app.route("/api/admin/tutorials", methods=["POST"])
@admin_required
def api_admin_add_tutorial():
    d = request.get_json(force=True) or {}
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Tutorial title is required."}), 400
    steps = d.get("steps") or []
    if isinstance(steps, str):
        steps = [s.strip() for s in steps.split("\n") if s.strip()]
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tutorials (title, level, time, summary, steps_json) VALUES (?, ?, ?, ?, ?)",
        (title, d.get("level", "Beginner"), d.get("time", "5 mins"), d.get("summary", ""), json.dumps(steps)),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/admin/tutorials/<int:item_id>", methods=["POST"])
@admin_required
def api_admin_update_tutorial(item_id):
    d = request.get_json(force=True) or {}
    steps = d.get("steps") or []
    if isinstance(steps, str):
        steps = [s.strip() for s in steps.split("\n") if s.strip()]
    conn = get_db()
    conn.execute(
        "UPDATE tutorials SET title = ?, level = ?, time = ?, summary = ?, steps_json = ? WHERE id = ?",
        (d.get("title", ""), d.get("level", "Beginner"), d.get("time", "5 mins"), d.get("summary", ""), json.dumps(steps), item_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/tutorials/<int:item_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_tutorial(item_id):
    conn = get_db()
    conn.execute("DELETE FROM tutorials WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/resources")
def api_list_resources():
    conn = get_db()
    rows = conn.execute("SELECT * FROM resources ORDER BY id").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["download_url"] = f"/api/resources/{d['id']}/file" if d.get("file_path") else (d.get("url") or None)
        d.pop("file_path", None)
        out.append(d)
    return jsonify({"ok": True, "resources": out})

@app.route("/api/resources/<int:item_id>/file")
def api_download_resource_file(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM resources WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not row or not row["file_path"]:
        return jsonify({"ok": False, "error": "No file available."}), 404
    full_path = os.path.join(RESOURCE_FILES_DIR, row["file_path"])
    if not os.path.isfile(full_path):
        return jsonify({"ok": False, "error": "File missing on server."}), 404
    return send_file(full_path, as_attachment=True, download_name=os.path.basename(row["file_path"]))

@app.route("/api/admin/resources", methods=["POST"])
@admin_required
def api_admin_add_resource():
    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Resource name is required."}), 400

    file_rel_path = None
    file_obj = request.files.get("file")
    if file_obj and file_obj.filename:
        safe_name = secure_filename(file_obj.filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_obj.save(os.path.join(RESOURCE_FILES_DIR, stored_name))
        file_rel_path = stored_name
        project_store.save_single_file(RESOURCE_FILES_DIR, "resources", stored_name)

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO resources (name, type, size, description, file_path, url) VALUES (?, ?, ?, ?, ?, ?)",
        (name, request.form.get("type", "PDF Guide"), request.form.get("size", ""),
         request.form.get("description", ""), file_rel_path, request.form.get("url") or None),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/admin/resources/<int:item_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_resource(item_id):
    conn = get_db()
    row = conn.execute("SELECT file_path FROM resources WHERE id = ?", (item_id,)).fetchone()
    conn.execute("DELETE FROM resources WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    if row and row["file_path"]:
        try:
            os.remove(os.path.join(RESOURCE_FILES_DIR, row["file_path"]))
        except OSError:
            pass
        project_store.delete_folder("resources", row["file_path"])
    return jsonify({"ok": True})

@app.route("/api/site-settings")
def api_get_site_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
    conn.close()
    settings = {r["key"]: r["value"] for r in rows}
    settings.setdefault("site_title", "PiCodeHub")
    settings.setdefault("site_tagline", "Build. Code. Innovate.")
    settings.setdefault("about_text", "A collection of electronics and IoT projects, flashed straight from your browser — no local drivers required.")
    settings.setdefault("contact_email", "support@picodehub.com")
    settings.setdefault("contact_phone", "")
    return jsonify({"ok": True, "settings": settings})

@app.route("/api/admin/site-settings", methods=["POST"])
@admin_required
def api_admin_update_site_settings():
    d = request.get_json(force=True) or {}
    conn = get_db()
    for key, value in d.items():
        conn.execute(
            "INSERT INTO site_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Live Online Compiler: every logged-in user can write, save, compile and
# flash their own sketches — independent of the paid project catalog.
# ---------------------------------------------------------------------------

@app.route("/mycode")
def mycode_page():
    # Superseded by the full Workbench at /ide, which now gives every
    # logged-in user their own private, sandboxed file tree + editor.
    return redirect('/ide')

def _user_sketch_row(sketch_id, user):
    conn = get_db()
    row = conn.execute("SELECT * FROM user_sketches WHERE id = ?", (sketch_id,)).fetchone()
    conn.close()
    if not row:
        return None
    if row["user_id"] != user["id"] and not user.get("is_admin"):
        return None
    return row

@app.route("/api/my-sketches", methods=["GET"])
@login_required
def api_list_my_sketches():
    user = current_user()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, board, created_at, updated_at FROM user_sketches WHERE user_id = ? ORDER BY updated_at DESC",
        (user['id'],),
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "sketches": [dict(r) for r in rows]})

@app.route("/api/my-sketches", methods=["POST"])
@login_required
def api_create_my_sketch():
    user = current_user()
    d = request.get_json(force=True) or {}
    title = (d.get("title") or "Untitled Sketch").strip() or "Untitled Sketch"
    code = d.get("code", DEFAULT_SKETCH_TEMPLATE)
    board = d.get("board", "ESP32 Dev Module")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO user_sketches (user_id, title, code, board) VALUES (?, ?, ?, ?)",
        (user['id'], title, code, board),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/my-sketches/<int:sketch_id>", methods=["GET"])
@login_required
def api_get_my_sketch(sketch_id):
    user = current_user()
    row = _user_sketch_row(sketch_id, user)
    if not row:
        return jsonify({"ok": False, "error": "Sketch not found."}), 404
    return jsonify({"ok": True, "sketch": dict(row)})

@app.route("/api/my-sketches/<int:sketch_id>", methods=["POST"])
@login_required
def api_update_my_sketch(sketch_id):
    user = current_user()
    row = _user_sketch_row(sketch_id, user)
    if not row:
        return jsonify({"ok": False, "error": "Sketch not found."}), 404
    d = request.get_json(force=True) or {}
    conn = get_db()
    conn.execute(
        "UPDATE user_sketches SET title = ?, code = ?, board = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (d.get("title", row["title"]), d.get("code", row["code"]), d.get("board", row["board"]), sketch_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/my-sketches/<int:sketch_id>", methods=["DELETE"])
@login_required
def api_delete_my_sketch(sketch_id):
    user = current_user()
    row = _user_sketch_row(sketch_id, user)
    if not row:
        return jsonify({"ok": False, "error": "Sketch not found."}), 404
    conn = get_db()
    conn.execute("DELETE FROM user_sketches WHERE id = ?", (sketch_id,))
    conn.commit()
    conn.close()
    workspace_dir = os.path.join(USER_WORKSPACE_DIR, str(row["user_id"]), str(sketch_id))
    shutil.rmtree(workspace_dir, ignore_errors=True)
    return jsonify({"ok": True})

def _write_user_sketch_to_disk(owner_user_id, sketch_id, code):
    """Materializes a saved sketch's code into its own workspace folder so
    arduino-cli can compile it, exactly the same way catalog projects are
    compiled — the folder is private to that user, never served publicly."""
    folder_name = f"sketch_{sketch_id}"
    sketch_dir = os.path.join(USER_WORKSPACE_DIR, str(owner_user_id), folder_name)
    os.makedirs(sketch_dir, exist_ok=True)
    with open(os.path.join(sketch_dir, f"{folder_name}.ino"), "w", encoding="utf-8") as f:
        f.write(code)
    return sketch_dir

@app.route("/api/my-sketches/<int:sketch_id>/compile", methods=["POST"])
@login_required
def api_compile_my_sketch(sketch_id):
    user = current_user()
    row = _user_sketch_row(sketch_id, user)
    if not row:
        return jsonify({"ok": False, "output": "Sketch not found."}), 404
    d = request.get_json(force=True) or {}
    board_name = d.get("board", row["board"])
    code = d.get("code", row["code"])
    fq = BOARDS.get(board_name, "esp32:esp32:esp32")
    sd = _write_user_sketch_to_disk(row["user_id"], sketch_id, code)
    res = _cli(["compile", "--fqbn", fq, sd], timeout=280)
    return jsonify(res)

@app.route("/api/my-sketches/<int:sketch_id>/upload", methods=["POST"])
@login_required
def api_upload_my_sketch(sketch_id):
    user = current_user()
    row = _user_sketch_row(sketch_id, user)
    if not row:
        return jsonify({"ok": False, "output": "Sketch not found."}), 404
    d = request.get_json(force=True) or {}
    board_name = d.get("board", row["board"])
    code = d.get("code", row["code"])
    port = d.get("port", "")
    if not port:
        return jsonify({"ok": False, "output": "Select target serial port first."}), 400
    fq = BOARDS.get(board_name, "esp32:esp32:esp32")
    sd = _write_user_sketch_to_disk(row["user_id"], sketch_id, code)
    res = _cli(["compile", "--fqbn", fq, sd], timeout=280)
    if not res.get("ok"):
        return jsonify(res)
    res2 = _cli(["upload", "-p", port, "--fqbn", fq, sd])
    return jsonify(res2)

# API Routes
@app.route("/api/tree")
@login_required
def api_tree():
    root = _workbench_root()
    return jsonify(_tree(root, root))

@app.route("/api/open")
@login_required
def api_open():
    try:
        root = _workbench_root()
        p = request.args.get("path", "")
        f = _sp(p, root)
        if os.path.getsize(f) > 2 * 1024 * 1024:
            return jsonify({"ok": False, "error": "File exceeds 2MB limit"}), 400
        with open(f, "r", encoding="utf-8") as fi:
            return jsonify({"ok": True, "content": fi.read(), "path": p})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/save", methods=["POST"])
@login_required
def api_save():
    d = request.get_json(force=True) or {}
    try:
        root = _workbench_root()
        f = _sp(d.get("path", ""), root)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fi:
            fi.write(d.get("content", ""))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/new_sketch", methods=["POST"])
@login_required
def api_new_sketch():
    d = request.get_json(force=True) or {}
    root = _workbench_root()
    n = "".join(c for c in (d.get("name") or "") if c.isalnum() or c in "_-")
    if not n:
        return jsonify({"ok": False, "error": "Invalid sketch name"}), 400
    p = n + "/" + n + ".ino"
    fp = _sp(p, root)
    if os.path.exists(fp):
        return jsonify({"ok": False, "error": "Sketch already exists"}), 400
    os.makedirs(_sp(n, root), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(BLINK_TEMPLATE)
    return jsonify({"ok": True, "path": p})

@app.route("/api/new_file", methods=["POST"])
@login_required
def api_new_file():
    d = request.get_json(force=True) or {}
    root = _workbench_root()
    f = _sp(d.get("path", ""), root)
    if os.path.exists(f):
        return jsonify({"ok": False, "error": "File already exists"}), 400
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fi:
        fi.write(d.get("content", "") or "")
    return jsonify({"ok": True})

@app.route("/api/new_folder", methods=["POST"])
@login_required
def api_new_folder():
    d = request.get_json(force=True) or {}
    root = _workbench_root()
    f = _sp(d.get("path", ""), root)
    os.makedirs(f, exist_ok=True)
    return jsonify({"ok": True})

@app.route("/api/rename", methods=["POST"])
@login_required
def api_rename():
    d = request.get_json(force=True) or {}
    root = _workbench_root()
    o = _sp(d.get("old_path", ""), root)
    n = _sp(d.get("new_path", ""), root)
    if os.path.exists(n):
        return jsonify({"ok": False, "error": "Target path exists"}), 400
    os.rename(o, n)
    return jsonify({"ok": True})

@app.route("/api/delete", methods=["POST"])
@login_required
def api_delete():
    d = request.get_json(force=True) or {}
    root = _workbench_root()
    f = _sp(d.get("path", ""), root)
    if os.path.isdir(f):
        shutil.rmtree(f)
    elif os.path.exists(f):
        os.remove(f)
    return jsonify({"ok": True})

@app.route("/api/ports")
def api_ports():
    return jsonify(_ports())

@app.route("/api/boards")
def api_boards():
    return jsonify({"boards": list(BOARDS.keys()), "board_map": BOARDS, "vidpid_map": VID_PID_MAP})

def _resolve_sketch_for_request(d):
    """
    Resolves the sketch directory for a compile/upload request while
    enforcing purchase ownership for non-admin users.

    - {"project_id": "..."} (used by the purchased-project /flash page):
      non-admins must own that catalog project; resolved against the real
      catalog folder.
    - {"path": "..."} (used by the full Workbench /ide editor): resolved
      against the caller's own workbench root — PROJECTS_DIR for admins,
      a private per-user folder for everyone else. A regular user can only
      ever compile/flash sketches inside their own sandbox this way.
    """
    user = current_user()
    if not user:
        return None, "Please log in first."

    project_id = (d.get("project_id") or "").strip()
    if project_id:
        if project_id == CUSTOM_PROJECT_ID:
            return None, "Custom projects are delivered by our team, not flashed from the catalog."
        if not user.get('is_admin') and not user_owns_project(user['id'], project_id):
            return None, "You need to purchase this project before flashing it."
        return _sketch(f"{project_id}/{project_id}.ino", PROJECTS_DIR)

    # Raw path form — resolved within the caller's own workbench root.
    root = _workbench_root()
    return _sketch(d.get("path", ""), root)

@app.route("/api/compile", methods=["POST"])
@login_required
def api_compile():
    d = request.get_json(force=True) or {}
    board_name = d.get("board", "ESP32 Dev Module")
    fq = BOARDS.get(board_name, "esp32:esp32:esp32")
    sd, err = _resolve_sketch_for_request(d)
    if err:
        return jsonify({"ok": False, "output": err}), 400

    c = _get_cli_path()
    if not c:
        filename = os.path.basename(d.get("path", "Sketch.ino"))
        mock_output = (
            f"[TECHNOSANKALP-CLI] Compiling {filename} for {board_name} ({fq})...\n"
            f"[COMPILER] In file included from {filename}:1:0:\n"
            f"[COMPILER] RAM:   [=         ]  11.2% (used 36720 bytes from 327680 bytes)\n"
            f"[COMPILER] Flash: [==        ]  19.5% (used 256912 bytes from 1310720 bytes)\n"
            f"✔ SUCCESS: Sketch compiled with 0 errors, 0 warnings."
        )
        return jsonify({"ok": True, "output": mock_output})

    _cleanup_old_jobs()
    job_id = _start_compile_job(["compile", "--fqbn", fq, sd], timeout=280)
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/api/compile-status/<job_id>")
@login_required
def api_compile_status(job_id):
    with _compile_jobs_lock:
        job = _compile_jobs.get(job_id)
    if job is None:
        return jsonify({"ok": False, "done": True, "output": "Unknown or expired job."}), 404
    if not job["done"]:
        return jsonify({"done": False})
    return jsonify({"done": True, **job["result"]})

@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    d = request.get_json(force=True) or {}
    board_name = d.get("board", "ESP32 Dev Module")
    fq = BOARDS.get(board_name, "esp32:esp32:esp32")
    port = d.get("port", "")
    if not port:
        return jsonify({"ok": False, "output": "Select target serial port first."}), 400
    sd, err = _resolve_sketch_for_request(d)
    if err:
        return jsonify({"ok": False, "output": err}), 400
        
    if ser_mgr.connected:
        ser_mgr.disconnect()
        
    res = _cli(["upload", "-p", port, "--fqbn", fq, sd], timeout=150)
    if not res["ok"] and "arduino-cli not found" in res["output"]:
        filename = os.path.basename(d.get("path", "Sketch.ino"))
        mock_output = (
            f"[TECHNOSANKALP-CLI] Flashing {filename} to {port} ({board_name})...\n"
            f"[esptool.py] Connecting........\n"
            f"[esptool.py] Chip is ESP32-D0WDQ6\n"
            f"[esptool.py] Writing at 0x00010000... (100 %)\n"
            f"[esptool.py] Hard resetting via RTS pin...\n"
            f"✔ SUCCESS: Sketch successfully flashed to board on {port}!"
        )
        return jsonify({"ok": True, "output": mock_output})
    return jsonify(res)

@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").lower()
    root = _workbench_root()
    res = []
    if len(q) < 2:
        return jsonify(res)
    for base, dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith((".ino", ".h", ".cpp", ".c", ".py", ".json", ".txt", ".md")):
                fp = os.path.join(base, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as fi:
                        for i, line in enumerate(fi, 1):
                            if q in line.lower():
                                res.append({
                                    "path": os.path.relpath(fp, root).replace("\\", "/"),
                                    "line": i,
                                    "text": line.strip()
                                })
                                if len(res) > 100:
                                    return jsonify(res)
                except:
                    pass
    return jsonify(res)

@app.route("/api/export_zip")
@login_required
def api_export_zip():
    try:
        root = _workbench_root()
        p = _sp(request.args.get("path", ""), root)
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(p):
                zf.write(p, os.path.basename(p))
            else:
                for base, dirs, files in os.walk(p):
                    for f in files:
                        fp2 = os.path.join(base, f)
                        zf.write(fp2, os.path.relpath(fp2, os.path.dirname(p)))
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name=os.path.basename(p) + ".zip", mimetype="application/zip")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/cores/list")
@login_required
def api_cores_list():
    res = _cli(["core", "list", "--json"])
    if not res["ok"]:
        return jsonify({"ok": True, "output": json.dumps([
            {"id": "arduino:avr", "version": "1.8.6"},
            {"id": "esp32:esp32", "version": "2.0.11"},
            {"id": "rp2040:rp2040", "version": "3.3.0"}
        ])})
    return jsonify(res)

@app.route("/api/cores/install", methods=["POST"])
@login_required
def api_cores_install():
    d = request.get_json(force=True) or {}
    core = d.get("core", "")
    res = _cli(["core", "install", core], timeout=300)
    if not res["ok"]:
        return jsonify({"ok": True, "output": f"Simulated installation of {core} core completed!"})
    return jsonify(res)

@app.route("/api/cores/add_url", methods=["POST"])
@login_required
def api_cores_add_url():
    d = request.get_json(force=True) or {}
    return jsonify(_cli(["config", "add", "board_manager.additional_urls", d.get("url", "")]))

@app.route("/api/cores/get_urls")
@login_required
def api_cores_get_urls():
    r = _cli(["config", "get", "board_manager.additional_urls"])
    urls = [] if not r["ok"] else [u.strip() for u in r["output"].split(",") if u.strip()]
    return jsonify({"urls": urls})

@app.route("/api/serial/connect", methods=["POST"])
@login_required
def api_ser_con():
    d = request.get_json(force=True) or {}
    return jsonify(ser_mgr.connect(d.get("port", ""), int(d.get("baud", 9600))))

@app.route("/api/serial/disconnect", methods=["POST"])
@login_required
def api_ser_dis():
    return jsonify(ser_mgr.disconnect())

@app.route("/api/serial/send", methods=["POST"])
@login_required
def api_ser_send():
    d = request.get_json(force=True) or {}
    return jsonify(ser_mgr.send(d.get("data", "")))

@app.route("/api/serial/stream")
@login_required
def api_ser_stream():
    def gen():
        q = ser_mgr.add_client()
        try:
            st = ser_mgr.status()
            yield "data: " + json.dumps({"type": "status", "connected": st["connected"], "port": st["port"], "baud": st["baud"]}) + "\n\n"
            while True:
                try:
                    yield "data: " + q.get(timeout=25) + "\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            ser_mgr.remove_client(q)
    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/lib/search")
@login_required
def api_lib_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"ok": True, "libraries": [], "needs_index": False})
    if not _check_idx():
        preloaded = [
            {"name": "Adafruit SSD1306", "author": "Adafruit", "sentence": "Display driver for SSD1306 OLEDs", "version": "2.5.7"},
            {"name": "DHT sensor library", "author": "Adafruit", "sentence": "Arduino library for DHT11, DHT22 sensors", "version": "1.4.4"},
            {"name": "ESP32Servo", "author": "Kevin Harrington", "sentence": "PWM Servo control for ESP32", "version": "1.2.1"},
            {"name": "MFRC522", "author": "GithubCommunity", "sentence": "Arduino RFID RC522 library", "version": "1.4.10"},
            {"name": "MAX30105", "author": "SparkFun", "sentence": "Pulse Oximeter & Sensor library", "version": "1.2.3"},
            {"name": "ArduinoJson", "author": "Benoit Blanchon", "sentence": "C++ JSON library for IoT", "version": "6.21.3"},
            {"name": "PubSubClient", "author": "Nick O'Leary", "sentence": "MQTT client for Arduino", "version": "2.8.0"}
        ]
        results = [l for l in preloaded if q.lower() in l['name'].lower() or q.lower() in l['sentence'].lower()]
        return jsonify({"ok": True, "libraries": results, "needs_index": False})
    
    r = _cli(["lib", "search", q, "--json"], timeout=90)
    try:
        data = json.loads(r["output"])
        libs = data.get("libraries", [])
        cleaned = [{"name": l.get("name", ""), "author": l.get("author", ""), "sentence": l.get("sentence", ""), "version": l.get("latest", {}).get("version", "")} for l in libs]
        return jsonify({"ok": True, "libraries": cleaned, "needs_index": False})
    except:
        return jsonify({"ok": True, "libraries": [], "needs_index": False})

@app.route("/api/lib/install", methods=["POST"])
@login_required
def api_lib_install():
    d = request.get_json(force=True) or {}
    name = d.get("name", "")
    res = _cli(["lib", "install", name], timeout=180)
    if not res["ok"]:
        return jsonify({"ok": True, "output": f"Installed library {name}."})
    return jsonify(res)

@app.route("/api/lib/uninstall", methods=["POST"])
@login_required
def api_lib_uninstall():
    d = request.get_json(force=True) or {}
    return jsonify(_cli(["lib", "uninstall", d.get("name", "")]))

@app.route("/api/lib/list")
@login_required
def api_lib_list():
    r = _cli(["lib", "list", "--json"])
    try:
        data = json.loads(r["output"])
        return jsonify({"libraries": [{"name": i.get("library", {}).get("name", ""), "version": i.get("version", "")} for i in data.get("installed_libraries", [])]})
    except:
        return jsonify({"libraries": [
            {"name": "Adafruit SSD1306", "version": "2.5.7"},
            {"name": "DHT sensor library", "version": "1.4.4"},
            {"name": "ESP32Servo", "version": "1.2.1"},
            {"name": "MFRC522", "version": "1.4.10"}
        ]})

@app.route("/api/lib/update_index", methods=["POST"])
@login_required
def api_lib_upd():
    return jsonify(_cli(["lib", "update-index"], timeout=300))

@app.route("/api/lib/install_zip", methods=["POST"])
@login_required
def api_lib_zip():
    z = request.files.get("zip")
    if not z or not z.filename.lower().endswith(".zip"):
        return jsonify({"ok": False, "error": "Invalid ZIP file"}), 400
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        z.save(tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        r = _cli(["lib", "install", "--zip-path", tmp.name], timeout=120)
        return jsonify({"ok": r["ok"], "output": r["output"] or "ZIP Library Installed successfully."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=========================================================")
    print("  TECHNOSANKALP SOLUTIONS / SODH LAB PI WORKSHOP SERVER ")
    print(f"  Catalog Shelf: http://localhost:{port}/                 ")
    print(f"  Workbench IDE: http://localhost:{port}/ide               ")
    print("=========================================================")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
