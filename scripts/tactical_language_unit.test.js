#!/usr/bin/env node

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend', 'tactical-editor');
const tscBin = path.join(frontendRoot, 'node_modules', '.bin', 'tsc');
const buildDir = fs.mkdtempSync(path.join(os.tmpdir(), 'tactical-language-unit-'));

execFileSync(
  tscBin,
  [
    '--module',
    'CommonJS',
    '--target',
    'ES2020',
    '--moduleResolution',
    'Node',
    '--esModuleInterop',
    '--skipLibCheck',
    '--resolveJsonModule',
    '--outDir',
    buildDir,
    '--rootDir',
    'src',
    'src/domain/taskDocument.ts',
    'src/editor/assets/assetRegistry.ts',
    'src/editor/animation/AnimationCommands.ts',
    'src/editor/animation/AnimationEngine.ts',
    'src/editor/animation/AnimationInterpolator.ts',
    'src/editor/animation/AnimationPlayer.ts',
    'src/editor/animation/AnimationSelection.ts',
    'src/editor/animation/AnimationSerializer.ts',
    'src/editor/animation/AnimationTrack.ts',
    'src/editor/core/sceneSchema.ts',
    'src/editor/core/HistoryManager.ts',
    'src/editor/core/LayerManager.ts',
    'src/editor/core/SelectionManager.ts',
    'src/editor/core/editorOperations.ts',
    'src/editor/objects/ObjectFactory.ts',
    'src/editor/serialization/SceneSerializer.ts',
    'src/tactical-language/index.ts',
    'src/tactical-language/types.ts',
    'src/tactical-language/vocabulary.ts',
    'src/tactical-language/normalizer.ts',
    'src/tactical-language/inference.ts',
    'src/tactical-language/resolver.ts',
    'src/tactical-language/possession.ts',
    'src/tactical-language/timing.ts',
    'src/tactical-language/compiler.ts',
    'src/tactical-language/fixtures/buildUpFromGoalkeeper.ts',
    'src/store/editorStore.ts',
  ],
  {
    cwd: frontendRoot,
    stdio: 'inherit',
  }
);

const tacticalLanguage = require(path.join(buildDir, 'tactical-language', 'index.js'));
const fixture = require(path.join(buildDir, 'tactical-language', 'fixtures', 'buildUpFromGoalkeeper.js'));
const sceneSchema = require(path.join(buildDir, 'editor', 'core', 'sceneSchema.js'));
const objectFactory = require(path.join(buildDir, 'editor', 'objects', 'ObjectFactory.js'));

const result = tacticalLanguage.compileTacticalRecreation(fixture.createBuildUpFromGoalkeeperFixture());

assert.equal(result.language.statements.length, 9);
assert.equal(result.plan.executionOrder.length > 0, true);
assert.equal(result.timeline.duration, 10);
assert.equal(result.timeline.tracks.length >= 4, true);
assert.equal(result.timeline.keyframes.length > 0, true);
assert.equal(result.possession.state, 'controlled');
assert.ok(result.possession.carrierId);

function addLabeledObject(scene, type, x, y, label, options = {}) {
  const object = objectFactory.createObject(type, { x, y, ...options });
  object.data.label = label;
  scene.objects.push(object);
  return object;
}

function createScenarioScene(id, title, builder) {
  const scene = sceneSchema.createDefaultScene(id, title, 1050, 680);
  builder(scene);
  return scene;
}

function scenarioAssertions(name, compiled, expectedVerbs) {
  expectedVerbs.forEach((verb) => {
    assert.equal(compiled.language.statements.some((statement) => statement.verb === verb), true, `${name}: missing ${verb}`);
  });
  assert.equal(compiled.plan.executionOrder.length > 0, true, `${name}: missing execution order`);
  assert.equal(compiled.timeline.tracks.length > 0, true, `${name}: missing tracks`);
  assert.equal(compiled.timeline.keyframes.length > 0, true, `${name}: missing keyframes`);
  assert.equal(compiled.validationIssues.some((issue) => issue.severity === 'error'), false, `${name}: unexpected validation error`);
}

