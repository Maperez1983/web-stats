/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
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

async function readDraftState(page) {
  const draftKey = await page.$eval('#task-builder-form', (el) => String(el?.dataset?.draftKey || ''));
  if (!draftKey) return { draftKey: '', state: null };
  const raw = await page.evaluate((key) => window.localStorage.getItem(key) || '', draftKey);
  if (!raw) return { draftKey, state: null };
  try {
    const parsed = JSON.parse(raw);
    const canvasState = JSON.parse(String(parsed?.fields?.draw_canvas_state || '{}'));
    return { draftKey, state: canvasState };
  } catch (error) {
    return { draftKey, state: null };
  }
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'localadmin';
  const password = process.env.E2E_PASSWORD || 'localadmin';
  const outDir = process.env.E2E_OUT_DIR || '/private/tmp';

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1720, height: 1180 },
    deviceScaleFactor: 2,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);

  try {
    const ok = await login(page, baseUrl, username, password);
    if (!ok) throw new Error('login_failed');

    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage', { state: 'visible' });
    await page.waitForFunction(() => window.__WEBSTATS_TPAD_READY === true, null, { timeout: 12000 }).catch(() => null);
    await page.waitForTimeout(1200);

    await page.evaluate(() => {
      document.querySelector('#task-board-resources-toggle')?.click();
    }).catch(() => null);
    await page.waitForTimeout(250);
    await page.evaluate(() => {
      document.querySelector('.resource-tab[data-resource="figuras"]')?.click();
    }).catch(() => null);
    await page.waitForTimeout(400);

    const readStageState = () => page.evaluate(() => {
      const stage = document.getElementById('task-pitch-stage');
      const svg = document.getElementById('task-pitch-surface');
      const cs = stage ? window.getComputedStyle(stage) : null;
      const surfaceRect = svg?.getBoundingClientRect?.();
      const rect = stage?.getBoundingClientRect?.();
      return {
        orientation: document.getElementById('draw-task-pitch-orientation')?.value || '',
        grass: document.getElementById('pitch-grass-select')?.value || '',
        activeResource: document.querySelector('.resource-tab.is-active')?.getAttribute('data-resource') || '',
        label: document.getElementById('pitch-size-label')?.textContent?.trim() || '',
        stageWidth: Math.round(Number(rect?.width || 0)),
        stageHeight: Math.round(Number(rect?.height || 0)),
        surfaceWidth: Math.round(Number(surfaceRect?.width || 0)),
        surfaceHeight: Math.round(Number(surfaceRect?.height || 0)),
        viewBox: svg?.getAttribute('viewBox') || '',
        stageMaxUser: cs?.getPropertyValue('--stage-max-user')?.trim() || '',
        stageMaxFit: cs?.getPropertyValue('--stage-max-fit')?.trim() || '',
        inlineStageMaxUser: stage?.style?.getPropertyValue('--stage-max-user')?.trim() || '',
        inlineStageMaxFit: stage?.style?.getPropertyValue('--stage-max-fit')?.trim() || '',
        styleWidth: cs?.width || '',
        styleMaxWidth: cs?.maxWidth || '',
        sizeStorageLandscape: window.localStorage.getItem('tpad_stage_size_landscape_v1') || '',
        sizeStoragePortrait: window.localStorage.getItem('tpad_stage_size_portrait_v1') || '',
        lastError: window.localStorage.getItem('webstats:tpad:last_error') || '',
        status: document.getElementById('task-builder-status')?.textContent?.trim() || '',
      };
    });
    const initial = await readStageState();

    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('webstats:tpad:assistant-board', {
        detail: {
          clear: false,
          items: [
            { payload: { kind: 'shape_lane_3' }, x: 0.28, y: 0.22, scale: 1.25 },
            { payload: { kind: 'shape_lane_4' }, x: 0.50, y: 0.22, scale: 1.25 },
            { payload: { kind: 'shape_lane_5' }, x: 0.72, y: 0.22, scale: 1.25 },
          ],
        },
      }));
    });
    await page.waitForTimeout(1200);

    const afterLanes = await readDraftState(page);
    const laneKinds = ((afterLanes.state?.objects) || [])
      .map((obj) => String(obj?.data?.kind || ''))
      .filter((kind) => kind.startsWith('shape-lane-') || kind.startsWith('shape_lane_'))
      .sort();
    const laneObjectCount = laneKinds.length;

    await page.evaluate(() => {
      const select = document.getElementById('pitch-grass-select');
      if (!select) throw new Error('grass_select_missing');
      select.value = 'broadcast_premium';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(1600);
    const grassChanged = await readStageState();

    await page.evaluate(() => {
      const btn = document.getElementById('pitch-size-down');
      btn?.click();
      btn?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    });
    await page.waitForTimeout(700);
    const sizeDown = await readStageState();
    await page.evaluate(() => {
      const btn = document.getElementById('pitch-size-up');
      btn?.click();
      btn?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    });
    await page.waitForTimeout(700);
    const sizeUp = await readStageState();

    await page.evaluate(() => document.getElementById('pitch-orientation-toggle-quick')?.click());
    await page.waitForTimeout(1800);
    const portrait = await readStageState();

    const afterPortraitLanes = await readDraftState(page);
    const portraitLaneKinds = ((afterPortraitLanes.state?.objects) || [])
      .map((obj) => String(obj?.data?.kind || ''))
      .filter((kind) => kind.startsWith('shape-lane-') || kind.startsWith('shape_lane_'))
      .sort();

    await page.evaluate(() => document.getElementById('pitch-orientation-toggle-quick')?.click());
    await page.waitForTimeout(1800);
    const landscapeAgain = await readStageState();

    const finalState = await readDraftState(page);
    const finalLaneKinds = ((finalState.state?.objects) || [])
      .map((obj) => String(obj?.data?.kind || ''))
      .filter((kind) => kind.startsWith('shape-lane-') || kind.startsWith('shape_lane_'))
      .sort();

    const screenshotPath = path.join(outDir, 'task_builder_controls_validation.png');
    await page.locator('#task-pitch-stage').screenshot({ path: screenshotPath });

    const summary = {
      initial,
      laneKinds,
      laneObjectCount,
      grassChanged,
      sizeDown,
      sizeUp,
      portrait,
      portraitLaneKinds,
      landscapeAgain,
      finalLaneKinds,
      screenshotPath,
    };

    fs.writeFileSync(path.join(outDir, 'task_builder_controls_validation.json'), JSON.stringify(summary, null, 2));
    console.log(JSON.stringify(summary, null, 2));
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
