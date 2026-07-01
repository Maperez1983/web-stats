/* eslint-disable no-console */
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

async function login(page, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  if (!/\/login\/?/.test(page.url())) return true;
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  return !/\/login\/?/.test(page.url());
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
  const outDir = process.env.E2E_OUT_DIR || '/private/tmp';
  const grassStyle = process.env.E2E_GRASS_STYLE || 'classic';
  const requestedOrientation = process.env.E2E_ORIENTATION || '';
  const deviceScaleFactor = Number(process.env.E2E_DEVICE_SCALE_FACTOR || 2);
  const viewportWidth = Number(process.env.E2E_VIEWPORT_WIDTH || 1720);
  const viewportHeight = Number(process.env.E2E_VIEWPORT_HEIGHT || 1180);
  const browser = await chromium.launch({
    headless: true,
    args: ['--enable-gpu', '--use-angle=metal'],
  });
  const context = await browser.newContext({
    viewport: { width: viewportWidth, height: viewportHeight },
    deviceScaleFactor,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);

  try {
    const ok = await login(page, baseUrl, username, password);
    if (!ok) throw new Error('login_failed');
    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage', { state: 'visible' });
    await page.waitForTimeout(2500);
    await page.evaluate(({ requestedGrassStyle, requestedOrientationValue }) => {
      const select = document.getElementById('pitch-grass-select');
      if (select && requestedGrassStyle) {
        select.value = requestedGrassStyle;
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (requestedOrientationValue === 'portrait' || requestedOrientationValue === 'vertical') {
        const hiddenInput = document.getElementById('draw-task-pitch-orientation');
        if (hiddenInput && hiddenInput.value !== 'portrait') {
          const toggle = document.getElementById('pitch-orientation-toggle-quick') || document.getElementById('pitch-orientation-toggle');
          if (toggle) toggle.click();
        }
      } else if (requestedOrientationValue === 'landscape' || requestedOrientationValue === 'horizontal') {
        const hiddenInput = document.getElementById('draw-task-pitch-orientation');
        if (hiddenInput && hiddenInput.value !== 'landscape') {
          const toggle = document.getElementById('pitch-orientation-toggle-quick') || document.getElementById('pitch-orientation-toggle');
          if (toggle) toggle.click();
        }
      }
    }, { requestedGrassStyle: grassStyle, requestedOrientationValue: requestedOrientation });
    await page.waitForTimeout(1800);
    const info = await page.evaluate(() => {
      const stage = document.getElementById('task-pitch-stage');
      const viewport = document.getElementById('task-pitch-viewport');
      const surface = document.getElementById('task-pitch-surface');
      const plane = document.getElementById('task-pitch-plane');
      const live = document.getElementById('task-pitch-surface-3d');
      const rectOf = (node) => {
        if (!node || !node.getBoundingClientRect) return null;
        const r = node.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height, top: r.top, left: r.left };
      };
      return {
        stageClass: stage ? stage.className : '',
        viewportClass: viewport ? viewport.className : '',
        live3dActive: live ? live.dataset.active : '',
        live3dSize: live ? { width: live.width, height: live.height } : null,
        stageRect: rectOf(stage),
        viewportRect: rectOf(viewport),
        planeRect: rectOf(plane),
        surfaceRect: rectOf(surface),
        surfaceViewBox: surface ? surface.getAttribute('viewBox') : '',
        surfacePreserve: surface ? surface.getAttribute('preserveAspectRatio') : '',
        bodyClass: document.body ? document.body.className : '',
      };
    });
    console.log(JSON.stringify(info, null, 2));
    const stagePath = path.join(outDir, 'task_builder_editor_stage_latest.png');
    await page.locator('#task-pitch-stage').screenshot({ path: stagePath });
    const canvasDataUrl = await page.evaluate(() => {
      const live = document.getElementById('task-pitch-surface-3d');
      if (!live || typeof live.toDataURL !== 'function') return '';
      try { return live.toDataURL('image/png'); } catch (error) { return ''; }
    });
    let canvasPath = '';
    if (canvasDataUrl.startsWith('data:image/png;base64,')) {
      canvasPath = path.join(outDir, 'task_builder_editor_surface_native.png');
      fs.writeFileSync(canvasPath, Buffer.from(canvasDataUrl.slice('data:image/png;base64,'.length), 'base64'));
    }
    console.log(JSON.stringify({ stagePath, canvasPath }));
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
