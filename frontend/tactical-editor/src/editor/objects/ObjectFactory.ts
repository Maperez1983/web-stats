import { createUuid } from '../core/sceneSchema';
import type { SceneLayerId, SceneObject, SceneObjectType } from '../core/sceneSchema';

type CreateObjectOptions = {
  x?: number;
  y?: number;
  zIndex?: number;
};

function centeredObject(
  base: Partial<SceneObject>,
  options: CreateObjectOptions = {}
): SceneObject {
  return {
    id: String(base.id || createUuid('obj')),
    type: base.type || 'legacy-shape',
    layerId: (base.layerId || 'players') as SceneLayerId,
    x: Number(base.x ?? options.x ?? 420),
    y: Number(base.y ?? options.y ?? 240),
    width: Number(base.width ?? 42),
    height: Number(base.height ?? 42),
    rotation: Number(base.rotation ?? 0),
    scaleX: Number(base.scaleX ?? 1),
    scaleY: Number(base.scaleY ?? 1),
    visible: base.visible !== false,
    locked: Boolean(base.locked),
    zIndex: Number(base.zIndex ?? options.zIndex ?? 0),
    style: { ...(base.style || {}) },
    data: { ...(base.data || {}) },
  };
}

export function defaultLayerForObject(type: SceneObjectType): SceneLayerId {
  if (type === 'zone-rect' || type === 'zone-circle') return 'zones';
  if (type === 'arrow-straight' || type === 'arrow-curved' || type === 'line-dashed')
    return 'paths';
  if (type === 'text' || type === 'label') return 'texts';
  if (type === 'player' || type === 'goalkeeper' || type === 'ball') return 'players';
  return 'equipment';
}

export function createObject(
  type: SceneObjectType,
  options: CreateObjectOptions = {}
): SceneObject {
  const layerId = defaultLayerForObject(type);
  switch (type) {
    case 'player':
      return centeredObject(
        {
          type,
          layerId,
          width: 42,
          height: 42,
          style: {
            fill: '#2563eb',
            stroke: '#eff6ff',
            strokeWidth: 3,
            textColor: '#ffffff',
            fontSize: 15,
          },
          data: { team: 'home', number: '8', name: '', label: 'J' },
        },
        options
      );
    case 'goalkeeper':
      return centeredObject(
        {
          type,
          layerId,
          width: 44,
          height: 44,
          style: {
            fill: '#16a34a',
            stroke: '#ecfccb',
            strokeWidth: 3,
            textColor: '#ffffff',
            fontSize: 15,
          },
          data: { team: 'home', number: '1', name: '', role: 'goalkeeper' },
        },
        options
      );
    case 'ball':
      return centeredObject(
        {
          type,
          layerId,
          width: 18,
          height: 18,
          style: { fill: '#ffffff', stroke: '#0f172a', strokeWidth: 2 },
        },
        options
      );
    case 'cone':
      return centeredObject(
        {
          type,
          layerId,
          width: 26,
          height: 30,
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
    case 'line-dashed':
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
      return centeredObject(
        {
          type,
          layerId,
          width: 180,
          height: 110,
          style: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 },
        },
        options
      );
    case 'zone-circle':
      return centeredObject(
        {
          type,
          layerId,
          width: 110,
          height: 110,
          style: { fill: 'rgba(59,130,246,0.16)', stroke: '#60a5fa', strokeWidth: 2 },
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
