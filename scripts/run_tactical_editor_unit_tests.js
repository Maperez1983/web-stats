#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend', 'tactical-editor');
const tscBin = path.join(frontendRoot, 'node_modules', '.bin', 'tsc');
const buildDir = fs.mkdtempSync(path.join(os.tmpdir(), 'tactical-editor-unit-'));
const sourceFiles = [
  'src/domain/taskDocument.ts',
  'src/editor/core/sceneSchema.ts',
  'src/editor/core/HistoryManager.ts',
  'src/editor/core/LayerManager.ts',
  'src/editor/core/SelectionManager.ts',
  'src/editor/objects/ObjectFactory.ts',
  'src/editor/serialization/SceneSerializer.ts',
];

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
    ...sourceFiles,
  ],
  {
    cwd: frontendRoot,
    stdio: 'inherit',
  }
);

const testFile = path.join(repoRoot, 'scripts', 'tactical_editor_unit.test.js');
const result = spawnSync(process.execPath, ['--test', testFile], {
  cwd: repoRoot,
  env: {
    ...process.env,
    TACTICAL_EDITOR_BUILD_DIR: buildDir,
  },
  stdio: 'inherit',
});

if (result.error) {
  throw result.error;
}

process.exit(result.status == null ? 1 : result.status);
