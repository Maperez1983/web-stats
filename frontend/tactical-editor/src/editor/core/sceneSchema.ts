import { resolveAssetId } from '../assets/assetRegistry';

export const SCENE_SCHEMA_VERSION = 1;
export const HISTORY_LIMIT = 60;

export type PitchType = 'full' | 'half' | 'attacking-third' | 'custom';
export type PitchOrientation = 'landscape' | 'portrait';
export type SceneLayerId =
  | 'pitch'
  | 'zones'
  | 'paths'
  | 'equipment'
  | 'players'
  | 'ball'
  | 'texts'
  | 'annotations';
export type SceneObjectType =
  | 'player'
  | 'goalkeeper'
  | 'player-home'
  | 'player-away'
  | 'player-joker'
  | 'goalkeeper-home'
  | 'goalkeeper-away'
  | 'coach'
  | 'referee'
  | 'injured-player'
  | 'ball-carrier'
  | 'numbered-player'
  | 'ball'
  | 'cone'
  | 'high-cone'
  | 'pole'
  | 'goal'
  | 'hoop'
  | 'mini-goal'
  | 'bench'
  | 'marker'
  | 'flag'
  | 'mannequin'
  | 'bib'
  | 'arrow-straight'
  | 'arrow-curved'
  | 'arrow-segmented'
  | 'arrow-double'
  | 'arrow-pass'
  | 'arrow-run'
  | 'trajectory'
  | 'line'
  | 'line-dashed'
  | 'zone-rect'
  | 'zone-circle'
  | 'zone-ellipse'
  | 'zone-polygon'
  | 'zone-free'
  | 'lane'
  | 'stripe-h'
  | 'stripe-v'
  | 'sector'
  | 'text'
  | 'label'
  | 'legacy-shape';

export type SceneLayer = {
  id: SceneLayerId;
  name: string;
  visible: boolean;
  locked: boolean;
  order: number;
};

export type SceneObjectStyle = {
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  opacity?: number;
  dash?: number[];
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: string | number;
  textColor?: string;
};

export type SceneObjectData = Record<string, unknown> & {
  assetId?: string;
  label?: string;
  team?: 'home' | 'away' | 'neutral' | 'joker';
  number?: string;
  name?: string;
  points?: number[];
  groupId?: string;
  groupLabel?: string;
  role?: string;
  variant?: string;
  orientation?: string;
  legacySource?: Record<string, unknown>;
};

export type SceneTimelineKeyframe = {
  id: string;
  time: number;
  label?: string;
  objectIds: string[];
  objects: Array<
    Pick<
      SceneObject,
      'id' | 'type' | 'layerId' | 'x' | 'y' | 'width' | 'height' | 'rotation' | 'scaleX' | 'scaleY'
    > & {
      style: SceneObjectStyle;
      data: SceneObjectData;
      visible: boolean;
      locked: boolean;
      zIndex: number;
    }
  >;
};

export type EditorPreferences = {
  snapEnabled: boolean;
  snapDistance: number;
  gridVisible: boolean;
  gridSize: number;
  showGuides: boolean;
};

export type SceneObject = {
  id: string;
  type: SceneObjectType;
  layerId: SceneLayerId;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  scaleX: number;
  scaleY: number;
  visible: boolean;
  locked: boolean;
  zIndex: number;
  style: SceneObjectStyle;
  data: SceneObjectData;
};

export type TacticalScene = {
  schemaVersion: number;
  documentId: string;
  pitch: {
    type: PitchType;
    orientation: PitchOrientation;
    surface: 'grass' | 'artificial' | 'futsal';
    width: number;
    height: number;
  };
  canvas: {
    width: number;
    height: number;
    padding: number;
  };
  viewport: {
    zoom: number;
    x: number;
    y: number;
  };
  layers: SceneLayer[];
  objects: SceneObject[];
  timeline: {
    duration: number;
    currentTime: number;
    keyframes: SceneTimelineKeyframe[];
  };
  metadata: {
    title: string;
    createdAt: string;
    updatedAt: string;
    source: 'legacy' | 'foundation-v1';
    preferences: EditorPreferences;
  };
};

