import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import importPlugin from 'eslint-plugin-import';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';

const commonIgnores = [
  '**/.venv/**',
  '**/artifacts/**',
  '**/media/**',
  '**/mobile/**',
  '**/node_modules/**',
  '**/output/**',
  '**/outputs/**',
  '**/staticfiles/**',
  '**/tmp/**',
  'football/static/vendor/**',
  'football/static/football/editor-pro/**',
];

export default [
  { ignores: commonIgnores },
  js.configs.recommended,
  {
    files: ['frontend/tactical-editor/**/*.{ts,tsx}'],
    plugins: {
      import: importPlugin,
      '@typescript-eslint': tsPlugin,
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true,
        },
      },
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'import/no-unresolved': 'off',
    },
  },
  {
    files: [
      'football/static/football/js/pitch_surface_25d.js',
      'football/static/football/js/session_task_detail_3d.js',
      'football/static/football/js/sessions_tactical_pad.js',
    ],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        fabric: 'readonly',
      },
    },
    rules: {
      'no-empty': ['warn', { allowEmptyCatch: true }],
      'no-extra-boolean-cast': 'off',
      'no-unreachable': 'off',
      'no-undef': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'import/no-unresolved': 'off',
      'no-useless-escape': 'warn',
    },
  },
  {
    files: ['scripts/**/*.{js,mjs,cjs}', 'eslint.config.mjs'],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.node,
      },
    },
    rules: {
      'no-empty': ['warn', { allowEmptyCatch: true }],
      'no-undef': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'import/no-unresolved': 'off',
    },
  },
  prettierConfig,
];
