/* Captura rápida · registro de acciones para el dedo.
 *
 * El sitio manda: tocas el campo y los jugadores salen DONDE pones el dedo, ordenados por
 * cercanía. Todo lo que se registra va al mismo endpoint que el registro clásico, así que
 * un partido capturado aquí es indistinguible de uno capturado allí.
 *
 * Sin cobertura no se pierde nada: lo que no sale va a una cola en el propio dispositivo
 * y se reenvía sola al volver la red.
 */
(function () {
  var nodo = document.getElementById('capture-config');
  if (!nodo) return;
  var CFG = JSON.parse(nodo.textContent);

  var SELLOS = CFG.sellos || [];
  var RECHACE = {};
  (CFG.rechace || []).forEach(function (a) { RECHACE[a] = 1; });
  var DETALLE = CFG.detalle || {};
  var IMPACTO = CFG.impacto || [];
  // null = sin tope (amistosos, y categorías con cambios rodados). Entonces el contador cuenta
  // los hechos en vez de los que quedan, y nunca bloquea.
  var CAMBIOS_MAX = (CFG.cambios === null || CFG.cambios === undefined) ? null : CFG.cambios;
  var MINUTOS_PARTE = CFG.minutos_parte || 45;
  function pintaCambios() {
    var e = document.getElementById('quedan-cambios');
    if (!e) return;
    e.textContent = CAMBIOS_MAX === null ? cambiosHechos : Math.max(0, CAMBIOS_MAX - cambiosHechos);
    var eti = e.parentElement;
    if (eti) eti.firstChild.textContent = CAMBIOS_MAX === null ? 'Cambios hechos' : 'Cambios';
  }

  var once = (CFG.once || []).map(function (j) { return Object.assign({}, j); });
  var banquillo = (CFG.banquillo || []).map(function (j) { return Object.assign({}, j); });

  // ---------------------------------------------------------------- guardado
  var COLA_KEY = 'webstats:captura:cola:' + (CFG.match_id || '0');
  var cola = [];
  try { cola = JSON.parse(localStorage.getItem(COLA_KEY) || '[]'); } catch (e) { cola = []; }

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function uid() {
    return 'cap-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }
  function guardaCola() {
    try { localStorage.setItem(COLA_KEY, JSON.stringify(cola)); } catch (e) {}
    var pill = document.getElementById('cola-offline');
    var n = document.getElementById('cola-n');
    if (n) n.textContent = cola.length;
    if (pill) pill.classList.toggle('visible', cola.length > 0);
  }
  function envia(url, campos) {
    var cuerpo = new URLSearchParams();
    Object.keys(campos).forEach(function (k) {
      if (campos[k] !== undefined && campos[k] !== null && campos[k] !== '') cuerpo.set(k, campos[k]);
    });
    if (CFG.match_id) cuerpo.set('match_id', CFG.match_id);
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest',
                 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json' },
      credentials: 'same-origin',
      body: cuerpo.toString()
    }).then(function (r) {
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    });
  }
  // Guarda una acción. Si el envío falla, la acción NO se pierde: queda en la cola del
  // dispositivo con su uid, y el servidor la deduplica cuando por fin llega.
  function guardar(reg, url, campos) {
    campos.client_event_uid = reg.uid;
    return envia(url, campos)
      .then(function (data) { reg.id = data.id; reg.pendiente = false; repinta(); return data; })
      .catch(function () {
        reg.pendiente = true;
        cola.push({ uid: reg.uid, url: url, campos: campos });
        guardaCola();
        repinta();
        return null;
      });
  }
  function vaciaCola() {
    if (!cola.length) return;
    var pendientes = cola.slice();
    cola = [];
    guardaCola();
    pendientes.forEach(function (item) {
      envia(item.url, item.campos)
        .then(function (data) {
          var r = registros.find(function (x) { return x.uid === item.uid; });
          if (r) { r.id = data.id; r.pendiente = false; }
          repinta();
        })
        .catch(function () { cola.push(item); guardaCola(); });
    });
  }
  window.addEventListener('online', vaciaCola);
  setInterval(function () { if (navigator.onLine) vaciaCola(); }, 20000);
  guardaCola();

  function borraEnServidor(reg) {
    // Si nunca llegó a salir, basta con sacarla de la cola.
    var i = cola.findIndex(function (x) { return x.uid === reg.uid; });
    if (i >= 0) { cola.splice(i, 1); guardaCola(); return; }
    if (!reg.id) return;
    if (reg.rival && !reg.corner) {
      envia(CFG.urls.rival, { event_id: reg.id, borrar: '1' }).catch(function () {});
    } else {
      envia(CFG.urls.borrar, { event_id: reg.id }).catch(function () {});
    }
  }

  // ------------------------------------------------------------------ estado
  var registros = [];
  var sello = SELLOS[0], punto = null, zona = '', todos = false;
  var segundos = 0, parte = 1, corriendo = true;
  var modoABP = null, modoCaida = null, modoSuceso = null;
  var ultimoLanzador = null, amarillasPor = {}, cambiosHechos = 0, saliendo = null;
  var trazo = null, arrastrando = null;

  // Lo ya guardado en el servidor entra como historial: al recargar en el descanso no se pierde.
  (CFG.eventos || []).forEach(function (ev) {
    registros.push({
      uid: 'srv-' + ev.id, id: ev.id,
      min: ev.minute === null || ev.minute === undefined ? '' : String(ev.minute),
      n: ev.player && ev.player.number !== '--' ? ev.player.number : '',
      quien: ev.player && ev.player.name ? ev.player.name : 'Equipo',
      accion: ev.action, res: ev.result, zona: ev.zone, parte: ev.period || 1,
      tono: '', previo: true
    });
  });

  var campo = document.getElementById('campo'), rejilla = document.getElementById('rejilla');
  var cercanosEl = document.getElementById('cercanos'), sellosEl = document.getElementById('sellos');
  var listaEl = document.getElementById('lista'), relojEl = document.getElementById('reloj');
  var pasoEl = document.getElementById('paso'), zonaTxt = document.getElementById('zona-txt');
  var tercioTxt = document.getElementById('tercio-txt');
  var pistaRes = document.getElementById('pista-res'), btnPorteria = document.getElementById('btn-porteria');
  var btnParte = document.getElementById('btn-parte');

  function minutoActual() { return Math.floor(segundos / 60); }

  // El reloj sobrevive a una recarga: en un partido de verdad se recarga por lo que sea
  // (pantalla bloqueada, batería, un toque mal dado) y volver al minuto 0 falsea todo lo
  // que se registre después.
  var RELOJ_KEY = 'webstats:captura:reloj:' + (CFG.match_id || '0');
  (function restauraReloj() {
    try {
      var guardado = JSON.parse(localStorage.getItem(RELOJ_KEY) || 'null');
      if (!guardado) return;
      segundos = guardado.segundos || 0;
      parte = guardado.parte || 1;
      corriendo = !!guardado.corriendo;
      if (corriendo && guardado.ts) segundos += Math.floor((Date.now() - guardado.ts) / 1000);
    } catch (e) {}
  })();
  function guardaReloj() {
    try {
      localStorage.setItem(RELOJ_KEY, JSON.stringify({
        segundos: segundos, parte: parte, corriendo: corriendo, ts: Date.now()
      }));
    } catch (e) {}
  }

  function pintaParte() {
    btnParte.textContent = corriendo ? (parte + 'ª parte') : (parte === 1 ? 'Descanso · ir a 2ª' : 'Final');
    btnParte.classList.toggle('descanso', !corriendo);
  }
  btnParte.addEventListener('click', function () {
    if (corriendo) { corriendo = false; }
    else if (parte === 1) { parte = 2; segundos = MINUTOS_PARTE * 60; corriendo = true; }
    pintaParte(); pinta(); guardaReloj();
  });
  // Tocar el reloj lo pone en hora: el árbitro nunca pita cuando tú abres la pantalla.
  relojEl.addEventListener('click', function () {
    var dicho = window.prompt('¿Por qué minuto va el partido?', String(minutoActual()));
    if (dicho === null) return;
    var m = parseInt(String(dicho).replace(/[^0-9]/g, ''), 10);
    if (isNaN(m) || m < 0 || m > 130) return;
    segundos = m * 60;
    parte = m >= 45 ? 2 : 1;
    pintaParte(); pinta(); guardaReloj();
  });
  setInterval(function () { if (corriendo) { segundos++; pinta(); if (segundos % 10 === 0) guardaReloj(); } }, 1000);
  window.addEventListener('pagehide', guardaReloj);
  document.addEventListener('visibilitychange', guardaReloj);
  function pinta() {
    var m = Math.floor(segundos / 60), s = segundos % 60;
    relojEl.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }
  pintaParte(); pinta();

  var TER = ['Defensa', 'Medio', 'Ataque'], CAR = ['Izquierda', 'Centro', 'Derecha'];
  function zonaDe(p) {
    if (!p) return '';
    return TER[Math.min(2, Math.floor(p.x / 33.34))] + ' ' + CAR[Math.min(2, Math.floor(p.y / 33.34))];
  }
  function tercioDe(z) {
    if (!z) return '—';
    if (z === 'Portería') return 'Defensa';
    if (z.indexOf('Defensa') === 0) return 'Defensa';
    if (z.indexOf('Medio') === 0) return 'Construcción';
    return 'Ataque';
  }
  for (var i = 0; i < 9; i++) rejilla.appendChild(document.createElement('div'));

  SELLOS.forEach(function (s) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'sello'; b.textContent = s.id;
    b.setAttribute('aria-pressed', s.id === sello.id ? 'true' : 'false');
    b.addEventListener('click', function () {
      sello = s;
      pistaRes.textContent = pistaDe(s);
      Array.prototype.forEach.call(sellosEl.children, function (o) {
        o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
      });
    });
    sellosEl.appendChild(b);
  });

  (CFG.abp || []).forEach(function (a) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'abp-btn si';
    b.innerHTML = a.etiqueta.replace('\n', '<br>');
    b.addEventListener('click', function () {
      modoCaida = null; modoSuceso = null;
      if (a.equipo) {
        // El córner es acción de equipo: no lleva jugador, va de un toque.
        var reg = nuevoRegistro({ n: '', quien: 'EQUIPO', accion: a.accion, res: 'A FAVOR', tono: 'bien', zona: zona });
        guardar(reg, CFG.urls.guardar, {
          action_type: a.accion, result: 'A FAVOR', zone: zona, minute: minutoActual(),
          period: parte, team_side: 'for'
        });
        cierra(); limpiaPunto(); repinta();
        return;
      }
      modoABP = { accion: a.accion, res: 'A FAVOR' };
      pasoEl.innerHTML = '¿Quién lo <b>lanza</b>?';
      abreCercanos(50, 46, { x: 50, y: 50 });
    });
    document.getElementById('abp').appendChild(b);
  });

  (CFG.rival || []).forEach(function (r) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'riv-btn';
    b.innerHTML = r.emoji + '<span>' + r.etiqueta + '</span>';
    b.addEventListener('click', function () {
      modoCaida = null; modoSuceso = null; modoABP = null;
      var reg = nuevoRegistro({
        n: '', quien: 'RIVAL', accion: r.etiqueta, res: r.res, tono: 'mal', zona: '', rival: true
      });
      if (r.equipo) {
        // El córner en contra ya existe en la taxonomía del registro: va por la vía normal,
        // que es la que alimenta el acta. Se marca como córner para el marcador de arriba.
        reg.corner = true;
        guardar(reg, CFG.urls.guardar, {
          action_type: r.accion, result: 'EN CONTRA', zone: '', minute: minutoActual(),
          period: parte, team_side: 'against'
        });
      } else {
        guardar(reg, CFG.urls.rival, {
          action_type: r.accion, result: r.res, minute: minutoActual(), period: parte
        });
      }
      cierra(); limpiaPunto(); repinta();
    });
    document.getElementById('rival-fila').appendChild(b);
  });

  function pintaOnce() {
    Array.prototype.forEach.call(campo.querySelectorAll('.pb-chip'), function (c) { c.remove(); });
    once.forEach(function (j) {
      var c = document.createElement('div');
      c.className = 'pb-chip'; c.dataset.n = j.n;
      c.style.left = j.x + '%'; c.style.top = j.y + '%';
      var foto = j.foto
        ? '<img src="' + j.foto + '" alt="" />'
        : '<img src="" alt="" style="display:none" />';
      c.innerHTML = '<span class="pb-avatar">' + foto + '<span class="pb-num">' + j.n + '</span></span>' +
                    '<span class="pb-name">' + j.nom + '</span>';
      campo.appendChild(c);
    });
  }
  pintaOnce();

  function pistaDe(s) {
    if (!s.botones.length) return 'Un toque en el dorsal y queda registrada';
    // Si el botón lleva palabra en vez de emoji, la palabra ya lo dice todo: repetir el
    // resultado detrás sólo hace ruido ("FORZADA MAL NO FORZADA MAL").
    var t = s.botones.map(function (b) { return b.e ? (b.e + ' ' + b.res) : b.t; }).join('   ');
    return s.suelto ? (t + '   ·   sólo el dorsal = ' + s.suelto) : t;
  }
  pistaRes.textContent = pistaDe(sello);

  function cierra() { cercanosEl.classList.remove('abierto'); cercanosEl.innerHTML = ''; todos = false; }

  function botonQuien(j) {
    var fila = document.createElement('div');
    fila.className = 'quien-fila';
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'quien';
    b.innerHTML = '<b>' + j.n + '</b><span>' + j.nom + '</span>';
    if (modoABP && ultimoLanzador === j.n) {
      var eti = document.createElement('span');
      eti.className = 'habitual'; eti.textContent = 'de siempre';
      b.appendChild(eti);
    }
    if (modoSuceso && modoSuceso.tipo === 'amarilla' && amarillasPor[j.n]) {
      var av = document.createElement('span');
      av.className = 'habitual'; av.style.background = '#c04a3c'; av.style.color = '#fff';
      av.textContent = 'ya tiene una'; b.appendChild(av);
    }
    b.addEventListener('click', function (ev) {
      ev.stopPropagation();
      if (modoSuceso) return registraSuceso(j);
      if (modoCaida) return registraCaida(j);
      registrar(j, 'suelto');
    });
    fila.appendChild(b);
    // En una tarjeta, un cambio o una caída la pregunta es otra y valorar no pinta nada
    // (un ✅ ahí registraría la acción equivocada). El ABP sí se valora: lo hay bien puesto
    // y mal ejecutado.
    var valoraciones = modoABP ? (CFG.abp_botones || [])
      : ((modoSuceso || modoCaida) ? [] : sello.botones);
    valoraciones.forEach(function (bt) {
      var v = document.createElement('button');
      v.type = 'button';
      v.className = 'valorar ' + (bt.tono === 'mal' ? 'no' : (bt.tono === 'medio' ? 'medio' : 'si'));
      v.innerHTML = bt.e ? bt.e : '<span class="sentido">' + bt.t + '</span>';
      v.title = bt.res;
      v.addEventListener('click', function (ev) { ev.stopPropagation(); registrar(j, bt); });
      fila.appendChild(v);
    });
    return fila;
  }

  var abiertoEn = 0;
  function abreCercanos(px, py, p) {
    cercanosEl.innerHTML = '';
    var lista;
    if (modoSuceso) {
      lista = (modoSuceso.tipo === 'entra') ? banquillo.slice() : once.slice().sort(function (a, b) { return a.n - b.n; });
      if (modoSuceso.tipo !== 'entra') lista = lista.slice(0, 6);
    } else if (modoCaida) {
      lista = once.slice().sort(function (a, b) {
        var da = Math.pow(a.x - p.x, 2) + Math.pow(a.y - p.y, 2);
        var db = Math.pow(b.x - p.x, 2) + Math.pow(b.y - p.y, 2);
        return da - db;
      }).slice(0, 4);
    } else if (modoABP) {
      // El portero no lanza los córners: fuera de la lista.
      lista = once.filter(function (o) { return !o.gk; }).slice(0, 6);
    } else {
      lista = once.slice().sort(function (a, b) {
        var da = Math.pow(a.x - p.x, 2) + Math.pow(a.y - p.y, 2);
        var db = Math.pow(b.x - p.x, 2) + Math.pow(b.y - p.y, 2);
        return da - db;
      }).slice(0, todos ? once.length : 6);
    }

    if (!modoSuceso && !modoCaida && !modoABP) {
      var tira = document.createElement('div');
      tira.className = 'tira-sellos';
      SELLOS.forEach(function (sl) {
        var t = document.createElement('button');
        t.type = 'button';
        t.className = 'mini-sello' + (sl.id === sello.id ? ' puesto' : '');
        t.textContent = sl.id;
        t.addEventListener('click', function (ev) {
          ev.stopPropagation();
          sello = sl; pistaRes.textContent = pistaDe(sl);
          Array.prototype.forEach.call(sellosEl.children, function (o) {
            o.setAttribute('aria-pressed', o.textContent === sl.id ? 'true' : 'false');
          });
          abreCercanos(px, py, p);
        });
        tira.appendChild(t);
      });
      cercanosEl.appendChild(tira);
    }

    lista.forEach(function (j) { cercanosEl.appendChild(botonQuien(j)); });

    if (modoCaida) {
      var rival = document.createElement('button');
      rival.type = 'button'; rival.className = 'mas rival';
      rival.textContent = 'La coge el rival';
      rival.addEventListener('click', function (ev) { ev.stopPropagation(); registraCaida(null); });
      cercanosEl.appendChild(rival);
      var sigue = document.createElement('button');
      sigue.type = 'button'; sigue.className = 'mas';
      sigue.textContent = 'Sigue el juego · sin caída';
      sigue.addEventListener('click', function (ev) {
        ev.stopPropagation(); modoCaida = null; cierra(); limpiaPunto();
      });
      cercanosEl.appendChild(sigue);
    } else if (!modoSuceso && !todos) {
      var mas = document.createElement('button');
      mas.type = 'button'; mas.className = 'mas';
      mas.textContent = '··· Otros jugadores';
      mas.addEventListener('click', function (ev) { ev.stopPropagation(); todos = true; abreCercanos(px, py, p); });
      cercanosEl.appendChild(mas);
    }

    var pista = document.createElement('div');
    pista.className = 'cercanos-pista';
    pista.textContent = modoSuceso || modoCaida || modoABP ? 'Toca al jugador' : pistaDe(sello);
    cercanosEl.appendChild(pista);
    cercanosEl.style.left = px + '%'; cercanosEl.style.top = py + '%';
    cercanosEl.classList.add('abierto');
    encajaEnElCampo();
    abiertoEn = Date.now();
  }
  // El panel se coloca donde tocas, pero no puede salirse del campo: si tocas junto a la banda
  // se iba fuera de la pantalla y sus botones dejaban de existir para el dedo.
  function encajaEnElCampo() {
    var c = campo.getBoundingClientRect();
    var p = cercanosEl.getBoundingClientRect();
    if (!c.width || !p.width) return;
    var margen = 6;
    var izq = p.left - c.left, arr = p.top - c.top;
    var dx = 0, dy = 0;
    if (izq < margen) dx = margen - izq;
    else if (izq + p.width > c.width - margen) dx = (c.width - margen) - (izq + p.width);
    if (arr < margen) dy = margen - arr;
    else if (arr + p.height > c.height - margen) dy = (c.height - margen) - (arr + p.height);
    if (!dx && !dy) return;
    var actualX = parseFloat(cercanosEl.style.left) || 50;
    var actualY = parseFloat(cercanosEl.style.top) || 50;
    cercanosEl.style.left = (actualX + (dx / c.width) * 100) + '%';
    cercanosEl.style.top = (actualY + (dy / c.height) * 100) + '%';
  }
  // El panel sale DEBAJO del dedo: el mismo toque genera después un click de compatibilidad
  // que caería sobre el botón recién aparecido y registraría una acción que nadie ha pedido.
  // Se mata en origen (touchend del campo) y el reloj queda de red.
  campo.addEventListener('touchend', function (ev) { ev.preventDefault(); }, { passive: false });
  cercanosEl.addEventListener('click', function (ev) {
    if (Date.now() - abiertoEn < 120) { ev.stopPropagation(); ev.preventDefault(); }
  }, true);

  function pctDe(ev) {
    var r = campo.getBoundingClientRect();
    return { x: ((ev.clientX - r.left) / r.width) * 100, y: ((ev.clientY - r.top) / r.height) * 100 };
  }
  function ponMarca(p) {
    var vieja = campo.querySelector('.marca-punto'); if (vieja) vieja.remove();
    var d = document.createElement('div'); d.className = 'marca-punto';
    d.style.left = p.x + '%'; d.style.top = p.y + '%'; campo.appendChild(d);
  }
  function dibujaTrazo(a, b, visible) {
    var l = document.getElementById('linea-trazo');
    l.setAttribute('x1', a.x); l.setAttribute('y1', a.y);
    l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
    l.setAttribute('opacity', visible ? '0.95' : '0');
  }
  // Cambio de orientación: girar el juego al lado CONTRARIO. No vale el carril de al lado.
  function esCambioDeOrientacion(a, b) {
    var carril = function (y) { return Math.min(2, Math.floor(y / 33.34)); };
    return Math.abs(carril(a.y) - carril(b.y)) === 2 || Math.abs(b.y - a.y) > 50;
  }
  campo.addEventListener('pointerdown', function (ev) {
    if (!sello.traza || modoABP) return;
    arrastrando = pctDe(ev);
  });
  campo.addEventListener('pointermove', function (ev) {
    if (!arrastrando) return;
    dibujaTrazo(arrastrando, pctDe(ev), true);
  });
  campo.addEventListener('pointerup', function (ev) {
    var p = pctDe(ev);
    if (sello.traza && arrastrando) {
      var d = Math.hypot(p.x - arrastrando.x, p.y - arrastrando.y);
      trazo = d > 6 ? { de: arrastrando, a: p } : null;
      if (trazo) dibujaTrazo(trazo.de, trazo.a, true); else dibujaTrazo(p, p, false);
      punto = arrastrando;
      arrastrando = null;
    } else {
      trazo = null; punto = p; dibujaTrazo(p, p, false);
    }
    zona = zonaDe(punto);
    ponMarca(punto);
    zonaTxt.textContent = zona + (trazo ? ' → ' + zonaDe(trazo.a) : '');
    tercioTxt.textContent = tercioDe(zona);
    btnPorteria.setAttribute('aria-pressed', 'false');
    pasoEl.innerHTML = 'Ahora <b>quién</b>';
    abreCercanos(Math.min(82, Math.max(18, punto.x)), Math.min(74, Math.max(26, punto.y - 14)), punto);
  });

  btnPorteria.addEventListener('click', function () {
    zona = zona === 'Portería' ? '' : 'Portería';
    btnPorteria.setAttribute('aria-pressed', zona === 'Portería' ? 'true' : 'false');
    zonaTxt.textContent = zona || 'sin marcar'; tercioTxt.textContent = tercioDe(zona);
    if (zona) { punto = { x: 8, y: 50 }; abreCercanos(20, 40, punto); pasoEl.innerHTML = 'Ahora <b>quién</b>'; }
  });

  function resalta(n) {
    var c = campo.querySelector('.pb-chip[data-n="' + n + '"]');
    if (!c) return;
    c.classList.add('resaltado');
    setTimeout(function () { c.classList.remove('resaltado'); }, 900);
  }
  function limpiaPunto() {
    var m = campo.querySelector('.marca-punto'); if (m) m.remove();
    Array.prototype.forEach.call(rejilla.children, function (d) { d.classList.remove('marcada'); });
    punto = null; zona = ''; trazo = null; dibujaTrazo({ x: 0, y: 0 }, { x: 0, y: 0 }, false);
    zonaTxt.textContent = 'sin marcar'; tercioTxt.textContent = '—';
    btnPorteria.setAttribute('aria-pressed', 'false');
    pasoEl.innerHTML = 'Toca <b>dónde</b> ha pasado';
  }

  function nuevoRegistro(datos) {
    var reg = Object.assign({ uid: uid(), min: String(minutoActual()), parte: parte, pendiente: true }, datos);
    registros.unshift(reg);
    return reg;
  }

  function abreSuceso(tipo, texto) {
    modoSuceso = { tipo: tipo };
    modoCaida = null; modoABP = null;
    pasoEl.innerHTML = texto;
    abreCercanos(50, 46, { x: 50, y: 50 });
  }
  function registraSuceso(j) {
    var t = modoSuceso.tipo;
    if (t === 'amarilla' || t === 'roja') {
      var segunda = t === 'amarilla' && !!amarillasPor[j.n];
      if (t === 'amarilla') amarillasPor[j.n] = (amarillasPor[j.n] || 0) + 1;
      var reg = nuevoRegistro({
        n: j.n, quien: j.nom,
        accion: segunda ? 'Doble amarilla · roja' : (t === 'amarilla' ? 'Tarjeta amarilla' : 'Tarjeta roja'),
        res: segunda || t === 'roja' ? 'ROJA' : 'AMARILLA', tono: 'mal', zona: '',
        efecto: t === 'amarilla' ? { tipo: 'amarilla', n: j.n } : null
      });
      // La 2ª amarilla la decide el servidor (ve todas las tarjetas del partido, no sólo las de esta pantalla).
      guardar(reg, CFG.urls.guardar, {
        player: j.id,
        action_type: t === 'amarilla' ? 'Tarjeta Amarilla' : 'Tarjeta Roja',
        zone: t === 'amarilla' ? 'Tarjeta Amarilla' : 'Tarjeta Roja',
        result: t === 'amarilla' ? 'Amarilla' : 'Roja',
        minute: minutoActual(), period: parte, team_side: 'for'
      });
    } else if (t === 'sale') {
      saliendo = j;
      modoSuceso = { tipo: 'entra' };
      pasoEl.innerHTML = 'Sale #' + j.n + ' ' + j.nom + ' · ¿<b>quién entra</b>?';
      abreCercanos(50, 46, { x: 50, y: 50 });
      return;
    } else if (t === 'entra') {
      cambiosHechos++;
      pintaCambios();
      var idx = once.findIndex(function (o) { return o.n === saliendo.n; });
      var hueco = idx >= 0 ? { x: once[idx].x, y: once[idx].y } : { x: 50, y: 50 };
      var sale = idx >= 0 ? once.splice(idx, 1)[0] : null;
      var ib = banquillo.findIndex(function (o) { return o.n === j.n; });
      if (ib >= 0) banquillo.splice(ib, 1);
      once.push({ id: j.id, n: j.n, nom: j.nom, foto: j.foto, x: hueco.x, y: hueco.y });
      if (sale) banquillo.unshift(sale);
      pintaOnce();
      var regEntra = nuevoRegistro({
        n: j.n, quien: j.nom, accion: 'Cambio', res: 'ENTRA', tono: 'bien', zona: '',
        tras: '#' + saliendo.n + ' ' + saliendo.nom + ' · sale',
        efecto: { tipo: 'cambio', entra: { n: j.n, nom: j.nom }, sale: sale }
      });
      // Un cambio son dos eventos, como en el registro clásico: el que sale y el que entra.
      var quienSale = saliendo;
      guardar(regEntra, CFG.urls.guardar, {
        player: j.id, action_type: 'Sustitución', zone: 'Sustitución Entrante', result: 'Entrada',
        minute: minutoActual(), period: parte, team_side: 'for'
      });
      if (quienSale && quienSale.id) {
        var regSale = { uid: uid() };
        envia(CFG.urls.guardar, {
          player: quienSale.id, action_type: 'Sustitución', zone: 'Sustitución Saliente', result: 'Salida',
          minute: minutoActual(), period: parte, team_side: 'for', client_event_uid: regSale.uid
        }).then(function (data) { regEntra.idSale = data.id; })
          .catch(function () {
            cola.push({ uid: regSale.uid, url: CFG.urls.guardar, campos: {
              player: quienSale.id, action_type: 'Sustitución', zone: 'Sustitución Saliente', result: 'Salida',
              minute: minutoActual(), period: parte, team_side: 'for', client_event_uid: regSale.uid } });
            guardaCola();
          });
      }
      saliendo = null;
    }
    modoSuceso = null; cierra(); limpiaPunto(); repinta();
  }

  function registraCaida(j) {
    var reg = nuevoRegistro({
      n: j ? j.n : '', quien: j ? j.nom : 'RIVAL',
      accion: 'Caída', res: j ? 'GANADO' : 'PERDIDO', tono: j ? 'bien' : 'mal',
      zona: modoCaida.zona, tras: modoCaida.tras
    });
    if (j) {
      guardar(reg, CFG.urls.guardar, {
        player: j.id, action_type: 'Caída', result: 'GANADO', zone: modoCaida.zona,
        observation: modoCaida.tras, minute: minutoActual(), period: parte, team_side: 'for'
      });
      resalta(j.n);
    } else {
      // La coge el rival: la caída es nuestra (la generamos), pero se pierde.
      guardar(reg, CFG.urls.rival, {
        action_type: 'Caída perdida', result: 'PERDIDO', minute: minutoActual(), period: parte
      });
      reg.rival = true;
    }
    modoCaida = null; cierra(); limpiaPunto(); repinta();
  }

  function registrar(j, elegido) {
    if (modoABP) {
      ultimoLanzador = j.n;
      var resAbp = (elegido !== 'suelto' && elegido.res) ? elegido.res : modoABP.res;
      var regAbp = nuevoRegistro({
        n: j.n, quien: j.nom, accion: modoABP.accion, res: resAbp,
        tono: resAbp === 'MAL' ? 'malo' : 'bueno', zona: zona, lanza: true, playerId: j.id
      });
      guardar(regAbp, CFG.urls.guardar, {
        player: j.id, action_type: modoABP.accion, result: resAbp, zone: zona,
        minute: minutoActual(), period: parte, team_side: 'for'
      });
      modoABP = null; cierra(); limpiaPunto(); repinta();
      return;
    }
    var res, tono;
    if (elegido === 'suelto') { res = sello.suelto || 'sin resultado'; tono = sello.suelto ? 'neutro' : ''; }
    else { res = elegido.res; tono = elegido.tono === 'si' ? 'bueno' : (elegido.tono === 'medio' ? 'medio' : 'malo'); }
    // Hay botones que no cambian el resultado sino la acción (pérdida forzada / no forzada).
    var accion = (elegido !== 'suelto' && elegido.accion) ? elegido.accion : sello.accion;
    if (trazo && (accion === 'Pase' || accion === 'Pase largo') && esCambioDeOrientacion(trazo.de, trazo.a)) {
      accion = 'Cambio de orientación';
    }
    var reg = nuevoRegistro({
      n: j.n, quien: j.nom, playerId: j.id, accion: accion, res: res, tono: tono, zona: zona,
      hasta: trazo ? zonaDe(trazo.a) : ''
    });
    guardar(reg, CFG.urls.guardar, {
      player: j.id, action_type: accion, result: res === 'sin resultado' ? 'NEUTRAL' : res,
      zone: zona, minute: minutoActual(), period: parte, team_side: 'for',
      observation: trazo ? ('hasta ' + zonaDe(trazo.a)) : ''
    });
    resalta(j.n);
    // Si ha entrado, no hay rechace: el balón sale del juego y no se pregunta la caída.
    if (RECHACE[accion] && res !== 'GOL') {
      modoCaida = { tras: '#' + j.n + ' ' + j.nom + ' · ' + accion, zona: zona };
      pasoEl.innerHTML = 'Segunda jugada · ¿<b>quién coge la caída</b>?';
      abreCercanos(Math.min(82, Math.max(18, (punto ? punto.x : 50))),
                   Math.min(74, Math.max(26, (punto ? punto.y : 50) - 14)), punto || { x: 50, y: 50 });
      trazo = null; dibujaTrazo({ x: 0, y: 0 }, { x: 0, y: 0 }, false);
      repinta();
      return;
    }
    cierra(); limpiaPunto(); repinta();
  }

  function necesitaDetalle(r) {
    if (r.rival || r.previo || r.accion === 'Cambio' || r.res === 'AMARILLA' || r.res === 'ROJA') return false;
    var campos = DETALLE[r.accion];
    if (!campos) return false;
    return !r.detalle;
  }
  function cuenta(f) { return registros.filter(f).length; }

  function kpis() {
    var mio = function (r) { return !r.rival; };
    var disparos = cuenta(function (r) { return mio(r) && r.accion === 'Disparo'; });
    var goles = cuenta(function (r) { return mio(r) && r.accion === 'Disparo' && r.res === 'GOL'; });
    var ap = cuenta(function (r) { return mio(r) && r.accion === 'Disparo' && r.res === 'AP'; });
    // Duelo de suelo y duelo aéreo son dos datos, pero el marcador de arriba mira el total:
    // lo que quieres de un vistazo es si estás ganando la disputa, no dónde.
    var esDuelo = function (r) { return r.accion === 'Duelo' || r.accion === 'Duelo aéreo'; };
    var duelos = cuenta(function (r) { return mio(r) && esDuelo(r); });
    var duelosG = cuenta(function (r) { return mio(r) && esDuelo(r) && r.res === 'GANADO'; });
    var aereos = cuenta(function (r) { return mio(r) && r.accion === 'Duelo aéreo'; });
    var aereosG = cuenta(function (r) { return mio(r) && r.accion === 'Duelo aéreo' && r.res === 'GANADO'; });
    var perdF = cuenta(function (r) { return mio(r) && r.accion === 'Pérdida forzada'; });
    var perdNF = cuenta(function (r) { return mio(r) && r.accion === 'Pérdida no forzada'; });
    var pases = cuenta(function (r) { return mio(r) && (r.accion === 'Pase' || r.accion === 'Pase largo' || r.accion === 'Pase a la espalda' || r.accion === 'Cambio de orientación'); });
    var pasesOK = cuenta(function (r) { return mio(r) && (r.accion === 'Pase' || r.accion === 'Pase largo' || r.accion === 'Pase a la espalda' || r.accion === 'Cambio de orientación') && r.res === 'OK'; });
    var largos = cuenta(function (r) { return mio(r) && r.accion === 'Pase largo'; });
    var segG = cuenta(function (r) { return r.accion === 'Caída' && r.res === 'GANADO'; });
    var segP = cuenta(function (r) { return r.accion === 'Caída' && r.res === 'PERDIDO'; });
    // El % de segunda jugada se mide sobre TODOS los duelos generados, no sólo sobre las
    // caídas que se llegaron a disputar: un duelo que no genera segunda también cuenta.
    var segBase = duelos;
    var cf = cuenta(function (r) { return mio(r) && r.accion.indexOf('Saque de esquina') === 0 && r.res === 'A FAVOR'; });
    var fc = cuenta(function (r) { return mio(r) && r.accion === 'Falta' && r.res === 'EN CONTRA'; });
    var fr = cuenta(function (r) { return mio(r) && r.accion === 'Falta' && r.res === 'A FAVOR'; });
    var rGoles = cuenta(function (r) { return r.rival && r.res === 'GOL'; });
    var rDisp = cuenta(function (r) { return r.rival && (r.accion === 'Disparo' || r.res === 'GOL'); });
    var rCorn = cuenta(function (r) { return r.rival && r.corner; });
    var rTarj = cuenta(function (r) { return r.rival && (r.res === 'Amarilla' || r.res === 'Roja'); });
    var nTarj = cuenta(function (r) { return mio(r) && (r.res === 'AMARILLA' || r.res === 'ROJA'); });
    var duelosP = duelos - duelosG;
    var pon = function (id, v) { var e = document.getElementById(id); if (e) e.textContent = v; };
    var pareja = function (id, a, b) { var e = document.getElementById(id); if (e) e.innerHTML = a + '<i>–' + b + '</i>'; };
    pareja('k-goles', goles, rGoles);
    pareja('k-disparos', disparos, rDisp);
    pareja('k-corners', cf, rCorn);
    pareja('k-tarjetas', nTarj, rTarj);
    pon('k-duelos', duelos ? Math.round(duelosG * 100 / duelos) + '%' : '—');
    pon('k-duelos-crudo', duelosG + '–' + duelosP);
    pon('k-segundas', segBase ? Math.round(segG * 100 / segBase) + '%' : '—');
    pon('k-segundas-crudo', segG + '–' + segP);
    pon('h-riv-goles', rGoles); pon('h-riv-disparos', rDisp);
    pon('h-riv-corners', rCorn); pon('h-riv-tarjetas', rTarj);
    pon('h-disparos', disparos); pon('h-ap', ap); pon('h-goles', goles);
    pon('h-corner-f', cf);
    pon('h-corner-c', rCorn);
    pon('h-espalda', cuenta(function (r) { return mio(r) && r.accion === 'Pase a la espalda'; }));
    pon('h-cambios', cuenta(function (r) { return mio(r) && r.accion === 'Cambio de orientación'; }));
    pon('h-duelos', duelos); pon('h-duelos-g', duelosG);
    pon('h-aereos', aereos + ' · ' + aereosG + ' ganados');
    pon('h-perd-f', perdF); pon('h-perd-nf', perdNF);
    pon('h-pases', pases); pon('h-pases-ok', pasesOK); pon('h-largos', largos);
    pon('h-seg-g', segG); pon('h-seg-p', segP);
    pon('h-seg-pct', segBase ? Math.round(segG * 100 / segBase) + '%' : '—');
    pon('h-robos', cuenta(function (r) { return mio(r) && r.accion === 'Robo'; }));
    pon('h-faltas-c', fc); pon('h-faltas-r', fr);
    pon('h-amarillas', cuenta(function (r) { return mio(r) && r.res === 'AMARILLA'; }));
    pon('h-rojas', cuenta(function (r) { return mio(r) && r.res === 'ROJA'; }));
    pon('h-cambios-libres', CAMBIOS_MAX === null ? 'sin tope' : Math.max(0, CAMBIOS_MAX - cambiosHechos));
    pon('h-total', registros.length);
    var porJugador = {};
    registros.forEach(function (r) {
      if (!r.n) return;
      porJugador[r.n] = porJugador[r.n] || { n: r.n, nom: r.quien, c: 0 };
      porJugador[r.n].c++;
    });
    var top = Object.keys(porJugador).map(function (k) { return porJugador[k]; })
      .sort(function (a, b) { return b.c - a.c; }).slice(0, 5);
    var cont = document.getElementById('h-top');
    if (!cont) return;
    cont.innerHTML = top.length ? '' : '<span class="vacio-top">Sin acciones todavía.</span>';
    top.forEach(function (t) {
      var d = document.createElement('span'); d.className = 'top-jug';
      d.innerHTML = '#' + t.n + ' ' + t.nom + ' <i>' + t.c + '</i>';
      cont.appendChild(d);
    });
  }

  function repinta() {
    kpis();
    var bd = document.getElementById('btn-deshacer');
    if (bd) bd.disabled = !registros.filter(function (r) { return !r.previo; }).length;
    var pd = document.getElementById('pendientes-det');
    if (pd) pd.textContent = registros.filter(function (r) { return necesitaDetalle(r); }).length;
    listaEl.innerHTML = '';
    if (!registros.length) {
      var v = document.createElement('div'); v.className = 'vacio';
      v.textContent = 'Aún no has registrado nada.';
      listaEl.appendChild(v);
    }
    registros.slice(0, 6).forEach(function (r) {
      var d = document.createElement('div'); d.className = 'registro';
      var res = r.tono ? '<span class="res ' + r.tono + '">' + r.res + '</span>' : '<span>' + r.res + '</span>';
      var quien = r.n ? ('#' + r.n + ' ' + r.quien + (r.lanza ? ' lanza' : '')) : r.quien;
      var donde = r.zona ? (r.zona + (r.hasta ? ' → ' + r.hasta : '')) : 'sin zona';
      if (r.tras) donde = 'tras ' + r.tras;
      if (r.pendiente) donde += ' · sin enviar';
      d.innerHTML = '<span class="min">' + r.min + "'</span><b>" + quien + '</b><span>' + r.accion + '</span>' +
                    res + '<span>' + donde + '</span>';
      listaEl.appendChild(d);
    });
  }

  function deshacer() {
    var i = registros.findIndex(function (r) { return !r.previo; });
    if (i < 0) return;
    var r = registros.splice(i, 1)[0];
    borraEnServidor(r);
    if (r.idSale) envia(CFG.urls.borrar, { event_id: r.idSale }).catch(function () {});
    if (r.efecto && r.efecto.tipo === 'cambio') {
      cambiosHechos = Math.max(0, cambiosHechos - 1);
      pintaCambios();
      var ie = once.findIndex(function (o) { return o.n === r.efecto.entra.n; });
      var entra = ie >= 0 ? once.splice(ie, 1)[0] : null;
      if (entra) banquillo.unshift({ id: entra.id, n: entra.n, nom: entra.nom, foto: entra.foto });
      if (r.efecto.sale) {
        var ib = banquillo.findIndex(function (o) { return o.n === r.efecto.sale.n; });
        if (ib >= 0) banquillo.splice(ib, 1);
        once.push(r.efecto.sale);
      }
      pintaOnce();
    }
    if (r.efecto && r.efecto.tipo === 'amarilla') {
      amarillasPor[r.efecto.n] = Math.max(0, (amarillasPor[r.efecto.n] || 1) - 1);
      if (!amarillasPor[r.efecto.n]) delete amarillasPor[r.efecto.n];
    }
    modoCaida = null; modoSuceso = null; modoABP = null;
    cierra(); limpiaPunto(); repinta();
  }
  document.getElementById('btn-deshacer').addEventListener('click', deshacer);
  document.getElementById('btn-amarilla').addEventListener('click', function () { abreSuceso('amarilla', '🟨 ¿A <b>quién</b>?'); });
  document.getElementById('btn-roja').addEventListener('click', function () { abreSuceso('roja', '🟥 ¿A <b>quién</b>?'); });
  document.getElementById('btn-cambio').addEventListener('click', function () { abreSuceso('sale', '🔁 ¿Quién <b>sale</b>?'); });

  // La pasada de detalle escribe sobre la MISMA acción (no crea otra): matiz en la observación
  // e impacto por su endpoint.
  function guardaDetalle(r) {
    if (!r.id) return;
    envia(CFG.urls.actualizar, {
      event_id: r.id, action_type: r.accion, result: r.res, zone: r.zona,
      observation: [r.tras || '', r.detalle || ''].filter(Boolean).join(' · '),
      minute: r.min, period: r.parte, team_side: 'for', player: r.playerId || ''
    }).catch(function () {});
  }
  function guardaImpacto(r) {
    if (!r.id) return;
    envia(CFG.urls.impacto, { event_id: r.id, impact_code: r.impactoCode || '' }).catch(function () {});
  }

  function pintaDetalle() {
    var cont = document.getElementById('lista-detalle');
    cont.innerHTML = '';
    var pend = registros.filter(function (r) { return DETALLE[r.accion] && !r.rival && !r.previo; });
    if (!pend.length) {
      cont.innerHTML = '<div class="det-vacio">No hay nada que detallar todavía.</div>';
      return;
    }
    pend.forEach(function (r) {
      var fila = document.createElement('div'); fila.className = 'det-fila';
      var cab = document.createElement('div'); cab.className = 'det-cab';
      cab.innerHTML = '<span class="min">' + r.min + "'</span><b>#" + r.n + ' ' + r.quien + '</b><span>' +
                      r.accion + ' · ' + r.res + (r.zona ? ' · ' + r.zona : '') + '</span>';
      fila.appendChild(cab);
      var chips = document.createElement('div'); chips.className = 'det-chips';
      var def = DETALLE[r.accion];
      var et = document.createElement('span'); et.className = 'det-grupo'; et.textContent = def.titulo;
      chips.appendChild(et);
      (def.opciones || []).forEach(function (op) {
        var c = document.createElement('button');
        c.type = 'button'; c.className = 'det-chip' + (r.detalle === op ? ' puesto' : '');
        c.textContent = op;
        c.addEventListener('click', function () {
          r.detalle = (r.detalle === op) ? '' : op;
          guardaDetalle(r); pintaDetalle(); repinta();
        });
        chips.appendChild(c);
      });
      var eti = document.createElement('span'); eti.className = 'det-grupo'; eti.textContent = 'Impacto';
      chips.appendChild(eti);
      IMPACTO.forEach(function (im) {
        var c = document.createElement('button');
        c.type = 'button'; c.className = 'det-chip' + (r.impactoCode === im.code ? ' puesto' : '');
        c.textContent = im.label;
        c.addEventListener('click', function () {
          r.impactoCode = (r.impactoCode === im.code) ? '' : im.code;
          guardaImpacto(r); pintaDetalle();
        });
        chips.appendChild(c);
      });
      fila.appendChild(chips);
      cont.appendChild(fila);
    });
  }
  document.getElementById('btn-detalle').addEventListener('click', function () {
    pintaDetalle();
    document.getElementById('hoja-detalle').hidden = false;
  });
  document.getElementById('cerrar-detalle').addEventListener('click', function () {
    document.getElementById('hoja-detalle').hidden = true;
  });
  document.getElementById('abrir-kpis').addEventListener('click', function () {
    document.getElementById('hoja-kpis').hidden = false;
  });
  document.getElementById('cerrar-kpis').addEventListener('click', function () {
    document.getElementById('hoja-kpis').hidden = true;
  });

  pintaCambios();
  repinta();
  if (navigator.onLine) vaciaCola();
})();
