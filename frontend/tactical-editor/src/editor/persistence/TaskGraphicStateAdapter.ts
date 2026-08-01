import {
  clampNumber,
  createDefaultScene,
  createUuid,
  deepClone,
  ensureScene,
  normalizeLayerId,
  type SceneLayerId,
  type SceneObject,
  type SceneObjectType,
  type TacticalScene,
} from '../core/sceneSchema';
import { getAssetDefinition, resolveAssetDefinition, resolveAssetId } from '../assets/assetRegistry';
import { normalizeAnimationTimeline } from '../animation/AnimationSerializer';
import type { TacticalCanvasObject, TacticalCanvasState, TaskEditorDocument } from '../../domain/taskDocument';

export type TaskGraphicCompatibilitySeverity = 'info' | 'warning' | 'error';

export type TaskGraphicCompatibilityWarning = {
  code: string;
  message: string;
  severity: TaskGraphicCompatibilitySeverity;
  path?: string;
  details?: Record<string, unknown>;
};

type TaskGraphicCompatibilityBundle = {
  source: 'legacy' | 'konva' | 'empty';
  warnings: TaskGraphicCompatibilityWarning[];
  preservedLegacyFields: Record<string, unknown>;
  preservedAt: string;
};

type SceneWithCompatibility = TacticalScene & {
  metadata: TacticalScene['metadata'] & {
    __taskGraphicCompatibility?: TaskGraphicCompatibilityBundle;
  };
};

export type TaskGraphicNormalizationResult = {
  scene: SceneWithCompatibility;
  warnings: TaskGraphicCompatibilityWarning[];
  preservedLegacyFields: Record<string, unknown>;
  source: 'legacy' | 'konva' | 'empty';
};

export type TaskGraphicLegacyCanvasResult = {
  canvasState: TacticalCanvasState & Record<string, unknown>;
  warnings: TaskGraphicCompatibilityWarning[];
};

const KNOWN_ROOT_FIELDS = new Set([
  'version',
  'schemaVersion',
  'documentId',
  'pitch',
  'canvas',
  'viewport',
  'layers',
  'objects',
  'sceneObjects',
  'timeline',
  'timelineState',
  'metadata',
]);

function coerceRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function cloneUnknownFields(source: Record<string, unknown> | null | undefined): Record<string, unknown> {
  if (!source) return {};
  const result: Record<string, unknown> = {};
  Object.entries(source).forEach(([key, value]) => {
    if (!KNOWN_ROOT_FIELDS.has(key)) {
      result[key] = deepClone(value);
    }
  });
  return result;
}

function compatibilityBundle(
  source: 'legacy' | 'konva' | 'empty',
  warnings: TaskGraphicCompatibilityWarning[],
  preservedLegacyFields: Record<string, unknown>
): TaskGraphicCompatibilityBundle {
  return {
    source,
    warnings: warnings.map((warning) => ({ ...warning, details: warning.details ? { ...warning.details } : undefined })),
    preservedLegacyFields: deepClone(preservedLegacyFields),
    preservedAt: new Date().toISOString(),
  };
}

function attachCompatibility(scene: TacticalScene, bundle: TaskGraphicCompatibilityBundle): SceneWithCompatibility {
  return {
    ...scene,
    metadata: {
      ...scene.metadata,
      __taskGraphicCompatibility: bundle,
    } as SceneWithCompatibility['metadata'],
  };
}

function detectWarnings(rawState: Record<string, unknown> | null | undefined): TaskGraphicCompatibilityWarning[] {
  const warnings: TaskGraphicCompatibilityWarning[] = [];
  if (!rawState || Object.keys(rawState).length === 0) {
    warnings.push({
      code: 'task-graphic-empty',
      severity: 'info',
      message: 'El estado gráfico estaba vacío y se creó una escena base.',
    });
    return warnings;
  }

  const schemaVersion = clampNumber(rawState.schemaVersion, 1, 0);
  if (schemaVersion > 1) {
    warnings.push({
      code: 'task-graphic-future-schema',
      severity: 'warning',
      path: 'schemaVersion',
      message: `La escena usa schemaVersion ${schemaVersion}, superior al compatible actual.`,
      details: { schemaVersion },
    });
  }

  const objects = Array.isArray(rawState.sceneObjects)
    ? rawState.sceneObjects
    : Array.isArray(rawState.objects)
      ? rawState.objects
      : [];
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  objects.forEach((object, index) => {
    const record = coerceRecord(object);
    const id = String(record?.id || record?.name || `object-${index}`).trim();
    if (!id) {
      warnings.push({
        code: 'task-graphic-object-missing-id',
        severity: 'warning',
        path: `objects.${index}.id`,
        message: 'Se detectó un objeto sin ID estable.',
      });
      return;
    }
    if (seen.has(id)) {
      duplicates.add(id);
      return;
    }
    seen.add(id);
  });
  duplicates.forEach((id) => {
    warnings.push({
      code: 'task-graphic-duplicate-id',
      severity: 'warning',
      path: 'objects',
      message: `Se detectó un ID duplicado: ${id}.`,
      details: { id },
    });
  });
  return warnings;
}

