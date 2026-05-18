(() => {
  const safeText = (value) => String(value == null ? '' : value).trim();

  const isPdfLikePath = (pathname) => {
    const p = safeText(pathname).toLowerCase();
    if (!p) return false;
    if (p.includes('/pdf/')) return true;
    if (p.endsWith('/pdf')) return true;
    // Caso especial: acta PDF del registro de acciones.
    if (p.includes('/registro-acciones/acta')) return true;
    return false;
  };

  const buildViewerUrl = ({ pdfUrl, title, backUrl }) => {
    const params = new URLSearchParams();
    params.set('u', pdfUrl);
    if (title) params.set('title', title);
    if (backUrl) params.set('back', backUrl);
    return `/pdf/viewer/?${params.toString()}`;
  };

  const getBackUrl = () => {
    try {
      return `${window.location.pathname || '/'}${window.location.search || ''}${window.location.hash || ''}`;
    } catch (e) {
      return '/';
    }
  };

  const shouldHandleLink = (a, url) => {
    if (!a || !url) return false;
    if (a.hasAttribute('data-no-pdf-viewer')) return false;
    if (a.getAttribute('download') != null) return false;
    const href = safeText(a.getAttribute('href'));
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return false;
    if (url.origin !== window.location.origin) return false;
    if (safeText(url.pathname).startsWith('/pdf/viewer/')) return false;
    // Vista previa HTML: no debe abrir el visor PDF (evita 502 si el motor PDF falla).
    try {
      const fmt = safeText(url.searchParams.get('format')).toLowerCase();
      if (fmt === 'html' || fmt === 'htm') return false;
    } catch (e) {
      // ignore
    }
    // Si está marcado explícitamente (para endpoints que no contienen /pdf/).
    if (a.hasAttribute('data-pdf-viewer')) return true;
    // Heurística: endpoints “pdf-like”.
    if (isPdfLikePath(url.pathname)) return true;
    // Heurística extra: links con class pdf.
    if (a.classList && a.classList.contains('pdf')) return true;
    return false;
  };

  document.addEventListener(
    'click',
    (event) => {
      const a = event.target && event.target.closest ? event.target.closest('a[href]') : null;
      if (!a) return;
      // Respeta Ctrl/Cmd click y target=_blank explícito en desktop.
      try {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      } catch (e) {
        // ignore
      }
      let url = null;
      try {
        url = new URL(a.href, window.location.href);
      } catch (e) {
        return;
      }
      if (!shouldHandleLink(a, url)) return;

      // Evita navegación “a ciegas” en webviews.
      event.preventDefault();
      event.stopPropagation();

      // En visor embebido (iframe) necesitamos Content-Disposition inline; pasamos `inline=1`
      // a los endpoints PDF (si el endpoint ya decide ignorarlo, no pasa nada).
      try {
        if (!url.searchParams.has('inline')) url.searchParams.set('inline', '1');
      } catch (e) {
        // ignore
      }
      const qs = (() => {
        try {
          const raw = url.searchParams.toString();
          return raw ? `?${raw}` : '';
        } catch (e) {
          return url.search || '';
        }
      })();
      const pdfUrl = `${url.pathname}${qs}${url.hash || ''}`;
      const title = safeText(a.getAttribute('data-pdf-title')) || safeText(a.getAttribute('title')) || safeText(a.textContent) || 'PDF';
      const backUrl = getBackUrl();
      const viewerUrl = buildViewerUrl({ pdfUrl, title, backUrl });
      try {
        window.location.href = viewerUrl;
      } catch (e) {
        // fallback: abrir el PDF directamente.
        try {
          window.location.href = pdfUrl;
        } catch (err) {
          // ignore
        }
      }
    },
    true,
  );
})();
