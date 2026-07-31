/*
 * Papel cebolla: el fantasma del paso ANTERIOR mientras dibujas el siguiente.
 *
 * Sin esto, al preparar el paso 2 no ves donde estaban las fichas en el paso 1 y trabajas a
 * ciegas: hay que recordar las posiciones o calcularlas. Es la diferencia entre poder dibujar una
 * secuencia y no poder.
 *
 * Va en un canvas APARTE, por debajo del lienzo de Fabric y por encima del cesped. Asi no toca el
 * estado del editor: los fantasmas no son objetos de Fabric, no se pueden seleccionar, no se
 * guardan y no pueden colarse en el dibujo por accidente.
 *
 * API (la usa sessions_tactical_pad.js al cambiar de paso):
 *   window.__tpadOnionSkin.render(canvasStateAnterior, {width, height})
 *   window.__tpadOnionSkin.clear()
 */
(() => {
  'use strict';

  const TAU = Math.PI * 2;
  const ID = 'task-onion-canvas';

  const num = (v, d = 0) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : d;
  };

  const text = (v, d = '') => {
    const s = (v === null || v === undefined) ? '' : String(v).trim();
    return s || d;
  };

  /* Centro del objeto en coordenadas del lienzo de origen. Mismo criterio que usan el visor 3D y
     el derivador del guion en Python: Fabric guarda left/top respecto a su origen, que puede ser
     el centro o una esquina. */
  const center = (obj) => {
    const w = num(obj.width) * num(obj.scaleX, 1);
    const h = num(obj.height) * num(obj.scaleY, 1);
    let x = num(obj.left);
    let y = num(obj.top);
    const ox = text(obj.originX, 'center').toLowerCase();
    const oy = text(obj.originY, 'center').toLowerCase();
    if (ox === 'left') x += w / 2; else if (ox === 'right') x -= w / 2;
    if (oy === 'top') y += h / 2; else if (oy === 'bottom') y -= h / 2;
    return { x, y, r: Math.max(w, h) / 2 || 20 };
  };

  const isToken = (obj) => {
    const data = (obj && typeof obj.data === 'object') ? obj.data : {};
    const kind = text(data.kind || data.token_kind).toLowerCase().replace(/-/g, '_');
    return kind.startsWith('player') || kind.startsWith('goalkeeper')
      || kind === 'token' || kind === 'ball' || kind === 'ball_token';
  };

  /* El fantasma va DENTRO del contenedor de Fabric, no del escenario.
     El escenario incluye el decorado de la superficie (marco de estadio, vallas, porterias) y
     segun la superficie elegida -2D plano, cesped natural, media cancha, vertical- el lienzo no
     tiene por que llenarlo: puede quedar centrado con bandas. Anclado al escenario, el fantasma se
     estiraria respecto a las fichas de verdad y marcaria posiciones que no son. Anclado al
     contenedor del lienzo, comparte exactamente el mismo rectangulo que Fabric, sea cual sea la
     superficie. Va como primer hijo, asi que las dos capas de Fabric lo tapan por orden del DOM:
     el fantasma queda debajo de las fichas reales sin tocar sus z-index. */
  const ensureCanvas = () => {
    const host = document.querySelector('#task-pitch-stage .canvas-container')
      || document.querySelector('.canvas-container');
    if (!host) return null;
    let el = document.getElementById(ID);
    if (!el) {
      el = document.createElement('canvas');
      el.id = ID;
      el.setAttribute('aria-hidden', 'true');
      // Sin capturar el raton: es una guia, no un objeto.
      el.style.cssText = 'position:absolute; left:0; top:0; width:100%; height:100%; pointer-events:none;';
    }
    if (el.parentElement !== host) host.insertBefore(el, host.firstChild);
    return el;
  };

  const clear = () => {
    const el = document.getElementById(ID);
    if (!el) return;
    const ctx = el.getContext('2d');
    if (ctx) ctx.clearRect(0, 0, el.width, el.height);
  };

  const render = (state, opts) => {
    clear();
    if (!state || typeof state !== 'object') return;
    const objects = Array.isArray(state.objects) ? state.objects : [];
    if (!objects.length) return;

    const el = ensureCanvas();
    if (!el) return;
    // Mismo rectangulo que el lienzo de Fabric: ver ensureCanvas.
    const rect = el.parentElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const srcW = num((opts || {}).width) || num(state.width) || rect.width;
    const srcH = num((opts || {}).height) || num(state.height) || rect.height;
    if (srcW <= 0 || srcH <= 0) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width = Math.round(rect.width * dpr);
    el.height = Math.round(rect.height * dpr);
    const ctx = el.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const kx = rect.width / srcW;
    const ky = rect.height / srcH;

    // Una ficha ocupa una fraccion pequena del campo. Hay objetos guardados con un tamano
    // disparatado (grupos serializados con la caja de todo el lienzo), y pintarlos a su escala
    // llenaba el campo de manchas y numeros gigantes: el fantasma tapaba justo lo que ayuda a ver.
    const rMax = Math.min(rect.width, rect.height) * 0.075;

    objects.forEach((obj) => {
      if (!obj || typeof obj !== 'object' || !isToken(obj)) return;
      const c = center(obj);
      const x = c.x * kx;
      const y = c.y * ky;
      const r = Math.min(rMax, Math.max(6, c.r * Math.min(kx, ky)));
      const data = (typeof obj.data === 'object' && obj.data) ? obj.data : {};

      ctx.save();
      // Contorno discontinuo y translucido: tiene que leerse como "aqui ESTABA", no como una
      // ficha mas. Relleno muy tenue para no competir con las fichas de verdad.
      ctx.globalAlpha = 0.42;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.fillStyle = text(data.token_base_color, '#94a3b8');
      ctx.globalAlpha = 0.16;
      ctx.fill();
      ctx.globalAlpha = 0.6;
      ctx.setLineDash([Math.max(3, r * 0.32), Math.max(3, r * 0.26)]);
      ctx.lineWidth = Math.max(1.4, r * 0.13);
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();

      const label = text(data.playerNumber || data.label).slice(0, 3);
      if (label) {
        ctx.setLineDash([]);
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = '#ffffff';
        ctx.font = `800 ${Math.round(r * 0.95)}px system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x, y);
      }
      ctx.restore();
    });
  };

  // Al redimensionar el campo hay que repintar: el fantasma se dibuja en pixeles del escenario,
  // no del lienzo de origen, asi que si cambia el tamano se desalinea.
  let ultimo = null;
  window.__tpadOnionSkin = {
    render: (state, opts) => { ultimo = { state, opts }; render(state, opts); },
    clear: () => { ultimo = null; clear(); },
  };
  window.addEventListener('resize', () => { if (ultimo) render(ultimo.state, ultimo.opts); }, { passive: true });
})();