const rondoScene = createScenarioScene('mvp-rondo', 'Rondo simple', (scene) => {
  addLabeledObject(scene, 'player-home', 220, 200, 'A');
  addLabeledObject(scene, 'player-home', 330, 120, 'B');
  addLabeledObject(scene, 'player-home', 420, 280, 'C');
  addLabeledObject(scene, 'player-home', 520, 180, 'D');
  addLabeledObject(scene, 'player-away', 390, 200, 'Defensor');
  addLabeledObject(scene, 'ball', 250, 200, 'Balón', { assetId: 'ball.standard' });
});

const wallScene = createScenarioScene('mvp-wall', 'Pared simple', (scene) => {
  addLabeledObject(scene, 'player-home', 260, 240, 'Jugador A');
  addLabeledObject(scene, 'player-home', 410, 240, 'Jugador B');
  addLabeledObject(scene, 'ball', 280, 240, 'Balón', { assetId: 'ball.standard' });
  addLabeledObject(scene, 'arrow-pass', 286, 232, 'Pase');
  addLabeledObject(scene, 'arrow-run', 270, 210, 'Apoyo');
});

const finishScene = createScenarioScene('mvp-finish', 'Finalización', (scene) => {
  addLabeledObject(scene, 'player-home', 390, 300, 'Mediocentro');
  addLabeledObject(scene, 'player-home', 610, 300, 'Delantero');
  addLabeledObject(scene, 'goal', 860, 240, 'Portería', { assetId: 'goal.standard' });
  addLabeledObject(scene, 'ball', 410, 300, 'Balón', { assetId: 'ball.standard' });
  addLabeledObject(scene, 'arrow-pass', 440, 292, 'Pase');
  addLabeledObject(scene, 'arrow-pass', 620, 290, 'Tiro');
});

const circuitScene = createScenarioScene('mvp-circuit', 'Circuito técnico', (scene) => {
  addLabeledObject(scene, 'goalkeeper-home', 120, 300, 'Portero');
  addLabeledObject(scene, 'player-home', 330, 220, 'Central');
  addLabeledObject(scene, 'player-home', 470, 260, 'Mediocentro');
  addLabeledObject(scene, 'player-home', 620, 180, 'Lateral');
  addLabeledObject(scene, 'player-home', 760, 260, 'Llegada');
  addLabeledObject(scene, 'ball', 150, 300, 'Balón', { assetId: 'ball.standard' });
  addLabeledObject(scene, 'zone-rect', 820, 220, 'Zona objetivo');
  addLabeledObject(scene, 'arrow-pass', 180, 292, 'Pase');
  addLabeledObject(scene, 'arrow-run', 630, 180, 'Carrera');
});

scenarioAssertions('build-up', result, ['BUILD_UP', 'PASS', 'RECEIVE', 'CARRY', 'SUPPORT', 'HOLD', 'PROGRESSION']);
scenarioAssertions('rondo', tacticalLanguage.compileTacticalRecreation(rondoScene), ['BUILD_UP', 'PASS', 'RECEIVE', 'PRESS', 'SEQUENCE']);
scenarioAssertions('wall-pass', tacticalLanguage.compileTacticalRecreation(wallScene), ['PASS', 'RECEIVE', 'RETURN_PASS', 'SUPPORT']);
scenarioAssertions('finishing', tacticalLanguage.compileTacticalRecreation(finishScene), ['PASS', 'RECEIVE', 'SHOOT', 'HOLD']);
scenarioAssertions('technical-circuit', tacticalLanguage.compileTacticalRecreation(circuitScene), ['CARRY', 'RUN', 'PASS', 'RECEIVE', 'OCCUPY_SPACE']);

console.log('✔ tactical language MVP compiles a build-up recreation deterministically');
