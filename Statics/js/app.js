/* ============================================
   StaffTrack – app.js
   ============================================ */

/* ---------- Global Modal Functions (Immediately Available) ---------- */
window.openModal = function(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.add('open');
    m.removeAttribute('hidden');
    m.style.display = 'flex';
  } else {
    console.error('Modal with id "' + id + '" not found in DOM.');
  }
};

window.closeModal = function(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.remove('open');
    m.style.display = '';
  }
};

window.openAssignTaskModal = function(userId, userName) {
  const modal = document.getElementById('assignTaskModal');
  if (!modal) {
    console.error('assignTaskModal element not found');
    return;
  }
  const select = document.getElementById('assignTaskOwnerSelect');
  const title = document.getElementById('assignTaskModalTitle');
  if (select && userId) {
    let opt = select.querySelector('option[value="' + userId + '"]');
    if (!opt && userName) {
      opt = document.createElement('option');
      opt.value = String(userId);
      opt.textContent = userName;
      select.appendChild(opt);
    }
    select.value = String(userId);
  }
  if (title && userName) {
    title.textContent = 'Assign Task to ' + userName;
  } else if (title) {
    title.textContent = 'Assign Task';
  }
  window.openModal('assignTaskModal');
  if (window.lucide && window.lucide.createIcons) {
    window.lucide.createIcons();
  }
};

/* Delegated click handler for any assign task button (capture phase so no stopPropagation blocks it) */
document.addEventListener('click', function(e) {
  const btn = e.target.closest('[data-assign-task-btn]');
  if (btn) {
    e.preventDefault();
    e.stopPropagation();
    const uid = btn.getAttribute('data-user-id') || null;
    const uname = btn.getAttribute('data-user-name') || null;
    window.openAssignTaskModal(uid, uname);
  }
}, true);

