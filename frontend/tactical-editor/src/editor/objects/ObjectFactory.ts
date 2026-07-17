import { resolveAssetDefinition } from '../assets/assetRegistry';
import { createUuid } from '../core/sceneSchema';
import type { SceneLayerId, SceneObject, SceneObjectType } from '../core/sceneSchema';

type CreateObjectOptions = {
  x?: number;
  y?: number;
  zIndex?: number;
  assetId?: string;
  assetVariant?: string;
  orientation?: string;
};

function applyAssetDefaults(
  type: SceneObjectType,
  base: Partial<SceneObject>,
  options: CreateObjectOptions
): Partial<SceneObject> {
  const asset = resolveAssetDefinition(
    options.assetId || (base.data?.assetId as string | undefined),
    type,
    options.assetVariant || (base.data?.variant as string | undefined)
  );
  return {
    ...base,
    layerId: (base.layerId || asset.layerId) as SceneLayerId,
    width: Number(base.width ?? asset.defaultSize.width),
    height: Number(base.height ?? asset.defaultSize.height),
    style: { ...asset.defaultStyle, ...(base.style || {}) },
    data: {
      ...asset.defaultData,
      ...(base.data || {}),
      assetId: asset.assetId,
      variant:
        options.assetVariant || (base.data?.variant as string | undefined) || asset.defaultData.variant,
      orientation:
        options.orientation || (base.data?.orientation as string | undefined) || asset.defaultData.orientation,
    },
  };
}

function centeredObject(
  base: Partial<SceneObject>,
  options: CreateObjectOptions = {}
): SceneObject {
  const resolved = applyAssetDefaults(String(base.type || 'legacy-shape') as SceneObjectType, base, options);
  return {
    id: String(resolved.id || createUuid('obj')),
    type: (resolved.type || 'legacy-shape') as SceneObjectType,
    layerId: (resolved.layerId || 'players') as SceneLayerId,
    x: Number(resolved.x ?? options.x ?? 420),
    y: Number(resolved.y ?? options.y ?? 240),
    width: Number(resolved.width ?? 42),
    height: Number(resolved.height ?? 42),
    rotation: Number(resolved.rotation ?? 0),
    scaleX: Number(resolved.scaleX ?? 1),
    scaleY: Number(resolved.scaleY ?? 1),
    visible: resolved.visible !== false,
    locked: Boolean(resolved.locked),
    zIndex: Number(resolved.zIndex ?? options.zIndex ?? 0),
    style: { ...(resolved.style || {}) },
    data: { ...(resolved.data || {}) },
  };
}

export function defaultLayerForObject(type: SceneObjectType): SceneLayerId {
  if (
    type === 'zone-rect' ||
    type === 'zone-circle' ||
    type === 'zone-ellipse' ||
    type === 'zone-polygon' ||
    type === 'zone-free' ||
    type === 'lane' ||
    type === 'stripe-h' ||
    type === 'stripe-v' ||
    type === 'sector'
  ) {
    return 'zones';
  }
  if (
    type === 'arrow-straight' ||
    type === 'arrow-curved' ||
    type === 'arrow-segmented' ||
    type === 'arrow-double' ||
    type === 'arrow-pass' ||
    type === 'arrow-run' ||
    type === 'trajectory' ||
    type === 'line-dashed' ||
    type === 'line'
  ) {
    return 'paths';
  }
  if (type === 'ball') return 'ball';
  if (type === 'text' || type === 'label') return 'texts';
  if (
    type === 'player' ||
    type === 'goalkeeper' ||
    type === 'player-home' ||
    type === 'player-away' ||
    type === 'player-joker' ||
    type === 'goalkeeper-home' ||
    type === 'goalkeeper-away' ||
    type === 'coach' ||
    type === 'referee' ||
    type === 'injured-player' ||
    type === 'ball-carrier' ||
    type === 'numbered-player'
  ) {
    return 'players';
  }
  if (type === 'goal') return 'equipment';
  return 'equipment';
}

function playerObject(
  type: SceneObjectType,
  layerId: SceneLayerId,
  fill: string,
  stroke: string,
  options: CreateObjectOptions,
  extraData: Record<string, unknown> = {}
): SceneObject {
  return centeredObject(
    {
      type,
      layerId,
      width: 42,
      height: 42,
      style: {
        fill,
        stroke,
        strokeWidth: 3,
        textColor: '#ffffff',
        fontSize: 15,
      },
      data: { team: 'home', number: '8', name: '', label: 'J', ...extraData },
    },
    options
  );
}

