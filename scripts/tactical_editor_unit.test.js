const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const buildDir = process.env.TACTICAL_EDITOR_BUILD_DIR;

if (!buildDir) {
  throw new Error('TACTICAL_EDITOR_BUILD_DIR is required');
}

function load(relPath) {
  return require(path.join(buildDir, relPath));
}

const sceneSchema = load('editor/core/sceneSchema.js');
const historyManager = load('editor/core/HistoryManager.js');
const layerManager = load('editor/core/LayerManager.js');
const selectionManager = load('editor/core/SelectionManager.js');
const editorOperations = load('editor/core/editorOperations.js');
const pitchGeometry = load('editor/pitch/pitchGeometry.js');
const objectFactory = load('editor/objects/ObjectFactory.js');
const serializer = load('editor/serialization/SceneSerializer.js');

test('scene schema creates a stable default scene and normalizes bad input', () => {
  const scene = sceneSchema.createDefaultScene('doc-1', 'Tarea base', 1280, 720);
  assert.equal(scene.schemaVersion, sceneSchema.SCENE_SCHEMA_VERSION);
  assert.equal(scene.documentId, 'doc-1');
  assert.equal(scene.canvas.width, 1280);
  assert.equal(scene.pitch.type, 'full');
  assert.equal(scene.layers.length, sceneSchema.DEFAULT_LAYERS.length);

  const original = {
    schemaVersion: 0,
    documentId: 42,
    pitch: { type: 'invalid', orientation: 'portrait', surface: 'ice', width: 7, height: 3 },
    canvas: { width: '400', height: '240', padding: 500 },
    viewport: { zoom: 99, x: '12', y: null },
    layers: [{ id: 'bad-layer', visible: false, locked: true, order: 5 }],
    objects: [{ id: 'o1', type: 'cone', x: '17', y: '19', width: '24', height: '28' }],
  };
  const snapshot = JSON.parse(JSON.stringify(original));
  const normalized = sceneSchema.ensureScene(original, {
    documentId: 'fallback-doc',
    title: 'Fallback',
    canvasWidth: 1050,
    canvasHeight: 680,
  });
  assert.deepEqual(original, snapshot);
  assert.equal(normalized.documentId, '42');
  assert.equal(normalized.pitch.type, sceneSchema.createDefaultScene('', '').pitch.type);
  assert.equal(normalized.pitch.orientation, 'portrait');
  assert.equal(normalized.pitch.surface, 'grass');
  assert.equal(normalized.canvas.padding, 160);
  assert.equal(normalized.viewport.zoom, 6);
  assert.equal(normalized.objects[0].layerId, 'players');
  assert.equal(sceneSchema.normalizeLayerId('unknown'), 'players');
  assert.match(sceneSchema.createUuid('scene'), /^scene-/);
});

test('history manager supports push undo redo and transaction snapshots', () => {
  const base = sceneSchema.createDefaultScene('doc-1', 'Tarea');
  const first = sceneSchema.createDefaultScene('doc-1', 'Tarea');
  first.objects.push(objectFactory.createObject('cone', { x: 40, y: 48 }));
  const history0 = historyManager.createHistoryState();
  const history1 = historyManager.pushHistorySnapshot(history0, base);
  assert.equal(history1.past.length, 1);
  const undoResult = historyManager.undoHistory(history1, first);
  assert.ok(undoResult.scene);
  const redoResult = historyManager.redoHistory(undoResult.history, undoResult.scene);
  assert.ok(redoResult.scene);
  const started = historyManager.beginHistoryTransaction(history0, base);
  const committed = historyManager.commitHistoryTransaction(started, base);
  assert.equal(committed.past.length, 0);
});

