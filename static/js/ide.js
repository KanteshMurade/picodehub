/* =========================================================
   Technosankalp Solutions / Sodh Lab IDE - ide.js
   ========================================================= */
var E = null, blankModel = null;
var tabs = [], aTab = -1;
var selPort = null, busy = false;
var mRes = null, serCon = false, serEv = null;
var mCtxTarget = null;

var BOARD_INFO = {
  "Arduino Uno":       { cpu: "16 MHz", flash: "32 KB",  boot: "Optiboot"  },
  "Arduino Nano":      { cpu: "16 MHz", flash: "32 KB",  boot: "Optiboot"  },
  "Arduino Mega":      { cpu: "16 MHz", flash: "256 KB", boot: "Optiboot"  },
  "ESP32 Dev Module":  { cpu: "240 MHz",flash: "4 MB",   boot: "ESP-IDF"   },
  "ESP8266 NodeMCU":   { cpu: "80 MHz", flash: "4 MB",   boot: "ESP-IDF"   },
  "Raspberry Pi Pico": { cpu: "133 MHz",flash: "2 MB",   boot: "UF2"       },
};

var VID_PID_MAP = {
  "2341:0043": "Arduino Uno",  "2341:0001": "Arduino Uno",
  "2341:0042": "Arduino Mega", "2A03:0043": "Arduino Uno",
  "1A86:7523": "Arduino Uno (CH340)", "1A86:43FF": "Arduino Uno (CH340)",
  "303A:1001": "ESP32 Dev Module",
  "10C4:EA60": "ESP8266 NodeMCU (CH340)",
  "2E8A:0005": "Raspberry Pi Pico"
};

// ── File language detection ─────────────────────────────────
function lang(n) {
  var e = (n.split('.').pop() || '').toLowerCase();
  return {
    ino:'cpp', pde:'cpp', c:'c', h:'cpp', cpp:'cpp', hpp:'cpp',
    py:'python', js:'javascript', ts:'typescript', json:'json',
    html:'html', css:'css', xml:'xml', md:'markdown',
    yaml:'yaml', yml:'yaml', sh:'shell', txt:'plaintext'
  }[e] || 'plaintext';
}

// ── File icon mapping ───────────────────────────────────────
function fileIconClass(n) {
  var e = (n.split('.').pop() || '').toLowerCase();
  var icons = {
    ino:'fas fa-circle-dot', cpp:'fas fa-code', c:'fas fa-code',
    h:'fas fa-file-code', hpp:'fas fa-file-code',
    py:'fab fa-python', js:'fab fa-js', ts:'fas fa-file-code',
    json:'fas fa-brackets-curly', html:'fab fa-html5',
    css:'fab fa-css3-alt', md:'fab fa-markdown',
    png:'fas fa-image', jpg:'fas fa-image', jpeg:'fas fa-image',
    gif:'fas fa-image', svg:'fas fa-vector-square',
    pdf:'fas fa-file-pdf', zip:'fas fa-file-zipper',
    txt:'fas fa-file-lines'
  };
  return icons[e] || 'fas fa-file';
}

function fileColorClass(n) {
  var e = (n.split('.').pop() || '').toLowerCase();
  if (['ino','pde'].includes(e)) return 'file-ino';
  if (['h','hpp'].includes(e)) return 'file-h';
  if (['png','jpg','jpeg','gif','svg'].includes(e)) return 'file-img';
  if (['md','txt'].includes(e)) return 'file-md';
  return '';
}

