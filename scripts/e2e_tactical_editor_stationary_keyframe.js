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
  clickControl,
  getFreePort,
  openEditor,
  readSceneState,
  saveBoard,
  seedTacticalEditorTask,
  selectAsset,
  selectSceneObjectById,
  setTimelineTime,
  spawnLogged,
  wait,
  waitForServer,
} = require('./e2e/helpers/tacticalEditorHelpers');

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-editor-stationary-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath}`;
  const port = Number(process.env.E2E_PORT || (await getFreePort()));
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'editor-stationary';
  const password = process.env.E2E_PASSWORD || 'editor-stationary';

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
    teamSlug: 'tactical-editor-stationary-keyframe',
    teamName: 'Tactical Editor Stationary Keyframe',
    workspaceSlug: 'tactical-editor-stationary-keyframe',
    workspaceName: 'Tactical Editor Stationary Keyframe',
    microcycleTitle: 'Micro tactical editor stationary keyframe',
    sessionDate: '2026-07-18',
    focus: 'Selección estacionaria',
    taskTitle: 'Tarea mínima keyframe estacionario',
    taskDurationMinutes: 18,
    source: 'stationary-keyframe',
  });

  const server = spawn('python3', ['manage.py', 'runserver', `127.0.0.1:${port}`, '--noreload'], {
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

  try {
    if (!(await waitForServer(baseUrl))) {
      throw new Error('Server did not start');
    }

    const browser = await chromium.launch({
      headless: true,
      args: ['--disable-dev-shm-usage', '--no-sandbox'],
    });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();

    try {
      await openEditor(page, baseUrl, taskId, username, password);
      const box = await canvasBox(page);
      assert.ok(box, 'Missing canvas box');

      await selectAsset(page, 'Portero local');
      await clickCanvasAtScene(page, box, { x: box.width * 0.22, y: box.height * 0.44 });

      const insertedObjectButton = page.locator('[data-testid^="scene-object-"]').first();
      await insertedObjectButton.waitFor({ state: 'visible', timeout: 15_000 });
      const insertedId = await insertedObjectButton.evaluate((button) =>
        button.getAttribute('data-testid')?.replace('scene-object-', '') || null
      );
      assert(insertedId, 'Expected a goalkeeper to be inserted');

      const objectButton = page.getByTestId(`scene-object-${insertedId}`);
      assert.equal(await objectButton.count(), 1);
      assert.equal(await objectButton.isVisible(), true);
      assert.equal(await objectButton.isEnabled(), true);
      assert.ok(await objectButton.boundingBox(), 'Expected object button bounding box');

      await selectSceneObjectById(page, insertedId);
      assert.equal(await objectButton.getAttribute('aria-pressed'), 'true');

      const keyframeButton = page.getByTestId('animation-add-keyframe');
      assert.equal(await keyframeButton.isVisible(), true);
      assert.equal(await keyframeButton.isEnabled(), true);

      await clickControl(page, 'animation-add-keyframe');
      let snapshot = await readSceneState(page);
      let track = snapshot.scene.timeline.tracks.find((item) => item.objectId === insertedId);
      assert.equal(track?.keyframes?.length || 0, 1);

      await setTimelineTime(page, 3);
      await selectSceneObjectById(page, insertedId);
      assert.equal(await objectButton.getAttribute('aria-pressed'), 'true');
      assert.equal(await keyframeButton.isEnabled(), true);

      await clickControl(page, 'animation-add-keyframe');
      snapshot = await readSceneState(page);
      track = snapshot.scene.timeline.tracks.find((item) => item.objectId === insertedId);
      assert.equal(track?.keyframes?.length || 0, 2);

      await clickControl(page, 'animation-play');
      await wait(800);
      await clickControl(page, 'animation-pause');
      await clickControl(page, 'animation-stop');

      await saveBoard(page);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
      await page.locator('text=Motor 2D Konva').waitFor({ state: 'visible', timeout: 30_000 });

      const reloadedObjectButton = page.getByTestId(`scene-object-${insertedId}`);
      await selectSceneObjectById(page, insertedId);
      assert.equal(await reloadedObjectButton.getAttribute('aria-pressed'), 'true');

      const reloadedSnapshot = await readSceneState(page);
      const reloadedTrack = reloadedSnapshot.scene.timeline.tracks.find((item) => item.objectId === insertedId);
      assert.equal(reloadedTrack?.keyframes?.length || 0, 2);
    } finally {
      await browser.close();
    }
  } finally {
    server.kill('SIGTERM');
    await new Promise((resolve) => server.on('exit', resolve));
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