function inferLegacySceneTypeFromSceneObject(sceneObject: SceneObject): SceneObjectType {
  const assetId = typeof sceneObject.data?.assetId === 'string' ? sceneObject.data.assetId : undefined;
  const variant = typeof sceneObject.data?.variant === 'string' ? sceneObject.data.variant : undefined;
  const assetDefinition = resolveAssetDefinition(assetId, sceneObject.type, variant);
  return assetDefinition?.type || sceneObject.type;
}

function inferSceneType(rawObject: TacticalCanvasObject): SceneObjectType {
  const assetId = typeof rawObject.data?.assetId === 'string' ? rawObject.data.assetId : undefined;
  const assetDefinition = assetId ? getAssetDefinition(assetId) : null;
  if (assetDefinition?.type) {
    return assetDefinition.type;
  }
  const kind = String(rawObject.data?.kind || rawObject.data?.type || rawObject.name || '')
    .trim()
    .toLowerCase();
  if (kind.includes('goalkeeper')) return 'goalkeeper';
  if (kind.includes('player')) return 'player';
  if (kind.includes('ball')) return 'ball';
  if (kind.includes('cone')) return 'cone';
  if (kind.includes('pole') || kind.includes('pica')) return 'pole';
  if (kind.includes('hoop') || kind.includes('aro')) return 'hoop';
  if (kind.includes('mini-goal') || kind.includes('miniporter')) return 'mini-goal';
  if (kind.includes('arrow-curved')) return 'arrow-curved';
  if (kind.includes('arrow')) return 'arrow-straight';
  if (kind.includes('dashed')) return 'line-dashed';
  if (kind.includes('zone-circle')) return 'zone-circle';
  if (kind.includes('zone')) return 'zone-rect';
  if (kind.includes('text')) return 'text';
  if (kind.includes('label')) return 'label';

  switch (rawObject.type) {
    case 'circle':
      return String(rawObject.data?.marker || '').toLowerCase() === 'ball' ? 'ball' : 'player';
    case 'triangle':
      return 'cone';
    case 'textbox':
    case 'i-text':
    case 'text':
      return 'text';
    case 'line':
      return Array.isArray(rawObject.strokeDashArray) || Array.isArray(rawObject.data?.dash)
        ? 'line-dashed'
        : 'arrow-straight';
    case 'image':
      return 'legacy-shape';
    default:
      return 'legacy-shape';
  }
}

function inferLayerId(type: SceneObjectType): SceneLayerId {
  if (type === 'zone-rect' || type === 'zone-circle') return 'zones';
  if (type === 'arrow-straight' || type === 'arrow-curved' || type === 'line-dashed') return 'paths';
  if (type === 'text' || type === 'label') return 'texts';
  if (type === 'player' || type === 'goalkeeper' || type === 'ball') return 'players';
  return 'equipment';
}

