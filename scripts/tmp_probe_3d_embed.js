const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function main() {
  const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:8022';
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'admin1234';
  const taskId = process.env.E2E_TASK_ID || '376';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'tmp', 'probe-3d-embed');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const consoleLogs = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on('console', (msg) => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => pageErrors.push(String(err && err.stack ? err.stack : err)));
  page.on('requestfailed', (req) => {
    failedRequests.push({
      url: req.url(),
      method: req.method(),
      failure: req.failure() ? req.failure().errorText : '',
    });
  });

  await page.goto(`${baseUrl}/login/`, { waitUntil: 'networkidle' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);

  const targetUrl = `${baseUrl}/coach/sesiones/tarea/${taskId}/pdf-3d-embed/?camera=coach&cb=${Date.now()}`;
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForSelector('#task-detail-3d-canvas', { timeout: 15000 });
  } catch (error) {
    fs.writeFileSync(path.join(outDir, `task-${taskId}-embed-fail.html`), await page.content(), 'utf8');
    await page.screenshot({ path: path.join(outDir, `task-${taskId}-embed-fail.png`), fullPage: true }).catch(() => null);
    throw error;
  }
  await page.waitForTimeout(3500);

  const info = await page.evaluate(() => {
    const canvas = document.getElementById('task-detail-3d-canvas');
    const payload = document.getElementById('task-detail-3d-payload');
    let parsed = {};
    try {
      parsed = JSON.parse(payload?.textContent || '{}');
    } catch (error) {
      parsed = { error: String(error) };
    }
    const gl = canvas?.getContext('webgl2') || canvas?.getContext('webgl');
    return {
      href: window.location.href,
      stadiumVersion: window.__taskDetail3DStadiumVersion || '',
      presentationMode: window.__taskDetail3DPresentationMode || '',
      payloadCameraPreset: parsed.cameraPreset || '',
      payloadStadiumModelUrl: parsed.stadiumModelUrl || '',
      canvasSize: canvas ? { cssW: canvas.clientWidth, cssH: canvas.clientHeight, w: canvas.width, h: canvas.height } : null,
      diagnostics: window.__ollanaDiagnostics?.render_surfaces?.['task-detail-3d-canvas'] || null,
      webgl: gl ? (gl.constructor && gl.constructor.name ? gl.constructor.name : 'webgl') : '',
      bodyText: document.body.innerText.slice(0, 400),
      scriptCount: document.scripts.length,
    };
  });

  info.consoleLogs = consoleLogs;
  info.pageErrors = pageErrors;
  info.failedRequests = failedRequests;
  fs.writeFileSync(path.join(outDir, `task-${taskId}-embed.html`), await page.content(), 'utf8');

  fs.writeFileSync(path.join(outDir, `task-${taskId}-embed-info.json`), JSON.stringify(info, null, 2));
  await page.screenshot({ path: path.join(outDir, `task-${taskId}-embed-full.png`), fullPage: true });
  const canvas = page.locator('#task-detail-3d-canvas');
  await canvas.screenshot({ path: path.join(outDir, `task-${taskId}-embed-canvas.png`) });

  console.log(JSON.stringify(info, null, 2));
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
