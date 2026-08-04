/*
  Táctica · Jugadas: el dibujo libre.

  Mismo campo, misma ficha y mismos pasos que el Planteamiento; lo nuevo es la capa de trazos. Va en
  un SVG con el viewBox del césped (1664x945) para que las líneas no se deformen: con un viewBox
  cuadrado y preserveAspectRatio="none" las puntas de flecha salen aplastadas.

  Las coordenadas se guardan en PORCENTAJE, igual que el planteamiento y el registro de acciones, no
  en píxeles: así el mismo dibujo vale en un móvil, en el proyector y en la foto en PNG.
*/
(function () {
  const leerJson = (id, alterno) => {
    try {
      const nodo = document.getElementById(id);
      if (!nodo) return alterno;
      const crudo = JSON.parse(nodo.textContent || 'null');
      return typeof crudo === 'string' ? JSON.parse(crudo) : (crudo || alterno);
    } catch (e) {
      return alterno;
    }
  };

  const campo = document.getElementById('tj-pitch');
  const lienzo = document.getElementById('tj-draw');
  if (!campo || !lienzo) return;
  const $ = (id) => document.getElementById(id);

  const NS = 'http://www.w3.org/2000/svg';
  const ANCHO = 1664;
  const ALTO = 945;
  const LIMITE = Number(window.TJ_LIMITE || 11);
  const MAX_PASOS = Number(window.TJ_MAX_PASOS || 12);
  const URLS = window.TJ_URLS || {};
  const slots = leerJson('tj-slots', []);
  const plantilla = leerJson('tj-jugadores', []);
  const planes = leerJson('tj-planes', []);
  const TIPOS = leerJson('tj-tipos', [{ key: 'ataque', name: 'Ataque' }]);
  let jugadas = leerJson('tj-jugadas', []);

  // Las herramientas. El color y el trazo son los de la pizarra de toda la vida: el balón viaja en
  // línea continua, el jugador se mueve en discontinua, y la conducción es la ondulada.
  const HERRAMIENTAS = [
    { clave: 'pase', nombre: 'Pase', color: '#6fd3ff' },
    { clave: 'conduccion', nombre: 'Conducción', color: '#6fd3ff' },
    { clave: 'desmarque', nombre: 'Desmarque', color: '#ffd76a' },
    { clave: 'zona', nombre: 'Zona', color: '#eaf4ef' },
    { clave: 'cono', nombre: 'Cono', color: '#ff9f43' },
    { clave: 'balon', nombre: 'Balón', color: '#ffffff' },
    { clave: 'texto', nombre: 'Texto', color: '#eaf4ef' },
  ];
  const MARCAS = ['cono', 'balon', 'texto'];
  const colorDe = (clave) => (HERRAMIENTAS.find((h) => h.clave === clave) || {}).color || '#eaf4ef';

  const pasoVacio = (nombre) => ({ name: nombre, starters: [], rival: [], shapes: [] });
  const estado = {
    id: null,
    kind: (TIPOS[0] || {}).key || 'ataque',
    pasos: [pasoVacio('Paso 1')],
    i: 0,
    herramienta: '',
  };
  const paso = () => estado.pasos[estado.i] || estado.pasos[0];

  const csrf = () => {
    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : '';
  };
  const aviso = (texto) => { const n = $('tj-status'); if (n) n.textContent = texto; };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const ux = (x) => (x / 100) * ANCHO;
  const uy = (y) => (y / 100) * ALTO;

  // --- capa de dibujo ---
  const crearSvg = (etiqueta, atributos) => {
    const el = document.createElementNS(NS, etiqueta);
    Object.keys(atributos || {}).forEach((k) => el.setAttribute(k, atributos[k]));
    return el;
  };

  const puntas = () => {
    const defs = crearSvg('defs', {});
    HERRAMIENTAS.filter((h) => !MARCAS.includes(h.clave)).forEach((h) => {
      const marca = crearSvg('marker', {
        id: 'tj-punta-' + h.clave,
        markerWidth: 6, markerHeight: 6, refX: 5, refY: 3,
        orient: 'auto', markerUnits: 'strokeWidth',
      });
      marca.appendChild(crearSvg('path', { d: 'M0,0 L6,3 L0,6 z', fill: h.color }));
      defs.appendChild(marca);
    });
    return defs;
  };

  // La conducción se dibuja ondulada: se recorre el trazo y se va desplazando a un lado y a otro de
  // la línea. Sin esto, "pase" y "conducción" serían la misma raya.
  const ondular = (puntos) => {
    const salida = [];
    const AMPLITUD = 9;
    const PASO = 26;
    let acumulado = 0;
    let lado = 1;
    for (let i = 1; i < puntos.length; i += 1) {
      const a = puntos[i - 1];
      const b = puntos[i];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const largo = Math.hypot(dx, dy);
      if (largo < 0.01) continue;
      const nx = -dy / largo;
      const ny = dx / largo;
      let recorrido = 0;
      while (recorrido + PASO <= largo) {
        recorrido += PASO;
        acumulado += PASO;
        const t = recorrido / largo;
        salida.push({ x: a.x + dx * t + nx * AMPLITUD * lado, y: a.y + dy * t + ny * AMPLITUD * lado });
        lado *= -1;
      }
    }
    return salida;
  };

  const trazoAPath = (puntosPx) => puntosPx.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' ');

  const pintarTrazo = (trazo) => {
    const puntos = (trazo.points || []).map((p) => ({ x: ux(p.x), y: uy(p.y) }));
    if (!puntos.length) return null;
    const color = colorDe(trazo.tool);
    const g = crearSvg('g', {});

    if (trazo.tool === 'zona') {
      const a = puntos[0];
      const b = puntos[puntos.length - 1];
      g.appendChild(crearSvg('rect', {
        x: Math.min(a.x, b.x), y: Math.min(a.y, b.y),
        width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y),
        rx: 10, fill: 'rgba(234,244,239,.13)', stroke: color, 'stroke-width': 3, 'stroke-dasharray': '12 9',
      }));
    } else if (trazo.tool === 'cono') {
      const p = puntos[0];
      g.appendChild(crearSvg('path', {
        d: 'M' + p.x + ' ' + (p.y - 14) + ' L' + (p.x + 12) + ' ' + (p.y + 10) + ' L' + (p.x - 12) + ' ' + (p.y + 10) + ' z',
        fill: color, stroke: 'rgba(0,0,0,.45)', 'stroke-width': 2,
      }));
    } else if (trazo.tool === 'balon') {
      const p = puntos[0];
      g.appendChild(crearSvg('circle', { cx: p.x, cy: p.y, r: 11, fill: '#fff', stroke: '#12211b', 'stroke-width': 3 }));
      g.appendChild(crearSvg('circle', { cx: p.x, cy: p.y, r: 4, fill: '#12211b' }));
    } else if (trazo.tool === 'texto') {
      const p = puntos[0];
      const t = crearSvg('text', {
        x: p.x, y: p.y, fill: color, 'font-size': 30, 'font-weight': 800,
        'text-anchor': 'middle', 'paint-order': 'stroke', stroke: 'rgba(0,0,0,.75)', 'stroke-width': 6,
      });
      t.textContent = trazo.text || '';
      g.appendChild(t);
    } else {
      const dibujo = trazo.tool === 'conduccion' ? [puntos[0]].concat(ondular(puntos)).concat([puntos[puntos.length - 1]]) : puntos;
      g.appendChild(crearSvg('path', {
        d: trazoAPath(dibujo),
        fill: 'none', stroke: color, 'stroke-width': 5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
        'stroke-dasharray': trazo.tool === 'desmarque' ? '16 12' : '',
        'marker-end': 'url(#tj-punta-' + trazo.tool + ')',
      }));
    }
    return g;
  };

  const pintarDibujo = (trazos) => {
    lienzo.setAttribute('viewBox', '0 0 ' + ANCHO + ' ' + ALTO);
    lienzo.setAttribute('preserveAspectRatio', 'none');
    lienzo.innerHTML = '';
    lienzo.appendChild(puntas());
    (trazos || []).forEach((t) => {
      const nodo = pintarTrazo(t);
      if (nodo) lienzo.appendChild(nodo);
    });
  };

  // --- fichas ---
  const hacerArrastrable = (el, fila) => {
    let desde = null;
    let arrastrando = false;
    el.addEventListener('pointerdown', (ev) => {
      if (estado.herramienta) return;
      if (ev.button !== undefined && ev.button !== 0) return;
      ev.stopPropagation();
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
      if (arrastrando) aviso('Movido. Recuerda guardar la jugada.');
      arrastrando = false;
    };
    el.addEventListener('pointerup', soltar);
    el.addEventListener('pointercancel', soltar);
  };

  const crearFicha = (fila, esRival) => {
    const el = document.createElement('div');
    el.className = 'tj-token' + (esRival ? ' is-rival' : '');
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
    if (!esRival && fila.baja) {
      el.classList.add('is-baja');
      el.title = (fila.name || '') + ' · ' + fila.baja;
    }
    const lbl = document.createElement('span');
    lbl.className = 'lbl';
    lbl.textContent = String(fila.name || '').split(' ')[0].slice(0, 12);
    el.appendChild(lbl);
    hacerArrastrable(el, fila);
    return el;
  };

  const pintarCampo = () => {
    Array.from(campo.querySelectorAll('.tj-token')).forEach((n) => n.remove());
    const p = paso();
    (p.starters || []).forEach((f) => campo.appendChild(crearFicha(f, false)));
    (p.rival || []).forEach((f) => campo.appendChild(crearFicha(f, true)));
    pintarDibujo(p.shapes);
  };

  // --- dibujar sobre el campo ---
  let trazando = null;
  const puntoDelEvento = (ev) => {
    const r = campo.getBoundingClientRect();
    return {
      x: clamp(((ev.clientX - r.left) / r.width) * 100, 0, 100),
      y: clamp(((ev.clientY - r.top) / r.height) * 100, 0, 100),
    };
  };

  campo.addEventListener('pointerdown', (ev) => {
    if (!estado.herramienta) return;
    if (ev.button !== undefined && ev.button !== 0) return;
    const punto = puntoDelEvento(ev);
    if (MARCAS.includes(estado.herramienta)) {
      let texto = '';
      if (estado.herramienta === 'texto') {
        texto = (window.prompt('¿Qué pone?') || '').trim();
        if (!texto) return;
      }
      paso().shapes.push({ tool: estado.herramienta, points: [punto], text: texto });
      pintarDibujo(paso().shapes);
      aviso('Puesto. Sigue dibujando o cambia de herramienta.');
      return;
    }
    try { campo.setPointerCapture(ev.pointerId); } catch (e) {}
    trazando = { tool: estado.herramienta, points: [punto], text: '' };
  });

  campo.addEventListener('pointermove', (ev) => {
    if (!trazando) return;
    const punto = puntoDelEvento(ev);
    const ultimo = trazando.points[trazando.points.length - 1];
    // No se guardan todos los píxeles: un trazo con 400 puntos pesa y no se dibuja mejor.
    if (Math.abs(punto.x - ultimo.x) + Math.abs(punto.y - ultimo.y) < 1.2) return;
    trazando.points.push(punto);
    pintarDibujo((paso().shapes || []).concat([trazando]));
  });

  const soltarTrazo = () => {
    if (!trazando) return;
    const t = trazando;
    trazando = null;
    if (t.points.length < 2) { pintarDibujo(paso().shapes); return; }
    // La zona sólo necesita las dos esquinas; el resto del arrastre sobra.
    if (t.tool === 'zona') t.points = [t.points[0], t.points[t.points.length - 1]];
    if (t.points.length > 40) {
      const paso_ = Math.ceil(t.points.length / 40);
      t.points = t.points.filter((_, i) => i % paso_ === 0 || i === t.points.length - 1);
    }
    paso().shapes.push(t);
    pintarDibujo(paso().shapes);
    aviso('Trazo añadido al ' + (paso().name || 'paso') + '.');
  };
  campo.addEventListener('pointerup', soltarTrazo);
  campo.addEventListener('pointercancel', soltarTrazo);

  // --- barra de herramientas ---
  const muestraDe = (h) => {
    // aria-hidden en el SVG: es la muestra del trazo, no información. El nombre lo pone el botón.

    if (h.clave === 'zona') return '<svg aria-hidden="true" viewBox="0 0 26 12"><rect x="1" y="1" width="24" height="10" rx="2" fill="none" stroke="' + h.color + '" stroke-width="1.6" stroke-dasharray="3 2"/></svg>';
    if (h.clave === 'cono') return '<svg aria-hidden="true" viewBox="0 0 26 12"><path d="M13 1 L18 11 L8 11 z" fill="' + h.color + '"/></svg>';
    if (h.clave === 'balon') return '<svg aria-hidden="true" viewBox="0 0 26 12"><circle cx="13" cy="6" r="5" fill="#fff" stroke="#12211b" stroke-width="1.4"/></svg>';
    if (h.clave === 'texto') return '<svg aria-hidden="true" viewBox="0 0 26 12"><text x="13" y="10" text-anchor="middle" font-size="11" font-weight="800" fill="' + h.color + '">Aa</text></svg>';
    const raya = h.clave === 'desmarque'
      ? '<path d="M1 6 H20" stroke="' + h.color + '" stroke-width="2" stroke-dasharray="4 3"/>'
      : (h.clave === 'conduccion'
        ? '<path d="M1 6 q3 -4 6 0 q3 4 6 0 q3 -4 6 0" fill="none" stroke="' + h.color + '" stroke-width="2"/>'
        : '<path d="M1 6 H20" stroke="' + h.color + '" stroke-width="2"/>');
    return '<svg aria-hidden="true" viewBox="0 0 26 12">' + raya + '<path d="M20 2 L25 6 L20 10 z" fill="' + h.color + '"/></svg>';
  };

  const pintarHerramientas = () => {
    const cont = $('tj-tools');
    if (!cont) return;
    cont.innerHTML = '';
    const mover = document.createElement('button');
    mover.type = 'button';
    mover.className = 'tj-tool' + (estado.herramienta ? '' : ' is-on');
    mover.innerHTML = '<span>✋ Mover fichas</span>';
    mover.addEventListener('click', () => elegirHerramienta(''));
    cont.appendChild(mover);
    HERRAMIENTAS.forEach((h) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'tj-tool' + (estado.herramienta === h.clave ? ' is-on' : '');
      // El nombre va también en aria-label: el dibujito del trazo es un SVG decorativo y sin esto
      // el botón se anuncia vacío a quien navega con lector.
      b.setAttribute('aria-label', h.nombre);
      b.setAttribute('aria-pressed', estado.herramienta === h.clave ? 'true' : 'false');
      b.innerHTML = muestraDe(h) + '<span>' + h.nombre + '</span>';
      b.addEventListener('click', () => elegirHerramienta(h.clave));
      cont.appendChild(b);
    });
  };

  const elegirHerramienta = (clave) => {
    estado.herramienta = clave;
    campo.classList.toggle('dibujando', !!clave);
    pintarHerramientas();
    aviso(clave
      ? 'Herramienta: ' + (HERRAMIENTAS.find((h) => h.clave === clave) || {}).nombre + '. Arrastra sobre el campo.'
      : 'Ahora se mueven las fichas.');
  };

  // --- pasos ---
  const pintarPasos = () => {
    const cont = $('tj-steps');
    if (!cont) return;
    cont.innerHTML = '';
    estado.pasos.forEach((p, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'tj-step' + (i === estado.i ? ' is-on' : '');
      b.textContent = p.name || 'Paso ' + (i + 1);
      b.title = i === estado.i ? 'Vuelve a tocarlo para cambiarle el nombre' : 'Ver este paso';
      b.addEventListener('click', () => {
        if (i === estado.i) {
          const nuevo = (window.prompt('Nombre del paso', p.name) || '').trim();
          if (nuevo) { p.name = nuevo.slice(0, 40); pintarPasos(); }
          return;
        }
        estado.i = i;
        pintarPasos();
        pintarCampo();
        aviso('Paso ' + (i + 1) + ': ' + (p.name || ''));
      });
      cont.appendChild(b);
    });
    const mas = document.createElement('button');
    mas.type = 'button';
    mas.className = 'tj-step';
    mas.textContent = '+ Paso';
    mas.title = 'Un paso nuevo continúa donde acaba éste';
    mas.addEventListener('click', anadirPaso);
    cont.appendChild(mas);
    if (estado.pasos.length > 1) {
      const menos = document.createElement('button');
      menos.type = 'button';
      menos.className = 'tj-step';
      menos.textContent = '− Quitar paso';
      menos.addEventListener('click', () => {
        if (!window.confirm('¿Quitar «' + (paso().name || 'este paso') + '»?')) return;
        estado.pasos.splice(estado.i, 1);
        estado.i = Math.max(0, estado.i - 1);
        pintarPasos();
        pintarCampo();
        aviso('Paso quitado.');
      });
      cont.appendChild(menos);
    }
  };

  // Un paso nuevo arranca donde acaba el anterior: los jugadores siguen donde estaban y el dibujo
  // empieza limpio. Nadie quiere recolocar once fichas para contar el segundo movimiento.
  const anadirPaso = () => {
    if (estado.pasos.length >= MAX_PASOS) { aviso('Una jugada admite ' + MAX_PASOS + ' pasos como mucho.'); return; }
    const actual = paso();
    estado.pasos.splice(estado.i + 1, 0, {
      name: 'Paso ' + (estado.pasos.length + 1),
      starters: (actual.starters || []).map((f) => ({ ...f })),
      rival: (actual.rival || []).map((f) => ({ ...f })),
      shapes: [],
    });
    estado.i += 1;
    pintarPasos();
    pintarCampo();
    aviso('Paso nuevo: mueve a quien se mueve y dibuja lo que pasa.');
  };

  // --- banquillo ---
  const pintarBanquillo = () => {
    const cont = $('tj-bank');
    if (!cont) return;
    cont.innerHTML = '';
    plantilla.forEach((p) => {
      const puesto = (paso().starters || []).some((s) => String(s.id) === String(p.id));
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'button' + (puesto ? ' primary' : '');
      b.textContent = (p.number ? '#' + p.number + ' ' : '') + (p.name || '').split(' ')[0];
      if (p.baja) { b.classList.add('es-baja'); b.title = p.baja; }
      b.addEventListener('click', () => {
        const actual = paso();
        if (puesto) {
          // Se quita de TODOS los pasos: un jugador que desaparece a mitad de jugada no existe.
          estado.pasos.forEach((s) => { s.starters = (s.starters || []).filter((x) => String(x.id) !== String(p.id)); });
        } else {
          if ((actual.starters || []).length >= LIMITE) { aviso('Ya hay ' + LIMITE + ' en el campo.'); return; }
          const hueco = slots[(actual.starters || []).length] || { x: 50, y: 50 };
          const ficha = { id: p.id, name: p.name, number: p.number, position: p.position, photo_url: p.photo_url || '', baja: p.baja || '', x_pct: hueco.x, y_pct: hueco.y };
          estado.pasos.forEach((s) => { s.starters = (s.starters || []).concat([{ ...ficha }]); });
        }
        pintarBanquillo();
        pintarCampo();
      });
      cont.appendChild(b);
    });
  };

  const botonRival = $('tj-add-rival');
  if (botonRival) {
    botonRival.addEventListener('click', () => {
      const actual = paso();
      const n = (actual.rival || []).length;
      if (n >= LIMITE) { aviso('Ya hay ' + LIMITE + ' rivales.'); return; }
      const hueco = slots[n] || { x: 50, y: 50 };
      // Sin nombre a propósito: un rival genérico es un dorsal, y once etiquetas que ponen "Rival"
      // debajo de cada ficha sólo tapan el dibujo.
      const ficha = { code: 'r' + n, name: '', number: String(n + 1), position: '', photo_url: '', x_pct: 100 - hueco.x, y_pct: 100 - hueco.y };
      estado.pasos.forEach((s) => { s.rival = (s.rival || []).concat([{ ...ficha }]); });
      pintarCampo();
      aviso('Rival añadido. Arrástralo a su sitio.');
    });
  }

  // --- empezar desde un planteamiento ---
  const pintarSelectorPlan = () => {
    const sel = $('tj-plan');
    if (!sel) return;
    planes.forEach((p) => {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.name;
      sel.appendChild(o);
    });
    sel.addEventListener('change', () => {
      const plan = planes.find((p) => String(p.id) === String(sel.value));
      if (!plan) return;
      const porId = new Map(plantilla.map((p) => [String(p.id), p]));
      const actual = paso();
      actual.starters = (plan.starters || []).map((f) => {
        const p = porId.get(String(f.id));
        return { ...f, photo_url: (p && p.photo_url) || '', baja: (p && p.baja) || '' };
      });
      actual.rival = (plan.rival || []).map((f) => ({ ...f }));
      pintarBanquillo();
      pintarCampo();
      aviso('Cargado el once de «' + plan.name + '» en este paso.');
    });
  };

  // --- lista de jugadas ---
  // El filtro por tipo es lo que permite que "Balón parado" del menú sea ESTA pantalla filtrada y
  // no una pizarra aparte: el área tiene un editor, no tres.
  let filtro = String(window.TJ_TIPO_INICIAL || '');
  if (filtro && !TIPOS.some((t) => t.key === filtro)) filtro = '';

  const pintarFiltro = () => {
    const cont = $('tj-filter');
    if (!cont) return;
    cont.innerHTML = '';
    [{ key: '', name: 'Todas' }].concat(TIPOS).forEach((t) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'tj-step' + (filtro === t.key ? ' is-on' : '');
      const cuantas = t.key ? jugadas.filter((j) => j.kind === t.key).length : jugadas.length;
      b.textContent = t.name + (cuantas ? ' ' + cuantas : '');
      b.addEventListener('click', () => { filtro = t.key; pintarFiltro(); pintarLista(); });
      cont.appendChild(b);
    });
  };

  const pintarLista = () => {
    const cont = $('tj-list');
    if (!cont) return;
    const visibles = filtro ? jugadas.filter((j) => j.kind === filtro) : jugadas;
    if (!visibles.length) {
      cont.innerHTML = '<p class="tj-hint" style="margin:0;">'
        + (filtro ? 'No hay ninguna de este tipo todavía.' : 'Todavía no hay ninguna guardada.')
        + '</p>';
      return;
    }
    cont.innerHTML = '';
    visibles.forEach((j) => {
      const fila = document.createElement('div');
      fila.className = 'tj-item' + (String(j.id) === String(estado.id) ? ' is-on' : '');
      fila.innerHTML = '<strong></strong><small></small>';
      fila.querySelector('strong').textContent = j.name;
      fila.querySelector('small').textContent = (j.kind_label || '') + ' · ' + (j.steps || []).length + ' pasos';
      fila.addEventListener('click', () => cargarJugada(j));
      cont.appendChild(fila);
    });
  };

  const cargarJugada = (j) => {
    const porId = new Map(plantilla.map((p) => [String(p.id), p]));
    estado.id = j.id;
    estado.kind = j.kind || 'ataque';
    estado.pasos = ((j.steps || []).length ? j.steps : [pasoVacio('Paso 1')]).map((s, i) => ({
      name: s.name || 'Paso ' + (i + 1),
      starters: (s.starters || []).map((f) => {
        const p = porId.get(String(f.id));
        return { ...f, photo_url: (p && p.photo_url) || '', baja: (p && p.baja) || '' };
      }),
      rival: (s.rival || []).map((f) => ({ ...f })),
      shapes: (s.shapes || []).map((t) => ({ ...t, points: (t.points || []).map((q) => ({ ...q })) })),
    }));
    estado.i = 0;
    $('tj-name').value = j.name || '';
    $('tj-kind').value = estado.kind;
    $('tj-notes').value = j.notes || '';
    pintarLista();
    pintarPasos();
    pintarBanquillo();
    pintarCampo();
    refrescarEnlaces();
    pintarPublicacion();
    aviso('Jugada «' + j.name + '» cargada.');
  };

  // --- guardar / borrar / nueva ---
  const cuerpoJugada = () => ({
    id: estado.id,
    name: ($('tj-name').value || '').trim(),
    kind: ($('tj-kind') || {}).value || estado.kind,
    notes: ($('tj-notes').value || '').trim(),
    steps: estado.pasos.map((p) => ({
      name: p.name,
      starters: (p.starters || []).map((f) => ({ id: f.id, x_pct: f.x_pct, y_pct: f.y_pct })),
      rival: (p.rival || []).map((f) => ({ code: f.code, name: f.name, number: f.number, position: f.position, photo_url: f.photo_url, x_pct: f.x_pct, y_pct: f.y_pct })),
      shapes: p.shapes || [],
    })),
  });

  $('tj-save').addEventListener('click', async () => {
    const cuerpo = cuerpoJugada();
    if (!cuerpo.name) { aviso('Ponle un nombre a la jugada.'); return; }
    aviso('Guardando…');
    try {
      const r = await fetch(URLS.save, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(cuerpo),
      });
      const d = await r.json();
      if (!d.ok) { aviso(d.error || 'No se pudo guardar.'); return; }
      const idx = jugadas.findIndex((j) => String(j.id) === String(d.play.id));
      if (idx >= 0) jugadas[idx] = d.play; else jugadas.unshift(d.play);
      estado.id = d.play.id;
      pintarFiltro();
      pintarLista();
      refrescarEnlaces();
      pintarPublicacion();
      aviso('Guardada.');
    } catch (e) {
      aviso('No se pudo guardar.');
    }
  });

  $('tj-delete').addEventListener('click', async () => {
    if (!estado.id) { aviso('No hay ninguna jugada cargada.'); return; }
    if (!window.confirm('¿Borrar esta jugada?')) return;
    try {
      await fetch(URLS.del, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ id: estado.id }),
      });
      jugadas = jugadas.filter((j) => String(j.id) !== String(estado.id));
      estado.id = null;
      pintarFiltro();
      pintarLista();
      refrescarEnlaces();
      pintarPublicacion();
      aviso('Borrada.');
    } catch (e) {
      aviso('No se pudo borrar.');
    }
  });

  $('tj-new').addEventListener('click', () => {
    estado.id = null;
    estado.pasos = [pasoVacio('Paso 1')];
    estado.i = 0;
    $('tj-name').value = '';
    $('tj-notes').value = '';
    pintarLista();
    pintarPasos();
    pintarBanquillo();
    pintarCampo();
    refrescarEnlaces();
    pintarPublicacion();
    aviso('Jugada nueva: pon a los jugadores y dibuja el primer movimiento.');
  });

  const btnDeshacer = $('tj-undo');
  if (btnDeshacer) {
    btnDeshacer.addEventListener('click', () => {
      const p = paso();
      if (!(p.shapes || []).length) { aviso('No hay nada dibujado en este paso.'); return; }
      p.shapes.pop();
      pintarDibujo(p.shapes);
      aviso('Trazo deshecho.');
    });
  }
  const btnLimpiar = $('tj-clear');
  if (btnLimpiar) {
    btnLimpiar.addEventListener('click', () => {
      const p = paso();
      if (!(p.shapes || []).length) { aviso('No hay nada dibujado en este paso.'); return; }
      if (!window.confirm('¿Borrar todo el dibujo de este paso?')) return;
      p.shapes = [];
      pintarDibujo(p.shapes);
      aviso('Dibujo borrado. Las fichas siguen donde estaban.');
    });
  }

  // --- reproducir ---
  // Los pasos son los fotogramas: se interpola la posición de las fichas y el dibujo de cada paso
  // se ve mientras dura su tramo. Es la misma animación del Planteamiento.
  let animando = false;
  const reproducir = async () => {
    if (estado.pasos.length < 2) { aviso('Hacen falta al menos dos pasos para reproducir.'); return; }
    animando = true;
    const vuelta = estado.i;
    const btn = $('tj-play');
    if (btn) btn.textContent = '■ Parar';

    const interpolar = (a, b, t) => {
      const porId = new Map((b || []).map((p) => [String(p.id || p.code), p]));
      return (a || []).map((p) => {
        const fin = porId.get(String(p.id || p.code));
        if (!fin) return p;
        return { ...p, x_pct: p.x_pct + (fin.x_pct - p.x_pct) * t, y_pct: p.y_pct + (fin.y_pct - p.y_pct) * t };
      });
    };
    const suave = (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);
    const pintarFotograma = (starters, rival, shapes) => {
      Array.from(campo.querySelectorAll('.tj-token')).forEach((n) => n.remove());
      starters.forEach((f) => campo.appendChild(crearFicha(f, false)));
      rival.forEach((f) => campo.appendChild(crearFicha(f, true)));
      pintarDibujo(shapes);
    };

    for (let i = 0; i < estado.pasos.length - 1 && animando; i += 1) {
      const desde = estado.pasos[i];
      const hasta = estado.pasos[i + 1];
      const inicio = performance.now();
      const DURACION = 1200;
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => {
        const marco = (ahora) => {
          if (!animando) { resolve(); return; }
          const t = Math.min(1, (ahora - inicio) / DURACION);
          pintarFotograma(
            interpolar(desde.starters, hasta.starters, suave(t)),
            interpolar(desde.rival, hasta.rival, suave(t)),
            desde.shapes,
          );
          if (t < 1) requestAnimationFrame(marco); else resolve();
        };
        requestAnimationFrame(marco);
      });
      // eslint-disable-next-line no-await-in-loop
      if (animando) await new Promise((r) => setTimeout(r, 500));
    }

    animando = false;
    if (btn) btn.textContent = '▶ Reproducir';
    estado.i = vuelta;
    pintarCampo();
  };

  const btnPlay = $('tj-play');
  if (btnPlay) {
    btnPlay.addEventListener('click', () => {
      if (animando) { animando = false; return; }
      reproducir();
    });
  }

  // --- publicar a los jugadores ---
  // Guardar es para ti; publicar es mandársela al equipo y avisarles. Por eso son dos botones y no
  // uno: nadie quiere que cada retoque le suene el móvil a veinte chavales.
  const pintarPublicacion = () => {
    const nodo = $('tj-publish-state');
    const btn = $('tj-publish');
    const jugada = jugadas.find((j) => String(j.id) === String(estado.id));
    const publicada = !!(jugada && jugada.published);
    if (btn) btn.textContent = publicada ? 'Retirar del espacio del jugador' : 'Publicar a los jugadores';
    if (!nodo) return;
    if (!estado.id) nodo.textContent = 'Se guarda antes de publicar.';
    else if (publicada) nodo.textContent = 'Publicada: tus jugadores la ven en su espacio.';
    else nodo.textContent = 'Todavía no la ve nadie más que tú.';
  };

  const btnPublicar = $('tj-publish');
  if (btnPublicar) {
    btnPublicar.addEventListener('click', async () => {
      if (!estado.id) { aviso('Guarda la jugada antes de publicarla.'); return; }
      const jugada = jugadas.find((j) => String(j.id) === String(estado.id));
      const publicar = !(jugada && jugada.published);
      if (publicar && !window.confirm('¿Publicar «' + (jugada || {}).name + '» y avisar a los jugadores?')) return;
      try {
        const r = await fetch(URLS.publish, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
          body: JSON.stringify({ id: estado.id, publish: publicar }),
        });
        const d = await r.json();
        if (!d.ok) { aviso(d.error || 'No se pudo publicar.'); return; }
        if (jugada) jugada.published = d.published;
        pintarPublicacion();
        aviso(d.published
          ? (d.notified === 1
            ? 'Publicada. Avisado 1 jugador con cuenta.'
            : 'Publicada. Avisados ' + d.notified + ' jugadores con cuenta.')
          : 'Retirada del espacio del jugador.');
      } catch (e) {
        aviso('No se pudo publicar.');
      }
    });
  }

  // --- la jugada en la charla de un partido ---
  const selPartido = $('tj-match');
  if (selPartido) {
    leerJson('tj-partidos', []).forEach((p) => {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.label;
      selPartido.appendChild(o);
    });
  }
  const btnPartido = $('tj-match-add');
  if (btnPartido) {
    btnPartido.addEventListener('click', async () => {
      if (!estado.id) { aviso('Guarda la jugada antes de llevarla a un partido.'); return; }
      const partido = (selPartido || {}).value;
      if (!partido) { aviso('Elige a qué partido la llevas.'); return; }
      try {
        const r = await fetch(URLS.match, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
          body: JSON.stringify({ play_id: estado.id, match_id: partido }),
        });
        const d = await r.json();
        if (!d.ok) { aviso(d.error || 'No se pudo añadir al partido.'); return; }
        aviso('Añadida a la charla de ese partido (' + d.total + ' en total).');
      } catch (e) {
        aviso('No se pudo añadir al partido.');
      }
    });
  }

  // --- enlaces que necesitan la jugada guardada ---
  const conId = (url) => String(url || '').replace('/0/', '/' + estado.id + '/');
  const refrescarEnlaces = () => {
    const img = $('tj-image');
    const board = $('tj-board');
    const gif = $('tj-gif');
    [[img, URLS.image, 'Descargar imagen'],
     [gif, URLS.gif, 'Descargar animación (GIF)'],
     [board, URLS.board, 'Ver a pantalla completa']].forEach(([nodo, url, texto]) => {
      if (!nodo) return;
      if (!estado.id) {
        nodo.removeAttribute('href');
        nodo.textContent = texto + ' (guarda antes)';
      } else {
        nodo.href = conId(url);
        nodo.textContent = texto;
      }
    });
  };

  const selTipo = $('tj-kind');
  if (selTipo) {
    TIPOS.forEach((t) => {
      const o = document.createElement('option');
      o.value = t.key;
      o.textContent = t.name;
      selTipo.appendChild(o);
    });
    selTipo.value = estado.kind;
    const etiqueta = $('tj-kind-label');
    const refrescarTipo = () => {
      estado.kind = selTipo.value;
      if (etiqueta) etiqueta.textContent = (TIPOS.find((t) => t.key === estado.kind) || {}).name || '';
    };
    selTipo.addEventListener('change', refrescarTipo);
    refrescarTipo();
  }

  pintarHerramientas();
  pintarPasos();
  pintarSelectorPlan();
  pintarFiltro();
  pintarLista();
  pintarBanquillo();
  refrescarEnlaces();
  pintarPublicacion();
  const primeras = filtro ? jugadas.filter((j) => j.kind === filtro) : jugadas;
  if (filtro) { estado.kind = filtro; if (selTipo) { selTipo.value = filtro; selTipo.dispatchEvent(new Event('change')); } }
  if (primeras.length) cargarJugada(primeras[0]); else pintarCampo();
})();
