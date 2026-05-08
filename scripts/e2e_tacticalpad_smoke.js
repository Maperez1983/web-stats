/* eslint-disable no-console */
// Smoke test for the tactical pad (task builder) that:
// - logs in
// - opens the task builder page
// - captures console/page errors
// - verifies we can place and drag a token on the canvas (touch-like context)
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8001 E2E_USERNAME=e2e_coach E2E_PASSWORD=e2e node scripts/e2e_tacticalpad_smoke.js
const { chromium, webkit } = require('playwright');

function pickBrowserType() {
  const raw = String(process.env.E2E_BROWSER || 'chromium').trim().toLowerCase();
  if (raw === 'webkit' || raw === 'safari') return webkit;
  return chromium;
}

function extractFirstObjectOfKind(state, kind) {
  const objects = state && Array.isArray(state.objects) ? state.objects : [];
  for (const obj of objects) {
    if (!obj) continue;
    const k = obj.data && typeof obj.data === 'object' ? String(obj.data.kind || '') : '';
    if (k === kind) return obj;
  }
  return null;
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'e2e_coach';
  const password = process.env.E2E_PASSWORD || 'e2e';
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';
  const forceDevice = String(process.env.E2E_DEVICE || 'tablet').trim().toLowerCase(); // tablet|desktop|auto

  const browserType = pickBrowserType();
  const browser = await browserType.launch({ headless });
  const context = await browser.newContext({
    // Use a large viewport so controls are visible, but keep touch enabled.
    // This still catches many touch/pointer related regressions without fighting mobile UI chrome.
    viewport: { width: 1400, height: 900 },
    deviceScaleFactor: 2,
    hasTouch: true,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  const consoleLines = [];
  const pageErrors = [];

  page.on('console', (msg) => {
    const line = `[console.${msg.type()}] ${msg.text()}`;
    consoleLines.push(line);
    // show only the most relevant lines to not spam CI
    if (msg.type() === 'error' || msg.type() === 'warning') console.log(line);
  });
  page.on('pageerror', (err) => {
    const raw = String(err && err.stack ? err.stack : err);
    // WebKit headless puede emitir un pageerror benigno al intentar registrar/leer el service worker en local.
    // No afecta al editor (y en Safari real no bloquea el flujo).
    if (/sw\.js/i.test(raw) && /Cannot load http/i.test(raw)) return;
    const line = `[pageerror] ${raw}`;
    pageErrors.push(line);
    console.log(line);
  });

  try {
    // Login
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    const [loginResp] = await Promise.all([
      page.waitForResponse((resp) => {
        try {
          const url = resp.url() || '';
          return url.includes('/login') && resp.request()?.method?.() === 'POST';
        } catch (e) {
          return false;
        }
      }).catch(() => null),
      page.click('button[type="submit"]'),
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    ]);
    // Si hay un mensaje de error visible, fallamos explícitamente.
    const errText = await page.locator('.error').first().textContent().catch(() => '');
    if (errText && errText.trim()) {
      const status = loginResp ? loginResp.status() : null;
      throw new Error(`Login failed${status ? ` [status=${status}]` : ''} (${errText.trim().slice(0, 180)})`);
    }

    // Login robusto: algunos despliegues devuelven 200 y redirigen por JS (la URL puede seguir siendo /login).
    const hasSessionCookie = async () => {
      try {
        const cookies = await context.cookies();
        return (cookies || []).some((c) => {
          const name = String(c?.name || '').toLowerCase();
          return name === 'sessionid' || name === 'webstats_sessionid' || name.includes('sessionid');
        });
      } catch (e) {
        return false;
      }
    };
    for (let i = 0; i < 12; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      if (await hasSessionCookie()) break;
      // eslint-disable-next-line no-await-in-loop
      await page.waitForTimeout(250);
    }
    if (!(await hasSessionCookie())) {
      const status = loginResp ? loginResp.status() : null;
      throw new Error(`Login failed${status ? ` [status=${status}]` : ''}`);
    }

    // Clear previous tactical-pad error marker to detect fresh failures.
    await page.evaluate(() => {
      try { window.localStorage.removeItem('webstats:tpad:last_error'); } catch (e) { /* ignore */ }
      try { window.localStorage.setItem('webstats:tpad:focus-mode-v1', '0'); } catch (e) { /* ignore */ }
      try { window.localStorage.setItem('tpad_tactics_panel_open_v1', '1'); } catch (e) { /* ignore */ }
      try { window.localStorage.setItem('tpad_tactics_tools_open_v1', '1'); } catch (e) { /* ignore */ }
    });

    // Open task builder (tactical pad) in a clean state (avoid stale local drafts).
    const deviceParam = (forceDevice === 'desktop' || forceDevice === 'tablet') ? `&device=${encodeURIComponent(forceDevice)}` : '';
    const builderUrl = `${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1${deviceParam}`;
    const builderResp = await page.goto(builderUrl, { waitUntil: 'domcontentloaded' });
    try {
      const status = builderResp ? builderResp.status() : null;
      console.log(`[e2e] builder url=${page.url()} status=${status == null ? 'n/a' : status}`);
    } catch (e) { /* ignore */ }
    try {
      await page.waitForSelector('#create-task-canvas', { timeout: 35_000 });
    } catch (e) {
      const nowUrl = page.url();
      const title = await page.title().catch(() => '');
      const bodyText = await page.evaluate(() => (document.body && document.body.innerText ? document.body.innerText.slice(0, 420) : '')).catch(() => '');
      console.error(`[e2e] builder missing canvas; url=${nowUrl} title=${title} body=${JSON.stringify(bodyText)}`);
      try {
        const fs = require('fs');
        fs.mkdirSync('artifacts', { recursive: true });
        await page.screenshot({ path: 'artifacts/e2e_tacticalpad_builder_missing.png', fullPage: true }).catch(() => null);
      } catch (err) { /* ignore */ }
      throw e;
    }

    // If the init failed, the JS stores last error in localStorage.
    const lastError = await page.evaluate(() => window.localStorage.getItem('webstats:tpad:last_error') || '');
    if (lastError) {
      console.log(`[e2e] last_error=${lastError}`);
    }

    // Wait until fabric created the upper-canvas
    const upperCanvas = page.locator('#task-pitch-stage canvas.upper-canvas');
    await upperCanvas.waitFor({ state: 'visible', timeout: 35_000 });

    // Add a player token using the roster bank (always visible in the editor).
    // We simulate the iPad workflow: drag a player into the pitch (pointer-based DnD).
    const bankBtn = page.locator('#task-player-bank button.player-token-bank').first();
    await bankBtn.waitFor({ state: 'visible', timeout: 35_000 });

    const bankBox = await bankBtn.boundingBox();
    if (!bankBox) throw new Error('No player bank bounding box');
    const box = await upperCanvas.boundingBox();
    if (!box) throw new Error('No canvas bounding box');
    const startX = bankBox.x + (bankBox.width / 2);
    const startY = bankBox.y + (bankBox.height / 2);
    const dropX = box.x + (box.width / 2);
    const dropY = box.y + (box.height / 2);

    // Simulate pointer-based drag (iPad/pen/touch) rather than HTML5 drag-and-drop.
    // We dispatch PointerEvents because Playwright's mouse may trigger native DnD on draggable elements.
    const pointerId = 77;
    await page.dispatchEvent('#task-player-bank button.player-token-bank', 'pointerdown', {
      pointerId,
      button: 0,
      clientX: startX,
      clientY: startY,
      pointerType: 'touch',
      isPrimary: true,
      bubbles: true,
      cancelable: true,
    });
    await page.dispatchEvent('body', 'pointermove', {
      pointerId,
      clientX: dropX,
      clientY: dropY,
      pointerType: 'touch',
      isPrimary: true,
      bubbles: true,
      cancelable: true,
    });
    await page.dispatchEvent('body', 'pointerup', {
      pointerId,
      button: 0,
      clientX: dropX,
      clientY: dropY,
      pointerType: 'touch',
      isPrimary: true,
      bubbles: true,
      cancelable: true,
    });
    await page.waitForTimeout(1200); // autosave debounce

    const draftKey = await page
      .$eval('#task-builder-form', (el) => (el && el.dataset ? String(el.dataset.draftKey || '') : ''))
      .catch(() => '');
    if (!draftKey) throw new Error('No se encontró data-draft-key en el form');

    const afterAddRaw = await page.evaluate((key) => window.localStorage.getItem(key) || '', draftKey);
    const draftAfterAdd = JSON.parse(afterAddRaw || '{}');
    const canvasStateAfterAdd = JSON.parse(String(draftAfterAdd?.fields?.draw_canvas_state || '{}'));
    const addedPlayer = extractFirstObjectOfKind(canvasStateAfterAdd, 'token');
    if (!addedPlayer) throw new Error('No se pudo añadir la chapa (token) en el canvas');

    const beforeLeft = Number(addedPlayer.left);
    const beforeTop = Number(addedPlayer.top);
    if (!Number.isFinite(beforeLeft) || !Number.isFinite(beforeTop)) throw new Error('Coordenadas inválidas tras añadir jugador');
    const canvasDims = await page.evaluate(() => {
      const el = document.querySelector('#task-pitch-stage canvas.upper-canvas');
      const rect = el?.getBoundingClientRect?.();
      return {
        cssW: Math.round(Number(rect?.width || 0)),
        cssH: Math.round(Number(rect?.height || 0)),
        attrW: Number(el?.width || 0),
        attrH: Number(el?.height || 0),
        dpr: Number(window.devicePixelRatio || 1),
        worldW: Number(document.getElementById('draw-canvas-width')?.value || 0),
        worldH: Number(document.getElementById('draw-canvas-height')?.value || 0),
      };
    });
    if (canvasDims?.cssW && canvasDims?.cssH) {
      console.log(
        `[e2e] token at left=${beforeLeft.toFixed(1)} top=${beforeTop.toFixed(1)} canvas css=${canvasDims.cssW}x${canvasDims.cssH} attr=${canvasDims.attrW}x${canvasDims.attrH} world=${canvasDims.worldW}x${canvasDims.worldH} dpr=${canvasDims.dpr}`,
      );
    }

    // Validate the token isn't clamped to margins (reported iPad bug: only drops on a side strip).
    if (Number.isFinite(canvasDims?.worldW) && canvasDims.worldW > 0 && Number.isFinite(canvasDims?.worldH) && canvasDims.worldH > 0) {
      const margin = 60;
      const okX = beforeLeft > margin && beforeLeft < (canvasDims.worldW - margin);
      const okY = beforeTop > margin && beforeTop < (canvasDims.worldH - margin);
      if (!okX || !okY) {
        throw new Error(`Drop parece clampado al borde: left=${beforeLeft} top=${beforeTop} world=${canvasDims.worldW}x${canvasDims.worldH}`);
      }
    }

    // Ensure inspector dock works in tablet mode (new iPad UX): select token and expect dock visible.
    if (forceDevice === 'tablet') {
      // Click near canvas center (token drop position) to trigger selection.
      await page.dispatchEvent('#task-pitch-stage canvas.upper-canvas', 'pointerdown', {
        pointerId: 88,
        button: 0,
        clientX: dropX,
        clientY: dropY,
        pointerType: 'touch',
        isPrimary: true,
        bubbles: true,
        cancelable: true,
      });
      await page.dispatchEvent('#task-pitch-stage canvas.upper-canvas', 'pointerup', {
        pointerId: 88,
        button: 0,
        clientX: dropX,
        clientY: dropY,
        pointerType: 'touch',
        isPrimary: true,
        bubbles: true,
        cancelable: true,
      });
      await page.waitForTimeout(450);

      const dockVisible = await page.evaluate(() => {
        const dock = document.getElementById('task-selection-dock');
        if (!dock) return false;
        const hidden = dock.hidden || dock.getAttribute('hidden') != null;
        const rect = dock.getBoundingClientRect?.();
        const sizeOk = rect && rect.width > 40 && rect.height > 40;
        return !hidden && !!sizeOk;
      });
      if (!dockVisible) throw new Error('Inspector flotante (task-selection-dock) no visible tras seleccionar objeto');

      // Close button should exist and hide dock.
      await page.click('#task-selection-dock-close');
      await page.waitForTimeout(250);
      const dockHiddenAfterClose = await page.evaluate(() => {
        const dock = document.getElementById('task-selection-dock');
        if (!dock) return true;
        return !!dock.hidden || dock.getAttribute('hidden') != null;
      });
      if (!dockHiddenAfterClose) throw new Error('Cerrar inspector flotante no ocultó el dock');
    }

    // If there were pageerrors, treat as failure
    if (pageErrors.length) throw new Error(`JS pageerror: ${pageErrors[0]}`);
    console.log('[e2e] OK');
  } catch (err) {
    console.error('[e2e] FAIL:', err && err.stack ? err.stack : err);
    try {
      const lastError = await page.evaluate(() => window.localStorage.getItem('webstats:tpad:last_error') || '');
      if (lastError) console.error('[e2e] last_error:', lastError);
    } catch (e) {
      // ignore
    }
    process.exitCode = 1;
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main();