function normalizeLegacyObject(rawObject: TacticalCanvasObject, index: number): SceneObject {
  const scaleX = clampNumber(rawObject.scaleX, 1, 0.05, 20);
  const scaleY = clampNumber(rawObject.scaleY, 1, 0.05, 20);
  const radius = clampNumber(rawObject.radius, 18, 1);
  const width = rawObject.type === 'circle' ? radius * 2 : clampNumber(rawObject.width, 42, 4);
  const height = rawObject.type === 'circle' ? radius * 2 : clampNumber(rawObject.height, 42, 4);
  const type = inferSceneType(rawObject);
  return {
    id: String(rawObject.id || rawObject.name || rawObject.data?.id || createUuid('legacy')),
    type,
    layerId: normalizeLayerId(rawObject.data?.layerId || inferLayerId(type)),
    x: clampNumber(rawObject.left, 0),
    y: clampNumber(rawObject.top, 0),
    width,
    height,
    rotation: clampNumber(rawObject.angle, 0),
    scaleX,
    scaleY,
    visible: rawObject.visible !== false,
    locked: Boolean(rawObject.data?.locked || rawObject.lockMovementX || rawObject.lockMovementY),
    zIndex: clampNumber(rawObject.zIndex, index),
    style: {
      fill: typeof rawObject.fill === 'string' ? rawObject.fill : undefined,
      stroke: typeof rawObject.stroke === 'string' ? rawObject.stroke : undefined,
      strokeWidth: clampNumber(rawObject.strokeWidth, 2, 0),
      fontSize: clampNumber(rawObject.fontSize, 20, 8),
      textColor: typeof rawObject.fill === 'string' ? rawObject.fill : undefined,
      dash: Array.isArray(rawObject.strokeDashArray)
        ? rawObject.strokeDashArray.map((item) => Number(item))
        : undefined,
      opacity: clampNumber(rawObject.opacity, 1, 0, 1),
    },
    data: {
      ...(rawObject.data || {}),
      assetId: resolveAssetId(
        rawObject.data?.assetId as string | undefined,
        type,
        rawObject.data?.variant as string | undefined
      ),
      label:
        typeof rawObject.text === 'string'
          ? rawObject.text
          : typeof rawObject.data?.label === 'string'
            ? rawObject.data.label
            : undefined,
      orientation: typeof rawObject.data?.orientation === 'string' ? rawObject.data.orientation : undefined,
      points:
        typeof rawObject.x1 === 'number' &&
        typeof rawObject.y1 === 'number' &&
        typeof rawObject.x2 === 'number' &&
        typeof rawObject.y2 === 'number'
          ? [rawObject.x1, rawObject.y1, rawObject.x2, rawObject.y2]
          : Array.isArray(rawObject.data?.points)
            ? (rawObject.data?.points as number[])
            : undefined,
      legacySource: deepClone(rawObject as Record<string, unknown>),
    },
  };
}

function sceneObjectToLegacyObject(sceneObject: SceneObject): TacticalCanvasObject {
  const legacySceneType = inferLegacySceneTypeFromSceneObject(sceneObject);
  const legacySource = sceneObject.data?.legacySource;
  const raw =
    legacySource && typeof legacySource === 'object'
      ? (deepClone(legacySource) as TacticalCanvasObject)
      : ({ type: 'rect' } as TacticalCanvasObject);

  raw.id = sceneObject.id;
  raw.name = sceneObject.id;
  raw.left = sceneObject.x;
  raw.top = sceneObject.y;
  raw.width = sceneObject.width;
  raw.height = sceneObject.height;
  raw.scaleX = sceneObject.scaleX;
  raw.scaleY = sceneObject.scaleY;
  raw.angle = sceneObject.rotation;
  raw.visible = sceneObject.visible;
  raw.opacity = sceneObject.style.opacity ?? 1;
  raw.fill = sceneObject.style.fill ?? raw.fill;
  raw.stroke = sceneObject.style.stroke ?? raw.stroke;
  raw.strokeWidth = sceneObject.style.strokeWidth ?? raw.strokeWidth ?? 2;
  raw.data = {
    ...(raw.data || {}),
    ...sceneObject.data,
    id: sceneObject.id,
    layerId: sceneObject.layerId,
    sceneType: legacySceneType,
    locked: sceneObject.locked,
    points: sceneObject.data?.points,
  };

  switch (legacySceneType) {
    case 'player':
    case 'player-home':
    case 'player-away':
    case 'player-joker':
    case 'goalkeeper':
    case 'goalkeeper-home':
    case 'goalkeeper-away':
    case 'coach':
    case 'referee':
    case 'injured-player':
    case 'ball-carrier':
    case 'numbered-player':
    case 'ball':
    case 'hoop':
    case 'zone-circle':
      raw.type = 'circle';
      raw.radius = Math.max(sceneObject.width, sceneObject.height) / 2;
      break;
    case 'cone':
      raw.type = 'triangle';
      break;
    case 'arrow-straight':
    case 'arrow-curved':
    case 'line-dashed': {
      const points = Array.isArray(sceneObject.data?.points)
        ? sceneObject.data.points.map((value) => Number(value))
        : [0, 0, sceneObject.width, 0];
      raw.type = 'line';
      raw.x1 = points[0] ?? 0;
      raw.y1 = points[1] ?? 0;
      raw.x2 = points[points.length - 2] ?? sceneObject.width;
      raw.y2 = points[points.length - 1] ?? sceneObject.height;
      raw.strokeDashArray = sceneObject.style.dash;
      break;
    }
    case 'text':
    case 'label':
      raw.type = 'text';
      raw.text = String(sceneObject.data?.label || '');
      raw.fontSize = sceneObject.style.fontSize ?? 20;
      raw.fill = sceneObject.style.textColor ?? sceneObject.style.fill ?? '#f8fafc';
      break;
    default:
      raw.type =
        sceneObject.type === 'legacy-shape'
          ? inferLegacySceneTypeFromSceneObject(sceneObject) || String(raw.type || 'rect')
          : 'rect';
      break;
  }
  if (raw.data && typeof raw.data === 'object') {
    raw.data.sceneType = raw.type;
  }
  return raw;
}

