/* eslint-disable no-console */

const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');

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

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = require('node:net').createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address && typeof address === 'object') {
        const { port } = address;
        server.close(() => resolve(port));
        return;
      }
      server.close(() => reject(new Error('Unable to resolve a free port')));
    });
  });
}

async function seedTacticalEditorTask(dbUrl, options) {
  const payload = {
    username: options.username,
    password: options.password,
    teamSlug: options.teamSlug,
    teamName: options.teamName,
    workspaceSlug: options.workspaceSlug,
    workspaceName: options.workspaceName,
    microcycleTitle: options.microcycleTitle,
    sessionDate: options.sessionDate,
    focus: options.focus,
    taskTitle: options.taskTitle,
    taskDurationMinutes: options.taskDurationMinutes ?? 18,
    source: options.source,
    canvasWidth: options.canvasWidth ?? 1280,
    canvasHeight: options.canvasHeight ?? 720,
  };

  const shellCode = `
import json
from datetime import date
from football.models import AppUserRole, SessionTask, Team, TrainingMicrocycle, TrainingSession, Workspace, WorkspaceMembership, WorkspaceTeam
from django.contrib.auth import get_user_model

config = json.loads(${JSON.stringify(JSON.stringify(payload))})

User = get_user_model()
user, _ = User.objects.get_or_create(username=config["username"], defaults={"email": f'{config["username"]}@example.com'})
user.email = f'{config["username"]}@example.com'
user.set_password(config["password"])
user.save()
AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})
team, _ = Team.objects.get_or_create(
    slug=config["teamSlug"],
    defaults={"name": config["teamName"], "is_primary": True},
)
workspace, _ = Workspace.objects.get_or_create(
    slug=config["workspaceSlug"],
    defaults={
        "name": config["workspaceName"],
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
    title=config["microcycleTitle"],
    defaults={"week_start": date.fromisoformat(config["sessionDate"]), "week_end": date.fromisoformat(config["sessionDate"])},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date.fromisoformat(config["sessionDate"]),
    defaults={"focus": config["focus"], "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title=config["taskTitle"],
    defaults={"block": SessionTask.BLOCK_MAIN_1, "duration_minutes": config["taskDurationMinutes"]},
)
task.block = SessionTask.BLOCK_MAIN_1
task.duration_minutes = config["taskDurationMinutes"]
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
                "canvas": {"width": config["canvasWidth"], "height": config["canvasHeight"], "padding": 28},
                "viewport": {"zoom": 1, "x": 0, "y": 0},
                "layers": [],
                "objects": [],
                "timeline": {
                    "duration": 0,
                    "currentTime": 0,
                    "keyframes": [],
                    "tracks": [],
                    "sequences": [],
                    "currentSequenceId": None,
                },
                "metadata": {
                    "title": task.title,
                    "createdAt": "",
                    "updatedAt": "",
                    "source": config["source"],
                },
            },
            "canvas_width": config["canvasWidth"],
            "canvas_height": config["canvasHeight"],
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

function sceneToScreen(box, viewport, point) {
  return {
    x: box.x + viewport.x + point.x * viewport.zoom,
    y: box.y + viewport.y + point.y * viewport.zoom,
  };
}

async function getSceneState(page) {
  return page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return {
      viewport: state?.scene?.viewport || { x: 0, y: 0, zoom: 1 },
      scene: state?.scene || null,
      selectedIds: state?.selectedIds || [],
      activeTool: state?.activeTool || null,
    };
  });
}

async function getNewSceneObjectId(page, beforeIds) {
  return page.evaluate((ids) => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const objects = store?.getState().scene?.objects || [];
    const created = objects.find((object) => !ids.includes(object.id));
    return created?.id || null;
  }, beforeIds);
}

async function readSceneState(page) {
  return page.evaluate(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return {
      selectedIds: state?.selectedIds || [],
      scene: state?.scene || null,
    };
  });
}

async function openEditor(page, baseUrl, taskId, username, password, query = '?editor2d=1') {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/editor-pro/${query}`, {
    waitUntil: 'domcontentloaded',
  });
  await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
  await page.locator('text=Motor 2D Konva').waitFor({ state: 'visible', timeout: 30_000 });
}

async function selectTool(page, name) {
  await page.getByRole('button', { name, exact: true }).click();
}