export const DEFAULT_EDITOR_PREFERENCES: EditorPreferences = {
  snapEnabled: true,
  snapDistance: 8,
  gridVisible: false,
  gridSize: 20,
  showGuides: true,
};

export const DEFAULT_LAYERS: SceneLayer[] = [
  { id: 'pitch', name: 'Campo', visible: true, locked: true, order: 0 },
  { id: 'zones', name: 'Zonas', visible: true, locked: false, order: 10 },
  { id: 'paths', name: 'Flechas y recorridos', visible: true, locked: false, order: 20 },
  { id: 'equipment', name: 'Material', visible: true, locked: false, order: 30 },
  { id: 'players', name: 'Jugadores', visible: true, locked: false, order: 40 },
  { id: 'ball', name: 'Balón', visible: true, locked: false, order: 50 },
  { id: 'texts', name: 'Textos', visible: true, locked: false, order: 60 },
  { id: 'annotations', name: 'Anotaciones', visible: true, locked: false, order: 70 },
];

export function deepClone<T>(value: T): T {
  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

export function clampNumber(value: unknown, fallback: number, min?: number, max?: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  if (typeof min === 'number' && parsed < min) {
    return min;
  }
  if (typeof max === 'number' && parsed > max) {
    return max;
  }
  return parsed;
}

export function createUuid(prefix = 'obj'): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Math.random().toString(16).slice(2, 10)}-${Date.now().toString(16)}`;
}

export function createDefaultScene(
  documentId: string,
  title: string,
  canvasWidth = 1050,
  canvasHeight = 680
): TacticalScene {
  const now = new Date().toISOString();
  return {
    schemaVersion: SCENE_SCHEMA_VERSION,
    documentId,
    pitch: {
      type: 'full',
      orientation: 'landscape',
      surface: 'grass',
      width: 105,
      height: 68,
    },
    canvas: {
      width: canvasWidth,
      height: canvasHeight,
      padding: 28,
    },
    viewport: {
      zoom: 1,
      x: 0,
      y: 0,
    },
    layers: deepClone(DEFAULT_LAYERS),
    objects: [],
    timeline: {
      duration: 0,
      currentTime: 0,
      keyframes: [],
    },
    metadata: {
      title,
      createdAt: now,
      updatedAt: now,
      source: 'foundation-v1',
      preferences: deepClone(DEFAULT_EDITOR_PREFERENCES),
    },
  };
}

export function normalizeLayerId(value: unknown): SceneLayerId {
  const raw = String(value || '').trim();
  if (
    raw === 'zones' ||
    raw === 'paths' ||
    raw === 'equipment' ||
    raw === 'players' ||
    raw === 'ball' ||
    raw === 'texts' ||
    raw === 'annotations' ||
    raw === 'pitch'
  ) {
    return raw;
  }
  return 'players';
}

export function sortLayers(layers: SceneLayer[]): SceneLayer[] {
  return [...layers].sort((a, b) => a.order - b.order);
}

export function ensureScene(
  input: Partial<TacticalScene> | null | undefined,
  options?: { documentId?: string; title?: string; canvasWidth?: number; canvasHeight?: number }
): TacticalScene {
  const base = createDefaultScene(
    String(options?.documentId || input?.documentId || ''),
    String(options?.title || input?.metadata?.title || ''),
    clampNumber(options?.canvasWidth || input?.canvas?.width, 1050, 320, 4000),
    clampNumber(options?.canvasHeight || input?.canvas?.height, 680, 240, 4000)
  );
  if (!input || typeof input !== 'object') {
    return base;
  }
  const safeLayers = Array.isArray(input.layers) ? input.layers : base.layers;
  const safeObjects = Array.isArray(input.objects) ? input.objects : [];
  return {
    schemaVersion: clampNumber(input.schemaVersion, SCENE_SCHEMA_VERSION, 1),
    documentId: String(input.documentId || base.documentId),
    pitch: {
      type: ['full', 'half', 'attacking-third', 'custom'].includes(String(input.pitch?.type))
        ? (input.pitch?.type as PitchType)
        : base.pitch.type,
      orientation: input.pitch?.orientation === 'portrait' ? 'portrait' : 'landscape',
      surface:
        input.pitch?.surface === 'artificial' || input.pitch?.surface === 'futsal'
          ? input.pitch.surface
          : 'grass',
      width: clampNumber(input.pitch?.width, base.pitch.width, 10, 150),
      height: clampNumber(input.pitch?.height, base.pitch.height, 10, 100),
    },
    canvas: {
      width: clampNumber(input.canvas?.width, base.canvas.width, 320, 4000),
      height: clampNumber(input.canvas?.height, base.canvas.height, 240, 4000),
      padding: clampNumber(input.canvas?.padding, base.canvas.padding, 0, 160),
    },
    viewport: {
      zoom: clampNumber(input.viewport?.zoom, base.viewport.zoom, 0.2, 6),
      x: clampNumber(input.viewport?.x, base.viewport.x),
      y: clampNumber(input.viewport?.y, base.viewport.y),
    },
    layers: sortLayers(
      safeLayers.map((layer, index) => ({
        id: normalizeLayerId(layer.id),
        name: String(layer.name || DEFAULT_LAYERS[index]?.name || layer.id || 'Capa'),
        visible: layer.visible !== false,
        locked: Boolean(layer.locked),
        order: clampNumber(layer.order, DEFAULT_LAYERS[index]?.order ?? index * 10),
      }))
    ),
    objects: safeObjects.map((object, index) => ({
      id: String(object.id || createUuid('legacy')),
      type: String(object.type || 'legacy-shape') as SceneObjectType,
      layerId: normalizeLayerId(object.layerId),
      x: clampNumber(object.x, 0),
      y: clampNumber(object.y, 0),
      width: clampNumber(object.width, 42, 4),
      height: clampNumber(object.height, 42, 4),
      rotation: clampNumber(object.rotation, 0),
      scaleX: clampNumber(object.scaleX, 1, 0.05, 20),
      scaleY: clampNumber(object.scaleY, 1, 0.05, 20),
      visible: object.visible !== false,
      locked: Boolean(object.locked),
      zIndex: clampNumber(object.zIndex, index),
      style:
        typeof object.style === 'object' && object.style
          ? { ...(object.style as SceneObjectStyle) }
          : {},
      data: (() => {
        const data =
          typeof object.data === 'object' && object.data
            ? ({ ...(object.data as SceneObjectData) } as SceneObjectData)
            : ({} as SceneObjectData);
        const type = String(object.type || 'legacy-shape') as SceneObjectType;
        const resolvedAssetId = resolveAssetId(data.assetId, type, data.variant);
        return {
          ...data,
          assetId: resolvedAssetId,
          orientation: typeof data.orientation === 'string' ? data.orientation : undefined,
        };
      })(),
    })),
    timeline: {
      duration: clampNumber(input.timeline?.duration, 0, 0),
      currentTime: clampNumber(input.timeline?.currentTime, 0, 0),
      keyframes: Array.isArray(input.timeline?.keyframes) ? input.timeline?.keyframes : [],
    },
    metadata: {
      title: String(input.metadata?.title || base.metadata.title),
      createdAt: String(input.metadata?.createdAt || base.metadata.createdAt),
      updatedAt: String(input.metadata?.updatedAt || base.metadata.updatedAt),
      source: input.metadata?.source === 'legacy' ? 'legacy' : 'foundation-v1',
      preferences: {
        snapEnabled:
          typeof input.metadata?.preferences?.snapEnabled === 'boolean'
            ? input.metadata?.preferences?.snapEnabled
            : base.metadata.preferences.snapEnabled,
        snapDistance: clampNumber(
          input.metadata?.preferences?.snapDistance,
          base.metadata.preferences.snapDistance,
          0,
          80
        ),
        gridVisible:
          typeof input.metadata?.preferences?.gridVisible === 'boolean'
            ? input.metadata?.preferences?.gridVisible
            : base.metadata.preferences.gridVisible,
        gridSize: clampNumber(
          input.metadata?.preferences?.gridSize,
          base.metadata.preferences.gridSize,
          4,
          100
        ),
        showGuides:
          typeof input.metadata?.preferences?.showGuides === 'boolean'
            ? input.metadata?.preferences?.showGuides
            : base.metadata.preferences.showGuides,
      },
    },
  };
}
