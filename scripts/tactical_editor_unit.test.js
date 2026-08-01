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
const assetRegistry = load('editor/assets/assetRegistry.js');
const canvasAdapter = load('editor/canvas/CanvasAdapter.js');
const legacyCanvasAdapter = load('editor/canvas/LegacyCanvasAdapter.js');
const konvaCanvasAdapter = load('editor/canvas/KonvaCanvasAdapter.js');
const taskGraphicStateAdapter = load('editor/persistence/TaskGraphicStateAdapter.js');
const objectFactory = load('editor/objects/ObjectFactory.js');
const serializer = load('editor/serialization/SceneSerializer.js');
const animationCommands = load('editor/animation/AnimationCommands.js');
const animationEngine = load('editor/animation/AnimationEngine.js');
const animationPlayer = load('editor/animation/AnimationPlayer.js');
const animationSerializer = load('editor/animation/AnimationSerializer.js');
const animationSelection = load('editor/animation/AnimationSelection.js');
global.window = global.window || { location: { search: '' } };
const editorStore = load('store/editorStore.js');
const tacticalLanguage = load('tactical-language/index.js');
const tacticalFixture = load('tactical-language/fixtures/buildUpFromGoalkeeper.js');

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

test('asset registry exposes categories search and defaults for training objects', () => {
  const categories = assetRegistry.listAssetCategories();
  assert.ok(categories.find((item) => item.id === 'players'));
  assert.ok(categories.find((item) => item.id === 'equipment'));
  assert.ok(assetRegistry.searchAssets('jugador').some((asset) => asset.assetId === 'player.home.front'));
  const playerAsset = assetRegistry.getAssetDefinition('player.home.front');
  assert.equal(playerAsset.label, 'Jugador local');
  assert.equal(assetRegistry.resolveAssetId(undefined, 'player-home'), 'player.home.front');
  assert.equal(assetRegistry.resolveAssetLayer('player.home.front'), 'players');
  const created = objectFactory.createAssetObject('cone.high', { x: 120, y: 160 });
  assert.equal(created.data.assetId, 'cone.high');
  assert.equal(created.data.variant, 'high');
  assert.equal(created.layerId, 'equipment');
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
  modernScene.objects.push(objectFactory.createAssetObject('player.home.back', { x: 400, y: 240 }));
  modernScene.objects[0].data.label = '9';
  modernScene.objects[0].data.team = 'away';
  modernScene.timeline.keyframes.push({ title: 'Paso 1', canvas_state: { objects: [] } });
  const serialized = serializer.sceneToLegacyCanvasState(modernScene);
  assert.equal(serialized.sceneObjects.length, 1);
  assert.equal(serialized.objects.length, 1);
  assert.equal(serialized.objects[0].data.sceneType, 'circle');
  assert.equal(serialized.objects[0].data.assetId, 'player.home.back');
  assert.ok(String(serialized.metadata.updatedAt).length > 0);

  const imported = serializer.parseImportedScene(JSON.stringify(modernScene), legacyDocument);
  assert.equal(imported.objects.length, 1);
  assert.equal(imported.objects[0].type, 'player-home');
  assert.equal(imported.objects[0].data.assetId, 'player.home.back');
  assert.equal(imported.timeline.keyframes.length, 1);
});

