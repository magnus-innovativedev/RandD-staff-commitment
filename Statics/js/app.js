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
      el.style.setProperty('--i', Math.min(i, 14));
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

  /* ---------- Progress bar animation ---------- */
  const animateBars = () => {
    document.querySelectorAll('.progress-bar-fill').forEach(bar => {
      const pct = parseInt(bar.dataset.pct || '0', 10);
      bar.style.width = pct + '%';
      if (pct >= 100) bar.classList.add('success');
      else if (pct === 0) bar.classList.add('danger');
    });
  };
  reduceMotion ? animateBars() : setTimeout(animateBars, 250);

  /* ---------- Count-up for stat numbers ---------- */
  document.querySelectorAll('.stat-value, .m-stat-val').forEach(el => {
    const text = el.textContent.trim();
    if (!/^\d+$/.test(text) || reduceMotion) return;
    const target = parseInt(text, 10);
    if (target === 0) return;
    const duration = 900;
    const start = performance.now();
    el.textContent = '0';
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased);
      if (t < 1) requestAnimationFrame(tick);
    };
    setTimeout(() => requestAnimationFrame(tick), 250);
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

});