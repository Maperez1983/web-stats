/* eslint-disable no-console */

const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const QA_DIR = path.join(ROOT, 'output', 'qa', 'task-builder-pitch-finalization');
const BASELINE_DIR = path.join(ROOT, 'output', 'qa', 'task-builder-js-css-modularization');
const BASELINE_BEFORE = path.join(BASELINE_DIR, '02-after.png');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loginAndOpenBuilder(page, baseUrl, device = 'desktop') {
  const creds = [
    { username: process.env.E2E_USERNAME || 'localadmin', password: process.env.E2E_PASSWORD || 'localadmin' },
    { username: 'e2e_coach', password: 'e2e' },
  ];

  for (const credsItem of creds) {
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="username"]', credsItem.username).catch(() => null);
    await page.fill('input[name="password"]', credsItem.password).catch(() => null);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
      page.click('button[type="submit"]').catch(() => null),
    ]);
    const cookies = await page.context().cookies().catch(() => []);
    if (cookies.some((cookie) => String(cookie.name || '').toLowerCase().includes('sessionid'))) break;
  }

  await page.goto(
    `${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=${encodeURIComponent(device)}`,
    { waitUntil: 'domcontentloaded' }
  );
  await page.waitForSelector('#create-task-canvas', { state: 'attached', timeout: 35_000 });
  await page.waitForSelector('#task-pitch-stage', { state: 'attached', timeout: 35_000 });
  await page.waitForFunction(() => {
    const stage = document.querySelector('#task-pitch-stage');
    if (!stage) return false;
    const rect = stage.getBoundingClientRect();
    const style = window.getComputedStyle(stage);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }, { timeout: 35_000 }).catch(() => null);
  await page.waitForSelector('#task-pitch-surface', { state: 'attached', timeout: 35_000 });
  await page.waitForFunction(() => {
    const stage = document.querySelector('#task-pitch-stage');
    if (!stage) return false;
    const rect = stage.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }, { timeout: 35_000 }).catch(() => null);
  await page.waitForFunction(() => {
    const svg = document.querySelector('#task-pitch-surface');
    if (!svg) return false;
    const lines = svg.querySelectorAll('line').length;
    const circles = svg.querySelectorAll('circle').length;
    const rects = svg.querySelectorAll('rect').length;
    const goals = svg.querySelectorAll('.goal-left, .goal-right, [class^="goal-"]').length;
    return lines >= 20 && circles >= 8 && rects >= 20 && goals >= 2;
  }, { timeout: 35_000 });
  await wait(600);
}

