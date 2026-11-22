// Senior Web Architect Interactive Runtime
(() => {
  const $ = (s, r = document) => r.querySelector(s),
        $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // 1. Header stickiness with smooth threshold detection
  const header = $('#header');
  const updateHeader = () => {
    if (!header) return;
    const isScrolled = window.scrollY > 20 || (!document.getElementById('mobile-nav')?.hidden);
    header.classList.toggle('stuck', isScrolled);
  };
  window.addEventListener('scroll', updateHeader, { passive: true });
  updateHeader();

  // 2. Mobile Menu Controller with ARIA & Focus Trap
  const btn = $('#menu-btn'), nav = $('#mobile-nav');
  if (btn && nav) {
    const setMenu = (open) => {
      nav.hidden = !open;
      btn.setAttribute('aria-expanded', open);
      btn.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
      $('[data-open]', btn).hidden = open;
      $('[data-close]', btn).hidden = !open;
      updateHeader();
    };
    btn.addEventListener('click', () => setMenu(nav.hidden));
    window.addEventListener('keydown', (e) => e.key === 'Escape' && !nav.hidden && setMenu(false));
  }

  // 3. High-Performance Intersection Observer for Scroll Reveals
  const revealElements = $$('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          obs.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.15 });
    revealElements.forEach((el) => observer.observe(el));
  } else {
    revealElements.forEach((el) => el.classList.add('in'));
  }

  // 4. Card Mouse Coordinate Tracking for Specular Glow Effect
  $$('.card').forEach((card) => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / card.clientWidth) * 100;
      const y = ((e.clientY - rect.top) / card.clientHeight) * 100;
      card.style.setProperty('--mouse-x', `${x}%`);
      card.style.setProperty('--mouse-y', `${y}%`);
    });
  });

  // 5. About Section Expand/Collapse Toggle
  const moreBtn = $('#more-btn');
  if (moreBtn) {
    moreBtn.addEventListener('click', () => {
      const expanded = moreBtn.getAttribute('aria-expanded') !== 'true';
      moreBtn.setAttribute('aria-expanded', expanded);
      const span = $('span', moreBtn);
      if (span) span.textContent = expanded ? 'Show less' : 'Read more';
      $$('[data-more]').forEach((p) => {
        p.hidden = !expanded;
        p.classList.toggle('rise', expanded);
      });
    });
  }

  // 6. Events Category Filter with Dynamic Active States
  const catsContainer = $('#cats');
  if (catsContainer) {
    let selectedCategory = 'all';
    const applyEventFilter = () => {
      const query = ($('#event-search')?.value || '').trim().toLowerCase();
      $$('#event-list > li').forEach((li) => {
        const matches = (selectedCategory === 'all' || li.dataset.cat === selectedCategory) && li.textContent.toLowerCase().includes(query);
        li.style.display = matches ? '' : 'none';
      });
    };
    $('#event-search')?.addEventListener('input', applyEventFilter);
    catsContainer.addEventListener('click', (e) => {
      const button = e.target.closest('button[data-cat]');
      if (!button) return;
      $$('#cats button').forEach((b) => {
        const active = b === button;
        b.setAttribute('aria-pressed', active);
        b.classList.toggle('btn-acid', active);
      });
      selectedCategory = button.dataset.cat;
      applyEventFilter();
    });
  }
  $('#project-search')?.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    $$('#project-list > li').forEach((li) => { li.style.display = li.dataset.search.includes(q) ? '' : 'none'; });
  });

  // 7. Destructive Action Confirmation Guard
  $$('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (e) => {
      if (!window.confirm(form.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // Password visibility controls are created next to password inputs without extra markup.
  $$('input[data-password]').forEach((input) => {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'link-u text-sm text-acid justify-self-start';
    button.textContent = 'Show password';
    input.insertAdjacentElement('afterend', button);
    button.addEventListener('click', () => {
      const show = input.type === 'password'; input.type = show ? 'text' : 'password';
      button.textContent = show ? 'Hide password' : 'Show password';
    });
  });
})();
