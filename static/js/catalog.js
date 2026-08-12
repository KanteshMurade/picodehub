document.addEventListener('DOMContentLoaded', () => {
  let allProjects = [];
  let currentFilter = 'all';
  let searchQuery = '';
  let boltClickCount = 0;
  let boltClickTimer = null;
  let activeSerialInterval = null;
  let currentUser = null;
  let activeModalProject = null;

  // View Sections
  const views = {
    catalog: document.getElementById('viewCatalog'),
    categories: document.getElementById('viewCategories'),
    components: document.getElementById('viewComponents'),
    tutorials: document.getElementById('viewTutorials'),
    resources: document.getElementById('viewResources')
  };

  // Elements
  const projectsGrid = document.getElementById('projectsGrid');
  const searchInput = document.getElementById('searchInput');
  const filterPills = document.querySelectorAll('.filter-pill');
  const gridViewBtn = document.getElementById('gridViewBtn');
  const listViewBtn = document.getElementById('listViewBtn');
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const topPageHeading = document.getElementById('topPageHeading');
  const loadMoreBtn = document.getElementById('loadMoreBtn');

  // Modal Elements
  const projectModal = document.getElementById('projectModal');
  const modalCloseBtn = document.getElementById('modalCloseBtn');
  const modalTitle = document.getElementById('modalTitle');
  const modalCategory = document.getElementById('modalCategory');
  const modalDifficulty = document.getElementById('modalDifficulty');
  const modalDesc = document.getElementById('modalDesc');
  const wiringTableBody = document.getElementById('wiringTableBody');
  const componentsTableBody = document.getElementById('componentsTableBody');
  const terminalConsole = document.getElementById('terminalConsole');
  const openIdeBtn = document.getElementById('openIdeBtn');
  const pdfLinkBtn = document.getElementById('pdfLinkBtn');
  const startPlaybackBtn = document.getElementById('startPlaybackBtn');

  const aboutModal = document.getElementById('aboutModal');
  const aboutModalClose = document.getElementById('aboutModalClose');

  const contactModal = document.getElementById('contactModal');
  const contactModalClose = document.getElementById('contactModalClose');
  const contactForm = document.getElementById('contactForm');

  const secretBoltBadge = document.getElementById('secretBoltBadge');
  const importModal = document.getElementById('importModal');
  const importModalClose = document.getElementById('importModalClose');
  const zipFileInput = document.getElementById('zipFileInput');
  const uploadZipBtn = document.getElementById('uploadZipBtn');

  // Auth & commerce elements
  const loginNavBtn = document.getElementById('loginNavBtn');
  const registerNavBtn = document.getElementById('registerNavBtn');
  const authNav = document.getElementById('authNav');
  const userMenu = document.getElementById('userMenu');
  const userMenuTrigger = document.getElementById('userMenuTrigger');
  const userDropdown = document.getElementById('userDropdown');
  const userMenuName = document.getElementById('userMenuName');
  const userAvatarInitial = document.getElementById('userAvatarInitial');
  const adminPanelLink = document.getElementById('adminPanelLink');
  const logoutBtn = document.getElementById('logoutBtn');
  const myPurchasesBtn = document.getElementById('myPurchasesBtn');
  const promoCustomBtn = document.getElementById('promoCustomBtn');

  const loginModal = document.getElementById('loginModal');
  const loginModalClose = document.getElementById('loginModalClose');
  const loginForm = document.getElementById('loginForm');
  const loginError = document.getElementById('loginError');
  const switchToRegister = document.getElementById('switchToRegister');

  const registerModal = document.getElementById('registerModal');
  const registerModalClose = document.getElementById('registerModalClose');
  const registerForm = document.getElementById('registerForm');
  const registerError = document.getElementById('registerError');
  const switchToLogin = document.getElementById('switchToLogin');

  const customReqModal = document.getElementById('customReqModal');
  const customReqModalClose = document.getElementById('customReqModalClose');
  const customReqText = document.getElementById('customReqText');
  const submitCustomReqBtn = document.getElementById('submitCustomReqBtn');

  const purchasesModal = document.getElementById('purchasesModal');
  const purchasesModalClose = document.getElementById('purchasesModalClose');
  const purchasesModalBody = document.getElementById('purchasesModalBody');

  const forgotPasswordLink = document.getElementById('forgotPasswordLink');
  const forgotModal = document.getElementById('forgotModal');
  const forgotModalClose = document.getElementById('forgotModalClose');
  const forgotForm = document.getElementById('forgotForm');
  const forgotError = document.getElementById('forgotError');
  const switchToLoginFromForgot = document.getElementById('switchToLoginFromForgot');

  const changePasswordBtn = document.getElementById('changePasswordBtn');
  const changePasswordModal = document.getElementById('changePasswordModal');
  const changePasswordModalClose = document.getElementById('changePasswordModalClose');
  const changePasswordForm = document.getElementById('changePasswordForm');
  const changePasswordError = document.getElementById('changePasswordError');

  // Load Saved Theme
  const savedTheme = localStorage.getItem('sl-thm');
  if (savedTheme === 'light') {
    document.body.classList.add('light-theme');
    if (themeIcon) themeIcon.className = 'fas fa-moon';
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const isLight = document.body.classList.toggle('light-theme');
      localStorage.setItem('sl-thm', isLight ? 'light' : 'dark');
      if (themeIcon) themeIcon.className = isLight ? 'fas fa-moon' : 'fas fa-sun';
      showToast(`Switched to ${isLight ? 'Light' : 'Dark'} Mode`, 'info');
    });
  }

  fetchMe().then(fetchProjects);
  fetchSiteSettings();

  function fetchSiteSettings() {
    fetch('/api/site-settings').then(r => r.json()).then(data => {
      if (!data.ok) return;
      const s = data.settings;
      const titleEl = document.getElementById('siteTitleText');
      const taglineEl = document.getElementById('siteTaglineText');
      const aboutEl = document.getElementById('siteAboutText');
      if (titleEl) titleEl.textContent = s.site_title;
      if (taglineEl) taglineEl.textContent = s.site_tagline;
      if (aboutEl) aboutEl.innerHTML = `<strong style="color: var(--text-primary);">${escapeHtml(s.site_title)}</strong> ${escapeHtml(s.about_text || '')}`;
      document.title = `${s.site_title} - Embedded & IoT Workshop Platform`;
    }).catch(() => {});
  }

  function fetchMe() {
    return fetch('/api/me').then(r => r.json()).then(data => {
      currentUser = data.user || null;
      renderAuthNav();
    }).catch(() => {});
  }

  function fetchProjects() {
    fetch('/api/projects')
      .then(res => res.json())
      .then(data => {
        allProjects = data;
        renderProjects();
        renderCategoriesView();
        renderComponentsView();
        renderTutorialsView();
        renderResourcesView();
      })
      .catch(err => {
        console.error('Error fetching projects:', err);
        showToast('Failed to load projects', 'error');
      });
  }

  const menuItems = document.querySelectorAll('.sidebar-menu .menu-item');
  menuItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = item.dataset.view;
      if (!targetView) return;

      if (targetView === 'about') {
        if (aboutModal) aboutModal.classList.add('active');
        return;
      }
      if (targetView === 'contact') {
        if (contactModal) contactModal.classList.add('active');
        return;
      }
      menuItems.forEach(m => m.classList.remove('active'));
      item.classList.add('active');

      Object.keys(views).forEach(k => {
        if (views[k]) views[k].style.display = (k === targetView) ? 'block' : 'none';
      });

      // Update Header Text
      if (topPageHeading) {
        if (targetView === 'catalog') {
          topPageHeading.innerHTML = `<h1><span class="highlight">All</span> Projects</h1><p>A collection of electronics and IoT projects by Technosankalp Solutions.</p>`;
        } else if (targetView === 'categories') {
          topPageHeading.innerHTML = `<h1>Project <span class="highlight">Categories</span></h1><p>Explore projects grouped by engineering discipline and technology.</p>`;
        } else if (targetView === 'components') {
          topPageHeading.innerHTML = `<h1>Component <span class="highlight">Library</span></h1><p>Datasheets, specs, and pinout details for hardware modules.</p>`;
        } else if (targetView === 'tutorials') {
          topPageHeading.innerHTML = `<h1>Workshop <span class="highlight">Tutorials</span></h1><p>Step-by-step guides for flashing, wiring, and microcontrollers.</p>`;
        } else if (targetView === 'resources') {
          topPageHeading.innerHTML = `<h1>Resources & <span class="highlight">Downloads</span></h1><p>Driver downloads, pinout cheat sheets, and documentation.</p>`;
        }
      }
    });
  });

  // Keyboard shortcut Ctrl+K / Cmd+K
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (searchInput) searchInput.focus();
    }
  });

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase();
      renderProjects();
      renderCategoriesView();
      renderComponentsView();
    });
  }

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.dataset.filter;
      renderProjects();
    });
  });

  if (gridViewBtn && listViewBtn) {
    gridViewBtn.addEventListener('click', () => {
      gridViewBtn.classList.add('active');
      listViewBtn.classList.remove('active');
      projectsGrid.classList.remove('list-view');
    });

    listViewBtn.addEventListener('click', () => {
      listViewBtn.classList.add('active');
      gridViewBtn.classList.remove('active');
      projectsGrid.classList.add('list-view');
    });
  }

  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => {
      showToast('All available workshop projects loaded!', 'info');
    });
  }

  function renderProjects() {
    if (!projectsGrid) return;

    const filtered = allProjects.filter(p => {
      const pChipCat = (p.chipCategory || p.chipTag || '').toLowerCase();
      const pCat = (p.category || '').toLowerCase();
      const targetFilter = currentFilter.toLowerCase();

      let matchFilter = targetFilter === 'all' || 
                        pChipCat.includes(targetFilter) || 
                        pCat.includes(targetFilter) ||
                        (p.chips && p.chips.some(c => c.toLowerCase().includes(targetFilter)));

      const matchSearch = p.title.toLowerCase().includes(searchQuery) ||
                          p.description.toLowerCase().includes(searchQuery) ||
                          (p.chips && p.chips.some(c => c.toLowerCase().includes(searchQuery)));
      
      return matchFilter && matchSearch;
    });

    if (filtered.length === 0) {
      projectsGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 4rem; color: var(--text-muted);">
          <i class="fas fa-layer-group" style="font-size: 3rem; margin-bottom: 1rem;"></i>
          <h3>No projects match your search criteria</h3>
          <p>Try searching for another micro-controller or sensor name.</p>
        </div>
      `;
      return;
    }

    projectsGrid.innerHTML = filtered.map(p => {
      const chipBadgeText = p.chipTag || (p.chips ? p.chips[0] : 'Arduino');
      let chipClass = 'chip-arduino';
      if (chipBadgeText.includes('ESP32')) chipClass = 'chip-esp32';
      if (chipBadgeText.includes('Raspberry')) chipClass = 'chip-raspberry';
      if (chipBadgeText.includes('Pico')) chipClass = 'chip-pico';
      if (chipBadgeText.includes('8266')) chipClass = 'chip-esp8266';

      const coverImg = p.cover || '/static/images/smart_door.jpg';
      const priceLabel = p.is_custom ? `From ₹${p.price}` : `₹${p.price}`;

      return `
        <div class="project-card ${p.is_custom ? 'custom-project-card' : ''}" data-id="${p.id}">
          <div class="card-media">
            <img src="${coverImg}" alt="${p.title}" onerror="this.src='/static/images/smart_door.jpg';">
            <span class="chip-badge-top ${chipClass}">${chipBadgeText}</span>
            <button class="bookmark-btn" onclick="event.stopPropagation(); this.querySelector('i').classList.toggle('fas');"><i class="far fa-bookmark"></i></button>
          </div>
          <div class="card-content">
            <h3 class="card-title">${p.title}</h3>
            <span class="sub-chip-pill">${chipBadgeText} • ${p.category || 'General'}</span>
            <div class="card-stats">
              <div class="stat-item rating"><i class="fas fa-star"></i> <span>${p.rating || '4.8'}</span></div>
              <div class="stat-item"><i class="far fa-eye"></i> <span>${p.views || '5.2K'}</span></div>
            </div>
            <div class="card-price-row">
              <span class="card-price">${priceLabel}</span>
              ${p.owned ? '<span class="owned-pill">OWNED</span>' : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');

    document.querySelectorAll('.project-card').forEach(card => {
      card.addEventListener('click', () => {
        const pId = card.dataset.id;
        const project = allProjects.find(p => p.id === pId);
        if (project) openProjectModal(project);
      });
    });
  }

  function renderCategoriesView() {
    const grid = document.getElementById('categoriesGrid');
    if (!grid) return;
    grid.innerHTML = `<p class="flash-muted">Loading…</p>`;

    fetch('/api/categories').then(r => r.json()).then(data => {
      const categories = data.categories || [];
      grid.innerHTML = categories.map(cat => {
        const count = allProjects.filter(p => (p.category || '').toLowerCase() === cat.name.toLowerCase() || (p.chipCategory || '').toLowerCase() === cat.name.toLowerCase()).length;
        return `
          <div class="project-card" style="padding: 1.5rem; display: flex; flex-direction: column; justify-content: space-between;" onclick="selectCategoryFilter('${escapeHtml(cat.name)}')">
            <div>
              <div style="width: 48px; height: 48px; border-radius: 12px; background: var(--gradient-nav); display: flex; align-items: center; justify-content: center; font-size: 1.4rem; color: white; margin-bottom: 1rem;">
                <i class="fas ${cat.icon || 'fa-layer-group'}"></i>
              </div>
              <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.4rem;">${escapeHtml(cat.name)}</h3>
              <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(cat.description || '')}</p>
            </div>
            <div style="margin-top: 1.5rem; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
              <span class="sub-chip-pill" style="margin-bottom: 0;">${count} Projects</span>
              <span style="font-size: 0.85rem; color: var(--accent-indigo); font-weight: 600;">Explore &rarr;</span>
            </div>
          </div>
        `;
      }).join('') || `<p class="flash-muted">No categories yet.</p>`;
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  window.selectCategoryFilter = (catName) => {
    const catalogItem = document.querySelector('.sidebar-menu .menu-item[data-view="catalog"]');
    if (catalogItem) catalogItem.click();
    const pill = Array.from(filterPills).find(p => p.dataset.filter.toLowerCase() === catName.toLowerCase());
    if (pill) {
      pill.click();
    } else {
      currentFilter = catName;
      renderProjects();
    }
  };

  function renderComponentsView() {
    const grid = document.getElementById('componentsGrid');
    if (!grid) return;
    grid.innerHTML = `<p class="flash-muted">Loading…</p>`;

    fetch('/api/components').then(r => r.json()).then(data => {
      const components = data.components || [];
      grid.innerHTML = components.map(c => `
        <div class="project-card" style="padding: 1.25rem;">
          <div style="display: flex; align-items: center; gap: 0.85rem; margin-bottom: 0.75rem;">
            <div style="width: 40px; height: 40px; border-radius: 10px; background: rgba(99, 102, 241, 0.15); color: var(--accent-indigo); display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
              <i class="fas ${c.icon || 'fa-microchip'}"></i>
            </div>
            <div>
              <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(c.name)}</h4>
              <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(c.type || '')}</span>
            </div>
          </div>
          <p style="font-size: 0.83rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1rem;">${escapeHtml(c.specs || '')}</p>
          <div style="border-top: 1px solid var(--border-color); padding-top: 0.6rem;">
            <span style="font-size: 0.75rem; color: var(--accent-indigo); font-family: var(--font-mono);">Datasheet Verified</span>
          </div>
        </div>
      `).join('') || `<p class="flash-muted">No components yet.</p>`;
    });
  }

  function renderTutorialsView() {
    const container = document.getElementById('tutorialsContainer');
    if (!container) return;
    container.innerHTML = `<p class="flash-muted">Loading…</p>`;

    fetch('/api/tutorials').then(r => r.json()).then(data => {
      const tutorials = data.tutorials || [];
      container.innerHTML = tutorials.map(t => `
        <div class="project-card" style="padding: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
            <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(t.title)}</h3>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <span class="sub-chip-pill" style="margin-bottom: 0;">${escapeHtml(t.level || '')}</span>
              <span style="font-size: 0.8rem; color: var(--text-muted);"><i class="far fa-clock"></i> ${escapeHtml(t.time || '')}</span>
            </div>
          </div>
          <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.6;">${escapeHtml(t.summary || '')}</p>
          <div style="background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 10px; padding: 1rem;">
            <h4 style="font-size: 0.85rem; color: var(--accent-indigo); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">Step-by-Step Instructions:</h4>
            <ol style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.7;">
              ${(t.steps || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}
            </ol>
          </div>
        </div>
      `).join('') || `<p class="flash-muted">No tutorials yet.</p>`;
    });
  }

  function renderResourcesView() {
    const grid = document.getElementById('resourcesGrid');
    if (!grid) return;
    grid.innerHTML = `<p class="flash-muted">Loading…</p>`;

    fetch('/api/resources').then(r => r.json()).then(data => {
      const resources = data.resources || [];
      grid.innerHTML = resources.map(r => `
        <div class="project-card" style="padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
              <i class="fas fa-file-pdf" style="font-size: 1.8rem; color: #ef4444;"></i>
              <span class="sub-chip-pill" style="margin-bottom:0;">${escapeHtml(r.type || '')}</span>
            </div>
            <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.4rem;">${escapeHtml(r.name)}</h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(r.description || '')}</p>
          </div>
          <div style="margin-top: 1.25rem; border-top: 1px solid var(--border-color); padding-top: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(r.size || '')}</span>
            ${r.download_url
              ? `<a class="btn-secondary" style="padding: 0.3rem 0.8rem; font-size: 0.8rem; text-decoration:none;" href="${r.download_url}" target="_blank"><i class="fas fa-download"></i> Download</a>`
              : `<span class="flash-muted" style="font-size:0.75rem;">No file yet</span>`}
          </div>
        </div>
      `).join('') || `<p class="flash-muted">No resources yet.</p>`;
    });
  }

  function openProjectModal(project) {
    activeModalProject = project;
    modalTitle.textContent = project.title;
    modalCategory.textContent = project.category || 'Electronics';
    modalDifficulty.textContent = project.difficulty || 'Intermediate';
    modalDesc.textContent = project.description;

    if (project.wiring && project.wiring.length > 0) {
      wiringTableBody.innerHTML = project.wiring.map(w => `
        <tr>
          <td><span class="pin-chip">${w.from}</span></td>
          <td><span class="pin-chip">${w.to}</span></td>
          <td>
            <div class="wire-color-badge">
              <span class="color-dot" style="background-color: ${w.color};"></span>
              <span>${w.color}</span>
            </div>
          </td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${w.notes || ''}</td>
        </tr>
      `).join('');
    } else {
      wiringTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No wiring pins defined.</td></tr>`;
    }

    if (project.components && project.components.length > 0) {
      componentsTableBody.innerHTML = project.components.map(c => `
        <tr>
          <td style="font-weight: 600;">${c.name}</td>
          <td><span class="sub-chip-pill">${c.quantity}</span></td>
          <td style="color: var(--text-muted); font-size: 0.85rem;">${c.specs || ''}</td>
        </tr>
      `).join('');
    } else {
      componentsTableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No component list recorded.</td></tr>`;
    }

    terminalConsole.innerHTML = '';
    if (activeSerialInterval) clearInterval(activeSerialInterval);
    
    if (project.serialPlayback && project.serialPlayback.length > 0) {
      project.serialPlayback.forEach(line => {
        const div = document.createElement('div');
        div.style.marginBottom = '0.2rem';
        div.textContent = line;
        terminalConsole.appendChild(div);
      });
    } else {
      terminalConsole.innerHTML = `<div style="color: var(--text-muted);">[SYSTEM] Ready to monitor board output.</div>`;
    }

    if (startPlaybackBtn) {
      startPlaybackBtn.onclick = () => {
        terminalConsole.innerHTML = '';
        let idx = 0;
        if (activeSerialInterval) clearInterval(activeSerialInterval);
        const logs = project.serialPlayback || ["[SYSTEM] Serial output test stream."];
        activeSerialInterval = setInterval(() => {
          if (idx < logs.length) {
            const div = document.createElement('div');
            div.style.marginBottom = '0.2rem';
            div.textContent = logs[idx++];
            terminalConsole.appendChild(div);
            terminalConsole.scrollTop = terminalConsole.scrollHeight;
          } else {
            clearInterval(activeSerialInterval);
          }
        }, 600);
      };
    }

    if (project.pdf) {
      pdfLinkBtn.style.display = 'inline-flex';
      pdfLinkBtn.href = project.pdf;
    } else {
      pdfLinkBtn.style.display = 'none';
    }

    renderModalAction(project);
    projectModal.classList.add('active');
  }

  const modalPriceEl = document.getElementById('modalPrice');
  const actionBtn = document.getElementById('actionBtn');

  function renderModalAction(project) {
    if (modalPriceEl) {
      modalPriceEl.textContent = project.is_custom ? `From ₹${project.price}` : `₹${project.price}`;
    }
    if (!actionBtn) return;

    actionBtn.onclick = null;

    if (project.owned) {
      if (project.is_custom) {
        actionBtn.innerHTML = `<i class="fas fa-comment-dots"></i> Submit Requirements`;
        actionBtn.onclick = () => {
          projectModal.classList.remove('active');
          if (customReqModal) customReqModal.classList.add('active');
        };
      } else {
        actionBtn.innerHTML = `<i class="fas fa-bolt"></i> Flash This Project &rarr;`;
        actionBtn.onclick = () => {
          window.location.href = `/flash?project=${encodeURIComponent(project.id)}`;
        };
      }
    } else {
      actionBtn.innerHTML = `<i class="fas fa-cart-shopping"></i> Buy Now — ₹${project.price}`;
      actionBtn.onclick = () => buyProject(project);
    }
  }

  function buyProject(project) {
    if (!currentUser) {
      projectModal.classList.remove('active');
      if (loginModal) loginModal.classList.add('active');
      showToast('Please log in to buy this project.', 'info');
      return;
    }
    actionBtn.disabled = true;
    fetch(`/api/projects/${encodeURIComponent(project.id)}/buy`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        actionBtn.disabled = false;
        if (!data.ok) {
          showToast(data.error || 'Purchase failed.', 'error');
          return;
        }
        showToast(data.already_owned ? 'You already own this project.' : 'Purchase successful!', 'success');
        fetchProjects();
        project.owned = true;
        if (project.is_custom) {
          projectModal.classList.remove('active');
          if (customReqModal) customReqModal.classList.add('active');
        } else {
          renderModalAction(project);
        }
      })
      .catch(() => {
        actionBtn.disabled = false;
        showToast('Server error while purchasing.', 'error');
      });
  }

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', () => {
      projectModal.classList.remove('active');
      if (activeSerialInterval) clearInterval(activeSerialInterval);
    });
  }

  if (aboutModalClose) {
    aboutModalClose.addEventListener('click', () => {
      aboutModal.classList.remove('active');
    });
  }

  if (contactModalClose) {
    contactModalClose.addEventListener('click', () => {
      contactModal.classList.remove('active');
    });
  }

  if (contactForm) {
    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      contactModal.classList.remove('active');
      contactForm.reset();
      showToast('Thank you! Your message has been sent to Technosankalp Support.', 'success');
    });
  }

  const modalTabBtns = document.querySelectorAll('.modal-tabs .tab-btn');
  const modalTabPanes = document.querySelectorAll('.tab-pane');
  modalTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modalTabBtns.forEach(b => b.classList.remove('active'));
      modalTabPanes.forEach(p => p.style.display = 'none');
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.style.display = 'block';
    });
  });

  // ---------------------------------------------------------------------
  // Auth: login / register / logout / user menu
  // ---------------------------------------------------------------------

  function renderAuthNav() {
    if (!authNav) return;
    if (currentUser) {
      loginNavBtn.classList.add('hidden');
      registerNavBtn.classList.add('hidden');
      userMenu.classList.remove('hidden');
      userMenuName.textContent = currentUser.username;
      userAvatarInitial.textContent = currentUser.username.charAt(0).toUpperCase();
      if (currentUser.is_admin) {
        adminPanelLink.classList.remove('hidden');
      } else {
        adminPanelLink.classList.add('hidden');
      }
    } else {
      loginNavBtn.classList.remove('hidden');
      registerNavBtn.classList.remove('hidden');
      userMenu.classList.add('hidden');
      userDropdown.classList.remove('open');
    }
  }

  function closeAllAuthModals() {
    [loginModal, registerModal, customReqModal, purchasesModal, forgotModal, changePasswordModal].forEach(m => {
      if (m) m.classList.remove('active');
    });
  }

  if (loginNavBtn) loginNavBtn.addEventListener('click', () => { closeAllAuthModals(); loginModal.classList.add('active'); });
  if (registerNavBtn) registerNavBtn.addEventListener('click', () => { closeAllAuthModals(); registerModal.classList.add('active'); });
  if (loginModalClose) loginModalClose.addEventListener('click', () => loginModal.classList.remove('active'));
  if (registerModalClose) registerModalClose.addEventListener('click', () => registerModal.classList.remove('active'));
  if (switchToRegister) switchToRegister.addEventListener('click', (e) => { e.preventDefault(); closeAllAuthModals(); registerModal.classList.add('active'); });
  if (switchToLogin) switchToLogin.addEventListener('click', (e) => { e.preventDefault(); closeAllAuthModals(); loginModal.classList.add('active'); });

  if (forgotPasswordLink) forgotPasswordLink.addEventListener('click', (e) => { e.preventDefault(); closeAllAuthModals(); forgotModal.classList.add('active'); });
  if (forgotModalClose) forgotModalClose.addEventListener('click', () => forgotModal.classList.remove('active'));
  if (switchToLoginFromForgot) switchToLoginFromForgot.addEventListener('click', (e) => { e.preventDefault(); closeAllAuthModals(); loginModal.classList.add('active'); });

  if (changePasswordBtn) changePasswordBtn.addEventListener('click', (e) => {
    e.preventDefault();
    userDropdown.classList.remove('open');
    closeAllAuthModals();
    changePasswordModal.classList.add('active');
  });
  if (changePasswordModalClose) changePasswordModalClose.addEventListener('click', () => changePasswordModal.classList.remove('active'));

  if (forgotForm) {
    forgotForm.addEventListener('submit', (e) => {
      e.preventDefault();
      forgotError.classList.add('hidden');
      const email = document.getElementById('forgotEmail').value.trim();
      fetch('/api/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      }).then(r => r.json()).then(data => {
        if (!data.ok) {
          forgotError.textContent = data.message || 'Something went wrong.';
          forgotError.classList.remove('hidden');
          return;
        }
        forgotModal.classList.remove('active');
        forgotForm.reset();
        showToast(data.message || 'Check your email for a reset link.', 'success');
      }).catch(() => {
        forgotError.textContent = 'Server error. Please try again.';
        forgotError.classList.remove('hidden');
      });
    });
  }

  if (changePasswordForm) {
    changePasswordForm.addEventListener('submit', (e) => {
      e.preventDefault();
      changePasswordError.classList.add('hidden');
      const current_password = document.getElementById('currentPasswordInput').value;
      const new_password = document.getElementById('newPasswordInput').value;
      const confirm_password = document.getElementById('confirmPasswordInput').value;
      if (new_password !== confirm_password) {
        changePasswordError.textContent = 'New passwords do not match.';
        changePasswordError.classList.remove('hidden');
        return;
      }
      fetch('/api/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password, new_password }),
      }).then(r => r.json()).then(data => {
        if (!data.ok) {
          changePasswordError.textContent = data.message || 'Could not change password.';
          changePasswordError.classList.remove('hidden');
          return;
        }
        changePasswordModal.classList.remove('active');
        changePasswordForm.reset();
        showToast(data.message || 'Password changed successfully.', 'success');
      }).catch(() => {
        changePasswordError.textContent = 'Server error. Please try again.';
        changePasswordError.classList.remove('hidden');
      });
    });
  }

  [loginModal, registerModal, customReqModal, purchasesModal, forgotModal, changePasswordModal].forEach(modal => {
    if (!modal) return;
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('active'); });
  });

  if (userMenuTrigger) {
    userMenuTrigger.addEventListener('click', () => userDropdown.classList.toggle('open'));
    document.addEventListener('click', (e) => {
      if (userMenu && !userMenu.contains(e.target)) userDropdown.classList.remove('open');
    });
  }

  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      loginError.classList.add('hidden');
      const identifier = document.getElementById('loginIdentifier').value.trim();
      const password = document.getElementById('loginPassword').value;
      fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, password }),
      }).then(r => r.json()).then(data => {
        if (!data.ok) {
          loginError.textContent = data.error || 'Login failed.';
          if (data.unverified) {
            loginError.innerHTML = (data.error || 'Please verify your email first.') +
              ' <a href="#" id="resendVerifyLink" style="text-decoration:underline;">Resend verification email</a>';
            const link = document.getElementById('resendVerifyLink');
            if (link) link.addEventListener('click', (ev) => {
              ev.preventDefault();
              fetch('/api/resend-verification', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: identifier }),
              }).then(r => r.json()).then(d => showToast(d.message || 'Check your email.', d.ok ? 'success' : 'error'));
            });
          }
          loginError.classList.remove('hidden');
          return;
        }
        loginModal.classList.remove('active');
        loginForm.reset();
        showToast(`Welcome back, ${data.user.username}!`, 'success');
        fetchMe().then(fetchProjects);
      }).catch(() => {
        loginError.textContent = 'Server error. Please try again.';
        loginError.classList.remove('hidden');
      });
    });
  }

  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      e.preventDefault();
      registerError.classList.add('hidden');
      const username = document.getElementById('regUsername').value.trim();
      const email = document.getElementById('regEmail').value.trim();
      const password = document.getElementById('regPassword').value;
      fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      }).then(r => r.json()).then(data => {
        if (!data.ok) {
          registerError.textContent = data.error || 'Registration failed.';
          registerError.classList.remove('hidden');
          return;
        }
        registerModal.classList.remove('active');
        registerForm.reset();
        closeAllAuthModals();
        loginModal.classList.add('active');
        showToast(data.message || 'Account created. Please check your email to verify your account.', 'success');
      }).catch(() => {
        registerError.textContent = 'Server error. Please try again.';
        registerError.classList.remove('hidden');
      });
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      fetch('/api/logout', { method: 'POST' }).then(() => {
        currentUser = null;
        userDropdown.classList.remove('open');
        renderAuthNav();
        showToast('Logged out.', 'info');
        fetchProjects();
      });
    });
  }

  // ---------------------------------------------------------------------
  // Custom project requirements
  // ---------------------------------------------------------------------

  if (customReqModalClose) customReqModalClose.addEventListener('click', () => customReqModal.classList.remove('active'));

  if (promoCustomBtn) {
    promoCustomBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const customProject = allProjects.find(p => p.is_custom);
      if (!customProject) return;
      if (!currentUser) {
        closeAllAuthModals();
        loginModal.classList.add('active');
        showToast('Please log in to request a custom project.', 'info');
        return;
      }
      if (!customProject.owned) {
        buyProject(customProject);
      } else {
        customReqModal.classList.add('active');
      }
    });
  }

  if (submitCustomReqBtn) {
    submitCustomReqBtn.addEventListener('click', () => {
      const requirements = customReqText.value.trim();
      if (!requirements) {
        showToast('Please describe your requirements first.', 'error');
        return;
      }
      submitCustomReqBtn.disabled = true;
      fetch('/api/custom-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirements }),
      }).then(r => r.json()).then(data => {
        submitCustomReqBtn.disabled = false;
        if (!data.ok) {
          showToast(data.error || 'Failed to send requirements.', 'error');
          return;
        }
        customReqText.value = '';
        customReqModal.classList.remove('active');
        showToast('Requirements sent! We will get back to you soon.', 'success');
      }).catch(() => {
        submitCustomReqBtn.disabled = false;
        showToast('Server error. Please try again.', 'error');
      });
    });
  }

  // ---------------------------------------------------------------------
  // My Purchases panel
  // ---------------------------------------------------------------------

  if (myPurchasesBtn) {
    myPurchasesBtn.addEventListener('click', (e) => {
      e.preventDefault();
      userDropdown.classList.remove('open');
      loadPurchasesPanel();
      purchasesModal.classList.add('active');
    });
  }
  if (purchasesModalClose) purchasesModalClose.addEventListener('click', () => purchasesModal.classList.remove('active'));

  function loadPurchasesPanel() {
    purchasesModalBody.innerHTML = `<p style="color: var(--text-secondary); font-size: 0.85rem;">Loading…</p>`;

    Promise.all([
      fetch('/api/my-purchases').then(r => r.json()),
      fetch('/api/my-custom-requests').then(r => r.json()),
    ]).then(([purchasesData, requestsData]) => {
      const purchases = (purchasesData.purchases || []).filter(p => p.project_id !== 'custom_project');
      const requests = requestsData.requests || [];

      let html = '';

      if (!purchases.length && !requests.length) {
        html += `<p style="color: var(--text-secondary); font-size: 0.9rem;">You haven't purchased anything yet.</p>`;
      }

      if (purchases.length) {
        html += `<h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">Projects</h4>`;
        purchases.forEach(p => {
          const project = allProjects.find(ap => ap.id === p.project_id);
          const title = project ? project.title : p.project_id;
          html += `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:0.7rem 0; border-bottom:1px solid var(--border-color);">
              <span style="font-size:0.9rem;">${title}</span>
              <a href="/flash?project=${encodeURIComponent(p.project_id)}" class="btn-secondary" style="text-decoration:none; font-size:0.8rem;"><i class="fas fa-bolt"></i> Flash</a>
            </div>`;
        });
      }

      if (requests.length) {
        html += `<h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); margin: 1.25rem 0 0.5rem;">Custom Project Requests</h4>`;
        requests.forEach(r => {
          html += `
            <div style="padding:0.8rem 0; border-bottom:1px solid var(--border-color);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                <span style="font-size:0.85rem; color: var(--text-secondary);">${new Date(r.created_at).toLocaleDateString()}</span>
                <span style="font-size:0.7rem; font-weight:700; padding:0.15rem 0.5rem; border-radius:999px; ${r.status === 'responded' ? 'background:rgba(16,185,129,0.15); color:var(--accent-green);' : 'background:rgba(245,158,11,0.15); color:var(--accent-amber);'}">${r.status}</span>
              </div>
              <p style="font-size:0.85rem; color: var(--text-secondary); margin-bottom:0.4rem;">${r.requirements}</p>
              ${r.admin_message ? `<p style="font-size:0.85rem; color: var(--text-primary);"><i class="fas fa-reply" style="color: var(--accent-indigo);"></i> ${r.admin_message}</p>` : ''}
              ${r.admin_file_name ? `<a href="/api/custom-requests/${r.id}/file" class="btn-secondary" style="text-decoration:none; font-size:0.8rem; display:inline-flex; margin-top:0.4rem;"><i class="fas fa-download"></i> ${r.admin_file_name}</a>` : ''}
            </div>`;
        });
      }

      purchasesModalBody.innerHTML = html;
    }).catch(() => {
      purchasesModalBody.innerHTML = `<p style="color:#f87171; font-size:0.85rem;">Failed to load your purchases.</p>`;
    });
  }

  function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'toastContainer';
      toastContainer.className = 'toast-container';
      document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i class="fas fa-bolt" style="color: #fbbf24;"></i> <span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
});