function buildSceneFromState(
  rawState: Record<string, unknown> | null | undefined,
  document: TaskEditorDocument,
  source: 'legacy' | 'konva' | 'empty'
): TaskGraphicNormalizationResult {
  const warnings = detectWarnings(rawState);
  const preservedLegacyFields = cloneUnknownFields(rawState);
  const raw = rawState || {};
  const rawMetadata = coerceRecord(raw.metadata);
  const rawPreferences = coerceRecord(rawMetadata?.preferences);
  const sceneObjects = Array.isArray(raw.sceneObjects) ? raw.sceneObjects : [];
  const objects = Array.isArray(raw.objects) ? raw.objects : [];
  const sceneRoot = sceneObjects.length
    ? ensureScene(
        {
          schemaVersion: clampNumber(raw.schemaVersion, 1, 1),
          documentId: String(raw.documentId || document.task.id),
          pitch: (raw.pitch || {}) as TacticalScene['pitch'],
          canvas: (raw.canvas || {
            width: document.graphic?.canvas_width || 1050,
            height: document.graphic?.canvas_height || 680,
            padding: 28,
          }) as TacticalScene['canvas'],
          viewport: (raw.viewport || {}) as TacticalScene['viewport'],
          layers: (raw.layers || []) as TacticalScene['layers'],
          objects: sceneObjects as TacticalScene['objects'],
          timeline: (raw.timelineState || {
            duration: 0,
            currentTime: 0,
            keyframes: [],
          }) as TacticalScene['timeline'],
          metadata: (raw.metadata || {
            title: document.task.title,
            source: 'foundation-v1',
          }) as TacticalScene['metadata'],
        },
        {
          documentId: String(document.task.id),
          title: document.task.title,
          canvasWidth: document.graphic?.canvas_width || 1050,
          canvasHeight: document.graphic?.canvas_height || 680,
        }
      )
    : null;

  const scene = sceneRoot
    ? normalizeAnimationTimeline(sceneRoot)
    : normalizeAnimationTimeline(
        ensureScene(
          {
            schemaVersion: clampNumber(raw.schemaVersion, 1, 1),
            documentId: String(raw.documentId || document.task.id),
            pitch: (raw.pitch || {}) as TacticalScene['pitch'],
            canvas: (raw.canvas || {
              width: document.graphic?.canvas_width || 1050,
              height: document.graphic?.canvas_height || 680,
              padding: 28,
            }) as TacticalScene['canvas'],
            viewport: (raw.viewport || {}) as TacticalScene['viewport'],
            layers: (raw.layers || []) as TacticalScene['layers'],
            objects: objects.map((item, index) => normalizeLegacyObject(item as TacticalCanvasObject, index)),
            timeline: {
              duration: clampNumber((raw.timeline as Record<string, unknown> | undefined)?.duration, 0, 0),
              currentTime: clampNumber((raw.timeline as Record<string, unknown> | undefined)?.currentTime, 0, 0),
              keyframes: Array.isArray((raw.timeline as Record<string, unknown> | undefined)?.keyframes)
                ? (((raw.timeline as Record<string, unknown> | undefined)?.keyframes as TacticalScene['timeline']['keyframes']) || [])
                : [],
              tracks: Array.isArray((raw.timeline as Record<string, unknown> | undefined)?.tracks)
                ? (((raw.timeline as Record<string, unknown> | undefined)?.tracks as TacticalScene['timeline']['tracks']) || [])
                : [],
              sequences: Array.isArray((raw.timeline as Record<string, unknown> | undefined)?.sequences)
                ? (((raw.timeline as Record<string, unknown> | undefined)?.sequences as TacticalScene['timeline']['sequences']) || [])
                : [],
              currentSequenceId:
                typeof (raw.timeline as Record<string, unknown> | undefined)?.currentSequenceId === 'string'
                  ? String((raw.timeline as Record<string, unknown> | undefined)?.currentSequenceId)
                  : null,
            },
            metadata: {
              title: String(rawMetadata?.title || document.task.title),
              createdAt: String(rawMetadata?.createdAt || ''),
              updatedAt: String(rawMetadata?.updatedAt || ''),
              source: 'legacy',
              preferences: {
                snapEnabled:
                  typeof rawPreferences?.snapEnabled === 'boolean' ? Boolean(rawPreferences.snapEnabled) : true,
                snapDistance: clampNumber(rawPreferences?.snapDistance, 8, 0, 80),
                gridVisible:
                  typeof rawPreferences?.gridVisible === 'boolean' ? Boolean(rawPreferences.gridVisible) : false,
                gridSize: clampNumber(rawPreferences?.gridSize, 20, 4, 100),
                showGuides: typeof rawPreferences?.showGuides === 'boolean' ? Boolean(rawPreferences.showGuides) : true,
              },
            },
          },
          {
            documentId: String(document.task.id),
            title: document.task.title,
            canvasWidth: document.graphic?.canvas_width || 1050,
            canvasHeight: document.graphic?.canvas_height || 680,
          }
        )
      );

  const normalized = attachCompatibility(scene, compatibilityBundle(source, warnings, preservedLegacyFields));
  return {
    scene: normalized,
    warnings,
    preservedLegacyFields,
    source,
  };
}

