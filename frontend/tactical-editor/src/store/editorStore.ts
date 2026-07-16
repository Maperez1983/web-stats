import { create } from 'zustand';
import {
  createHistoryState,
  beginHistoryTransaction,
  commitHistoryTransaction,
  pushHistorySnapshot,
  redoHistory,
  undoHistory,
} from '../editor/core/HistoryManager';
import {
  createDefaultLayers,
  moveLayer,
  toggleLayerLock,
  toggleLayerVisibility,
} from '../editor/core/LayerManager';
import { toggleSelection } from '../editor/core/SelectionManager';
import { createDefaultScene, createUuid, deepClone } from '../editor/core/sceneSchema';
import type { HistoryState } from '../editor/core/HistoryManager';
import type {
  PitchType,
  SceneLayerId,
  SceneObject,
  SceneObjectType,
  TacticalScene,
} from '../editor/core/sceneSchema';
import { createObject } from '../editor/objects/ObjectFactory';
import {
  createSceneFromDocument,
  sceneToLegacyCanvasState,
} from '../editor/serialization/SceneSerializer';
import type { TaskEditorDocument } from '../domain/taskDocument';

export type EditorViewport = 'board2d' | 'board3d' | 'uefa';
export type EditorInspector = 'properties' | 'sequence' | 'exports';
export type EditorTool =
  | 'select'
  | 'pan'
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
  | 'label';

export type CanvasExportOptions = {
  pixelRatio?: number;
  includeUi?: boolean;
  background?: string | null;
};

export type CanvasApi = {
  exportPngDataUrl: (options?: CanvasExportOptions) => string | null;
  fitToScene: () => void;
};

type EditorStore = {
  document: TaskEditorDocument | null;
  scene: TacticalScene | null;
  activeViewport: EditorViewport;
  activeInspector: EditorInspector;
  activeTool: EditorTool;
  selectedIds: string[];
  dirty: boolean;
  saving: boolean;
  error: string | null;
  history: HistoryState;
  clipboard: SceneObject[];
  revision: number;
  canvasApi: CanvasApi | null;
  featureEnabled: boolean;
  setDocument: (document: TaskEditorDocument) => void;
  setViewport: (viewport: EditorViewport) => void;
  setInspector: (inspector: EditorInspector) => void;
  setTool: (tool: EditorTool) => void;
  setCanvasApi: (api: CanvasApi | null) => void;
  clearSelection: () => void;
  selectSingle: (id: string | null) => void;
  toggleObjectSelection: (id: string, additive: boolean) => void;
  setSelection: (ids: string[]) => void;
  addSceneObject: (type: SceneObjectType, options?: { x?: number; y?: number }) => void;
  patchSceneObject: (
    id: string,
    patch: Partial<SceneObject>,
    options?: { history?: boolean }
  ) => void;
  replaceSceneObject: (id: string, object: SceneObject, options?: { history?: boolean }) => void;
  removeSelectedObjects: () => void;
  duplicateSelectedObjects: () => void;
  copySelectedObjects: () => void;
  pasteClipboard: () => void;
  setObjectVisibility: (id: string, visible: boolean) => void;
  setObjectLock: (id: string, locked: boolean) => void;
  setObjectColor: (id: string, fill: string) => void;
  setObjectLabel: (id: string, label: string) => void;
  setObjectTeam: (id: string, team: 'home' | 'away' | 'neutral' | 'joker') => void;
  reorderSelected: (direction: 'forward' | 'backward') => void;
  setPitchType: (pitchType: PitchType) => void;
  setSceneViewport: (patch: Partial<TacticalScene['viewport']>) => void;
  setLayerVisibility: (layerId: SceneLayerId) => void;
  setLayerLock: (layerId: SceneLayerId) => void;
  moveLayerOrder: (layerId: SceneLayerId, direction: -1 | 1) => void;
  beginTransaction: () => void;
  commitTransaction: () => void;
  undo: () => void;
  redo: () => void;
  exportSceneJson: () => string;
  importScene: (scene: TacticalScene) => void;
  getSavePayload: () => {
    canvas_state: Record<string, unknown>;
    canvas_width: number;
    canvas_height: number;
  } | null;
  saveStart: () => number;
  saveSuccess: (document: TaskEditorDocument, savedRevision: number) => void;
  saveError: (message: string) => void;
};

function isFeatureEnabled(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  const params = new URLSearchParams(window.location.search);
  return ['1', 'true', 'konva', 'foundation'].includes(
    String(params.get('editor2d') || '').toLowerCase()
  );
}

function cloneScene(scene: TacticalScene): TacticalScene {
  return deepClone(scene);
}

