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

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
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

  async function gotoTracked(urlPath, { label, waitUntil = 'networkidle', timeoutMs = 60000 } = {}) {
    const targetUrl = urlPath.startsWith('http') ? urlPath : `${baseUrl}${urlPath}`;
    const entry = {
      label: label || urlPath,
      url: targetUrl,
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
      await page.goto(targetUrl, { waitUntil, timeout: timeoutMs });
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

  async function createTaskStudioTask() {
    const start = Date.now();
    const entry = { action: 'task_studio_create_task', ok: false, duration_ms: 0, details: {} };
    try {
      await gotoTracked('/task-studio/tareas/nueva/', { label: 'task-studio-new-task' });
      const title = `E2E ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`;
      await page.fill('input[name="draw_task_title"]', title);
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'networkidle', timeout: 60000 }).catch(() => null),
        page.click('button[type="submit"].primary'),
      ]);
      const afterUrl = page.url();
      entry.ok = !afterUrl.includes('/login');
      entry.details = { title, after_url: afterUrl };
      await screenshot('task-studio-created');
    } catch (err) {
      entry.ok = false;
      entry.details = { error: String(err && err.message ? err.message : err) };
    }
    entry.duration_ms = Date.now() - start;
    globalLog.actions.push(entry);
    return entry;
  }

  async function updatePlayerPhoto() {
    const start = Date.now();
    const entry = { action: 'player_update_photo', ok: false, duration_ms: 0, details: {} };
    try {
      await gotoTracked('/player/1/?tab=general', { label: 'player-1' });
      const before = await page.getAttribute('.photo-card img', 'src').catch(() => '');
      const photoPath =
        process.env.E2E_PHOTO_PATH ||
        path.join(process.cwd(), 'CAMPO DE FUTBOL.JPG');
      if (!fs.existsSync(photoPath)) {
        entry.details = { error: `No existe E2E_PHOTO_PATH: ${photoPath}` };
      } else {
        const fileInput = page.locator('input[type="file"][name="player_photo"]');
        await fileInput.setInputFiles(photoPath);
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle', timeout: 60000 }).catch(() => null),
          page.click('button[type="submit"]'),
        ]);
        const after = await page.getAttribute('.photo-card img', 'src').catch(() => '');
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

  const loginResult = await login();
  if (!loginResult.ok) {
    globalLog.actions.push({ action: 'abort', reason: 'login_failed' });
  } else {
    // Visitas principales "click-a-click"
    await gotoTracked('/', { label: 'home' });
    await gotoTracked('/api/dashboard/?fresh=1', { label: 'api-dashboard-fresh', waitUntil: 'domcontentloaded' });
    await gotoTracked('/players/', { label: 'players' });
    await gotoTracked('/coach/', { label: 'coach' });
    await gotoTracked('/coach/plantilla/', { label: 'coach-roster' });
    await gotoTracked('/registro-acciones/', { label: 'match-actions' });
    await gotoTracked('/task-studio/', { label: 'task-studio' });
    await gotoTracked('/task-studio/plantilla/', { label: 'task-studio-roster' });
    await gotoTracked('/platform/', { label: 'platform' });
    await gotoTracked('/platform/?tab=users', { label: 'platform-users' });

    // Acciones críticas
    await createTaskStudioTask();
    await updatePlayerPhoto();
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