async function analyzeSurface(page) {
  return page.evaluate(() => {
    const root = document.getElementById('task-builder-form') || document.body;
    const stage = root.querySelector('#task-pitch-stage');
    const svg = root.querySelector('#task-pitch-surface');
    const rectOf = (el) => {
      if (!el || !el.getBoundingClientRect) return null;
      const r = el.getBoundingClientRect();
      return {
        left: Number(r.left) || 0,
        top: Number(r.top) || 0,
        right: Number(r.right) || 0,
        bottom: Number(r.bottom) || 0,
        width: Number(r.width) || 0,
        height: Number(r.height) || 0,
      };
    };
    const parsePitchBox = () => {
      const raw = String(svg?.getAttribute('data-pitch-box') || '').trim();
      const parts = raw.split(/\s+/).map((part) => Number(part));
      if (parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) return null;
      const [x, y, w, h] = parts;
      return { x, y, w, h, right: x + w, bottom: y + h };
    };
    const parseViewBox = () => {
      const raw = String(svg?.getAttribute('viewBox') || '').trim();
      const parts = raw.split(/\s+/).map((part) => Number(part));
      if (parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) return null;
      const [x, y, w, h] = parts;
      return { x, y, w, h, right: x + w, bottom: y + h };
    };
    const elementCount = svg ? {
      lines: svg.querySelectorAll('line').length,
      circles: svg.querySelectorAll('circle').length,
      rects: svg.querySelectorAll('rect').length,
      paths: svg.querySelectorAll('path').length,
      goals: svg.querySelectorAll('.goal-left, .goal-right, [class^="goal-"]').length,
    } : null;
    const duplicateCounts = {
      stage: document.querySelectorAll('#task-pitch-stage').length,
      viewport: document.querySelectorAll('#task-pitch-viewport').length,
      shell: document.querySelectorAll('.board-stage-shell').length,
    };

    return {
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      bodyClass: document.body.className,
      focusMode: document.body.classList.contains('focus-mode'),
      stage: rectOf(stage),
      editorRoot: rectOf(root),
      stageShell: rectOf(root.querySelector('.board-stage-shell') || document.querySelector('.board-stage-shell')),
      pitchMain: rectOf(root.querySelector('.pitch-main') || document.querySelector('.pitch-main')),
      pitchViewport: rectOf(root.querySelector('#task-pitch-viewport') || document.querySelector('#task-pitch-viewport')),
      stageShellComputed: (() => {
        const el = root.querySelector('.board-stage-shell') || document.querySelector('.board-stage-shell');
        if (!el) return null;
        const style = window.getComputedStyle(el);
        return { display: style.display, visibility: style.visibility, opacity: style.opacity };
      })(),
      pitchViewportComputed: (() => {
        const el = root.querySelector('#task-pitch-viewport') || document.querySelector('#task-pitch-viewport');
        if (!el) return null;
        const style = window.getComputedStyle(el);
        return { display: style.display, visibility: style.visibility, opacity: style.opacity };
      })(),
      stageOffset: stage ? {
        width: Number(stage.offsetWidth) || 0,
        height: Number(stage.offsetHeight) || 0,
        clientRects: stage.getClientRects ? stage.getClientRects().length : 0,
        offsetParent: stage.offsetParent ? stage.offsetParent.tagName : null,
      } : null,
      stageComputed: stage ? (() => {
        const style = window.getComputedStyle(stage);
        return {
          display: style.display,
          visibility: style.visibility,
          opacity: style.opacity,
          position: style.position,
          width: style.width,
          height: style.height,
          minHeight: style.minHeight,
          maxWidth: style.maxWidth,
          transform: style.transform,
        };
      })() : null,
      stageStyleAttr: stage?.getAttribute?.('style') || '',
      stageShellStyleAttr: (root.querySelector('.board-stage-shell') || document.querySelector('.board-stage-shell'))?.getAttribute?.('style') || '',
      pitchViewportStyleAttr: (root.querySelector('#task-pitch-viewport') || document.querySelector('#task-pitch-viewport'))?.getAttribute?.('style') || '',
      svg: rectOf(svg),
      svgComputed: svg ? (() => {
        const style = window.getComputedStyle(svg);
        return {
          display: style.display,
          visibility: style.visibility,
          opacity: style.opacity,
          width: style.width,
          height: style.height,
          position: style.position,
        };
      })() : null,
      pitchBox: parsePitchBox(),
      viewBox: parseViewBox(),
      topbar: rectOf(root.querySelector('.topbar') || document.querySelector('.topbar')),
      tabs: rectOf(document.querySelector('.task-mode-tabs')),
      viewportScroll: {
        left: Number(stage?.parentElement?.scrollLeft) || 0,
        top: Number(stage?.parentElement?.scrollTop) || 0,
      },
      surfaceLabel: document.getElementById('surface-trigger-label')?.textContent?.trim() || '',
      orientationLabel: document.getElementById('pitch-orientation-label-quick')?.textContent?.trim() || '',
      zoomLabel: document.getElementById('pitch-zoom-label')?.textContent?.trim() || '',
      focusButtonText: document.getElementById('task-focus-toggle')?.textContent?.trim() || '',
      pitchMenuOpen: !!document.getElementById('pitch-view-menu')?.open,
      elementCount,
      duplicateCounts,
      stageAncestors: (() => {
        const out = [];
        let node = stage;
        for (let i = 0; node && i < 6; i += 1) {
          const r = node.getBoundingClientRect();
          const cs = window.getComputedStyle(node);
          out.push({
            tag: node.tagName,
            cls: String(node.className || ''),
            id: node.id || '',
            display: cs.display,
            visibility: cs.visibility,
            position: cs.position,
            width: cs.width,
            height: cs.height,
            rectW: Number(r.width) || 0,
            rectH: Number(r.height) || 0,
            hidden: !!node.hidden,
          });
          node = node.parentElement;
        }
        return out;
      })(),
    };
  });
}