// ── Monaco Initialization ───────────────────────────────────
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
require(['vs/editor/editor.main'], function () {
  var isLight = localStorage.getItem('sl-thm') === 'light';
  if (isLight) document.body.classList.add('light');

  var fs = parseInt(localStorage.getItem('sl-fs')) || 14;
  var ts = parseInt(localStorage.getItem('sl-ts')) || 2;
  if (document.getElementById('s-fs')) document.getElementById('s-fs').value = fs;
  if (document.getElementById('s-ts')) document.getElementById('s-ts').value = ts;
  if (document.getElementById('s-ww')) document.getElementById('s-ww').checked = localStorage.getItem('sl-ww') === '1';
  if (document.getElementById('s-mm')) document.getElementById('s-mm').checked = localStorage.getItem('sl-mm') !== '0';

  blankModel = monaco.editor.createModel(
    '// Welcome to Technosankalp Sodh Lab IDE\n// Open a sketch from the Explorer or Catalog Shelf to start editing.\n', 'cpp'
  );

  E = monaco.editor.create(document.getElementById('editor'), {
    value: '',
    language: 'cpp',
    theme: isLight ? 'vs' : 'vs-dark',
    automaticLayout: true,
    fontSize: fs,
    tabSize: ts,
    insertSpaces: true,
    wordWrap: localStorage.getItem('sl-ww') === '1' ? 'on' : 'off',
    minimap: { enabled: localStorage.getItem('sl-mm') !== '0' },
    scrollBeyondLastLine: false,
    bracketPairColorization: { enabled: true },
    model: blankModel
  });

  E.onDidChangeModelContent(function () { setDirty(true); });
  E.onDidChangeCursorPosition(function (e) {
    document.getElementById('st-pos').textContent = 'Ln ' + e.position.lineNumber + ', Col ' + e.position.column;
  });

  loadBoards();
  loadLibs();
  loadCores();
  initSer();
  loadUrls();
  scanPorts();

  refTree().then(function () {
    var urlParams = new URLSearchParams(window.location.search);
    var initPath = urlParams.get('open');
    if (initPath) openTab(initPath);
  });
});

// ── Theme ──────────────────────────────────────────────────
function toggleTheme() {
  var l = document.body.classList.toggle('light');
  if (E) monaco.editor.setTheme(l ? 'vs' : 'vs-dark');
  localStorage.setItem('sl-thm', l ? 'light' : 'dark');
}

// ── Settings ───────────────────────────────────────────────
function applySettings() {
  if (!E) return;
  E.updateOptions({
    fontSize: parseInt(document.getElementById('s-fs').value) || 14,
    tabSize: parseInt(document.getElementById('s-ts').value) || 2,
    wordWrap: document.getElementById('s-ww').checked ? 'on' : 'off',
    minimap: { enabled: document.getElementById('s-mm').checked }
  });
  localStorage.setItem('sl-fs', document.getElementById('s-fs').value);
  localStorage.setItem('sl-ts', document.getElementById('s-ts').value);
  localStorage.setItem('sl-ww', document.getElementById('s-ww').checked ? '1' : '0');
  localStorage.setItem('sl-mm', document.getElementById('s-mm').checked ? '1' : '0');
}

// ── Activity Bar / Panel switching ────────────────────────
function switchPanel(name) {
  document.querySelectorAll('.ai').forEach(function (a) {
    a.classList.toggle('act', a.dataset.panel === name);
  });
  document.querySelectorAll('.sidebar-panel').forEach(function (p) {
    p.classList.toggle('act', p.id === 'panel-' + name);
  });
  if (name === 'libraries') loadLibs();
  if (name === 'boards') loadCores();
  if (name === 'search') setTimeout(function () { document.getElementById('gs-in').focus(); }, 50);
}

// ── Tabs ───────────────────────────────────────────────────
function openTab(path) {
  var i = tabs.findIndex(function (t) { return t.path === path; });
  if (i !== -1) { swTab(i); return; }
  fetch('/api/open?path=' + encodeURIComponent(path))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d.ok) { setSt('Cannot open: ' + path, 'fail'); return; }
      var m = monaco.editor.createModel(d.content, lang(path));
      tabs.push({ path: path, name: path.split('/').pop(), model: m, dirty: false, vs: null, sp: 0 });
      swTab(tabs.length - 1);
      renTabs();
    });
}

function swTab(i) {
  if (aTab !== -1 && tabs[aTab]) {
    tabs[aTab].vs = E.saveViewState();
    tabs[aTab].sp = E.getScrollTop();
  }
  aTab = i;
  var t = tabs[i];
  E.setModel(t.model);
  if (t.vs) E.restoreViewState(t.vs);
  E.setScrollTop(t.sp);
  monaco.editor.setModelLanguage(E.getModel(), lang(t.name));
  updStatus();
  renTabs();
  setDirty(t.dirty);
  document.getElementById('active-filename').textContent = t.name;
  hlAct(t.path);
}

function renTabs() {
  var tb = document.getElementById('tab-bar');
  tb.innerHTML = '';
  tabs.forEach(function (t, i) {
    var d = document.createElement('div');
    d.className = 'tab' + (i === aTab ? ' act' : '');
    d.innerHTML =
      '<i class="' + fileIconClass(t.name) + ' tab-icon"></i>' +
      '<span class="tab-name">' + esc(t.name) + '</span>' +
      (t.dirty ? '<span class="tab-dirty">●</span>' : '') +
      '<button class="tab-close" onclick="event.stopPropagation();closeTab(' + i + ')" title="Close">×</button>';
    d.onclick = function () { swTab(i); };
    tb.appendChild(d);
  });
}

