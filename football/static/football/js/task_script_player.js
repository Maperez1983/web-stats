/*
 * Reproductor del GUION de una tarea.
 *
 * Lee `tactical_layout.task_layout_light.script` (ver football/task_script.py) y anima el
 * movimiento sobre un campo dibujado a mano. Nada de Fabric ni de Three: el guion trae posiciones
 * normalizadas 0..1, asi que pintar es una regla de tres.
 *
 * Por que un reproductor nuevo y no reutilizar task_simulation_share.js (1.316 lineas): aquel lee
 * el formato viejo (un lienzo Fabric entero por paso) y adaptarlo era mas arriesgado que escribir
 * esto. Este es el renderizador que van a compartir la ficha, el portal del jugador y la captura
 * de GIF, asi que conviene que sea pequeno y legible.
 *
 * Uso:
 *   <div data-task-script-player data-script-id="mi-json"></div>
 *   {{ script|json_script:"mi-json" }}
 */
(() => {
  'use strict';

  const TAU = Math.PI * 2;

  const num = (value, fallback = 0) => {
    const out = Number(value);
    return Number.isFinite(out) ? out : fallback;
  };

  // Suavizado en la entrada y la salida: un jugador no arranca ni frena de golpe.
  const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  /* Punto del recorrido en el instante t (0..1), repartiendo por longitud real de cada tramo
     para que la ficha no acelere en los tramos cortos. */
  const samplePath = (points, t) => {
    if (!Array.isArray(points) || !points.length) return null;
    if (points.length === 1) return { x: points[0][0], y: points[0][1] };
    const segments = [];
    let total = 0;
    for (let i = 1; i < points.length; i += 1) {
      const dx = points[i][0] - points[i - 1][0];
      const dy = points[i][1] - points[i - 1][1];
      const len = Math.hypot(dx, dy) || 0.0001;
      segments.push(len);
      total += len;
    }
    let target = Math.max(0, Math.min(1, t)) * total;
    for (let i = 0; i < segments.length; i += 1) {
      if (target <= segments[i]) {
        const k = segments[i] ? target / segments[i] : 0;
        return {
          x: points[i][0] + (points[i + 1][0] - points[i][0]) * k,
          y: points[i][1] + (points[i + 1][1] - points[i][1]) * k,
        };
      }
      target -= segments[i];
    }
    const last = points[points.length - 1];
    return { x: last[0], y: last[1] };
  };

  /* El campo lo pinta el MISMO renderizador que la pizarra (pitch_surface_25d.js), con el preset,
     la orientacion y el cesped que dice el guion. Antes este reproductor dibujaba su propio campo
     verde a franjas: dos aspectos para el mismo tablero hacen que parezca otro programa. */
  const pitchImageCache = new Map();

  const pitchImage = (pitch) => {
    const preset = String(pitch?.preset || 'full_pitch');
    const orientation = String(pitch?.orientation || 'landscape');
    /* Un SVG cargado como <img> NO puede traerse imagenes externas, y el cesped "2D plano" es
       justo eso: una foto referenciada dentro del SVG. Por eso salia el campo en blanco. Para
       rasterizar existe `flat_export`: el mismo verde a franjas dibujado en SVG puro. Es el mismo
       cambio que ya se hizo para la miniatura de la ficha y el PDF. */
    const grassRaw = String(pitch?.grass || 'flat_2d');
    const grass = grassRaw === 'flat_2d' ? 'flat_export' : grassRaw;
    const key = `${preset}|${orientation}|${grass}`;
    if (pitchImageCache.has(key)) return pitchImageCache.get(key);
    let img = null;
    try {
      const api = window.WebstatsPitch25D;
      if (api && typeof api.buildPitchSvg === 'function') {
        const svg = api.buildPitchSvg(preset, orientation, grass);
        if (svg) {
          img = new Image();
          img.decoding = 'async';
          img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
        }
      }
    } catch (e) { img = null; }
    pitchImageCache.set(key, img);
    return img;
  };

  // Respaldo sobrio por si el renderizador no ha cargado: verde liso, sin inventarse un estilo.
  const drawPitchFallback = (ctx, w, h) => {
    ctx.fillStyle = '#2f7d32';
    ctx.fillRect(0, 0, w, h);
  };

  const actorImageCache = new Map();

  const actorImage = (url) => {
    if (!url) return null;
    if (actorImageCache.has(url)) return actorImageCache.get(url);
    const img = new Image();
    img.decoding = 'async';
    // Mismo origen que la pizarra: el navegador suele traerla ya cacheada.
    img.src = url;
    actorImageCache.set(url, img);
    return img;
  };

  /* Cada figura se recorta y se escala UNA vez a su tamano. Escalar 22 PNG grandes en cada
     fotograma es lo que hace que una animacion se arrastre. */
  const spriteCache = new Map();

  const actorSprite = (url, radius) => {
    const img = actorImage(url);
    if (!img || !img.complete || !img.naturalWidth) return null;
    const lado = Math.max(8, Math.round(radius * 2));
    const clave = `${url}|${lado}`;
    if (spriteCache.has(clave)) return spriteCache.get(clave);
    let off = null;
    try {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      off = document.createElement('canvas');
      off.width = Math.round(lado * dpr);
      off.height = Math.round(lado * dpr);
      const octx = off.getContext('2d');
      octx.setTransform(dpr, 0, 0, dpr, 0, 0);
      octx.beginPath();
      octx.arc(lado / 2, lado / 2, lado / 2, 0, TAU);
      octx.clip();
      octx.drawImage(img, 0, 0, lado, lado);
    } catch (e) { off = null; }
    spriteCache.set(clave, off);
    return off;
  };

  const drawActor = (ctx, actor, pos, w, h, radius) => {
    const x = pos.x * w;
    const y = pos.y * h;
    if (actor.kind === 'ball') {
      ctx.beginPath();
      ctx.arc(x, y, radius * 0.45, 0, TAU);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = 'rgba(15,23,42,0.75)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      return;
    }
    // Sombra: la misma pista de profundidad que usa la chapa en el editor.
    ctx.beginPath();
    ctx.arc(x, y + radius * 0.16, radius, 0, TAU);
    ctx.fillStyle = 'rgba(2,6,23,0.28)';
    ctx.fill();

    const ficha = actorSprite(actor.img, radius);
    const listo = !!ficha;
    if (listo) {
      // La figura del jugador, ya recortada y a su tamano: por fotograma solo se copia.
      ctx.drawImage(ficha, x - radius, y - radius, radius * 2, radius * 2);
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, TAU);
      ctx.strokeStyle = actor.color || 'rgba(255,255,255,0.92)';
      ctx.lineWidth = Math.max(1.6, radius * 0.16);
      ctx.stroke();
    } else {
      // Sin figura (o mientras carga): disco con su color, que es lo que hace la pizarra tambien.
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, TAU);
      ctx.fillStyle = actor.color || '#2f6fd6';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.92)';
      ctx.lineWidth = Math.max(1.4, radius * 0.14);
      ctx.stroke();
    }

    const label = String(actor.label || '').slice(0, 3);
    if (label) {
      // El dorsal SIEMPRE encima y legible: a este tamano es lo unico que identifica de un vistazo.
      const rr = radius * 0.62;
      const cy = listo ? y + radius * 0.52 : y;
      if (listo) {
        ctx.beginPath();
        ctx.arc(x, cy, rr, 0, TAU);
        ctx.fillStyle = 'rgba(9,15,26,0.82)';
        ctx.fill();
      }
      ctx.fillStyle = '#ffffff';
      ctx.font = `800 ${Math.round(rr * 1.15)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, x, cy);
    }
  };

  const mount = (host) => {
    let script = null;
    try {
      const src = document.getElementById(host.dataset.scriptId || '');
      script = src ? JSON.parse(src.textContent || '{}') : null;
    } catch (e) { script = null; }
    const steps = Array.isArray(script?.steps) ? script.steps : [];
    const actors = Array.isArray(script?.actors) ? script.actors : [];
    // Con un solo paso no hay movimiento que reproducir: se calla en vez de ofrecer un play que
    // no hace nada. La tarea ya tiene su foto de la pizarra encima.
    if (steps.length < 2 || !actors.length) return;

    /* La chapa del editor va incrustada en el dibujo (~127 KB por jugador): no cabe en el guion,
       asi que se pide a la tarea, que ya la tiene guardada. Es el MISMO byte que pinta la pizarra. */
    const plantillaImg = String(host.dataset.tokenImgBase || '');
    actors.forEach((a) => {
      if (!a.img && a.img_embedded && plantillaImg && a.uid) {
        a.img = plantillaImg.replace('UID', encodeURIComponent(a.uid));
      }
    });

    const actorById = new Map(actors.map((a) => [a.uid, a]));
    // Las figuras llegan por red: cuando cada una carga se repinta, para no dejar discos de color
    // en una tarea que si tiene chapas.
    let repintar = null;
    actors.forEach((a) => {
      const img = actorImage(a.img);
      if (img && !img.complete) img.addEventListener('load', () => { try { repintar && repintar(); } catch (e) {} }, { once: true });
    });

    host.innerHTML = `
      <canvas class="tsp-canvas"></canvas>
      <div class="tsp-bar">
        <button type="button" class="tsp-play" aria-label="Reproducir">▶</button>
        <span class="tsp-step"></span>
        <input class="tsp-seek" type="range" min="0" max="1000" value="0" aria-label="Momento" />
      </div>`;
    const canvas = host.querySelector('.tsp-canvas');
    const playBtn = host.querySelector('.tsp-play');
    const stepLabel = host.querySelector('.tsp-step');
    const seek = host.querySelector('.tsp-seek');
    const ctx = canvas.getContext('2d');

    const totalSeconds = steps.reduce((acc, s) => acc + Math.max(1, num(s.duration, 3)), 0);
    let elapsed = 0;
    let playing = false;
    let last = 0;

    const sizeCanvas = () => {
      const rect = host.getBoundingClientRect();
      const cssW = Math.max(240, rect.width || 640);
      // Acotado: en pantalla ancha un campo a 0.62 se comia media ficha y empujaba el documento
      // fuera de la vista. La tarea se lee mejor si el movimiento y el texto caben juntos.
      const cssH = Math.round(Math.min(cssW * 0.62, 420));
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      canvas.style.width = `${cssW}px`;
      canvas.style.height = `${cssH}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w: cssW, h: cssH };
    };

    /* Instante global -> (paso, t dentro del paso). Se guarda tambien el paso anterior porque el
       movimiento entre pasos es una interpolacion: sin el, las fichas darian saltos. */
    const locate = (seconds) => {
      let acc = 0;
      for (let i = 0; i < steps.length; i += 1) {
        const dur = Math.max(1, num(steps[i].duration, 3));
        if (seconds < acc + dur || i === steps.length - 1) {
          return { index: i, t: Math.max(0, Math.min(1, (seconds - acc) / dur)) };
        }
        acc += dur;
      }
      return { index: 0, t: 0 };
    };

    /* El cesped es un SVG grande (puede llevar la foto del cesped dentro). Dibujarlo en cada
       fotograma congelaba la pagina: se rasteriza UNA vez por tamano en un lienzo aparte y por
       fotograma solo se copia, que es una operacion plana. */
    let fondo = null;
    let fondoClave = '';
    const fondoPara = (w, h) => {
      const campo = pitchImage(script.pitch);
      if (!campo) return null;
      if (!(campo.complete && campo.naturalWidth)) {
        if (!campo.__reintento) {
          campo.__reintento = true;
          campo.addEventListener('load', () => { try { fondoClave = ''; render(); } catch (e) {} }, { once: true });
        }
        return null;
      }
      const clave = `${Math.round(w)}x${Math.round(h)}`;
      if (fondo && fondoClave === clave) return fondo;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const off = document.createElement('canvas');
      off.width = Math.round(w * dpr);
      off.height = Math.round(h * dpr);
      const octx = off.getContext('2d');
      octx.setTransform(dpr, 0, 0, dpr, 0, 0);
      try { octx.drawImage(campo, 0, 0, w, h); } catch (e) { return null; }
      fondo = off;
      fondoClave = clave;
      return fondo;
    };

    const render = () => {
      const { w, h } = sizeCanvas();
      const cesped = fondoPara(w, h);
      if (cesped) ctx.drawImage(cesped, 0, 0, w, h);
      else drawPitchFallback(ctx, w, h);
      const { index, t } = locate(elapsed);
      const step = steps[index] || {};
      const prev = steps[index - 1] || null;
      const radius = Math.max(7, Math.min(w, h) * 0.026);
      const eased = easeInOut(t);

      actors.forEach((actor) => {
        const path = step.moves ? step.moves[actor.uid] : null;
        let pos = null;
        if (Array.isArray(path) && path.length > 1) {
          pos = samplePath(path, eased);            // recorrido dibujado: se sigue la linea
        } else if (Array.isArray(path) && path.length === 1) {
          const from = prev && prev.moves && Array.isArray(prev.moves[actor.uid])
            ? prev.moves[actor.uid][prev.moves[actor.uid].length - 1]
            : null;
          pos = from
            ? { x: from[0] + (path[0][0] - from[0]) * eased, y: from[1] + (path[0][1] - from[1]) * eased }
            : { x: path[0][0], y: path[0][1] };     // sin recorrido: se interpola desde el paso anterior
        }
        if (pos) drawActor(ctx, actorById.get(actor.uid) || actor, pos, w, h, radius);
      });

      stepLabel.textContent = `${index + 1}/${steps.length} · ${step.title || ''}`;
      if (!seek.matches(':active')) seek.value = String(Math.round((elapsed / totalSeconds) * 1000));
    };

    const tick = (now) => {
      if (!playing) return;
      const dt = last ? (now - last) / 1000 : 0;
      last = now;
      elapsed += dt;
      if (elapsed >= totalSeconds) {
        elapsed = totalSeconds;
        playing = false;
        playBtn.textContent = '▶';
      }
      render();
      if (playing) window.requestAnimationFrame(tick);
    };

    playBtn.addEventListener('click', () => {
      if (playing) {
        playing = false;
        playBtn.textContent = '▶';
        return;
      }
      if (elapsed >= totalSeconds) elapsed = 0;
      playing = true;
      last = 0;
      playBtn.textContent = '⏸';
      window.requestAnimationFrame(tick);
    });
    seek.addEventListener('input', () => {
      playing = false;
      playBtn.textContent = '▶';
      elapsed = (num(seek.value) / 1000) * totalSeconds;
      render();
    });
    repintar = render;
    window.addEventListener('resize', render, { passive: true });
    render();
  };

  const boot = () => document.querySelectorAll('[data-task-script-player]').forEach(mount);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
