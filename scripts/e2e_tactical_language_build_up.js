/* eslint-disable no-console */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const {
  canvasBox,
  clickCanvasAtScene,
  configureSelectedPlayer,
  getFreePort,
  getNewSceneObjectId,
  getSceneState,
  openEditor,
  readSceneJson,
  saveBoard,
  selectAsset,
  selectSceneObjectById,
  selectTool,
  fillInspectorField,
  seedTacticalEditorTask,
  spawnLogged,
  takeShot,
  wait,
  waitForServer,
} = require('./e2e/helpers/tacticalEditorHelpers');

async function insertConfiguredPlayer(page, box, asset, center, config) {
  await selectAsset(page, asset);
  const beforeIds = (await getSceneState(page)).scene?.objects.map((object) => object.id) || [];
  await clickCanvasAtScene(page, box, center);
  const objectId = await getNewSceneObjectId(page, beforeIds);
  assert(objectId, `Expected ${config.name || asset} to be inserted`);
  await selectTool(page, 'Seleccionar');
  await selectSceneObjectById(page, objectId);
  if (config.name || config.label || config.number || config.team) {
    await configureSelectedPlayer(page, config);
  }
  return objectId;
}

async function insertConfiguredAsset(page, box, asset, center, label) {
  await selectAsset(page, asset);
  const beforeIds = (await getSceneState(page)).scene?.objects.map((object) => object.id) || [];
  await clickCanvasAtScene(page, box, center);
  const objectId = await getNewSceneObjectId(page, beforeIds);
  assert(objectId, `Expected ${asset} to be inserted`);
  await selectTool(page, 'Seleccionar');
  await selectSceneObjectById(page, objectId);
  if (label) {
    await fillInspectorField(page, 'Etiqueta', label);
  }
  return objectId;
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-language-mvp-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath.replace(/^\/+/, '')}`;
  const port = Number(process.env.E2E_PORT || (await getFreePort()));
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'tactical-language-mvp';
  const password = process.env.E2E_PASSWORD || 'tactical-language-mvp';
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-language-mvp', 'build-up');
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

  const taskId = await seedTacticalEditorTask(dbUrl, {
    username,
    password,
    teamSlug: 'tactical-language-mvp',
    teamName: 'Tactical Language MVP',
    workspaceSlug: 'tactical-language-mvp',
    workspaceName: 'Tactical Language MVP',
    microcycleTitle: 'Micro tactical language MVP',
    sessionDate: '2026-07-18',
    focus: 'Salida de balón automática',
    taskTitle: 'Tactical Language MVP',
    taskDurationMinutes: 18,
    source: 'tactical-language-mvp',
  });

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

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    acceptDownloads: true,
    permissions: ['clipboard-read', 'clipboard-write'],
    recordVideo: { dir: outDir, size: { width: 1600, height: 1100 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);

  try {
    if (!(await waitForServer(baseUrl))) {
      throw new Error('The tactical language test server did not start');
    }

    await openEditor(page, baseUrl, taskId, username, password);
    await page.getByTestId('viewport-board2d').click();
    await page.getByRole('button', { name: 'Ajustar campo' }).click();
    await wait(500);
    const box = await canvasBox(page);
    assert.ok(box, 'Missing canvas box');

    const goalkeeperId = await insertConfiguredPlayer(
      page,
      box,
      'goalkeeper.home.front',
      { x: 120, y: 340 },
      { name: 'Portero', label: 'GK', number: '1', team: 'home' }
    );
    const rcbId = await insertConfiguredPlayer(
      page,
      box,
      'player.home.back',
      { x: 250, y: 220 },
      { name: 'Central derecho', label: 'RCB', number: '4', team: 'home' }
    );
    const lcbId = await insertConfiguredPlayer(
      page,
      box,
      'player.home.back',
      { x: 250, y: 460 },
      { name: 'Central izquierdo', label: 'LCB', number: '5', team: 'home' }
    );
    const mcdId = await insertConfiguredPlayer(
      page,
      box,
      'player.home.front',
      { x: 390, y: 340 },
      { name: 'Mediocentro', label: 'MCD', number: '6', team: 'home' }
    );
    const rbId = await insertConfiguredPlayer(
      page,
      box,
      'player.home.side',
      { x: 350, y: 150 },
      { name: 'Lateral derecho', label: 'RB', number: '2', team: 'home' }
    );
    const ballId = await insertConfiguredAsset(page, box, 'ball.standard', { x: 120, y: 340 }, 'Balón');
    const pass1Id = await insertConfiguredAsset(page, box, 'arrow.pass', { x: 178, y: 300 }, 'Pase 1');
    const runId = await insertConfiguredAsset(page, box, 'arrow.run', { x: 462, y: 238 }, 'Carrera');
    const pass2Id = await insertConfiguredAsset(page, box, 'arrow.ball', { x: 430, y: 334 }, 'Pase 2');
    const zoneId = await insertConfiguredAsset(page, box, 'zone.rect', { x: 792, y: 248 }, 'Zona objetivo');

    assert.ok(goalkeeperId && rcbId && lcbId && mcdId && rbId && ballId && pass1Id && runId && pass2Id && zoneId);

    await takeShot(page, path.join(outDir, '01-scene-ready.png'));

    await page.getByTestId('generate-tactical-recreation').click();
    await page.waitForFunction(
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        return Boolean(
          state?.tacticalRecreation &&
            (state.tacticalRecreation.scene.timeline.tracks?.length || 0) >= 4 &&
            (state.tacticalRecreation.scene.timeline.keyframes?.length || 0) > 0
        );
      },
      null,
      { timeout: 30_000 }
    );

    const generatedScene = await readSceneJson(page);
    const parsedGeneratedScene = JSON.parse(generatedScene);
    fs.writeFileSync(path.join(outDir, 'recreation-scene.json'), JSON.stringify(parsedGeneratedScene, null, 2), 'utf8');
    fs.writeFileSync(
      path.join(outDir, 'recreation-animation.json'),
      JSON.stringify(parsedGeneratedScene.timeline, null, 2),
      'utf8'
    );

    await page.waitForFunction(
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) > 0.05;
      },
      null,
      { timeout: 10_000 }
    );
    await takeShot(page, path.join(outDir, '02-playing.png'));

    await page.getByTestId('animation-pause').click();
    await takeShot(page, path.join(outDir, '03-paused.png'));

    await page.getByTestId('animation-stop').click();
    await takeShot(page, path.join(outDir, '04-stopped.png'));

    await saveBoard(page);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await takeShot(page, path.join(outDir, '05-after-reload.png'));

    const reloadedScene = JSON.parse(await readSceneJson(page));
    assert.ok(Array.isArray(reloadedScene.timeline?.tracks));
    assert.ok((reloadedScene.timeline?.tracks || []).length >= 4);
    assert.ok(Array.isArray(reloadedScene.timeline?.keyframes));
    assert.ok((reloadedScene.timeline?.keyframes || []).length > 0);

    await page.getByTestId('generate-tactical-recreation').click();
    await page.waitForFunction(
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) > 0.05;
      },
      null,
      { timeout: 10_000 }
    );
    await takeShot(page, path.join(outDir, '06-playing-after-regenerate.png'));

    const video = page.video ? page.video() : null;
    if (video) {
      try {
        const videoPath = await video.path();
        fs.copyFileSync(videoPath, path.join(outDir, 'recreation-demo.webm'));
      } catch (error) {
        console.error('[tactical-language-mvp] video unavailable', error);
      }
    }

    fs.writeFileSync(
      path.join(outDir, 'report.md'),
      [
        '# Tactical Language MVP',
        '',
        '- Escenario: salida de balón desde portero',
        `- Objetos: ${parsedGeneratedScene.objects.length}`,
        `- Duration: ${parsedGeneratedScene.timeline?.duration || 0}`,
        `- Tracks: ${(parsedGeneratedScene.timeline?.tracks || []).length}`,
        `- Keyframes: ${(parsedGeneratedScene.timeline?.keyframes || []).length}`,
        '- Reproducción: OK',
        '- Persistencia: OK',
        '- Video: ' + (fs.existsSync(path.join(outDir, 'recreation-demo.webm')) ? 'Generado' : 'No disponible'),
        '',
        '## Capturas',
        '- 01-scene-ready.png',
        '- 02-playing.png',
        '- 03-paused.png',
        '- 04-stopped.png',
        '- 05-after-reload.png',
        '- 06-playing-after-regenerate.png',
      ].join('\n'),
      'utf8'
    );
  } finally {
    await page.close().catch(() => {});
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    serverProc.kill('SIGTERM');
    await new Promise((resolve) => serverProc.on('exit', resolve));
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