export function preserveUnknownLegacyFields(rawState: unknown): Record<string, unknown> {
  return cloneUnknownFields(coerceRecord(rawState));
}

export function validateTaskGraphicState(rawState: unknown): TaskGraphicCompatibilityWarning[] {
  return detectWarnings(coerceRecord(rawState));
}

export function legacyCanvasToKonvaScene(
  rawState: unknown,
  document: TaskEditorDocument
): TaskGraphicNormalizationResult {
  return buildSceneFromState(coerceRecord(rawState), document, coerceRecord(rawState)?.sceneObjects ? 'konva' : 'legacy');
}

export function normalizeTaskGraphicState(
  rawState: unknown,
  document: TaskEditorDocument
): TaskGraphicNormalizationResult {
  return legacyCanvasToKonvaScene(rawState, document);
}

export function konvaSceneToLegacyCanvas(scene: TacticalScene): TaskGraphicLegacyCanvasResult {
  const compatibility = (scene as SceneWithCompatibility).metadata.__taskGraphicCompatibility;
  const safeScene = normalizeAnimationTimeline(
    ensureScene(scene, {
      documentId: scene.documentId,
      title: scene.metadata.title,
      canvasWidth: scene.canvas.width,
      canvasHeight: scene.canvas.height,
    })
  );
  const baseCanvasState: TacticalCanvasState & Record<string, unknown> = {
    version: '5.3.0',
    schemaVersion: safeScene.schemaVersion,
    documentId: safeScene.documentId,
    pitch: deepClone(safeScene.pitch),
    canvas: deepClone(safeScene.canvas),
    viewport: deepClone(safeScene.viewport),
    layers: deepClone(safeScene.layers),
    sceneObjects: deepClone(safeScene.objects),
    timelineState: deepClone(safeScene.timeline),
    timeline: Array.isArray(safeScene.timeline.keyframes) ? deepClone(safeScene.timeline.keyframes) : [],
    metadata: {
      ...deepClone(safeScene.metadata),
      updatedAt: new Date().toISOString(),
    },
    objects: safeScene.objects.map((sceneObject) => sceneObjectToLegacyObject(sceneObject)),
  };

  if (compatibility?.preservedLegacyFields && Object.keys(compatibility.preservedLegacyFields).length) {
    Object.assign(baseCanvasState, deepClone(compatibility.preservedLegacyFields));
  }

  baseCanvasState.metadata = {
    ...(baseCanvasState.metadata as Record<string, unknown>),
    compatibility: {
      source: compatibility?.source || 'konva',
      warnings: compatibility?.warnings ? deepClone(compatibility.warnings) : [],
      preservedLegacyFields: compatibility?.preservedLegacyFields ? deepClone(compatibility.preservedLegacyFields) : {},
      preservedAt: compatibility?.preservedAt || new Date().toISOString(),
    },
  };

  return {
    canvasState: baseCanvasState,
    warnings: compatibility?.warnings ? deepClone(compatibility.warnings) : [],
  };
}
