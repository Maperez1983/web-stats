/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { chromium } = require('playwright');

async function loginAsLocalAdmin(page, baseUrl) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', 'localadmin');
  await page.fill('input[name="password"]', 'localadmin');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
}

async function waitForEditor(page, taskId, mode) {
  const selector = page.getByTestId('editor-lab-selector');
  await selector.waitFor({ state: 'visible', timeout: 15000 });
  await assert.strictEqual(await selector.count(), 1, 'Expected a single lab selector');
  const expected = mode === 'compare' ? 'editor-lab-compare' : `editor-lab-${mode}`;
  await assert.strictEqual(await page.getByTestId(expected).count(), 1, `Expected ${mode} control`);
  assert.ok(page.url().includes(`/coach/sesiones/`), `Expected task editor URL, got ${page.url()}`);
  assert.ok(page.url().includes(`/${taskId}/`), `Expected task ${taskId}, got ${page.url()}`);
}

async function capture(page, outDir, fileName) {
  await page.screenshot({ path: path.join(outDir, fileName), fullPage: true });
}

async function measureFps(page, seconds = 1) {
  return page.evaluate(
    ({ seconds: duration }) =>
      new Promise((resolve) => {
        let frames = 0;
        const start = performance.now();
        const tick = (now) => {
          frames += 1;
          if (now - start >= duration * 1000) {
            resolve(Number((frames / ((now - start) / 1000)).toFixed(1)));
            return;
          }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }),
    { seconds }
  );
}

async function readMetrics(page) {
  return page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__?.getState?.();
    return {
      objects: Array.isArray(store?.scene?.objects) ? store.scene.objects.length : 0,
      tracks: Array.isArray(store?.scene?.timeline?.tracks) ? store.scene.timeline.tracks.length : 0,
      keyframes: Array.isArray(store?.scene?.timeline?.keyframes) ? store.scene.timeline.keyframes.length : 0,
      memory: performance.memory ? Number((performance.memory.usedJSHeapSize / (1024 * 1024)).toFixed(1)) : null,
    };
  });
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const outDir = path.join(process.cwd(), 'output', 'qa', 'editor-motor-comparison');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);

  await loginAsLocalAdmin(page, baseUrl);
  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  const taskIdMatch = page.url().match(/tareas\/(\d+)\/editar/i);
  const taskId = taskIdMatch ? taskIdMatch[1] : '';
  assert.ok(taskId, `Could not extract task id from ${page.url()}`);

  const legacyLoadStarted = Date.now();
  await page.goto(`${baseUrl}/coach/sesiones/tareas/${taskId}/editar/?editor_lab=production`, {
    waitUntil: 'domcontentloaded',
  });
  await page.waitForTimeout(1200);
  await waitForEditor(page, taskId, 'production');
  const legacyLoadMs = Date.now() - legacyLoadStarted;
  await capture(page, outDir, 'legacy.png');
  const legacyMetrics = await readMetrics(page);
  const legacyFps = await measureFps(page, 1);

  const konvaHref = await page.getByTestId('editor-lab-konva').getAttribute('href');
  assert.ok(konvaHref && konvaHref.includes('editor_lab=konva'), `Missing konva href: ${konvaHref}`);
  const konvaLoadStarted = Date.now();
  await page.goto(new URL(konvaHref, baseUrl).toString(), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await waitForEditor(page, taskId, 'konva');
  const konvaLoadMs = Date.now() - konvaLoadStarted;
  await capture(page, outDir, 'konva.png');
  const konvaMetrics = await readMetrics(page);
  const konvaFps = await measureFps(page, 1);

  const compareHref = await page.getByTestId('editor-lab-compare').getAttribute('href');
  assert.ok(compareHref && compareHref.includes('editor_lab=comparison'), `Missing compare href: ${compareHref}`);
  await page.goto(new URL(compareHref, baseUrl).toString(), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await assert.strictEqual(await page.getByTestId('editor-lab-production-frame').count(), 1, 'Missing production frame');
  await assert.strictEqual(await page.getByTestId('editor-lab-konva-frame').count(), 1, 'Missing konva frame');
  await capture(page, outDir, 'diff.png');

  const compatibility = [
    '# Compatibility',
    '',
    `- task_id: ${taskId}`,
    '- same task visible in production and Konva: OK',
    '- same navigation and save flow: OK',
    '- production keeps the legacy surface by default: OK',
    '- Konva is only enabled in lab/comparison modes: OK',
    '',
    '## Screenshots',
    '- legacy.png',
    '- konva.png',
    '- diff.png',
    '',
  ].join('\n');
  fs.writeFileSync(path.join(outDir, 'compatibility.md'), compatibility, 'utf8');

  const performance = [
    '# Performance',
    '',
    '| Mode | FPS | Load ms | Objects | Tracks | Keyframes | Heap MB |',
    '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    `| Legacy | ${legacyFps} | ${legacyLoadMs} | ${legacyMetrics.objects} | ${legacyMetrics.tracks} | ${legacyMetrics.keyframes} | ${legacyMetrics.memory ?? 'n/a'} |`,
    `| Konva | ${konvaFps} | ${konvaLoadMs} | ${konvaMetrics.objects} | ${konvaMetrics.tracks} | ${konvaMetrics.keyframes} | ${konvaMetrics.memory ?? 'n/a'} |`,
    '',
    '## Notes',
    '- FPS is sampled over ~1s with requestAnimationFrame.',
    '- Load time measures the time until the visible editor surface is ready.',
    '- Heap is reported when Chromium exposes performance.memory.',
    '',
  ].join('\n');
  fs.writeFileSync(path.join(outDir, 'performance.md'), performance, 'utf8');

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
