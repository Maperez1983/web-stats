import type { SceneObject } from './sceneSchema';

export type SelectionBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function toggleSelection(selectedIds: string[], id: string, additive: boolean): string[] {
  if (!additive) {
    return [id];
  }
  return selectedIds.includes(id)
    ? selectedIds.filter((item) => item !== id)
    : [...selectedIds, id];
}

export function normalizeSelectionBox(box: SelectionBox): SelectionBox {
  const x = box.width < 0 ? box.x + box.width : box.x;
  const y = box.height < 0 ? box.y + box.height : box.y;
  return {
    x,
    y,
    width: Math.abs(box.width),
    height: Math.abs(box.height),
  };
}

export function intersectingIds(objects: SceneObject[], selectionBox: SelectionBox): string[] {
  const box = normalizeSelectionBox(selectionBox);
  return objects
    .filter((object) => {
      const width = object.width * object.scaleX;
      const height = object.height * object.scaleY;
      return !(
        object.x + width < box.x ||
        object.y + height < box.y ||
        object.x > box.x + box.width ||
        object.y > box.y + box.height
      );
    })
    .map((object) => object.id);
}
