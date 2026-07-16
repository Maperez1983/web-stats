import {
  clampNumber,
  createDefaultScene,
  createUuid,
  deepClone,
  ensureScene,
  normalizeLayerId,
} from '../core/sceneSchema';
import type {
  SceneLayerId,
  SceneObject,
  SceneObjectType,
  TacticalScene,
} from '../core/sceneSchema';
import type {
  TacticalCanvasObject,
  TacticalCanvasState,
  TaskEditorDocument,
} from '../../domain/taskDocument';

function inferSceneType(rawObject: TacticalCanvasObject): SceneObjectType {
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
  if (type === 'arrow-straight' || type === 'arrow-curved' || type === 'line-dashed')
    return 'paths';
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
      label:
        typeof rawObject.text === 'string'
          ? rawObject.text
          : typeof rawObject.data?.label === 'string'
            ? rawObject.data.label
            : undefined,
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

export function createSceneFromDocument(document: TaskEditorDocument): TacticalScene {
  const rawState = (document.graphic?.canvas_state || {}) as TacticalCanvasState &
    Record<string, unknown>;
  const sceneRoot =
    typeof rawState === 'object' &&
    rawState &&
    Array.isArray((rawState as Record<string, unknown>).sceneObjects)
      ? ensureScene(
          {
            schemaVersion: clampNumber((rawState as Record<string, unknown>).schemaVersion, 1, 1),
            documentId: String(
              (rawState as Record<string, unknown>).documentId || document.task.id
            ),
            pitch: ((rawState as Record<string, unknown>).pitch || {}) as TacticalScene['pitch'],
            canvas: ((rawState as Record<string, unknown>).canvas || {
              width: document.graphic?.canvas_width || 1050,
              height: document.graphic?.canvas_height || 680,
              padding: 28,
            }) as TacticalScene['canvas'],
            viewport: ((rawState as Record<string, unknown>).viewport ||
              {}) as TacticalScene['viewport'],
            layers: ((rawState as Record<string, unknown>).layers || []) as TacticalScene['layers'],
            objects: ((rawState as Record<string, unknown>).sceneObjects ||
              []) as TacticalScene['objects'],
            timeline: ((rawState as Record<string, unknown>).timelineState || {
              duration: 0,
              currentTime: 0,
              keyframes: [],
            }) as TacticalScene['timeline'],
            metadata: ((rawState as Record<string, unknown>).metadata || {
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

  if (sceneRoot) {
    return sceneRoot;
  }

  const base = createDefaultScene(
    String(document.task.id),
    document.task.title,
    clampNumber(document.graphic?.canvas_width, 1050, 320, 4000),
    clampNumber(document.graphic?.canvas_height, 680, 240, 4000)
  );
  const rawObjects = Array.isArray(rawState?.objects) ? rawState.objects : [];
  const timeline = Array.isArray(rawState?.timeline) ? rawState.timeline : [];
  return {
    ...base,
    objects: rawObjects.map((item, index) => normalizeLegacyObject(item, index)),
    timeline: {
      duration: timeline.length,
      currentTime: 0,
      keyframes: timeline,
    },
    metadata: {
      ...base.metadata,
      source: 'legacy',
    },
  };
}

function sceneObjectToLegacyObject(sceneObject: SceneObject): TacticalCanvasObject {
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
    sceneType: sceneObject.type,
    locked: sceneObject.locked,
    points: sceneObject.data?.points,
  };

  switch (sceneObject.type) {
    case 'player':
    case 'goalkeeper':
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
      raw.y2 = points[points.length - 1] ?? 0;
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
      raw.type = sceneObject.type === 'legacy-shape' ? String(raw.type || 'rect') : 'rect';
      break;
  }
  return raw;
}

export function sceneToLegacyCanvasState(
  scene: TacticalScene
): TacticalCanvasState & Record<string, unknown> {
  const safeScene = ensureScene(scene, {
    documentId: scene.documentId,
    title: scene.metadata.title,
    canvasWidth: scene.canvas.width,
    canvasHeight: scene.canvas.height,
  });
  return {
    version: '5.3.0',
    schemaVersion: safeScene.schemaVersion,
    documentId: safeScene.documentId,
    pitch: deepClone(safeScene.pitch),
    canvas: deepClone(safeScene.canvas),
    viewport: deepClone(safeScene.viewport),
    layers: deepClone(safeScene.layers),
    sceneObjects: deepClone(safeScene.objects),
    timelineState: deepClone(safeScene.timeline),
    timeline: Array.isArray(safeScene.timeline.keyframes)
      ? deepClone(safeScene.timeline.keyframes)
      : [],
    metadata: {
      ...deepClone(safeScene.metadata),
      updatedAt: new Date().toISOString(),
    },
    objects: safeScene.objects.map((sceneObject) => sceneObjectToLegacyObject(sceneObject)),
  };
}

export function parseImportedScene(raw: string, document: TaskEditorDocument): TacticalScene {
  const parsed = JSON.parse(raw) as Partial<TacticalScene> | Record<string, unknown>;
  if (
    parsed &&
    typeof parsed === 'object' &&
    Array.isArray((parsed as Record<string, unknown>).sceneObjects)
  ) {
    return createSceneFromDocument({
      ...document,
      graphic: {
        ...document.graphic,
        canvas_state: parsed as TacticalCanvasState,
      },
    });
  }
  return ensureScene(parsed as Partial<TacticalScene>, {
    documentId: String(document.task.id),
    title: document.task.title,
    canvasWidth: document.graphic?.canvas_width || 1050,
    canvasHeight: document.graphic?.canvas_height || 680,
  });
}
