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
      if (arrastrando) { pintarLectura(); aviso('Movido. Recuerda guardar el planteamiento.'); }
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
    if (fila.photo_url) {
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
    pintarCarriles();
    estado.starters.forEach((f) => campo.appendChild(crearFicha(f, false)));
    estado.rival.forEach((f) => campo.appendChild(crearFicha(f, true)));
    pintarLectura();
    pintarCabeceraRival();
  };

  // Los carriles sobre el césped: se encienden con el interruptor, no van siempre puestos.
  let carrilesVisibles = false;
  const pintarCarriles = () => {
    if (!carrilesVisibles) return;
    const capa = document.createElement('div');
    capa.className = 'tp-lanes-layer';
    CARRILES.forEach((c) => {
      const banda = document.createElement('div');
      banda.className = 'tp-lane-band';
      banda.style.top = c.desde + '%';
      banda.style.height = (c.hasta - c.desde) + '%';
      const etq = document.createElement('span');
      etq.textContent = c.nombre;
      banda.appendChild(etq);
      capa.appendChild(banda);
    });
    ZONAS.slice(1).forEach((z) => {
      const linea = document.createElement('div');
      linea.className = 'tp-zone-line';
      linea.style.left = z.desde + '%';
      capa.appendChild(linea);
    });
    campo.appendChild(capa);
  };

  // --- lectura del campo: carriles, estructura y superioridades ---
  //
  // El eje X es la longitud (portería a portería) y el Y la ANCHURA, así que los carriles son
  // bandas horizontales. Los cinco de siempre: banda, interior (la medialuna), central, interior,
  // banda. Las proporciones no son iguales a propósito: el central es más ancho que los interiores.
  const CARRILES = [
    { clave: 'izq', nombre: 'Banda izq.', desde: 0, hasta: 20 },
    { clave: 'int_izq', nombre: 'Interior izq.', desde: 20, hasta: 37 },
    { clave: 'centro', nombre: 'Central', desde: 37, hasta: 63 },
    { clave: 'int_der', nombre: 'Interior der.', desde: 63, hasta: 80 },
    { clave: 'der', nombre: 'Banda der.', desde: 80, hasta: 100 },
  ];
  const ZONAS = [
    { clave: 'def', nombre: 'Defensiva', desde: 0, hasta: 34 },
    { clave: 'media', nombre: 'Media', desde: 34, hasta: 67 },
    { clave: 'ofe', nombre: 'Ofensiva', desde: 67, hasta: 100 },
  ];

  const carrilDe = (y) => CARRILES.find((c) => y >= c.desde && y < c.hasta) || CARRILES[CARRILES.length - 1];
  const zonaDe = (x) => ZONAS.find((z) => x >= z.desde && x < z.hasta) || ZONAS[ZONAS.length - 1];

  const leerEstructura = () => {
    const jug = estado.starters.filter((p) => Number.isFinite(Number(p.x_pct)));
    if (jug.length < 3) return null;
    // El portero fuera: si entra, la profundidad y la altura del bloque mienten.
    const ordenados = [...jug].sort((a, b) => a.x_pct - b.x_pct);
    const portero = ordenados[0];
    const campo = ordenados.slice(1);
    if (!campo.length) return null;

    // Líneas: se agrupan por cercanía en X. Un salto grande abre línea nueva.
    const lineas = [];
    let actual = [campo[0]];
    for (let i = 1; i < campo.length; i += 1) {
      if (campo[i].x_pct - campo[i - 1].x_pct > 7) { lineas.push(actual); actual = []; }
      actual.push(campo[i]);
    }
    lineas.push(actual);

    const xs = campo.map((p) => p.x_pct);
    const ys = campo.map((p) => p.y_pct);
    const media = (a) => a.reduce((s, v) => s + v, 0) / a.length;
    // Distancia entre líneas: la mayor separación entre líneas consecutivas, que es por donde
    // te parten.
    let mayorHueco = 0;
    for (let i = 1; i < lineas.length; i += 1) {
      const hueco = media(lineas[i].map((p) => p.x_pct)) - media(lineas[i - 1].map((p) => p.x_pct));
      if (hueco > mayorHueco) mayorHueco = hueco;
    }
    return {
      dibujo: '1-' + lineas.map((l) => l.length).join('-'),
      amplitud: Math.round(Math.max(...ys) - Math.min(...ys)),
      profundidad: Math.round(Math.max(...xs) - Math.min(...xs)),
      entreLineas: Math.round(mayorHueco),
      altura: Math.round(media(xs)),
      porteroFuera: Math.round(portero.x_pct),
    };
  };

  const leerCarriles = () => CARRILES.map((c) => ({
    nombre: c.nombre,
    nuestros: estado.starters.filter((p) => carrilDe(p.y_pct).clave === c.clave).length,
    rival: estado.rival.filter((p) => carrilDe(p.y_pct).clave === c.clave).length,
  }));

  const leerZonas = () => ZONAS.map((z) => ({
    nombre: z.nombre,
    nuestros: estado.starters.filter((p) => zonaDe(p.x_pct).clave === z.clave).length,
    // El rival mira hacia el otro lado: su zona ofensiva es nuestra defensiva.
    rival: estado.rival.filter((p) => zonaDe(100 - p.x_pct).clave === z.clave).length,
  }));

  const pintarLectura = () => {
    const cont = $('tp-read');
    if (!cont) return;
    const e = leerEstructura();
    if (!e) { cont.innerHTML = '<p class="tp-hint" style="margin:0;">Coloca el once y aquí verás cómo queda.</p>'; return; }
    const fila = (etq, val, pista) => '<div class="tp-metric"><span>' + etq + '</span><strong title="' + pista + '">' + val + '</strong></div>';
    let html = '<div class="tp-dibujo">' + e.dibujo + '</div>';
    html += '<div class="tp-metrics">';
    html += fila('Amplitud', e.amplitud + '%', 'Cuánto ocupas a lo ancho');
    html += fila('Profundidad', e.profundidad + '%', 'Del último al primero, sin el portero');
    html += fila('Entre líneas', e.entreLineas + '%', 'La mayor separación entre dos líneas: por ahí te parten');
    html += fila('Altura', e.altura + '%', 'Dónde vive el bloque');
    html += '</div>';

    const carriles = leerCarriles();
    html += '<p class="tp-sub">Carriles</p><div class="tp-lanes">';
    carriles.forEach((c) => {
      const dif = c.nuestros - c.rival;
      const clase = dif > 0 ? 'mas' : (dif < 0 ? 'menos' : '');
      const marca = estado.rival.length ? (dif > 0 ? '+' + dif : String(dif)) : String(c.nuestros);
      html += '<div class="tp-lane ' + clase + '"><span>' + c.nombre + '</span><strong>' + marca + '</strong></div>';
    });
    html += '</div>';

    if (estado.rival.length) {
      html += '<p class="tp-sub">Zonas</p><div class="tp-lanes">';
      leerZonas().forEach((z) => {
        const dif = z.nuestros - z.rival;
        const clase = dif > 0 ? 'mas' : (dif < 0 ? 'menos' : '');
        html += '<div class="tp-lane ' + clase + '"><span>' + z.nombre + '</span><strong>' + (dif > 0 ? '+' + dif : dif) + '</strong></div>';
      });
      html += '</div><p class="tp-hint" style="margin:.4rem 0 0;">+ es superioridad nuestra en esa franja.</p>';
    }
    cont.innerHTML = html;
    const forma = $('tp-shape');
    if (forma) forma.textContent = e.dibujo;
  };

  const pintarCabeceraRival = () => {
    const nombre = $('tp-rival-name');
    const escudo = $('tp-rival-crest');
    const forma = $('tp-shape-rival');
    const r = rivales.find((x) => String(x.id) === String(estado.rival_team_id));
    if (nombre) nombre.textContent = r ? r.name : 'Sin rival';
    if (escudo) {
      if (r && r.crest) { escudo.src = r.crest; escudo.hidden = false; } else { escudo.hidden = true; }
    }
    if (forma) {
      // El dibujo del rival se lee igual que el nuestro, pero mirando desde su lado.
      const suyos = estado.rival.map((p) => ({ ...p, x_pct: 100 - p.x_pct }));
      const guardado = estado.starters;
      estado.starters = suyos;
      const e = leerEstructura();
      estado.starters = guardado;
      forma.textContent = e ? e.dibujo : '—';
    }
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
          estado.starters.push({ id: p.id, name: p.name, number: p.number, position: p.position, photo_url: p.photo_url || '', x_pct: hueco.x, y_pct: hueco.y });
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
    const porId = new Map(plantilla.map((p) => [String(p.id), p]));
    estado.starters = ((plan.lineup || {}).starters || []).map((f) => {
      const p = porId.get(String(f.id));
      return { ...f, photo_url: (p && p.photo_url) || '' };
    });
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

  const btnCarriles = $('tp-lanes-toggle');
  if (btnCarriles) {
    btnCarriles.addEventListener('click', () => {
      carrilesVisibles = !carrilesVisibles;
      btnCarriles.textContent = carrilesVisibles ? 'Carriles: ON' : 'Carriles: OFF';
      btnCarriles.setAttribute('aria-pressed', carrilesVisibles ? 'true' : 'false');
      pintarCampo();
    });
  }

  pintarSelectorPartido();
  pintarSelectorRival();
  pintarLista();
  pintarBanquillo();
  if (planes.length) cargarPlan(planes[0]); else pintarCampo();
})();
