export const SCENE_SCHEMA_VERSION = 1;
export const HISTORY_LIMIT = 60;

export type PitchType = 'full' | 'half' | 'attacking-third' | 'custom';
export type PitchOrientation = 'landscape' | 'portrait';
export type SceneLayerId = 'pitch' | 'zones' | 'paths' | 'equipment' | 'players' | 'texts';
export type SceneObjectType =
  | 'player'
  | 'goalkeeper'
  | 'ball'
  | 'cone'
  | 'pole'
  | 'hoop'
  | 'mini-goal'
  | 'arrow-straight'
  | 'arrow-curved'
  | 'line-dashed'
  | 'zone-rect'
  | 'zone-circle'
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
  label?: string;
  team?: 'home' | 'away' | 'neutral' | 'joker';
  number?: string;
  name?: string;
  points?: number[];
  legacySource?: Record<string, unknown>;
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
    keyframes: Array<Record<string, unknown>>;
  };
  metadata: {
    title: string;
    createdAt: string;
    updatedAt: string;
    source: 'legacy' | 'foundation-v1';
  };
};

export const DEFAULT_LAYERS: SceneLayer[] = [
  { id: 'pitch', name: 'Campo', visible: true, locked: true, order: 0 },
  { id: 'zones', name: 'Zonas', visible: true, locked: false, order: 10 },
  { id: 'paths', name: 'Flechas y recorridos', visible: true, locked: false, order: 20 },
  { id: 'equipment', name: 'Material', visible: true, locked: false, order: 30 },
  { id: 'players', name: 'Jugadores y balón', visible: true, locked: false, order: 40 },
  { id: 'texts', name: 'Textos', visible: true, locked: false, order: 50 },
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
    raw === 'texts' ||
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
      data:
        typeof object.data === 'object' && object.data
          ? { ...(object.data as SceneObjectData) }
          : {},
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
    },
  };
}