test('task graphic adapter preserves unknown legacy fields and warns on corrupt input', () => {
  const document = {
    task: { id: 41, title: 'Compatibilidad', block_label: 'Principal 1', duration_minutes: 18 },
    graphic: { canvas_width: 1280, canvas_height: 720, canvas_state: { objects: [] } },
  };
  const raw = {
    version: '5.3.0',
    schemaVersion: 7,
    documentId: '41',
    objects: [
      { id: 'dup-player', type: 'circle', left: 100, top: 140, width: 24, height: 24, data: { kind: 'player' } },
      { id: 'dup-player', type: 'circle', left: 140, top: 140, width: 24, height: 24, data: { kind: 'player' } },
    ],
    timeline: { duration: '12', currentTime: '18', keyframes: [] },
    legacyTheme: 'night',
    importedFrom: 'legacy-editor',
  };
  const preserved = taskGraphicStateAdapter.preserveUnknownLegacyFields(raw);
  assert.equal(preserved.legacyTheme, 'night');
  assert.equal(preserved.importedFrom, 'legacy-editor');
  assert.equal(taskGraphicStateAdapter.validateTaskGraphicState(raw).length >= 2, true);
  const normalized = taskGraphicStateAdapter.legacyCanvasToKonvaScene(raw, document);
  assert.ok(normalized.warnings.some((warning) => warning.code === 'task-graphic-future-schema'));
  assert.ok(normalized.warnings.some((warning) => warning.code === 'task-graphic-duplicate-id'));
  assert.equal(normalized.scene.metadata.__taskGraphicCompatibility.preservedLegacyFields.legacyTheme, 'night');

  const roundTrip = taskGraphicStateAdapter.konvaSceneToLegacyCanvas(normalized.scene);
  assert.equal(roundTrip.canvasState.legacyTheme, 'night');
  assert.equal(roundTrip.canvasState.importedFrom, 'legacy-editor');
  assert.equal(roundTrip.canvasState.objects.length, 2);
});

