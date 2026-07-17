/* eslint-disable no-console */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { chromium } = require('playwright');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = require('node:http').get(
      url,
      { headers: { 'Cache-Control': 'no-cache' } },
      (res) => {
        res.resume();
        resolve({ status: res.statusCode || 0 });
      }
    );
    req.on('error', reject);
    req.setTimeout(5000, () => req.destroy(new Error('timeout')));
  });
}

async function waitForServer(baseUrl, timeoutMs = 120_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await httpGet(`${baseUrl}/login/`);
      if (res.status >= 200 && res.status < 500) {
        return true;
      }
    } catch (error) {
      // ignore
    }
    await wait(750);
  }
  return false;
}

function spawnLogged(command, args, options = {}) {
  const proc = spawn(command, args, {
    stdio: 'inherit',
    ...options,
  });
  return new Promise((resolve, reject) => {
    proc.on('error', reject);
    proc.on('exit', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${args.join(' ')} failed with code ${code}`));
      }
    });
  });
}

async function seedFixture(dbUrl, username, password) {
  const shellCode = `
from datetime import date
from football.models import AppUserRole, SessionTask, Team, TrainingMicrocycle, TrainingSession, Workspace, WorkspaceMembership, WorkspaceTeam
from django.contrib.auth import get_user_model

username = ${JSON.stringify(username)}
password = ${JSON.stringify(password)}
User = get_user_model()
user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
user.email = f"{username}@example.com"
user.set_password(password)
user.save()
AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})
team, _ = Team.objects.get_or_create(
    slug="tactical-editor-professional-tools",
    defaults={"name": "Tactical Editor Professional Tools", "is_primary": True},
)
workspace, _ = Workspace.objects.get_or_create(
    slug="tactical-editor-professional-tools",
    defaults={
        "name": "Tactical Editor Professional Tools",
        "kind": Workspace.KIND_CLUB,
        "primary_team": team,
        "owner_user": user,
        "enabled_modules": {"sessions": True},
        "is_active": True,
    },
)
workspace.enabled_modules = {"sessions": True}
workspace.primary_team = team
workspace.owner_user = user
workspace.is_active = True
workspace.save()
WorkspaceMembership.objects.update_or_create(
    workspace=workspace,
    user=user,
    defaults={"role": WorkspaceMembership.ROLE_OWNER, "module_access": {"sessions": True}},
)
WorkspaceTeam.objects.update_or_create(
    workspace=workspace,
    team=team,
    defaults={"is_default": True},
)
microcycle, _ = TrainingMicrocycle.objects.get_or_create(
    team=team,
    title="Micro tactical editor professional tools",
    defaults={"week_start": date(2026, 7, 13), "week_end": date(2026, 7, 19)},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date(2026, 7, 15),
    defaults={"focus": "Salida de balón", "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title="Tarea base editor profesional",
    defaults={"block": SessionTask.BLOCK_MAIN_1, "duration_minutes": 18},
)
task.block = SessionTask.BLOCK_MAIN_1
task.duration_minutes = 18
task.tactical_layout = {
    "meta": {
        "graphic_editor": {
            "canvas_state": {
                "schemaVersion": 1,
                "documentId": str(task.id),
                "pitch": {
                    "type": "full",
                    "orientation": "landscape",
                    "surface": "grass",
                    "width": 105,
                    "height": 68,
                },
                "canvas": {"width": 1280, "height": 720, "padding": 28},
                "viewport": {"zoom": 1, "x": 0, "y": 0},
                "layers": [],
                "objects": [],
                "timeline": {"duration": 0, "currentTime": 0, "keyframes": []},
                "metadata": {
                    "title": task.title,
                    "createdAt": "",
                    "updatedAt": "",
                    "source": "professional-tools-v1",
                },
            },
            "canvas_width": 1280,
            "canvas_height": 720,
        }
    }
}
task.save()
print(task.id)
`;
  const result = spawnSync('python3', ['manage.py', 'shell', '-c', shellCode], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      DATABASE_URL: dbUrl,
      DEBUG: 'true',
      SECRET_KEY: process.env.SECRET_KEY || 'dev',
      ALLOW_SQLITE_IN_PROD: 'true',
    },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  if (result.status !== 0) {
    throw new Error('Seed fixture failed');
  }
  const taskId = Number(String(result.stdout || '').trim().split(/\s+/).pop());
  if (!Number.isFinite(taskId)) {
    throw new Error(`Invalid task id from seed: ${result.stdout}`);
  }
  return taskId;
}

function canvasBox(page) {
  return page.locator('.te-konva-stage').boundingBox();
}

async function clickCanvas(page, box, xRatio, yRatio) {
  await page.mouse.click(
    Math.round(box.x + box.width * xRatio),
    Math.round(box.y + box.height * yRatio)
  );
}

async function dragCanvas(page, box, from, to, options = {}) {
  await page.mouse.move(box.x + box.width * from[0], box.y + box.height * from[1]);
  await page.mouse.down(options);
  await page.mouse.move(box.x + box.width * to[0], box.y + box.height * to[1], {
    steps: 20,
  });
  await page.mouse.up(options);
}

async function openEditor(page, baseUrl, taskId, username, password) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/editor-pro/?editor2d=1`, {
    waitUntil: 'domcontentloaded',
  });
  await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
  await page.locator('text=Motor 2D Konva').waitFor({ state: 'visible', timeout: 30_000 });
}

async function selectTool(page, name, options = {}) {
  await page.getByRole('button', { name, ...options }).click();
}

async function selectAsset(page, label) {
  await page.locator('.te-asset-card').filter({ hasText: label }).first().click();
}

async function readSceneJson(page) {
  await page.getByRole('button', { name: /Copiar JSON/i }).click();
  return page.evaluate(() => navigator.clipboard.readText());
}

async function savePng(page, outDir, name) {
  const box = await canvasBox(page);
  await page.locator('.te-konva-stage').screenshot({ path: path.join(outDir, name) });
  return box;
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-editor-professional-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath}`;
  const port = Number(process.env.E2E_PORT || 8132);
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'editor-professional';
  const password = process.env.E2E_PASSWORD || 'editor-professional';
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-editor-phase-2b', 'professional-tools');
  fs.mkdirSync(outDir, { recursive: true });

  await spawnLogged('python3', ['manage.py', 'migrate', '--noinput'], {
    cwd: repoRoot,
    env: {
      ...process.env,
      DATABASE_URL: dbUrl,
      DEBUG: 'true',
      SECRET_KEY: process.env.SECRET_KEY || 'dev',
      ALLOW_SQLITE_IN_PROD: 'true',
    },
  });

  const taskId = await seedFixture(dbUrl, username, password);

  const serverProc = spawn('python3', ['manage.py', 'runserver', `127.0.0.1:${port}`, '--noreload'], {
    cwd: repoRoot,
    env: {
      ...process.env,
      DATABASE_URL: dbUrl,
      DEBUG: 'true',
      SECRET_KEY: process.env.SECRET_KEY || 'dev',
      ALLOW_SQLITE_IN_PROD: 'true',
    },
    stdio: 'inherit',
  });

  const serverReady = await waitForServer(baseUrl);
  if (!serverReady) {
    serverProc.kill('SIGTERM');
    throw new Error('The tactical editor test server did not start');
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    acceptDownloads: true,
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  page.on('console', (message) => {
    if (message.type() === 'error') {
      console.error('[browser-console]', message.text());
    }
  });
  page.on('pageerror', (error) => {
    console.error('[browser-pageerror]', error);
  });

  const report = [];
  const record = (name, details) => {
    report.push({ name, ...details });
  };

  try {
    await openEditor(page, baseUrl, taskId, username, password).catch(async (error) => {
      console.error('[debug] current url', page.url());
      await page.screenshot({ path: path.join(outDir, 'debug-open-editor-failure.png'), fullPage: true }).catch(() => {});
      throw error;
    });
    await savePng(page, outDir, '01-editor-open.png');
    record('editor-open', { result: 'ok' });

    await selectAsset(page, 'Jugador local');
    await clickCanvas(page, await canvasBox(page), 0.34, 0.36);
    await selectAsset(page, 'Jugador visitante');
    await clickCanvas(page, await canvasBox(page), 0.48, 0.42);
    await selectAsset(page, 'Cono');
    await clickCanvas(page, await canvasBox(page), 0.58, 0.48);
    await selectAsset(page, 'Flecha curva');
    await clickCanvas(page, await canvasBox(page), 0.72, 0.38);
    await savePng(page, outDir, '02-objects-inserted.png');

    await selectTool(page, 'Seleccionar', { exact: true });
    await page.keyboard.down(process.platform === 'darwin' ? 'Meta' : 'Control');
    await page.mouse.click(
      Math.round((await canvasBox(page)).x + (await canvasBox(page)).width * 0.34),
      Math.round((await canvasBox(page)).y + (await canvasBox(page)).height * 0.36)
    );
    await page.keyboard.up(process.platform === 'darwin' ? 'Meta' : 'Control');
    const box = await canvasBox(page);
    await dragCanvas(page, box, [0.28, 0.28], [0.63, 0.54]);
    await page.getByText(/4 objeto\(s\)|3 objeto\(s\)/).waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    await savePng(page, outDir, '03-marquee-selection.png');

    await page.getByRole('button', { name: 'Snap' }).click();
    await page.getByRole('button', { name: 'Guías' }).click();
    await page.getByRole('button', { name: 'Grid' }).click();
    await page.getByRole('button', { name: 'Ajustar campo' }).click();
    await savePng(page, outDir, '04-snap-guides-fit.png');

    const inspector = page.locator('.te-inspector');
    await inspector.getByRole('button', { name: 'Seleccionar todo' }).click();
    await inspector.getByRole('button', { name: 'Alinear izq.' }).click();
    await inspector.getByRole('button', { name: 'Distribuir H' }).click();
    await inspector.getByRole('button', { name: 'Agrupar', exact: true }).click();
    await page.keyboard.press(`${process.platform === 'darwin' ? 'Meta' : 'Control'}+Shift+G`);
    await page.keyboard.press(`${process.platform === 'darwin' ? 'Meta' : 'Control'}+G`);
    await savePng(page, outDir, '05-grouping-and-alignment.png');

    const contextBox = await canvasBox(page);
    await page.mouse.click(
      Math.round(contextBox.x + contextBox.width * 0.34),
      Math.round(contextBox.y + contextBox.height * 0.36),
      { button: 'right' }
    );
    const contextMenu = page.locator('.te-context-menu');
    await contextMenu.waitFor({ state: 'visible', timeout: 10_000 });
    await contextMenu.getByRole('button', { name: 'Bloquear' }).click();
    await savePng(page, outDir, '06-context-menu-lock.png');

    await page.mouse.click(
      Math.round(contextBox.x + contextBox.width * 0.34),
      Math.round(contextBox.y + contextBox.height * 0.36),
      { button: 'right' }
    );
    await contextMenu.waitFor({ state: 'visible', timeout: 10_000 });
    await page.once('dialog', async (dialog) => dialog.accept('equipment'));
    await contextMenu.getByRole('button', { name: 'Mover a capa' }).click();
    await contextMenu.getByRole('button', { name: 'Traer al frente' }).click();

    const selectionTypeSelect = inspector
      .locator('.te-stat-card')
      .filter({ hasText: 'Selección por tipo' })
      .locator('select');
    await selectionTypeSelect.selectOption({ label: 'Jugador local' });
    const nameInput = inspector.getByRole('textbox', { name: 'Nombre' });
    await nameInput.waitFor({ state: 'visible', timeout: 10_000 });
    await nameInput.fill('Jugador eje');
    const numberInput = inspector.getByRole('textbox', { name: 'Dorsal' });
    await numberInput.fill('10');
    await inspector.getByLabel('Color').first().fill('#16a34a');
    await savePng(page, outDir, '07-inspector-editing.png');

    await page.getByRole('button', { name: /Guardar pizarra|Guardando\.\.\.|Pizarra guardada/ }).click();
    await page.waitForTimeout(1500);
    const beforeReload = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'scene-before-reload.json'), JSON.stringify(beforeReload, null, 2), 'utf8');
    assert.ok(beforeReload.objects.length >= 3, 'The scene should contain inserted objects');
    assert.ok(
      beforeReload.objects.some((object) => object.data && object.data.name === 'Jugador eje'),
      'The edited player should be persisted'
    );

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await savePng(page, outDir, '08-after-reload.png');

    const afterReload = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'scene-after-reload.json'), JSON.stringify(afterReload, null, 2), 'utf8');
    assert.equal(afterReload.objects.length, beforeReload.objects.length, 'Reload should keep the scene size');
    assert.ok(
      afterReload.objects.some((object) => object.data && object.data.name === 'Jugador eje'),
      'Reload should keep the edited player name'
    );

    const exportPngPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar PNG' }).click();
    const pngDownload = await exportPngPromise;
    await pngDownload.saveAs(path.join(outDir, 'exported-scene.png'));

    const exportJsonPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar JSON' }).click();
    const jsonDownload = await exportJsonPromise;
    await jsonDownload.saveAs(path.join(outDir, 'exported-scene.json'));

    await page.getByRole('button', { name: 'Importar JSON' }).click();
    await page.locator('input[type="file"]').setInputFiles(path.join(outDir, 'exported-scene.json'));
    await page.waitForTimeout(1000);
    await savePng(page, outDir, '09-after-import.png');
    const afterImport = JSON.parse(await readSceneJson(page));
    assert.equal(afterImport.objects.length, afterReload.objects.length, 'Import should keep object count');
    assert.ok(
      afterImport.objects.some((object) => object.data && object.data.name === 'Jugador eje'),
      'Import should keep the edited player name'
    );

    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(500);
    await savePng(page, outDir, '10-responsive.png');

    record('export', { result: 'png/json saved', outDir });
    fs.writeFileSync(
      path.join(outDir, 'report.md'),
      `# Tactical editor professional tools QA\n\n` +
        report.map((item) => `- ${item.name}: ${JSON.stringify(item)}`).join('\n') +
        '\n',
      'utf8'
    );
  } finally {
    await browser.close().catch(() => {});
    serverProc.kill('SIGTERM');
    await wait(1000);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
