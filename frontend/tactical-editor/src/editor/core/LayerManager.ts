import { DEFAULT_LAYERS, deepClone, sortLayers } from './sceneSchema';
import type { SceneLayer, SceneLayerId } from './sceneSchema';

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