async function selectAsset(page, label) {
  const exactCard = page.locator(`.te-asset-card[title="${label}"]`).first();
  try {
    await exactCard.waitFor({ state: 'visible', timeout: 10_000 });
    await exactCard.scrollIntoViewIfNeeded();
    await exactCard.click();
    await page.waitForFunction(() => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      return Boolean(state?.activeAssetId) && state?.activeTool !== 'select' && state?.activeTool !== 'pan';
    });
    return;
  } catch (error) {
    // Fallback to visible text search.
  }
  const search = page.locator('.te-library-search input[type="search"]');
  if (await search.count()) {
    try {
      await search.fill(label);
      const card = page.locator('.te-asset-card').filter({ hasText: label }).first();
      await card.waitFor({ state: 'visible', timeout: 10_000 });
      await card.scrollIntoViewIfNeeded();
      await card.click();
      await search.fill('');
      await page.waitForFunction(() => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        return Boolean(state?.activeAssetId) && state?.activeTool !== 'select' && state?.activeTool !== 'pan';
      });
      return;
    } catch (error) {
      // Fallback below.
    }
  }
  const roleCard = page.getByRole('button', { name: new RegExp(label) }).first();
  await roleCard.waitFor({ state: 'visible', timeout: 10_000 });
  await roleCard.scrollIntoViewIfNeeded();
  await roleCard.click();
  await page.waitForFunction(() => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    return Boolean(state?.activeAssetId) && state?.activeTool !== 'select' && state?.activeTool !== 'pan';
  });
}

async function clickCanvasAtScene(page, box, scenePoint) {
  const { viewport } = await getSceneState(page);
  const screen = sceneToScreen(box, viewport, scenePoint);
  await page.mouse.click(Math.round(screen.x), Math.round(screen.y));
}

async function dragCanvasAtScene(page, box, fromPoint, toPoint) {
  const { viewport } = await getSceneState(page);
  const from = sceneToScreen(box, viewport, fromPoint);
  const to = sceneToScreen(box, viewport, toPoint);
  await page.mouse.move(Math.round(from.x), Math.round(from.y));
  await page.mouse.down();
  await page.mouse.move(Math.round(to.x), Math.round(to.y), { steps: 18 });
  await page.mouse.up();
}

async function selectSceneObjectById(page, objectId) {
  const objectButton = page.getByTestId(`scene-object-${objectId}`);
  await objectButton.waitFor({ state: 'visible', timeout: 15_000 });
  assert.equal(await objectButton.count(), 1, `Expected a single scene-object-${objectId} button`);
  assert.equal(await objectButton.isEnabled(), true, `Expected scene-object-${objectId} to be enabled`);
  await objectButton.click();
  await page.waitForFunction(
    (id) => {
      const button = document.querySelector(`[data-testid="scene-object-${id}"]`);
      return button?.getAttribute('aria-pressed') === 'true';
    },
    objectId
  );
  await page.waitForFunction(
    (id) => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      return Boolean(state?.selectedIds?.includes(id));
    },
    objectId
  );
}

async function assertControlReady(page, testId) {
  const locator = page.getByTestId(testId);
  await locator.waitFor({ state: 'visible', timeout: 15_000 });
  assert.equal(await locator.isEnabled(), true, `${testId} should be enabled`);
  const box = await locator.boundingBox();
  assert(box, `${testId} should have a bounding box`);
  assert(box.width > 0, `${testId} should have width`);
  assert(box.height > 0, `${testId} should have height`);
  const covered = await page.evaluate(
    ({ currentTestId, x, y }) => {
      const element = document.elementFromPoint(x, y);
      return Boolean(element?.closest(`[data-testid="${currentTestId}"]`));
    },
    { currentTestId: testId, x: box.x + box.width / 2, y: box.y + box.height / 2 }
  );
  assert.equal(covered, true, `${testId} should not be covered`);
  return locator;
}

async function clickControl(page, testId) {
  const locator = await assertControlReady(page, testId);
  await locator.click();
}

async function setInspectorNumericField(page, label, value) {
  const field = page.locator('.te-inspector').getByRole('spinbutton', { name: label, exact: true });
  await field.waitFor({ state: 'visible', timeout: 15_000 });
  await field.fill(String(value));
  await field.press('Enter');
}