test('layer and selection managers preserve ordering and hit testing', () => {
  const layers = layerManager.createDefaultLayers();
  const hidden = layerManager.toggleLayerVisibility(layers, 'zones');
  assert.equal(layerManager.getLayerById(hidden, 'zones').visible, false);
  const locked = layerManager.toggleLayerLock(hidden, 'zones');
  assert.equal(layerManager.getLayerById(locked, 'zones').locked, true);
  const moved = layerManager.moveLayer(layers, 'players', -1);
  assert.equal(moved[3].id, 'players');
  const selection = selectionManager.toggleSelection(['a'], 'b', true);
  assert.deepEqual(selection, ['a', 'b']);
  const normalized = selectionManager.normalizeSelectionBox({ x: 80, y: 90, width: -30, height: -40 });
  assert.deepEqual(normalized, { x: 50, y: 50, width: 30, height: 40 });
  const ids = selectionManager.intersectingIds(
    [
      { id: 'p1', x: 20, y: 20, width: 40, height: 40, scaleX: 1, scaleY: 1 },
      { id: 'p2', x: 300, y: 300, width: 40, height: 40, scaleX: 1, scaleY: 1 },
    ],
    { x: 0, y: 0, width: 120, height: 120 }
  );
  assert.deepEqual(ids, ['p1']);
});

test('object factory returns object defaults per tool', () => {
  const player = objectFactory.createObject('player', { x: 100, y: 140 });
  const keeper = objectFactory.createObject('goalkeeper', { x: 160, y: 200 });
  const cone = objectFactory.createObject('cone');
  const arrow = objectFactory.createObject('arrow-curved');
  assert.equal(player.layerId, 'players');
  assert.equal(player.data.team, 'home');
  assert.equal(keeper.data.number, '1');
  assert.equal(cone.layerId, 'equipment');
  assert.equal(arrow.layerId, 'paths');
  assert.deepEqual(objectFactory.defaultLayerForObject('zone-rect'), 'zones');
});

test('serializer migrates legacy payloads and round-trips modern scene data', () => {
  const legacyDocument = {
    task: { id: 99, title: 'Legacy task', block_label: 'Principal 1', duration_minutes: 15 },
    graphic: {
      canvas_width: 1280,
      canvas_height: 720,
      canvas_state: {
        objects: [
          {
            id: 'cone-legacy',
            type: 'triangle',
            left: 120,
            top: 140,
            width: 28,
            height: 30,
            fill: '#f97316',
            data: { kind: 'cone' },
          },
        ],
      },
    },
  };
  const scene = serializer.createSceneFromDocument(legacyDocument);
  assert.equal(scene.documentId, '99');
  assert.equal(scene.objects[0].type, 'cone');
  assert.equal(scene.objects[0].layerId, 'equipment');

  const modernScene = sceneSchema.createDefaultScene('99', 'Legacy task', 1280, 720);
  modernScene.objects.push(objectFactory.createObject('player', { x: 400, y: 240 }));
  modernScene.objects[0].data.label = '9';
  modernScene.objects[0].data.team = 'away';
  modernScene.timeline.keyframes.push({ title: 'Paso 1', canvas_state: { objects: [] } });
  const serialized = serializer.sceneToLegacyCanvasState(modernScene);
  assert.equal(serialized.sceneObjects.length, 1);
  assert.equal(serialized.objects.length, 1);
  assert.equal(serialized.objects[0].data.sceneType, 'player');
  assert.ok(String(serialized.metadata.updatedAt).length > 0);

  const imported = serializer.parseImportedScene(JSON.stringify(modernScene), legacyDocument);
  assert.equal(imported.objects.length, 1);
  assert.equal(imported.objects[0].type, 'player');
  assert.equal(imported.timeline.keyframes.length, 1);
});

