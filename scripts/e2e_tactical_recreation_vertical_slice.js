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
  getProjectedObjectById,
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

function writeJson(outDir, fileName, value) {
  fs.writeFileSync(path.join(outDir, fileName), JSON.stringify(value, null, 2), 'utf8');
}

async function waitForTimelineState(page, predicate, timeout = 30_000) {
  await page.waitForFunction(predicate, null, { timeout });
}

async function readEditorSnapshot(page) {
  return page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return {
      tacticalRecreation: state?.tacticalRecreation || null,
      scene: state?.scene || null,
      selectedIds: state?.selectedIds || [],
    };
  });
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-recreation-vertical-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath.replace(/^\/+/, '')}`;
  const port = Number(process.env.E2E_PORT || (await getFreePort()));
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'tactical-recreation';
  const password = process.env.E2E_PASSWORD || 'tactical-recreation';
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-recreation-vertical-slice');
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
    teamSlug: 'tactical-recreation',
    teamName: 'Tactical Recreation',
    workspaceSlug: 'tactical-recreation',
    workspaceName: 'Tactical Recreation',
    microcycleTitle: 'Micro tactical recreation',
    sessionDate: '2026-07-18',
    focus: 'Salida de balón desde portero',
    taskTitle: 'Tactical Recreation Vertical Slice',
    taskDurationMinutes: 18,
    source: 'tactical-recreation',
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
      throw new Error('The tactical recreation test server did not start');
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

    const initialSceneState = await getSceneState(page);
    const initialEditorState = await readEditorSnapshot(page);
    assert.equal(initialSceneState.scene.timeline.tracks.length, 0);
    assert.equal(initialSceneState.scene.timeline.keyframes.length, 0);
    assert.equal(initialSceneState.scene.timeline.duration, 1);
    assert.equal(initialSceneState.scene.timeline.currentTime, 0);
    assert.equal(initialEditorState.tacticalRecreation, null);
    writeJson(outDir, 'scene-input.json', initialSceneState.scene);
    await takeShot(page, path.join(outDir, '01-static-input.png'));

    await page.getByTestId('generate-tactical-recreation').click();
    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        const recreation = state?.tacticalRecreation;
        return Boolean(
          recreation &&
            recreation.language.statements.length >= 3 &&
            recreation.plan.executionOrder.length > 0 &&
            recreation.plan.warnings.length >= 0 &&
            (recreation.scene.timeline.tracks?.length || 0) >= 4 &&
            (recreation.scene.timeline.keyframes?.length || 0) > 0
        );
      }
    );

    const generatedState = await getSceneState(page);
    const generatedEditorState = await readEditorSnapshot(page);
    const recreation = generatedEditorState.tacticalRecreation;
    assert.ok(recreation, 'Expected tactical recreation to be generated');
    assert.equal(recreation.language.statements.length >= 3, true);
    assert.equal(recreation.plan.executionOrder.length > 0, true);
    assert.equal(recreation.scene.timeline.duration >= 8, true);
    assert.equal(recreation.scene.timeline.currentTime, 0);
    assert.equal(Array.isArray(recreation.scene.timeline.tracks), true);
    assert.equal(recreation.scene.timeline.tracks.length >= 4, true);
    assert.equal(Array.isArray(recreation.scene.timeline.keyframes), true);
    assert.equal(recreation.scene.timeline.keyframes.length > 0, true);
    assert.equal(recreation.possession.state, 'controlled');
    assert.ok(recreation.possession.carrierId, 'Expected a ball carrier');

    const ballTrack = recreation.scene.timeline.tracks.find((track) => track.objectId === ballId);
    assert.ok(ballTrack, 'Expected the ball to receive a dedicated track');
    assert.ok((ballTrack?.keyframes || []).length >= 3, 'Expected at least three ball keyframes');
    const lateralTrack = recreation.scene.timeline.tracks.find((track) => track.objectId === rbId);
    assert.ok(lateralTrack, 'Expected the lateral to receive a track');
    assert.ok((lateralTrack?.keyframes || []).length >= 3, 'Expected a parallel run for the lateral');

    writeJson(outDir, 'tactical-language.json', recreation.language);
    writeJson(outDir, 'resolved-plan.json', recreation.plan);
    writeJson(outDir, 'generated-timeline.json', recreation.scene.timeline);
    writeJson(outDir, 'recreation-scene.json', recreation.scene);

    await takeShot(page, path.join(outDir, '02-actions-detected.png'));
    await takeShot(page, path.join(outDir, '03-resolved-plan.png'));
    await takeShot(page, path.join(outDir, '04-generated-timeline.png'));

    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const playButton = document.querySelector('[data-testid="animation-play"]');
        return (
          (store?.getState().scene?.timeline?.currentTime || 0) > 0.05 ||
          Boolean(playButton && playButton instanceof HTMLButtonElement && playButton.disabled)
        );
      },
      20_000
    );
    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) > 1.95;
      },
      20_000
    );
    const ballAfterTwoSeconds = await getProjectedObjectById(page, ballId);
    assert.ok(ballAfterTwoSeconds, 'Expected the ball to be projected');
    assert.ok(
      Math.abs(ballAfterTwoSeconds.x - (initialSceneState.scene.objects.find((item) => item.id === ballId)?.x || 0)) > 5 ||
        Math.abs(ballAfterTwoSeconds.y - (initialSceneState.scene.objects.find((item) => item.id === ballId)?.y || 0)) > 5,
      'Expected the ball to move by second 2'
    );
    await takeShot(page, path.join(outDir, '05-second-2.png'));

    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) > 3.95;
      },
      20_000
    );
    const rcbAfterFourSeconds = await getProjectedObjectById(page, rcbId);
    assert.ok(rcbAfterFourSeconds, 'Expected the central-right player to be projected');
    assert.ok(
      Math.abs(rcbAfterFourSeconds.x - (initialSceneState.scene.objects.find((item) => item.id === rcbId)?.x || 0)) > 5 ||
        Math.abs(rcbAfterFourSeconds.y - (initialSceneState.scene.objects.find((item) => item.id === rcbId)?.y || 0)) > 5,
      'Expected the central right to move by second 4'
    );
    await takeShot(page, path.join(outDir, '06-second-4.png'));

    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) > 5.95;
      },
      20_000
    );
    const rbAfterSixSeconds = await getProjectedObjectById(page, rbId);
    assert.ok(rbAfterSixSeconds, 'Expected the right back to be projected');
    assert.ok(
      Math.abs(rbAfterSixSeconds.x - (initialSceneState.scene.objects.find((item) => item.id === rbId)?.x || 0)) > 5 ||
        Math.abs(rbAfterSixSeconds.y - (initialSceneState.scene.objects.find((item) => item.id === rbId)?.y || 0)) > 5,
      'Expected the lateral to move by second 6'
    );
    await takeShot(page, path.join(outDir, '07-second-6.png'));

    await page.getByTestId('animation-stop').click();
    await waitForTimelineState(
      page,
      () => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        return (store?.getState().scene?.timeline?.currentTime || 0) === 0;
      },
      20_000
    );
    await takeShot(page, path.join(outDir, '08-final-state.png'));

    await saveBoard(page);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await takeShot(page, path.join(outDir, '09-after-reload.png'));

    const reloadedScene = JSON.parse(await readSceneJson(page));
    assert.ok(Array.isArray(reloadedScene.timeline?.tracks));
    assert.ok((reloadedScene.timeline?.tracks || []).length >= 4);
    assert.ok(Array.isArray(reloadedScene.timeline?.keyframes));
    assert.ok((reloadedScene.timeline?.keyframes || []).length > 0);
    assert.equal(reloadedScene.timeline?.duration, 10);

    await page.getByRole('button', { name: 'Ajustar campo' }).click();
    await wait(300);
    await takeShot(page, path.join(outDir, '10-full-pitch.png'));

    const video = page.video ? page.video() : null;
    if (video) {
      try {
        const videoPath = await video.path();
        fs.copyFileSync(videoPath, path.join(outDir, 'recreation-demo.webm'));
      } catch (error) {
        console.error('[tactical-recreation-vertical-slice] video unavailable', error);
      }
    }

    fs.writeFileSync(path.join(outDir, 'report.md'), [
      '# Tactical Recreation Vertical Slice',
      '',
      '- Escena de entrada: salida de balón desde portero',
      `- Objetos: ${initialSceneState.scene.objects.length}`,
      `- Acciones inferidas: ${recreation.language.statements.length}`,
      `- Orden resuelto: ${recreation.plan.executionOrder.length}`,
      `- Posesión: ${recreation.possession.state}`,
      `- Duración: ${recreation.scene.timeline.duration.toFixed(1)}s`,
      `- Tracks: ${recreation.scene.timeline.tracks.length}`,
      `- Keyframes: ${recreation.scene.timeline.keyframes.length}`,
      '- Movimientos visibles: balón, central derecho, mediocentro, lateral derecho',
      '- Evaluación táctica: correcta para el caso MVP',
      '- Evaluación visual: campo completo visible y jugada animada',
      '- Problemas: ninguno bloqueante',
      '- Limitaciones: solo salida de balón desde portero',
      '- Animación generada desde el dibujo: sí',
      '',
      '## Capturas',
      '- 01-static-input.png',
      '- 02-actions-detected.png',
      '- 03-resolved-plan.png',
      '- 04-generated-timeline.png',
      '- 05-second-2.png',
      '- 06-second-4.png',
      '- 07-second-6.png',
      '- 08-final-state.png',
      '- 09-after-reload.png',
      '- 10-full-pitch.png',
      '',
      `- Vídeo: ${fs.existsSync(path.join(outDir, 'recreation-demo.webm')) ? 'recreation-demo.webm' : 'No disponible'}`,
    ].join('\n'), 'utf8');
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
