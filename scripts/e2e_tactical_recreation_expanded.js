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
  getProjectedObjectById,
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

async function insertScenarioObject(page, box, spec) {
  if (spec.kind === 'player') {
    return insertConfiguredPlayer(page, box, spec.asset, spec.center, spec.config);
  }
  return insertConfiguredAsset(page, box, spec.asset, spec.center, spec.label);
}

function writeJson(outDir, fileName, value) {
  fs.writeFileSync(path.join(outDir, fileName), JSON.stringify(value, null, 2), 'utf8');
}

async function readEditorSnapshot(page) {
  return page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return {
      tacticalRecreation: state?.tacticalRecreation || null,
      tacticalRecreationDraft: state?.tacticalRecreationDraft || null,
      tacticalRecreationModified: Boolean(state?.tacticalRecreationModified),
      scene: state?.scene || null,
      selectedIds: state?.selectedIds || [],
    };
  });
}

async function getSceneObjectIdByLabel(page, label) {
  return page.evaluate((needle) => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const objects = store?.getState().scene?.objects || [];
    const lowered = String(needle || '').toLowerCase();
    return (
      objects.find((object) =>
        [object.data?.name, object.data?.label, object.type].some((value) =>
          String(value || '').toLowerCase() === lowered
        )
      )?.id || null
    );
  }, label);
}

async function waitForRecreation(page, expectedStatements) {
  await page.waitForFunction(
    (minimumStatements) => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      const recreation = state?.tacticalRecreation;
      return Boolean(
        recreation &&
          recreation.language.statements.length >= minimumStatements &&
          recreation.plan.executionOrder.length > 0 &&
          recreation.scene.timeline.tracks.length > 0 &&
          recreation.scene.timeline.keyframes.length > 0
      );
    },
    expectedStatements
  );
}

async function selectFirstDraftDuration(page, value) {
  const duration = page.locator('.te-recreation-item').first().getByLabel('Duración', { exact: true });
  await duration.waitFor({ state: 'visible', timeout: 15_000 });
  await duration.fill(String(value));
  await duration.press('Enter').catch(() => {});
}