function closeTab(i) {
  if (tabs[i].dirty && !confirm('Discard unsaved changes to ' + tabs[i].name + '?')) return;
  tabs[i].model.dispose();
  tabs.splice(i, 1);
  if (tabs.length === 0) {
    aTab = -1;
    E.setModel(blankModel);
    document.getElementById('tab-bar').innerHTML = '';
    document.title = 'Technosankalp Solutions — IDE';
    document.getElementById('active-filename').textContent = 'No file open';
    document.body.classList.remove('dirty');
  } else {
    aTab = Math.max(0, i <= aTab ? aTab - 1 : aTab);
    swTab(aTab);
  }
  renTabs();
}

function setDirty(dirty) {
  if (aTab !== -1) tabs[aTab].dirty = dirty;
  document.body.classList.toggle('dirty', !!dirty);
  renTabs();
  if (aTab !== -1) {
    document.title = (dirty ? '● ' : '') + tabs[aTab].name + ' — Technosankalp Solutions IDE';
  }
}

// ── Save ───────────────────────────────────────────────────
async function saveCurrent() {
  if (aTab === -1) return;
  setSt('Saving…', 'run');
  var t = tabs[aTab];
  var r = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: t.path, content: E.getValue() })
  });
  var d = await r.json();
  if (d.ok) { t.dirty = false; setDirty(false); setSt('Saved — ' + t.name, 'ok'); }
  else setSt('Save failed', 'fail');
}

// ── New Sketch / File / Folder ─────────────────────────────
async function doNewSketch() {
  var n = await mod('New Sketch', 'Sketch name (e.g. BlinkLED):', 'MySketch');
  if (!n) return;
  setSt('Creating sketch…', 'run');
  var r = await fetch('/api/new_sketch', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: n })
  });
  var d = await r.json();
  if (d.ok) { await refTree(); openTab(d.path); }
  else setSt(d.error || 'Failed', 'fail');
}

async function doNewFile() {
  var n = await mod('New File', 'File path (e.g. MySketch/config.h):', '');
  if (!n) return;
  var r = await fetch('/api/new_file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: n })
  });
  var d = await r.json();
  if (d.ok) { await refTree(); openTab(n); }
  else setSt(d.error || 'Failed', 'fail');
}

async function doNewFolder() {
  var n = await mod('New Folder', 'Folder path:', '');
  if (!n) return;
  var r = await fetch('/api/new_folder', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: n })
  });
  var d = await r.json();
  if (d.ok) { await refTree(); setSt('Folder created', 'ok'); }
  else setSt(d.error || 'Failed', 'fail');
}

// ── Tree ───────────────────────────────────────────────────
async function refTree() {
  var r = await fetch('/api/tree');
  var d = await r.json();
  var c = document.getElementById('tree');
  c.innerHTML = '';
  if (!d.length) {
    c.innerHTML = '<div class="empty-state">No projects yet.<br>Click + to create a sketch.</div>';
    return;
  }
  rNodes(d, c, 0);
  if (aTab !== -1) hlAct(tabs[aTab].path);
}

function rNodes(nodes, container, depth) {
  nodes.forEach(function (nd) {
    var el = document.createElement('div');
    var isDir = nd.type === 'folder' || nd.is_dir;
    el.className = 'tree-item' + (isDir ? ' folder' : ' ' + fileColorClass(nd.name));
    el.dataset.p = nd.path;
    el.style.paddingLeft = (12 + depth * 14) + 'px';
    var icon = isDir ? 'fas fa-chevron-right' : fileIconClass(nd.name);
    el.innerHTML =
      '<i class="' + icon + ' ti-icon" id="ic-' + nd.path.replace(/[^a-z0-9]/gi,'_') + '"></i>' +
      '<span class="ti-name">' + esc(nd.name) + '</span>' +
      '<i class="fas fa-ellipsis ti-menu" onclick="event.stopPropagation();showCtx(event,\'' + escA(nd.path) + '\',\'' + (isDir?'folder':'file') + '\')"></i>';
    container.appendChild(el);

    if (isDir) {
      var child = document.createElement('div');
      child.className = 'tree-children collapsed';
      child.id = 'tc-' + nd.path.replace(/[^a-z0-9]/gi, '_');
      rNodes(nd.children || [], child, depth + 1);
      container.appendChild(child);
      el.onclick = function () {
        child.classList.toggle('collapsed');
        var icEl = document.getElementById('ic-' + nd.path.replace(/[^a-z0-9]/gi,'_'));
        if (icEl) {
          icEl.className = child.classList.contains('collapsed')
            ? 'fas fa-chevron-right ti-icon'
            : 'fas fa-chevron-down ti-icon';
        }
      };
      el.oncontextmenu = function (ev) { ev.preventDefault(); showCtx(ev, nd.path, 'folder'); };
    } else {
      el.onclick = function () { openTab(nd.path); };
      el.oncontextmenu = function (ev) { ev.preventDefault(); showCtx(ev, nd.path, 'file'); };
    }
  });
}

