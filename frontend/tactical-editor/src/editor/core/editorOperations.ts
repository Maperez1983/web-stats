import { getPitchRect } from '../pitch/pitchGeometry';
import { createUuid, deepClone, type EditorPreferences, type SceneLayer, type SceneObject, type SceneObjectType, type TacticalScene, type SceneTimelineKeyframe } from './sceneSchema';

type ObjectRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type SnapGuide = {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type SnapResult = {
  x: number;
  y: number;
  guides: SnapGuide[];
};

type AlignMode = 'left' | 'center-x' | 'right' | 'top' | 'center-y' | 'bottom';
type DistributeMode = 'horizontal' | 'vertical';
type OrderMode = 'front' | 'forward' | 'backward' | 'back';

function layerById(scene: TacticalScene, id: string): SceneLayer | undefined {
  return scene.layers.find((layer) => layer.id === id);
}

export function getLayerOrder(scene: TacticalScene, layerId: string): number {
  return layerById(scene, layerId)?.order ?? 0;
}

export function isSelectableObject(scene: TacticalScene, object: SceneObject): boolean {
  if (!object.visible || object.locked || object.layerId === 'pitch') {
    return false;
  }
  const layer = layerById(scene, object.layerId);
  return Boolean(layer?.visible !== false && !layer?.locked);
}

export function selectableObjects(scene: TacticalScene): SceneObject[] {
  return scene.objects.filter((object) => isSelectableObject(scene, object));
}

export function expandSelectionByGroups(scene: TacticalScene, ids: string[]): string[] {
  const selected = new Set(ids);
  const groups = new Set(
    scene.objects
      .filter((object) => selected.has(object.id) && typeof object.data.groupId === 'string')
      .map((object) => String(object.data.groupId))
  );
  if (!groups.size) {
    return [...selected];
  }
  scene.objects.forEach((object) => {
    if (object.data.groupId && groups.has(String(object.data.groupId))) {
      selected.add(object.id);
    }
  });
  return [...selected];
}

export function selectAllIds(scene: TacticalScene): string[] {
  return selectableObjects(scene).map((object) => object.id);
}

export function invertSelection(scene: TacticalScene, selectedIds: string[]): string[] {
  const selected = new Set(selectedIds);
  return selectableObjects(scene)
    .map((object) => object.id)
    .filter((id) => !selected.has(id));
}

export function selectByType(scene: TacticalScene, type: SceneObjectType): string[] {
  return selectableObjects(scene)
    .filter((object) => object.type === type)
    .map((object) => object.id);
}

export function selectByLayer(scene: TacticalScene, layerId: string): string[] {
  return selectableObjects(scene)
    .filter((object) => object.layerId === layerId)
    .map((object) => object.id);
}

function rectFromObject(object: SceneObject): ObjectRect {
  const points = Array.isArray(object.data.points) ? object.data.points.map((value) => Number(value)) : [];
  if (points.length >= 4) {
    const xs = points.filter((_, index) => index % 2 === 0);
    const ys = points.filter((_, index) => index % 2 === 1);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    return {
      x: object.x + minX,
      y: object.y + minY,
      width: Math.max(4, maxX - minX),
      height: Math.max(4, maxY - minY),
    };
  }
  return {
    x: object.x,
    y: object.y,
    width: Math.max(4, object.width * object.scaleX),
    height: Math.max(4, object.height * object.scaleY),
  };
}

export function getObjectRect(object: SceneObject): ObjectRect {
  return rectFromObject(object);
}

export function getSelectionBounds(scene: TacticalScene, ids: string[]): ObjectRect | null {
  const objects = scene.objects.filter((object) => ids.includes(object.id));
  if (!objects.length) {
    return null;
  }
  const rects = objects.map(rectFromObject);
  const minX = Math.min(...rects.map((rect) => rect.x));
  const minY = Math.min(...rects.map((rect) => rect.y));
  const maxX = Math.max(...rects.map((rect) => rect.x + rect.width));
  const maxY = Math.max(...rects.map((rect) => rect.y + rect.height));
  return {
    x: minX,
    y: minY,
    width: Math.max(4, maxX - minX),
    height: Math.max(4, maxY - minY),
  };
}

function getSortedObjects(scene: TacticalScene): SceneObject[] {
  return [...scene.objects].sort((left, right) => {
    const layerDiff = getLayerOrder(scene, left.layerId) - getLayerOrder(scene, right.layerId);
    if (layerDiff !== 0) {
      return layerDiff;
    }
    if (left.zIndex !== right.zIndex) {
      return left.zIndex - right.zIndex;
    }
    return left.id.localeCompare(right.id);
  });
}

function normalizeZIndexes(objects: SceneObject[]): SceneObject[] {
  return objects.map((object, index) => ({ ...object, zIndex: index * 10 }));
}

export function moveSelectionOrder(
  scene: TacticalScene,
  ids: string[],
  direction: OrderMode
): TacticalScene {
  const selected = new Set(ids);
  const ordered = getSortedObjects(scene);
  const movable = ordered.filter((object) => selected.has(object.id));
  if (!movable.length) {
    return scene;
  }
  const remainder = ordered.filter((object) => !selected.has(object.id));
  let merged: SceneObject[] = [];
  if (direction === 'front') {
    merged = [...remainder, ...movable];
  } else if (direction === 'back') {
    merged = [...movable, ...remainder];
  } else {
    const result = [...ordered];
    movable.forEach((object) => {
      const index = result.findIndex((item) => item.id === object.id);
      const swapIndex = direction === 'forward' ? index + 1 : index - 1;
      if (index < 0 || swapIndex < 0 || swapIndex >= result.length) {
        return;
      }
      [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
    });
    merged = result;
  }
  return {
    ...scene,
    objects: normalizeZIndexes(
      merged.map((object, index) => ({
        ...object,
        zIndex: index * 10,
      }))
    ),
  };
}

function applyDelta(object: SceneObject, dx: number, dy: number): SceneObject {
  return {
    ...object,
    x: object.x + dx,
    y: object.y + dy,
  };
}

export function alignObjects(
  scene: TacticalScene,
  ids: string[],
  mode: AlignMode,
  options?: { fieldCentered?: boolean }
): TacticalScene {
  const objects = scene.objects.filter((object) => ids.includes(object.id));
  if (objects.length < 2) {
    return scene;
  }
  const bounds = getSelectionBounds(scene, ids);
  if (!bounds) {
    return scene;
  }
  const field = getPitchRect(scene);
  const fieldCenterX = field.x + field.width / 2;
  const fieldCenterY = field.y + field.height / 2;
  const nextObjects = scene.objects.map((object) => {
    if (!ids.includes(object.id)) {
      return object;
    }
    const rect = rectFromObject(object);
    const delta = { x: 0, y: 0 };
    if (mode === 'left') delta.x = bounds.x - rect.x;
    if (mode === 'center-x') delta.x = bounds.x + bounds.width / 2 - (rect.x + rect.width / 2);
    if (mode === 'right') delta.x = bounds.x + bounds.width - (rect.x + rect.width);
    if (mode === 'top') delta.y = bounds.y - rect.y;
    if (mode === 'center-y') delta.y = bounds.y + bounds.height / 2 - (rect.y + rect.height / 2);
    if (mode === 'bottom') delta.y = bounds.y + bounds.height - (rect.y + rect.height);
    if (options?.fieldCentered) {
      if (mode === 'left' || mode === 'center-x' || mode === 'right') {
        delta.x = fieldCenterX - (rect.x + rect.width / 2);
      }
      if (mode === 'top' || mode === 'center-y' || mode === 'bottom') {
        delta.y = fieldCenterY - (rect.y + rect.height / 2);
      }
    }
    return applyDelta(object, delta.x, delta.y);
  });
  return { ...scene, objects: normalizeZIndexes(nextObjects) };
}

export function equalizeObjectSize(
  scene: TacticalScene,
  ids: string[],
  mode: 'width' | 'height' | 'both'
): TacticalScene {
  const objects = scene.objects.filter((object) => ids.includes(object.id));
  if (objects.length < 2) {
    return scene;
  }
  const maxWidth = Math.max(...objects.map((object) => object.width));
  const maxHeight = Math.max(...objects.map((object) => object.height));
  return {
    ...scene,
    objects: scene.objects.map((object) => {
      if (!ids.includes(object.id)) {
        return object;
      }
      return {
        ...object,
        width: mode === 'height' ? object.width : maxWidth,
        height: mode === 'width' ? object.height : maxHeight,
      };
    }),
  };
}

export function distributeObjects(
  scene: TacticalScene,
  ids: string[],
  mode: DistributeMode,
  fixedGap?: number
): TacticalScene {
  const objects = scene.objects.filter((object) => ids.includes(object.id));
  if (objects.length < 3) {
    return scene;
  }
  const sorted = [...objects].sort((left, right) => {
    const leftRect = rectFromObject(left);
    const rightRect = rectFromObject(right);
    return mode === 'horizontal' ? leftRect.x - rightRect.x : leftRect.y - rightRect.y;
  });
  const first = rectFromObject(sorted[0]);
  const last = rectFromObject(sorted[sorted.length - 1]);
  const span =
    mode === 'horizontal'
      ? last.x + last.width - first.x
      : last.y + last.height - first.y;
  const totalSize = sorted.reduce((sum, object) => {
    const rect = rectFromObject(object);
    return sum + (mode === 'horizontal' ? rect.width : rect.height);
  }, 0);
  const gap = fixedGap ?? (span - totalSize) / Math.max(sorted.length - 1, 1);
  let cursor = mode === 'horizontal' ? first.x : first.y;
  const placement = new Map<string, { x: number; y: number }>();
  sorted.forEach((object) => {
    const rect = rectFromObject(object);
    placement.set(object.id, {
      x: mode === 'horizontal' ? cursor - rect.x : object.x,
      y: mode === 'vertical' ? cursor - rect.y : object.y,
    });
    cursor += (mode === 'horizontal' ? rect.width : rect.height) + gap;
  });
  return {
    ...scene,
    objects: scene.objects.map((object) => {
      const delta = placement.get(object.id);
      if (!delta) {
        return object;
      }
      return { ...object, x: object.x + delta.x, y: object.y + delta.y };
    }),
  };
}

export function groupObjects(scene: TacticalScene, ids: string[], label?: string): TacticalScene {
  const groupId = createUuid('group');
  return {
    ...scene,
    objects: scene.objects.map((object) => {
      if (!ids.includes(object.id)) {
        return object;
      }
      return {
        ...object,
        data: {
          ...object.data,
          groupId,
          groupLabel: label || String(object.data.groupLabel || 'Grupo'),
        },
      };
    }),
  };
}

export function ungroupObjects(scene: TacticalScene, ids: string[]): TacticalScene {
  const selected = new Set(ids);
  return {
    ...scene,
    objects: scene.objects.map((object) => {
      if (!selected.has(object.id) && !ids.includes(String(object.data.groupId || ''))) {
        return object;
      }
      const nextData = { ...object.data };
      delete nextData.groupId;
      delete nextData.groupLabel;
      return { ...object, data: nextData };
    }),
  };
}

function captureSceneObject(object: SceneObject) {
  return {
    id: object.id,
    type: object.type,
    layerId: object.layerId,
    x: object.x,
    y: object.y,
    width: object.width,
    height: object.height,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    style: deepClone(object.style),
    data: deepClone(object.data),
    visible: object.visible,
    locked: object.locked,
    zIndex: object.zIndex,
  };
}

export function captureTimelineKeyframe(
  scene: TacticalScene,
  time: number,
  options?: { objectIds?: string[]; label?: string }
): SceneTimelineKeyframe {
  const objectIds = options?.objectIds?.length
    ? options.objectIds
    : scene.objects.map((object) => object.id);
  return {
    id: createUuid('keyframe'),
    time,
    label: options?.label,
    objectIds,
    objects: scene.objects
      .filter((object) => objectIds.includes(object.id))
      .map((object) => captureSceneObject(object)),
  };
}

function lerp(left: number, right: number, ratio: number): number {
  return left + (right - left) * ratio;
}

export function projectSceneAtTime(scene: TacticalScene, time: number): TacticalScene {
  const keyframes = [...scene.timeline.keyframes].sort((left, right) => left.time - right.time);
  if (!keyframes.length) {
    return scene;
  }
  const previousFrames = keyframes.filter((frame) => frame.time <= time);
  const previous = previousFrames[previousFrames.length - 1] || keyframes[0];
  const next = keyframes.find((frame) => frame.time >= time) || previous;
  if (!previous || !next || previous.id === next.id) {
    const matched = previous || next;
    if (!matched) {
      return scene;
    }
    const objectMap = new Map<string, SceneTimelineKeyframe['objects'][number]>(
      matched.objects.map((object) => [object.id, object])
    );
    return {
      ...scene,
      objects: scene.objects.map((object) => {
        const frameObject = objectMap.get(object.id);
        return frameObject
          ? {
              ...object,
              x: frameObject.x,
              y: frameObject.y,
              width: frameObject.width,
              height: frameObject.height,
              rotation: frameObject.rotation,
              scaleX: frameObject.scaleX,
              scaleY: frameObject.scaleY,
              style: deepClone(frameObject.style),
              data: deepClone(frameObject.data),
              visible: frameObject.visible,
              locked: frameObject.locked,
              zIndex: frameObject.zIndex,
            }
          : object;
      }),
    };
  }
  const ratio = Math.min(1, Math.max(0, (time - previous.time) / Math.max(next.time - previous.time, 1)));
  const previousMap = new Map<string, SceneTimelineKeyframe['objects'][number]>(
    previous.objects.map((object) => [object.id, object])
  );
  const nextMap = new Map<string, SceneTimelineKeyframe['objects'][number]>(
    next.objects.map((object) => [object.id, object])
  );
  return {
    ...scene,
    objects: scene.objects.map((object) => {
      const left = previousMap.get(object.id);
      const right = nextMap.get(object.id);
      if (!left || !right) {
        return object;
      }
      return {
        ...object,
        x: lerp(left.x, right.x, ratio),
        y: lerp(left.y, right.y, ratio),
        width: lerp(left.width, right.width, ratio),
        height: lerp(left.height, right.height, ratio),
        rotation: lerp(left.rotation, right.rotation, ratio),
        scaleX: lerp(left.scaleX, right.scaleX, ratio),
        scaleY: lerp(left.scaleY, right.scaleY, ratio),
        style: {
          ...deepClone(left.style),
          ...deepClone(right.style),
        },
        data: {
          ...deepClone(left.data),
          ...deepClone(right.data),
        },
        visible: right.visible,
        locked: right.locked,
        zIndex: right.zIndex,
      };
    }),
  };
}

export function snapObjectPosition(
  scene: TacticalScene,
  object: SceneObject,
  preferences: EditorPreferences,
  options?: { ignore?: boolean; movingIds?: string[] }
): SnapResult {
  if (options?.ignore || !preferences.snapEnabled) {
    return { x: object.x, y: object.y, guides: [] };
  }
  const rect = rectFromObject(object);
  const pitch = getPitchRect(scene);
  const candidates = {
    vertical: new Set<number>([
      pitch.x,
      pitch.x + pitch.width / 2,
      pitch.x + pitch.width,
      pitch.x + pitch.width * 0.165,
      pitch.x + pitch.width - pitch.width * 0.165,
    ]),
    horizontal: new Set<number>([
      pitch.y,
      pitch.y + pitch.height / 2,
      pitch.y + pitch.height,
      pitch.y + pitch.height * 0.24,
      pitch.y + pitch.height - pitch.height * 0.24,
    ]),
  };
  scene.objects.forEach((other) => {
    if (other.id === object.id) {
      return;
    }
    if (options?.movingIds?.includes(other.id)) {
      return;
    }
    const otherRect = rectFromObject(other);
    candidates.vertical.add(otherRect.x);
    candidates.vertical.add(otherRect.x + otherRect.width / 2);
    candidates.vertical.add(otherRect.x + otherRect.width);
    candidates.horizontal.add(otherRect.y);
    candidates.horizontal.add(otherRect.y + otherRect.height / 2);
    candidates.horizontal.add(otherRect.y + otherRect.height);
  });
  let nextX = object.x;
  let nextY = object.y;
  const guides: SnapGuide[] = [];
  const snapDistance = Math.max(0, preferences.snapDistance);
  let bestVertical: { delta: number; guide: SnapGuide } | null = null;
  let bestHorizontal: { delta: number; guide: SnapGuide } | null = null;
  const anchors = [
    { value: rect.x, offset: 0 },
    { value: rect.x + rect.width / 2, offset: rect.width / 2 },
    { value: rect.x + rect.width, offset: rect.width },
  ];
  const anchorY = [
    { value: rect.y, offset: 0 },
    { value: rect.y + rect.height / 2, offset: rect.height / 2 },
    { value: rect.y + rect.height, offset: rect.height },
  ];
  candidates.vertical.forEach((candidate) => {
    anchors.forEach((anchor) => {
      const delta = candidate - anchor.value;
      if (Math.abs(delta) <= snapDistance && (!bestVertical || Math.abs(delta) < Math.abs(bestVertical.delta))) {
        bestVertical = {
          delta,
          guide: {
            id: `v-${candidate}`,
            x1: candidate,
            y1: pitch.y,
            x2: candidate,
            y2: pitch.y + pitch.height,
          },
        };
      }
    });
  });
  candidates.horizontal.forEach((candidate) => {
    anchorY.forEach((anchor) => {
      const delta = candidate - anchor.value;
      if (Math.abs(delta) <= snapDistance && (!bestHorizontal || Math.abs(delta) < Math.abs(bestHorizontal.delta))) {
        bestHorizontal = {
          delta,
          guide: {
            id: `h-${candidate}`,
            x1: pitch.x,
            y1: candidate,
            x2: pitch.x + pitch.width,
            y2: candidate,
          },
        };
      }
    });
  });
  if (bestVertical) {
    const vertical = bestVertical as { delta: number; guide: SnapGuide };
    nextX += vertical.delta;
    guides.push(vertical.guide);
  }
  if (bestHorizontal) {
    const horizontal = bestHorizontal as { delta: number; guide: SnapGuide };
    nextY += horizontal.delta;
    guides.push(horizontal.guide);
  }
  return { x: nextX, y: nextY, guides };
}
