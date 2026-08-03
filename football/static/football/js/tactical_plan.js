/*
  Táctica · Planteamiento.

  Fichas de los dos equipos sobre el césped, arrastrables, y varios planteamientos guardados por
  equipo. Las coordenadas van en porcentaje y en la misma orientación que el prepartido ('lr',
  campo horizontal, nosotros a la izquierda): es lo que permitirá volcar un planteamiento sobre un
  partido sin convertir nada.
*/
(function () {
  const leerJson = (id, alterno) => {
    try {
      const nodo = document.getElementById(id);
      if (!nodo) return alterno;
      const crudo = JSON.parse(nodo.textContent || 'null');
      // El servidor manda una cadena JSON dentro del json_script; puede venir ya como objeto.
      return typeof crudo === 'string' ? JSON.parse(crudo) : (crudo || alterno);
    } catch (e) {
      return alterno;
    }
  };

  const campo = document.getElementById('tp-pitch');
  if (!campo) return;
  const $ = (id) => document.getElementById(id);

  const LIMITE = Number(window.TP_LIMITE || 11);
  const URLS = window.TP_URLS || {};
  const slots = leerJson('tp-slots', []);
  const plantilla = leerJson('tp-jugadores', []);
  const rivales = leerJson('tp-rivales', []);
  let planes = leerJson('tp-planes', []);

  const estado = { id: null, name: '', formation: '', starters: [], rival_team_id: '', rival: [] };

  const csrf = () => {
    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : '';
  };
  const aviso = (texto) => { const n = $('tp-status'); if (n) n.textContent = texto; };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  // --- fichas ---
  const hacerArrastrable = (el, fila) => {
    let desde = null;
    let arrastrando = false;
    el.addEventListener('pointerdown', (ev) => {
      if (ev.button !== undefined && ev.button !== 0) return;
      try { el.setPointerCapture(ev.pointerId); } catch (e) {}
      desde = { x: ev.clientX, y: ev.clientY };
      arrastrando = false;
    });
    el.addEventListener('pointermove', (ev) => {
      if (!desde) return;
      if (!arrastrando && (Math.abs(ev.clientX - desde.x) + Math.abs(ev.clientY - desde.y)) < 6) return;
      arrastrando = true;
      const r = campo.getBoundingClientRect();
      fila.x_pct = clamp(((ev.clientX - r.left) / r.width) * 100, 3, 97);
      fila.y_pct = clamp(((ev.clientY - r.top) / r.height) * 100, 5, 95);
      el.style.left = fila.x_pct + '%';
      el.style.top = fila.y_pct + '%';
    });
    const soltar = () => {
      if (!desde) return;
      desde = null;
      if (arrastrando) aviso('Movido. Recuerda guardar el planteamiento.');
      arrastrando = false;
    };
    el.addEventListener('pointerup', soltar);
    el.addEventListener('pointercancel', soltar);
  };

  const crearFicha = (fila, esRival) => {
    const el = document.createElement('div');
    el.className = 'tp-token' + (esRival ? ' is-rival' : '');
    el.style.left = (fila.x_pct ?? 50) + '%';
    el.style.top = (fila.y_pct ?? 50) + '%';
    if (esRival && fila.photo_url) {
      const img = document.createElement('img');
      img.src = fila.photo_url;
      img.alt = '';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => {
        img.remove();
        const n = document.createElement('span');
        n.className = 'num';
        n.textContent = fila.number || '·';
        el.prepend(n);
      });
      el.appendChild(img);
    } else {
      const n = document.createElement('span');
      n.className = 'num';
      n.textContent = fila.number || '·';
      el.appendChild(n);
    }
    const lbl = document.createElement('span');
    lbl.className = 'lbl';
    lbl.textContent = String(fila.name || '').split(' ')[0].slice(0, 12);
    el.appendChild(lbl);
    hacerArrastrable(el, fila);
    return el;
  };

  const pintarCampo = () => {
    campo.innerHTML = '';
    estado.starters.forEach((f) => campo.appendChild(crearFicha(f, false)));
    estado.rival.forEach((f) => campo.appendChild(crearFicha(f, true)));
  };

  // --- banquillo de la plantilla ---
  const pintarBanquillo = () => {
    const cont = $('tp-bank');
    if (!cont) return;
    cont.innerHTML = '';
    plantilla.forEach((p) => {
      const puesto = estado.starters.some((s) => String(s.id) === String(p.id));
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'button' + (puesto ? ' primary' : '');
      b.textContent = (p.number ? '#' + p.number + ' ' : '') + (p.name || '').split(' ')[0];
      b.addEventListener('click', () => {
        if (puesto) {
          estado.starters = estado.starters.filter((s) => String(s.id) !== String(p.id));
        } else {
          if (estado.starters.length >= LIMITE) { aviso('Ya hay ' + LIMITE + ' en el campo.'); return; }
          const hueco = slots[estado.starters.length] || { x: 50, y: 50 };
          estado.starters.push({ id: p.id, name: p.name, number: p.number, position: p.position, x_pct: hueco.x, y_pct: hueco.y });
        }
        pintarBanquillo();
        pintarCampo();
      });
      cont.appendChild(b);
    });
  };

  // --- lista de planteamientos ---
  const pintarLista = () => {
    const cont = $('tp-list');
    if (!cont) return;
    if (!planes.length) {
      cont.innerHTML = '<p class="tp-hint" style="margin:0;">Todavía no hay ninguno guardado.</p>';
      return;
    }
    cont.innerHTML = '';
    planes.forEach((plan) => {
      const fila = document.createElement('div');
      fila.className = 'tp-plan' + (String(plan.id) === String(estado.id) ? ' is-on' : '');
      fila.innerHTML = '<strong></strong><small></small>';
      fila.querySelector('strong').textContent = plan.name;
      fila.querySelector('small').textContent = plan.formation || '';
      fila.addEventListener('click', () => cargarPlan(plan));
      cont.appendChild(fila);
    });
  };

  const cargarPlan = (plan) => {
    estado.id = plan.id;
    estado.name = plan.name || '';
    estado.formation = plan.formation || '';
    estado.starters = ((plan.lineup || {}).starters || []).map((f) => ({ ...f }));
    estado.rival = ((plan.rival_lineup || {}).starters || []).map((f) => ({ ...f }));
    estado.rival_team_id = plan.rival_team_id || '';
    $('tp-name').value = estado.name;
    $('tp-formation').value = estado.formation;
    $('tp-rival').value = estado.rival_team_id || '';
    pintarLista();
    pintarBanquillo();
    pintarCampo();
    aviso('Planteamiento «' + estado.name + '» cargado.');
  };

  // --- rival ---
  const pintarSelectorRival = () => {
    const sel = $('tp-rival');
    if (!sel) return;
    rivales.forEach((r) => {
      const o = document.createElement('option');
      o.value = r.id;
      o.textContent = r.name + ' (' + r.players + ')';
      sel.appendChild(o);
    });
    sel.addEventListener('change', async () => {
      estado.rival_team_id = sel.value;
      if (!sel.value) { estado.rival = []; pintarCampo(); return; }
      aviso('Cargando el once del rival…');
      try {
        const r = await fetch(URLS.rival + '?rival=' + encodeURIComponent(sel.value), { credentials: 'same-origin' });
        const d = await r.json();
        const jug = (d.players || []).slice(0, LIMITE);
        estado.rival = jug.map((p, i) => {
          const s = slots[i] || { x: 50, y: 50 };
          return { ...p, x_pct: 100 - s.x, y_pct: 100 - s.y };
        });
        pintarCampo();
        aviso('Rival colocado: ' + estado.rival.length + ' jugadores.');
      } catch (e) {
        aviso('No se pudo cargar la plantilla del rival.');
      }
    });
  };

  // --- guardar / borrar ---
  $('tp-save').addEventListener('click', async () => {
    const nombre = ($('tp-name').value || '').trim();
    if (!nombre) { aviso('Ponle un nombre al planteamiento.'); return; }
    aviso('Guardando…');
    try {
      const r = await fetch(URLS.save, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({
          id: estado.id,
          name: nombre,
          formation: ($('tp-formation').value || '').trim(),
          lineup: { starters: estado.starters },
          rival_team_id: estado.rival_team_id || null,
          rival_lineup: { starters: estado.rival },
        }),
      });
      const d = await r.json();
      if (!d.ok) { aviso(d.error || 'No se pudo guardar.'); return; }
      const idx = planes.findIndex((p) => String(p.id) === String(d.plan.id));
      if (idx >= 0) planes[idx] = d.plan; else planes.unshift(d.plan);
      estado.id = d.plan.id;
      pintarLista();
      aviso('Guardado.');
    } catch (e) {
      aviso('No se pudo guardar.');
    }
  });

  $('tp-delete').addEventListener('click', async () => {
    if (!estado.id) { aviso('No hay ningún planteamiento cargado.'); return; }
    if (!window.confirm('¿Borrar este planteamiento?')) return;
    try {
      await fetch(URLS.del, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ id: estado.id }),
      });
      planes = planes.filter((p) => String(p.id) !== String(estado.id));
      estado.id = null;
      pintarLista();
      aviso('Borrado.');
    } catch (e) {
      aviso('No se pudo borrar.');
    }
  });

  $('tp-new').addEventListener('click', () => {
    estado.id = null;
    estado.starters = [];
    estado.rival = [];
    estado.rival_team_id = '';
    $('tp-name').value = '';
    $('tp-formation').value = '';
    $('tp-rival').value = '';
    pintarLista();
    pintarBanquillo();
    pintarCampo();
    aviso('Planteamiento nuevo: elige los once y colócalos.');
  });

  // --- aplicar a un partido ---
  const pintarSelectorPartido = () => {
    const sel = $('tp-match');
    if (!sel) return;
    leerJson('tp-partidos', []).forEach((p) => {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.label;
      sel.appendChild(o);
    });
  };

  const botonAplicar = $('tp-apply');
  if (botonAplicar) {
    botonAplicar.addEventListener('click', async () => {
      const partido = ($('tp-match') || {}).value;
      if (!estado.id) { aviso('Guarda el planteamiento antes de aplicarlo.'); return; }
      if (!partido) { aviso('Elige a qué partido lo aplicas.'); return; }
      aviso('Aplicando…');
      try {
        const r = await fetch(URLS.apply, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
          body: JSON.stringify({ plan_id: estado.id, match_id: partido }),
        });
        const d = await r.json();
        if (!d.ok) { aviso(d.error || 'No se pudo aplicar.'); return; }
        const extra = d.added_to_convocation
          ? ' (' + d.added_to_convocation + ' añadidos a la convocatoria)'
          : '';
        aviso('Aplicado: ' + d.starters + ' titulares' + (d.rival ? ' y ' + d.rival + ' del rival' : '') + extra + '.');
      } catch (e) {
        aviso('No se pudo aplicar.');
      }
    });
  }

  pintarSelectorPartido();
  pintarSelectorRival();
  pintarLista();
  pintarBanquillo();
  if (planes.length) cargarPlan(planes[0]); else pintarCampo();
})();