function hlAct(p) {
  document.querySelectorAll('.tree-item').forEach(function (e) { e.classList.remove('act'); });
  if (p) {
    var el = document.querySelector('.tree-item[data-p="' + CSS.escape(p) + '"]');
    if (el) el.classList.add('act');
  }
}

// ── Context Menu ───────────────────────────────────────────
function showCtx(ev, p, type) {
  mCtxTarget = { p: p, type: type };
  var m = document.getElementById('ctx-menu');
  var html = '';
  if (type === 'file') {
    html += '<div class="ctx-item" onclick="openTab(\'' + escA(p) + '\')"><i class="fas fa-folder-open"></i> Open</div>';
    html += '<div class="ctx-sep"></div>';
  }
  html += '<div class="ctx-item" onclick="ctxAct(\'file\')"><i class="fas fa-plus"></i> New File Here</div>';
  html += '<div class="ctx-item" onclick="ctxAct(\'folder\')"><i class="fas fa-folder-plus"></i> New Folder Here</div>';
  html += '<div class="ctx-sep"></div>';
  html += '<div class="ctx-item" onclick="ctxAct(\'rename\')"><i class="fas fa-pen"></i> Rename</div>';
  html += '<div class="ctx-item" onclick="zipExp(\'' + escA(p) + '\')"><i class="fas fa-file-zipper"></i> Download ZIP</div>';
  html += '<div class="ctx-sep"></div>';
  html += '<div class="ctx-item danger" onclick="delF(\'' + escA(p) + '\')"><i class="fas fa-trash"></i> Delete</div>';
  m.innerHTML = html;
  m.style.left = ev.clientX + 'px';
  m.style.top = ev.clientY + 'px';
  m.style.display = 'block';
  var rect = m.getBoundingClientRect();
  if (rect.right > window.innerWidth) m.style.left = (ev.clientX - rect.width) + 'px';
  if (rect.bottom > window.innerHeight) m.style.top = (ev.clientY - rect.height) + 'px';
}

