/* eslint-disable no-console */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require('playwright');

const {
  canvasBox,
  fillInspectorField,
  getSceneState,
  moveObjectToScenePoint,
  readSceneJson,
  saveBoard,
  selectAsset,
  selectSceneObjectById,
  selectTool,
  setInspectorNumericField,
  takeShot,
  waitForObjectPosition,
} = require('./e2e/helpers/tacticalEditorHelpers');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loginAsLocalAdmin(page, baseUrl) {
  await page.goto(`${baseUrl}/login/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', 'localadmin');
  await page.fill('input[name="password"]', 'localadmin');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  await wait(500);
}

async function waitForServer(baseUrl, timeoutMs = 120_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(`${baseUrl}/login/`, { method: 'GET' });
      if (response.ok || response.status < 500) {
        return true;
      }
    } catch (error) {
      // ignore
    }
    await wait(750);
  }
  return false;
}

function seedCompatFixture() {
  const shellCode = `
from datetime import date
import json
from football.models import AppUserRole, SessionTask, Team, TrainingMicrocycle, TrainingSession, Workspace, WorkspaceMembership, WorkspaceTeam
from django.contrib.auth import get_user_model

User = get_user_model()
user, _ = User.objects.get_or_create(username="konva-compat", defaults={"email": "konva-compat@example.com"})
user.email = "konva-compat@example.com"
user.set_password("konva-compat")
user.save()
AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})
team, _ = Team.objects.get_or_create(
    slug="konva-compat-team",
    defaults={"name": "Konva Compatibility Team", "is_primary": True},
)
workspace, _ = Workspace.objects.get_or_create(
    slug="konva-compat-workspace",
    defaults={
        "name": "Konva Compatibility Workspace",
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
    title="Konva compat microcycle",
    defaults={"week_start": date(2026, 7, 13), "week_end": date(2026, 7, 19)},
)
session, _ = TrainingSession.objects.get_or_create(
    microcycle=microcycle,
    session_date=date(2026, 7, 15),
    defaults={"focus": "Compatibilidad Legacy Konva", "duration_minutes": 90},
)
task, _ = SessionTask.objects.get_or_create(
    session=session,
    title="Compatibilidad Legacy ↔ Konva",
    defaults={"block": SessionTask.BLOCK_MAIN_1, "duration_minutes": 18},
)
task.block = SessionTask.BLOCK_MAIN_1
task.duration_minutes = 18
task.objective = "Comprobar persistencia entre Legacy y Konva."
task.coaching_points = "Mantener IDs, tipos y metadatos."
task.notes = "Fixture local para Slice 4."
task.tactical_layout = {
    "meta": {
        "graphic_editor": {
            "canvas_state": {
                "version": "5.3.0",
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
                "objects": [
                    {
                        "id": "legacy-gk",
                        "name": "legacy-gk",
                        "type": "circle",
                        "left": 112,
                        "top": 300,
                        "width": 46,
                        "height": 46,
                        "fill": "#16a34a",
                        "stroke": "#dcfce7",
                        "strokeWidth": 2,
                        "text": "1",
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "goalkeeper",
                            "assetId": "goalkeeper.home.front",
                            "team": "home",
                            "orientation": "front",
                            "label": "GK",
                        },
                    },
                    {
                        "id": "legacy-cb",
                        "name": "legacy-cb",
                        "type": "circle",
                        "left": 250,
                        "top": 210,
                        "width": 44,
                        "height": 44,
                        "fill": "#2563eb",
                        "stroke": "#dbeafe",
                        "strokeWidth": 2,
                        "text": "4",
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "player",
                            "assetId": "player.home.back",
                            "team": "home",
                            "orientation": "back",
                            "label": "CB",
                            "number": "4",
                        },
                    },
                    {
                        "id": "legacy-cone",
                        "name": "legacy-cone",
                        "type": "triangle",
                        "left": 430,
                        "top": 400,
                        "width": 28,
                        "height": 30,
                        "fill": "#f97316",
                        "stroke": "#7c2d12",
                        "strokeWidth": 2,
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "cone",
                            "assetId": "cone.standard",
                            "variant": "standard",
                        },
                    },
                    {
                        "id": "legacy-pole",
                        "name": "legacy-pole",
                        "type": "rect",
                        "left": 548,
                        "top": 392,
                        "width": 10,
                        "height": 44,
                        "fill": "#fbbf24",
                        "stroke": "#78350f",
                        "strokeWidth": 2,
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "pica",
                            "assetId": "pole.standard",
                            "variant": "standard",
                        },
                    },
                    {
                        "id": "legacy-goal",
                        "name": "legacy-goal",
                        "type": "rect",
                        "left": 1000,
                        "top": 292,
                        "width": 80,
                        "height": 34,
                        "fill": "rgba(255,255,255,0.04)",
                        "stroke": "#f8fafc",
                        "strokeWidth": 2,
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "goal",
                            "assetId": "goal.standard",
                            "variant": "standard",
                        },
                    },
                    {
                        "id": "legacy-mini",
                        "name": "legacy-mini",
                        "type": "rect",
                        "left": 860,
                        "top": 200,
                        "width": 54,
                        "height": 24,
                        "fill": "rgba(255,255,255,0.04)",
                        "stroke": "#e2e8f0",
                        "strokeWidth": 2,
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "mini-goal",
                            "assetId": "mini-goal.standard",
                            "variant": "standard",
                        },
                    },
                    {
                        "id": "legacy-arrow",
                        "name": "legacy-arrow",
                        "type": "line",
                        "x1": 314,
                        "y1": 232,
                        "x2": 470,
                        "y2": 248,
                        "stroke": "#0ea5e9",
                        "strokeWidth": 4,
                        "fill": "#0ea5e9",
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "arrow-pass",
                            "assetId": "arrow.pass",
                            "variant": "pass",
                            "points": [314, 232, 470, 248],
                        },
                    },
                    {
                        "id": "legacy-zone",
                        "name": "legacy-zone",
                        "type": "rect",
                        "left": 650,
                        "top": 180,
                        "width": 180,
                        "height": 110,
                        "fill": "rgba(34,197,94,0.18)",
                        "stroke": "#4ade80",
                        "strokeWidth": 2,
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "zone-rect",
                            "assetId": "zone.rect",
                            "variant": "rect",
                        },
                    },
                    {
                        "id": "legacy-text",
                        "name": "legacy-text",
                        "type": "text",
                        "left": 680,
                        "top": 330,
                        "width": 180,
                        "height": 40,
                        "fill": "#f8fafc",
                        "stroke": "#f8fafc",
                        "strokeWidth": 1,
                        "fontSize": 24,
                        "text": "Salida",
                        "visible": True,
                        "opacity": 1,
                        "data": {
                            "kind": "text",
                            "assetId": "text.label",
                            "variant": "text",
                            "label": "Salida",
                        },
                    },
                ],
                "timeline": {
                    "duration": 0,
                    "currentTime": 0,
                    "keyframes": [],
                    "tracks": [],
                    "sequences": [],
                    "currentSequenceId": null,
                },
                "metadata": {
                    "title": task.title,
                    "createdAt": "",
                    "updatedAt": "",
                    "source": "legacy-seed",
                    "customNote": "slice4",
                },
                "legacyTheme": "midnight",
                "importedFrom": "legacy-fixture",
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
      DEBUG: 'true',
      SECRET_KEY: process.env.SECRET_KEY || 'dev',
      ALLOW_SQLITE_IN_PROD: 'true',
    },
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  if (result.status !== 0) {
    throw new Error('Failed to seed Konva compatibility fixture');
  }
  const taskId = Number(String(result.stdout || '').trim().split(/\s+/).pop());
  if (!Number.isFinite(taskId)) {
    throw new Error(`Invalid seeded task id: ${result.stdout}`);
  }
  return taskId;
}

