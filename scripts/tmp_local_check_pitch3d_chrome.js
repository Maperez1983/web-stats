/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'artifacts', 'tmp-local-check-pitch3d');
  const sessionid = String(process.env.E2E_SESSIONID || '').trim();
  const targetPath = process.env.E2E_TARGET_PATH || '/coach/sesiones/tareas/nueva/';
  const username = String(process.env.E2E_USERNAME || 'admin').trim();
  const password = String(process.env.E2E_PASSWORD || 'admin1234').trim();
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-gpu',
      '--disable-gpu-compositing',
      '--use-gl=swiftshader',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
  });
  if (sessionid) {
    await context.addCookies([{
      name: 'sessionid',
      value: sessionid,
      url: `${baseUrl}/`,
      sameSite: 'Lax',
    }]);
  }
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.on('console', (msg) => console.log(`[console:${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[pageerror] ${err && err.stack ? err.stack : err}`));
  await page.goto(`${baseUrl}${targetPath}`, { waitUntil: 'domcontentloaded' });
  if (/\/login\/?/i.test(page.url())) {
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
      page.locator('button[type="submit"]').first().click(),
    ]);
    await page.goto(`${baseUrl}${targetPath}`, { waitUntil: 'domcontentloaded' });
  }
  await page.waitForTimeout(3000);

  await page.screenshot({ path: path.join(outDir, '01-page.png'), fullPage: true });

  const oldTriggerCount = await page.locator('[data-pitch3d-trigger="1"]').count();
  if (oldTriggerCount) {
    await page.locator('[data-pitch3d-trigger="1"]').first().click();
  } else {
    const buttonLabels = ['PIZARRA 3D', 'Pizarra 3D', 'IR A PIZARRA', 'PIZARRA GRAFICA', 'Pizarra grafica'];
    let clicked = false;
    for (const label of buttonLabels) {
      const locator = page.getByRole('button', { name: label }).first();
      if (await locator.count()) {
        await locator.click();
        clicked = true;
        break;
      }
    }
    if (!clicked) {
      const textLocator = page.locator('button, a').filter({ hasText: /PIZARRA 3D|PIZARRA GRAFICA|IR A PIZARRA/i }).first();
      if (await textLocator.count()) {
        await textLocator.click();
        clicked = true;
      }
    }
    if (!clicked) throw new Error('pitch3d_trigger_missing');
  }
  await page.waitForTimeout(6000);

  await page.screenshot({ path: path.join(outDir, '02-modal.png'), fullPage: true });

  const captureButton = page.getByRole('button', { name: /CAPTURA HD/i }).first();
  if (await captureButton.count()) {
    const downloadPromise = page.waitForEvent('download', { timeout: 20000 }).catch(() => null);
    await captureButton.click().catch(() => null);
    const download = await downloadPromise;
    if (download) {
      const target = path.join(outDir, download.suggestedFilename() || 'captura_3d.png');
      await download.saveAs(target).catch(() => null);
      console.log(`[download] ${target}`);
    }
    await page.waitForTimeout(2000);
  }

  const state = await page.evaluate(() => {
    const modal = document.getElementById('task-pitch-3d-modal');
    const canvas = document.getElementById('task-pitch-3d-canvas');
    const fallback = document.getElementById('task-pitch-3d-fallback');
    const scene = window.__WEBSTATS_PITCH3D_SCENE || null;
    const rendererReady = !!window.__WEBSTATS_PITCH3D_RENDER_READY;
    const loadInfo = window.__WEBSTATS_PITCH3D_STADIUM_LOAD_INFO || null;
    const attachInfo = window.__WEBSTATS_PITCH3D_STADIUM_ATTACH_INFO || null;
    const kinds = [];
    try {
      scene?.traverse?.((node) => {
        const kind = String(node?.userData?.kind || '').trim();
        if (kind && kinds.length < 120) kinds.push(kind);
      });
    } catch (e) {}
    let sample = null;
    try {
      if (canvas && canvas.width > 8 && canvas.height > 8) {
        const c2d = document.createElement('canvas');
        c2d.width = canvas.width;
        c2d.height = canvas.height;
        const ctx = c2d.getContext('2d');
        ctx.drawImage(canvas, 0, 0);
        const x = Math.floor(canvas.width / 2);
        const y = Math.floor(canvas.height / 2);
        const data = ctx.getImageData(x, y, 1, 1).data;
        sample = Array.from(data);
      }
    } catch (e) {
      sample = ['read_error', String(e && e.message ? e.message : e)];
    }
    return {
      modalOpen: !!(modal && !modal.hidden),
      canvasSize: canvas ? { width: canvas.width, height: canvas.height } : null,
      fallbackVisible: !!(fallback && !fallback.hidden && fallback.style.display !== 'none'),
      rendererReady,
      loadInfo,
      attachInfo,
      sample,
      kinds,
    };
  });

  fs.writeFileSync(path.join(outDir, 'state.json'), JSON.stringify(state, null, 2));
  console.log(JSON.stringify(state, null, 2));

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
