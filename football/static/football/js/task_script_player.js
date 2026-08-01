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

  const drawPitch = (ctx, w, h) => {
    ctx.fillStyle = '#2f7d32';
    ctx.fillRect(0, 0, w, h);
    // Franjas de corte: dan escala y hacen que se note el movimiento.
    ctx.fillStyle = 'rgba(255,255,255,0.045)';
    const bands = 8;
    for (let i = 0; i < bands; i += 1) {
      if (i % 2) continue;
      ctx.fillRect((w / bands) * i, 0, w / bands, h);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.72)';
    ctx.lineWidth = Math.max(1.2, w * 0.0022);
    const m = w * 0.02;
    ctx.strokeRect(m, m, w - m * 2, h - m * 2);
    ctx.beginPath();
    ctx.moveTo(w / 2, m);
    ctx.lineTo(w / 2, h - m);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, Math.min(w, h) * 0.13, 0, TAU);
    ctx.stroke();
    const areaW = w * 0.15;
    const areaH = h * 0.44;
    ctx.strokeRect(m, (h - areaH) / 2, areaW, areaH);
    ctx.strokeRect(w - m - areaW, (h - areaH) / 2, areaW, areaH);
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
    ctx.beginPath();
    ctx.arc(x, y + radius * 0.16, radius, 0, TAU);
    ctx.fillStyle = 'rgba(2,6,23,0.28)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, TAU);
    ctx.fillStyle = actor.color || '#2f6fd6';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.92)';
    ctx.lineWidth = Math.max(1.4, radius * 0.14);
    ctx.stroke();
    const label = String(actor.label || '').slice(0, 3);
    if (label) {
      ctx.fillStyle = '#ffffff';
      ctx.font = `800 ${Math.round(radius * 1.05)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, x, y);
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

    const actorById = new Map(actors.map((a) => [a.uid, a]));

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

    const render = () => {
      const { w, h } = sizeCanvas();
      drawPitch(ctx, w, h);
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
    window.addEventListener('resize', render, { passive: true });
    render();
  };

  const boot = () => document.querySelectorAll('[data-task-script-player]').forEach(mount);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
