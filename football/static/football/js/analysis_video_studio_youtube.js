(function () {
  function byId(id) { return document.getElementById(id); }
  var videoId = Number((byId('vs-video-id') && byId('vs-video-id').value) || 0) || 0;
  var youtubeId = String((byId('vs-youtube-id') && byId('vs-youtube-id').value) || '').trim();
  var initialClipId = Number((byId('vs-initial-clip-id') && byId('vs-initial-clip-id').value) || 0) || 0;
  var clipsUrl = String((byId('vs-clips-url') && byId('vs-clips-url').value) || '').trim();
  var clipSaveUrl = String((byId('vs-clip-save-url') && byId('vs-clip-save-url').value) || '').trim();
  var clipDeleteUrl = String((byId('vs-clip-delete-url') && byId('vs-clip-delete-url').value) || '').trim();
  var assignUrl = String((byId('vs-assign-url') && byId('vs-assign-url').value) || '').trim();
  var csrf = '';
  try {
    var inp = document.querySelector('#vs-csrf input[name="csrfmiddlewaretoken"]');
    csrf = inp ? String(inp.value || '') : '';
  } catch (e) { csrf = ''; }

  var btnPlay = byId('vs-play');
  var btnPause = byId('vs-pause');
  var btnMarkIn = byId('vs-mark-in');
  var btnMarkOut = byId('vs-mark-out');
  var selSpeed = byId('vs-speed');
  var nowEl = byId('vs-now');
  var inLabel = byId('vs-in-label');
  var outLabel = byId('vs-out-label');
  var statusEl = byId('vs-status');

  var inInput = byId('vs-in-s');
  var outInput = byId('vs-out-s');
  var titleInput = byId('vs-clip-title');
  var collectionInput = byId('vs-clip-collection');
  var tagsInput = byId('vs-clip-tags');
  var notesInput = byId('vs-clip-notes');
  var btnSave = byId('vs-clip-save');
  var btnClear = byId('vs-clip-clear');
  var btnRefresh = byId('vs-clip-refresh');
  var clipStatus = byId('vs-clip-status');
  var clipsList = byId('vs-clips');
  var assignTeamSelect = byId('vs-assign-team');
  var assignBtn = byId('vs-assign-btn');

  var player = null;
  var tickTimer = 0;

  function setText(el, text) { if (el) el.textContent = String(text || ''); }
  function setStatus(text) { setText(statusEl, text || ''); }
  function setClipStatus(text) { setText(clipStatus, text || ''); }

  function fmtTime(sec) {
    var s = Math.max(0, Number(sec) || 0);
    var m = Math.floor(s / 60);
    var r = Math.floor(s - m * 60);
    return String(m) + ':' + String(r).padStart ? String(r).padStart(2, '0') : (r < 10 ? ('0' + r) : String(r));
  }

  function getNow() {
    if (!player) return 0;
    try {
      var t = player.getCurrentTime();
      return Number(t) || 0;
    } catch (e) {
      return 0;
    }
  }

  function setInOutLabels() {
    var inS = Number(inInput && inInput.value ? inInput.value : 0) || 0;
    var outS = Number(outInput && outInput.value ? outInput.value : 0) || 0;
    setText(inLabel, fmtTime(inS));
    setText(outLabel, fmtTime(outS));
  }

  function setIn(sec) {
    if (!inInput) return;
    inInput.value = String(Math.max(0, Math.round((Number(sec) || 0) * 10) / 10));
    setInOutLabels();
  }
  function setOut(sec) {
    if (!outInput) return;
    outInput.value = String(Math.max(0, Math.round((Number(sec) || 0) * 10) / 10));
    setInOutLabels();
  }

  function parseTags(raw) {
    var s = String(raw || '').trim();
    if (!s) return [];
    var parts = s.split(',');
    var out = [];
    for (var i = 0; i < parts.length; i += 1) {
      var t = String(parts[i] || '').trim();
      if (!t) continue;
      out.push(t.slice(0, 40));
      if (out.length >= 24) break;
    }
    return out;
  }

  function jsonPost(url, payload) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload || {})
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        return { ok: resp.ok, data: data };
      });
    });
  }

  function initAssign() {
    if (!assignUrl || !videoId || !assignTeamSelect || !assignBtn) return;
    assignBtn.addEventListener('click', function () {
      var targetTeamId = Number(assignTeamSelect.value || 0) || 0;
      if (!targetTeamId) {
        setStatus('Selecciona un equipo para asignar el vídeo.');
        return;
      }
      assignBtn.disabled = true;
      jsonPost(assignUrl, { video_id: videoId, team_id: targetTeamId })
        .then(function (res) {
          if (!res || !res.ok || !res.data || !res.data.ok) throw new Error((res.data && res.data.error) ? res.data.error : 'No se pudo asignar.');
          setStatus('Asignado. Recargando…');
          window.location.reload();
        })
        .catch(function (e) { setStatus((e && e.message) ? e.message : 'No se pudo asignar.'); })
        .finally(function () { assignBtn.disabled = false; });
    });
  }

  function loadClips() {
    if (!clipsUrl || !videoId) return Promise.resolve([]);
    var url = new URL(clipsUrl, window.location.href);
    url.searchParams.set('video_id', String(videoId));
    return fetch(url.toString(), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (resp) {
        return resp.json().catch(function () { return {}; }).then(function (data) {
          if (!resp.ok || !data || !data.ok) throw new Error((data && data.error) ? data.error : 'No se pudo cargar.');
          return Array.isArray(data.items) ? data.items : [];
        });
      });
  }

  function renderClips(items) {
    if (!clipsList) return;
    var clips = Array.isArray(items) ? items : [];
    if (!clips.length) {
      clipsList.innerHTML = '<div class="hint">No hay clips todavía.</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < clips.length; i += 1) {
      var c = clips[i] || {};
      var title = String(c.title || '').trim() || ('Clip ' + String(c.id || ''));
      var inS = Number(c.in_s || 0) || 0;
      var outS = Number(c.out_s || 0) || 0;
      var meta = fmtTime(inS) + ' → ' + (outS ? fmtTime(outS) : '…');
      var viewUrl = String(c.view_url || '').trim();
      html += ''
        + '<div class="row">'
        + '  <div style="display:flex; flex-direction:column; gap:0.15rem; min-width:0;">'
        + '    <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">' + escapeHtml(title) + '</strong>'
        + '    <small>' + escapeHtml(meta) + '</small>'
        + '  </div>'
        + '  <div style="display:flex; gap:0.35rem; flex-wrap:wrap; justify-content:flex-end;">'
        + '    <button type="button" class="button ghost" data-clip-jump="' + String(c.id || '') + '">Ir</button>'
        + (viewUrl ? ('<a class="button ghost" href="' + escapeAttr(viewUrl) + '">Ver</a>') : '')
        + '    <button type="button" class="button ghost" data-clip-edit="' + String(c.id || '') + '">Editar</button>'
        + '    <button type="button" class="button ghost" data-clip-del="' + String(c.id || '') + '">Borrar</button>'
        + '  </div>'
        + '</div>';
    }
    clipsList.innerHTML = html;

    var jumpBtns = clipsList.querySelectorAll('[data-clip-jump]');
    for (var j = 0; j < jumpBtns.length; j += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-jump') || 0) || 0;
          var clip = findClipById(clips, cid);
          if (!clip) return;
          jumpToClip(clip);
        });
      })(jumpBtns[j]);
    }
    var editBtns = clipsList.querySelectorAll('[data-clip-edit]');
    for (var k = 0; k < editBtns.length; k += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-edit') || 0) || 0;
          var clip = findClipById(clips, cid);
          if (!clip) return;
          fillFormFromClip(clip);
        });
      })(editBtns[k]);
    }
    var delBtns = clipsList.querySelectorAll('[data-clip-del]');
    for (var d = 0; d < delBtns.length; d += 1) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var cid = Number(btn.getAttribute('data-clip-del') || 0) || 0;
          if (!cid) return;
          if (!window.confirm('¿Borrar este clip?')) return;
          deleteClip(cid);
        });
      })(delBtns[d]);
    }

    if (initialClipId) {
      var initial = findClipById(clips, initialClipId);
      if (initial) {
        fillFormFromClip(initial);
        jumpToClip(initial);
      }
      initialClipId = 0;
    }
  }

  function findClipById(clips, id) {
    for (var i = 0; i < clips.length; i += 1) {
      if (Number(clips[i] && clips[i].id) === Number(id)) return clips[i];
    }
    return null;
  }

  function fillFormFromClip(c) {
    if (!c) return;
    try { if (titleInput) titleInput.value = String(c.title || '').trim(); } catch (e) {}
    try { if (collectionInput) collectionInput.value = String(c.collection || '').trim(); } catch (e) {}
    try { if (notesInput) notesInput.value = String(c.notes || '').trim(); } catch (e) {}
    try {
      var tags = Array.isArray(c.tags) ? c.tags : [];
      if (tagsInput) tagsInput.value = tags.join(', ');
    } catch (e2) {}
    setIn(Number(c.in_s || 0) || 0);
    setOut(Number(c.out_s || 0) || 0);
    try { clipsList && clipsList.setAttribute('data-edit-id', String(c.id || '')); } catch (e3) {}
    setClipStatus('Editando clip #' + String(c.id || ''));
  }

  function clearForm() {
    try { if (titleInput) titleInput.value = ''; } catch (e) {}
    try { if (collectionInput) collectionInput.value = ''; } catch (e) {}
    try { if (notesInput) notesInput.value = ''; } catch (e) {}
    try { if (tagsInput) tagsInput.value = ''; } catch (e) {}
    setIn(0); setOut(0);
    try { clipsList && clipsList.removeAttribute('data-edit-id'); } catch (e2) {}
    setClipStatus('');
  }

  function jumpToClip(c) {
    if (!player || !c) return;
    var start = Number(c.in_s || 0) || 0;
    try {
      player.seekTo(Math.max(0, start), true);
    } catch (e) {}
    try { player.playVideo(); } catch (e2) {}
    setStatus('Reproduciendo clip…');
    var out = Number(c.out_s || 0) || 0;
    if (out && out > start) {
      stopAt(out);
    }
  }

  var stopAtTimer = 0;
  function stopAt(outSec) {
    try { if (stopAtTimer) window.clearInterval(stopAtTimer); } catch (e) {}
    stopAtTimer = window.setInterval(function () {
      if (!player) return;
      var now = getNow();
      if (now >= outSec - 0.05) {
        try { player.pauseVideo(); } catch (e2) {}
        try { window.clearInterval(stopAtTimer); } catch (e3) {}
        stopAtTimer = 0;
        setStatus('Fin de clip.');
      }
    }, 80);
  }

  function deleteClip(id) {
    if (!clipDeleteUrl) return;
    if (!id) return;
    setClipStatus('Borrando…');
    if (btnSave) btnSave.disabled = true;
    return jsonPost(clipDeleteUrl, { id: id })
      .then(function (r) {
        if (!r.ok || !r.data || !r.data.ok) throw new Error((r.data && r.data.error) ? r.data.error : 'No se pudo borrar.');
        clearForm();
        return refreshClips();
      })
      .catch(function (e) {
        setClipStatus(String((e && e.message) || 'Error borrando.'));
      })
      .finally(function () {
        if (btnSave) btnSave.disabled = false;
      });
  }

  function refreshClips() {
    setClipStatus('');
    return loadClips()
      .then(function (items) { renderClips(items); return items; })
      .catch(function (e) {
        var msg = String((e && e.message) || 'No se pudo cargar.');
        if (clipsList) clipsList.innerHTML = '<div class="hint">' + escapeHtml(msg) + '</div>';
      });
  }

  function saveClip() {
    if (!clipSaveUrl || !videoId) return;
    var title = String(titleInput && titleInput.value ? titleInput.value : '').trim();
    var collection = String(collectionInput && collectionInput.value ? collectionInput.value : '').trim();
    var notes = String(notesInput && notesInput.value ? notesInput.value : '').trim();
    var tags = parseTags(tagsInput && tagsInput.value ? tagsInput.value : '');
    var inS = Number(inInput && inInput.value ? inInput.value : 0) || 0;
    var outS = Number(outInput && outInput.value ? outInput.value : 0) || 0;
    if (outS && outS < inS) { var tmp = inS; inS = outS; outS = tmp; }
    var editId = 0;
    try { editId = Number(clipsList && clipsList.getAttribute('data-edit-id') ? clipsList.getAttribute('data-edit-id') : 0) || 0; } catch (e) { editId = 0; }

    if (!title) title = 'Clip';

    setClipStatus('Guardando…');
    if (btnSave) btnSave.disabled = true;
    return jsonPost(clipSaveUrl, {
      id: editId || undefined,
      video_id: videoId,
      title: title,
      collection: collection,
      in_s: inS,
      out_s: outS,
      tags: tags,
      notes: notes,
      overlay: {}
    }).then(function (r) {
      if (!r.ok || !r.data || !r.data.ok) throw new Error((r.data && r.data.error) ? r.data.error : 'No se pudo guardar.');
      var savedId = Number(r.data.id || 0) || 0;
      setClipStatus('OK · clip #' + String(savedId));
      try { clipsList && clipsList.setAttribute('data-edit-id', String(savedId)); } catch (e2) {}
      return refreshClips();
    }).catch(function (e) {
      setClipStatus(String((e && e.message) || 'Error guardando.'));
    }).finally(function () {
      if (btnSave) btnSave.disabled = false;
    });
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, '&quot;');
  }

  function tick() {
    if (!player) return;
    var now = getNow();
    setText(nowEl, fmtTime(now));
  }

  function startTicker() {
    try { if (tickTimer) window.clearInterval(tickTimer); } catch (e) {}
    tickTimer = window.setInterval(tick, 250);
  }

  function setPlaying(isPlaying) {
    if (btnPlay) btnPlay.hidden = isPlaying;
    if (btnPause) btnPause.hidden = !isPlaying;
  }

  function loadYouTubeApi() {
    return new Promise(function (resolve) {
      if (window.YT && window.YT.Player) { resolve(); return; }
      var tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      tag.async = true;
      var first = document.getElementsByTagName('script')[0];
      if (first && first.parentNode) first.parentNode.insertBefore(tag, first);
      else document.head.appendChild(tag);
      window.onYouTubeIframeAPIReady = function () { resolve(); };
    });
  }

  function initPlayer() {
    if (!youtubeId) { setStatus('Falta youtube_id.'); return; }
    loadYouTubeApi().then(function () {
      try {
        player = new window.YT.Player('vs-youtube-player', {
          videoId: youtubeId,
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1
          },
          events: {
            onReady: function () {
              setStatus('Listo.');
              startTicker();
              setInOutLabels();
              refreshClips();
            },
            onStateChange: function (ev) {
              var st = Number(ev && ev.data) || 0;
              // 1 playing, 2 paused, 0 ended
              if (st === 1) setPlaying(true);
              else if (st === 2 || st === 0) setPlaying(false);
            }
          }
        });
      } catch (e) {
        setStatus('No se pudo inicializar el player.');
      }
    });
  }

  if (btnPlay) btnPlay.addEventListener('click', function () {
    if (!player) return;
    try { player.playVideo(); } catch (e) {}
  });
  if (btnPause) btnPause.addEventListener('click', function () {
    if (!player) return;
    try { player.pauseVideo(); } catch (e) {}
  });
  if (selSpeed) selSpeed.addEventListener('change', function () {
    if (!player) return;
    var v = Number(selSpeed.value || 1) || 1;
    try { player.setPlaybackRate(v); } catch (e) {}
  });
  if (btnMarkIn) btnMarkIn.addEventListener('click', function () {
    setIn(getNow());
  });
  if (btnMarkOut) btnMarkOut.addEventListener('click', function () {
    setOut(getNow());
  });
  if (inInput) inInput.addEventListener('input', setInOutLabels);
  if (outInput) outInput.addEventListener('input', setInOutLabels);
  if (btnSave) btnSave.addEventListener('click', function () { saveClip(); });
  if (btnClear) btnClear.addEventListener('click', function () { clearForm(); });
  if (btnRefresh) btnRefresh.addEventListener('click', function () { refreshClips(); });

  initAssign();
  initPlayer();
})();
