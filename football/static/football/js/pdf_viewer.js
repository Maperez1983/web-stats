(function () {
  const isCapacitor =
    !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  if (!isCapacitor) return;

  const safeText = (value) => String(value ?? '').trim();
  const isSameOrigin = (url) => {
    try {
      return url && url.origin === window.location.origin;
    } catch (e) {
      return false;
    }
  };

  const looksLikePdfRoute = (url) => {
    const path = String(url?.pathname || '').toLowerCase();
    if (!path) return false;
    // Rutas típicas del proyecto (GET):
    // - /.../pdf/ (player/staff/session/convocation...)
    // - /registro-acciones/acta/ (acta partido)
    if (path.includes('/pdf')) return true;
    if (path.includes('/acta')) return true;
    if (path.endsWith('.pdf')) return true;
    return false;
  };

  const fileSafeSlug = (value) =>
    safeText(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 80);

  let overlay = null;
  const ensureOverlay = () => {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'pdf-viewer-overlay';
    overlay.style.cssText = [
      'position:fixed',
      'inset:0',
      'z-index:2147483647',
      'background:rgba(2,6,23,0.78)',
      'display:none',
      'flex-direction:column',
    ].join(';');
    overlay.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.6rem;padding:0.65rem 0.75rem;background:rgba(7,16,30,0.96);border-bottom:1px solid rgba(255,255,255,0.12);">
        <button type="button" id="pdf-viewer-close" style="appearance:none;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.06);color:rgba(245,247,250,0.92);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;cursor:pointer;">Cerrar</button>
        <button type="button" id="pdf-viewer-print" style="appearance:none;border:1px solid rgba(244,180,0,0.22);background:rgba(244,180,0,0.10);color:rgba(255,249,232,0.95);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;cursor:pointer;">Imprimir</button>
        <a id="pdf-viewer-download" href="#" style="margin-left:auto;appearance:none;border:1px solid rgba(70,211,255,0.22);background:rgba(70,211,255,0.10);color:rgba(230,236,255,0.95);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;text-decoration:none;">Descargar</a>
      </div>
      <iframe id="pdf-viewer-frame" title="PDF" style="flex:1;border:0;width:100%;background:#ffffff;"></iframe>
    `;
    document.body.appendChild(overlay);

    const close = () => {
      const frame = document.getElementById('pdf-viewer-frame');
      try {
        const currentUrl = frame?.dataset?.blobUrl || '';
        if (currentUrl && currentUrl.startsWith('blob:')) URL.revokeObjectURL(currentUrl);
      } catch (e) {
        // ignore
      }
      if (frame) {
        try {
          frame.removeAttribute('src');
        } catch (e) {
          /* ignore */
        }
        try {
          frame.removeAttribute('srcdoc');
        } catch (e) {
          /* ignore */
        }
        try {
          frame.dataset.blobUrl = '';
        } catch (e) {
          /* ignore */
        }
      }
      overlay.style.display = 'none';
    };

    overlay.querySelector('#pdf-viewer-close')?.addEventListener('click', close);
    overlay.addEventListener('click', (ev) => {
      if (ev.target === overlay) close();
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && overlay.style.display !== 'none') close();
    });
    overlay.querySelector('#pdf-viewer-print')?.addEventListener('click', () => {
      const frame = document.getElementById('pdf-viewer-frame');
      try {
        frame?.contentWindow?.focus?.();
        frame?.contentWindow?.print?.();
      } catch (e) {
        // ignore
      }
    });

    return overlay;
  };

  const openOverlay = ({ blobUrl = '', filename = '', html = '' } = {}) => {
    const root = ensureOverlay();
    const frame = root.querySelector('#pdf-viewer-frame');
    const download = root.querySelector('#pdf-viewer-download');

    if (download) {
      download.setAttribute('href', blobUrl || '#');
      try {
        if (filename) download.setAttribute('download', filename);
      } catch (e) {
        // ignore
      }
      download.style.pointerEvents = blobUrl ? 'auto' : 'none';
      download.style.opacity = blobUrl ? '1' : '0.45';
    }
    if (frame) {
      try {
        frame.dataset.blobUrl = blobUrl || '';
      } catch (e) {
        // ignore
      }
      if (blobUrl) {
        try {
          frame.removeAttribute('srcdoc');
        } catch (e) {
          /* ignore */
        }
        frame.setAttribute('src', blobUrl);
      } else if (html) {
        try {
          frame.removeAttribute('src');
        } catch (e) {
          /* ignore */
        }
        try {
          frame.srcdoc = html;
        } catch (e) {
          // ignore
        }
      } else {
        try {
          frame.removeAttribute('src');
        } catch (e) {
          /* ignore */
        }
        try {
          frame.srcdoc =
            '<!doctype html><html lang="es"><meta charset="utf-8"><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:20px;">Cargando…</body></html>';
        } catch (e) {
          // ignore
        }
      }
    }
    root.style.display = 'flex';
  };

  const contentDispositionFilename = (headerValue) => {
    const raw = safeText(headerValue);
    if (!raw) return '';
    const match = raw.match(/filename\\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?/i);
    const value = match ? safeText(match[1] || match[2]) : '';
    if (!value) return '';
    try {
      return decodeURIComponent(value);
    } catch (e) {
      return value;
    }
  };

  const fetchAndOpenPdf = async (url, { suggestedName = '' } = {}) => {
    openOverlay({ html: '<!doctype html><html lang="es"><meta charset="utf-8"><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:20px;"><h1 style="font-size:16px;margin:0 0 8px;">Generando PDF…</h1><p style="margin:0;color:#334155;">En unos segundos aparecerá el documento.</p></body></html>' });
    let resp = null;
    try {
      resp = await fetch(url.toString(), { credentials: 'include', cache: 'no-store' });
    } catch (e) {
      openOverlay({
        html: '<!doctype html><html lang="es"><meta charset="utf-8"><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:20px;">No se pudo conectar para descargar el PDF.</body></html>',
      });
      return;
    }

    const ct = String(resp.headers.get('content-type') || '').toLowerCase();
    if (!resp.ok) {
      const msg = safeText(await resp.text()) || `No se pudo generar el PDF (HTTP ${resp.status}).`;
      openOverlay({
        html: `<!doctype html><html lang="es"><meta charset="utf-8"><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:20px;"><strong>Error:</strong> ${msg}</body></html>`,
      });
      return;
    }

    if (ct.includes('application/pdf')) {
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const headerName = contentDispositionFilename(resp.headers.get('content-disposition'));
      const fallbackName = suggestedName || 'documento.pdf';
      const name = headerName || fallbackName;
      openOverlay({ blobUrl, filename: name });
      return;
    }

    // HTML fallback (servidor sin PDF): mostrar el HTML pero permitir cerrar sin bloquear la app.
    const html = await resp.text();
    openOverlay({ html });
  };

  document.addEventListener(
    'click',
    (event) => {
      const target = event.target;
      const anchor = target && target.closest ? target.closest('a') : null;
      if (!anchor) return;
      if (anchor.getAttribute('data-no-pdf-viewer') === '1') return;
      const href = safeText(anchor.getAttribute('href'));
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
      let url = null;
      try {
        url = new URL(href, window.location.href);
      } catch (e) {
        return;
      }
      if (!isSameOrigin(url)) return;
      if (!looksLikePdfRoute(url)) return;

      event.preventDefault();
      event.stopPropagation();

      const label =
        safeText(anchor.getAttribute('data-pdf-name')) ||
        safeText(anchor.getAttribute('download')) ||
        fileSafeSlug(anchor.textContent) ||
        fileSafeSlug(url.pathname.split('/').filter(Boolean).slice(-2).join('_'));
      const filename = `${label || 'documento'}.pdf`;
      fetchAndOpenPdf(url, { suggestedName: filename });
    },
    true,
  );
})();

