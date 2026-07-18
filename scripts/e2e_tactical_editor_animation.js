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
    slug="tactical-editor-animation",
    defaults={"name": "Tactical Editor Animation", "is_primary": True},
)
workspace, _ = Workspace.objects.get_or_create(
    slug="tactical-editor-animation",
    defaults={
        "name": "Tactical Editor Animation",
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
    title="Micro tactical editor animation",
    defaults={"week_start": date(2026, 7, 13), "week_end": date(2026, 7, 19)},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date(2026, 7, 17),
    defaults={"focus": "Reproducción", "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title="Tarea base animación",
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
                "timeline": {"duration": 0, "currentTime": 0, "keyframes": [], "tracks": [], "sequences": [], "currentSequenceId": None},
                "metadata": {
                    "title": task.title,
                    "createdAt": "",
                    "updatedAt": "",
                    "source": "animation-phase-2c",
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

async function dragCanvas(page, box, from, to) {
  await page.mouse.move(box.x + box.width * from[0], box.y + box.height * from[1]);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * to[0], box.y + box.height * to[1], {
    steps: 16,
  });
  await page.mouse.up();
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
  assert.equal(page.url().includes('editor2d=1'), true, `Expected editor2d=1 in URL, got ${page.url()}`);
  await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
  const viewport2d = page.getByTestId('viewport-board2d');
  await viewport2d.waitFor({ state: 'visible', timeout: 30_000 });
  await viewport2d.click();
  assert.equal(
    await viewport2d.evaluate((element) => element.classList.contains('is-active')),
    true,
    'Viewport 2D should become active'
  );
  assert.equal(
    await page.evaluate(() => window.__TACTICAL_EDITOR_STORE__?.getState().featureEnabled ?? false),
    true,
    'The tactical editor 2D feature must be enabled'
  );
  assert.equal(
    await page.evaluate(() => window.__TACTICAL_EDITOR_STORE__?.getState().activeViewport ?? null),
    'board2d',
    'The tactical editor should be on the 2D viewport'
  );
  await page.waitForFunction(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return Boolean(state?.document && state?.scene);
  });
  await page.locator('.te-konva-stage').waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByTestId('editor-tool-select').waitFor({ state: 'visible', timeout: 30_000 });
}

async function selectAsset(page, label) {
  const exactCard = page.locator(`.te-asset-card[title="${label}"]`).first();
  try {
    await exactCard.waitFor({ state: 'visible', timeout: 10_000 });
    await exactCard.scrollIntoViewIfNeeded();
    await exactCard.click();
    return;
  } catch (error) {
    // Fall back to text-based lookups below.
  }

  const roleCard = page.getByRole('button', { name: new RegExp(label) }).first();
  try {
    await roleCard.waitFor({ state: 'visible', timeout: 10_000 });
    await roleCard.scrollIntoViewIfNeeded();
    await roleCard.click();
    return;
  } catch (error) {
    // Fallbacks below.
  }

  const search = page.locator('.te-library-search input[type="search"]');
  const card = page.locator('.te-asset-card').filter({ hasText: label }).first();
  if ((await search.count()) > 0) {
    try {
      await search.fill(label);
      await card.waitFor({ state: 'visible', timeout: 10_000 });
      await card.scrollIntoViewIfNeeded();
      await card.click();
      await search.fill('');
      return;
    } catch (error) {
      // Fallback to the raw card click below.
    }
  }
  await card.waitFor({ state: 'attached', timeout: 10_000 });
  await card.scrollIntoViewIfNeeded();
  await card.click();
}

async function assertControlReady(page, testId) {
  const locator = page.getByTestId(testId);
  const count = await locator.count();
  assert.equal(count, 1, `Expected a single control for ${testId}, found ${count}`);
  await locator.waitFor({ state: 'visible', timeout: 15_000 });
  assert.equal(await locator.isEnabled(), true, `Control ${testId} should be enabled`);
  const box = await locator.boundingBox();
  assert(box, `Control ${testId} should expose a bounding box`);
  assert(box.width > 0, `Control ${testId} should have width`);
  assert(box.height > 0, `Control ${testId} should have height`);
  const viewport = page.viewportSize();
  if (viewport) {
    assert(box.x >= 0 && box.y >= 0, `Control ${testId} should remain within the viewport`);
    assert(box.x + box.width <= viewport.width + 1, `Control ${testId} should fit horizontally`);
    assert(box.y + box.height <= viewport.height + 1, `Control ${testId} should fit vertically`);
  }
  const covered = await page.evaluate(
    ({ testId: currentTestId, x, y }) => {
      const element = document.elementFromPoint(x, y);
      return Boolean(element?.closest(`[data-testid="${currentTestId}"]`));
    },
    { testId, x: box.x + box.width / 2, y: box.y + box.height / 2 }
  );
  assert.equal(covered, true, `Control ${testId} should not be covered`);
  return locator;
}

async function clickControl(page, testId) {
  const locator = await assertControlReady(page, testId);
  await locator.click();
}

async function expectSelectionCount(page, count) {
  const selectedCount = await page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    return store ? store.getState().selectedIds.length : null;
  });
  if (selectedCount !== null) {
    assert.equal(selectedCount, count, `Expected ${count} selected ids, got ${selectedCount}`);
    return;
  }
  const locator = page.getByTestId('canvas-selection-count');
  await locator.waitFor({ state: 'attached', timeout: 15_000 });
  const text = (await locator.textContent()) || '';
  assert.equal(
    text.includes(count ? `${count} activos` : 'Sin selección'),
    true,
    `Expected selection count to reflect ${count}, got ${text}`
  );
}