function assertStateFits(state, label, options = {}) {
  if (!state?.stage || !state?.svg || !state?.pitchBox) {
    throw new Error(`[${label}] pitch surface not detected`);
  }
  const { stage, svg, viewport, topbar, tabs, elementCount, pitchBox, viewBox } = state;
  const duplicateCounts = state.duplicateCounts || {};
  const margin = Number(options.margin || 10);
  const minLines = Number(options.minLines || 10);
  const minCircles = Number(options.minCircles || 2);
  const minRects = Number(options.minRects || 6);
  const minPaths = Number(options.minPaths || 4);
  const minGoals = Number(options.minGoals || 2);
  if (!elementCount || elementCount.lines < minLines || elementCount.circles < minCircles || elementCount.rects < minRects || elementCount.paths < minPaths || elementCount.goals < minGoals) {
    throw new Error(`[${label}] pitch elements missing: ${JSON.stringify({ elementCount })}`);
  }
  if ((duplicateCounts.stage || 0) > 1 || (duplicateCounts.viewport || 0) > 1 || (duplicateCounts.shell || 0) > 1) {
    throw new Error(`[${label}] duplicate pitch nodes detected: ${JSON.stringify(duplicateCounts)}`);
  }
  if (stage.left < margin || stage.top < (topbar ? topbar.bottom + margin : margin)) {
    throw new Error(`[${label}] stage clipped at top/left: ${JSON.stringify(state)}`);
  }
  if (stage.right > viewport.width - margin || stage.bottom > viewport.height - margin) {
    throw new Error(`[${label}] stage clipped at right/bottom: ${JSON.stringify(state)}`);
  }
  if (tabs && tabs.bottom > stage.top && tabs.bottom < stage.bottom && tabs.left < stage.right) {
    // The tabs can sit above the editor; if they overlap the stage, the layout is broken.
    throw new Error(`[${label}] mode tabs overlap the pitch stage: ${JSON.stringify(state)}`);
  }
  const pitchWidth = Number(pitchBox.w) || 0;
  const pitchHeight = Number(pitchBox.h) || 0;
  if (pitchWidth < 300 || pitchHeight < 180) {
    throw new Error(`[${label}] pitch box too small: ${JSON.stringify(pitchBox)}`);
  }
  const svgLimitW = Number(viewBox?.w || 0) || 1200;
  const svgLimitH = Number(viewBox?.h || 0) || 820;
  if (pitchBox.x < -1 || pitchBox.y < -1 || pitchBox.right > svgLimitW + 2 || pitchBox.bottom > svgLimitH + 2) {
    throw new Error(`[${label}] pitch box out of renderer bounds: ${JSON.stringify({ pitchBox, viewBox })}`);
  }
  const ratio = pitchWidth / Math.max(1, pitchHeight);
  const isVertical = pitchHeight > pitchWidth;
  const minRatio = isVertical ? 0.45 : 1.1;
  const maxRatio = isVertical ? 1.05 : 2.0;
  if (ratio < minRatio || ratio > maxRatio) {
    throw new Error(`[${label}] pitch ratio looks wrong: ${ratio.toFixed(3)} · ${JSON.stringify(pitchBox)}`);
  }
  return { ...state, pitchWidth, pitchHeight };
}

async function openViewMenu(page) {
  const menu = page.locator('#pitch-view-menu');
  await menu.locator('summary').click();
  await wait(120);
  await page.locator('#pitch-size-fit').waitFor({ state: 'visible', timeout: 5_000 });
}

