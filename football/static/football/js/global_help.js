(() => {
  if (window.__WEBSTATS_GLOBAL_HELP_LOADED) return;
  window.__WEBSTATS_GLOBAL_HELP_LOADED = true;

  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const helpModeKey = 'webstats:help_mode:enabled';
  const demoModeKey = 'webstats:demo_mode:enabled';
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

  const ensureHelpModeStyles = () => {
    if (document.getElementById('webstats-help-mode-styles')) return;
    const style = document.createElement('style');
    style.id = 'webstats-help-mode-styles';
    style.textContent = `
      .ws-help-layer{position:fixed;inset:0;z-index:9998;pointer-events:none}
      .ws-help-chip{position:fixed;max-width:min(280px,calc(100vw - 24px));display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px;align-items:flex-start;border:1px solid rgba(34,211,238,.42);background:rgba(8,15,28,.94);color:#f8fafc;border-radius:12px;padding:7px 9px;box-shadow:0 14px 36px rgba(0,0,0,.34);font:800 12px/1.25 var(--prod-font-ui,system-ui,sans-serif);pointer-events:none}
      .ws-help-chip__mark{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:999px;background:rgba(34,211,238,.2);color:#a5f3fc;border:1px solid rgba(34,211,238,.34);font-weight:950}
      .ws-help-chip__text{min-width:0;overflow-wrap:anywhere}
      .ws-help-target{outline:2px solid rgba(34,211,238,.72)!important;outline-offset:3px!important;box-shadow:0 0 0 4px rgba(34,211,238,.12)!important}
      .ws-help-toggle-active{border-color:rgba(34,211,238,.64)!important;background:rgba(34,211,238,.18)!important;color:#ecfeff!important}
      .ws-help-toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:10001;max-width:min(520px,calc(100vw - 24px));border:1px solid rgba(34,211,238,.36);background:rgba(8,15,28,.96);color:#f8fafc;border-radius:14px;padding:10px 12px;box-shadow:0 16px 40px rgba(0,0,0,.36);font:800 13px/1.3 var(--prod-font-ui,system-ui,sans-serif)}
      .ws-demo-toggle-active{border-color:rgba(251,191,36,.72)!important;background:rgba(251,191,36,.18)!important;color:#fffbeb!important}
      .ws-demo-floating-toggle{position:fixed;right:max(14px,env(safe-area-inset-right));bottom:max(14px,env(safe-area-inset-bottom));z-index:10001;border:1px solid rgba(251,191,36,.52);background:rgba(8,15,28,.94);color:#fffbeb;border-radius:999px;padding:9px 12px;font:950 12px/1 var(--prod-font-ui,system-ui,sans-serif);box-shadow:0 14px 34px rgba(0,0,0,.34);cursor:pointer}
      .ws-demo-banner{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:10002;max-width:min(680px,calc(100vw - 24px));display:flex;gap:10px;align-items:center;border:1px solid rgba(251,191,36,.48);background:rgba(24,18,5,.96);color:#fffbeb;border-radius:14px;padding:10px 12px;box-shadow:0 18px 44px rgba(0,0,0,.38);font:850 13px/1.25 var(--prod-font-ui,system-ui,sans-serif)}
      .ws-demo-banner button{border:1px solid rgba(251,191,36,.55);background:rgba(251,191,36,.14);color:#fffbeb;border-radius:999px;padding:6px 10px;font:900 12px/1 var(--prod-font-ui,system-ui,sans-serif);cursor:pointer}
      .ws-demo-dialog{position:fixed;inset:0;z-index:10003;display:grid;place-items:center;padding:18px;background:rgba(2,6,23,.5)}
      .ws-demo-card{width:min(460px,calc(100vw - 28px));border:1px solid rgba(251,191,36,.45);background:rgba(8,15,28,.98);color:#f8fafc;border-radius:16px;box-shadow:0 24px 64px rgba(0,0,0,.46);overflow:hidden;font-family:var(--prod-font-ui,system-ui,sans-serif)}
      .ws-demo-card__head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:14px 16px 10px;border-bottom:1px solid rgba(148,163,184,.18)}
      .ws-demo-card__eyebrow{color:#fde68a;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.08em}
      .ws-demo-card__title{margin-top:4px;font-size:16px;font-weight:950;line-height:1.2;overflow-wrap:anywhere}
      .ws-demo-card__close{border:0;background:transparent;color:#e5e7eb;font-weight:950;font-size:18px;line-height:1;cursor:pointer;padding:3px 6px}
      .ws-demo-card__body{padding:14px 16px 6px;font-size:14px;font-weight:760;line-height:1.4}
      .ws-demo-card__note{margin-top:10px;color:#cbd5e1;font-size:12px;font-weight:720}
      .ws-demo-card__actions{display:flex;justify-content:flex-end;gap:8px;padding:12px 16px 16px}
      .ws-demo-card__actions button{border:1px solid rgba(148,163,184,.28);background:rgba(15,23,42,.78);color:#f8fafc;border-radius:10px;padding:8px 11px;font:900 13px/1 var(--prod-font-ui,system-ui,sans-serif);cursor:pointer}
      .ws-demo-card__actions button[data-ws-demo-exit]{border-color:rgba(251,191,36,.48);background:rgba(251,191,36,.14);color:#fffbeb}
      @media (max-width:720px){.ws-help-chip{font-size:11px;max-width:min(240px,calc(100vw - 20px));padding:6px 8px}.ws-help-chip__mark{width:16px;height:16px}}
    `.trim();
    document.head.appendChild(style);
  };

  const helpState = {
    enabled: false,
    layer: null,
    observer: null,
    raf: 0,
    targets: [],
  };

  const isVisible = (el) => {
    if (!el || !el.getBoundingClientRect) return false;
    if (el.closest('.ws-help-layer,.ws-help-toast,.ws-demo-banner,.ws-demo-dialog,.ui-tour-root,.cmdk,.ws-modal')) return false;
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
    if (el.matches(':disabled,[disabled]')) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || 1) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return false;
    if (r.bottom < 0 || r.right < 0 || r.top > window.innerHeight || r.left > window.innerWidth) return false;
    return true;
  };

  const cleanLabel = (value) => safeText(value)
    .replace(/\s+/g, ' ')
    .replace(/^[·•\-\s]+/, '')
    .slice(0, 90);

  const normalizeHelpKey = (value) => {
    try {
      return safeText(value)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
    } catch (e) {
      return safeText(value).toLowerCase().replace(/\s+/g, ' ').trim();
    }
  };

  const helpDictionary = [
    [/^(portada|home|inicio)$/, 'Vuelve a la portada del equipo con el resumen y los accesos principales.'],
    [/^entrenador$/, 'Abre el panel de trabajo del entrenador: KPIs, seguimiento y tareas del staff.'],
    [/^staff|cuerpo tecnico/, 'Abre las fichas del cuerpo técnico: datos, rol, foto y acceso al sistema.'],
    [/entrenamiento|entrenos|sesiones|microciclo/, 'Planifica entrenamientos: microciclos, sesiones, tareas y pizarra.'],
    [/^partido$|matchday|dia de partido/, 'Gestiona el partido: convocatoria, 11 inicial, registro de acciones e informes.'],
    [/convocatoria/, 'Prepara la lista de convocados y disponibilidad para el partido.'],
    [/11 inicial|once inicial|lineup|titulares/, 'Define titulares, banquillo y estructura inicial del partido.'],
    [/registro de acciones|acciones|live|en vivo/, 'Registra lo que ocurre durante el partido para generar datos e informes.'],
    [/jugador|jugadores|plantilla|roster/, 'Abre la plantilla y las fichas individuales de jugadores.'],
    [/estadistica|estadisticas|kpi|metricas/, 'Consulta indicadores de rendimiento y seguimiento del equipo o jugador.'],
    [/tactica|pizarra|abp|modelo de juego/, 'Abre herramientas tácticas: modelo de juego, pizarra y acciones a balón parado.'],
    [/metodologia|periodizacion|microciclo estructurado/, 'Añade contexto metodológico: día relativo al partido, carga dominante, momento del juego y principios del modelo.'],
    [/dia del microciclo|md[\+\-]|match day/, 'Relaciona la sesión con el partido: recuperación, adquisición, activación o día de competición.'],
    [/carga dominante/, 'Marca qué tipo de carga predomina en la sesión o tarea: recuperación, tensión, duración, velocidad o activación.'],
    [/momento del juego/, 'Indica el momento táctico principal: ataque, defensa, transición o balón parado.'],
    [/principio|subprincipio/, 'Conecta el contenido con el modelo de juego del club para planificar y revisar con más coherencia.'],
    [/regla provocadora/, 'Define la condición que fuerza el comportamiento táctico buscado dentro de la tarea.'],
    [/anadir campo|añadir campo/, 'Muestra un campo opcional de metodología y mantiene oculta la información que no necesitas rellenar.'],
    [/analisis|video|clip|scouting/, 'Abre análisis de vídeo, clips, informes y preparación del rival.'],
    [/rival|rivales/, 'Gestiona información del rival y preparación del próximo partido.'],
    [/agenda|calendario/, 'Consulta agenda semanal, entrenamientos, partidos y eventos.'],
    [/lesion|lesiones|incidencia/, 'Gestiona lesiones, incidencias y estado físico del jugador.'],
    [/informe|informes|pdf/, 'Abre o genera informes y documentos PDF.'],
    [/academia|leccion|quiz/, 'Abre contenidos formativos, lecciones y seguimiento de aprendizaje.'],
    [/configurar|configuracion|ajustes|onboarding/, 'Configura temporada, equipo, módulos, identidad y permisos.'],
    [/platform|cliente|workspace|clubes/, 'Abre la gestión global de clubes, clientes, accesos y módulos.'],
    [/buscar|ir a|comando/, 'Busca pantallas, jugadores o acciones y navega rápidamente por la app.'],
    [/atajo|atajos|shortcuts/, 'Muestra atajos de teclado y acciones rápidas.'],
    [/tema|oscuro|claro|hc/, 'Cambia el tema visual para mejorar legibilidad.'],
    [/densidad|compacto|normal/, 'Cambia el espaciado para ver más información o trabajar más cómodo.'],
    [/presentacion|pantalla completa/, 'Activa una vista limpia para presentar o trabajar con más espacio.'],
    [/cuenta|perfil/, 'Abre la configuración de la cuenta del usuario actual.'],
    [/soporte|ayuda|contacto/, 'Abre ayuda y canales de soporte.'],
    [/admin|administracion/, 'Abre herramientas de administración y mantenimiento.'],
    [/guardar|actualizar|grabar/, 'Guarda los cambios realizados en esta pantalla.'],
    [/crear|nuevo|nueva|anadir|alta/, 'Crea un nuevo elemento en esta sección.'],
    [/editar|modificar/, 'Permite cambiar los datos de este elemento.'],
    [/borrar|eliminar|quitar|revocar/, 'Elimina o retira este elemento. Revisa antes de confirmar.'],
    [/copiar/, 'Copia el enlace o texto al portapapeles.'],
    [/descargar|download/, 'Descarga el archivo o documento a tu dispositivo.'],
    [/subir|importar|cargar/, 'Sube o importa información desde un archivo.'],
    [/exportar/, 'Exporta la información para compartirla o guardarla.'],
    [/volver|atras|anterior/, 'Vuelve a la pantalla anterior.'],
    [/entrar|abrir|ver/, 'Abre esta sección o ficha para consultar más detalle.'],
    [/salir|logout|cerrar sesion/, 'Cierra la sesión del usuario actual.'],
  ];

  const controlLabel = (el) => {
    if (!el) return '';
    const explicit = cleanLabel(el.getAttribute('data-help') || el.getAttribute('aria-label') || el.getAttribute('title'));
    if (explicit) return explicit;
    if (el.matches('input,textarea')) {
      return cleanLabel(el.getAttribute('placeholder') || el.getAttribute('name') || el.id);
    }
    if (el.matches('select')) {
      const labelledBy = cleanLabel(el.getAttribute('aria-labelledby'));
      if (labelledBy) {
        const labelEl = document.getElementById(labelledBy);
        const txt = cleanLabel(labelEl?.textContent);
        if (txt) return txt;
      }
      const label = el.closest('label');
      return cleanLabel(label?.textContent || el.getAttribute('name') || 'selector');
    }
    return cleanLabel(el.innerText || el.textContent);
  };

  const explainControl = (el) => {
    const dataHelp = cleanLabel(el.getAttribute('data-help'));
    if (dataHelp) return dataHelp;
    const label = controlLabel(el);
    const lower = label.toLowerCase();
    const normalized = normalizeHelpKey(label);
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    const type = cleanLabel(el.getAttribute('type')).toLowerCase();

    if (tag === 'select') return `Cambia ${label || 'esta opción'} y actualiza el contexto.`;
    if (type === 'file') return `Sube un archivo para ${label || 'esta sección'}.`;
    if (type === 'checkbox') return `Activa o desactiva ${label || 'esta opción'}.`;
    if (type === 'radio') return `Selecciona ${label || 'esta opción'}.`;
    if (type === 'search') return `Busca ${label || 'resultados'} en esta pantalla.`;
    if (tag === 'input' || tag === 'textarea') return `Introduce ${label || 'la información solicitada'}.`;

    const dictionaryMatch = helpDictionary.find(([pattern]) => pattern.test(normalized));
    if (dictionaryMatch) return dictionaryMatch[1];

    if (lower.includes('guardar') || lower.includes('actualizar')) return 'Guarda los cambios realizados.';
    if (lower.includes('crear') || lower.includes('añadir') || lower.includes('nuevo')) return `Crea ${label.replace(/^(crear|añadir|nuevo)\s*/i, '') || 'un nuevo elemento'}.`;
    if (lower.includes('borrar') || lower.includes('eliminar') || lower.includes('quitar')) return 'Elimina o retira este elemento. Revisa antes de confirmar.';
    if (lower.includes('volver') || lower.includes('atrás') || lower.includes('anterior')) return 'Vuelve a la pantalla anterior.';
    if (lower.includes('entrar') || lower.includes('abrir') || lower.includes('ver')) return `Abre ${label.replace(/^(entrar|abrir|ver)\s*/i, '') || 'esta sección'}.`;
    if (lower.includes('pdf') || lower.includes('imprimir')) return 'Genera o abre el documento PDF.';
    if (lower.includes('copiar')) return 'Copia el enlace o texto al portapapeles.';
    if (lower.includes('buscar')) return 'Abre la búsqueda rápida o filtra resultados.';
    if (lower.includes('tema')) return 'Cambia el aspecto visual de la app.';
    if (lower.includes('densidad') || lower.includes('compacto')) return 'Cambia el espaciado de la interfaz.';
    if (lower.includes('presentación')) return 'Activa una vista limpia para presentar o trabajar con más espacio.';
    if (lower.includes('salir') || lower.includes('logout')) return 'Cierra la sesión del usuario actual.';
    if (el.matches('a[href]')) return `Abre ${label || 'este apartado'}.`;
    if (el.matches('summary')) return `Muestra u oculta ${label || 'este menú'}.`;
    return label ? `Ejecuta: ${label}.` : 'Ejecuta esta acción.';
  };

  const collectHelpTargets = () => {
    const selectors = [
      'button',
      'a[href]',
      'summary',
      'select',
      'input[type="button"]',
      'input[type="submit"]',
      'input[type="reset"]',
      'input[type="checkbox"]',
      'input[type="radio"]',
      'input[type="file"]',
      '[role="button"]',
      '[data-help]',
    ].join(',');
    const raw = Array.from(document.querySelectorAll(selectors));
    const seen = new Set();
    return raw.filter((el) => {
      if (!isVisible(el)) return false;
      if (seen.has(el)) return false;
      seen.add(el);
      return true;
    }).slice(0, 80);
  };

  const chipPosition = (rect, chipWidth = 260, chipHeight = 48) => {
    const margin = 8;
    let top = rect.top - chipHeight - 8;
    let left = rect.left;
    if (top < margin) top = rect.bottom + 8;
    if (left + chipWidth > window.innerWidth - margin) left = window.innerWidth - chipWidth - margin;
    if (left < margin) left = margin;
    if (top + chipHeight > window.innerHeight - margin) top = Math.max(margin, window.innerHeight - chipHeight - margin);
    return { top, left };
  };

  const renderHelpLayer = () => {
    if (!helpState.enabled || !helpState.layer) return;
    helpState.raf = 0;
    helpState.layer.innerHTML = '';
    helpState.targets.forEach((el) => el.classList.remove('ws-help-target'));
    helpState.targets = collectHelpTargets();
    helpState.targets.forEach((el) => {
      el.classList.add('ws-help-target');
      const rect = el.getBoundingClientRect();
      const chip = document.createElement('div');
      chip.className = 'ws-help-chip';
      chip.innerHTML = `<span class="ws-help-chip__mark">?</span><span class="ws-help-chip__text"></span>`;
      chip.querySelector('.ws-help-chip__text').textContent = explainControl(el);
      helpState.layer.appendChild(chip);
      const measured = chip.getBoundingClientRect();
      const pos = chipPosition(rect, measured.width || 260, measured.height || 48);
      chip.style.top = `${pos.top}px`;
      chip.style.left = `${pos.left}px`;
    });
  };

  const scheduleHelpRender = () => {
    if (!helpState.enabled || helpState.raf) return;
    helpState.raf = window.requestAnimationFrame(renderHelpLayer);
  };

  const setHelpButtons = (enabled) => {
    document.querySelectorAll('[data-webstats-help-mode-toggle],#webstats-help-mode-toggle').forEach((btn) => {
      btn.classList.toggle('ws-help-toggle-active', enabled);
      btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      if (btn.id === 'webstats-help-mode-toggle') btn.textContent = enabled ? '×' : '?';
    });
  };

  const showHelpToast = (text) => {
    let toast = document.querySelector('.ws-help-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'ws-help-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    window.clearTimeout(showHelpToast.timer);
    showHelpToast.timer = window.setTimeout(() => {
      try { toast.remove(); } catch (e) {}
    }, 2600);
  };

  const setHelpMode = (enabled, { persist = true, announce = true } = {}) => {
    ensureHelpModeStyles();
    helpState.enabled = !!enabled;
    if (persist) {
      try { window.localStorage?.setItem(helpModeKey, enabled ? '1' : '0'); } catch (e) {}
    }
    setHelpButtons(helpState.enabled);
    if (helpState.enabled) {
      if (!helpState.layer) {
        helpState.layer = document.createElement('div');
        helpState.layer.className = 'ws-help-layer';
        helpState.layer.setAttribute('aria-hidden', 'true');
        document.body.appendChild(helpState.layer);
      }
      if (!helpState.observer) {
        helpState.observer = new MutationObserver((mutations) => {
          const hasExternalChange = (mutations || []).some((mutation) => {
            const target = mutation.target;
            return !(target && target.closest && target.closest('.ws-help-layer,.ws-help-toast'));
          });
          if (hasExternalChange) scheduleHelpRender();
        });
        helpState.observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'aria-hidden', 'style', 'disabled'] });
      }
      window.addEventListener('scroll', scheduleHelpRender, true);
      window.addEventListener('resize', scheduleHelpRender, true);
      renderHelpLayer();
      if (announce) showHelpToast('Modo ayuda activado. Pulsa × para ocultar las explicaciones.');
    } else {
      if (helpState.layer) helpState.layer.innerHTML = '';
      helpState.targets.forEach((el) => el.classList.remove('ws-help-target'));
      helpState.targets = [];
      if (helpState.observer) {
        helpState.observer.disconnect();
        helpState.observer = null;
      }
      window.removeEventListener('scroll', scheduleHelpRender, true);
      window.removeEventListener('resize', scheduleHelpRender, true);
      if (announce) showHelpToast('Modo ayuda desactivado.');
    }
  };

  const wireHelpMode = () => {
    document.addEventListener('click', (event) => {
      const btn = event.target?.closest?.('[data-webstats-help-mode-toggle],#webstats-help-mode-toggle');
      if (!btn) return;
      event.preventDefault();
      setHelpMode(!helpState.enabled);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && helpState.enabled) setHelpMode(false);
    });
    let saved = '0';
    try { saved = safeText(window.localStorage?.getItem(helpModeKey), '0'); } catch (e) {}
    if (saved === '1') {
      window.setTimeout(() => setHelpMode(true, { persist: false, announce: false }), 250);
    } else {
      setHelpButtons(false);
    }
    window.WebstatsHelpMode = { set: setHelpMode, refresh: renderHelpLayer };
  };

  const demoState = {
    enabled: false,
    dialog: null,
    banner: null,
    previousHelpEnabled: false,
  };

  const demoControlSelector = [
    'button',
    'a[href]',
    'summary',
    'select',
    'input[type="button"]',
    'input[type="submit"]',
    'input[type="reset"]',
    'input[type="checkbox"]',
    'input[type="radio"]',
    'input[type="file"]',
    '[role="button"]',
    '[data-help]',
  ].join(',');

  const setDemoButtons = (enabled) => {
    document.querySelectorAll('[data-webstats-demo-mode-toggle],#webstats-demo-mode-toggle').forEach((btn) => {
      btn.classList.toggle('ws-demo-toggle-active', enabled);
      btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      if (btn.id === 'webstats-demo-mode-toggle') {
        btn.textContent = enabled ? 'Salir demo' : 'Demo';
        btn.setAttribute('aria-label', enabled ? 'Salir del modo muestra' : 'Activar modo muestra');
      }
    });
  };

  const ensureFallbackDemoButton = () => {
    if (document.querySelector('[data-webstats-demo-mode-toggle],#webstats-demo-mode-toggle')) return;
    ensureHelpModeStyles();
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ws-demo-floating-toggle';
    btn.setAttribute('data-webstats-demo-mode-toggle', '');
    btn.setAttribute('data-help', 'Activa el modo muestra: toca controles para aprender sin ejecutar acciones reales.');
    btn.setAttribute('title', 'Modo muestra');
    btn.setAttribute('aria-label', 'Activar modo muestra');
    btn.setAttribute('aria-pressed', 'false');
    btn.textContent = 'Demo';
    document.body.appendChild(btn);
  };

  const closeDemoDialog = () => {
    if (!demoState.dialog) return;
    try { demoState.dialog.remove(); } catch (e) {}
    demoState.dialog = null;
  };

  const demoActionText = (el) => {
    const label = controlLabel(el) || 'este control';
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    const type = cleanLabel(el.getAttribute('type')).toLowerCase();
    if (el.matches('a[href]')) return `En modo normal abriría: ${label}.`;
    if (tag === 'select') return 'En modo normal cambiaría el contexto o aplicaría esta opción.';
    if (type === 'submit') return 'En modo normal enviaría el formulario y guardaría o procesaría la información.';
    if (type === 'checkbox' || type === 'radio') return 'En modo normal cambiaría esta selección.';
    if (type === 'file') return 'En modo normal abriría el selector de archivos.';
    if (el.matches('summary')) return 'En modo normal abriría o cerraría este menú.';
    return 'En modo normal ejecutaría esta acción.';
  };

  const showDemoExplanation = (el) => {
    ensureHelpModeStyles();
    closeDemoDialog();
    const title = controlLabel(el) || 'Control';
    const body = explainControl(el);
    const note = demoActionText(el);
    const dialog = document.createElement('div');
    dialog.className = 'ws-demo-dialog';
    dialog.setAttribute('role', 'presentation');
    dialog.innerHTML = `
      <div class="ws-demo-card" role="dialog" aria-modal="true" aria-label="Modo muestra">
        <div class="ws-demo-card__head">
          <div>
            <div class="ws-demo-card__eyebrow">Modo muestra</div>
            <div class="ws-demo-card__title"></div>
          </div>
          <button type="button" class="ws-demo-card__close" data-ws-demo-close aria-label="Cerrar">×</button>
        </div>
        <div class="ws-demo-card__body">
          <div class="ws-demo-card__text"></div>
          <div class="ws-demo-card__note"></div>
        </div>
        <div class="ws-demo-card__actions">
          <button type="button" data-ws-demo-close>Entendido</button>
          <button type="button" data-ws-demo-exit>Salir demo</button>
        </div>
      </div>
    `;
    dialog.querySelector('.ws-demo-card__title').textContent = title;
    dialog.querySelector('.ws-demo-card__text').textContent = body;
    dialog.querySelector('.ws-demo-card__note').textContent = note;
    dialog.querySelectorAll('[data-ws-demo-close]').forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        closeDemoDialog();
      });
    });
    dialog.querySelector('[data-ws-demo-exit]')?.addEventListener('click', (event) => {
      event.preventDefault();
      setDemoMode(false);
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) closeDemoDialog();
    });
    document.body.appendChild(dialog);
    demoState.dialog = dialog;
    dialog.querySelector('[data-ws-demo-close]')?.focus?.();
  };

  const showDemoBanner = () => {
    ensureHelpModeStyles();
    if (demoState.banner) return;
    const banner = document.createElement('div');
    banner.className = 'ws-demo-banner';
    banner.innerHTML = '<span>Modo muestra activo: toca cualquier botón para ver qué hace. No se ejecutan acciones reales.</span><button type="button" data-ws-demo-exit>Salir</button>';
    banner.querySelector('[data-ws-demo-exit]')?.addEventListener('click', (event) => {
      event.preventDefault();
      setDemoMode(false);
    });
    document.body.appendChild(banner);
    demoState.banner = banner;
  };

  const hideDemoBanner = () => {
    if (!demoState.banner) return;
    try { demoState.banner.remove(); } catch (e) {}
    demoState.banner = null;
  };

  const setDemoMode = (enabled, { persist = true, announce = true } = {}) => {
    ensureHelpModeStyles();
    demoState.enabled = !!enabled;
    if (persist) {
      try { window.localStorage?.setItem(demoModeKey, enabled ? '1' : '0'); } catch (e) {}
    }
    setDemoButtons(demoState.enabled);
    document.documentElement.toggleAttribute('data-webstats-demo-mode', demoState.enabled);
    if (demoState.enabled) {
      demoState.previousHelpEnabled = helpState.enabled;
      if (!helpState.enabled) setHelpMode(true, { persist: false, announce: false });
      showDemoBanner();
      if (announce) showHelpToast('Modo muestra activado. Las acciones quedan bloqueadas mientras aprendes.');
    } else {
      closeDemoDialog();
      hideDemoBanner();
      if (!demoState.previousHelpEnabled && helpState.enabled) setHelpMode(false, { persist: false, announce: false });
      if (announce) showHelpToast('Modo muestra desactivado.');
    }
  };

  const interceptDemoInteraction = (event) => {
    if (!demoState.enabled) return;
    const target = event.target;
    if (!target || !target.closest) return;
    if (target.closest('.ws-demo-banner,.ws-demo-dialog,.ws-help-layer,.ws-help-toast')) return;
    if (target.closest('[data-webstats-demo-mode-toggle],#webstats-demo-mode-toggle,[data-webstats-help-mode-toggle],#webstats-help-mode-toggle')) return;
    const control = target.closest(demoControlSelector);
    if (!control || !isVisible(control)) return;
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
    showDemoExplanation(control);
  };

  const interceptDemoSubmit = (event) => {
    if (!demoState.enabled) return;
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
    const submitter = event.submitter && event.submitter.closest ? event.submitter : null;
    showDemoExplanation(submitter || event.target);
  };

  const wireDemoMode = () => {
    ensureFallbackDemoButton();
    document.addEventListener('click', (event) => {
      const btn = event.target?.closest?.('[data-webstats-demo-mode-toggle],#webstats-demo-mode-toggle');
      if (!btn) return;
      event.preventDefault();
      setDemoMode(!demoState.enabled);
    });
    document.addEventListener('click', interceptDemoInteraction, true);
    document.addEventListener('submit', interceptDemoSubmit, true);
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || !demoState.enabled) return;
      if (demoState.dialog) {
        event.preventDefault();
        closeDemoDialog();
        return;
      }
      setDemoMode(false);
    });
    let saved = '0';
    try { saved = safeText(window.localStorage?.getItem(demoModeKey), '0'); } catch (e) {}
    if (saved === '1') {
      window.setTimeout(() => setDemoMode(true, { persist: false, announce: false }), 300);
    } else {
      setDemoButtons(false);
    }
    window.WebstatsDemoMode = { set: setDemoMode, show: showDemoExplanation };
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
    try {
      if (window.__WEBSTATS_SUPPRESS_AUTO_TOUR === true) return;
      if (document.body?.classList?.contains('suppress-auto-tour')) return;
    } catch (e) { /* ignore */ }
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
    wireHelpMode();
    wireDemoMode();
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
