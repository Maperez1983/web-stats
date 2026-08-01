import type { SceneObject, SceneObjectType, TacticalScene } from '../core/sceneSchema';
import type { CanvasExportOptions } from '../../store/editorStore';
import { sceneToLegacyCanvasState } from '../serialization/SceneSerializer';

export type CanvasAdapterKind = 'legacy' | 'konva';

export type CanvasObjectSpawnOptions = {
  x?: number;
  y?: number;
  assetId?: string;
  assetVariant?: string;
  orientation?: string;
};

export type CanvasAdapterDependencies = {
  getScene: () => TacticalScene | null;
  addSceneObject: (
    type: SceneObjectType,
    options?: CanvasObjectSpawnOptions
  ) => void;
  removeSelectedObjects: () => void;
  duplicateSelectedObjects: () => void;
  undo: () => void;
  redo: () => void;
  fitToScene: () => void;
  exportPngDataUrl?: (options?: CanvasExportOptions) => string | null;
};

export type CanvasAdapter = {
  kind: CanvasAdapterKind;
  load: (scene: TacticalScene | null) => void;
  save: (scene: TacticalScene | null) => Record<string, unknown> | null;
  render: (scene: TacticalScene | null) => void;
  createObject: (type: SceneObjectType, options?: CanvasObjectSpawnOptions) => SceneObject | null;
  createPlayer: (options?: CanvasObjectSpawnOptions) => SceneObject | null;
  createCone: (options?: CanvasObjectSpawnOptions) => SceneObject | null;
  createArrow: (type?: SceneObjectType, options?: CanvasObjectSpawnOptions) => SceneObject | null;
  delete: (ids?: string[]) => void;
  duplicate: (ids?: string[]) => void;
  undo: () => void;
  redo: () => void;
  exportPNG: (options?: CanvasExportOptions) => string | null;
  fitToScene: () => void;
};

export function createCanvasAdapter(
  kind: CanvasAdapterKind,
  dependencies: CanvasAdapterDependencies
): CanvasAdapter {
  const spawn = (type: SceneObjectType, options?: CanvasObjectSpawnOptions) => {
    dependencies.addSceneObject(type, options);
    const objects = dependencies.getScene()?.objects || [];
    return objects.length ? objects[objects.length - 1] : null;
  };

  return {
    kind,
    load: () => undefined,
    save: (scene) => (scene ? sceneToLegacyCanvasState(scene) : null),
    render: () => undefined,
    createObject: spawn,
    createPlayer: (options) => spawn('player', options),
    createCone: (options) => spawn('cone', options),
    createArrow: (type = 'arrow-straight', options) => spawn(type, options),
    delete: () => dependencies.removeSelectedObjects(),
    duplicate: () => dependencies.duplicateSelectedObjects(),
    undo: () => dependencies.undo(),
    redo: () => dependencies.redo(),
    exportPNG: (options) => dependencies.exportPngDataUrl?.(options) || null,
    fitToScene: () => dependencies.fitToScene(),
  };
}