async function fillInspectorField(page, labelText, value) {
  const field = page.locator('.te-inspector').getByLabel(labelText, { exact: true }).first();
  await field.waitFor({ state: 'visible', timeout: 15_000 });
  if (await field.evaluate((el) => el.tagName.toLowerCase() === 'select')) {
    await field.selectOption(String(value));
    return;
  }
  await field.fill(String(value));
  await field.press('Tab').catch(() => {});
}

async function configureSelectedPlayer(page, spec) {
  await fillInspectorField(page, 'Nombre', spec.name);
  await fillInspectorField(page, 'Etiqueta', spec.label);
  await fillInspectorField(page, 'Dorsal', spec.number);
  if (spec.team) {
    await fillInspectorField(page, 'Equipo', spec.team).catch(() => {});
  }
}

async function setTimelineTime(page, value) {
  const slider = page.getByLabel('Tiempo');
  await slider.evaluate((input, nextValue) => {
    const element = input;
    element.value = String(nextValue);
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }, value);
}

async function setTimelineDuration(page, seconds) {
  const input = page.locator('label:has-text("Duración") input[type="number"]');
  await input.fill(String(seconds));
  await input.evaluate((element) => {
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

async function waitForStoreKeyframes(page, expected) {
  await page.waitForFunction(
    (target) => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      return (state?.scene?.timeline?.keyframes?.length || 0) >= target;
    },
    expected
  );
}

async function readSceneJson(page) {
  await page.getByRole('button', { name: /Copiar JSON/i }).click();
  return page.evaluate(() => navigator.clipboard.readText());
}

async function getObjectById(page, objectId) {
  return page.evaluate((id) => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    const object = state?.scene?.objects.find((item) => item.id === id);
    return object
      ? {
          id: object.id,
          x: object.x,
          y: object.y,
          width: object.width,
          height: object.height,
          layerId: object.layerId,
          type: object.type,
        }
      : null;
  }, objectId);
}

async function getProjectedObjectById(page, objectId) {
  return page.evaluate((id) => {
    const store = window.__TACTICAL_EDITOR_STORE__;
    const state = store?.getState();
    const scene = state?.scene;
    if (!scene) {
      return null;
    }
    const timeline = scene.timeline || {
      duration: 0,
      currentTime: 0,
      keyframes: [],
      tracks: [],
      sequences: [],
      currentSequenceId: null,
    };
    const currentTime = typeof timeline.currentTime === 'number' ? timeline.currentTime : 0;
    const object = scene.objects.find((item) => item.id === id);
    if (!object) {
      return null;
    }
    const track = (Array.isArray(timeline.tracks) ? timeline.tracks : []).find((item) => item.objectId === id);
    if (!track || !Array.isArray(track.keyframes) || !track.keyframes.length) {
      return {
        id: object.id,
        x: object.x,
        y: object.y,
        width: object.width,
        height: object.height,
        layerId: object.layerId,
        type: object.type,
      };
    }
    const frames = [...track.keyframes].sort((left, right) => left.time - right.time);
    const first = frames[0];
    const last = frames[frames.length - 1];
    const lerp = (a, b, ratio) => a + (b - a) * ratio;
    const interpolate = (left, right, ratio) => {
      const values = right.values || left.values || {};
      const leftValues = left.values || {};
      const resolved = {};
      const numericKeys = ['x', 'y', 'width', 'height', 'rotation', 'scaleX', 'scaleY', 'zIndex'];
      for (const key of numericKeys) {
        if (typeof leftValues[key] === 'number' && typeof right.values?.[key] === 'number') {
          resolved[key] = lerp(leftValues[key], right.values[key], ratio);
        } else if (typeof values[key] === 'number') {
          resolved[key] = values[key];
        } else if (typeof leftValues[key] === 'number') {
          resolved[key] = leftValues[key];
        }
      }
      return resolved;
    };
    let values = first.values || {};
    if (currentTime <= first.time) {
      values = first.values || {};
    } else if (currentTime >= last.time) {
      values = last.values || {};
    } else {
      const previous = [...frames].reverse().find((frame) => frame.time <= currentTime) || first;
      const next = frames.find((frame) => frame.time >= currentTime && frame.id !== previous.id) || last;
      if (previous.id === next.id) {
        values = previous.values || {};
      } else {
        const ratio = Math.min(1, Math.max(0, (currentTime - previous.time) / Math.max(next.time - previous.time, 1)));
        values = interpolate(previous, next, ratio);
      }
    }
    return {
      id: object.id,
      x: typeof values.x === 'number' ? values.x : object.x,
      y: typeof values.y === 'number' ? values.y : object.y,
      width: typeof values.width === 'number' ? values.width : object.width,
      height: typeof values.height === 'number' ? values.height : object.height,
      layerId: object.layerId,
      type: object.type,
    };
  }, objectId);
}

async function waitForObjectPosition(page, objectId, expected) {
  await page.waitForFunction(
    ({ id, x, y }) => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const state = store?.getState();
      const object = state?.scene?.objects.find((item) => item.id === id);
      return Boolean(object) && Math.abs(object.x - x) < 20 && Math.abs(object.y - y) < 20;
    },
    { id: objectId, x: expected.x, y: expected.y }
  );
}