export function createObject(
  type: SceneObjectType,
  options: CreateObjectOptions = {}
): SceneObject {
  const layerId = defaultLayerForObject(type);
  switch (type) {
    case 'player':
    case 'player-home':
      return playerObject(type, layerId, '#2563eb', '#eff6ff', options, { team: 'home' });
    case 'player-away':
      return playerObject(type, layerId, '#f97316', '#ffedd5', options, { team: 'away' });
    case 'player-joker':
      return playerObject(type, layerId, '#a855f7', '#f3e8ff', options, { team: 'joker' });
    case 'goalkeeper':
    case 'goalkeeper-home':
      return playerObject(type, layerId, '#16a34a', '#ecfccb', options, {
        team: 'home',
        number: '1',
        role: 'goalkeeper',
      });
    case 'goalkeeper-away':
      return playerObject(type, layerId, '#f59e0b', '#fef3c7', options, {
        team: 'away',
        number: '13',
        role: 'goalkeeper',
      });
    case 'coach':
      return playerObject(type, layerId, '#0f172a', '#cbd5e1', options, {
        role: 'coach',
        number: 'C',
      });
    case 'referee':
      return playerObject(type, layerId, '#111827', '#f8fafc', options, {
        role: 'referee',
        number: 'R',
      });
    case 'injured-player':
      return playerObject(type, layerId, '#ef4444', '#fee2e2', options, {
        role: 'injured-player',
        number: '!',
      });
    case 'ball-carrier':
      return playerObject(type, layerId, '#0ea5e9', '#e0f2fe', options, {
        role: 'ball-carrier',
        number: '9',
      });
    case 'numbered-player':
      return playerObject(type, layerId, '#1d4ed8', '#dbeafe', options, {
        role: 'numbered-player',
        number: '10',
      });
    case 'ball':
      return centeredObject(
        {
          type,
          layerId,
          width: 18,
          height: 18,
          style: { fill: '#ffffff', stroke: '#0f172a', strokeWidth: 2 },
          data: { variant: 'ball' },
        },
        options
      );
    case 'cone':
    case 'high-cone':
      return centeredObject(
        {
          type,
          layerId,
          width: type === 'high-cone' ? 24 : 26,
          height: type === 'high-cone' ? 42 : 30,
          style: { fill: '#f97316', stroke: '#7c2d12', strokeWidth: 2 },
        },
        options
      );
    case 'pole':
      return centeredObject(
        {
          type,
          layerId,
          width: 10,
          height: 44,
          style: { fill: '#fbbf24', stroke: '#78350f', strokeWidth: 2 },
        },
        options
      );
    case 'goal':
      return centeredObject(
        {
          type,
          layerId,
          width: 80,
          height: 34,
          style: { fill: 'rgba(255,255,255,0.04)', stroke: '#f8fafc', strokeWidth: 2 },
          data: { role: 'goal' },
        },
        options
      );
    case 'hoop':
      return centeredObject(
        {
          type,
          layerId,
          width: 28,
          height: 28,
          style: { fill: 'rgba(0,0,0,0)', stroke: '#facc15', strokeWidth: 4 },
        },
        options
      );
    case 'bench':
      return centeredObject(
        {
          type,
          layerId,
          width: 96,
          height: 28,
          style: { fill: 'rgba(15,23,42,0.55)', stroke: '#94a3b8', strokeWidth: 2 },
          data: { role: 'bench' },
        },
        options
      );
    case 'marker':
      return centeredObject(
        {
          type,
          layerId,
          width: 18,
          height: 18,
          style: { fill: '#f59e0b', stroke: '#78350f', strokeWidth: 2 },
          data: { role: 'marker' },
        },
        options
      );
    case 'flag':
      return centeredObject(
        {
          type,
          layerId,
          width: 22,
          height: 54,
          style: { fill: '#f8fafc', stroke: '#0f172a', strokeWidth: 2 },
          data: { role: 'flag' },
        },
        options
      );
    case 'mannequin':
      return centeredObject(
        {
          type,
          layerId,
          width: 24,
          height: 72,
          style: { fill: 'rgba(255,255,255,0.08)', stroke: '#cbd5e1', strokeWidth: 2 },
          data: { role: 'mannequin' },
        },
        options
      );
    case 'bib':
      return centeredObject(
        {
          type,
          layerId,
          width: 34,
          height: 40,
          style: { fill: '#22c55e', stroke: '#14532d', strokeWidth: 2 },
          data: { role: 'bib' },
        },
        options
      );
    case 'mini-goal':
      return centeredObject(
        {
          type,
          layerId,
          width: 54,
          height: 24,
          style: { fill: 'rgba(255,255,255,0.04)', stroke: '#e2e8f0', strokeWidth: 2 },
        },
        options
      );
    case 'arrow-straight':
    case 'arrow-pass':
    case 'arrow-run':
      return centeredObject(
        {
          type,
          layerId,
          width: 120,
          height: 24,
          style: { stroke: '#38bdf8', strokeWidth: 4, fill: '#38bdf8' },
          data: { points: [0, 12, 120, 12] },
        },
        options
      );
    case 'arrow-curved':
    case 'trajectory':
      return centeredObject(
        {
          type,
          layerId,
          width: 150,
          height: 80,
          style: { stroke: '#22c55e', strokeWidth: 4, fill: '#22c55e' },
          data: { points: [0, 60, 60, 0, 150, 36] },
        },
        options
      );
    case 'arrow-segmented':
    case 'arrow-double':
      return centeredObject(
        {
          type,
          layerId,
          width: 150,
          height: 30,
          style: { stroke: '#38bdf8', strokeWidth: 4, fill: '#38bdf8' },
          data: { points: [0, 15, 40, 15, 80, 6, 150, 15] },
        },
        options
      );
    case 'line-dashed':
    case 'line':
      return centeredObject(
        {
          type,
          layerId,
          width: 140,
          height: 18,
          style: { stroke: '#f8fafc', strokeWidth: 3, dash: [12, 8] },
          data: { points: [0, 9, 140, 9] },
        },
        options
      );
    case 'zone-rect':
    case 'lane':
    case 'stripe-h':
    case 'stripe-v':
      return centeredObject(
        {
          type,
          layerId,
          width: type === 'lane' ? 120 : 180,
          height: type === 'stripe-v' ? 180 : 110,
          style: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 },
          data: {
            variant: type,
          },
        },
        options
      );
    case 'zone-circle':
    case 'zone-ellipse':
      return centeredObject(
        {
          type,
          layerId,
          width: type === 'zone-ellipse' ? 140 : 110,
          height: type === 'zone-ellipse' ? 90 : 110,
          style: { fill: 'rgba(59,130,246,0.16)', stroke: '#60a5fa', strokeWidth: 2 },
          data: { variant: type },
        },
        options
      );
    case 'zone-polygon':
    case 'zone-free':
    case 'sector':
      return centeredObject(
        {
          type,
          layerId,
          width: 160,
          height: 120,
          style: { fill: 'rgba(59,130,246,0.14)', stroke: '#60a5fa', strokeWidth: 2 },
          data: {
            variant: type,
            points:
              type === 'sector'
                ? [0, 120, 40, 24, 120, 0, 160, 24, 160, 120]
                : [0, 80, 40, 20, 80, 0, 120, 20, 160, 80, 120, 120, 40, 120],
          },
        },
        options
      );
    case 'text':
      return centeredObject(
        {
          type,
          layerId,
          width: 180,
          height: 40,
          style: { textColor: '#f8fafc', fontSize: 24, fontWeight: 700 },
          data: { label: 'Texto táctico' },
        },
        options
      );
    case 'label':
      return centeredObject(
        {
          type,
          layerId,
          width: 32,
          height: 32,
          style: {
            fill: '#0f172a',
            stroke: '#e2e8f0',
            strokeWidth: 2,
            textColor: '#f8fafc',
            fontSize: 16,
          },
          data: { label: '1' },
        },
        options
      );
    default:
      return centeredObject(
        {
          type: 'legacy-shape',
          layerId,
          width: 60,
          height: 40,
          style: { fill: 'rgba(255,255,255,0.1)', stroke: '#e2e8f0', strokeWidth: 2 },
        },
        options
      );
  }
}

export function createAssetObject(
  assetId: string,
  options: CreateObjectOptions = {}
): SceneObject {
  const asset = resolveAssetDefinition(assetId, 'legacy-shape');
  return createObject(asset.type, {
    ...options,
    assetId: asset.assetId,
    assetVariant: options.assetVariant || (asset.defaultData.variant as string | undefined),
    orientation: options.orientation || (asset.defaultData.orientation as string | undefined),
  });
}