async function ctxAct(type) {
  if (!mCtxTarget) return;
  var p = mCtxTarget.p;
  if (type === 'file') {
    var n = await mod('New File', 'File name:', '');
    if (n) {
      var np = p + (p.endsWith('/') ? '' : '/') + n;
      await fetch('/api/new_file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: np }) });
      await refTree(); openTab(np);
    }
  }
  if (type === 'folder') {
    var n = await mod('New Folder', 'Folder name:', '');
    if (n) {
      var np = p + (p.endsWith('/') ? '' : '/') + n;
      await fetch('/api/new_folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: np }) });
      await refTree();
    }
  }
  if (type === 'rename') {
    var oldN = p.split('/').pop();
    var pfx = p.substring(0, p.length - oldN.length);
    var newN = await mod('Rename', 'New name:', oldN);
    if (newN && newN !== oldN) {
      await fetch('/api/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old_path: p, new_path: pfx + newN }) });
      if (aTab !== -1 && tabs[aTab].path === p) {
        tabs[aTab].path = pfx + newN;
        tabs[aTab].name = newN;
        renTabs();
      }
      await refTree();
    }
  }
}

document.addEventListener('click', function () { document.getElementById('ctx-menu').style.display = 'none'; });

async function delF(p) {
  if (!confirm('Delete ' + p + '? This cannot be undone.')) return;
  await fetch('/api/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) });
  if (aTab !== -1 && (tabs[aTab].path === p || tabs[aTab].path.startsWith(p + '/'))) closeTab(aTab);
  refTree();
}

function zipExp(p) {
  window.open('/api/export_zip?path=' + encodeURIComponent(p), '_blank');
}

// ── Compile & Upload ───────────────────────────────────────
async function safeJson(resp) {
  const text = await resp.text();
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error('Server returned an unexpected response (HTTP ' + resp.status + '). It may have timed out — try again.');
  }
}

// Starts a compile job and polls for its result instead of waiting on one
// long HTTP request, which free-tier hosts (e.g. Render) kill with a 504
// before a real ESP32/AVR compile finishes.
async function compileAndPoll(body) {
  const startResp = await fetch('/api/compile', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const start = await safeJson(startResp);
  if (!start.ok) return start;
  if (start.job_id === undefined) return start; // mock/instant path

  while (true) {
    await new Promise(res => setTimeout(res, 1500));
    const pollResp = await fetch('/api/compile-status/' + start.job_id);
    const poll = await safeJson(pollResp);
    if (poll.done) return poll;
  }
}

async function doCompile() {
  if (aTab === -1) { setSt('Open a sketch file first.', 'fail'); return; }
  if (busy) return;
  if (tabs[aTab].dirty) { await saveCurrent(); }
  var b = document.getElementById('board-selector').value;
  switchBottomPane('output');
  logO('[BUILD] Compiling ' + tabs[aTab].name + ' for ' + b + '…', 'run');
  setSt('Compiling…', 'run');
  setBtnsDisabled(true);
  busy = true;
  try {
    var d = await compileAndPoll({ path: tabs[aTab].path, board: b });
    logO(d.output, d.ok ? 'ok' : 'fail');
    setSt(d.ok ? '✔ Build Succeeded' : '✘ Build Failed', d.ok ? 'ok' : 'fail');
  } catch (err) {
    logO(err.message, 'fail');
    setSt('✘ Build Failed', 'fail');
  }
  busy = false;
  setBtnsDisabled(false);
}

async function doUpload() {
  if (aTab === -1) { setSt('Open a sketch file first.', 'fail'); return; }
  if (!selPort) { setSt('Select a serial port first.', 'fail'); return; }
  if (busy) return;
  if (tabs[aTab].dirty) { await saveCurrent(); }
  var b = document.getElementById('board-selector').value;
  switchBottomPane('uploadlog');
  logO('[FLASH] Uploading ' + tabs[aTab].name + ' to ' + selPort + '…', 'run', 'pane-uploadlog');
  setSt('Uploading…', 'run');
  setBtnsDisabled(true);
  busy = true;
  var r = await fetch('/api/upload', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: tabs[aTab].path, board: b, port: selPort })
  });
  var d = await r.json();
  logO(d.output, d.ok ? 'ok' : 'fail', 'pane-uploadlog');
  setSt(d.ok ? '✔ Upload Complete' : '✘ Upload Failed', d.ok ? 'ok' : 'fail');
  busy = false;
  setBtnsDisabled(false);
}

function setBtnsDisabled(v) {
  ['btn-verify','btn-upload','rp-verify','rp-upload'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.disabled = v;
  });
}

// ── Board & Port ───────────────────────────────────────────
async function loadBoards() {
  var r = await fetch('/api/boards'), d = await r.json();
  var s = document.getElementById('board-selector');
  s.innerHTML = '';
  d.boards.forEach(function (n) {
    var o = document.createElement('option');
    o.value = n; o.textContent = n;
    s.appendChild(o);
  });
  updBoardPanel();
}

function updBoardPanel() {
  var b = document.getElementById('board-selector').value;
  document.getElementById('rp-board-name').textContent = b || '—';
  document.getElementById('bi-board').textContent = b || '—';
  document.getElementById('bi-board-mini').textContent = b || '—';
  var info = BOARD_INFO[b] || {};
  document.getElementById('bi-cpu').textContent = info.cpu || '—';
  document.getElementById('bi-flash').textContent = info.flash || '—';
  document.getElementById('bi-boot').textContent = info.boot || '—';
}

document.addEventListener('DOMContentLoaded', function () {
  var bs = document.getElementById('board-selector');
  if (bs) bs.addEventListener('change', function () { updBoardPanel(); updStatus(); });
});

async function scanPorts() {
  var r = await fetch('/api/ports'), d = await r.json();
  var rpSel = document.getElementById('rp-port-sel');
  rpSel.innerHTML = '<option value="">Select Port…</option>';
  if (d.ok && d.ports.length) {
    d.ports.forEach(function (pt) {
      var auto = VID_PID_MAP[pt.vidpid] || '';
      var o = document.createElement('option');
      o.value = pt.device;
      o.textContent = pt.device + (auto ? ' [' + auto + ']' : '') + (pt.description ? ' - ' + pt.description : '');
      rpSel.appendChild(o);
    });
  }
}

