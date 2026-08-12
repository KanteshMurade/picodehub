document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.tab-trigger');
  const panes = {
    tabProjects: document.getElementById('tabProjects'),
    tabCustom: document.getElementById('tabCustom'),
    tabCategories: document.getElementById('tabCategories'),
    tabComponents: document.getElementById('tabComponents'),
    tabTutorials: document.getElementById('tabTutorials'),
    tabResources: document.getElementById('tabResources'),
    tabSite: document.getElementById('tabSite'),
    tabUsers: document.getElementById('tabUsers'),
  };
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    Object.entries(panes).forEach(([k, el]) => { if (el) el.style.display = (k === t.dataset.tab) ? 'block' : 'none'; });
    if (t.dataset.tab === 'tabCustom') loadCustomRequests();
    if (t.dataset.tab === 'tabUsers') loadUsers();
    if (t.dataset.tab === 'tabCategories') loadCategories();
    if (t.dataset.tab === 'tabComponents') loadComponents();
    if (t.dataset.tab === 'tabTutorials') loadTutorials();
    if (t.dataset.tab === 'tabResources') loadResources();
    if (t.dataset.tab === 'tabSite') loadSiteSettings();
  }));

  const projectsTableBody = document.getElementById('projectsTableBody');
  const addProjectForm = document.getElementById('addProjectForm');

  function loadProjects() {
    fetch('/api/projects').then(r => r.json()).then(list => {
      const rows = list.filter(p => !p.is_custom);
      projectsTableBody.innerHTML = rows.map(p => `
        <tr>
          <td>${escapeHtml(p.title)}</td>
          <td>${escapeHtml(p.category || '')}</td>
          <td>
            <input type="number" class="admin-full-input price-input" data-id="${p.id}" value="${p.price}" style="width:100px; display:inline-block;">
          </td>
          <td style="min-width:260px;">
            <div style="display:flex; flex-direction:column; gap:0.35rem;">
              <span style="font-size:0.78rem; color:${p.has_firmware ? '#22c55e' : 'var(--text-secondary)'};">
                ${p.has_firmware ? `<i class="fas fa-circle-check"></i> Firmware uploaded (${escapeHtml(p.chip_family || 'ESP32')})` : 'No firmware uploaded yet'}
              </span>
              <div style="display:flex; gap:0.35rem; align-items:center;">
                <select class="admin-full-input chip-family-select" data-id="${p.id}" style="width:110px; padding:0.35rem;">
                  <option value="ESP32" ${p.chip_family === 'ESP32' ? 'selected' : ''}>ESP32</option>
                  <option value="ESP8266" ${p.chip_family === 'ESP8266' ? 'selected' : ''}>ESP8266</option>
                  <option value="ESP32-S2" ${p.chip_family === 'ESP32-S2' ? 'selected' : ''}>ESP32-S2</option>
                  <option value="ESP32-S3" ${p.chip_family === 'ESP32-S3' ? 'selected' : ''}>ESP32-S3</option>
                  <option value="ESP32-C3" ${p.chip_family === 'ESP32-C3' ? 'selected' : ''}>ESP32-C3</option>
                </select>
                <input type="file" class="firmware-file-input" data-id="${p.id}" accept=".bin" style="max-width:130px; font-size:0.75rem;">
                <button class="btn-secondary upload-firmware-btn" data-id="${p.id}" title="Upload firmware"><i class="fas fa-upload"></i></button>
              </div>
            </div>
          </td>
          <td style="display:flex; gap:0.4rem;">
            <button class="btn-secondary save-price-btn" data-id="${p.id}">Save</button>
            <button class="btn-secondary delete-project-btn" data-id="${p.id}" style="color:#f87171;">Delete</button>
          </td>
        </tr>
      `).join('');

      projectsTableBody.querySelectorAll('.upload-firmware-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const id = btn.dataset.id;
          const fileInput = projectsTableBody.querySelector(`.firmware-file-input[data-id="${id}"]`);
          const chipSelect = projectsTableBody.querySelector(`.chip-family-select[data-id="${id}"]`);
          const file = fileInput.files[0];
          if (!file) {
            alert('Choose a .bin file first.');
            return;
          }
          const fd = new FormData();
          fd.append('firmware', file);
          fd.append('chip_family', chipSelect.value);
          fd.append('flash_offset', '0x0');
          btn.disabled = true;
          fetch(`/api/admin/projects/${id}/firmware`, { method: 'POST', body: fd })
            .then(r => r.json())
            .then(data => {
              btn.disabled = false;
              if (!data.ok) {
                alert(data.error || 'Upload failed.');
                return;
              }
              loadProjects();
            })
            .catch(() => {
              btn.disabled = false;
              alert('Upload failed.');
            });
        });
      });

      projectsTableBody.querySelectorAll('.save-price-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const id = btn.dataset.id;
          const input = projectsTableBody.querySelector(`.price-input[data-id="${id}"]`);
          fetch(`/api/admin/projects/${id}/price`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ price: parseFloat(input.value) }),
          }).then(r => r.json()).then(() => loadProjects());
        });
      });

      projectsTableBody.querySelectorAll('.delete-project-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          if (!confirm('Delete this project permanently?')) return;
          fetch(`/api/admin/projects/${btn.dataset.id}`, { method: 'DELETE' })
            .then(r => r.json()).then(() => loadProjects());
        });
      });
    });
  }
  loadProjects();

  addProjectForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(addProjectForm);
    fetch('/api/admin/projects', { method: 'POST', body: fd })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          addProjectForm.reset();
          loadProjects();
        } else {
          alert(data.error || 'Failed to add project.');
        }
      });
  });

  function loadCustomRequests() {
    fetch('/api/admin/custom-requests').then(r => r.json()).then(data => {
      const list = document.getElementById('customRequestsList');
      const reqs = data.requests || [];
      if (!reqs.length) {
        list.innerHTML = `<div class="admin-section">No custom project requests yet.</div>`;
        return;
      }
      list.innerHTML = reqs.map(r => `
        <div class="admin-section">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
            <div>
              <strong>${escapeHtml(r.username)}</strong>
              <span style="color:var(--text-muted); font-size:0.8rem;"> — ${escapeHtml(r.email)}</span>
            </div>
            <span class="admin-badge ${r.status}">${r.status}</span>
          </div>
          <p style="color:var(--text-secondary); font-size:0.88rem; white-space:pre-wrap; margin-bottom:1rem;">${escapeHtml(r.requirements)}</p>
          ${r.admin_message ? `<p style="font-size:0.85rem; color:var(--accent-green); margin-bottom:0.75rem;"><i class="fas fa-check"></i> Sent: ${escapeHtml(r.admin_message)}${r.admin_file_name ? ' — file: ' + escapeHtml(r.admin_file_name) : ''}</p>` : ''}
          <form class="respond-form" data-id="${r.id}">
            <textarea class="admin-full-input" name="message" placeholder="Message to send to the user" rows="2" style="margin-bottom:0.6rem;"></textarea>
            <div style="display:flex; gap:0.6rem; align-items:center; flex-wrap:wrap;">
              <input type="file" name="file">
              <button type="submit" class="btn-primary" style="margin-left:auto;"><i class="fas fa-paper-plane"></i> Send Response</button>
            </div>
          </form>
        </div>
      `).join('');

      list.querySelectorAll('.respond-form').forEach(form => {
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          const fd = new FormData(form);
          fetch(`/api/admin/custom-requests/${form.dataset.id}/respond`, { method: 'POST', body: fd })
            .then(r => r.json()).then(() => loadCustomRequests());
        });
      });
    });
  }

  function loadUsers() {
    fetch('/api/admin/users').then(r => r.json()).then(data => {
      const body = document.getElementById('usersTableBody');
      body.innerHTML = (data.users || []).map(u => `
        <tr>
          <td>${escapeHtml(u.username)}</td>
          <td>${escapeHtml(u.email)}</td>
          <td>${u.is_admin ? '<span class="admin-badge responded">Admin</span>' : 'User'}</td>
          <td style="color:var(--text-muted); font-size:0.8rem;">${escapeHtml(u.created_at)}</td>
        </tr>
      `).join('');
    });
  }

  // ---------------------------------------------------------------------
  // Categories
  // ---------------------------------------------------------------------

  function loadCategories() {
    fetch('/api/categories').then(r => r.json()).then(data => {
      const body = document.getElementById('categoriesTableBody');
      body.innerHTML = (data.categories || []).map(c => `
        <tr>
          <td><i class="fas ${escapeHtml(c.icon || 'fa-layer-group')}"></i></td>
          <td>${escapeHtml(c.name)}</td>
          <td style="color:var(--text-muted); font-size:0.8rem;">${escapeHtml(c.description || '')}</td>
          <td><button class="btn-secondary delete-btn" data-kind="categories" data-id="${c.id}" style="color:#f87171;">Delete</button></td>
        </tr>
      `).join('');
      wireDeleteButtons();
    });
  }

  document.getElementById('addCategoryForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    fetch('/api/admin/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(fd)),
    }).then(r => r.json()).then(data => {
      if (data.ok) { e.target.reset(); loadCategories(); } else { alert(data.error || 'Failed to add category.'); }
    });
  });

  // ---------------------------------------------------------------------
  // Components
  // ---------------------------------------------------------------------

  function loadComponents() {
    fetch('/api/components').then(r => r.json()).then(data => {
      const body = document.getElementById('componentsTableBody');
      body.innerHTML = (data.components || []).map(c => `
        <tr>
          <td><i class="fas ${escapeHtml(c.icon || 'fa-microchip')}"></i> ${escapeHtml(c.name)}</td>
          <td>${escapeHtml(c.type || '')}</td>
          <td style="color:var(--text-muted); font-size:0.8rem;">${escapeHtml(c.specs || '')}</td>
          <td><button class="btn-secondary delete-btn" data-kind="components" data-id="${c.id}" style="color:#f87171;">Delete</button></td>
        </tr>
      `).join('');
      wireDeleteButtons();
    });
  }

  document.getElementById('addComponentForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    fetch('/api/admin/components', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(fd)),
    }).then(r => r.json()).then(data => {
      if (data.ok) { e.target.reset(); loadComponents(); } else { alert(data.error || 'Failed to add component.'); }
    });
  });

  // ---------------------------------------------------------------------
  // Tutorials
  // ---------------------------------------------------------------------

  function loadTutorials() {
    fetch('/api/tutorials').then(r => r.json()).then(data => {
      const body = document.getElementById('tutorialsTableBody');
      body.innerHTML = (data.tutorials || []).map(t => `
        <tr>
          <td>${escapeHtml(t.title)}</td>
          <td>${escapeHtml(t.level || '')}</td>
          <td><button class="btn-secondary delete-btn" data-kind="tutorials" data-id="${t.id}" style="color:#f87171;">Delete</button></td>
        </tr>
      `).join('');
      wireDeleteButtons();
    });
  }

  document.getElementById('addTutorialForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd);
    fetch('/api/admin/tutorials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => r.json()).then(data => {
      if (data.ok) { e.target.reset(); loadTutorials(); } else { alert(data.error || 'Failed to add tutorial.'); }
    });
  });

  // ---------------------------------------------------------------------
  // Resources
  // ---------------------------------------------------------------------

  function loadResources() {
    fetch('/api/resources').then(r => r.json()).then(data => {
      const body = document.getElementById('resourcesTableBody');
      body.innerHTML = (data.resources || []).map(r => `
        <tr>
          <td>${escapeHtml(r.name)}</td>
          <td>${escapeHtml(r.type || '')}</td>
          <td>${r.download_url ? `<a href="${r.download_url}" target="_blank" style="color:var(--accent-indigo);">Link</a>` : '<span style="color:var(--text-muted);">None</span>'}</td>
          <td><button class="btn-secondary delete-btn" data-kind="resources" data-id="${r.id}" style="color:#f87171;">Delete</button></td>
        </tr>
      `).join('');
      wireDeleteButtons();
    });
  }

  document.getElementById('addResourceForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    fetch('/api/admin/resources', { method: 'POST', body: fd })
      .then(r => r.json()).then(data => {
        if (data.ok) { e.target.reset(); loadResources(); } else { alert(data.error || 'Failed to add resource.'); }
      });
  });

  // ---------------------------------------------------------------------
  // Site settings
  // ---------------------------------------------------------------------

  function loadSiteSettings() {
    fetch('/api/site-settings').then(r => r.json()).then(data => {
      if (!data.ok) return;
      const form = document.getElementById('siteSettingsForm');
      Object.entries(data.settings).forEach(([key, value]) => {
        const field = form.elements[key];
        if (field) field.value = value;
      });
    });
  }

  document.getElementById('siteSettingsForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    fetch('/api/admin/site-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(fd)),
    }).then(r => r.json()).then(data => {
      if (data.ok) alert('Site settings saved.'); else alert(data.error || 'Failed to save.');
    });
  });

  // ---------------------------------------------------------------------
  // Shared delete-button wiring (categories/components/tutorials/resources)
  // ---------------------------------------------------------------------

  function wireDeleteButtons() {
    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.onclick = () => {
        if (!confirm('Delete this item?')) return;
        fetch(`/api/admin/${btn.dataset.kind}/${btn.dataset.id}`, { method: 'DELETE' })
          .then(r => r.json())
          .then(() => {
            const reload = { categories: loadCategories, components: loadComponents, tutorials: loadTutorials, resources: loadResources }[btn.dataset.kind];
            if (reload) reload();
          });
      };
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  // Guard: bounce non-admins back home if session expired.
  fetch('/api/me').then(r => r.json()).then(data => {
    if (!data.user || !data.user.is_admin) window.location.href = '/';
  });
});
