(function () {
  'use strict';

  if (window.__WEBSTATS_TACTICS_MODE !== true) return;
  if (window.__WEBSTATS_TACTICS_PRO_CONSOLE === true) return;
  window.__WEBSTATS_TACTICS_PRO_CONSOLE = true;

  const STORAGE_KEY = 'webstats:tactics:pro-console:v1';
  const AI_KEY = 'webstats:tactics:ai-context:v1';
  const PLUS_KEY = 'webstats:tactics:plus-workflow:v1';

  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));
  const safe = (value, fallback) => {
    const text = String(value == null ? '' : value).trim();
    return text || (fallback || '');
  };
  const setStatus = (message, isError) => {
    const el = $('#task-builder-status');
    if (el) {
      el.textContent = safe(message);
      el.classList.toggle('is-error', !!isError);
    }
  };
  const persist = (patch) => {
    try {
      const prev = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}') || {};
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.assign(prev, patch || {})));
    } catch (e) {
      /* ignore */
    }
  };
  const readState = () => {
    try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}') || {}; } catch (e) { return {}; }
  };

  const waitForCanvas = (tries) => new Promise((resolve, reject) => {
    let count = 0;
    const tick = () => {
      const canvas = window.__WEBSTATS_TPAD_CANVAS;
      if (canvas && window.fabric) {
        resolve(canvas);
        return;
      }
      count += 1;
      if (count >= (tries || 80)) {
        reject(new Error('canvas-not-ready'));
        return;
      }
      window.setTimeout(tick, 250);
    };
    tick();
  });

  const activatePane = (pane) => {
    const key = safe(pane);
    if (!key) return;
    const tab = $(`#task-side-tabs [data-pane="${key}"]`);
    if (tab) {
      tab.click();
      return;
    }
    $$('.side-tab').forEach((btn) => {
      const active = safe(btn.dataset.pane) === key;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    $$('.side-pane').forEach((paneEl) => paneEl.classList.toggle('is-active', safe(paneEl.dataset.pane) === key));
  };

  const canvasSize = (canvas) => ({
    w: Math.max(1, Number(canvas.getWidth && canvas.getWidth()) || 1200),
    h: Math.max(1, Number(canvas.getHeight && canvas.getHeight()) || 760),
  });
  const px = (canvas, x, y) => {
    const s = canvasSize(canvas);
    return { x: s.w * x, y: s.h * y, w: s.w, h: s.h };
  };
  const tagObject = (obj, layer, extra) => {
    obj.data = Object.assign({}, obj.data || {}, {
      ws_tactics_pro: true,
      ws_tactics_layer: layer || 'tactical',
    }, extra || {});
    return obj;
  };
  const add = (canvas, obj) => {
    tagObject(obj, obj && obj.data && obj.data.ws_tactics_layer);
    canvas.add(obj);
    return obj;
  };
  const bringLayersBehindPlayers = (canvas) => {
    try {
      canvas.getObjects().forEach((obj) => {
        if (obj && obj.data && ['channels', 'block', 'compare', 'sync', 'timeline', 'talk', 'rival', 'match_compare', 'checklist', 'training', 'player_view'].includes(obj.data.ws_tactics_layer)) {
          canvas.sendToBack(obj);
        }
      });
    } catch (e) {
      /* ignore */
    }
  };
  const requestRender = (canvas) => {
    try { bringLayersBehindPlayers(canvas); } catch (e) { /* ignore */ }
    try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
  };

  const makeText = (canvas, text, x, y, opts) => {
    const p = px(canvas, x, y);
    const options = Object.assign({
      left: p.x,
      top: p.y,
      fontFamily: 'Avenir Next, Inter, Segoe UI, sans-serif',
      fontSize: Math.max(13, Math.round(p.w * 0.015)),
      fontWeight: 900,
      fill: '#f8fafc',
      backgroundColor: 'rgba(2, 6, 23, 0.72)',
      padding: 7,
      selectable: true,
      evented: true,
      objectCaching: false,
    }, opts || {});
    return tagObject(new window.fabric.Textbox(safe(text), options), options.layer || 'labels');
  };

  const makePlayer = (canvas, x, y, number, team, label) => {
    const p = px(canvas, x, y);
    const r = Math.max(16, Math.min(28, Math.round(p.w * 0.018)));
    const local = team !== 'rival';
    const circle = new window.fabric.Circle({
      left: -r,
      top: -r,
      radius: r,
      fill: local ? '#22c55e' : '#ef4444',
      stroke: '#f8fafc',
      strokeWidth: 3,
      originX: 'center',
      originY: 'center',
    });
    const num = new window.fabric.Text(String(number || ''), {
      left: 0,
      top: -2,
      originX: 'center',
      originY: 'center',
      fontSize: Math.max(14, Math.round(r * 0.86)),
      fontWeight: 950,
      fill: '#ffffff',
      fontFamily: 'Avenir Next, Inter, Segoe UI, sans-serif',
    });
    const group = new window.fabric.Group([circle, num], {
      left: p.x,
      top: p.y,
      originX: 'center',
      originY: 'center',
      hasControls: true,
      objectCaching: false,
    });
    return tagObject(group, 'players', { token_kind: local ? 'player_local' : 'player_rival', label: safe(label) });
  };

  const makeBall = (canvas, x, y) => {
    const p = px(canvas, x, y);
    const r = Math.max(8, Math.round(p.w * 0.008));
    return tagObject(new window.fabric.Circle({
      left: p.x,
      top: p.y,
      originX: 'center',
      originY: 'center',
      radius: r,
      fill: '#f8fafc',
      stroke: '#0f172a',
      strokeWidth: 2,
      objectCaching: false,
    }), 'ball', { token_kind: 'ball' });
  };

  const makeArrow = (canvas, x1, y1, x2, y2, color, dashed, layer) => {
    const a = px(canvas, x1, y1);
    const b = px(canvas, x2, y2);
    const angle = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI + 90;
    const line = new window.fabric.Line([a.x, a.y, b.x, b.y], {
      stroke: color || '#38bdf8',
      strokeWidth: Math.max(4, Math.round(a.w * 0.004)),
      strokeDashArray: dashed ? [10, 8] : null,
      selectable: false,
      evented: false,
    });
    const head = new window.fabric.Triangle({
      left: b.x,
      top: b.y,
      width: Math.max(18, Math.round(a.w * 0.017)),
      height: Math.max(22, Math.round(a.w * 0.022)),
      fill: color || '#38bdf8',
      originX: 'center',
      originY: 'center',
      angle,
      selectable: false,
      evented: false,
    });
    return tagObject(new window.fabric.Group([line, head], {
      left: 0,
      top: 0,
      selectable: true,
      evented: true,
      objectCaching: false,
    }), layer || 'movement', { arrow_kind: dashed ? 'dashed' : 'solid' });
  };

  const makeZone = (canvas, x, y, w, h, color, label, layer) => {
    const p = px(canvas, x, y);
    const s = canvasSize(canvas);
    const rect = new window.fabric.Rect({
      left: p.x,
      top: p.y,
      width: s.w * w,
      height: s.h * h,
      fill: color || 'rgba(14, 165, 233, 0.12)',
      stroke: 'rgba(248, 250, 252, 0.55)',
      strokeDashArray: [10, 8],
      strokeWidth: 2,
      rx: 10,
      ry: 10,
      objectCaching: false,
    });
    if (!label) return tagObject(rect, layer || 'zones');
    const text = makeText(canvas, label, x + 0.012, y + 0.012, {
      fontSize: Math.max(12, Math.round(s.w * 0.011)),
      backgroundColor: 'rgba(2, 6, 23, 0.64)',
      layer: layer || 'zones',
    });
    return tagObject(new window.fabric.Group([rect, text], {
      left: 0,
      top: 0,
      selectable: true,
      evented: true,
      objectCaching: false,
    }), layer || 'zones');
  };

  const savePlusPayload = (patch) => {
    try {
      const prev = JSON.parse(window.localStorage.getItem(PLUS_KEY) || '{}') || {};
      window.localStorage.setItem(PLUS_KEY, JSON.stringify(Object.assign(prev, patch || {}, { updated_at: new Date().toISOString() })));
    } catch (e) {
      /* ignore */
    }
  };

  const addBoardCard = (canvas, title, lines, x, y, w, h, layer, color) => {
    const size = canvasSize(canvas);
    const rect = makeZone(canvas, x, y, w, h, color || 'rgba(15, 23, 42, 0.68)', '', layer);
    rect.set({
      stroke: 'rgba(226, 232, 240, 0.38)',
      strokeDashArray: null,
      rx: 14,
      ry: 14,
    });
    const text = makeText(canvas, `${title}\n${(lines || []).join('\n')}`, x + 0.018, y + 0.026, {
      width: size.w * Math.max(0.1, w - 0.04),
      fontSize: Math.max(12, Math.round(size.w * 0.012)),
      lineHeight: 1.22,
      fill: '#f8fafc',
      backgroundColor: 'rgba(0, 0, 0, 0)',
      layer,
    });
    text.set({ fontWeight: 800 });
    const group = new window.fabric.Group([rect, text], {
      left: 0,
      top: 0,
      selectable: true,
      evented: true,
      objectCaching: false,
    });
    return tagObject(group, layer);
  };

  const clearProLayer = async (layer) => {
    const canvas = await waitForCanvas();
    const wanted = safe(layer);
    canvas.getObjects().slice().forEach((obj) => {
      const data = obj && obj.data ? obj.data : {};
      if (data.ws_tactics_pro && (!wanted || data.ws_tactics_layer === wanted)) canvas.remove(obj);
    });
    requestRender(canvas);
    setStatus(wanted ? `Capa ${wanted} limpiada.` : 'Recursos PRO limpiados.');
  };

  const addChannels = async () => {
    const canvas = await waitForCanvas();
    [
      [0.00, 0.00, 0.18, 1, 'rgba(34, 197, 94, 0.10)', 'Carril exterior'],
      [0.18, 0.00, 0.14, 1, 'rgba(14, 165, 233, 0.09)', 'Half-space'],
      [0.32, 0.00, 0.36, 1, 'rgba(250, 204, 21, 0.07)', 'Carril central'],
      [0.68, 0.00, 0.14, 1, 'rgba(14, 165, 233, 0.09)', 'Half-space'],
      [0.82, 0.00, 0.18, 1, 'rgba(34, 197, 94, 0.10)', 'Carril exterior'],
    ].forEach((z) => add(canvas, makeZone(canvas, z[0], z[1], z[2], z[3], z[4], z[5], 'channels')));
    [
      [0.00, 0.00, 1, 0.333, 'rgba(248, 250, 252, 0.025)', 'Tercio inicio'],
      [0.00, 0.333, 1, 0.334, 'rgba(248, 250, 252, 0.035)', 'Tercio medio'],
      [0.00, 0.667, 1, 0.333, 'rgba(248, 250, 252, 0.025)', 'Tercio final'],
    ].forEach((z) => add(canvas, makeZone(canvas, z[0], z[1], z[2], z[3], z[4], z[5], 'channels')));
    requestRender(canvas);
    setStatus('Carriles, half-spaces y tercios añadidos.');
  };

  const addBlockReference = async (block) => {
    const canvas = await waitForCanvas();
    const map = {
      low: { title: 'Bloque bajo', y: 0.70, color: 'rgba(239, 68, 68, 0.15)' },
      mid: { title: 'Bloque medio', y: 0.50, color: 'rgba(250, 204, 21, 0.15)' },
      high: { title: 'Bloque alto', y: 0.30, color: 'rgba(34, 197, 94, 0.15)' },
    };
    const cfg = map[block] || map.mid;
    add(canvas, makeZone(canvas, 0.06, cfg.y - 0.10, 0.88, 0.20, cfg.color, cfg.title, 'block'));
    add(canvas, makeArrow(canvas, 0.18, cfg.y + 0.13, 0.18, cfg.y - 0.12, '#f8fafc', true, 'block'));
    add(canvas, makeArrow(canvas, 0.50, cfg.y + 0.13, 0.50, cfg.y - 0.12, '#f8fafc', true, 'block'));
    add(canvas, makeArrow(canvas, 0.82, cfg.y + 0.13, 0.82, cfg.y - 0.12, '#f8fafc', true, 'block'));
    requestRender(canvas);
    setStatus(`${cfg.title} añadido como referencia visual.`);
  };

  const templateMap = {
    build433: {
      label: 'Salida 4-3-3',
      players: [
        ['local', 1, 0.10, 0.50], ['local', 4, 0.22, 0.38], ['local', 5, 0.22, 0.62],
        ['local', 2, 0.32, 0.18], ['local', 3, 0.32, 0.82], ['local', 6, 0.43, 0.50],
        ['local', 8, 0.56, 0.36], ['local', 10, 0.58, 0.64], ['local', 7, 0.76, 0.22],
        ['local', 11, 0.76, 0.78], ['local', 9, 0.84, 0.50],
        ['rival', 9, 0.56, 0.50], ['rival', 7, 0.64, 0.30], ['rival', 11, 0.64, 0.70],
      ],
      arrows: [[0.10, 0.50, 0.22, 0.38], [0.22, 0.38, 0.43, 0.50], [0.43, 0.50, 0.76, 0.22]],
      tags: ['salida de balón', 'tercer hombre', 'progresión'],
    },
    highPress: {
      label: 'Presión alta',
      players: [
        ['local', 9, 0.78, 0.50], ['local', 7, 0.70, 0.26], ['local', 11, 0.70, 0.74],
        ['local', 10, 0.61, 0.50], ['local', 8, 0.52, 0.36], ['local', 6, 0.48, 0.64],
        ['rival', 1, 0.90, 0.50], ['rival', 4, 0.80, 0.38], ['rival', 5, 0.80, 0.62],
      ],
      arrows: [[0.78, 0.50, 0.88, 0.50], [0.70, 0.26, 0.80, 0.38], [0.70, 0.74, 0.80, 0.62], [0.61, 0.50, 0.80, 0.50]],
      tags: ['presión alta', 'orientar fuera', 'salto'],
    },
    midBlock: {
      label: 'Bloque medio',
      players: [
        ['local', 9, 0.62, 0.50], ['local', 7, 0.54, 0.22], ['local', 11, 0.54, 0.78],
        ['local', 8, 0.45, 0.36], ['local', 6, 0.42, 0.50], ['local', 10, 0.45, 0.64],
        ['local', 2, 0.32, 0.20], ['local', 4, 0.28, 0.40], ['local', 5, 0.28, 0.60], ['local', 3, 0.32, 0.80],
      ],
      zones: [[0.24, 0.18, 0.45, 0.64, 'rgba(250, 204, 21, 0.11)', 'Compacto']],
      tags: ['bloque medio', 'compactar', 'basculación'],
    },
    lowBlock: {
      label: 'Bloque bajo',
      players: [
        ['local', 1, 0.10, 0.50], ['local', 2, 0.22, 0.18], ['local', 4, 0.18, 0.38],
        ['local', 5, 0.18, 0.62], ['local', 3, 0.22, 0.82], ['local', 6, 0.32, 0.42],
        ['local', 8, 0.32, 0.58], ['local', 7, 0.38, 0.22], ['local', 11, 0.38, 0.78],
        ['local', 10, 0.46, 0.50], ['local', 9, 0.56, 0.50],
      ],
      zones: [[0.08, 0.12, 0.42, 0.76, 'rgba(239, 68, 68, 0.12)', 'Área protegida']],
      tags: ['bloque bajo', 'defender área', 'cerrar intervalos'],
    },
    transition: {
      label: 'Transición ofensiva',
      players: [
        ['local', 6, 0.42, 0.50], ['local', 8, 0.48, 0.36], ['local', 10, 0.56, 0.60],
        ['local', 7, 0.65, 0.22], ['local', 11, 0.65, 0.78], ['local', 9, 0.78, 0.50],
        ['rival', 4, 0.58, 0.42], ['rival', 5, 0.58, 0.58],
      ],
      arrows: [[0.42, 0.50, 0.56, 0.60], [0.56, 0.60, 0.78, 0.50], [0.65, 0.22, 0.84, 0.30], [0.65, 0.78, 0.84, 0.70]],
      tags: ['transición ofensiva', 'atacar espacio', 'primer pase'],
    },
    defensiveTransition: {
      label: 'Transición defensiva',
      players: [
        ['local', 8, 0.62, 0.35], ['local', 10, 0.64, 0.55], ['local', 6, 0.52, 0.50],
        ['local', 7, 0.76, 0.25], ['local', 11, 0.76, 0.75], ['rival', 10, 0.56, 0.50],
      ],
      arrows: [[0.62, 0.35, 0.52, 0.50], [0.64, 0.55, 0.52, 0.50], [0.76, 0.25, 0.62, 0.35], [0.76, 0.75, 0.64, 0.55]],
      tags: ['presión tras pérdida', 'cerrar dentro', 'repliegue'],
    },
    setPiece: {
      label: 'ABP ofensiva',
      players: [
        ['local', 7, 0.82, 0.18], ['local', 4, 0.78, 0.42], ['local', 5, 0.80, 0.58],
        ['local', 9, 0.88, 0.50], ['local', 10, 0.70, 0.68], ['rival', 1, 0.94, 0.50],
        ['rival', 4, 0.86, 0.42], ['rival', 5, 0.86, 0.58],
      ],
      arrows: [[0.82, 0.18, 0.88, 0.50], [0.78, 0.42, 0.72, 0.30], [0.80, 0.58, 0.88, 0.42]],
      tags: ['ABP ofensiva', 'bloqueo', 'zona de remate'],
    },
  };

  const applyTemplate = async (key) => {
    const cfg = templateMap[key];
    if (!cfg) return;
    const canvas = await waitForCanvas();
    add(canvas, makeText(canvas, cfg.label, 0.04, 0.04, { layer: 'labels' }));
    (cfg.zones || []).forEach((z) => add(canvas, makeZone(canvas, z[0], z[1], z[2], z[3], z[4], z[5], 'zones')));
    (cfg.players || []).forEach((p) => add(canvas, makePlayer(canvas, p[2], p[3], p[1], p[0], cfg.label)));
    (cfg.arrows || []).forEach((a) => add(canvas, makeArrow(canvas, a[0], a[1], a[2], a[3], '#38bdf8', false, 'movement')));
    if (cfg.tags && cfg.tags.length) {
      persist({ last_template: key, last_tags: cfg.tags, last_template_label: cfg.label });
    }
    requestRender(canvas);
    setStatus(`Plantilla aplicada: ${cfg.label}.`);
  };

  const addTags = async (tags) => {
    const canvas = await waitForCanvas();
    const list = (Array.isArray(tags) && tags.length ? tags : [
      'bloque bajo',
      'bloque medio',
      'bloque alto',
      'carril central',
      'half-space',
      '2v1',
      'tercer hombre',
      'presión tras pérdida',
      'cambio de orientación',
      'zona 14',
    ]).map((t) => safe(t)).filter(Boolean);
    add(canvas, makeText(canvas, `Etiquetas: ${list.join(' · ')}`, 0.04, 0.91, {
      width: canvasSize(canvas).w * 0.88,
      layer: 'labels',
      backgroundColor: 'rgba(15, 23, 42, 0.78)',
      fill: '#e0f2fe',
    }));
    persist({ last_tags: list });
    requestRender(canvas);
    setStatus('Etiquetas futbolísticas añadidas y guardadas para IA.');
  };

  const saveAiContext = async () => {
    const canvas = await waitForCanvas();
    const objects = canvas.getObjects().map((obj) => obj && obj.data ? obj.data : {}).filter((d) => d.ws_tactics_pro || d.token_kind);
    const state = readState();
    const payload = {
      version: 1,
      created_at: new Date().toISOString(),
      tags: state.last_tags || [],
      template: state.last_template_label || state.last_template || '',
      object_count: canvas.getObjects().length,
      tactical_objects: objects.slice(0, 120),
      training_goal: 'Interpretar bloque, carriles, superioridades, rutas y relación pizarra-video.',
    };
    try { window.localStorage.setItem(AI_KEY, JSON.stringify(payload)); } catch (e) { /* ignore */ }
    try { await navigator.clipboard.writeText(JSON.stringify(payload, null, 2)); } catch (e) { /* ignore */ }
    setStatus('Contexto IA guardado y copiado si el navegador lo permite.');
  };

  const addPlanRealityCompare = async () => {
    const canvas = await waitForCanvas();
    add(canvas, makeZone(canvas, 0.04, 0.08, 0.42, 0.82, 'rgba(34, 197, 94, 0.08)', 'Plan / pizarra', 'compare'));
    add(canvas, makeZone(canvas, 0.54, 0.08, 0.42, 0.82, 'rgba(14, 165, 233, 0.08)', 'Realidad / clip', 'compare'));
    add(canvas, makeText(canvas, 'Checklist: altura de bloque · carril ocupado · jugador libre · superioridad · siguiente pase · riesgo', 0.08, 0.84, {
      width: canvasSize(canvas).w * 0.82,
      layer: 'compare',
      fill: '#fef9c3',
      backgroundColor: 'rgba(2, 6, 23, 0.72)',
    }));
    requestRender(canvas);
    setStatus('Comparador plan vs realidad añadido.');
  };

  const openVideoLibrary = () => {
    const url = '/coach/analisis/?tab=videos&view=library';
    try { window.open(url, '_blank', 'noopener'); } catch (e) { window.location.href = url; }
    setStatus('Biblioteca de vídeo abierta para vincular clips reales.');
  };

  const openPresentation = () => {
    const btn = $('#task-focus-toggle');
    if (btn) btn.click();
    else document.body.classList.toggle('focus-mode', true);
    setStatus('Modo presentación abierto.');
  };

  const openPlaybookSave = () => {
    const btn = $('#tactics-save-clip-top') || $('#task-sim-clip-save');
    if (btn) btn.click();
    activatePane('playbook');
    setStatus('Guardar clip abierto. Usa fase, rival y etiquetas en nombre/carpeta/tags.');
  };

  const openExportPack = () => {
    activatePane('exportar');
    const pack = $('#task-playbook-export-pack');
    if (pack) pack.click();
    else ($('#export-png-hd') || $('#tactics-export-image-hq') || $('#export-png'))?.click();
    setStatus('Exportación preparada.');
  };

  const openAnimation = () => {
    activatePane('animacion');
    $('#task-step-add')?.click();
    setStatus('Escenario añadido para animación 2D/3D.');
  };

  const open3d = () => {
    $('#task-playbook-open-3d')?.click();
    setStatus('Vista 3D solicitada.');
  };

  const clickFirst = (selectors) => {
    const list = Array.isArray(selectors) ? selectors : [selectors];
    for (let i = 0; i < list.length; i += 1) {
      const el = $(list[i]);
      if (el) {
        el.click();
        return true;
      }
    }
    return false;
  };

  const setEasyAnimationMode = (enabled, options) => {
    const on = enabled !== false;
    const opts = options || {};
    document.body.classList.toggle('tactics-easy-animation', on);
    if (opts.persist === true) persist({ easy_animation: on });
    else if (!on) persist({ easy_animation: false });
    if (on) {
      clickFirst('#tactics-mode-interactive');
      window.setTimeout(() => {
        clickFirst(['#tactics-tool-route', '.tactics-interactive-dock [data-tactics-tool="route_move"]']);
      }, 80);
      setStatus('Animar fácil: selecciona una chapa, pulsa/arrastra hasta destino y usa ▶ para previsualizar.');
    } else {
      clickFirst('#tactics-mode-static');
      setStatus('Animar fácil desactivado.');
    }
  };

  const easyAnimationRoute = () => {
    setEasyAnimationMode(true);
    window.setTimeout(() => {
      clickFirst(['#tactics-tool-route', '.tactics-interactive-dock [data-tactics-tool="route_move"]']);
    }, 90);
  };

  const easyAnimationPlay = () => {
    setEasyAnimationMode(true);
    window.setTimeout(() => {
      clickFirst(['#tactics-tool-route-play', '.tactics-interactive-dock [data-tactics-tool="route_play"]']);
    }, 90);
  };

  const easyAnimationSequence = () => {
    setEasyAnimationMode(true);
    window.setTimeout(() => {
      clickFirst(['.tactics-interactive-dock [data-tactics-generate="seq"]', '[data-tactics-generate="seq"]']);
      activatePane('animacion');
    }, 120);
  };

  const easyAnimationSave = () => {
    setEasyAnimationMode(true);
    window.setTimeout(() => {
      clickFirst(['#tactics-save-clip-top', '#task-sim-clip-save']);
      activatePane('playbook');
    }, 120);
  };

  const easyAnimationOff = () => {
    setEasyAnimationMode(false);
  };

  const setFlowActive = (flow) => {
    const key = safe(flow || 'draw') || 'draw';
    $$('#tactics-flowbar [data-tactics-flow]').forEach((btn) => {
      const active = safe(btn.dataset.tacticsFlow) === key;
      btn.classList.toggle('is-active', active);
      try { btn.setAttribute('aria-pressed', active ? 'true' : 'false'); } catch (e) { /* ignore */ }
    });
  };

  const updateModeBadge = (label) => {
    const badge = $('#tactics-active-mode');
    if (!badge) return;
    badge.textContent = `Modo: ${safe(label || 'Dibujar') || 'Dibujar'}`;
  };

  const runTacticsFlow = (flow) => {
    const key = safe(flow || 'draw') || 'draw';
    setFlowActive(key);
    if (key === 'animate') {
      updateModeBadge('Animar');
      setEasyAnimationMode(true);
      return;
    }
    if (key === 'task') {
      setEasyAnimationMode(false);
      updateModeBadge('Crear tarea');
      activatePane('tacticalpro');
      setStatus('Crear tarea: dibuja la situación y usa Guardar como... > Tarea de entrenamiento.');
      return;
    }
    if (key === 'present') {
      setEasyAnimationMode(false);
      updateModeBadge('Presentar');
      openPresentation();
      setStatus('Preparar charla: añade llamadas, guarda pack o exporta captura.');
      return;
    }
    updateModeBadge('Dibujar');
    setEasyAnimationMode(false);
    clickFirst('#tactics-mode-static');
    setStatus('Dibujar jugada: usa fichas, balón, flechas, carriles y zonas.');
  };

  const bindFlowbar = () => {
    const flowbar = $('#tactics-flowbar');
    if (!flowbar || flowbar.dataset.bound === '1') return;
    flowbar.dataset.bound = '1';
    flowbar.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-tactics-flow]');
      if (!btn) return;
      event.preventDefault();
      runTacticsFlow(btn.dataset.tacticsFlow);
    });
  };

  const bindModeBadge = () => {
    if (document.body.dataset.tacticsModeBadgeBound === '1') return;
    document.body.dataset.tacticsModeBadgeBound = '1';
    document.addEventListener('click', (event) => {
      const target = event.target.closest('[data-tactics-tool], [data-tactics-board], [data-tactics-generate], #tactics-overlays-open, #tactics-zones-open');
      if (!target) return;
      const board = safe(target.dataset.tacticsBoard);
      const tool = safe(target.dataset.tacticsTool);
      const gen = safe(target.dataset.tacticsGenerate);
      if (board === 'interactive') updateModeBadge('Interactiva');
      else if (board === 'static') updateModeBadge('Dibujar');
      else if (tool === 'player_local') updateModeBadge('Jugador local');
      else if (tool === 'player_rival') updateModeBadge('Jugador rival');
      else if (tool === 'ball') updateModeBadge('Balón');
      else if (tool === 'arrow_solid') updateModeBadge('Flecha');
      else if (tool === 'text') updateModeBadge('Texto');
      else if (tool === 'route_move') updateModeBadge('Ruta');
      else if (tool === 'route_play') updateModeBadge('Reproducir');
      else if (gen) updateModeBadge('Secuencia');
      else if (target.id === 'tactics-overlays-open') updateModeBadge('Carriles');
      else if (target.id === 'tactics-zones-open') updateModeBadge('Zonas');
    }, true);
  };

  const addVideoBoardSync = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Vídeo + pizarra sincronizada', [
      'Clip: selecciona desde Biblioteca',
      '00:00 Fase 1 · inicio',
      '00:04 Fase 2 · ventaja',
      '00:08 Fase 3 · corrección',
    ], 0.05, 0.08, 0.36, 0.22, 'sync', 'rgba(14, 165, 233, 0.16)'));
    add(canvas, makeArrow(canvas, 0.44, 0.19, 0.58, 0.19, '#38bdf8', true, 'sync'));
    savePlusPayload({ video_board_sync: true });
    requestRender(canvas);
    setStatus('Plantilla de sincronización vídeo-pizarra añadida.');
  };

  const addClubPrinciples = async () => {
    const canvas = await waitForCanvas();
    const principles = [
      'Presionar fuera',
      'Lateral salta con cobertura',
      'Pivote protege intervalo',
      'Cerrar pase interior',
      'Atacar lado débil',
      'Primer pase tras robo',
    ];
    add(canvas, addBoardCard(canvas, 'Principios del club', principles.map((p) => `· ${p}`), 0.62, 0.07, 0.32, 0.30, 'labels', 'rgba(34, 197, 94, 0.13)'));
    savePlusPayload({ club_principles: principles });
    requestRender(canvas);
    setStatus('Banco de principios del club añadido.');
  };

  const addPlayerCorrections = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Correcciones por jugador', [
      '#2 temporiza antes de saltar',
      '#6 perfilado para ver espalda',
      '#8 cerrar línea de pase',
      '#9 orientar presión',
    ], 0.05, 0.67, 0.40, 0.24, 'player_view', 'rgba(168, 85, 247, 0.13)'));
    add(canvas, makeText(canvas, 'Vista individual: compartir solo consignas del jugador seleccionado', 0.50, 0.88, {
      width: canvasSize(canvas).w * 0.42,
      layer: 'player_view',
      fill: '#f5d0fe',
    }));
    savePlusPayload({ player_corrections: true });
    requestRender(canvas);
    setStatus('Correcciones por jugador añadidas.');
  };

  const addTacticalTimeline = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Timeline táctico', [
      '1 · Preparar: atraer presión',
      '2 · Progresar: tercer hombre',
      '3 · Acelerar: atacar espalda',
      '4 · Finalizar: ocupar área',
    ], 0.05, 0.39, 0.43, 0.23, 'timeline', 'rgba(250, 204, 21, 0.13)'));
    add(canvas, makeArrow(canvas, 0.10, 0.57, 0.42, 0.57, '#facc15', false, 'timeline'));
    savePlusPayload({ tactical_timeline: true });
    requestRender(canvas);
    setStatus('Timeline táctico añadido.');
  };

  const addTalkPack = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Pack charla vestuario', [
      '1. Problema detectado',
      '2. Principio del club',
      '3. Clip real',
      '4. Pizarra corregida',
      '5. Tarea de entrenamiento',
    ], 0.54, 0.39, 0.40, 0.26, 'talk', 'rgba(20, 184, 166, 0.13)'));
    savePlusPayload({ talk_pack: true });
    requestRender(canvas);
    setStatus('Pack para charla creado.');
  };

  const addRivalLibraryCard = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Biblioteca por rival', [
      'Salida: patrón principal',
      'Presión: trigger de salto',
      'ABP: zona fuerte',
      'Debilidad: lado débil',
      'Jugador clave: perfil y pie dominante',
    ], 0.55, 0.67, 0.39, 0.24, 'rival', 'rgba(239, 68, 68, 0.13)'));
    savePlusPayload({ rival_library: true });
    requestRender(canvas);
    setStatus('Ficha de biblioteca por rival añadida.');
  };

  const addMatchComparator = async () => {
    const canvas = await waitForCanvas();
    add(canvas, makeZone(canvas, 0.05, 0.08, 0.26, 0.26, 'rgba(14, 165, 233, 0.10)', 'Partido A', 'match_compare'));
    add(canvas, makeZone(canvas, 0.37, 0.08, 0.26, 0.26, 'rgba(34, 197, 94, 0.10)', 'Partido B', 'match_compare'));
    add(canvas, makeZone(canvas, 0.69, 0.08, 0.26, 0.26, 'rgba(250, 204, 21, 0.10)', 'Patrón repetido', 'match_compare'));
    add(canvas, makeText(canvas, 'Comparador: mismo concepto en varios partidos · frecuencia · corrección', 0.08, 0.31, {
      width: canvasSize(canvas).w * 0.84,
      layer: 'match_compare',
      fill: '#fef9c3',
    }));
    savePlusPayload({ match_comparator: true });
    requestRender(canvas);
    setStatus('Comparador entre partidos añadido.');
  };

  const addAnalysisChecklist = async () => {
    const canvas = await waitForCanvas();
    const lastTags = readState().last_tags || [];
    add(canvas, addBoardCard(canvas, 'Checklist análisis', [
      `Fase: ${lastTags[0] || 'definir'}`,
      'Bloque: bajo / medio / alto',
      'Carril: exterior / half-space / central',
      'Superioridad: 2v1 / 3v2 / libre',
      'Riesgo: espalda / intervalo / rechace',
      'Solución: pase / conducción / pausa',
    ], 0.08, 0.10, 0.42, 0.35, 'checklist', 'rgba(59, 130, 246, 0.13)'));
    savePlusPayload({ analysis_checklist: true });
    requestRender(canvas);
    setStatus('Checklist de análisis añadido.');
  };

  const convertToTrainingTask = async () => {
    const canvas = await waitForCanvas();
    add(canvas, addBoardCard(canvas, 'Convertir en entrenamiento', [
      'Objetivo: reproducir situación del partido',
      'Espacio: carril + zona de finalización',
      'Regla: punto extra si aparece tercer hombre',
      'Corrección: perfil corporal y timing',
    ], 0.08, 0.49, 0.42, 0.25, 'training', 'rgba(34, 197, 94, 0.14)'));
    $('#tactics-save-task-top')?.click();
    savePlusPayload({ training_task: true });
    requestRender(canvas);
    setStatus('Bloque de tarea de entrenamiento añadido; guardado como tarea solicitado.');
  };

  const addPlayerView = async () => {
    const canvas = await waitForCanvas();
    add(canvas, makeZone(canvas, 0.56, 0.47, 0.36, 0.38, 'rgba(168, 85, 247, 0.11)', 'Vista jugador', 'player_view'));
    add(canvas, makeText(canvas, 'Jugador: clips asignados · corrección individual · consigna · fecha revisión', 0.59, 0.54, {
      width: canvasSize(canvas).w * 0.30,
      layer: 'player_view',
      fill: '#f5d0fe',
    }));
    openVideoLibrary();
    savePlusPayload({ player_view: true });
    requestRender(canvas);
    setStatus('Vista jugador preparada y biblioteca abierta.');
  };

  const bindAction = (root) => {
    root.addEventListener('click', async (event) => {
      const btn = event.target.closest('[data-tactics-pro]');
      if (!btn) return;
      event.preventDefault();
      const action = safe(btn.dataset.tacticsPro);
      try {
        if (action.startsWith('template:')) await applyTemplate(action.split(':')[1]);
        else if (action === 'channels') await addChannels();
        else if (action.startsWith('block:')) await addBlockReference(action.split(':')[1]);
        else if (action === 'tags') await addTags();
        else if (action === 'ai') await saveAiContext();
        else if (action === 'compare') await addPlanRealityCompare();
        else if (action === 'video') openVideoLibrary();
        else if (action === 'present') openPresentation();
        else if (action === 'save') openPlaybookSave();
        else if (action === 'export') openExportPack();
        else if (action === 'animation') openAnimation();
        else if (action === '3d') open3d();
        else if (action === 'easy-animate') setEasyAnimationMode(true);
        else if (action === 'easy-route') easyAnimationRoute();
        else if (action === 'easy-play') easyAnimationPlay();
        else if (action === 'easy-seq') easyAnimationSequence();
        else if (action === 'easy-save') easyAnimationSave();
        else if (action === 'easy-off') easyAnimationOff();
        else if (action === 'sync') await addVideoBoardSync();
        else if (action === 'principles') await addClubPrinciples();
        else if (action === 'corrections') await addPlayerCorrections();
        else if (action === 'timeline') await addTacticalTimeline();
        else if (action === 'talkpack') await addTalkPack();
        else if (action === 'rival-library') await addRivalLibraryCard();
        else if (action === 'match-compare') await addMatchComparator();
        else if (action === 'checklist') await addAnalysisChecklist();
        else if (action === 'training') await convertToTrainingTask();
        else if (action === 'player-view') await addPlayerView();
        else if (action === 'clear') await clearProLayer('');
        else if (action === 'clear-channels') await clearProLayer('channels');
      } catch (err) {
        setStatus(err && err.message ? err.message : 'No se pudo aplicar la acción.', true);
      }
    });
  };

  const panelHtml = () => `
    <div class="section tactics-pro-console" id="tactics-pro-console">
      <div class="tactics-pro-head">
        <div>
          <h3>Tactical Pro</h3>
          <p>Plantillas, capas, presentación, IA, vídeo y exportación.</p>
        </div>
        <button type="button" class="button ghost" data-tactics-pro="clear">Limpiar PRO</button>
      </div>

      <div class="tactics-pro-block">
        <h4>Animación simple</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="easy-animate">Animar fácil</button>
          <button type="button" data-tactics-pro="easy-route">Crear ruta</button>
          <button type="button" data-tactics-pro="easy-play">Reproducir</button>
          <button type="button" data-tactics-pro="easy-seq">Crear secuencia</button>
          <button type="button" data-tactics-pro="easy-save">Guardar animación</button>
          <button type="button" data-tactics-pro="easy-off">Salir animación</button>
        </div>
      </div>

      <div class="tactics-pro-block">
        <h4>Plantillas rápidas</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="template:build433">Salida 4-3-3</button>
          <button type="button" data-tactics-pro="template:highPress">Presión alta</button>
          <button type="button" data-tactics-pro="template:midBlock">Bloque medio</button>
          <button type="button" data-tactics-pro="template:lowBlock">Bloque bajo</button>
          <button type="button" data-tactics-pro="template:transition">Transición OF</button>
          <button type="button" data-tactics-pro="template:defensiveTransition">Transición DEF</button>
          <button type="button" data-tactics-pro="template:setPiece">ABP ofensiva</button>
        </div>
      </div>

      <div class="tactics-pro-block">
        <h4>Capas tácticas</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="channels">Carriles + tercios</button>
          <button type="button" data-tactics-pro="block:low">Referencia bajo</button>
          <button type="button" data-tactics-pro="block:mid">Referencia medio</button>
          <button type="button" data-tactics-pro="block:high">Referencia alto</button>
          <button type="button" data-tactics-pro="clear-channels">Quitar carriles</button>
        </div>
      </div>

      <div class="tactics-pro-block">
        <h4>Flujo entrenador</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="animation">Animación 2D</button>
          <button type="button" data-tactics-pro="3d">Vista 3D</button>
          <button type="button" data-tactics-pro="present">Presentación</button>
          <button type="button" data-tactics-pro="save">Guardar Playbook</button>
          <button type="button" data-tactics-pro="export">Exportar pack</button>
          <button type="button" data-tactics-pro="video">Clips reales</button>
        </div>
      </div>

      <div class="tactics-pro-block">
        <h4>IA y evaluación</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="tags">Etiquetas fútbol</button>
          <button type="button" data-tactics-pro="compare">Plan vs realidad</button>
          <button type="button" data-tactics-pro="ai">Guardar contexto IA</button>
        </div>
      </div>

      <div class="tactics-pro-block">
        <h4>Plus</h4>
        <div class="tactics-pro-grid">
          <button type="button" data-tactics-pro="sync">Vídeo + pizarra</button>
          <button type="button" data-tactics-pro="principles">Principios club</button>
          <button type="button" data-tactics-pro="corrections">Correcciones jugador</button>
          <button type="button" data-tactics-pro="timeline">Timeline táctico</button>
          <button type="button" data-tactics-pro="talkpack">Pack charla</button>
          <button type="button" data-tactics-pro="rival-library">Biblioteca rival</button>
          <button type="button" data-tactics-pro="match-compare">Comparar partidos</button>
          <button type="button" data-tactics-pro="checklist">Checklist análisis</button>
          <button type="button" data-tactics-pro="training">Pasar a entreno</button>
          <button type="button" data-tactics-pro="player-view">Vista jugador</button>
        </div>
      </div>
    </div>
  `;

  const inject = () => {
    const tabs = $('#task-side-tabs');
    if (!tabs || $('#tactics-pro-console')) return;
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'side-tab';
    tab.dataset.pane = 'tacticalpro';
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', 'false');
    tab.innerHTML = '<span class="tab-emoji" aria-hidden="true">PRO</span><span class="tab-label">Tactical Pro</span>';
    tabs.appendChild(tab);

    const pane = document.createElement('div');
    pane.className = 'side-pane';
    pane.dataset.pane = 'tacticalpro';
    pane.setAttribute('role', 'tabpanel');
    pane.innerHTML = panelHtml();
    const exportPane = $('.side-pane[data-pane="exportar"]');
    if (exportPane && exportPane.parentNode) exportPane.parentNode.insertBefore(pane, exportPane);
    else tabs.insertAdjacentElement('afterend', pane);
    bindAction(pane);

    const dock = document.createElement('div');
    dock.className = 'tactics-easy-anim-dock';
    dock.setAttribute('aria-label', 'Animación fácil');
    dock.innerHTML = `
      <strong>Animar fácil</strong>
      <button type="button" data-tactics-pro="easy-route">Ruta</button>
      <button type="button" data-tactics-pro="easy-play">▶</button>
      <button type="button" data-tactics-pro="easy-seq">Secuencia</button>
      <button type="button" data-tactics-pro="easy-save">Guardar</button>
      <button type="button" data-tactics-pro="easy-off">Salir</button>
    `;
    document.body.appendChild(dock);
    bindAction(dock);

    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'surface-trigger tactics-chip';
    chip.id = 'tactics-pro-open';
    chip.textContent = 'Tactical Pro';
    chip.title = 'Plantillas, IA, comparador y flujo de presentación';
    chip.addEventListener('click', () => activatePane('tacticalpro'));
    const quickbar = $('#tactics-quickbar');
    if (quickbar) quickbar.appendChild(chip);

    const animChip = document.createElement('button');
    animChip.type = 'button';
    animChip.className = 'surface-trigger tactics-chip';
    animChip.id = 'tactics-easy-animate-open';
    animChip.textContent = 'Animar fácil';
    animChip.title = 'Activa rutas y controles mínimos para animar chapas';
    animChip.addEventListener('click', () => setEasyAnimationMode(true));
    if (quickbar) quickbar.appendChild(animChip);

    bindFlowbar();
    bindModeBadge();

    const params = new URL(window.location.href).searchParams;
    if (params.get('pane') === 'tacticalpro' || params.get('pro') === '1') {
      window.setTimeout(() => activatePane('tacticalpro'), 100);
    }
    if (params.get('anim') === 'easy') {
      window.setTimeout(() => setEasyAnimationMode(true, { persist: false }), 220);
    } else {
      // Evita que una sesión anterior deje la pizarra bloqueada en Interactiva/Ruta.
      persist({ easy_animation: false });
    }

    document.addEventListener('click', (event) => {
      try {
        if (!document.body.classList.contains('tactics-easy-animation')) return;
        const target = event.target;
        if (!target || !target.closest) return;
        if (target.closest('.tactics-easy-anim-dock') || target.closest('#tactics-pro-console')) return;
        if (target.closest('.resource-panel button') || target.closest('.player-bank button') || target.closest('[data-add]')) {
          setEasyAnimationMode(false);
        }
      } catch (e) {
        /* ignore */
      }
    }, true);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject, { once: true });
  } else {
    inject();
  }
  waitForCanvas(120).then(() => setStatus('Tactical Pro listo.')).catch(() => {});
})();