function onRpPortChange() {
  var v = document.getElementById('rp-port-sel').value;
  selPort = v || null;
  var portBadge = document.getElementById('port-badge');
  var portDot = document.getElementById('port-dot');
  var portLabel = document.getElementById('port-label');
  if (selPort) {
    portDot.classList.add('connected');
    portBadge.classList.add('connected');
    portLabel.textContent = selPort;
    portDot.style.background = 'var(--green)';
  } else {
    portDot.classList.remove('connected');
    portBadge.classList.remove('connected');
    portLabel.textContent = 'No Port';
    portDot.style.background = '';
  }
  // Update board status dot in right panel
  document.getElementById('rp-board-dot').classList.toggle('connected', !!selPort);
  document.getElementById('rp-board-status').textContent = selPort ? 'Connected' : 'Not Connected';
  document.getElementById('bi-port').textContent = selPort || '—';
  updStatus();
}

async function togglePortsPanel() {
  await scanPorts();
}

function updStatus() {
  var b = document.getElementById('board-selector') ? document.getElementById('board-selector').value : '';
  var status = document.getElementById('bi-board-mini');
  if (status) status.textContent = b + (selPort ? ' on ' + selPort : '');
}

// ── Bottom Panel ───────────────────────────────────────────
function switchBottomPane(name) {
  document.querySelectorAll('.btab').forEach(function (b) {
    b.classList.toggle('act', b.dataset.pane === name);
  });
  document.querySelectorAll('.bpane').forEach(function (p) { p.classList.remove('act'); p.style.display = 'none'; });
  var target = document.getElementById('pane-' + name);
  if (target) { target.classList.add('act'); target.style.display = name === 'serial' ? 'flex' : 'block'; }
}

function switchToSerial() {
  switchBottomPane('serial');
}

function toggleBottomPanel() {
  var bp = document.getElementById('bottom-panel');
  bp.style.display = bp.style.display === 'none' ? 'flex' : 'none';
  if (E) E.layout();
}

function clearOutput() {
  var active = document.querySelector('.bpane.act');
  if (active) active.innerHTML = '';
}

function logO(text, kind, paneId) {
  var p = document.getElementById(paneId || 'pane-output');
  if (!p) return;
  text.split('\n').forEach(function (line) {
    if (!line.trim()) return;
    var el = document.createElement('div');
    el.className = 'out-line ' + (kind || '');
    el.textContent = line;
    p.appendChild(el);
  });
  p.scrollTop = p.scrollHeight;
}

// ── Search ─────────────────────────────────────────────────
async function doGS() {
  var q = document.getElementById('gs-in').value.trim();
  if (q.length < 2) return;
  var c = document.getElementById('gs-res');
  c.innerHTML = '<div class="empty-state"><i class="fas fa-circle-notch spin"></i> Searching…</div>';
  var r = await fetch('/api/search?q=' + encodeURIComponent(q));
  var d = await r.json();
  if (!d.length) { c.innerHTML = '<div class="empty-state">No matches found.</div>'; return; }
  c.innerHTML = '';
  d.forEach(function (result) {
    var s = document.createElement('div');
    s.className = 'search-result';
    s.innerHTML = '<div class="sr-path">' + esc(result.path) + ':' + result.line + '</div>' +
                  '<div class="sr-text">' + esc(result.text.substring(0, 80)) + '</div>';
    s.onclick = function () { openTab(result.path); setTimeout(function () { E.revealLineInCenter(result.line); }, 100); };
    c.appendChild(s);
  });
}

// ── Serial Monitor ─────────────────────────────────────────
function initSer() {
  serEv = new EventSource('/api/serial/stream');
  serEv.onmessage = function (e) {
    try {
      var d = JSON.parse(e.data);
      if (d.type === 'status') updSerUI(d);
      else if (d.type === 'data') appendSer(d.text);
    } catch (err) {}
  };
  serEv.onerror = function () {
    serEv.close();
    setTimeout(initSer, 3000);
  };
}

