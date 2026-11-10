/* ============================================
   StaffTrack – app.js
   ============================================ */

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

  /* ---------- Clickable rows (instant feedback) ---------- */
  document.querySelectorAll('tr.clickable-row[data-href]').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('a, button, input, select, textarea')) return;
      row.classList.add('row-navigating');
      requestAnimationFrame(() => {
        window.location.href = row.dataset.href;
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

  /* ---------- Toggle staff with no commitment covering today ---------- */
  const zeroCommitmentToggle = document.getElementById('zeroCommitmentToggle');
  const zeroCommitmentDetails = document.getElementById('zeroCommitmentDetails');
  if (zeroCommitmentToggle && zeroCommitmentDetails) {
    zeroCommitmentToggle.addEventListener('click', () => {
      const expanded = zeroCommitmentToggle.getAttribute('aria-expanded') !== 'true';
      zeroCommitmentToggle.setAttribute('aria-expanded', String(expanded));
      zeroCommitmentDetails.hidden = !expanded;
      if (expanded) zeroCommitmentDetails.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        const visible = !filtered || row.dataset.zeroCommitmentToday === 'true';
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
  window.openModal = (id) => {
    const m = document.getElementById(id);
    if (m) m.classList.add('open');
  };
  window.closeModal = (id) => {
    const m = document.getElementById(id);
    if (m) m.classList.remove('open');
  };
  document.querySelectorAll('.modal-backdrop').forEach(m => {
    m.addEventListener('click', (e) => { if (e.target === m) m.classList.remove('open'); });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
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
  let deferredPrompt = null;
  const installSidebarBtn = document.getElementById('installAppBtn');
  const installTopbarBtn = document.getElementById('installAppTopbarBtn');
  const installLoginBtn = document.getElementById('installAppLoginBtn');
  const installButtons = [installSidebarBtn, installTopbarBtn, installLoginBtn].filter(Boolean);

  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    });
  }

  const showInstallButtons = () => {
    if (isStandalone) return;
    installButtons.forEach(btn => {
      btn.style.display = btn.classList.contains('nav-item') ? 'flex' : 'inline-flex';
    });
    if (typeof lucide !== 'undefined') lucide.createIcons();
  };

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallButtons();
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    installButtons.forEach(btn => {
      btn.style.display = 'none';
    });
  });

  if (!isStandalone) {
    setTimeout(showInstallButtons, 600);
  }

  const handleInstallClick = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      try {
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
          deferredPrompt = null;
          installButtons.forEach(btn => { btn.style.display = 'none'; });
        }
      } catch (err) {}
    } else {
      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
      if (isIOS) {
        alert("To install StaffTrack on your iPhone or iPad:\n\n1. Tap the Share button in Safari (box with up arrow)\n2. Scroll down and tap 'Add to Home Screen'");
      } else {
        alert("To install StaffTrack:\n\nClick the Install icon in your browser's address bar, or open the browser menu and select 'Install StaffTrack' or 'Install App'.");
      }
    }
  };

  installButtons.forEach(btn => {
    btn.addEventListener('click', handleInstallClick);
  });

});