async function moveObjectToScenePoint(page, objectId, targetCenter) {
  const baseObject = await getObjectById(page, objectId);
  assert(baseObject, `Missing object ${objectId}`);
  const stationary =
    Boolean(baseObject) &&
    Math.abs(baseObject.x + baseObject.width / 2 - targetCenter.x) < 0.5 &&
    Math.abs(baseObject.y + baseObject.height / 2 - targetCenter.y) < 0.5;
  await selectTool(page, 'Seleccionar');
  await selectSceneObjectById(page, objectId);
  if (stationary) {
    return;
  }
  await setInspectorNumericField(page, 'X', targetCenter.x - baseObject.width / 2);
  await setInspectorNumericField(page, 'Y', targetCenter.y - baseObject.height / 2);
  await waitForObjectPosition(page, objectId, {
    x: targetCenter.x - baseObject.width / 2,
    y: targetCenter.y - baseObject.height / 2,
  });
}

async function captureSelectionKeyframe(page) {
  await page.waitForFunction(
    () => {
      const button = document.querySelector('[data-testid="animation-add-keyframe"]');
      return Boolean(button && !button.hasAttribute('disabled'));
    },
    { timeout: 10_000 }
  );
  await clickControl(page, 'animation-add-keyframe');
  const scene = await getSceneState(page);
  assert.equal(scene.selectedIds.length > 0, true, 'A selected object is required to add keyframes');
}

async function saveBoard(page) {
  await page.getByRole('button', { name: /Guardar pizarra|Pizarra guardada|Guardando/i }).click();
  await page.waitForTimeout(1800);
}

async function takeShot(page, filePath) {
  await page.screenshot({ path: filePath, fullPage: true });
}