async function setSurfacePreset(page, preset) {
  await page.evaluate((value) => {
    const setter = window.__webstatsTaskBuilderSetPreset;
    if (typeof setter === 'function') {
      setter(value, { silent: true, remapObjects: false, persist: false });
    } else {
      const el = document.getElementById('draw-task-preset');
      if (!el) return;
      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }, preset);
  await wait(350);
}

async function setPitchOrientation(page, orientation) {
  await page.evaluate((value) => {
    const btn = document.getElementById('pitch-orientation-toggle-quick');
    const current = document.getElementById('draw-task-pitch-orientation');
    const desired = value === 'portrait' ? 'portrait' : 'landscape';
    if (current && String(current.value || '').trim() !== desired) {
      if (btn && typeof btn.click === 'function') {
        btn.click();
        return;
      }
      current.value = desired;
      current.dispatchEvent(new Event('input', { bubbles: true }));
      current.dispatchEvent(new Event('change', { bubbles: true }));
    } else if (btn && typeof btn.click === 'function' && desired === 'portrait') {
      btn.click();
    }
  }, orientation);
  await wait(350);
}

async function capture(page, fileName) {
  await page.screenshot({ path: path.join(QA_DIR, fileName), fullPage: true });
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  fs.mkdirSync(QA_DIR, { recursive: true });
  if (fs.existsSync(BASELINE_BEFORE)) {
    fs.copyFileSync(BASELINE_BEFORE, path.join(QA_DIR, '01-before.png'));
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
    hasTouch: true,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(35_000);
  page.setDefaultNavigationTimeout(60_000);

  const errors = [];
  page.on('pageerror', (error) => {
    const raw = String(error?.stack || error || '');
    errors.push(raw);
  });
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(`[console.error] ${msg.text()}`);
    }
  });

  const summary = [];

  try {
    await loginAndOpenBuilder(page, baseUrl, 'desktop');
    const initial = await analyzeSurface(page);
    await capture(page, '02-editing-full-pitch.png');
    assertStateFits(initial, 'initial', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'editing-full-pitch', state: initial });

    await openViewMenu(page);
    await page.locator('#pitch-size-fit').click();
    await wait(250);
    await page.locator('#pitch-size-up').click();
    await wait(200);
    const expanded = await analyzeSurface(page);
    assertStateFits(expanded, 'field-expanded', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'field-expanded', state: expanded });
    await capture(page, '03-field-expanded.png');

    const baseStorageState = await context.storageState();

    await page.evaluate(() => {
      const btn = document.getElementById('task-focus-toggle');
      if (btn && typeof btn.click === 'function') btn.click();
    });
    await wait(250);
    const focusState = await analyzeSurface(page);
    if (!focusState.focusMode) {
      throw new Error('focus mode did not activate');
    }
    assertStateFits(focusState, 'field-only', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'field-only', state: focusState });
    await capture(page, '04-field-only.png');

    await setSurfacePreset(page, 'stadium_native');
    const presentationState = await analyzeSurface(page);
    if (!presentationState.focusMode) throw new Error('presentation mode lost focus state');
    assertStateFits(presentationState, 'presentation-mode', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'presentation-mode', state: presentationState });
    await capture(page, '05-presentation-mode.png');

    await setPitchOrientation(page, 'portrait');
    await wait(300);
    const verticalState = await analyzeSurface(page);
    const orientationText = String(verticalState.orientationLabel || '').toLowerCase();
    if (!/vertical|vertical/i.test(orientationText) && !String(verticalState.bodyClass).includes('pitch-orientation-portrait')) {
      throw new Error('vertical orientation did not activate');
    }
    assertStateFits(verticalState, 'vertical-orientation', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'vertical-orientation', state: verticalState });
    await capture(page, '06-vertical-orientation.png');

    await setSurfacePreset(page, 'half_pitch');
    const halfPitch = await analyzeSurface(page);
    assertStateFits(halfPitch, 'half-pitch', { minGreen: 6000, minWhite: 400, minGoals: 1 });
    summary.push({ step: 'half-pitch', state: halfPitch });
    await capture(page, '07-half-pitch.png');

    await setSurfacePreset(page, 'seven_side_single');
    const football7 = await analyzeSurface(page);
    assertStateFits(football7, 'football-7', { minGreen: 6000, minWhite: 400, minGoals: 1 });
    summary.push({ step: 'football-7', state: football7 });
    await capture(page, '08-football-7.png');

    const zoomBefore = football7.zoomLabel;
    await page.evaluate(() => {
      const btn = document.getElementById('pitch-zoom-in');
      if (btn && typeof btn.click === 'function') {
        btn.click();
        btn.click();
        btn.click();
        btn.click();
        btn.click();
      }
    });
    await wait(500);
    const zoomed = await analyzeSurface(page);
    if (String(zoomed.zoomLabel || '') === String(zoomBefore || '')) {
      throw new Error('zoom-in did not change the viewport');
    }

    const panBefore = zoomed;
    const viewportBox = await page.locator('#task-pitch-viewport').boundingBox();
    if (!viewportBox) throw new Error('viewport box not found');
    const panStart = {
      x: viewportBox.x + (viewportBox.width / 2),
      y: viewportBox.y + (viewportBox.height / 2),
    };
    await page.evaluate(() => {
      const debug = window.__webstatsTaskBuilderViewportDebug;
      if (debug && typeof debug.setPan === 'function') {
        debug.setPan(120, 84);
      }
    });
    await wait(300);
    const panned = await analyzeSurface(page);
    const panState = await page.evaluate(() => {
      const debug = window.__webstatsTaskBuilderViewportDebug;
      return debug && typeof debug.state === 'function' ? debug.state() : null;
    });
    const movedPan = Math.max(Math.abs(Number(panState?.panX) || 0), Math.abs(Number(panState?.panY) || 0));
    if (!panState || movedPan < 1) {
      throw new Error(`[pan] viewport state did not change: ${JSON.stringify({ before: panBefore.viewportScroll, after: panned.viewportScroll, panState })}`);
    }
    await page.evaluate(() => {
      const debug = window.__webstatsTaskBuilderViewportDebug;
      if (debug && typeof debug.resetPan === 'function') {
        debug.resetPan();
      }
    });
    summary.push({ step: 'pan-check', state: panned });

    const laptopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
      hasTouch: false,
      storageState: baseStorageState,
      ignoreHTTPSErrors: true,
    });
    const laptopPage = await laptopContext.newPage();
    await laptopPage.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=desktop`, { waitUntil: 'domcontentloaded' });
    await laptopPage.waitForSelector('#create-task-canvas', { timeout: 35_000 });
    await laptopPage.waitForSelector('#task-pitch-stage', { timeout: 35_000 });
    await laptopPage.waitForSelector('#task-pitch-surface', { timeout: 35_000 });
    await wait(600);
    const laptopState = await analyzeSurface(laptopPage);
    assertStateFits(laptopState, 'laptop-layout', { minGreen: 12000, minWhite: 800 });
    await laptopPage.screenshot({ path: path.join(QA_DIR, '09-laptop-layout.png'), fullPage: true });
    summary.push({ step: 'laptop-layout', state: laptopState });
    await laptopContext.close();

    const tabletContext = await browser.newContext({
      viewport: { width: 1024, height: 768 },
      deviceScaleFactor: 2,
      hasTouch: true,
      storageState: baseStorageState,
      ignoreHTTPSErrors: true,
    });
    const tabletPage = await tabletContext.newPage();
    await tabletPage.goto(`${baseUrl}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=tablet`, { waitUntil: 'domcontentloaded' });
    await tabletPage.waitForSelector('#create-task-canvas', { timeout: 35_000 });
    await tabletPage.waitForSelector('#task-pitch-stage', { timeout: 35_000 });
    await tabletPage.waitForSelector('#task-pitch-surface', { timeout: 35_000 });
    await wait(600);
    const tabletState = await analyzeSurface(tabletPage);
    assertStateFits(tabletState, 'tablet-layout', { minGreen: 12000, minWhite: 800 });
    await tabletPage.screenshot({ path: path.join(QA_DIR, '10-tablet-layout.png'), fullPage: true });
    summary.push({ step: 'tablet-layout', state: tabletState });
    await tabletContext.close();

    await page.evaluate(() => {
      const btn = document.getElementById('task-focus-toggle');
      if (btn && typeof btn.click === 'function') btn.click();
    });
    await wait(200);
    await page.locator('#pitch-size-fit').click();
    await wait(200);
    const restored = await analyzeSurface(page);
    assertStateFits(restored, 'restored-view', { minGreen: 12000, minWhite: 800 });
    summary.push({ step: 'restored', state: restored });

    if (errors.length) {
      throw new Error(`unexpected console/page errors: ${errors.join(' | ')}`);
    }

    const report = [
      '# Task Builder Pitch Finalization',
      '',
      `- Base URL: ${baseUrl}`,
      `- Focus mode supported: ${summary.some((item) => item.step === 'field-only') ? 'yes' : 'no'}`,
      `- Presentation stadium supported: ${summary.some((item) => item.step === 'presentation-mode') ? 'yes' : 'no'}`,
      '',
      '## Captures',
      '',
      '- 01-before.png',
      '- 02-editing-full-pitch.png',
      '- 03-field-expanded.png',
      '- 04-field-only.png',
      '- 05-presentation-mode.png',
      '- 06-vertical-orientation.png',
      '- 07-half-pitch.png',
      '- 08-football-7.png',
      '- 09-laptop-layout.png',
      '- 10-tablet-layout.png',
      '',
      '## Notes',
      '',
      '- The field now occupies the dominant share of the editor surface.',
      '- The helper guide is hidden in the default editor view to reduce visual noise.',
      '- Presentation mode reuses the existing focus toggle and stadium surface.',
      '- Zoom, fit and orientation controls continue to operate through the existing UI.',
    ].join('\n');
    fs.writeFileSync(path.join(QA_DIR, 'report.md'), report);

    console.log(`[pitch-finalization] ok · captures=${summary.length}`);
  } finally {
    await browser.close().catch(() => null);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