function updSerUI(d) {
  serCon = d.connected;
  var btn = document.getElementById('ser-con-btn');
  var lbl = document.getElementById('ser-lbl');
  var dot = document.getElementById('ser-dot');
  if (btn) { btn.textContent = serCon ? 'Disconnect' : 'Connect'; btn.classList.toggle('connected', serCon); }
  if (lbl) lbl.textContent = serCon ? (d.port + ' @ ' + d.baud + ' baud') : 'Disconnected';
  if (dot) dot.classList.toggle('on', serCon);
  document.getElementById('rp-board-dot').classList.toggle('connected', !!selPort || serCon);
  document.getElementById('rp-board-status').textContent = (!!selPort || serCon) ? 'Connected' : 'Not Connected';
}

async function togSer() {
  if (serCon) {
    await fetch('/api/serial/disconnect', { method: 'POST' });
    return;
  }
  if (!selPort) { setSt('Select a serial port first.', 'fail'); return; }
  var r = await fetch('/api/serial/connect', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ port: selPort, baud: document.getElementById('baud-sel').value })
  });
  var d = await r.json();
  if (!d.ok) setSt('Serial error: ' + d.error, 'fail');
}

async function sendSer() {
  if (!serCon) return;
  var t = document.getElementById('ser-in').value;
  var le = document.getElementById('le-sel').value;
  t += le;
  document.getElementById('ser-in').value = '';
  await fetch('/api/serial/send', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: t })
  });
}

function appendSer(text) {
  var p = document.getElementById('serial-output');
  var el = document.createElement('span');
  el.className = 'ser-text';
  el.textContent = text;
  p.appendChild(el);
  p.scrollTop = p.scrollHeight;
}

// ── Libraries ──────────────────────────────────────────────
async function loadLibs() {
  var r = await fetch('/api/lib/list'), d = await r.json();
  var c = document.getElementById('lib-inst');
  var rpLibs = document.getElementById('rp-libs-list');
  if (!d.libraries || !d.libraries.length) {
    if (c) c.innerHTML = '<div class="empty-state">No libraries installed.</div>';
    if (rpLibs) rpLibs.innerHTML = '<div class="empty-state" style="padding:4px 0;">No libraries installed.</div>';
    return;
  }
  if (c) {
    c.innerHTML = '';
    d.libraries.forEach(function (l) {
      var el = document.createElement('div');
      el.className = 'lib-item';
      el.innerHTML = '<div><div class="lib-name">' + esc(l.name) + '</div><div class="lib-ver">' + esc(l.version) + '</div></div>' +
                     '<button class="lib-action-btn remove" onclick="uninstLib(\'' + escA(l.name) + '\')">Remove</button>';
      c.appendChild(el);
    });
  }
  if (rpLibs) {
    rpLibs.innerHTML = '';
    d.libraries.slice(0, 8).forEach(function (l) {
      var el = document.createElement('div');
      el.className = 'rp-lib-item';
      el.innerHTML = '<div><div class="rlib-name">' + esc(l.name) + '</div><div class="rlib-ver">' + esc(l.version) + '</div></div>' +
                     '<i class="fas fa-check-circle rlib-ok"></i>';
      rpLibs.appendChild(el);
    });
  }
}

async function doLibS() {
  var q = document.getElementById('lib-in').value.trim();
  if (q.length < 2) return;
  var c = document.getElementById('lib-res');
  c.innerHTML = '<div class="empty-state"><i class="fas fa-circle-notch spin"></i> Searching…</div>';
  var r = await fetch('/api/lib/search?q=' + encodeURIComponent(q));
  var d = await r.json();
  if (!d.libraries || !d.libraries.length) { c.innerHTML = '<div class="empty-state">No results found.</div>'; return; }
  c.innerHTML = '';
  d.libraries.forEach(function (l) {
    var el = document.createElement('div');
    el.className = 'lib-item';
    el.innerHTML = '<div><div class="lib-name">' + esc(l.name) + '</div><div class="lib-ver">' + esc(l.sentence || '') + ' — ' + esc(l.version) + '</div></div>' +
                   '<button class="lib-action-btn install" onclick="insLib(\'' + escA(l.name) + '\')">Install</button>';
    c.appendChild(el);
  });
}

async function insLib(n) {
  setSt('Installing ' + n + '…', 'run');
  var r = await fetch('/api/lib/install', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: n })
  });
  var d = await r.json();
  setSt(d.ok ? 'Installed ' + n : 'Install failed', d.ok ? 'ok' : 'fail');
  loadLibs();
}