const DEMO_RECREATION_PARTICIPANTS = [
  {
    key: 'goalkeeper',
    asset: 'Portero local',
    name: 'Portero',
    label: 'GK',
    number: '1',
    team: 'home',
    frames: [
      { time: 0, center: { x: 120, y: 340 } },
      { time: 3, center: { x: 120, y: 340 } },
      { time: 6, center: { x: 126, y: 346 } },
      { time: 10, center: { x: 136, y: 348 } },
    ],
  },
  {
    key: 'rcb',
    asset: 'Jugador local espalda',
    name: 'Central derecho',
    label: 'RCB',
    number: '4',
    team: 'home',
    frames: [
      { time: 0, center: { x: 250, y: 220 } },
      { time: 3, center: { x: 304, y: 220 } },
      { time: 6, center: { x: 344, y: 238 } },
      { time: 10, center: { x: 366, y: 246 } },
    ],
  },
  {
    key: 'lcb',
    asset: 'Jugador local espalda',
    name: 'Central izquierdo',
    label: 'LCB',
    number: '5',
    team: 'home',
    frames: [
      { time: 0, center: { x: 250, y: 460 } },
      { time: 3, center: { x: 284, y: 446 } },
      { time: 6, center: { x: 300, y: 440 } },
      { time: 10, center: { x: 312, y: 438 } },
    ],
  },
  {
    key: 'rb',
    asset: 'Jugador local lateral',
    name: 'Lateral derecho',
    label: 'RB',
    number: '2',
    team: 'home',
    frames: [
      { time: 0, center: { x: 350, y: 150 } },
      { time: 3, center: { x: 418, y: 162 } },
      { time: 6, center: { x: 506, y: 188 } },
      { time: 10, center: { x: 620, y: 230 } },
    ],
  },
  {
    key: 'lb',
    asset: 'Jugador local',
    name: 'Lateral izquierdo',
    label: 'LB',
    number: '3',
    team: 'home',
    frames: [
      { time: 0, center: { x: 350, y: 420 } },
      { time: 3, center: { x: 382, y: 426 } },
      { time: 6, center: { x: 412, y: 432 } },
      { time: 10, center: { x: 458, y: 438 } },
    ],
  },
  {
    key: 'mcd',
    asset: 'Jugador local',
    name: 'Mediocentro',
    label: 'MCD',
    number: '6',
    team: 'home',
    frames: [
      { time: 0, center: { x: 390, y: 340 } },
      { time: 3, center: { x: 356, y: 332 } },
      { time: 6, center: { x: 446, y: 338 } },
      { time: 10, center: { x: 520, y: 362 } },
    ],
  },
  {
    key: 'ir',
    asset: 'Jugador local',
    name: 'Interior derecho',
    label: 'IR',
    number: '8',
    team: 'home',
    frames: [
      { time: 0, center: { x: 550, y: 220 } },
      { time: 3, center: { x: 578, y: 224 } },
      { time: 6, center: { x: 612, y: 240 } },
      { time: 10, center: { x: 706, y: 250 } },
    ],
  },
  {
    key: 'il',
    asset: 'Jugador local',
    name: 'Interior izquierdo',
    label: 'IL',
    number: '10',
    team: 'home',
    frames: [
      { time: 0, center: { x: 550, y: 460 } },
      { time: 3, center: { x: 564, y: 456 } },
      { time: 6, center: { x: 582, y: 452 } },
      { time: 10, center: { x: 602, y: 454 } },
    ],
  },
  {
    key: 'st',
    asset: 'Jugador local',
    name: 'Delantero',
    label: 'DC',
    number: '9',
    team: 'home',
    frames: [
      { time: 0, center: { x: 760, y: 340 } },
      { time: 3, center: { x: 784, y: 334 } },
      { time: 6, center: { x: 806, y: 324 } },
      { time: 10, center: { x: 826, y: 314 } },
    ],
  },
  {
    key: 'ball',
    asset: 'Balón',
    name: 'Balón',
    label: 'BAL',
    number: '',
    team: 'home',
    frames: [
      { time: 0, center: { x: 120, y: 340 } },
      { time: 3, center: { x: 304, y: 220 } },
      { time: 6, center: { x: 446, y: 338 } },
      { time: 10, center: { x: 620, y: 230 } },
    ],
  },
];

const DEMO_RECREATION_STATIC_ASSETS = [
  { asset: 'Cono', center: { x: 790, y: 186 } },
  { asset: 'Cono', center: { x: 826, y: 224 } },
  { asset: 'Cono', center: { x: 778, y: 300 } },
  { asset: 'Cono', center: { x: 842, y: 330 } },
  { asset: 'Zona rectangular', center: { x: 788, y: 252 } },
  { asset: 'Flecha de pase', center: { x: 214, y: 286 } },
  { asset: 'Flecha de carrera', center: { x: 484, y: 240 } },
  { asset: 'Trayectoria de balón', center: { x: 500, y: 332 } },
];

module.exports = {
  DEMO_RECREATION_PARTICIPANTS,
  DEMO_RECREATION_STATIC_ASSETS,
  assertControlReady,
  canvasBox,
  captureSelectionKeyframe,
  clickCanvasAtScene,
  clickControl,
  configureSelectedPlayer,
  dragCanvasAtScene,
  fillInspectorField,
  getFreePort,
  getObjectById,
  getNewSceneObjectId,
  getProjectedObjectById,
  getSceneState,
  httpGet,
  moveObjectToScenePoint,
  openEditor,
  readSceneJson,
  readSceneState,
  saveBoard,
  sceneToScreen,
  seedTacticalEditorTask,
  selectAsset,
  selectSceneObjectById,
  selectTool,
  setInspectorNumericField,
  setTimelineDuration,
  setTimelineTime,
  spawnLogged,
  takeShot,
  wait,
  waitForObjectPosition,
  waitForServer,
  waitForStoreKeyframes,
};
