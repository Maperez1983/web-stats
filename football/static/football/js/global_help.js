(() => {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const isNativeApp = () => {
    try {
      if (window.Capacitor && typeof window.Capacitor.getPlatform === 'function') {
        return String(window.Capacitor.getPlatform() || '').toLowerCase() !== 'web';
      }
    } catch (e) {}
    const ua = safeText(navigator.userAgent).toLowerCase();
    return ua.includes('capacitor') || ua.includes('wkwebview') || (ua.includes('webview') && !ua.includes('safari'));
  };

  const buildPdfViewerUrl = (href, title = 'PDF') => {
    try {
      const target = new URL(String(href || ''), window.location.href);
      const u = `${target.pathname || '/'}${target.search || ''}`;
      const back = `${window.location.pathname || '/'}${window.location.search || ''}${window.location.hash || ''}`;
      const viewer = new URL('/pdf/viewer/', window.location.origin);
      viewer.searchParams.set('u', u);
      viewer.searchParams.set('back', back);
      viewer.searchParams.set('title', safeText(title, 'PDF').slice(0, 140));
      return `${viewer.pathname}${viewer.search}`;
    } catch (e) {
      const back = `${window.location.pathname || '/'}${window.location.search || ''}${window.location.hash || ''}`;
      const encoded = encodeURIComponent(String(href || '').trim());
      const encodedBack = encodeURIComponent(back);
      const encodedTitle = encodeURIComponent(safeText(title, 'PDF').slice(0, 140));
      return `/pdf/viewer/?u=${encoded}&back=${encodedBack}&title=${encodedTitle}`;
    }
  };

  const isPdfLikeHref = (href) => {
    const h = safeText(href).toLowerCase();
    if (!h || h === '#') return false;
    if (h.startsWith('/pdf/viewer')) return false;
    if (h.includes('/pdf')) return true;
    if (h.endsWith('.pdf')) return true;
    return false;
  };

  const openPdfInViewer = (href, title) => {
    const viewerUrl = buildPdfViewerUrl(href, title);
    try { window.location.href = viewerUrl; } catch (e) {}
  };

  const findNavLinkByText = (needle) => {
    const links = Array.from(document.querySelectorAll('.product-nav-shortcuts a'));
    const lower = safeText(needle).toLowerCase();
    return links.find((a) => safeText(a.textContent).toLowerCase() === lower) || null;
  };

  const globalTourSteps = () => {
    const menuSummary = document.querySelector('.product-nav-shortcuts details.nav-more > summary');
    const searchBtn = document.querySelector('[data-command-palette]');
    const entrenos = findNavLinkByText('Entrenos');
    const partido = findNavLinkByText('Partido');
    const portada = findNavLinkByText('Portada');

    return [
      {
        anchor: '.dragon-nav, .dragon-link',
        title: 'Guía general',
        body: 'Esta guía te enseña cómo moverte por la app. Puedes repetirla cuando quieras desde “Guía”.',
      },
      {
        anchor: portada ? '.product-nav-shortcuts a.is-active, .product-nav-shortcuts a' : '.product-nav-shortcuts',
        title: 'Navegación',
        body: 'Arriba tienes accesos a Portada, Entrenos y Partido. El resto está en “Menú”.',
      },
      {
        anchor: entrenos ? '.product-nav-shortcuts a[href*=\"coach/sesiones\"]' : '.product-nav-shortcuts',
        title: 'Entrenos',
        body: 'Aquí creas sesiones y tareas (pizarras). Desde las tareas puedes imprimir PDF.',
      },
      {
        anchor: partido ? '.product-nav-shortcuts a[href*=\"match\"], .product-nav-shortcuts a[href*=\"partido\"], .product-nav-shortcuts a[href*=\"registro-acciones\"], .product-nav-shortcuts a[href*=\"convocatoria\"]' : '.product-nav-shortcuts',
        title: 'Partido',
        body: 'Convocatoria, 11 inicial y registro de acciones para el día de partido.',
      },
      {
        anchor: menuSummary ? '.product-nav-shortcuts details.nav-more > summary' : '.product-nav-shortcuts',
        title: 'Menú',
        body: 'En “Menú” tienes el buscador, análisis, plantilla/jugadores, staff y ajustes.',
      },
      {
        anchor: searchBtn ? '[data-command-palette]' : '.product-nav-shortcuts details.nav-more',
        title: 'Buscar / Ir a…',
        body: 'Usa “Buscar / Ir a…” para llegar rápido a cualquier pantalla (y para descubrir funciones).',
      },
    ];
  };

  const pageTour = () => {
    const id = safeText(window.__WEBSTATS_PAGE_TOUR_ID);
    const steps = Array.isArray(window.__WEBSTATS_PAGE_TOUR_STEPS) ? window.__WEBSTATS_PAGE_TOUR_STEPS : null;
    if (id && steps && steps.length) return { id, steps };
    return null;
  };

  const startTour = (options = {}) => {
    const tour = window.WebstatsTour;
    if (!tour) return false;
    const page = pageTour();
    if (page && options.preferGlobal !== true) {
      return tour.start(page.id, page.steps, { force: true });
    }
    return tour.start('global_nav_v1', globalTourSteps(), { force: true });
  };

  const wireHelpButtons = () => {
    const btn = document.getElementById('webstats-global-help');
    if (!btn) return;
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      startTour({ preferGlobal: event.altKey === true });
    });
  };

  const autoStartOnce = () => {
    const tour = window.WebstatsTour;
    if (!tour) return;
    const key = 'webstats:tour:global_nav_v1:done';
    let seen = '0';
    try { seen = safeText(window.localStorage?.getItem(key), '0'); } catch (e) { /* ignore */ }
    if (seen === '1') return;
    // Auto-start solo si existe barra de navegación (para no romper páginas especiales/login).
    const hasNav = !!document.querySelector('.product-nav-shortcuts');
    if (!hasNav) return;
    // Pequeño delay para no interrumpir renders iniciales.
    window.setTimeout(() => {
      try { tour.startIfNeeded('global_nav_v1', globalTourSteps(), { force: false }); } catch (e) { /* ignore */ }
    }, 650);
  };

  window.addEventListener('DOMContentLoaded', () => {
    wireHelpButtons();
    autoStartOnce();
    // En iOS/Capacitor, `target=_blank` abre un webview sin navegación y el usuario puede quedar atrapado.
    // Interceptamos enlaces a PDFs y los abrimos en un visor con botón "Volver".
    if (isNativeApp()) {
      try {
        window.WebstatsPdf = window.WebstatsPdf || {};
        window.WebstatsPdf.isNativeApp = isNativeApp;
        window.WebstatsPdf.buildViewerUrl = buildPdfViewerUrl;
        window.WebstatsPdf.openInViewer = openPdfInViewer;
      } catch (e) {}

      document.addEventListener(
        'click',
        (event) => {
          const target = event.target;
          const link = target && target.closest ? target.closest('a[href]') : null;
          if (!link) return;
          const href = link.getAttribute('href') || '';
          if (!isPdfLikeHref(href)) return;
          if (safeText(link.getAttribute('data-no-pdf-viewer')).trim() === '1') return;
          event.preventDefault();
          event.stopPropagation();
          const title = safeText(link.getAttribute('data-pdf-title')) || safeText(link.textContent) || 'PDF';
          openPdfInViewer(href, title);
        },
        true,
      );
    }
  });
})();