function markSceneDirty(scene: TacticalScene): TacticalScene {
  return {
    ...scene,
    metadata: {
      ...scene.metadata,
      updatedAt: new Date().toISOString(),
    },
  };
}

function normalizeScene(document: TaskEditorDocument): TacticalScene {
  const parsed = createSceneFromDocument(document);
  return {
    ...parsed,
    layers: parsed.layers.length ? parsed.layers : createDefaultLayers(),
  };
}

function withSceneMutation(
  state: EditorStore,
  mutator: (scene: TacticalScene) => TacticalScene,
  options?: { history?: boolean; clearSelection?: boolean; selectionIds?: string[] }
): Partial<EditorStore> {
  if (!state.scene) {
    return {};
  }
  const base = options?.history ? pushHistorySnapshot(state.history, state.scene) : state.history;
  const nextScene = markSceneDirty(mutator(cloneScene(state.scene)));
  return {
    scene: nextScene,
    history: {
      ...base,
      future: options?.history ? [] : base.future,
    },
    dirty: true,
    revision: state.revision + 1,
    selectedIds: options?.selectionIds ?? (options?.clearSelection ? [] : state.selectedIds),
  };
}

function findObject(scene: TacticalScene | null, id: string): SceneObject | undefined {
  return scene?.objects.find((object) => object.id === id);
}

function selectedObjects(scene: TacticalScene | null, selectedIds: string[]): SceneObject[] {
  if (!scene) return [];
  return scene.objects.filter((object) => selectedIds.includes(object.id));
}