async function readSceneJson(page) {
  await page.getByRole('button', { name: /Copiar JSON/i }).click();
  return page.evaluate(() => navigator.clipboard.readText());
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-editor-animation-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath}`;
  const port = Number(process.env.E2E_PORT || 8133);
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'editor-animation';
  const password = process.env.E2E_PASSWORD || 'editor-animation';
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-editor-phase-2c-animation');
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

  try {
    await openEditor(page, baseUrl, taskId, username, password);
    await page.screenshot({ path: path.join(outDir, '01-editor-open.png'), fullPage: true });

    const box = await canvasBox(page);
    await selectAsset(page, 'player.home.front');
    await clickCanvas(page, box, 0.38, 0.42);
    await expectSelectionCount(page, 1);
    await clickControl(page, 'animation-add-keyframe');
    await page.screenshot({ path: path.join(outDir, '02-first-keyframe.png'), fullPage: true });

    const movedPosition = await page.evaluate(() => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      const selectedId = state?.selectedIds?.[0];
      const object = state?.scene?.objects.find((item) => item.id === selectedId);
      return {
        x: Math.round((object?.x || 0) + 96),
        y: Math.round((object?.y || 0) + 64),
      };
    });
    await page.locator('.te-inspector').getByRole('spinbutton', { name: /^X$/ }).fill(String(movedPosition.x));
    await page.locator('.te-inspector').getByRole('spinbutton', { name: /^Y$/ }).fill(String(movedPosition.y));
    await page.waitForFunction(
      (expected) => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        const selectedId = state?.selectedIds?.[0];
        const object = state?.scene?.objects.find((item) => item.id === selectedId);
        return (
          Boolean(object) &&
          Math.round(object.x) === expected.x &&
          Math.round(object.y) === expected.y
        );
      },
      movedPosition
    );
    await page.locator('label:has-text("Tiempo") input[type="range"]').evaluate((element, value) => {
      const input = element;
      input.value = String(value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }, 3);
    await clickControl(page, 'animation-add-keyframe');
    await page.screenshot({ path: path.join(outDir, '03-second-keyframe.png'), fullPage: true });

    await clickControl(page, 'animation-go-start');
    await page.waitForFunction(
      () => (window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0) < 0.05
    );
    const timelineBeforePlay = await page.evaluate(
      () => window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0
    );
    const playingBefore = await page.locator('.te-konva-stage').screenshot();
    await clickControl(page, 'animation-play');
    await page.waitForFunction(
      (expected) => {
        const current = window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime;
        return typeof current === 'number' && Math.abs(current - expected) > 0.05;
      },
      timelineBeforePlay
    );
    const timelineAfterPlay = await page.evaluate(
      () => window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0
    );
    assert.notEqual(timelineAfterPlay, timelineBeforePlay);
    const playingAfter = await page.locator('.te-konva-stage').screenshot();
    assert.notDeepEqual(playingAfter, playingBefore);
    await page.screenshot({ path: path.join(outDir, '04-playing.png'), fullPage: true });

    await clickControl(page, 'animation-pause');
    assert.equal(await page.getByTestId('animation-pause').isDisabled(), true);
    await page.screenshot({ path: path.join(outDir, '05-paused.png'), fullPage: true });

    await clickControl(page, 'animation-stop');
    await page.screenshot({ path: path.join(outDir, '06-stopped.png'), fullPage: true });

    const sceneJson = await readSceneJson(page);
    const parsedScene = JSON.parse(sceneJson);
    assert.equal(parsedScene.timeline.keyframes.length >= 2, true);
    assert.equal(Array.isArray(parsedScene.timeline.tracks), true);
    assert.equal(parsedScene.timeline.tracks.length >= 1, true);

    await page.getByRole('button', { name: /Guardar pizarra|Pizarra guardada|Guardando/i }).click().catch(() => {});
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await page.screenshot({ path: path.join(outDir, '07-after-reload.png'), fullPage: true });

    const reloadedJson = await readSceneJson(page);
    const parsedReloaded = JSON.parse(reloadedJson);
    assert.equal(parsedReloaded.timeline.keyframes.length >= 2, true);
    assert.equal(Array.isArray(parsedReloaded.timeline.tracks), true);
    assert.equal(parsedReloaded.timeline.tracks.length >= 1, true);

    await clickControl(page, 'animation-go-start');
    await page.waitForFunction(
      () => (window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0) < 0.05
    );
    const reloadedTimelineBeforePlay = await page.evaluate(
      () => window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0
    );
    const reloadedPlayingBefore = await page.locator('.te-konva-stage').screenshot();
    await clickControl(page, 'animation-play');
    await page.waitForFunction(
      (expected) => {
        const current = window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime;
        return typeof current === 'number' && Math.abs(current - expected) > 0.05;
      },
      reloadedTimelineBeforePlay
    );
    const reloadedTimelineAfterPlay = await page.evaluate(
      () => window.__TACTICAL_EDITOR_STORE__?.getState().scene?.timeline?.currentTime ?? 0
    );
    assert.notEqual(reloadedTimelineAfterPlay, reloadedTimelineBeforePlay);
    await clickControl(page, 'animation-pause');
    const reloadedPlayingAfter = await page.locator('.te-konva-stage').screenshot();
    assert.notDeepEqual(reloadedPlayingAfter, reloadedPlayingBefore);
    await page.screenshot({ path: path.join(outDir, '08-playing-after-reload.png'), fullPage: true });
  } finally {
    await page.close().catch(() => {});
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    serverProc.kill('SIGTERM');
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