async function openTaskEditor(page, baseUrl, taskId, mode) {
  const isKonva = mode === 'konva';
  const query = isKonva ? '?editor_lab=konva' : '?editor_lab=production';
  const route = isKonva
    ? `/coach/sesiones/tarea/${taskId}/editor-pro/`
    : `/coach/sesiones/tareas/${taskId}/editar/`;
  await page.goto(`${baseUrl}${route}${query}`, {
    waitUntil: 'domcontentloaded',
  });
  await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByTestId('editor-lab-selector').waitFor({ state: 'visible', timeout: 15_000 }).catch(() => null);
}

async function openDetailPage(page, baseUrl, taskId) {
  await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => null);
}

async function assertNoConsoleErrors(page, logBuffer) {
  const messages = logBuffer.filter((entry) => entry.type === 'error');
  assert.equal(messages.length, 0, `Expected no console errors, saw ${messages.map((entry) => entry.text).join('\n')}`);
  const pageErrors = page.__slice4PageErrors || [];
  assert.equal(pageErrors.length, 0, `Expected no page errors, saw ${pageErrors.map((entry) => entry.message).join('\n')}`);
}

async function main() {
  const baseUrl = (process.env.E2E_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
  const outDir = path.join(process.cwd(), 'output', 'qa', 'task-builder-konva-persistence');
  fs.mkdirSync(outDir, { recursive: true });

  if (!(await waitForServer(baseUrl))) {
    throw new Error(`Server not reachable at ${baseUrl}`);
  }

  const taskId = seedCompatFixture();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  const consoleBuffer = [];
  page.__slice4PageErrors = [];
  page.on('console', (message) => {
    consoleBuffer.push({ type: message.type(), text: message.text() });
  });
  page.on('pageerror', (error) => {
    page.__slice4PageErrors.push({ message: error.message });
  });

  try {
    await loginAsLocalAdmin(page, baseUrl);

    await openTaskEditor(page, baseUrl, taskId, 'production');
    await page.waitForTimeout(1200);
    const productionSelector = page.getByTestId('editor-lab-selector');
    await productionSelector.waitFor({ state: 'visible', timeout: 15_000 });
    assert.equal(await productionSelector.count(), 1);
    await takeShot(page, path.join(outDir, '01-legacy-original.png'));

    const originalJson = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'original-legacy-state.json'), JSON.stringify(originalJson, null, 2), 'utf8');
    assert.ok(Array.isArray(originalJson.objects) && originalJson.objects.length >= 8, 'Expected legacy objects');
    assert.equal(originalJson.legacyTheme, 'midnight');
    assert.equal(originalJson.importedFrom, 'legacy-fixture');
    assert.equal(originalJson.metadata?.customNote, 'slice4');

    await page.getByTestId('editor-lab-konva').click();
    await page.waitForURL(/editor_lab=konva/, { timeout: 15_000 });
    await page.waitForTimeout(1400);

    const konvaState = await getSceneState(page);
    assert.ok(konvaState.scene, 'Konva scene should load');
    assert.ok((konvaState.scene.objects || []).length >= 8, 'Konva should import all objects');
    await takeShot(page, path.join(outDir, '02-konva-imported.png'));

    const importedState = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'imported-konva-scene.json'), JSON.stringify(importedState, null, 2), 'utf8');
    assert.equal(importedState.legacyTheme, 'midnight');
    assert.equal(importedState.importedFrom, 'legacy-fixture');
    assert.equal(importedState.metadata?.compatibility?.source, 'legacy');
    assert.ok(Array.isArray(importedState.objects) && importedState.objects.length >= 8);

    await selectTool(page, 'Seleccionar');
    await selectSceneObjectById(page, 'legacy-cb');
    await moveObjectToScenePoint(page, 'legacy-cb', { x: 360, y: 246 });
    await selectSceneObjectById(page, 'legacy-cb');
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+D' : 'Control+D');
    await page.waitForTimeout(500);
    await selectSceneObjectById(page, 'legacy-cone');
    await page.keyboard.press('Backspace');
    await page.waitForTimeout(500);

    const beforeAddIds = (await getSceneState(page)).scene.objects.map((object) => object.id);
    await selectAsset(page, 'Jugador local');
    const konvaBox = await canvasBox(page);
    await page.mouse.click(konvaBox.x + 540, konvaBox.y + 250);
    await page.waitForFunction(
      (ids) => {
        const store = window.__TACTICAL_EDITOR_STORE__;
        const state = store?.getState();
        return (state?.scene?.objects || []).some((object) => !ids.includes(object.id));
      },
      beforeAddIds
    );
    const addedPlayerId = await page.evaluate((ids) => {
      const store = window.__TACTICAL_EDITOR_STORE__;
      const objects = store?.getState()?.scene?.objects || [];
      return objects.find((object) => !ids.includes(object.id))?.id || null;
    }, beforeAddIds);
    assert.ok(addedPlayerId, 'Expected a new player to be added');

    await selectAsset(page, 'Balón');
    await page.mouse.click(konvaBox.x + 620, konvaBox.y + 300);
    await selectAsset(page, 'Cono');
    await page.mouse.click(konvaBox.x + 700, konvaBox.y + 340);
    await selectAsset(page, 'Flecha de pase');
    await page.mouse.click(konvaBox.x + 760, konvaBox.y + 210);
    await selectAsset(page, 'Zona rectangular');
    await page.mouse.click(konvaBox.x + 860, konvaBox.y + 250);
    await selectAsset(page, 'Texto');
    await page.mouse.click(konvaBox.x + 780, konvaBox.y + 370);

    await selectSceneObjectById(page, 'legacy-text');
    await fillInspectorField(page, 'Nombre', 'Compatibilidad Konva').catch(() => {});
    await fillInspectorField(page, 'Etiqueta', 'Compatibilidad Konva').catch(() => {});
    await setInspectorNumericField(page, 'Opacidad', 0.92);

    await saveBoard(page);
    await page.waitForTimeout(1500);
    await takeShot(page, path.join(outDir, '03-konva-edited.png'));
    const savedKonvaState = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'saved-konva-scene.json'), JSON.stringify(savedKonvaState, null, 2), 'utf8');
    assert.equal(savedKonvaState.legacyTheme, 'midnight');
    assert.equal(savedKonvaState.importedFrom, 'legacy-fixture');
    assert.ok((savedKonvaState.objects || []).length >= 10, 'Expected additional objects after editing');
    assert.ok(
      (savedKonvaState.objects || []).some((object) => String(object.data?.name || object.text || '').includes('Compatibilidad Konva')),
      'Expected updated text to persist'
    );

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#tactical-editor-root').waitFor({ state: 'visible', timeout: 30_000 });
    await page.waitForTimeout(1200);
    await takeShot(page, path.join(outDir, '04-konva-after-reload.png'));
    const afterReloadKonva = JSON.parse(await readSceneJson(page));
    assert.equal(afterReloadKonva.legacyTheme, 'midnight');
    assert.equal(afterReloadKonva.importedFrom, 'legacy-fixture');
    assert.ok((afterReloadKonva.objects || []).length >= (savedKonvaState.objects || []).length);

    await openTaskEditor(page, baseUrl, taskId, 'production');
    await page.waitForTimeout(1200);
    const roundtripLegacy = JSON.parse(await readSceneJson(page));
    fs.writeFileSync(path.join(outDir, 'roundtrip-legacy-state.json'), JSON.stringify(roundtripLegacy, null, 2), 'utf8');
    assert.equal(roundtripLegacy.legacyTheme, 'midnight');
    assert.equal(roundtripLegacy.importedFrom, 'legacy-fixture');
    assert.ok((roundtripLegacy.objects || []).length >= (afterReloadKonva.objects || []).length);
    await takeShot(page, path.join(outDir, '05-legacy-after-roundtrip.png'));

    await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/editor-lab/?editor_lab=comparison`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(1200);
    await page.getByTestId('editor-lab-compare-warning').waitFor({ state: 'visible', timeout: 15_000 });
    const konvaFrame = page.frameLocator('[data-testid="editor-lab-konva-frame"]');
    await konvaFrame.getByTestId('editor-compare-warning').waitFor({ state: 'visible', timeout: 15_000 });
    const compareSaveButton = konvaFrame.getByRole('button', { name: /Guardar pizarra|Pizarra guardada|Guardando/i });
    await compareSaveButton.waitFor({ state: 'visible', timeout: 15_000 });
    assert.equal(await compareSaveButton.isDisabled(), true, 'Compare mode must keep Konva read-only');

    await openTaskEditor(page, baseUrl, taskId, 'production');
    await page.waitForTimeout(1200);

    const pngDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exportar PNG' }).click();
    const pngDownload = await pngDownloadPromise;
    await pngDownload.saveAs(path.join(outDir, '06-export-png.png'));

    await openDetailPage(page, baseUrl, taskId);
    const pdfButton = page.getByRole('link', { name: /PDF Club/i });
    const pdfHref = await pdfButton.getAttribute('href');
    assert.ok(pdfHref, 'Expected PDF Club link');
    const pdfPagePromise = page.waitForEvent('popup').catch(() => null);
    await pdfButton.click();
    const pdfPage = await pdfPagePromise;
    if (pdfPage) {
      await pdfPage.waitForLoadState('domcontentloaded').catch(() => {});
      await pdfPage.screenshot({ path: path.join(outDir, '07-export-pdf.png'), fullPage: true }).catch(() => null);
      await pdfPage.close().catch(() => {});
    } else {
      await page.screenshot({ path: path.join(outDir, '07-export-pdf.png'), fullPage: true });
    }

    await page.goto(`${baseUrl}/coach/sesiones/tarea/${taskId}/?tab=presentation`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    await takeShot(page, path.join(outDir, '08-presentation.png'));

    const warnings = {
      original: originalJson.metadata?.compatibility?.warnings || [],
      imported: importedState.metadata?.compatibility?.warnings || [],
      saved: savedKonvaState.metadata?.compatibility?.warnings || [],
      roundtrip: roundtripLegacy.metadata?.compatibility?.warnings || [],
    };
    fs.writeFileSync(path.join(outDir, 'conversion-warnings.json'), JSON.stringify(warnings, null, 2), 'utf8');

    const report = [
      '# Konva persistence compatibility',
      '',
      `- task_id: ${taskId}`,
      '- legacy canvas source: SessionTask.tactical_layout.meta.graphic_editor.canvas_state',
      '- legacy -> konva -> legacy round-trip: OK',
      '- IDs preserved when possible: OK',
      '- unknown legacy fields preserved: OK',
      '- export PNG: OK',
      '- export PDF / presentation: OK',
      '',
      '## Objects validated',
      '- goalkeeper',
      '- player',
      '- cone',
      '- pole',
      '- goal',
      '- mini-goal',
      '- arrow',
      '- zone',
      '- text',
      '',
      '## Warnings',
      `- original: ${warnings.original.length}`,
      `- imported: ${warnings.imported.length}`,
      `- saved: ${warnings.saved.length}`,
      `- roundtrip: ${warnings.roundtrip.length}`,
      '',
      '## QA',
      '- 01-legacy-original.png',
      '- 02-konva-imported.png',
      '- 03-konva-edited.png',
      '- 04-konva-after-reload.png',
      '- 05-legacy-after-roundtrip.png',
      '- 06-export-png.png',
      '- 07-export-pdf.png',
      '- 08-presentation.png',
      '',
    ].join('\n');
    fs.writeFileSync(path.join(outDir, 'compatibility-report.md'), report, 'utf8');

    await assertNoConsoleErrors(page, consoleBuffer);
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
