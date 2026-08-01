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
  const username = process.env.E2E_USERNAME || 'admin';
  const password = process.env.E2E_PASSWORD || 'admin1234';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'artifacts', 'tmp-verify-3d');
  const headless = String(process.env.E2E_HEADLESS || '').trim() === '1';
  const requestedCamera = String(process.env.E2E_CAMERA || '').trim();
  const softwareGl = String(process.env.E2E_SOFTWARE_GL || '1').trim() !== '0';
  fs.mkdirSync(outDir, { recursive: true });

  const launchArgs = [];
  if (softwareGl) {
    launchArgs.push(
      '--disable-gpu',
      '--disable-gpu-compositing',
      '--use-gl=swiftshader',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
    );
  } else if (!headless) {
    launchArgs.push('--enable-gpu', '--use-angle=metal');
  }

  const browser = await chromium.launch({
    headless,
    args: launchArgs,
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.on('console', (msg) => console.log(`[console:${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[pageerror] ${err && err.stack ? err.stack : err}`));
  page.on('crash', () => console.log('[page] crash'));
  page.on('close', () => console.log('[page] close'));
  page.on('requestfailed', (request) => {
    console.log(`[requestfailed] ${request.failure()?.errorText || 'failed'} ${request.url()}`);
  });
  page.on('response', async (response) => {
    if (response.status() >= 400) {
      console.log(`[response:${response.status()}] ${response.url()}`);
    }
  });

  try {
    const ok = await login(page, baseUrl, username, password);
    if (!ok) throw new Error('login_failed');

    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage', { state: 'visible' });
    await page.waitForFunction(() => !!window.__WEBSTATS_TPAD_READY, null, { timeout: 60000 }).catch(() => null);
    await page.waitForTimeout(3000);

    await page.evaluate(() => {
      const trigger = document.querySelector('[data-pitch3d-trigger="1"]');
      if (!trigger) throw new Error('pitch3d_trigger_missing');
      trigger.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    });
    await page.waitForFunction(() => {
      const modal = document.getElementById('task-pitch-3d-modal');
      return !!(modal && !modal.hidden);
    }, null, { timeout: 60000 });
    await page.waitForFunction(() => !!window.__WEBSTATS_PITCH3D_STADIUM_ATTACH_INFO, null, { timeout: 15000 }).catch(() => null);
    await page.waitForFunction(() => {
      const info = window.__WEBSTATS_PITCH3D_STADIUM_LOAD_INFO;
      if (!info) return false;
      return info.loading === false || info.failed === true;
    }, null, { timeout: 45000 }).catch(() => null);
    await page.waitForTimeout(2500);

    if (requestedCamera) {
      await page.evaluate((cameraValue) => {
        const select = document.getElementById('task-pitch-3d-camera');
        if (!select) throw new Error('pitch3d_camera_select_missing');
        const hasOption = Array.from(select.options || []).some((option) => option.value === cameraValue);
        if (!hasOption) throw new Error(`pitch3d_camera_option_missing:${cameraValue}`);
        select.value = cameraValue;
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }, requestedCamera);
      await page.waitForTimeout(2500);
    }

    const manualLoadCheck = await page.evaluate(async () => {
      try {
        const form = document.querySelector('form[data-three-gltf-loader-src][data-pitch3d-stadium-model-src]');
        if (!form) return { ok: false, error: 'form_missing' };
        const loaderSrc = String(form.dataset.threeGltfLoaderSrc || '').trim();
        const modelSrc = String(form.dataset.pitch3dStadiumModelSrc || '').trim();
        if (!loaderSrc) return { ok: false, error: 'gltf_loader_src_missing' };
        if (!modelSrc) return { ok: false, error: 'stadium_model_src_missing' };
        const mod = await import(loaderSrc);
        const GLTFLoader = mod && mod.GLTFLoader;
        if (typeof GLTFLoader !== 'function') return { ok: false, error: 'gltf_loader_class_missing' };
        const loader = new GLTFLoader();
        return await new Promise((resolve) => {
          let settled = false;
          const finish = (value) => {
            if (settled) return;
            settled = true;
            resolve(value);
          };
          const timer = window.setTimeout(() => finish({ ok: false, error: 'timeout' }), 12000);
          loader.load(
            modelSrc,
            (gltf) => {
              window.clearTimeout(timer);
              const scene = gltf?.scene || null;
              let meshCount = 0;
              try { scene?.traverse?.((node) => { if (node?.isMesh) meshCount += 1; }); } catch (e) {}
              finish({ ok: true, meshCount, childCount: scene?.children?.length || 0 });
            },
            undefined,
            (error) => {
              window.clearTimeout(timer);
              finish({ ok: false, error: String(error && error.message ? error.message : error || 'load_failed') });
            },
          );
        });
      } catch (error) {
        return { ok: false, error: String(error && error.message ? error.message : error || 'eval_failed') };
      }
    });

    const state = await page.evaluate(() => {
      const canvas = document.getElementById('task-pitch-3d-canvas');
      const fallback = document.getElementById('task-pitch-3d-fallback');
      const camera = document.getElementById('task-pitch-3d-camera');
      const cameraOptions = camera
        ? Array.from(camera.options || []).map((option) => ({
            value: option.value,
            text: String(option.textContent || '').trim(),
          }))
        : [];
      const scene = window.__WEBSTATS_PITCH3D_SCENE || null;
      const sceneKinds = [];
      try {
        scene?.traverse?.((node) => {
          const kind = String(node?.userData?.kind || '').trim();
          if (kind && sceneKinds.length < 40) sceneKinds.push(kind);
        });
      } catch (e) {}
      const rightGoalHits = [];
      try {
        scene?.updateMatrixWorld?.(true);
        scene?.traverse?.((node) => {
          if (!node?.isMesh || !node.geometry?.computeBoundingBox) return;
          node.geometry.computeBoundingBox();
          const bb = node.geometry.boundingBox?.clone?.()?.applyMatrix4?.(node.matrixWorld);
          if (!bb) return;
          const sx = bb.max.x - bb.min.x;
          const sy = bb.max.y - bb.min.y;
          const sz = bb.max.z - bb.min.z;
          const cx = (bb.max.x + bb.min.x) / 2;
          const cy = (bb.max.y + bb.min.y) / 2;
          const cz = (bb.max.z + bb.min.z) / 2;
          const nearRightGoal = cx > 43 && cx < 58 && cz > -12 && cz < 12 && cy > -0.5 && cy < 6;
          const bounded = sx < 20 && sy < 10 && sz < 20;
          if (!nearRightGoal || !bounded) return;
          rightGoalHits.push({
            name: String(node.name || ''),
            kind: String(node.userData?.kind || ''),
            center: [Number(cx.toFixed(3)), Number(cy.toFixed(3)), Number(cz.toFixed(3))],
            size: [Number(sx.toFixed(3)), Number(sy.toFixed(3)), Number(sz.toFixed(3))],
            material: Array.isArray(node.material)
              ? node.material.map((item) => String(item?.name || item?.type || ''))
              : String(node.material?.name || node.material?.type || ''),
          });
        });
      } catch (e) {}
      return {
        camera: camera ? camera.value : '',
        cameraOptions,
        attachInfo: window.__WEBSTATS_PITCH3D_STADIUM_ATTACH_INFO || null,
        loadInfo: window.__WEBSTATS_PITCH3D_STADIUM_LOAD_INFO || null,
        sideDetailsProgress: window.__WEBSTATS_PITCH3D_SIDE_DETAILS_PROGRESS || null,
        sideDetailsError: window.__WEBSTATS_PITCH3D_SIDE_DETAILS_ERROR || null,
        open: !!window.__WEBSTATS_PITCH3D_OPEN,
        fallbackVisible: !!(fallback && !fallback.hidden && fallback.style.display !== 'none'),
        triggerCount: document.querySelectorAll('[data-pitch3d-trigger="1"]').length,
        gltfLoaderReady: !!window.__WEBSTATS_GLTF_LOADER_CLASS,
        sceneObjectCount: scene?.children?.length || 0,
        sceneKinds,
        rightGoalHits,
        canvasOpacity: canvas ? getComputedStyle(canvas).opacity : '',
        canvasSize: canvas ? {
          width: canvas.width,
          height: canvas.height,
          cssWidth: canvas.getBoundingClientRect().width,
          cssHeight: canvas.getBoundingClientRect().height,
        } : null,
      };
    });

    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation: none !important;
          transition: none !important;
          caret-color: transparent !important;
        }
      `,
    }).catch(() => null);

    const suffix = requestedCamera ? `-${requestedCamera}` : '';
    const modalPath = path.join(outDir, `task-builder-3d-modal${suffix}.png`);
    const modalBox = await page.evaluate(() => {
      const el = document.querySelector('#task-pitch-3d-modal .sim-3d-card');
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return {
        x: Math.max(0, Math.floor(rect.left)),
        y: Math.max(0, Math.floor(rect.top)),
        width: Math.max(1, Math.ceil(rect.width)),
        height: Math.max(1, Math.ceil(rect.height)),
      };
    });
    if (!modalBox) throw new Error('pitch3d_modal_box_missing');
    await page.screenshot({
      path: modalPath,
      clip: modalBox,
      animations: 'disabled',
      timeout: 90000,
    });

    const pagePath = path.join(outDir, `task-builder-3d-page${suffix}.png`);
    await page.screenshot({ path: pagePath, fullPage: false });

    console.log(JSON.stringify({ manualLoadCheck, state, modalPath, pagePath }, null, 2));
    await page.waitForTimeout(1500);
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
