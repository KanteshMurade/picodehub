document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const projectId = params.get('project');

  const boardSelect = document.getElementById('boardSelect');
  const portSelect = document.getElementById('portSelect');
  const refreshPortsBtn = document.getElementById('refreshPortsBtn');
  const uploadBtn = document.getElementById('uploadBtn');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const consoleEl = document.getElementById('flashConsole');
  const titleEl = document.getElementById('flashTitle');

  function log(line) {
    consoleEl.textContent += line + '\n';
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  function setProgress(pct, text) {
    progressFill.style.width = Math.max(0, Math.min(100, pct)) + '%';
    progressText.textContent = text;
  }

  if (!projectId) {
    window.location.href = '/';
    return;
  }

  if (!('serial' in navigator)) {
    portSelect.innerHTML = `<option value="">Not supported in this browser</option>`;
    log('Your browser does not support the Web Serial API. Please use Chrome or Edge on desktop.');
  }

  let purchasedProject = null;
  let selectedSerialPort = null; // the actual navigator.serial SerialPort object

  function pickMatchingBoard(chipTag, chips, boardNames) {
    const candidates = [chipTag, ...(chips || [])].filter(Boolean).map(c => c.toLowerCase());
    for (const candidate of candidates) {
      let found = boardNames.find(b => b.toLowerCase() === candidate);
      if (found) return found;
    }
    for (const candidate of candidates) {
      let found = boardNames.find(b => b.toLowerCase().includes(candidate) || candidate.includes(b.toLowerCase().split(' ')[0]));
      if (found) return found;
    }
    return boardNames[0];
  }

  Promise.all([
    fetch('/api/projects').then(r => r.json()),
    fetch('/api/boards').then(r => r.json()),
  ]).then(([list, boardsData]) => {
    purchasedProject = list.find(p => p.id === projectId);
    const boardNames = boardsData.boards || [];

    if (purchasedProject) {
      titleEl.innerHTML = `<i class="fas fa-bolt" style="color:#fbbf24;"></i> ${purchasedProject.title}`;
    }

    boardSelect.innerHTML = boardNames.map(b => `<option value="${b}">${b}</option>`).join('');

    if (purchasedProject && !purchasedProject.is_custom) {
      const matched = pickMatchingBoard(purchasedProject.chipTag, purchasedProject.chips, boardNames);
      boardSelect.value = matched;
      boardSelect.disabled = true;
      const lockNote = document.createElement('p');
      lockNote.className = 'flash-muted';
      lockNote.style.marginTop = '0.35rem';
      lockNote.innerHTML = `<i class="fas fa-lock"></i> Board locked to what you purchased this project for.`;
      boardSelect.insertAdjacentElement('afterend', lockNote);
    }

    if (purchasedProject && !purchasedProject.owned) {
      log('You need to purchase this project before flashing it.');
      uploadBtn.disabled = true;
      compileBtn.disabled = true;
    }
  });

  // ---------------------------------------------------------------------
  // Serial Port: real browser permission popup (Web Serial API)
  // ---------------------------------------------------------------------
  async function requestSerialPort() {
    if (!('serial' in navigator)) {
      log('Web Serial not supported in this browser.');
      return;
    }
    portSelect.innerHTML = `<option>Waiting for browser permission…</option>`;
    try {
      // This triggers the native browser popup: "this site wants to
      // connect to a serial port" — same as the ESPWebTool prompt.
      selectedSerialPort = await navigator.serial.requestPort();
      const info = selectedSerialPort.getInfo ? selectedSerialPort.getInfo() : {};
      const label = info.usbVendorId
        ? `USB Device (VID ${info.usbVendorId.toString(16)} / PID ${info.usbProductId.toString(16)})`
        : 'Selected Serial Port';
      portSelect.innerHTML = `<option value="selected">${label} — Paired</option>`;
      log('> Serial port granted: ' + label);
    } catch (err) {
      // User clicked Cancel, or no device was available.
      portSelect.innerHTML = `<option value="">No port selected</option>`;
      log('> Port selection cancelled: ' + (err.message || err));
      selectedSerialPort = null;
    }
  }

  refreshPortsBtn.addEventListener('click', requestSerialPort);
  portSelect.addEventListener('mousedown', (e) => {
    // Also trigger the picker if they click straight into the (empty)
    // dropdown instead of the refresh icon.
    if (!selectedSerialPort) {
      e.preventDefault();
      requestSerialPort();
    }
  });
  portSelect.innerHTML = `<option value="">Click to select a port</option>`;

  // ---------------------------------------------------------------------
  // No live "Compile" step here: the admin pre-compiles firmware for
  // each catalog project (see /api/admin/projects/<id>/firmware) and this
  // page flashes that pre-built firmware.bin straight over WebSerial.
  // Running a real arduino-cli compile on the free-tier server was
  // unreliable (times out or OOM-crashes the process on a heavy ESP32
  // build), so it's intentionally not offered here.
  // ---------------------------------------------------------------------

  // ---------------------------------------------------------------------
  // Flash to Board — entirely in the browser via Web Serial + esptool-js.
  // Uses the port granted above and the pre-compiled firmware.bin the
  // admin uploaded for this project.
  // ---------------------------------------------------------------------
  function bufferToBinaryString(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return binary;
  }

  uploadBtn.addEventListener('click', async () => {
    if (!('serial' in navigator)) {
      log('Web Serial not supported in this browser. Use Chrome or Edge on desktop.');
      return;
    }
    if (!selectedSerialPort) {
      log('Click the Serial Port button first and pick your board.');
      await requestSerialPort();
      if (!selectedSerialPort) return;
    }

    uploadBtn.disabled = true;
    setProgress(5, 'Preparing firmware…');
    log('> Fetching firmware for this project…');

    let firmwareBuffer;
    try {
      const fwResp = await fetch(`/api/projects/${encodeURIComponent(projectId)}/firmware.bin`);
      if (!fwResp.ok) {
        const err = await fwResp.json().catch(() => ({}));
        throw new Error(err.error || 'No firmware uploaded for this project yet.');
      }
      firmwareBuffer = await fwResp.arrayBuffer();
    } catch (err) {
      log('Error: ' + err.message);
      setProgress(0, 'Error');
      uploadBtn.disabled = false;
      return;
    }

    try {
      setProgress(15, 'Connecting to board…');
      log('> Loading flashing library…');

      let ESPLoader, Transport;
      try {
        const mod = await import('https://esm.sh/esptool-js@0.4.6');
        ESPLoader = mod.ESPLoader;
        Transport = mod.Transport;
      } catch (importErr) {
        console.error(importErr);
        throw new Error('Could not load the flashing library from esm.sh. Check your internet connection, or that esm.sh isn\'t blocked on this network, then try again.');
      }

      log('> Connecting to ESP chip…');
      const transport = new Transport(selectedSerialPort);
      const loader = new ESPLoader({
        transport,
        baudrate: 115200,
        terminal: {
          clean() {},
          writeLine: (msg) => log(msg),
          write: (msg) => log(msg),
        },
      });

      const chip = await loader.main();
      log('> Chip detected: ' + chip);
      setProgress(35, 'Erasing & writing flash…');

      await loader.writeFlash({
        fileArray: [
          { data: bufferToBinaryString(firmwareBuffer), address: 0x0 },
        ],
        flashSize: 'keep',
        eraseAll: false,
        compress: true,
        reportProgress: (fileIndex, written, total) => {
          const pct = 35 + Math.round((written / total) * 60);
          setProgress(pct, `Flashing… ${Math.round((written / total) * 100)}%`);
        },
      });

      log('> Flash complete. Resetting board…');
      if (transport.disconnect) await transport.disconnect();
      setProgress(100, 'Flash complete');
      log('> Done! Your board is now running this project.');
    } catch (err) {
      console.error(err);
      log('Error: ' + (err.message || err));
      setProgress(0, 'Flash failed');
    } finally {
      uploadBtn.disabled = false;
    }
  });
});
