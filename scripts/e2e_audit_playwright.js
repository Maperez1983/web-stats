/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function timestampId() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function safeName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/https?:\/\//g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 80) || 'page';
}

function normalizePath(href, baseUrl) {
  if (!href) return '';
  const raw = String(href).trim();
  if (!raw || raw === '#' || raw.startsWith('javascript:') || raw.startsWith('mailto:')) return '';
  try {
    const url = new URL(raw, baseUrl);
    return url.pathname + (url.search || '');
  } catch (err) {
    if (raw.startsWith('/')) return raw;
    return '';
  }
}

function shouldSkipPath(pathname) {
  const p = String(pathname || '').trim();
  if (!p || !p.startsWith('/')) return true;
  // Evitar acciones destructivas / no idempotentes durante auditoría.
  const bannedFragments = [
    '/logout',
    '/admin/',
    '/platform/clear',
    '/delete',
    '/eliminar',
    '/reiniciar',
    '/reset',
    '/finalizar',
    '/guardar/',
    '/save/',
  ];
  if (bannedFragments.some((frag) => p.includes(frag))) return true;
  // Evita estáticos/media.
  if (p.startsWith('/static') || p.startsWith('/media/')) return true;
  return false;
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
  const convocationCount = Math.max(1, Math.min(parseInt(process.env.E2E_CONVOCATION_COUNT || '11', 10) || 11, 30));
  const outDir =
    process.env.E2E_OUT_DIR ||
    path.join(process.cwd(), 'artifacts', 'e2e-audit', timestampId());

  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  page.setDefaultNavigationTimeout(60000);

  const globalLog = {
    started_at: new Date().toISOString(),
    base_url: baseUrl,
    username,
    pages: [],
    actions: [],
  };

  async function screenshot(label) {
    const file = path.join(outDir, `${String(label).padStart(2, '0')}-${safeName(label)}.png`);
    try {
      await page.screenshot({ path: file, fullPage: true });
    } catch (err) {
      // ignore
    }
    return file;
  }

  async function gotoTracked(urlPath, { label, waitUntil = 'domcontentloaded', timeoutMs = 60000 } = {}) {
    const targetUrl = urlPath.startsWith('http') ? urlPath : `${baseUrl}${urlPath}`;
    const entry = {
      label: label || urlPath,
      url: targetUrl,
      final_url: '',
      status: 0,
      content_type: '',
      started_at: new Date().toISOString(),
      duration_ms: 0,
      console: [],
      page_errors: [],
      request_failed: [],
      bad_responses: [],
      screenshot: '',
      ok: true,
    };

    const onConsole = (msg) => {
      if (!msg) return;
      const type = msg.type();
      if (type === 'error' || type === 'warning') {
        entry.console.push({ type, text: msg.text() });
      }
    };
    const onPageError = (err) => {
      entry.page_errors.push({ message: String(err && err.message ? err.message : err) });
    };
    const onRequestFailed = (req) => {
      try {
        entry.request_failed.push({
          url: req.url(),
          method: req.method(),
          failure: (req.failure() || {}).errorText || '',
        });
      } catch (err) {
        // ignore
      }
    };
    const onResponse = (resp) => {
      try {
        const status = resp.status();
        const url = resp.url();
        if (status >= 400 && url.startsWith(baseUrl)) {
          entry.bad_responses.push({ status, url });
        }
      } catch (err) {
        // ignore
      }
    };

    page.on('console', onConsole);
    page.on('pageerror', onPageError);
    page.on('requestfailed', onRequestFailed);
    page.on('response', onResponse);

    const t0 = Date.now();
    try {
      const resp = await page.goto(targetUrl, { waitUntil, timeout: timeoutMs });
      // Mejor esfuerzo: muchos endpoints mantienen requests abiertos (keepalive), así que no bloqueamos por networkidle.
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => null);
      entry.final_url = page.url();
      entry.status = resp ? resp.status() : 0;
      entry.content_type = resp ? String(resp.headers()['content-type'] || '') : '';
    } catch (err) {
      entry.ok = false;
      entry.page_errors.push({ message: String(err && err.message ? err.message : err) });
    }
    entry.duration_ms = Date.now() - t0;
    entry.screenshot = await screenshot(globalLog.pages.length + 1);

    page.off('console', onConsole);
    page.off('pageerror', onPageError);
    page.off('requestfailed', onRequestFailed);
    page.off('response', onResponse);

    globalLog.pages.push(entry);
    return entry;
  }

  async function login() {
    const loginEntry = await gotoTracked('/login/', { label: 'login' });
    if (!loginEntry.ok) return loginEntry;

    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);

    const t0 = Date.now();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle', timeout: 60000 }).catch(() => null),
      page.click('button[type="submit"]'),
    ]);
    const duration = Date.now() - t0;
    const afterUrl = page.url();
    const ok = !afterUrl.includes('/login');
    globalLog.actions.push({
      action: 'login',
      ok,
      duration_ms: duration,
      after_url: afterUrl,
    });
    await screenshot('login-after');
    return { ok };
  }

  async function getCsrfToken() {
    const cookies = await context.cookies().catch(() => []);
    const csrfCookie = (cookies || []).find((c) => c && c.name === 'csrftoken');
    return csrfCookie ? csrfCookie.value : '';
  }

  async function extractTaskIdFromPage() {
    const html = await page.content().catch(() => '');
    const match = html.match(/const\s+taskId\s*=\s*'(\d+)'/);
    if (match) return parseInt(match[1], 10);
    const match2 = html.match(/taskId\s*=\s*\"(\d+)\"/);
    if (match2) return parseInt(match2[1], 10);
    return null;
  }

  async function createBuilderTask(builderPath, { labelPrefix } = {}) {
    const start = Date.now();
    const entry = {
      action: `${labelPrefix || 'builder'}_create_task`,
      ok: false,
      duration_ms: 0,
      details: {},
    };
    try {
      await gotoTracked(builderPath, { label: `${labelPrefix || builderPath}-new-task` });
      const title = `E2E ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`;
      await page.fill('input[name="draw_task_title"]', title);
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => null),
        page.click('button[type="submit"].primary'),
      ]);
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => null);
      const taskId = await extractTaskIdFromPage();
      const afterUrl = page.url();
      entry.ok = !afterUrl.includes('/login') && Boolean(taskId);
      entry.details = { title, task_id: taskId, after_url: afterUrl };
      await screenshot(`${labelPrefix || 'builder'}-created`);
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function updatePlayerPhoto(playerId) {
    const start = Date.now();
    const entry = { action: 'player_update_photo', ok: false, duration_ms: 0, details: {} };
    try {
      const pid = Number(playerId || 0) || 1;
      await gotoTracked(`/player/${pid}/?tab=general`, { label: `player-${pid}` });
      const before = await page.getAttribute('aside.player-photo-card img', 'src').catch(() => '');
      const photoPath =
        process.env.E2E_PHOTO_PATH ||
        path.join(process.cwd(), 'static', 'football', 'images', 'cdb-logo.png');
      if (!fs.existsSync(photoPath)) {
        entry.details = { error: `No existe E2E_PHOTO_PATH: ${photoPath}` };
      } else {
        const fileInput = page.locator('input[type="file"][name="player_photo"]');
        await fileInput.setInputFiles(photoPath);
        const profileFormSubmit = page.locator('form', {
          has: page.locator('input[name="form_action"][value="profile"]'),
        }).getByRole('button', { name: /guardar ficha/i });
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => null),
          profileFormSubmit.click(),
        ]);
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => null);
        const after = await page.getAttribute('aside.player-photo-card img', 'src').catch(() => '');
        entry.ok = Boolean(after) && after !== before;
        entry.details = { before, after };
        await screenshot('player-photo-updated');
      }
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function saveConvocation() {
    const start = Date.now();
    const entry = { action: 'convocation_save', ok: false, duration_ms: 0, details: {} };
    try {
      await gotoTracked('/convocatoria/', { label: 'convocation' });
      await page.waitForSelector('.roster-card', { timeout: 20000 }).catch(() => null);
      // Recoge N ids de jugadores (sirve para convocatoria + 11 inicial + registro acciones).
      const selectedIds = await page
        .evaluate((count) => {
          const ids = [];
          document.querySelectorAll('.roster-card[data-player-id]').forEach((card) => {
            const id = String(card.getAttribute('data-player-id') || '').trim();
            if (!id) return;
            if (ids.length < count) ids.push(id);
          });
          return ids;
        }, convocationCount)
        .catch(() => []);

      // Guardado robusto: usamos el mismo endpoint que el frontend (evita depender de mensajes UI).
      const csrf = await getCsrfToken();
      const matchInfo = await page
        .evaluate(() => ({
          opponent: String(document.getElementById('match-opponent-manual')?.value || document.getElementById('match-opponent-select')?.value || '').trim(),
          round: String(document.getElementById('match-round')?.value || '').trim(),
          date: String(document.getElementById('match-date')?.value || '').trim(),
          time: String(document.getElementById('match-time')?.value || '').trim(),
          location: String(document.getElementById('match-location-manual')?.value || document.getElementById('match-location-select')?.value || '').trim(),
        }))
        .catch(() => ({}));

      const payload = {
        players: Array.isArray(selectedIds) ? selectedIds : [],
        match_info: matchInfo || {},
      };
      const resp = await context.request.post(`${baseUrl}/convocatoria/save/`, {
        data: payload,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
          Referer: `${baseUrl}/convocatoria/`,
        },
      });
      const data = await resp.json().catch(() => ({}));
      entry.ok = resp.ok() && Boolean(data && data.saved);
      entry.details = { status: resp.status(), response: data, selected_count: (payload.players || []).length, selected_ids: payload.players || [] };
      await screenshot('convocation-saved');
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function saveInitialEleven(matchId, playerIds) {
    const start = Date.now();
    const entry = { action: 'initial_eleven_save', ok: false, duration_ms: 0, details: {} };
    try {
      const starters = (playerIds || []).slice(0, 11).map((id) => ({ id: String(id) }));
      const bench = (playerIds || []).slice(11, 18).map((id) => ({ id: String(id) }));
      const csrf = await getCsrfToken();
      const url = matchId ? `${baseUrl}/registro-acciones/lineup/save/?match_id=${encodeURIComponent(String(matchId))}` : `${baseUrl}/registro-acciones/lineup/save/`;
      const resp = await context.request.post(url, {
        data: { lineup: { starters, bench } },
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
          Referer: `${baseUrl}/coach/11-inicial/`,
        },
      });
      const data = await resp.json().catch(() => ({}));
      entry.ok = resp.ok() && Boolean(data && data.saved);
      entry.details = { status: resp.status(), response: data, starters: starters.length, bench: bench.length };
      await gotoTracked('/coach/11-inicial/', { label: 'initial-eleven' });
      await screenshot('initial-eleven-after');
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function recordAndDeleteMatchAction(matchId, playerId) {
    const start = Date.now();
    const entry = { action: 'match_action_record_delete', ok: false, duration_ms: 0, details: {} };
    try {
      const csrf = await getCsrfToken();
      const recordUrl = matchId
        ? `${baseUrl}/registro-acciones/guardar/?match_id=${encodeURIComponent(String(matchId))}`
        : `${baseUrl}/registro-acciones/guardar/`;
      const recordResp = await context.request.post(recordUrl, {
        form: {
          match_id: matchId ? String(matchId) : '',
          player: String(playerId || ''),
          action_type: 'Pase',
          result: 'OK',
          minute: '0',
          zone: '',
          observation: 'E2E',
        },
        headers: {
          'X-CSRFToken': csrf,
          Referer: `${baseUrl}/registro-acciones/${matchId ? `?match_id=${encodeURIComponent(String(matchId))}` : ''}`,
        },
      });
      const recorded = await recordResp.json().catch(() => ({}));
      const eventId = recorded && (recorded.id || recorded.event_id);
      if (!recordResp.ok() || !eventId) {
        entry.details = { record_status: recordResp.status(), record_response: recorded };
        entry.ok = false;
      } else {
        const deleteUrl = matchId
          ? `${baseUrl}/registro-acciones/eliminar/?match_id=${encodeURIComponent(String(matchId))}`
          : `${baseUrl}/registro-acciones/eliminar/`;
        const delResp = await context.request.post(deleteUrl, {
          form: { event_id: String(eventId) },
          headers: {
            'X-CSRFToken': csrf,
            Referer: `${baseUrl}/registro-acciones/${matchId ? `?match_id=${encodeURIComponent(String(matchId))}` : ''}`,
          },
        });
        const deleted = await delResp.json().catch(() => ({}));
        entry.ok = delResp.ok() && Boolean(deleted && deleted.deleted);
        entry.details = {
          record_status: recordResp.status(),
          record_id: eventId,
          delete_status: delResp.status(),
          delete_response: deleted,
        };
      }
      await gotoTracked(matchId ? `/registro-acciones/?match_id=${encodeURIComponent(String(matchId))}` : '/registro-acciones/', { label: 'match-actions' });
      await screenshot('match-actions-after');
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function collectInternalLinks() {
    const hrefs = await page
      .$$eval('a[href]', (anchors) => anchors.map((a) => a.getAttribute('href') || ''))
      .catch(() => []);
    const out = new Set();
    hrefs.forEach((href) => {
      const p = normalizePath(href, baseUrl);
      if (!p) return;
      if (shouldSkipPath(p)) return;
      out.add(p);
    });
    return Array.from(out);
  }

  async function crawlSite(seedPaths, { maxPages = 80 } = {}) {
    const visited = new Set();
    const queue = Array.from(new Set((seedPaths || []).filter(Boolean)));
    const crawlEntry = { action: 'crawl', ok: true, duration_ms: 0, details: {} };
    const start = Date.now();

    while (queue.length && globalLog.pages.length < maxPages) {
      const next = queue.shift();
      const pathOnly = normalizePath(next, baseUrl) || next;
      if (!pathOnly || visited.has(pathOnly)) continue;
      if (shouldSkipPath(pathOnly)) continue;
      visited.add(pathOnly);
      const entry = await gotoTracked(pathOnly, { label: `crawl:${pathOnly}` });
      // Si caemos en login, no seguimos expandiendo desde esa página.
      if (!entry.ok || (entry.final_url || '').includes('/login')) continue;
      if (String(entry.content_type || '').toLowerCase().includes('application/pdf')) continue;
      if (!String(entry.content_type || '').toLowerCase().includes('text/html')) continue;
      // Expandir enlaces internos.
      const links = await collectInternalLinks();
      links.forEach((p) => {
        if (!visited.has(p) && !queue.includes(p) && globalLog.pages.length + queue.length < maxPages * 3) {
          queue.push(p);
        }
      });
    }

    crawlEntry.duration_ms = Date.now() - start;
    crawlEntry.details = { visited: visited.size, queued_left: queue.length, max_pages: maxPages };
    globalLog.actions.push(crawlEntry);
    return crawlEntry;
  }

  const loginResult = await login();
  if (!loginResult.ok) {
    globalLog.actions.push({ action: 'abort', reason: 'login_failed' });
  } else {
    // Descubre un player_id real si existe.
    let playerId = 1;
    await gotoTracked('/players/', { label: 'players' });
    const playerLinks = await page
      .$$eval('a[href^="/player/"]', (anchors) => anchors.map((a) => a.getAttribute('href') || ''))
      .catch(() => []);
    const firstPlayer = (playerLinks || []).map((h) => String(h || '')).find((h) => /\/player\/\d+\//.test(h));
    if (firstPlayer) {
      const match = String(firstPlayer).match(/\/player\/(\d+)\//);
      if (match) playerId = parseInt(match[1], 10);
    }

    // Acciones críticas (crean datos y validan que no haya logout involuntario).
    const createdTaskStudio = await createBuilderTask('/task-studio/tareas/nueva/', { labelPrefix: 'task-studio' });
    const createdSessionCoach = await createBuilderTask('/coach/sesiones/tareas/nueva/', { labelPrefix: 'sessions-coach' });
    const createdSessionGk = await createBuilderTask('/coach/sesiones/porteros/tareas/nueva/', { labelPrefix: 'sessions-gk' });
    const createdSessionFit = await createBuilderTask('/coach/sesiones/preparacion-fisica/tareas/nueva/', { labelPrefix: 'sessions-fit' });
    const convocationSaved = await saveConvocation();
    const matchId = convocationSaved?.details?.response?.match_id || null;
    const convocationPlayerIds = convocationSaved?.details?.selected_ids || [];
    if (matchId && convocationPlayerIds.length) {
      await saveInitialEleven(matchId, convocationPlayerIds);
      await recordAndDeleteMatchAction(matchId, convocationPlayerIds[0]);
    }
    await updatePlayerPhoto(playerId);

    const seedPaths = [
      '/',
      '/api/dashboard/?fresh=1',
      '/api/session/keepalive/',
      '/players/',
      `/player/${playerId}/`,
      `/player/${playerId}/pdf/`,
      '/coach/',
      '/coach/plantilla/',
      '/coach/cards/',
      '/coach/11-inicial/',
      '/convocatoria/',
      '/registro-acciones/',
      '/task-studio/',
      '/task-studio/perfil/',
      '/task-studio/plantilla/',
      '/platform/',
      '/platform/?tab=users',
      '/platform/?tab=workspaces',
      '/coach/roles/entrenador/',
      '/coach/roles/porteros/',
      '/coach/roles/preparacion-fisica/',
      '/coach/roles/abp/',
      '/coach/abp/pizarra/',
      '/coach/sesiones/',
      '/coach/sesiones/porteros/',
      '/coach/sesiones/preparacion-fisica/',
      '/coach/multas/',
      '/coach/analisis/',
      '/coach/estadisticas-manuales/',
      '/incidencias/',
    ];

    if (createdTaskStudio?.details?.task_id) {
      const id = createdTaskStudio.details.task_id;
      seedPaths.push(`/task-studio/tareas/${id}/pdf/`);
      seedPaths.push(`/task-studio/tareas/${id}/preview/`);
    }
    [createdSessionCoach, createdSessionGk, createdSessionFit].forEach((created) => {
      const id = created?.details?.task_id;
      if (!id) return;
      seedPaths.push(`/coach/sesiones/tarea/${id}/pdf/`);
      seedPaths.push(`/coach/sesiones/tarea/${id}/preview/`);
    });

    if (convocationSaved && convocationSaved.ok) {
      seedPaths.push('/convocatoria/pdf/');
    }

    const maxPages = Math.max(20, Math.min(parseInt(process.env.E2E_MAX_PAGES || '90', 10) || 90, 220));
    await crawlSite(seedPaths, { maxPages });
  }

  globalLog.finished_at = new Date().toISOString();
  const reportPath = path.join(outDir, 'report.json');
  fs.writeFileSync(reportPath, JSON.stringify(globalLog, null, 2));

  const slowPages = globalLog.pages
    .filter((p) => (p.duration_ms || 0) >= 2000)
    .map((p) => ({ label: p.label, duration_ms: p.duration_ms, url: p.url }));
  const bad = globalLog.pages
    .filter((p) => (p.bad_responses || []).length || (p.page_errors || []).length || (p.request_failed || []).length)
    .map((p) => ({
      label: p.label,
      url: p.url,
      bad_responses: p.bad_responses || [],
      page_errors: p.page_errors || [],
      request_failed: p.request_failed || [],
      console: p.console || [],
    }));

  const summary = {
    out_dir: outDir,
    report: reportPath,
    pages: globalLog.pages.length,
    actions: globalLog.actions.length,
    slow_pages: slowPages,
    pages_with_errors: bad,
  };
  fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));

  console.log(`E2E audit listo: ${outDir}`);
  console.log(`Reporte: ${reportPath}`);
  console.log(`Páginas: ${globalLog.pages.length} · Acciones: ${globalLog.actions.length}`);
  if (slowPages.length) console.log(`Lentas (>=2s): ${slowPages.length}`);
  if (bad.length) console.log(`Con errores: ${bad.length}`);

  await browser.close();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