document.addEventListener('DOMContentLoaded', () => {

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Lucide icons ---------- */
  if (typeof lucide !== 'undefined') lucide.createIcons();

  /* ---------- Sidebar collapse ---------- */
  const sidebar = document.getElementById('sidebar');
  const mainWrapper = document.getElementById('mainWrapper');
  const toggleBtn = document.getElementById('sidebarToggle');
  const overlay = document.getElementById('sidebarOverlay');
  const hamburger = document.getElementById('hamburgerBtn');

  if (sidebar && mainWrapper) {
    const COLLAPSED_KEY = 'sidebar_collapsed';
    if (localStorage.getItem(COLLAPSED_KEY) === '1' && window.innerWidth > 768) {
      sidebar.classList.add('collapsed');
      mainWrapper.classList.add('sidebar-collapsed');
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const collapsed = sidebar.classList.toggle('collapsed');
        mainWrapper.classList.toggle('sidebar-collapsed', collapsed);
        localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
      });
    }

    const toggleMobile = () => {
      sidebar.classList.toggle('mobile-open');
      if (overlay) overlay.classList.toggle('active');
    };
    if (hamburger) hamburger.addEventListener('click', toggleMobile);
    if (overlay) {
      overlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
      });
    }
  }

  /* ---------- Sub-nav toggles ---------- */
  document.querySelectorAll('.nav-item[data-subnav]').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const subNav = document.getElementById(item.dataset.subnav);
      if (!subNav) return;
      const isOpen = subNav.classList.toggle('open');
      item.classList.toggle('open', isOpen);
    });
  });

  /* ---------- Auto-dismiss flash alerts ---------- */
  document.querySelectorAll('.alert[data-autodismiss]').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity .4s, transform .4s';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-6px)';
      setTimeout(() => alert.remove(), 400);
    }, 3500);
  });

  /* ---------- Entrance sequence (sets --i for stagger) ---------- */
  [
    '.stats-grid > .stat-card',
    '.page-body > .card:not(.banner)',
    '.manager-block',
    '.commitment-item',
    '.subordinate-card',
    'tbody tr'
  ].forEach(sel => {
    document.querySelectorAll(sel).forEach((el, i) => {
      el.style.setProperty('--i', Math.min(i, 8));
    });
  });

  /* ---------- Clickable rows and cards (instant feedback) ---------- */
  document.querySelectorAll('tr.clickable-row[data-href], .clickable-card[data-href]').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('a, button, input, select, textarea, [data-assign-task-btn]')) return;
      el.classList.add('row-navigating');
      requestAnimationFrame(() => {
        window.location.href = el.dataset.href;
      });
    });
  });

  /* ---------- Card loading state on form submit ---------- */
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      if (!form.checkValidity || form.checkValidity()) {
        const parentCard = form.closest('.card, .subordinate-card, .commitment-item, .stat-card');
        if (parentCard) {
          parentCard.classList.add('is-loading');
        }
      }
    });
  });

  /* ---------- Automatically save commitment progress on change ---------- */
  document.querySelectorAll('.commitment-progress-slider').forEach(input => {
    const updateProgressDisplay = () => {
      const percentage = `${input.value}%`;
      input.style.setProperty('--progress', percentage);
      const output = input.form.querySelector('.progress-pct');
      if (output) output.value = percentage;
    };

    updateProgressDisplay();
    input.addEventListener('input', updateProgressDisplay);
    input.addEventListener('change', () => {
      input.form.requestSubmit();
    });
  });

  /* ---------- Filter commitments from the summary cards ---------- */
  document.querySelectorAll('.commitment-page-layout').forEach(page => {
    const filters = page.querySelectorAll('.commitment-filter-card');
    const items = page.querySelectorAll('.commitment-item[data-commitment-status]');
    if (!filters.length || !items.length) return;

    const list = page.querySelector('.commitment-list-scroll');
    const title = page.querySelector('[data-commitment-list-title]');
    const visibleCount = page.querySelector('[data-commitment-visible-count]');
    const emptyState = page.querySelector('.commitment-filter-empty');

    filters.forEach(filter => {
      filter.addEventListener('click', () => {
        const status = filter.dataset.commitmentFilter;
        const label = filter.querySelector('.stat-label').textContent.trim();
        let count = 0;

        filters.forEach(card => {
          card.setAttribute('aria-pressed', String(card === filter));
        });
        items.forEach(item => {
          const visible = status === 'all' || item.dataset.commitmentStatus === status;
          item.hidden = !visible;
          if (visible) count += 1;
        });

        if (title) title.textContent = status === 'all' ? 'All Commitments' : `${label} Commitments`;
        if (visibleCount) visibleCount.textContent = count;
        if (emptyState) emptyState.hidden = count !== 0;
        if (list) list.scrollTop = 0;
      });
    });
  });

  /* ---------- CMO Zero Commitments Toggles & Card Filtering ---------- */
  const zeroCommitmentToggle = document.getElementById('zeroCommitmentToggle');
  const zeroCommitmentDetails = document.getElementById('zeroCommitmentDetails');
  const zeroManagerCommitmentToggle = document.getElementById('zeroManagerCommitmentToggle');
  const zeroManagerCommitmentDetails = document.getElementById('zeroManagerCommitmentDetails');
  const managerCards = document.querySelectorAll('[data-manager-card]');
  const cmoActiveFilterStatus = document.getElementById('cmoActiveFilterStatus');
  const cmoActiveFilterText = document.getElementById('cmoActiveFilterText');
  const cmoResetFilterBtn = document.getElementById('cmoResetFilterBtn');
  const cmoEmptyResetBtn = document.getElementById('cmoEmptyResetBtn');
  const cmoFilterEmptyState = document.getElementById('cmoFilterEmptyState');
  const cmoManagerCountBadge = document.getElementById('cmoManagerCountBadge');
  const totalManagerCount = managerCards.length;

  /* ---------- CMO Top KPI Cards Details Toggles ---------- */
  const kpiPanels = [
    { toggle: document.getElementById('kpiManagersToggle'), panel: document.getElementById('kpiDetailsManagers') },
    { toggle: document.getElementById('kpiStaffToggle'), panel: document.getElementById('kpiDetailsStaff') },
    { toggle: document.getElementById('kpiManagerCommitmentsToggle'), panel: document.getElementById('kpiDetailsManagerCommitments') },
    { toggle: document.getElementById('kpiTasksToggle'), panel: document.getElementById('kpiDetailsStaffTasks') }
  ];

  const closeAllKpiPanels = () => {
    kpiPanels.forEach(({ toggle, panel }) => {
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
      if (panel) panel.hidden = true;
    });
  };

  const closeAllOverviewPanels = () => {
    closeAllKpiPanels();
    resetCmoFilter();
  };

  kpiPanels.forEach(({ toggle, panel }) => {
    if (!toggle || !panel) return;

    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';

      if (isExpanded) {
        toggle.setAttribute('aria-expanded', 'false');
        panel.hidden = true;
      } else {
        closeAllOverviewPanels();

        toggle.setAttribute('aria-expanded', 'true');
        panel.hidden = false;
        if (typeof lucide !== 'undefined') lucide.createIcons();
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    toggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle.click();
      }
    });
  });

  // Delegated handler for closing any KPI panel via its close X button
  document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('[data-close-kpi]');
    if (closeBtn) {
      e.preventDefault();
      const targetPanelId = closeBtn.getAttribute('data-close-kpi');
      const targetPanel = document.getElementById(targetPanelId);
      if (targetPanel) {
        targetPanel.hidden = true;
        const matchingKpi = kpiPanels.find(item => item.panel === targetPanel);
        if (matchingKpi && matchingKpi.toggle) {
          matchingKpi.toggle.setAttribute('aria-expanded', 'false');
        }
      }
    }
  });

  const resetCmoFilter = () => {
    if (zeroCommitmentToggle) {
      zeroCommitmentToggle.setAttribute('aria-expanded', 'false');
      zeroCommitmentToggle.classList.remove('active-filter');
    }
    if (zeroCommitmentDetails) zeroCommitmentDetails.hidden = true;

    if (zeroManagerCommitmentToggle) {
      zeroManagerCommitmentToggle.setAttribute('aria-expanded', 'false');
      zeroManagerCommitmentToggle.classList.remove('active-filter');
    }
    if (zeroManagerCommitmentDetails) zeroManagerCommitmentDetails.hidden = true;

    managerCards.forEach(card => {
      card.style.display = '';
    });

    if (cmoActiveFilterStatus) cmoActiveFilterStatus.hidden = true;
    if (cmoFilterEmptyState) cmoFilterEmptyState.hidden = true;
    if (cmoManagerCountBadge) cmoManagerCountBadge.textContent = `${totalManagerCount} managers`;
  };

  const applyCmoFilter = (type) => {
    closeAllOverviewPanels();
    let matchedCount = 0;

    if (type === 'staff') {
      // Activate staff zero alert, collapse manager zero alert
      if (zeroCommitmentToggle) {
        zeroCommitmentToggle.setAttribute('aria-expanded', 'true');
        zeroCommitmentToggle.classList.add('active-filter');
      }
      if (zeroCommitmentDetails) zeroCommitmentDetails.hidden = false;

      if (zeroManagerCommitmentToggle) {
        zeroManagerCommitmentToggle.setAttribute('aria-expanded', 'false');
        zeroManagerCommitmentToggle.classList.remove('active-filter');
      }
      if (zeroManagerCommitmentDetails) zeroManagerCommitmentDetails.hidden = true;

      // Filter manager cards: only keep managers whose staff have zero commitments
      managerCards.forEach(card => {
        const staffZero = parseInt(card.dataset.staffZeroCount || '0', 10);
        const match = staffZero > 0;
        card.style.display = match ? '' : 'none';
        if (match) matchedCount++;
      });

      if (cmoActiveFilterText) {
        cmoActiveFilterText.textContent = `Staff Zero Commitments (${matchedCount} managers)`;
      }
      if (cmoActiveFilterStatus) cmoActiveFilterStatus.hidden = false;
      if (cmoManagerCountBadge) cmoManagerCountBadge.textContent = `${matchedCount} of ${totalManagerCount} managers`;
      if (cmoFilterEmptyState) cmoFilterEmptyState.hidden = matchedCount > 0;

      if (zeroCommitmentDetails) {
        zeroCommitmentDetails.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } else if (type === 'manager') {
      // Activate manager zero alert, collapse staff zero alert
      if (zeroManagerCommitmentToggle) {
        zeroManagerCommitmentToggle.setAttribute('aria-expanded', 'true');
        zeroManagerCommitmentToggle.classList.add('active-filter');
      }
      if (zeroManagerCommitmentDetails) zeroManagerCommitmentDetails.hidden = false;

      if (zeroCommitmentToggle) {
        zeroCommitmentToggle.setAttribute('aria-expanded', 'false');
        zeroCommitmentToggle.classList.remove('active-filter');
      }
      if (zeroCommitmentDetails) zeroCommitmentDetails.hidden = true;

      // Filter manager cards: only keep managers who themselves have zero commitments
      managerCards.forEach(card => {
        const match = card.dataset.managerHasZero === 'true';
        card.style.display = match ? '' : 'none';
        if (match) matchedCount++;
      });

      if (cmoActiveFilterText) {
        cmoActiveFilterText.textContent = `Managers with Zero Commitments (${matchedCount} managers)`;
      }
      if (cmoActiveFilterStatus) cmoActiveFilterStatus.hidden = false;
      if (cmoManagerCountBadge) cmoManagerCountBadge.textContent = `${matchedCount} of ${totalManagerCount} managers`;
      if (cmoFilterEmptyState) cmoFilterEmptyState.hidden = matchedCount > 0;

      if (zeroManagerCommitmentDetails) {
        zeroManagerCommitmentDetails.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
  };

  if (zeroCommitmentToggle) {
    zeroCommitmentToggle.addEventListener('click', (e) => {
      e.preventDefault();
      const isAlreadyActive = zeroCommitmentToggle.getAttribute('aria-expanded') === 'true';
      if (isAlreadyActive) {
        resetCmoFilter();
      } else {
        applyCmoFilter('staff');
      }
    });
  }

  if (zeroManagerCommitmentToggle) {
    zeroManagerCommitmentToggle.addEventListener('click', (e) => {
      e.preventDefault();
      const isAlreadyActive = zeroManagerCommitmentToggle.getAttribute('aria-expanded') === 'true';
      if (isAlreadyActive) {
        resetCmoFilter();
      } else {
        applyCmoFilter('manager');
      }
    });
  }

  if (cmoResetFilterBtn) {
    cmoResetFilterBtn.addEventListener('click', (e) => {
      e.preventDefault();
      resetCmoFilter();
    });
  }

  if (cmoEmptyResetBtn) {
    cmoEmptyResetBtn.addEventListener('click', (e) => {
      e.preventDefault();
      resetCmoFilter();
    });
  }


  const teamZeroFilter = document.querySelector('[data-zero-commitment-team-filter]');
  if (teamZeroFilter) {
    const tableRows = document.querySelectorAll('tr[data-zero-commitment-today]');
    const visibleCount = document.querySelector('[data-team-visible-count]');
    const title = document.querySelector('[data-team-members-title]');
    const reset = document.querySelector('[data-team-filter-reset]');
    const emptyRow = document.querySelector('[data-team-filter-empty]');

    const setFiltered = (filtered) => {
      let count = 0;
      tableRows.forEach(row => {
        const visible = !filtered || (row.dataset.zeroCommitmentToday === 'true' && row.dataset.currentlyPresent === 'true');
        row.hidden = !visible;
        if (visible) count += 1;
      });
      if (visibleCount) visibleCount.textContent = count;
      if (title) title.textContent = filtered ? 'Staff with Zero Commitments Today' : 'Team Members';
      if (reset) reset.hidden = !filtered;
      if (emptyRow) emptyRow.hidden = count !== 0;
      teamZeroFilter.setAttribute('aria-pressed', String(filtered));
    };

    teamZeroFilter.addEventListener('click', () => {
      setFiltered(teamZeroFilter.getAttribute('aria-pressed') !== 'true');
    });
    if (reset) reset.addEventListener('click', () => setFiltered(false));
  }

  /* ---------- Progress bar animation ---------- */
  const animateBars = () => {
    document.querySelectorAll('.progress-bar-fill').forEach(bar => {
      const pct = parseInt(bar.dataset.pct || '0', 10);
      bar.style.width = pct + '%';
      if (pct >= 100) bar.classList.add('success');
      else if (pct === 0) bar.classList.add('danger');
    });
  };
  reduceMotion ? animateBars() : setTimeout(animateBars, 100);

  /* ---------- Count-up for stat numbers ---------- */
  document.querySelectorAll('.stat-value, .m-stat-val').forEach(el => {
    const text = el.textContent.trim();
    if (!/^\d+$/.test(text) || reduceMotion) return;
    const target = parseInt(text, 10);
    if (target === 0) return;
    const duration = 600;
    const start = performance.now();
    el.textContent = '0';
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased);
      if (t < 1) requestAnimationFrame(tick);
    };
    setTimeout(() => requestAnimationFrame(tick), 80);
  });

  /* ---------- Confirm delete ---------- */
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  /* ---------- Modals ---------- */
  document.querySelectorAll('.modal-backdrop').forEach(m => {
    m.addEventListener('click', (e) => { if (e.target === m) closeModal(m.id); });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(m => closeModal(m.id));
    }
  });

  /* ---------- Highlight active nav item ---------- */
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item[href]').forEach(item => {
    const href = item.getAttribute('href');
    if (!href || href === '#') return;
    if (href === path || (href !== '/' && path.startsWith(href))) {
      item.classList.add('active');
      const subNav = item.closest('.sub-nav');
      if (subNav) {
        subNav.classList.add('open');
        const trigger = document.querySelector(`[data-subnav="${subNav.id}"]`);
        if (trigger) trigger.classList.add('open');
      }
    }
  });

  /* ---------- PWA Web App Installation ---------- */
  const installBtn = document.getElementById('installAppBtn');
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  // Hide the button if already installed as standalone app
  if (isStandalone && installBtn) {
    installBtn.style.display = 'none';
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    window.deferredPrompt = e;
  });

  window.addEventListener('appinstalled', () => {
    window.deferredPrompt = null;
    if (installBtn) installBtn.style.display = 'none';
  });

  const triggerPwaInstall = async () => {
    if (window.deferredPrompt) {
      window.deferredPrompt.prompt();
      try {
        const choice = await window.deferredPrompt.userChoice;
        if (choice && choice.outcome === 'accepted') {
          window.deferredPrompt = null;
          if (installBtn) installBtn.style.display = 'none';
          window.closeModal('pwaInstallGuideModal');
        }
      } catch (err) {
        console.debug('PWA install error:', err);
      }
    } else {
      // If browser hasn't prepared deferredPrompt yet, open helpful install guide modal
      window.openModal('pwaInstallGuideModal');
    }
  };

  if (installBtn) {
    installBtn.addEventListener('click', (e) => {
      e.preventDefault();
      triggerPwaInstall();
    });
  }

  const pwaTriggerPromptBtn = document.getElementById('pwaTriggerPromptBtn');
  if (pwaTriggerPromptBtn) {
    pwaTriggerPromptBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (window.deferredPrompt) {
        triggerPwaInstall();
      } else {
        alert("Please use the install icon (⊕) in your browser address bar or menu (⋮) -> 'Install StaffTrack'.");
      }
    });
  }

});