test('selection helpers respect visibility locking layers and groups', () => {
  const scene = sceneSchema.createDefaultScene('doc-2', 'Profesional');
  const player = objectFactory.createObject('player', { x: 120, y: 160 });
  const cone = objectFactory.createObject('cone', { x: 220, y: 160 });
  const hiddenBall = objectFactory.createObject('ball', { x: 320, y: 160 });
  hiddenBall.visible = false;
  const lockedMarker = objectFactory.createObject('marker', { x: 420, y: 160 });
  lockedMarker.locked = true;
  player.data.groupId = 'group-1';
  player.data.groupLabel = 'Bloque';
  cone.data.groupId = 'group-1';
  cone.data.groupLabel = 'Bloque';
  scene.objects.push(player, cone, hiddenBall, lockedMarker);

  assert.deepEqual(editorOperations.selectAllIds(scene).sort(), [player.id, cone.id].sort());
  assert.deepEqual(editorOperations.selectByType(scene, 'cone'), [cone.id]);
  assert.deepEqual(editorOperations.selectByLayer(scene, 'players'), [player.id]);
  assert.deepEqual(editorOperations.expandSelectionByGroups(scene, [player.id]).sort(), [player.id, cone.id].sort());
  assert.deepEqual(editorOperations.invertSelection(scene, [player.id]), [cone.id]);
});

test('snapping alignment grouping and timeline projection stay deterministic', () => {
  const scene = sceneSchema.createDefaultScene('doc-3', 'Profesional');
  const left = objectFactory.createObject('player', { x: 100, y: 140 });
  const middle = objectFactory.createObject('player', { x: 220, y: 180 });
  const right = objectFactory.createObject('player', { x: 340, y: 220 });
  scene.objects.push(left, middle, right);

  const aligned = editorOperations.alignObjects(scene, [left.id, middle.id, right.id], 'left');
  assert.equal(aligned.objects.find((object) => object.id === left.id).x, 100);
  assert.equal(aligned.objects.find((object) => object.id === middle.id).x, 100);

  const distributed = editorOperations.distributeObjects(scene, [left.id, middle.id, right.id], 'horizontal', 40);
  const distributedObjects = [left.id, middle.id, right.id].map((id) => distributed.objects.find((object) => object.id === id));
  assert.ok(distributedObjects[1].x > distributedObjects[0].x);
  assert.ok(distributedObjects[2].x > distributedObjects[1].x);

  const grouped = editorOperations.groupObjects(scene, [left.id, middle.id], 'Ataque');
  assert.ok(String(grouped.objects.find((object) => object.id === left.id).data.groupId).startsWith('group-'));
  const ungrouped = editorOperations.ungroupObjects(grouped, [left.id]);
  assert.equal(ungrouped.objects.find((object) => object.id === left.id).data.groupId, undefined);

  const snapScene = sceneSchema.createDefaultScene('doc-5', 'Snap');
  const snapObject = objectFactory.createObject('cone', { x: 31, y: 31 });
  snapScene.objects.push(snapObject);
  const snapped = editorOperations.snapObjectPosition(
    snapScene,
    { ...snapObject, x: 31, y: 31 },
    { snapEnabled: true, snapDistance: 20, gridVisible: false, gridSize: 10, showGuides: true }
  );
  assert.equal(snapped.x, pitchGeometry.getPitchRect(snapScene).x - snapObject.width / 2);
  assert.ok(snapped.guides.length > 0);

  const keyframeScene = sceneSchema.createDefaultScene('doc-4', 'Timeline');
  keyframeScene.objects.push(objectFactory.createObject('player', { x: 20, y: 20 }));
  const moving = keyframeScene.objects[0];
  const start = editorOperations.captureTimelineKeyframe(keyframeScene, 0, { objectIds: [moving.id], label: 'Inicio' });
  moving.x = 120;
  moving.y = 160;
  const end = editorOperations.captureTimelineKeyframe(keyframeScene, 10, { objectIds: [moving.id], label: 'Fin' });
  keyframeScene.timeline.keyframes.push(start, end);
  const projected = editorOperations.projectSceneAtTime(keyframeScene, 5);
  assert.equal(projected.objects[0].x, 70);
  assert.equal(projected.objects[0].y, 90);
});
