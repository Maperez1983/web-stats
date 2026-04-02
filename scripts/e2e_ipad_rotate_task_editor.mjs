import { webkit, devices } from 'playwright';

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000';
const USERNAME = process.env.E2E_USER || 'e2e';
const PASSWORD = process.env.E2E_PASS || 'e2e';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

async function placeLocalPlayer(page, position) {
  // Espera a que Fabric haya inicializado el canvas y los listeners del editor.
  await page.locator('canvas.upper-canvas').first().waitFor({ state: 'attached', timeout: 20000 });

  // Usa el toolstrip principal (no el strip draggable).
  const addButton = page.locator('#task-basic-tools [data-add="player_local"]').first();
  await addButton.waitFor({ state: 'visible' });
  await addButton.scrollIntoViewIfNeeded();
  await addButton.click({ force: true });
  await page.waitForTimeout(250);

  // Coloca sobre el canvas de interacción (Fabric -> upper-canvas). En iPad puede estar dentro de un viewport con scroll.
  const upperCanvas = page.locator('canvas.upper-canvas').first();
  await page.evaluate(() => {
    const el = document.querySelector('#task-pitch-viewport');
    try { el?.scrollIntoView({ block: 'center', inline: 'nearest' }); } catch {}
  });
  await page.waitForTimeout(250);
  await upperCanvas.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  // Dispara click en el canvas (Fabric escucha mouse:down).
  await upperCanvas.click({ position: { x: position?.x || 200, y: position?.y || 150 }, force: true });
  await page.waitForTimeout(650);
  const status = await page.evaluate(() => (document.getElementById('task-builder-status')?.textContent || '').trim());
  if (!status.toLowerCase().includes('elemento colocado')) {
    throw new Error(`No se confirmó la colocación del elemento. Status: ${JSON.stringify(status)}`);
  }
}

async function rotateViewport(page, width, height) {
  await page.setViewportSize({ width, height });
  await page.evaluate(() => {
    try {
      window.dispatchEvent(new Event('orientationchange'));
    } catch {}
  });
  // Espera al debounce del resize del editor (200ms + margen).
  await sleep(750);
}

async function main() {
  const iPad = devices['iPad (gen 7)'] || devices['iPad Pro 11'];
  assert(iPad, 'No se encontró el descriptor de dispositivo iPad en Playwright');

  const browser = await webkit.launch();
  const context = await browser.newContext(iPad);
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err?.message || String(err)}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(`console.error: ${msg.text()}`);
  });

  await page.goto(`${BASE_URL}/login/?next=/coach/sesiones/tareas/nueva/`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username').fill(USERNAME);
  await page.locator('#id_password').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/coach/sesiones/tareas/nueva/**', { timeout: 20000 });

  // Fuerza modo iPad para el layout del editor.
  const tabletToggle = page.locator('.device-toggle [data-device-mode="tablet"]');
  if (await tabletToggle.count()) await tabletToggle.click();
  await page.waitForTimeout(1000);

  // Espera a que el editor esté listo.
  await page.locator('#create-task-canvas').waitFor({ state: 'visible' });
  await page.waitForTimeout(350);

  await placeLocalPlayer(page, { x: 180, y: 140 });

  // Simula rotación a portrait y vuelve a landscape.
  const initialViewport = page.viewportSize();
  assert(initialViewport, 'No se pudo leer viewport inicial');
  await rotateViewport(page, Math.min(initialViewport.height, 1024), Math.min(initialViewport.width, 768));

  await placeLocalPlayer(page, { x: 480, y: 180 });

  await rotateViewport(page, initialViewport.width, initialViewport.height);
  await placeLocalPlayer(page, { x: 260, y: 340 });

  if (consoleErrors.length) {
    throw new Error(`Se detectaron errores JS durante la prueba:\n- ${consoleErrors.join('\n- ')}`);
  }

  await browser.close();
  console.log('OK: rotación iPad mantiene edición en el editor de tareas.');
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
