/* eslint-disable no-console */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const {
  DEMO_RECREATION_PARTICIPANTS,
  DEMO_RECREATION_STATIC_ASSETS,
  canvasBox,
  clickCanvasAtScene,
  clickControl,
  configureSelectedPlayer,
  getFreePort,
  getNewSceneObjectId,
  getSceneState,
  moveObjectToScenePoint,
  openEditor,
  readSceneJson,
  saveBoard,
  selectAsset,
  selectSceneObjectById,
  selectTool,
  seedTacticalEditorTask,
  setTimelineDuration,
  setTimelineTime,
  spawnLogged,
  takeShot,
  wait,
  waitForServer,
  waitForStoreKeyframes,
} = require('./e2e/helpers/tacticalEditorHelpers');

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-editor-demo-recreation-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath.replace(/^\/+/, '')}`;
  const port = Number(process.env.E2E_PORT || (await getFreePort()));
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'editor-demo-recreation';
  const password = process.env.E2E_PASSWORD || 'editor-demo-recreation';
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-editor-phase-2c-animation', 'demo-recreation');
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
    teamSlug: 'tactical-editor-demo-recreation',
    teamName: 'Tactical Editor Demo Recreation',
    workspaceSlug: 'tactical-editor-demo-recreation',
    workspaceName: 'Tactical Editor Demo Recreation',
    microcycleTitle: 'Micro tactical editor demo recreation',
    sessionDate: '2026-07-16',
    focus: 'Salida de balón',
    taskTitle: 'Demo animada de salida de balón',
    taskDurationMinutes: 18,
    source: 'demo-recreation',
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
    recordVideo: { dir: outDir, size: { width: 1600, height: 1100 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);

  const report = [];

  try {
    await openEditor(page, baseUrl, taskId, username, password);
    await page.getByTestId('viewport-board2d').click();
    await page.getByRole('button', { name: 'Ajustar campo' }).click();
    await page.waitForTimeout(750);
    const box = await canvasBox(page);
    assert.ok(box, 'Missing canvas box');

    const snapToggle = page.getByRole('button', { name: 'Snap' });
    if ((await snapToggle.count()) && (await snapToggle.evaluate((button) => button.classList.contains('is-active')))) {
      await snapToggle.click().catch(() => {});
    }

    for (const participant of DEMO_RECREATION_PARTICIPANTS) {
      await selectAsset(page, participant.asset);
      const beforeIds = (await getSceneState(page)).scene?.objects.map((object) => object.id) || [];
      await clickCanvasAtScene(page, box, participant.frames[0].center);
      await page.waitForFunction(
        (ids) => {
          const store = window.__TACTICAL_EDITOR_STORE__;
          const objects = store?.getState().scene?.objects || [];
          return objects.some((object) => !ids.includes(object.id));
        },
        beforeIds
      );
      const insertedId = await getNewSceneObjectId(page, beforeIds);
      assert(insertedId, `Expected ${participant.key} to be inserted`);
      participant.objectId = insertedId;

      await selectTool(page, 'Seleccionar');
      await selectSceneObjectById(page, insertedId);
      const debugSelection = await page.evaluate((id) => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        const button = document.querySelector('[data-testid="animation-add-keyframe"]');
        return {
          selectedIds: state?.selectedIds || [],
          selectedObjectType: state?.scene?.objects.find((object) => object.id === id)?.type || null,
          buttonDisabled: Boolean(button?.hasAttribute('disabled')),
        };
      }, insertedId);
      assert.equal(debugSelection.buttonDisabled, false, 'animation-add-keyframe should be enabled');
      assert.equal(debugSelection.selectedIds.includes(insertedId), true);

      await clickControl(page, 'animation-add-keyframe');
      await configureSelectedPlayer(page, participant);
    }

    for (const item of DEMO_RECREATION_STATIC_ASSETS) {
      await selectAsset(page, item.asset);
      await clickCanvasAtScene(page, box, item.center);
    }

    await takeShot(page, path.join(outDir, '01-initial-state.png'));
    await setTimelineDuration(page, 10);
    await wait(200);

    for (const time of [3, 6, 10]) {
      await setTimelineTime(page, time);
      await wait(250);
      for (const participant of DEMO_RECREATION_PARTICIPANTS) {
        const objectId = participant.objectId;
        const nextFrame = participant.frames.find((frame) => frame.time === time);
        if (!objectId || !nextFrame) {
          continue;
        }
        await moveObjectToScenePoint(page, objectId, nextFrame.center);
        await clickControl(page, 'animation-add-keyframe');
      }
      await waitForStoreKeyframes(page, 1);
      if (time === 3) {
        await takeShot(page, path.join(outDir, '02-second-3.png'));
      } else if (time === 6) {
        await takeShot(page, path.join(outDir, '03-second-6.png'));
      } else if (time === 10) {
        await takeShot(page, path.join(outDir, '04-final-state.png'));
      }
    }

    await takeShot(page, path.join(outDir, '05-timeline-complete.png'));

    await clickControl(page, 'animation-go-start');
    await page.waitForFunction(
      () => (window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0) < 0.05
    );
    const beforePlay = await page.locator('.te-konva-stage').screenshot();
    await clickControl(page, 'animation-play');
    await page.waitForTimeout(1800);
    const duringPlay = await page.locator('.te-konva-stage').screenshot();
    assert.notDeepEqual(duringPlay, beforePlay);
    await takeShot(page, path.join(outDir, '06-during-playback.png'));
    await clickControl(page, 'animation-pause');
    await clickControl(page, 'animation-stop');
    await takeShot(page, path.join(outDir, '07-stopped.png'));

    await saveBoard(page);
    const savedScene = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'recreation-scene.json'), JSON.stringify(savedScene, null, 2), 'utf8');
    fs.writeFileSync(path.join(outDir, 'recreation-animation.json'), JSON.stringify(savedScene.timeline, null, 2), 'utf8');

    const trackCount = Array.isArray(savedScene.timeline?.tracks) ? savedScene.timeline.tracks.length : 0;
    const keyframeCount = Array.isArray(savedScene.timeline?.keyframes) ? savedScene.timeline.keyframes.length : 0;
    report.push(
      ['Descripción', 'Salida de balón desde portero'],
      ['Duración', '10s'],
      ['Objetos', String(savedScene.objects.length)],
      ['Tracks', String(trackCount)],
      ['Keyframes', String(keyframeCount)],
      ['Balón', 'Portero -> central derecho -> mediocentro -> lateral derecho -> zona objetivo'],
      ['Reproducción', 'OK'],
      ['Persistencia', 'OK'],
      ['Capturas', 'Generadas'],
      ['Video', 'Intentado si el navegador lo soporta']
    );

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await takeShot(page, path.join(outDir, '08-after-reload.png'));

    const reloadedScene = JSON.parse(await readSceneJson(page));
    assert.equal(Array.isArray(reloadedScene.timeline?.tracks), true);
    assert.equal((reloadedScene.timeline?.tracks || []).length >= 1, true);
    assert.equal(Array.isArray(reloadedScene.timeline?.keyframes), true);
    assert.equal((reloadedScene.timeline?.keyframes || []).length >= 1, true);

    await clickControl(page, 'animation-go-start');
    await clickControl(page, 'animation-play');
    await page.waitForTimeout(1200);
    await takeShot(page, path.join(outDir, '09-playing-after-reload.png'));
    await clickControl(page, 'animation-pause');

    const animationVideo = page.video ? page.video() : null;
    await page.close();
    if (animationVideo) {
      try {
        const videoPath = await animationVideo.path();
        fs.copyFileSync(videoPath, path.join(outDir, 'recreation-demo.webm'));
      } catch (error) {
        report.push(['Video', `No disponible: ${error instanceof Error ? error.message : String(error)}`]);
      }
    }

    fs.writeFileSync(
      path.join(outDir, 'report.md'),
      `# Demo recreación táctica animada\n\n` +
        report.map((item) => `- ${item[0]}: ${item[1]}`).join('\n') +
        `\n\n` +
        `## Capturas\n` +
        `- 01-initial-state.png\n` +
        `- 02-second-3.png\n` +
        `- 03-second-6.png\n` +
        `- 04-final-state.png\n` +
        `- 05-timeline-complete.png\n` +
        `- 06-during-playback.png\n` +
        `- 07-stopped.png\n` +
        `- 08-after-reload.png\n` +
        `- 09-playing-after-reload.png\n`,
      'utf8'
    );
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    serverProc.kill('SIGTERM');
    await wait(1000);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