function sameSelection(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

export const useEditorStore = create<EditorStore>((set, get) => ({
  document: null,
  scene: null,
  activeViewport: 'board2d',
  activeInspector: 'properties',
  activeTool: 'select',
  selectedIds: [],
  dirty: false,
  saving: false,
  error: null,
  history: createHistoryState(),
  clipboard: [],
  revision: 0,
  canvasApi: null,
  featureEnabled: isFeatureEnabled(),
  setDocument: (document) =>
    set({
      document,
      scene: normalizeScene(document),
      selectedIds: [],
      dirty: false,
      saving: false,
      error: null,
      history: createHistoryState(),
    }),
  setViewport: (activeViewport) => set({ activeViewport }),
  setInspector: (activeInspector) => set({ activeInspector }),
  setTool: (activeTool) => set({ activeTool }),
  setCanvasApi: (canvasApi) => set({ canvasApi }),
  clearSelection: () => set({ selectedIds: [] }),
  selectSingle: (id) =>
    set((state) => {
      const nextSelectedIds = id ? [id] : [];
      return sameSelection(state.selectedIds, nextSelectedIds) ? {} : { selectedIds: nextSelectedIds };
    }),
  toggleObjectSelection: (id, additive) =>
    set((state) => {
      const nextSelectedIds = toggleSelection(state.selectedIds, id, additive);
      return sameSelection(state.selectedIds, nextSelectedIds) ? {} : { selectedIds: nextSelectedIds };
    }),
  setSelection: (selectedIds) =>
    set((state) => (sameSelection(state.selectedIds, selectedIds) ? {} : { selectedIds })),
  addSceneObject: (type, options) =>
    set((state) => {
      if (!state.scene) return {};
      const nextObject = createObject(type, {
        x: options?.x,
        y: options?.y,
        zIndex: state.scene.objects.length,
      });
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: [...scene.objects, nextObject],
        }),
        { history: true, selectionIds: [nextObject.id] }
      );
    }),
  patchSceneObject: (id, patch, options) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id
              ? {
                  ...object,
                  ...patch,
                  style: { ...object.style, ...(patch.style || {}) },
                  data: { ...object.data, ...(patch.data || {}) },
                }
              : object
          ),
        }),
        { history: options?.history === true }
      )
    ),
  replaceSceneObject: (id, object, options) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((item) => (item.id === id ? object : item)),
        }),
        { history: options?.history === true }
      )
    ),
  removeSelectedObjects: () =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.filter((object) => !state.selectedIds.includes(object.id)),
        }),
        { history: true, clearSelection: true }
      );
    }),
  duplicateSelectedObjects: () =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const copies = selectedObjects(state.scene, state.selectedIds).map((object, index) => ({
        ...deepClone(object),
        id: createUuid('dup'),
        x: object.x + 28,
        y: object.y + 28,
        zIndex: state.scene ? state.scene.objects.length + index : index,
      }));
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: [...scene.objects, ...copies],
        }),
        { history: true, selectionIds: copies.map((item) => item.id) }
      );
    }),
  copySelectedObjects: () =>
    set((state) => ({
      clipboard: selectedObjects(state.scene, state.selectedIds).map((object) => deepClone(object)),
    })),
  pasteClipboard: () =>
    set((state) => {
      if (!state.scene || !state.clipboard.length) return {};
      const pasted = state.clipboard.map((object, index) => ({
        ...deepClone(object),
        id: createUuid('paste'),
        x: object.x + 24,
        y: object.y + 24,
        zIndex: state.scene ? state.scene.objects.length + index : index,
      }));
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: [...scene.objects, ...pasted],
        }),
        { history: true, selectionIds: pasted.map((item) => item.id) }
      );
    }),
  setObjectVisibility: (id, visible) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, visible } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectLock: (id, locked) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, locked } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectColor: (id, fill) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, style: { ...object.style, fill } } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectLabel: (id, label) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, data: { ...object.data, label } } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectTeam: (id, team) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, data: { ...object.data, team } } : object
          ),
        }),
        { history: true }
      )
    ),
  reorderSelected: (direction) =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const delta = direction === 'forward' ? 1 : -1;
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects
            .map((object) =>
              state.selectedIds.includes(object.id)
                ? { ...object, zIndex: object.zIndex + delta }
                : object
            )
            .sort((a, b) => a.zIndex - b.zIndex)
            .map((object, index) => ({ ...object, zIndex: index })),
        }),
        { history: true }
      );
    }),
  setPitchType: (pitchType) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          pitch: { ...scene.pitch, type: pitchType },
        }),
        { history: true }
      )
    ),
  setSceneViewport: (patch) =>
    set((state) =>
      withSceneMutation(state, (scene) => ({
        ...scene,
        viewport: { ...scene.viewport, ...patch },
      }))
    ),
  setLayerVisibility: (layerId) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: toggleLayerVisibility(scene.layers, layerId),
        }),
        { history: true }
      )
    ),
  setLayerLock: (layerId) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: toggleLayerLock(scene.layers, layerId),
        }),
        { history: true }
      )
    ),
  moveLayerOrder: (layerId, direction) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: moveLayer(scene.layers, layerId, direction),
        }),
        { history: true }
      )
    ),
  beginTransaction: () =>
    set((state) => ({
      history: state.scene ? beginHistoryTransaction(state.history, state.scene) : state.history,
    })),
  commitTransaction: () =>
    set((state) => ({
      history: state.scene ? commitHistoryTransaction(state.history, state.scene) : state.history,
    })),
  undo: () =>
    set((state) => {
      if (!state.scene) return {};
      const next = undoHistory(state.history, state.scene);
      if (!next.scene) return {};
      return {
        scene: next.scene,
        history: next.history,
        dirty: true,
        revision: state.revision + 1,
      };
    }),
  redo: () =>
    set((state) => {
      if (!state.scene) return {};
      const next = redoHistory(state.history, state.scene);
      if (!next.scene) return {};
      return {
        scene: next.scene,
        history: next.history,
        dirty: true,
        revision: state.revision + 1,
      };
    }),
  exportSceneJson: () => {
    const scene = get().scene;
    return JSON.stringify(scene || createDefaultScene('', ''), null, 2);
  },
  importScene: (scene) =>
    set((state) => ({
      scene: cloneScene(scene),
      dirty: true,
      selectedIds: [],
      history: pushHistorySnapshot(state.history, state.scene || createDefaultScene('', '')),
      revision: state.revision + 1,
    })),
  getSavePayload: () => {
    const state = get();
    if (!state.scene) {
      return null;
    }
    const serialized = sceneToLegacyCanvasState(state.scene);
    return {
      canvas_state: serialized,
      canvas_width: state.scene.canvas.width,
      canvas_height: state.scene.canvas.height,
    };
  },
  saveStart: () => {
    const revision = get().revision;
    set({ saving: true, error: null });
    return revision;
  },
  saveSuccess: (document, savedRevision) =>
    set((state) => {
      if (state.revision !== savedRevision) {
        return {
          document,
          saving: false,
          error: null,
        };
      }
      return {
        document,
        scene: normalizeScene(document),
        selectedIds: [],
        dirty: false,
        saving: false,
        error: null,
      };
    }),
  saveError: (message) =>
    set({ saving: false, error: message || 'No se pudo guardar la pizarra.' }),
}));

export function useSelectedObject(): SceneObject | null {
  const scene = useEditorStore((state) => state.scene);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  if (!scene || selectedIds.length !== 1) {
    return null;
  }
  return findObject(scene, selectedIds[0]) || null;
}
