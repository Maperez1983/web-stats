import { createUuid, DEFAULT_LAYERS, deepClone, sortLayers } from './sceneSchema';
import type { SceneLayer, SceneLayerId, SceneObject, TacticalScene } from './sceneSchema';

export function createDefaultLayers(): SceneLayer[] {
  return deepClone(DEFAULT_LAYERS);
}

export function getLayerById(layers: SceneLayer[], layerId: SceneLayerId): SceneLayer | undefined {
  return layers.find((layer) => layer.id === layerId);
}

export function toggleLayerVisibility(layers: SceneLayer[], layerId: SceneLayerId): SceneLayer[] {
  return sortLayers(
    layers.map((layer) => (layer.id === layerId ? { ...layer, visible: !layer.visible } : layer))
  );
}

export function toggleLayerLock(layers: SceneLayer[], layerId: SceneLayerId): SceneLayer[] {
  return sortLayers(
    layers.map((layer) => (layer.id === layerId ? { ...layer, locked: !layer.locked } : layer))
  );
}

export function moveLayer(
  layers: SceneLayer[],
  layerId: SceneLayerId,
  direction: -1 | 1
): SceneLayer[] {
  const ordered = sortLayers(layers);
  const index = ordered.findIndex((layer) => layer.id === layerId);
  if (index < 0) {
    return ordered;
  }
  const swapIndex = index + direction;
  if (swapIndex < 0 || swapIndex >= ordered.length) {
    return ordered;
  }
  const next = [...ordered];
  [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
  return next.map((layer, position) => ({
    ...layer,
    order: position * 10,
  }));
}

export function createLayer(layers: SceneLayer[], name: string): SceneLayer[] {
  const order = layers.length ? Math.max(...layers.map((layer) => layer.order)) + 10 : 0;
  return sortLayers([
    ...layers,
    {
      id: createUuid('layer') as SceneLayerId,
      name,
      visible: true,
      locked: false,
      order,
    },
  ]);
}

export function renameLayer(layers: SceneLayer[], layerId: SceneLayerId, name: string): SceneLayer[] {
  return sortLayers(
    layers.map((layer) => (layer.id === layerId ? { ...layer, name } : layer))
  );
}

export function duplicateLayer(layers: SceneLayer[], layerId: SceneLayerId): SceneLayer[] {
  const source = getLayerById(layers, layerId);
  if (!source) {
    return layers;
  }
  const order = layers.length ? Math.max(...layers.map((layer) => layer.order)) + 10 : 0;
  return sortLayers([
    ...layers,
    {
      ...deepClone(source),
      id: createUuid('layer') as SceneLayerId,
      name: `${source.name} copia`,
      order,
    },
  ]);
}

export function removeLayer(
  layers: SceneLayer[],
  layerId: SceneLayerId,
  objects: SceneObject[]
): { layers: SceneLayer[]; movedObjects: SceneObject[] } {
  const target = getLayerById(layers, layerId);
  if (!target || target.id === 'pitch') {
    return { layers, movedObjects: [] };
  }
  const fallbackLayer = getLayerById(layers, 'annotations') || getLayerById(layers, 'texts');
  const movedObjects = objects.filter((object) => object.layerId === layerId).map((object) => ({
    ...object,
    layerId: (fallbackLayer?.id || 'texts') as SceneLayerId,
  }));
  return {
    layers: sortLayers(layers.filter((layer) => layer.id !== layerId)),
    movedObjects,
  };
}

export function moveObjectsToLayer(
  scene: TacticalScene,
  objectIds: string[],
  layerId: SceneLayerId
): TacticalScene {
  return {
    ...scene,
    objects: scene.objects.map((object) =>
      objectIds.includes(object.id) ? { ...object, layerId } : object
    ),
  };
}
