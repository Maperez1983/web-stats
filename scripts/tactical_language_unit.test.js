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

const result = tacticalLanguage.compileTacticalRecreation(fixture.createBuildUpFromGoalkeeperFixture());

assert.equal(result.language.statements.length, 9);
assert.equal(result.plan.executionOrder.length > 0, true);
assert.equal(result.timeline.duration, 10);
assert.equal(result.timeline.tracks.length >= 4, true);
assert.equal(result.timeline.keyframes.length > 0, true);
assert.equal(result.possession.state, 'controlled');
assert.ok(result.possession.carrierId);

console.log('✔ tactical language MVP compiles a build-up recreation deterministically');
