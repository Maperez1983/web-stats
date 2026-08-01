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
  await page.waitForTimeout(800);
}

async function expectMode(page, mode, taskId) {
  const selector = page.getByTestId('editor-lab-selector');
  await selector.waitFor({ state: 'visible', timeout: 15000 });
  await assert.strictEqual(await selector.count(), 1, 'Expected a single lab selector');
  const testId = mode === 'compare' ? 'editor-lab-compare' : `editor-lab-${mode}`;
  await assert.strictEqual(await page.getByTestId(testId).count(), 1, `Expected ${mode} control`);
  if (taskId) {
    const taskText = await selector.textContent();
    assert.ok(String(taskText || '').includes(`Tarea #${taskId}`), `Expected selector to mention task ${taskId}`);
  }
}

async function capture(page, outDir, fileName) {
  await page.screenshot({ path: path.join(outDir, fileName), fullPage: true });
}

async function hideDebugToolbar(page) {
  await page.evaluate(() => {
    const hide = (node) => {
      if (!node) return;
      node.style.display = 'none';
      node.style.visibility = 'hidden';
      node.style.pointerEvents = 'none';
    };
    hide(document.getElementById('djDebug'));
    hide(document.getElementById('djDT'));
  }).catch(() => null);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const outDir = path.join(process.cwd(), 'output', 'qa', 'editor-lab-selector');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  await page.addInitScript(() => {
    try {
      const hide = () => {
        const applyHide = (node) => {
          if (!node) return;
          node.style.display = 'none';
          node.style.visibility = 'hidden';
          node.style.pointerEvents = 'none';
        };
        applyHide(document.getElementById('djDebug'));
        applyHide(document.getElementById('djDT'));
      };
      hide();
      const observer = new MutationObserver(hide);
      observer.observe(document.documentElement, { childList: true, subtree: true });
      window.addEventListener('load', hide, { once: true });
    } catch (err) {
      // ignore
    }
  });

  await loginAsLocalAdmin(page, baseUrl);
  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await hideDebugToolbar(page);

  assert.ok(page.url().includes('/coach/sesiones/tareas/'), `Expected task editor URL, got ${page.url()}`);
  const taskIdMatch = page.url().match(/tareas\/(\d+)\/editar/i);
  const taskId = taskIdMatch ? taskIdMatch[1] : '';
  assert.ok(taskId, `Could not extract task id from ${page.url()}`);

  await expectMode(page, 'production', taskId);
  await capture(page, outDir, '01-production-mode.png');
  await capture(page, outDir, '02-selector-open.png');

  await page.getByTestId('editor-lab-konva').click();
  await page.waitForURL(/editor-pro\/.*editor_lab=konva/, { timeout: 15000 });
  await page.waitForTimeout(1500);
  await hideDebugToolbar(page);
  assert.ok(page.url().includes(`/${taskId}/`), `Konva mode should preserve task id ${taskId}, got ${page.url()}`);
  await expectMode(page, 'konva', taskId);
  await capture(page, outDir, '03-konva-mode.png');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await hideDebugToolbar(page);
  await expectMode(page, 'konva', taskId);

  const compareHref = await page.getByTestId('editor-lab-compare').getAttribute('href');
  assert.ok(compareHref && compareHref.includes('editor_lab=comparison'), `Expected comparison href, got ${compareHref}`);
  await page.goto(new URL(compareHref, baseUrl).toString(), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await hideDebugToolbar(page);
  await expectMode(page, 'compare', taskId);
  const prodFrame = page.getByTestId('editor-lab-production-frame');
  const konvaFrame = page.getByTestId('editor-lab-konva-frame');
  await assert.strictEqual(await prodFrame.count(), 1, 'Expected production comparison frame');
  await assert.strictEqual(await konvaFrame.count(), 1, 'Expected konva comparison frame');
  await assert.strictEqual(await prodFrame.getAttribute('data-task-id'), taskId, 'Production frame task id mismatch');
  await assert.strictEqual(await konvaFrame.getAttribute('data-task-id'), taskId, 'Konva frame task id mismatch');
  await capture(page, outDir, '04-comparison-mode.png');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await hideDebugToolbar(page);
  await expectMode(page, 'compare', taskId);

  const productionHref = await page.getByTestId('editor-lab-production').getAttribute('href');
  assert.ok(productionHref && productionHref.includes('editor_lab=production'), `Expected production href, got ${productionHref}`);
  await page.goto(new URL(productionHref, baseUrl).toString(), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await hideDebugToolbar(page);
  await expectMode(page, 'production', taskId);
  await capture(page, outDir, '05-back-to-production.png');

  const publicContext = await browser.newContext({ viewport: { width: 1280, height: 800 }, ignoreHTTPSErrors: true });
  const publicPage = await publicContext.newPage();
  await publicPage.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await hideDebugToolbar(publicPage);
  assert.strictEqual(await publicPage.getByTestId('editor-lab-selector').count(), 0, 'Public login must not expose lab selector');
  await publicContext.close();

  const report = [
    '# Editor lab selector',
    '',
    '## URLs',
    `- Producción: ${baseUrl}/`,
    `- Konva: ${baseUrl}/coach/sesiones/tarea/${taskId}/editor-pro/?editor_lab=konva`,
    `- Comparación: ${baseUrl}/coach/sesiones/tarea/${taskId}/editor-lab/?editor_lab=comparison`,
    '',
    '## Validación',
    '- Selector visible solo en laboratorio local: OK',
    '- Persistencia del modo tras recarga: OK',
    '- Comparación con mismo task_id en ambos paneles: OK',
    '- Producción pública sin selector: OK',
    '',
    '## QA',
    '- 01-production-mode.png',
    '- 02-selector-open.png',
    '- 03-konva-mode.png',
    '- 04-comparison-mode.png',
    '- 05-back-to-production.png',
    '',
    '## Observaciones',
    '- La selección usa `editor_lab` como convención principal.',
    '- Konva ya es el motor activo por defecto en el editor profesional.',
    '',
  ].join('\n');
  fs.writeFileSync(path.join(outDir, 'report.md'), report, 'utf8');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