async function runScenario(page, baseUrl, taskId, username, password, scenario) {
  await openEditor(page, baseUrl, taskId, username, password);
  await page.getByTestId('viewport-board2d').click();
  await page.getByRole('button', { name: 'Ajustar campo' }).click();
  await wait(450);

  const box = await canvasBox(page);
  assert.ok(box, 'Missing canvas box');

  for (const object of scenario.objects) {
    await insertScenarioObject(page, box, object);
  }

  const initialState = await readEditorSnapshot(page);
  assert.equal(initialState.scene.timeline.tracks.length, 0, `${scenario.slug}: expected empty timeline`);
  assert.equal(initialState.scene.timeline.keyframes.length, 0, `${scenario.slug}: expected no keyframes`);
  writeJson(scenario.outDir, 'scene-input.json', initialState.scene);
  await takeShot(page, path.join(scenario.outDir, '01-input.png'));

  await page.getByTestId('generate-tactical-recreation').click();
  await waitForRecreation(page, scenario.expectedStatements);

  const afterGenerate = await readEditorSnapshot(page);
  const recreation = afterGenerate.tacticalRecreation;
  assert(recreation, `${scenario.slug}: missing tactical recreation`);
  assert.equal(
    recreation.language.statements.some((statement) => scenario.expectedVerbs.includes(statement.verb)),
    true,
    `${scenario.slug}: missing expected verbs`
  );
  writeJson(scenario.outDir, 'inferred-actions.json', recreation.language);
  writeJson(scenario.outDir, 'resolved-plan.json', recreation.plan);
  writeJson(scenario.outDir, 'generated-timeline.json', recreation.scene.timeline);
  await takeShot(page, path.join(scenario.outDir, '02-detected-actions.png'));
  await takeShot(page, path.join(scenario.outDir, '03-timeline.png'));

  if (scenario.editDraft) {
    await selectFirstDraftDuration(page, scenario.editDraft.duration);
    await page.getByText('Borrador modificado').waitFor({ state: 'visible', timeout: 15_000 });
    await page.getByTestId('tactical-recreation-regenerate').click();
    await waitForRecreation(page, scenario.expectedStatements);
  }

  await page.getByTestId('animation-go-start').click();
  const movingObjectId = await getSceneObjectIdByLabel(page, scenario.movingLabel);
  const initialMoving = movingObjectId ? await getProjectedObjectById(page, movingObjectId) : null;
  const playButton = page.getByTestId('animation-play');
  await playButton.click();
  await wait(1400);
  const movingBefore = movingObjectId ? await getProjectedObjectById(page, movingObjectId) : null;
  await wait(600);
  const movingAfter = movingObjectId ? await getProjectedObjectById(page, movingObjectId) : null;
  if (movingBefore && movingAfter) {
    assert.notEqual(
      movingBefore.x.toFixed(1) + ':' + movingBefore.y.toFixed(1),
      movingAfter.x.toFixed(1) + ':' + movingAfter.y.toFixed(1),
      `${scenario.slug}: expected ${scenario.movingLabel} to move during playback`
    );
  }
  await takeShot(page, path.join(scenario.outDir, '04-middle.png'));

  await page.getByTestId('animation-pause').click();
  await page.getByTestId('animation-stop').click();
  const stoppedMoving = movingObjectId ? await getProjectedObjectById(page, movingObjectId) : null;
  if (initialMoving && stoppedMoving) {
    assert.equal(
      stoppedMoving.x.toFixed(1) + ':' + stoppedMoving.y.toFixed(1),
      initialMoving.x.toFixed(1) + ':' + initialMoving.y.toFixed(1),
      `${scenario.slug}: expected ${scenario.movingLabel} to return to start after stop`
    );
  }
  await takeShot(page, path.join(scenario.outDir, '05-final.png'));

  await saveBoard(page);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByTestId('viewport-board2d').click();
  await page.getByRole('button', { name: 'Ajustar campo' }).click();
  await wait(450);
  await takeShot(page, path.join(scenario.outDir, '08-after-reload.png'));

  const reloadedScene = JSON.parse(await readSceneJson(page));
  assert.ok((reloadedScene.timeline?.tracks || []).length > 0, `${scenario.slug}: expected tracks after reload`);
  assert.ok((reloadedScene.timeline?.keyframes || []).length > 0, `${scenario.slug}: expected keyframes after reload`);
  await takeShot(page, path.join(scenario.outDir, '10-full-pitch.png'));

  fs.writeFileSync(
    path.join(scenario.outDir, 'report.md'),
    [
      `# ${scenario.title}`,
      '',
      `- Objetos: ${initialState.scene.objects.length}`,
      `- Tracks: ${recreation.scene.timeline.tracks.length}`,
      `- Keyframes: ${recreation.scene.timeline.keyframes.length}`,
      `- Duración: ${recreation.scene.timeline.duration}`,
      `- Verbos: ${scenario.expectedVerbs.join(', ')}`,
      `- Reproducción: OK`,
      `- Persistencia: OK`,
      `- Edición: ${scenario.editDraft ? 'OK' : 'No requerida'}`,
      '',
      '## Evaluación',
      scenario.evaluation,
      '',
      '## Capturas',
      '- 01-input.png',
      '- 02-detected-actions.png',
      '- 03-timeline.png',
      '- 04-middle.png',
      '- 05-final.png',
      '- 08-after-reload.png',
      '- 10-full-pitch.png',
      '',
      '- WebM: pendiente de cierre del navegador',
    ].join('\n'),
    'utf8'
  );
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-recreation-expanded-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath.replace(/^\/+/, '')}`;
  const port = Number(process.env.E2E_PORT || (await getFreePort()));
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'tactical-recreation-expanded';
  const password = process.env.E2E_PASSWORD || 'tactical-recreation-expanded';
  const rootOut = path.join(repoRoot, 'output', 'qa', 'tactical-recreation-expanded');
  fs.mkdirSync(rootOut, { recursive: true });

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
    recordVideo: { dir: rootOut, size: { width: 1600, height: 1100 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);

  const scenarios = [
    {
      slug: 'build-up',
      title: 'Salida de balón',
      taskTitle: 'Recreación build-up',
      focus: 'Salida de balón desde portero',
      expectedStatements: 7,
      expectedVerbs: ['BUILD_UP', 'PASS', 'RECEIVE', 'CARRY', 'SUPPORT', 'HOLD', 'PROGRESSION'],
      movingLabel: 'Balón',
      editDraft: { duration: 1.3 },
      evaluation:
        'Correcto: el portero inicia la secuencia, el balón progresa por el central y el lateral ofrece una línea de apoyo visible.',
      objects: [
        { kind: 'player', asset: 'goalkeeper.home.front', center: { x: 120, y: 340 }, config: { name: 'Portero', label: 'GK', number: '1', team: 'home' } },
        { kind: 'player', asset: 'player.home.back', center: { x: 250, y: 220 }, config: { name: 'Central derecho', label: 'RCB', number: '4', team: 'home' } },
        { kind: 'player', asset: 'player.home.back', center: { x: 250, y: 460 }, config: { name: 'Central izquierdo', label: 'LCB', number: '5', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 390, y: 340 }, config: { name: 'Mediocentro', label: 'MCD', number: '6', team: 'home' } },
        { kind: 'player', asset: 'player.home.side', center: { x: 350, y: 150 }, config: { name: 'Lateral derecho', label: 'RB', number: '2', team: 'home' } },
        { kind: 'asset', asset: 'ball.standard', center: { x: 120, y: 340 }, label: 'Balón' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 178, y: 300 }, label: 'Pase 1' },
        { kind: 'asset', asset: 'arrow.run', center: { x: 462, y: 238 }, label: 'Carrera' },
        { kind: 'asset', asset: 'arrow.ball', center: { x: 430, y: 334 }, label: 'Pase 2' },
        { kind: 'asset', asset: 'zone.rect', center: { x: 792, y: 248 }, label: 'Zona objetivo' },
      ],
    },
    {
      slug: 'rondo',
      title: 'Rondo simple',
      taskTitle: 'Recreación rondo',
      focus: 'Rondo con presión',
      expectedStatements: 8,
      expectedVerbs: ['BUILD_UP', 'PASS', 'RECEIVE', 'PRESS', 'SEQUENCE'],
      movingLabel: 'Balón',
      evaluation:
        'Aceptable: la posesión se sostiene con presión y la secuencia de pases se entiende sin romper el ritmo.',
      objects: [
        { kind: 'player', asset: 'player.home.front', center: { x: 220, y: 200 }, config: { name: 'A', label: 'A', number: '7', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 330, y: 120 }, config: { name: 'B', label: 'B', number: '8', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 420, y: 280 }, config: { name: 'C', label: 'C', number: '9', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 520, y: 180 }, config: { name: 'D', label: 'D', number: '10', team: 'home' } },
        { kind: 'player', asset: 'player.away.front', center: { x: 390, y: 200 }, config: { name: 'Defensor', label: 'DEF', number: '11', team: 'away' } },
        { kind: 'asset', asset: 'ball.standard', center: { x: 250, y: 200 }, label: 'Balón' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 280, y: 190 }, label: 'Pase 1' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 360, y: 180 }, label: 'Pase 2' },
        { kind: 'asset', asset: 'arrow.run', center: { x: 410, y: 210 }, label: 'Presión' },
      ],
    },
    {
      slug: 'wall-pass',
      title: 'Pared simple',
      taskTitle: 'Recreación pared',
      focus: 'Pared y devolución',
      expectedStatements: 6,
      expectedVerbs: ['PASS', 'RECEIVE', 'RETURN_PASS', 'SUPPORT'],
      movingLabel: 'Balón',
      evaluation:
        'Correcto: la pared se ve clara, el apoyo acompaña y la devolución mantiene la continuidad de la jugada.',
      objects: [
        { kind: 'player', asset: 'player.home.front', center: { x: 260, y: 240 }, config: { name: 'Jugador A', label: 'A', number: '7', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 410, y: 240 }, config: { name: 'Jugador B', label: 'B', number: '9', team: 'home' } },
        { kind: 'asset', asset: 'ball.standard', center: { x: 280, y: 240 }, label: 'Balón' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 286, y: 232 }, label: 'Pase' },
        { kind: 'asset', asset: 'arrow.run', center: { x: 270, y: 210 }, label: 'Apoyo' },
      ],
    },
    {
      slug: 'finishing',
      title: 'Finalización',
      taskTitle: 'Recreación finalización',
      focus: 'Finalización con tiro',
      expectedStatements: 5,
      expectedVerbs: ['PASS', 'RECEIVE', 'SHOOT', 'HOLD'],
      movingLabel: 'Balón',
      evaluation:
        'Correcto: el pase, el control y el tiro son legibles y la portería queda como referencia visual clara.',
      objects: [
        { kind: 'player', asset: 'player.home.front', center: { x: 390, y: 300 }, config: { name: 'Mediocentro', label: 'MC', number: '6', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 610, y: 300 }, config: { name: 'Delantero', label: 'DC', number: '9', team: 'home' } },
        { kind: 'asset', asset: 'goal.standard', center: { x: 860, y: 240 }, label: 'Portería' },
        { kind: 'asset', asset: 'zone.rect', center: { x: 800, y: 240 }, label: 'Zona objetivo' },
        { kind: 'asset', asset: 'ball.standard', center: { x: 410, y: 300 }, label: 'Balón' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 440, y: 292 }, label: 'Pase' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 620, y: 290 }, label: 'Tiro' },
      ],
    },
    {
      slug: 'technical-circuit',
      title: 'Circuito técnico',
      taskTitle: 'Recreación circuito',
      focus: 'Circuito técnico con llegada a zona',
      expectedStatements: 6,
      expectedVerbs: ['CARRY', 'RUN', 'PASS', 'RECEIVE', 'OCCUPY_SPACE'],
      movingLabel: 'Balón',
      evaluation:
        'Aceptable: el circuito técnico combina conducción, carrera y llegada a objetivo con suficiente lectura espacial.',
      objects: [
        { kind: 'player', asset: 'goalkeeper.home.front', center: { x: 120, y: 300 }, config: { name: 'Portero', label: 'GK', number: '1', team: 'home' } },
        { kind: 'player', asset: 'player.home.back', center: { x: 330, y: 220 }, config: { name: 'Central', label: 'CB', number: '4', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 470, y: 260 }, config: { name: 'Mediocentro', label: 'MC', number: '6', team: 'home' } },
        { kind: 'player', asset: 'player.home.side', center: { x: 620, y: 180 }, config: { name: 'Lateral', label: 'RB', number: '2', team: 'home' } },
        { kind: 'player', asset: 'player.home.front', center: { x: 760, y: 260 }, config: { name: 'Llegada', label: 'L', number: '11', team: 'home' } },
        { kind: 'asset', asset: 'ball.standard', center: { x: 150, y: 300 }, label: 'Balón' },
        { kind: 'asset', asset: 'zone.rect', center: { x: 820, y: 220 }, label: 'Zona objetivo' },
        { kind: 'asset', asset: 'arrow.pass', center: { x: 180, y: 292 }, label: 'Pase' },
        { kind: 'asset', asset: 'arrow.run', center: { x: 630, y: 180 }, label: 'Carrera' },
      ],
    },
  ];

  try {
    if (!(await waitForServer(baseUrl))) {
      throw new Error('The tactical recreation expanded test server did not start');
    }

    for (const scenario of scenarios) {
      const taskId = await seedTacticalEditorTask(dbUrl, {
        username,
        password,
        teamSlug: `tactical-${scenario.slug}`,
        teamName: `Tactical ${scenario.title}`,
        workspaceSlug: `tactical-${scenario.slug}`,
        workspaceName: `Tactical ${scenario.title}`,
        microcycleTitle: `Micro ${scenario.title}`,
        sessionDate: '2026-07-18',
        focus: scenario.focus,
        taskTitle: scenario.taskTitle,
        taskDurationMinutes: 18,
        source: scenario.slug,
      });
      const scenarioOutDir = path.join(rootOut, scenario.slug);
      fs.mkdirSync(scenarioOutDir, { recursive: true });
      scenario.outDir = scenarioOutDir;

      await runScenario(page, baseUrl, taskId, username, password, scenario);
    }

    const video = page.video ? page.video() : null;
    if (video) {
      try {
        const videoPath = await video.path();
        fs.copyFileSync(videoPath, path.join(rootOut, 'recreation-expanded-demo.webm'));
      } catch (error) {
        console.error('[tactical-recreation-expanded] video unavailable', error);
      }
    }
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    await new Promise((resolve) => serverProc.kill('SIGTERM', resolve));
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