test('task graphic adapter normalizes empty and invalid payloads without crashing', () => {
  const document = {
    task: { id: 42, title: 'Vacío', block_label: 'Principal 1', duration_minutes: 18 },
    graphic: { canvas_width: 1280, canvas_height: 720, canvas_state: {} },
  };
  const normalized = taskGraphicStateAdapter.normalizeTaskGraphicState(null, document);
  assert.equal(normalized.scene.objects.length, 0);
  assert.equal(normalized.scene.timeline.currentTime, 0);
  assert.equal(taskGraphicStateAdapter.validateTaskGraphicState({}).length > 0, true);
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
  const reordered = editorOperations.moveSelectionOrder(scene, [player.id], 'front');
  const reorderedPlayer = reordered.objects.find((object) => object.id === player.id);
  assert.ok(reorderedPlayer.zIndex >= cone.zIndex);
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
  const ignoredSnap = editorOperations.snapObjectPosition(
    snapScene,
    { ...snapObject, x: 31, y: 31 },
    { snapEnabled: true, snapDistance: 20, gridVisible: false, gridSize: 10, showGuides: true },
    { ignore: true }
  );
  assert.equal(ignoredSnap.x, 31);
  assert.equal(ignoredSnap.guides.length, 0);

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

test('animation engine derives tracks and evaluates interpolated scenes', () => {
  const scene = sceneSchema.createDefaultScene('doc-6', 'Animación');
  const player = objectFactory.createObject('player', { x: 120, y: 160 });
  scene.objects.push(player);
  const startCapture = animationCommands.captureAnimationKeyframe(scene, 0, {
    objectIds: [player.id],
    label: 'Inicio',
  });
  scene.timeline.keyframes.push(startCapture.sceneKeyframe);
  scene.timeline.tracks = startCapture.tracks;
  player.x = 320;
  player.y = 260;
  player.rotation = 45;
  const endCapture = animationCommands.captureAnimationKeyframe(scene, 8, {
    objectIds: [player.id],
    label: 'Fin',
  });
  scene.timeline.keyframes.push(endCapture.sceneKeyframe);
  scene.timeline.tracks = endCapture.tracks;
  const normalized = animationSerializer.normalizeAnimationTimeline(scene);
  assert.equal(normalized.timeline.tracks.length, 1);
  assert.equal(normalized.timeline.tracks[0].keyframes.length, 2);
  const projected = animationEngine.evaluateAnimationScene(normalized, 4);
  const animatedPlayer = projected.objects.find((object) => object.id === player.id);
  assert.equal(Math.round(animatedPlayer.x), 220);
  assert.equal(Math.round(animatedPlayer.y), 210);
  assert.equal(Math.round(animatedPlayer.rotation), 23);
});

test('animation commands capture stationary keyframes without moving the object', () => {
  const scene = sceneSchema.createDefaultScene('doc-7', 'Estacionario');
  const goalkeeper = objectFactory.createObject('goalkeeper', { x: 140, y: 180 });
  scene.objects.push(goalkeeper);

  const firstCapture = animationCommands.captureAnimationKeyframe(scene, 0, {
    objectIds: [goalkeeper.id],
    label: 'Inicio fijo',
  });
  scene.timeline.keyframes.push(firstCapture.sceneKeyframe);
  scene.timeline.tracks = firstCapture.tracks;

  const secondCapture = animationCommands.captureAnimationKeyframe(scene, 4, {
    objectIds: [goalkeeper.id],
    label: 'Salida fija',
  });
  scene.timeline.keyframes.push(secondCapture.sceneKeyframe);
  scene.timeline.tracks = secondCapture.tracks;

  const normalized = animationSerializer.normalizeAnimationTimeline(scene);
  assert.equal(normalized.timeline.tracks.length, 1);
  assert.equal(normalized.timeline.tracks[0].keyframes.length, 2);
  assert.equal(normalized.timeline.tracks[0].keyframes[0].values.x, goalkeeper.x);
  assert.equal(normalized.timeline.tracks[0].keyframes[1].values.x, goalkeeper.x);
  const projected = animationEngine.evaluateAnimationScene(normalized, 2);
  const animatedGoalkeeper = projected.objects.find((object) => object.id === goalkeeper.id);
  assert.equal(animatedGoalkeeper.x, goalkeeper.x);
  assert.equal(animatedGoalkeeper.y, goalkeeper.y);
});

test('editor store preserves a stationary selection across timeline changes and keyframes', () => {
  const store = editorStore.useEditorStore;
  const scene = sceneSchema.createDefaultScene('doc-8', 'Store animación');
  const goalkeeper = objectFactory.createObject('goalkeeper-home', { x: 140, y: 180 });
  scene.objects.push(goalkeeper);

  const snapshot = store.getState();
  store.setState({
    scene,
    selectedIds: [],
  });

  try {
    store.getState().selectSingle(goalkeeper.id);
    assert.deepEqual(store.getState().selectedIds, [goalkeeper.id]);

    store.getState().setTimelineTime(3);
    assert.deepEqual(store.getState().selectedIds, [goalkeeper.id]);

    store.getState().addTimelineKeyframe(0, 'Inicio fijo');
    assert.deepEqual(store.getState().selectedIds, [goalkeeper.id]);

    store.getState().setTimelineTime(3);
    store.getState().addTimelineKeyframe(3, 'Salida fija');

    const timeline = store.getState().scene.timeline;
    assert.equal(timeline.tracks.length, 1);
    assert.equal(timeline.tracks[0].keyframes.length, 2);
    assert.equal(timeline.tracks[0].objectId, goalkeeper.id);
    assert.equal(store.getState().selectedIds[0], goalkeeper.id);
  } finally {
    store.setState(snapshot);
  }
});

test('editor store enables the 2D editor by default and still honors explicit legacy opt-out', () => {
  const storePath = path.join(buildDir, 'store/editorStore.js');
  const cacheKey = require.resolve(storePath);
  delete require.cache[cacheKey];
  const previousWindow = global.window;
  global.window = { location: { search: '', pathname: '/coach/sesiones/tarea/1/editor-pro/' } };
  const freshEditorStore = require(storePath);
  assert.equal(freshEditorStore.useEditorStore.getState().featureEnabled, true);
  delete require.cache[cacheKey];
  global.window = { location: { search: '?editor2d=0', pathname: '/coach/sesiones/tarea/1/editor-pro/' } };
  const legacyEditorStore = require(storePath);
  assert.equal(legacyEditorStore.useEditorStore.getState().featureEnabled, false);
  global.window = previousWindow;
  delete require.cache[cacheKey];
});

test('animation player advances speed and loop state deterministically', () => {
  const paused = animationPlayer.createAnimationPlaybackState();
  assert.equal(paused.playing, false);
  const advanced = animationPlayer.advanceAnimationTime(1, 1000, { ...paused, playing: true, speed: 2 }, 5);
  assert.equal(advanced.time, 3);
  const looped = animationPlayer.advanceAnimationTime(4.5, 1000, { ...paused, playing: true, loop: true, speed: 1 }, 5);
  assert.equal(looped.time, 0.5);
  const clamped = animationPlayer.advanceAnimationTime(4.5, 1000, { ...paused, playing: true, loop: false, speed: 1 }, 5);
  assert.equal(clamped.time, 5);
});

test('animation selection helpers deduplicate ids and preserve stable selection blocks', () => {
  const selection = animationSelection.createAnimationSelection({
    objectIds: ['a', 'a', 'b'],
    trackIds: ['t1', 't1'],
    keyframeIds: ['k1'],
    sequenceIds: [],
  });
  assert.deepEqual(selection.objectIds, ['a', 'b']);
  assert.deepEqual(animationSelection.toggleAnimationSelection(['a'], 'b', true), ['a', 'b']);
  assert.deepEqual(animationSelection.toggleAnimationSelection(['a', 'b'], 'a', true), ['b']);
});

test('tactical language MVP compiles a build-up recreation deterministically', () => {
  const scene = tacticalFixture.createBuildUpFromGoalkeeperFixture();
  const result = tacticalLanguage.compileTacticalRecreation(scene);
  assert.equal(result.scene.timeline.currentTime, 0);
  assert.equal(result.scene.timeline.tracks.length >= 4, true);
  assert.equal(result.scene.timeline.keyframes.length > 0, true);
  assert.equal(result.language.statements.some((statement) => statement.verb === 'PASS'), true);
  assert.equal(result.language.statements.some((statement) => statement.verb === 'RECEIVE'), true);
  assert.equal(result.language.statements.some((statement) => statement.verb === 'PROGRESSION'), true);
  assert.equal(result.possession.state, 'controlled');
  assert.equal(result.plan.executionOrder.length >= result.language.statements.length - 1, true);
});

test('editor store generates an automatic recreation without clearing the selection', () => {
  const store = editorStore.useEditorStore;
  const scene = tacticalFixture.createBuildUpFromGoalkeeperFixture();
  const goalkeeper = scene.objects.find((object) => object.type === 'goalkeeper-home');
  assert.ok(goalkeeper);

  const snapshot = store.getState();
  store.setState({
    scene,
    selectedIds: [goalkeeper.id],
    tacticalRecreation: null,
    tacticalRecreationToken: 0,
    dirty: false,
    error: null,
  });

  try {
    store.getState().generateRecreation();
    const next = store.getState();
    assert.deepEqual(next.selectedIds, [goalkeeper.id]);
    assert.equal(next.tacticalRecreationToken, 1);
    assert.ok(next.tacticalRecreation);
    assert.equal(next.scene.timeline.tracks.length >= 4, true);
    assert.equal(next.scene.timeline.keyframes.length > 0, true);
    assert.equal(next.scene.timeline.currentTime, 0);
    assert.equal(
      next.tacticalRecreation?.language.statements.some((statement) => statement.verb === 'PASS'),
      true
    );
  } finally {
    store.setState(snapshot);
  }
});

test('canvas adapters share the same public surface across legacy and konva', () => {
  const scene = sceneSchema.createDefaultScene('doc-canvas', 'Canvas');
  const deps = {
    getScene: () => scene,
    addSceneObject: () => undefined,
    removeSelectedObjects: () => undefined,
    duplicateSelectedObjects: () => undefined,
    undo: () => undefined,
    redo: () => undefined,
    fitToScene: () => undefined,
    exportPngDataUrl: () => 'data:image/png;base64,AA==',
  };
  const legacy = legacyCanvasAdapter.createLegacyCanvasAdapter(deps);
  const konva = konvaCanvasAdapter.createKonvaCanvasAdapter(deps);
  const methods = [
    'load',
    'save',
    'render',
    'createObject',
    'createPlayer',
    'createCone',
    'createArrow',
    'delete',
    'duplicate',
    'undo',
    'redo',
    'exportPNG',
    'fitToScene',
  ];
  methods.forEach((method) => {
    assert.equal(typeof legacy[method], 'function', `Legacy missing ${method}`);
    assert.equal(typeof konva[method], 'function', `Konva missing ${method}`);
  });
  assert.equal(legacy.kind, 'legacy');
  assert.equal(konva.kind, 'konva');
  assert.ok(canvasAdapter.createCanvasAdapter('legacy', deps).save(scene));
});
