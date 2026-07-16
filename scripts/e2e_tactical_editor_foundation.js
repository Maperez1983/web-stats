/* eslint-disable no-console */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { chromium, webkit } = require('playwright');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGet(url, env) {
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
    } catch (err) {
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
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from football.models import (
    AppUserRole,
    SessionTask,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)

username = ${JSON.stringify(username)}
password = ${JSON.stringify(password)}
User = get_user_model()
user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
user.email = f"{username}@example.com"
user.set_password(password)
user.save()
AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})
team, _ = Team.objects.get_or_create(
    slug="tactical-editor-foundation",
    defaults={"name": "Tactical Editor Foundation", "is_primary": True},
)
if not team.is_primary:
    team.is_primary = True
    team.save(update_fields=["is_primary"])
workspace, _ = Workspace.objects.get_or_create(
    slug="tactical-editor-foundation",
    defaults={
        "name": "Tactical Editor Foundation",
        "kind": Workspace.KIND_CLUB,
        "primary_team": team,
        "owner_user": user,
        "enabled_modules": {"sessions": True},
        "is_active": True,
    },
)
workspace.name = "Tactical Editor Foundation"
workspace.kind = Workspace.KIND_CLUB
workspace.primary_team = team
workspace.owner_user = user
workspace.enabled_modules = {"sessions": True}
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
    title="Micro tactical editor foundation",
    defaults={"week_start": date(2026, 7, 13), "week_end": date(2026, 7, 19)},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date(2026, 7, 15),
    defaults={"focus": "Salida de balón", "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title="Tarea base editor 2D",
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
                    "source": "foundation-v1",
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
  const result = spawnSync(
    'python3',
    ['manage.py', 'shell', '-c', shellCode],
    {
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
    }
  );
  if (result.status !== 0) {
    throw new Error('Seed fixture failed');
  }
  const taskId = Number(String(result.stdout || '').trim().split(/\s+/).pop());
  if (!Number.isFinite(taskId)) {
    throw new Error(`Invalid task id from seed: ${result.stdout}`);
  }
  return taskId;
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbUrl = `sqlite:////${path.join(os.tmpdir(), `tactical-editor-foundation-${Date.now()}.sqlite3`)}`;
  const port = Number(process.env.E2E_PORT || 8131);
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'editor-foundation';
  const password = process.env.E2E_PASSWORD || 'editor-foundation';
  const browserName = String(process.env.E2E_BROWSER || 'chromium').toLowerCase();

  await spawnLogged(
    'python3',
    ['manage.py', 'migrate', '--noinput'],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
        DEBUG: 'true',
        SECRET_KEY: process.env.SECRET_KEY || 'dev',
        ALLOW_SQLITE_IN_PROD: 'true',
      },
    }
  );
  const taskId = await seedFixture(dbUrl, username, password);

  const serverEnv = {
    ...process.env,
    DATABASE_URL: dbUrl,
    DEBUG: 'true',
    SECRET_KEY: process.env.SECRET_KEY || 'dev',
    ALLOW_SQLITE_IN_PROD: 'true',
    BOOTSTRAP_ADMIN_USERNAME: username,
    BOOTSTRAP_ADMIN_PASSWORD: password,
    BOOTSTRAP_ADMIN_EMAIL: `${username}@example.com`,
    BOOTSTRAP_ADMIN_RESET_PASSWORD: 'true', // pragma: allowlist secret
  };
  const serverProc = spawn('python3', ['manage.py', 'runserver', `127.0.0.1:${port}`, '--noreload'], {
    cwd: repoRoot,
    env: serverEnv,
    stdio: 'inherit',
  });

  const serverReady = await waitForServer(baseUrl);
  if (!serverReady) {
    serverProc.kill('SIGTERM');
    throw new Error('The tactical editor test server did not start');
  }

  let browserType = chromium;
  if (browserName === 'webkit') {
    browserType = webkit;
  }
  const browser = await browserType.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
    acceptDownloads: true,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);

  try {
    await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.click('button[type="submit"], input[type="submit"]'),
    ]);

    const editorUrl = `${baseUrl}/coach/sesiones/tarea/${taskId}/editor-pro/?editor2d=1`;
    await page.goto(editorUrl, { waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await page.getByRole('button', { name: 'Jugador' }).click();

    const stageCanvas = page.locator('.te-konva-stage canvas').first();
    await stageCanvas.waitFor({ state: 'visible', timeout: 30_000 });
    const box = await stageCanvas.boundingBox();
    if (!box) {
      throw new Error('Could not determine stage canvas bounds');
    }

    const playerScenePoint = {
      x: Math.round(box.width * 0.35) - 20,
      y: Math.round(box.height * 0.45) - 20,
    };
    await page.mouse.click(
      Math.round(box.x + box.width * 0.35),
      Math.round(box.y + box.height * 0.45)
    );
    await page.waitForTimeout(400);

    await page.getByRole('button', { name: 'Seleccionar' }).click();
    const dragStart = {
      x: Math.round(box.x + box.width * 0.35 + 21),
      y: Math.round(box.y + box.height * 0.45 + 21),
    };
    const dragEnd = {
      x: dragStart.x + 140,
      y: dragStart.y + 80,
    };
    await page.mouse.move(dragStart.x, dragStart.y);
    await page.mouse.down();
    await page.mouse.move(dragEnd.x, dragEnd.y, { steps: 10 });
    await page.mouse.up();

    await page.getByRole('button', { name: 'Cono' }).click();
    await page.mouse.click(
      Math.round(box.x + box.width * 0.62),
      Math.round(box.y + box.height * 0.28)
    );

    await page.getByRole('button', { name: 'Guardar pizarra' }).click();
    await page.waitForTimeout(1800);

    const documentUrlRaw = await page.locator('#tactical-editor-root').getAttribute('data-document-url');
    const documentUrl = documentUrlRaw ? new URL(documentUrlRaw, baseUrl).toString() : '';
    if (!documentUrl) {
      throw new Error('Missing document URL');
    }
    const response = await page.request.get(documentUrl);
    if (!response.ok()) {
      throw new Error(`Document API failed with status ${response.status()}`);
    }
    const payload = await response.json();
    const document = payload.document || {};
    const canvasState = (((document.graphic || {}).canvas_state) || {});
    const sceneObjects = Array.isArray(canvasState.sceneObjects) ? canvasState.sceneObjects : [];
    const objects = Array.isArray(canvasState.objects) ? canvasState.objects : [];
    if (!sceneObjects.some((item) => item.type === 'player')) {
      throw new Error('Saved scene does not contain a player');
    }
    if (!sceneObjects.some((item) => item.type === 'cone')) {
      throw new Error('Saved scene does not contain a cone');
    }
    const player = sceneObjects.find((item) => item.type === 'player');
    const playerX = Number(player?.x || 0);
    const playerY = Number(player?.y || 0);
    if (!player || (Math.abs(playerX - playerScenePoint.x) < 5 && Math.abs(playerY - playerScenePoint.y) < 5)) {
      throw new Error(`Player did not move as expected · x=${playerX} y=${playerY}`);
    }
    if (!objects.length) {
      throw new Error('Legacy canvas objects missing after save');
    }

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar PNG' }).click();
    const download = await downloadPromise;
    const downloadPath = path.join(os.tmpdir(), `tactical-editor-export-${Date.now()}.png`);
    await download.saveAs(downloadPath);
    const buffer = fs.readFileSync(downloadPath);
    if (buffer.length < 8) {
      throw new Error('PNG download is empty');
    }
    const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    if (!buffer.subarray(0, 8).equals(pngSignature)) {
      throw new Error('PNG signature mismatch');
    }

    console.log(`[e2e] editor foundation ok · task=${taskId}`);
  } finally {
    await page.close().catch(() => null);
    await context.close().catch(() => null);
    await browser.close().catch(() => null);
    serverProc.kill('SIGTERM');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
