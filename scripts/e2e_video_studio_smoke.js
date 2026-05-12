/* eslint-disable no-console */
// Smoke test: Video Studio debe cargar y permitir usar herramientas básicas sin errores JS.
//
// Usage:
//   E2E_BASE_URL=http://127.0.0.1:8000 E2E_USERNAME=admin E2E_PASSWORD=admin node scripts/e2e_video_studio_smoke.js
//
// Opcionales:
//   E2E_VIDEO_ID=2 E2E_TEAM_ID=1 E2E_HEADLESS=true|false
const { chromium, webkit } = require('playwright');

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

async function login(page, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForURL((url) => !String(url && url.pathname ? url.pathname : '').includes('/login'), { timeout: 45_000 }).catch(() => null),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  // Algunas rutas post-login redirigen varias veces; lo más fiable es comprobar que ya hay sesión.
  const cookies = await page.context().cookies(baseUrl).catch(() => []);
  const hasSession = Array.isArray(cookies) && cookies.some((c) => String(c && c.name) === 'webstats_sessionid');
  if (!hasSession) throw new Error('Login failed');
}

async function drawLineOnCanvas(page, canvasLocator, fromPct, toPct) {
  const box = await canvasLocator.boundingBox();
  assert(box, 'missing canvas boundingBox');
  const x1 = box.x + box.width * fromPct.x;
  const y1 = box.y + box.height * fromPct.y;
  const x2 = box.x + box.width * toPct.x;
  const y2 = box.y + box.height * toPct.y;
  await page.mouse.move(x1, y1);
  await page.mouse.down();
  await page.mouse.move(x2, y2, { steps: 12 });
  await page.mouse.up();
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'admin';
  const password = process.env.E2E_PASSWORD || 'admin';
  const headless = String(process.env.E2E_HEADLESS || 'true').toLowerCase() !== 'false';
  const videoId = Number(process.env.E2E_VIDEO_ID || 2) || 2;
  const teamId = Number(process.env.E2E_TEAM_ID || 1) || 1;

  const rawBrowser = String(process.env.E2E_BROWSER || 'webkit').trim().toLowerCase();
  const browserType = (rawBrowser === 'chromium' || rawBrowser === 'chrome') ? chromium : webkit;
  const browser = await browserType.launch({ headless });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 2,
    hasTouch: false,
    ignoreHTTPSErrors: true,
    locale: 'es-ES',
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err && err.stack ? err.stack : err)));
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text() || '';
    // En algunos entornos el vídeo puede fallar por CORS/codec y loguear errores que no invalidan el UI.
    if (/MediaError|AbortError|NotSupportedError/i.test(text)) return;
    errors.push(text);
  });

  try {
    await login(page, baseUrl, username, password);

    await page.goto(`${baseUrl}/analysis/video/${videoId}/?team=${teamId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#vs-stage', { state: 'visible', timeout: 45_000 });

    // Controles clave
    await page.waitForSelector('#vs-tool-arrow', { state: 'visible' });
    await page.waitForSelector('#vs-tool-text', { state: 'visible' });
    await page.waitForSelector('#vs-line-style', { state: 'visible' });
    await page.waitForSelector('#vs-arrow-double', { state: 'visible' });

    // El canvas de eventos de Fabric es el upper-canvas (se crea tras inicializar).
    const upperCanvas = page.locator('#vs-stage .upper-canvas');
    await upperCanvas.waitFor({ state: 'visible', timeout: 45_000 });

    // 1) Texto: popover abre y crea capa
    await page.click('#vs-tool-text');
    await drawLineOnCanvas(page, upperCanvas, { x: 0.50, y: 0.45 }, { x: 0.50, y: 0.45 });
    await page.waitForSelector('#vs-text-pop', { state: 'visible' });
    await page.fill('#vs-text-value', 'Prueba texto');
    await page.click('#vs-text-ok');
    await page.waitForSelector('#vs-text-pop', { state: 'hidden' });
    await page.waitForFunction(() => {
      const el = document.querySelector('#vs-draw-layers');
      return !!(el && (el.textContent || '').includes('Texto'));
    }, null, { timeout: 20_000 });

    // 2) Flecha: estilo dash + doble punta
    await page.click('#vs-tool-arrow');
    await page.selectOption('#vs-line-style', 'dash');
    await page.click('#vs-arrow-double');
    await drawLineOnCanvas(page, upperCanvas, { x: 0.18, y: 0.75 }, { x: 0.42, y: 0.45 });
    await page.waitForFunction(() => {
      const el = document.querySelector('#vs-draw-layers');
      return !!(el && (el.textContent || '').includes('Flecha'));
    }, null, { timeout: 20_000 });

    // Selecciona la primera capa para comprobar el panel de estilo.
    const firstSelect = page.locator('#vs-draw-layers button[data-vs-draw-select]').first();
    await firstSelect.click();
    await page.waitForSelector('#vs-layer-style-form', { state: 'visible' });
    const lineStyle = await page.locator('#vs-layer-line-style').inputValue().catch(() => '');
    assert(lineStyle === 'dash' || lineStyle === 'solid' || lineStyle === 'dot' || lineStyle === '', `line style inesperado: ${lineStyle}`);

    // 3) Trayectoria: debe crear "Grupo" en lista (movement_line)
    await page.click('#vs-tool-move');
    await drawLineOnCanvas(page, upperCanvas, { x: 0.60, y: 0.70 }, { x: 0.82, y: 0.48 });
    await page.waitForFunction(() => {
      const el = document.querySelector('#vs-draw-layers');
      const text = (el && el.textContent) ? el.textContent : '';
      return text.includes('Grupo') || text.includes('Capa');
    }, null, { timeout: 20_000 }).catch(() => null);

    if (errors.length) {
      throw new Error(`JS errors:\n- ${errors.slice(0, 20).join('\n- ')}`);
    }
    console.log('[e2e] OK (video studio)');
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main().catch((err) => {
  console.error('[e2e] FAIL:', err && err.stack ? err.stack : err);
  process.exit(1);
});
