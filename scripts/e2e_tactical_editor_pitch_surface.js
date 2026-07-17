/* eslint-disable no-console */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { chromium } = require(process.cwd() + '/node_modules/playwright');

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
    } catch (err) {
      // ignore retry
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
    slug="pitch-surface-team",
    defaults={"name": "Pitch Surface Team", "is_primary": True},
)
if not team.is_primary:
    team.is_primary = True
    team.save(update_fields=["is_primary"])
workspace, _ = Workspace.objects.get_or_create(
    slug="pitch-surface-workspace",
    defaults={
        "name": "Pitch Surface Workspace",
        "kind": Workspace.KIND_CLUB,
        "primary_team": team,
        "owner_user": user,
        "enabled_modules": {"sessions": True},
        "is_active": True,
    },
)
workspace.name = "Pitch Surface Workspace"
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
    title="Pitch Surface Microcycle",
    defaults={"week_start": date(2026, 7, 13), "week_end": date(2026, 7, 19)},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date(2026, 7, 15),
    defaults={"focus": "Pitch Surface", "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title="Pitch Surface Task",
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
                    "source": "pitch-surface",
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

async function analyzePitchBounds(page) {
  return page.evaluate(() => {
    const canvases = Array.from(document.querySelectorAll('.te-konva-stage canvas'));
    const analyzeCanvas = (canvas) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        return null;
      }
      const { width, height } = canvas;
      const { data } = ctx.getImageData(0, 0, width, height);
      let greenCount = 0;
      let minX = width;
      let minY = height;
      let maxX = -1;
      let maxY = -1;
      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const offset = (y * width + x) * 4;
          const r = data[offset];
          const g = data[offset + 1];
          const b = data[offset + 2];
          const a = data[offset + 3];
          if (a < 180) {
            continue;
          }
          if (g > 70 && g >= r + 12 && g >= b + 8) {
            greenCount += 1;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x);
            maxY = Math.max(maxY, y);
          }
        }
      }
      return {
        width,
        height,
        greenCount,
        bounds: greenCount ? { left: minX, top: minY, right: maxX, bottom: maxY } : null,
      };
    };
    const analyzed = canvases.map(analyzeCanvas).filter(Boolean);
    analyzed.sort((a, b) => b.greenCount - a.greenCount);
    return analyzed[0] || null;
  });
}

async function assertPitchFits(page, label) {
  const result = await analyzePitchBounds(page);
  if (!result || !result.bounds) {
    throw new Error(`[${label}] pitch bounds not detected`);
  }
  const { width, height, bounds } = result;
  const margin = 6;
  if (bounds.left < margin || bounds.top < margin) {
    throw new Error(`[${label}] pitch touches top/left edge: ${JSON.stringify(result)}`);
  }
  if (bounds.right > width - margin || bounds.bottom > height - margin) {
    throw new Error(`[${label}] pitch touches bottom/right edge: ${JSON.stringify(result)}`);
  }
  const pitchWidth = bounds.right - bounds.left + 1;
  const pitchHeight = bounds.bottom - bounds.top + 1;
  const ratio = pitchWidth / pitchHeight;
  if (ratio < 1.35 || ratio > 1.8) {
    throw new Error(`[${label}] pitch ratio out of bounds: ${ratio.toFixed(3)} · ${JSON.stringify(result)}`);
  }
  return result;
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
  await page.getByRole('button', { name: 'Vista 2D' }).click();
  await page.waitForTimeout(250);
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..');
  const dbPath = path.join(os.tmpdir(), `tactical-editor-pitch-surface-${Date.now()}.sqlite3`);
  const dbUrl = `sqlite:////${dbPath}`;
  const port = Number(process.env.E2E_PORT || 8137);
  const baseUrl = (process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`).replace(/\/+$/, '');
  const username = process.env.E2E_USERNAME || 'pitch-surface';
  const password = process.env.E2E_PASSWORD || 'pitch-surface';

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
    throw new Error('The tactical editor pitch surface server did not start');
  }

  const browser = await chromium.launch({ headless: true });
  const outDir = path.join(repoRoot, 'output', 'qa', 'tactical-editor-phase-2b', 'pitch-surface');
  fs.mkdirSync(outDir, { recursive: true });
  const sizes = [
    { name: '1440x900', width: 1440, height: 900 },
    { name: '1280x800', width: 1280, height: 800 },
    { name: '1024x768', width: 1024, height: 768 },
    { name: 'responsive', width: 920, height: 940 },
  ];

  try {
    for (const size of sizes) {
      const context = await browser.newContext({
        viewport: { width: size.width, height: size.height },
        acceptDownloads: true,
        ignoreHTTPSErrors: true,
      });
      const page = await context.newPage();
      page.setDefaultTimeout(30_000);
      await openEditor(page, baseUrl, taskId, username, password);

      await page.getByRole('button', { name: 'Ajustar campo' }).click();
      await page.waitForTimeout(350);
      await assertPitchFits(page, `${size.name}:fit`);
      await page.screenshot({ path: path.join(outDir, `pitch-${size.name}.png`), fullPage: true });

      if (size.name === '1440x900') {
        await page.getByRole('button', { name: 'Capas' }).click();
        await page.screenshot({ path: path.join(outDir, 'pitch-layers-open.png'), fullPage: true });
        await page.getByRole('button', { name: 'Props' }).click();
        const stageBox = await page.locator('.te-konva-stage').boundingBox();
        if (!stageBox) {
          throw new Error('Stage box not found for zoom interaction');
        }
        await page.mouse.move(
          Math.round(stageBox.x + stageBox.width / 2),
          Math.round(stageBox.y + stageBox.height / 2)
        );
        await page.mouse.wheel(0, -1200);
        await page.waitForTimeout(250);
        await page.screenshot({ path: path.join(outDir, 'pitch-zoomed-before-fit.png'), fullPage: true });
        await page.getByRole('button', { name: 'Ajustar campo' }).click();
        await page.waitForTimeout(350);
        await assertPitchFits(page, '1440x900:reset');
        await page.screenshot({ path: path.join(outDir, 'pitch-after-fit.png'), fullPage: true });
      }

      await context.close();
    }
    console.log(`[pitch-surface] ok · task=${taskId}`);
  } finally {
    await browser.close().catch(() => null);
    serverProc.kill('SIGTERM');
    try {
      fs.unlinkSync(dbPath);
    } catch (error) {
      // Ignore cleanup failures for temporary QA databases.
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
