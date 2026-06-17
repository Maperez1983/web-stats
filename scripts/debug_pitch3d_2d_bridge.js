/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function extractSummary(objects) {
  return (Array.isArray(objects) ? objects : []).map((obj, index) => ({
    index,
    type: obj?.type || '',
    left: obj?.left,
    top: obj?.top,
    width: obj?.width,
    height: obj?.height,
    angle: obj?.angle,
    originX: obj?.originX,
    originY: obj?.originY,
    data: {
      kind: obj?.data?.kind || '',
      token_kind: obj?.data?.token_kind || '',
      token_style: obj?.data?.token_style || '',
      playerNumber: obj?.data?.playerNumber || '',
      layer_uid: obj?.data?.layer_uid || '',
    },
  }));
}

async function login(page, context, baseUrl, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  const cookies = await context.cookies();
  if (!(cookies || []).some((c) => String(c?.name || '').toLowerCase().includes('session'))) {
    throw new Error('login_failed');
  }
}

async function clickFirstVisible(page, selector) {
  const locator = page.locator(selector);
  const count = await locator.count();
  if (count < 1) throw new Error(`selector_missing:${selector}:0`);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) {
      await candidate.click();
      return;
    }
  }
  throw new Error(`selector_not_visible:${selector}:${count}`);
}

async function activateHiddenAddKind(page, kind) {
  const clicked = await page.evaluate((nextKind) => {
    const button = Array.from(document.querySelectorAll('button[data-add]') || []).find((node) => {
      return String(node.getAttribute('data-add') || '') === String(nextKind);
    });
    if (!button) return false;
    button.click();
    return true;
  }, kind);
  if (!clicked) throw new Error(`missing_add_kind:${kind}`);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'https://app.segundajugada.es').replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || '';
  const password = process.env.E2E_PASSWORD || '';
  const outDir = process.env.E2E_OUT_DIR || path.join(process.cwd(), 'artifacts', 'pitch3d-bridge', stamp());
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    headless: String(process.env.E2E_HEADLESS || 'false').toLowerCase() !== 'false' ? true : false,
    args: ['--use-angle=metal'],
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1200 },
    deviceScaleFactor: 1.5,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  page.setDefaultNavigationTimeout(60000);

  const report = { started_at: new Date().toISOString(), baseUrl, screenshots: [], console: [], errors: [] };
  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) report.console.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    report.errors.push(String(err && err.stack ? err.stack : err));
  });

  try {
    await login(page, context, baseUrl, username, password);
    await page.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=desktop`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#task-pitch-stage canvas.upper-canvas', { state: 'visible' });
    await page.waitForTimeout(1800);
    report.resource_buttons = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('button[data-add]') || []).map((button) => {
        const rect = button.getBoundingClientRect();
        return {
          add: button.getAttribute('data-add') || '',
          text: (button.textContent || '').trim(),
          visible: !!(rect.width > 0 && rect.height > 0),
          width: rect.width,
          height: rect.height,
        };
      });
    });
    const beforePath = path.join(outDir, '00-before-insert.png');
    await page.screenshot({ path: beforePath, fullPage: true });
    report.screenshots.push(beforePath);

    const canvas = page.locator('#task-pitch-stage canvas.upper-canvas');
    const canvasBox = await canvas.boundingBox();
    if (!canvasBox) throw new Error('missing_canvas_box');

    await activateHiddenAddKind(page, 'player_local');
    await page.mouse.click(canvasBox.x + (canvasBox.width * 0.32), canvasBox.y + (canvasBox.height * 0.45));
    await page.waitForTimeout(400);

    await activateHiddenAddKind(page, 'arrow_solid');
    await page.mouse.move(canvasBox.x + (canvasBox.width * 0.46), canvasBox.y + (canvasBox.height * 0.52));
    await page.mouse.down();
    await page.mouse.move(canvasBox.x + (canvasBox.width * 0.62), canvasBox.y + (canvasBox.height * 0.36), { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(900);

    const state2d = await page.evaluate(() => {
      const fn = window.__WEBSTATS_SERIALIZE_CANVAS_ONLY;
      const state = typeof fn === 'function' ? fn() : null;
      const perf = window.__WEBSTATS_PITCH3D_PERF || null;
      return { state, perf };
    });
    report.serialized_before_3d = extractSummary(state2d?.state?.objects || []);

    const twoDPath = path.join(outDir, '01-2d.png');
    await page.screenshot({ path: twoDPath, fullPage: true });
    report.screenshots.push(twoDPath);

    await clickFirstVisible(page, '#pitch-3d-open');
    await page.waitForSelector('#task-pitch-3d-canvas', { state: 'visible' });
    await page.waitForTimeout(3000);

    const state3d = await page.evaluate(() => {
      const modal = document.getElementById('task-pitch-3d-modal');
      const perf = window.__WEBSTATS_PITCH3D_PERF || null;
      const renderState = window.__WEBSTATS_PITCH3D_RENDER_STATE || null;
      const scene = window.__WEBSTATS_PITCH3D_SCENE || null;
      const root = scene && Array.isArray(scene.children)
        ? scene.children.find((node) => node && node.type === 'Group' && node.userData && !node.userData.kind)
        : null;
      const summarize = (node) => {
        if (!node) return null;
        return {
          type: node.type || '',
          visible: node.visible !== false,
          childCount: Array.isArray(node.children) ? node.children.length : 0,
          userKind: node.userData && node.userData.kind ? String(node.userData.kind) : '',
          exactLook: !!(node.userData && node.userData.exact_look),
          position: node.position ? { x: node.position.x, y: node.position.y, z: node.position.z } : null,
        };
      };
      return {
        modalHidden: !!modal?.hidden,
        modalDisplay: modal ? window.getComputedStyle(modal).display : '',
        perf,
        hasRenderState: typeof renderState === 'function',
        tokenCount: root ? (root.children || []).filter((node) => String(node?.userData?.kind || '') === 'token').length : 0,
        ballCount: root ? (root.children || []).filter((node) => String(node?.userData?.kind || '') === 'ball').length : 0,
        lineCount: root ? (root.children || []).filter((node) => String(node?.userData?.kind || '').includes('line')).length : 0,
        sceneTokenLike: root ? (root.children || []).filter((node) => {
          const kind = node && node.userData && node.userData.kind ? String(node.userData.kind) : '';
          return kind.includes('token') || kind.includes('ball') || kind.includes('line') || kind.includes('route') || kind.includes('drawable');
        }).map(summarize) : [],
        rootChildKinds: root ? (root.children || []).map(summarize) : [],
      };
    });
    report.pitch3d = state3d;

    const threeDPath = path.join(outDir, '02-3d.png');
    await page.screenshot({ path: threeDPath, fullPage: true });
    report.screenshots.push(threeDPath);

    fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ outDir, report }, null, 2));
  } catch (error) {
    report.fatal = String(error && error.stack ? error.stack : error);
    fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));
    throw error;
  } finally {
    await browser.close().catch(() => null);
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