async function uninstLib(n) {
  if (!confirm('Uninstall ' + n + '?')) return;
  var r = await fetch('/api/lib/uninstall', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: n })
  });
  var d = await r.json();
  setSt(d.ok ? 'Removed ' + n : 'Uninstall failed', d.ok ? 'ok' : 'fail');
  loadLibs();
}

async function updIdx() {
  setSt('Updating library index…', 'run');
  var r = await fetch('/api/lib/update_index', { method: 'POST' });
  var d = await r.json();
  setSt(d.ok ? 'Index updated' : 'Update failed', d.ok ? 'ok' : 'fail');
}

function handleZip(inp) {
  var f = inp.files[0];
  if (!f) return;
  var fd = new FormData(); fd.append('zip', f);
  setSt('Installing ZIP library…', 'run');
  fetch('/api/lib/install_zip', { method: 'POST', body: fd })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      setSt(d.ok ? 'ZIP Library Installed' : 'Failed', d.ok ? 'ok' : 'fail');
      loadLibs();
    });
  inp.value = '';
}

// ── Cores ──────────────────────────────────────────────────
async function loadCores() {
  var r = await fetch('/api/cores/list'), d = await r.json(), c = document.getElementById('cores-list');
  if (!c) return;
  try {
    var data = JSON.parse(d.output);
    if (!data || !data.length) { c.innerHTML = '<div class="empty-state">No cores installed.</div>'; return; }
    c.innerHTML = '';
    data.forEach(function (cr) {
      var el = document.createElement('div');
      el.className = 'lib-item';
      el.innerHTML = '<div><div class="lib-name">' + esc(cr.id) + '</div><div class="lib-ver">' + esc(cr.version) + '</div></div>' +
                     '<i class="fas fa-check-circle" style="color:var(--green);"></i>';
      c.appendChild(el);
    });
  } catch (e) {
    c.innerHTML = '<div class="empty-state">Default cores loaded.</div>';
  }
}

async function insCore(id) {
  if (!confirm('Install core ' + id + '?')) return;
  setSt('Installing ' + id + '…', 'run');
  var r = await fetch('/api/cores/install', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ core: id })
  });
  var d = await r.json();
  setSt(d.ok ? 'Core installed' : 'Install failed', d.ok ? 'ok' : 'fail');
  loadCores();
}

async function loadUrls() {
  var r = await fetch('/api/cores/get_urls'), d = await r.json();
  if (!d.urls || !d.urls.length) return;
  var needed = [
    'https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json',
    'https://arduino.esp8266.com/stable/package_esp8266com_index.json',
    'https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json'
  ];
  for (var i = 0; i < needed.length; i++) {
    if (d.urls.indexOf(needed[i]) === -1) {
      await fetch('/api/cores/add_url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: needed[i] }) });
    }
  }
}

// ── Status Bar ─────────────────────────────────────────────
function setSt(text, kind) {
  var s = document.getElementById('statusbar');
  document.getElementById('st-txt').textContent = text;
  s.className = kind || '';
}

// ── Utilities ──────────────────────────────────────────────
function esc(s) {
  var d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}
function escA(s) {
  return (s || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

// ── Modal dialog ───────────────────────────────────────────
function mod(title, placeholder, def) {
  return new Promise(function (resolve) {
    mRes = resolve;
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-error').textContent = '';
    var i = document.getElementById('modal-input');
    i.value = def || ''; i.placeholder = placeholder;
    document.getElementById('modal-overlay').classList.add('open');
    setTimeout(function () { i.select(); i.focus(); }, 50);
  });
}

function clMod() {
  document.getElementById('modal-overlay').classList.remove('open');
  if (mRes) { mRes(null); mRes = null; }
}

function okMod() {
  var v = document.getElementById('modal-input').value.trim();
  document.getElementById('modal-overlay').classList.remove('open');
  if (mRes) { mRes(v || null); mRes = null; }
}

document.getElementById('modal-input').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') okMod();
  if (e.key === 'Escape') clMod();
});
document.getElementById('modal-overlay').addEventListener('click', function (e) {
  if (e.target === e.currentTarget) clMod();
});

// ── Keyboard Shortcuts ─────────────────────────────────────
document.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveCurrent(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'r' && !e.shiftKey) { e.preventDefault(); doCompile(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'u') { e.preventDefault(); doUpload(); }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
    e.preventDefault(); switchPanel('search');
  }
  if (e.key === 'Escape') { document.getElementById('ctx-menu').style.display = 'none'; }
});
