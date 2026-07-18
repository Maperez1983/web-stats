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
  alignObjects,
  distributeObjects,
  equalizeObjectSize,
  expandSelectionByGroups,
  getSelectionBounds,
  groupObjects,
  invertSelection,
  isSelectableObject,
  moveSelectionOrder,
  selectAllIds,
  selectByLayer,
  selectByType,
  snapObjectPosition,
  ungroupObjects,
} from '../editor/core/editorOperations';
import {
  applyAnimationKeyframeCapture,
  duplicateAnimationSelection,
  moveAnimationKeyframe,
  normalizeSceneAnimation,
  removeAnimationKeyframe,
} from '../editor/animation/AnimationCommands';
import {
  createDefaultLayers,
  createLayer,
  duplicateLayer,
  moveLayer,
  moveObjectsToLayer,
  removeLayer,
  renameLayer,
  toggleLayerLock,
  toggleLayerVisibility,
} from '../editor/core/LayerManager';
import { createDefaultScene, createUuid, deepClone } from '../editor/core/sceneSchema';
import type { HistoryState } from '../editor/core/HistoryManager';
import type {
  EditorPreferences,
  PitchType,
  SceneLayerId,
  SceneObject,
  SceneObjectType,
  TacticalScene,
} from '../editor/core/sceneSchema';
import { createAssetObject, createObject } from '../editor/objects/ObjectFactory';
import {
  createSceneFromDocument,
  sceneToLegacyCanvasState,
} from '../editor/serialization/SceneSerializer';
import { resolveAssetDefinition } from '../editor/assets/assetRegistry';
import { compileTacticalRecreation } from '../tactical-language';
import type { TaskEditorDocument } from '../domain/taskDocument';

export type EditorViewport = 'board2d' | 'board3d' | 'uefa';
export type EditorInspector = 'properties' | 'sequence' | 'exports';
export type EditorTool =
  | 'select'
  | 'pan'
  | 'player'
  | 'player-home'
  | 'player-away'
  | 'player-joker'
  | 'goalkeeper'
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
  | 'line-dashed'
  | 'line'
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
  activeAssetId: string | null;
  selectedIds: string[];
  dirty: boolean;
  saving: boolean;
  error: string | null;
  history: HistoryState;
  clipboard: SceneObject[];
  revision: number;
  canvasApi: CanvasApi | null;
  snapGuides: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>;
  featureEnabled: boolean;
  tacticalRecreation: ReturnType<typeof compileTacticalRecreation> | null;
  tacticalRecreationToken: number;
  setDocument: (document: TaskEditorDocument) => void;
  setViewport: (viewport: EditorViewport) => void;
  setInspector: (inspector: EditorInspector) => void;
  setTool: (tool: EditorTool) => void;
  setActiveAssetId: (assetId: string | null) => void;
  setCanvasApi: (api: CanvasApi | null) => void;
  clearSelection: () => void;
  selectSingle: (id: string | null) => void;
  toggleObjectSelection: (id: string, additive: boolean) => void;
  setSelection: (ids: string[]) => void;
  selectAllObjects: () => void;
  invertSelection: () => void;
  selectObjectsByType: (type: SceneObjectType) => void;
  selectObjectsByLayer: (layerId: SceneLayerId) => void;
  addSceneObject: (
    type: SceneObjectType,
    options?: { x?: number; y?: number; assetId?: string; assetVariant?: string; orientation?: string }
  ) => void;
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
  setSelectionVisibility: (visible: boolean) => void;
  setSelectionLock: (locked: boolean) => void;
  setObjectColor: (id: string, fill: string) => void;
  setObjectStrokeColor: (id: string, stroke: string) => void;
  setObjectOpacity: (id: string, opacity: number) => void;
  setObjectRotation: (id: string, rotation: number) => void;
  setObjectSize: (id: string, width: number, height: number) => void;
  setObjectPoints: (id: string, points: number[]) => void;
  setObjectLabel: (id: string, label: string) => void;
  setObjectName: (id: string, name: string) => void;
  setObjectTeam: (id: string, team: 'home' | 'away' | 'neutral' | 'joker') => void;
  setObjectAsset: (id: string, assetId: string) => void;
  setObjectLayer: (id: string, layerId: SceneLayerId) => void;
  reorderSelected: (direction: 'front' | 'forward' | 'backward' | 'back') => void;
  alignSelected: (mode: 'left' | 'center-x' | 'right' | 'top' | 'center-y' | 'bottom') => void;
  distributeSelected: (mode: 'horizontal' | 'vertical', gap?: number) => void;
  equalizeSelectedSize: (mode: 'width' | 'height' | 'both') => void;
  centerSelectedInField: () => void;
  groupSelected: () => void;
  ungroupSelected: () => void;
  setPitchType: (pitchType: PitchType) => void;
  setSceneViewport: (patch: Partial<TacticalScene['viewport']>) => void;
  setLayerVisibility: (layerId: SceneLayerId) => void;
  setLayerLock: (layerId: SceneLayerId) => void;
  moveLayerOrder: (layerId: SceneLayerId, direction: -1 | 1) => void;
  createLayer: (name: string) => void;
  renameLayer: (layerId: SceneLayerId, name: string) => void;
  duplicateLayer: (layerId: SceneLayerId) => void;
  removeLayer: (layerId: SceneLayerId) => void;
  moveSelectionToLayer: (layerId: SceneLayerId) => void;
  setSnapGuides: (guides: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>) => void;
  updatePreferences: (patch: Partial<EditorPreferences>) => void;
  generateRecreation: () => void;
  addTimelineKeyframe: (time?: number, label?: string) => void;
  removeTimelineKeyframe: (keyframeId: string) => void;
  moveTimelineKeyframe: (keyframeId: string, time: number) => void;
  duplicateTimelineKeyframes: (keyframeIds: string[], offset?: number) => void;
  setTimelineDuration: (duration: number) => void;
  setTimelineTime: (time: number) => void;
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
  return normalizeSceneAnimation({
    ...parsed,
    layers: parsed.layers.length ? parsed.layers : createDefaultLayers(),
  });
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

function getPreferences(scene: TacticalScene | null): EditorPreferences {
  return scene?.metadata.preferences || {
    snapEnabled: true,
    snapDistance: 8,
    gridVisible: false,
    gridSize: 20,
    showGuides: true,
  };
}

function updateScenePreferences(scene: TacticalScene, patch: Partial<EditorPreferences>): TacticalScene {
  return {
    ...scene,
    metadata: {
      ...scene.metadata,
      preferences: {
        ...getPreferences(scene),
        ...patch,
      },
    },
  };
}

function normalizeGroupSelection(scene: TacticalScene, ids: string[]): string[] {
  return expandSelectionByGroups(scene, ids).filter((id, index, array) => array.indexOf(id) === index);
}

function mutateSelectedSceneObjects(
  scene: TacticalScene,
  ids: string[],
  mutator: (object: SceneObject) => SceneObject
): TacticalScene {
  const selected = new Set(ids);
  return {
    ...scene,
    objects: scene.objects.map((object) => (selected.has(object.id) ? mutator(object) : object)),
  };
}

function reorderSceneObjects(scene: TacticalScene, ids: string[], mode: 'front' | 'forward' | 'backward' | 'back'): TacticalScene {
  return moveSelectionOrder(scene, ids, mode);
}

export const useEditorStore = create<EditorStore>((set, get) => ({
  document: null,
  scene: null,
  activeViewport: 'board2d',
  activeInspector: 'properties',
  activeTool: 'select',
  activeAssetId: null,
  selectedIds: [],
  dirty: false,
  saving: false,
  error: null,
  history: createHistoryState(),
  clipboard: [],
  revision: 0,
  canvasApi: null,
  snapGuides: [],
  featureEnabled: isFeatureEnabled(),
  tacticalRecreation: null,
  tacticalRecreationToken: 0,
  setDocument: (document) =>
    set({
      document,
      scene: normalizeScene(document),
      selectedIds: [],
      activeAssetId: null,
      dirty: false,
      saving: false,
      error: null,
      history: createHistoryState(),
      snapGuides: [],
      tacticalRecreation: null,
      tacticalRecreationToken: 0,
    }),
  setViewport: (activeViewport) => set({ activeViewport }),
  setInspector: (activeInspector) => set({ activeInspector }),
  setTool: (activeTool) => set({ activeTool }),
  setActiveAssetId: (activeAssetId) => set({ activeAssetId }),
  setCanvasApi: (canvasApi) => set({ canvasApi }),
  clearSelection: () => set({ selectedIds: [] }),
  selectSingle: (id) =>
    set((state) => {
      const nextSelectedIds = id && state.scene ? normalizeGroupSelection(state.scene, [id]) : [];
      return sameSelection(state.selectedIds, nextSelectedIds) ? {} : { selectedIds: nextSelectedIds };
    }),
  toggleObjectSelection: (id, additive) =>
    set((state) => {
      const expanded = state.scene ? normalizeGroupSelection(state.scene, [id]) : [id];
      const nextSelectedIds = additive
        ? [...new Set([...state.selectedIds, ...expanded])]
        : expanded;
      return sameSelection(state.selectedIds, nextSelectedIds) ? {} : { selectedIds: nextSelectedIds };
    }),
  setSelection: (selectedIds) =>
    set((state) => {
      const nextSelectedIds = state.scene ? normalizeGroupSelection(state.scene, selectedIds) : selectedIds;
      return sameSelection(state.selectedIds, nextSelectedIds) ? {} : { selectedIds: nextSelectedIds };
    }),
  selectAllObjects: () =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return { selectedIds: selectAllIds(state.scene) };
    }),
  invertSelection: () =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return { selectedIds: invertSelection(state.scene, state.selectedIds) };
    }),
  selectObjectsByType: (type) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return { selectedIds: selectByType(state.scene, type) };
    }),
  selectObjectsByLayer: (layerId) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return { selectedIds: selectByLayer(state.scene, layerId) };
    }),
  addSceneObject: (type, options) =>
    set((state) => {
      if (!state.scene) return {};
      const nextObject = options?.assetId
        ? createAssetObject(options.assetId, {
            x: options?.x,
            y: options?.y,
            zIndex: state.scene.objects.length,
            assetVariant: options?.assetVariant,
            orientation: options?.orientation,
          })
        : createObject(type, {
            x: options?.x,
            y: options?.y,
            zIndex: state.scene.objects.length,
            assetId: options?.assetId,
            assetVariant: options?.assetVariant,
            orientation: options?.orientation,
          });
      const centeredObject = {
        ...nextObject,
        x: typeof options?.x === 'number' ? options.x - nextObject.width / 2 : nextObject.x,
        y: typeof options?.y === 'number' ? options.y - nextObject.height / 2 : nextObject.y,
      };
      const preferences = getPreferences(state.scene);
      const snapped = snapObjectPosition(
        state.scene,
        { ...centeredObject, x: Number(centeredObject.x), y: Number(centeredObject.y) },
        preferences
      );
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: [
            ...scene.objects,
            {
              ...centeredObject,
              x: snapped.x,
              y: snapped.y,
            },
          ],
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
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.filter((object) => !selectedIds.includes(object.id)),
        }),
        { history: true, clearSelection: true }
      );
    }),
  duplicateSelectedObjects: () =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      const groupMap = new Map<string, string>();
      const copies = selectedObjects(state.scene, selectedIds).map((object, index) => {
        const copy = deepClone(object);
        copy.id = createUuid('dup');
        copy.x = object.x + 28;
        copy.y = object.y + 28;
        copy.zIndex = state.scene ? state.scene.objects.length + index : index;
        if (copy.data?.groupId) {
          const originalGroupId = String(copy.data.groupId);
          if (!groupMap.has(originalGroupId)) {
            groupMap.set(originalGroupId, createUuid('group'));
          }
          copy.data.groupId = groupMap.get(originalGroupId);
        }
        return copy;
      });
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
      clipboard: state.scene
        ? selectedObjects(state.scene, normalizeGroupSelection(state.scene, state.selectedIds)).map(
            (object) => deepClone(object)
          )
        : [],
    })),
  pasteClipboard: () =>
    set((state) => {
      if (!state.scene || !state.clipboard.length) return {};
      const groupMap = new Map<string, string>();
      const pasted = state.clipboard.map((object, index) => {
        const copy = deepClone(object);
        copy.id = createUuid('paste');
        copy.x = object.x + 24;
        copy.y = object.y + 24;
        copy.zIndex = state.scene ? state.scene.objects.length + index : index;
        if (copy.data?.groupId) {
          const originalGroupId = String(copy.data.groupId);
          if (!groupMap.has(originalGroupId)) {
            groupMap.set(originalGroupId, createUuid('group'));
          }
          copy.data.groupId = groupMap.get(originalGroupId);
        }
        return copy;
      });
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
  setSelectionVisibility: (visible) =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) {
        return {};
      }
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            selectedIds.includes(object.id) ? { ...object, visible } : object
          ),
        }),
        { history: true }
      );
    }),
  setSelectionLock: (locked) =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) {
        return {};
      }
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            selectedIds.includes(object.id) ? { ...object, locked } : object
          ),
        }),
        { history: true }
      );
    }),
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
  setObjectStrokeColor: (id, stroke) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, style: { ...object.style, stroke } } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectOpacity: (id, opacity) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, style: { ...object.style, opacity } } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectRotation: (id, rotation) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, rotation } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectSize: (id, width, height) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, width, height } : object
          ),
        }),
        { history: true }
      )
    ),
  setObjectPoints: (id, points) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id
              ? { ...object, data: { ...object.data, points: points.map((value) => Number(value)) } }
              : object
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
  setObjectName: (id, name) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, data: { ...object.data, name } } : object
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
  setObjectAsset: (id, assetId) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) => {
            if (object.id !== id) {
              return object;
            }
            const asset = resolveAssetDefinition(
              assetId,
              object.type,
              typeof object.data.variant === 'string' ? object.data.variant : undefined
            );
            return {
              ...object,
              type: asset.type,
              layerId: asset.layerId,
              width: asset.defaultSize.width,
              height: asset.defaultSize.height,
              style: { ...object.style, ...asset.defaultStyle },
              data: {
                ...asset.defaultData,
                ...object.data,
                assetId: asset.assetId,
                variant:
                  typeof object.data.variant === 'string'
                    ? object.data.variant
                    : (asset.defaultData.variant as string | undefined),
                orientation:
                  typeof object.data.orientation === 'string'
                    ? object.data.orientation
                    : (asset.defaultData.orientation as string | undefined),
              },
            };
          }),
        }),
        { history: true }
      )
    ),
  setObjectLayer: (id, layerId) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          objects: scene.objects.map((object) =>
            object.id === id ? { ...object, layerId } : object
          ),
        }),
        { history: true }
      )
    ),
  reorderSelected: (direction) =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => reorderSceneObjects(scene, selectedIds, direction),
        { history: true }
      );
    }),
  alignSelected: (mode) =>
    set((state) => {
      if (!state.scene || state.selectedIds.length < 2) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => alignObjects(scene, selectedIds, mode),
        { history: true }
      );
    }),
  distributeSelected: (mode, gap) =>
    set((state) => {
      if (!state.scene || state.selectedIds.length < 3) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => distributeObjects(scene, selectedIds, mode, gap),
        { history: true }
      );
    }),
  equalizeSelectedSize: (mode) =>
    set((state) => {
      if (!state.scene || state.selectedIds.length < 2) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(
        state,
        (scene) => equalizeObjectSize(scene, selectedIds, mode),
        { history: true }
      );
    }),
  centerSelectedInField: () =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const bounds = getSelectionBounds(state.scene, normalizeGroupSelection(state.scene, state.selectedIds));
      if (!bounds) return {};
      const field = state.scene.canvas;
      const dx = field.width / 2 - (bounds.x + bounds.width / 2);
      const dy = field.height / 2 - (bounds.y + bounds.height / 2);
      return withSceneMutation(
        state,
        (scene) =>
          mutateSelectedSceneObjects(scene, normalizeGroupSelection(scene, state.selectedIds), (object) => ({
            ...object,
            x: object.x + dx,
            y: object.y + dy,
          })),
        { history: true }
      );
    }),
  groupSelected: () =>
    set((state) => {
      if (!state.scene || state.selectedIds.length < 2) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(state, (scene) => groupObjects(scene, selectedIds), {
        history: true,
      });
    }),
  ungroupSelected: () =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) return {};
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(state, (scene) => ungroupObjects(scene, selectedIds), {
        history: true,
      });
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
  createLayer: (name) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: createLayer(scene.layers, name),
        }),
        { history: true }
      )
    ),
  renameLayer: (layerId, name) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: renameLayer(scene.layers, layerId, name),
        }),
        { history: true }
      )
    ),
  duplicateLayer: (layerId) =>
    set((state) =>
      withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          layers: duplicateLayer(scene.layers, layerId),
        }),
        { history: true }
      )
    ),
  removeLayer: (layerId) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return withSceneMutation(
        state,
        (scene) => {
          const result = removeLayer(scene.layers, layerId, scene.objects);
          return {
            ...scene,
            layers: result.layers,
            objects: result.movedObjects.length
              ? scene.objects.map((object) =>
                  object.layerId === layerId
                    ? { ...object, layerId: result.movedObjects[0].layerId }
                    : object
                )
              : scene.objects,
          };
        },
        { history: true }
      );
    }),
  moveSelectionToLayer: (layerId) =>
    set((state) => {
      if (!state.scene || !state.selectedIds.length) {
        return {};
      }
      const selectedIds = normalizeGroupSelection(state.scene, state.selectedIds);
      return withSceneMutation(state, (scene) => moveObjectsToLayer(scene, selectedIds, layerId), {
        history: true,
      });
    }),
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
  setSnapGuides: (guides) => set({ snapGuides: guides }),
  updatePreferences: (patch) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return withSceneMutation(
        state,
        (scene) => updateScenePreferences(scene, patch),
        { history: true }
      );
    }),
  generateRecreation: () =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      try {
        const result = compileTacticalRecreation(state.scene);
        return {
          scene: result.scene,
          history: pushHistorySnapshot(state.history, state.scene),
          dirty: true,
          revision: state.revision + 1,
          tacticalRecreation: result,
          tacticalRecreationToken: state.tacticalRecreationToken + 1,
          error: null,
        };
      } catch (error) {
        return {
          tacticalRecreation: null,
          error: error instanceof Error ? error.message : 'No se pudo generar la recreación táctica.',
        };
      }
    }),
  addTimelineKeyframe: (time, label) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      const sceneTime = typeof time === 'number' ? time : state.scene.timeline?.currentTime || 0;
      return withSceneMutation(
        state,
        (scene) => applyAnimationKeyframeCapture(scene, sceneTime, {
          label,
          objectIds: normalizeGroupSelection(scene, state.selectedIds).length
            ? normalizeGroupSelection(scene, state.selectedIds)
            : undefined,
          source: 'manual',
        }),
        { history: true }
      );
    }),
  removeTimelineKeyframe: (keyframeId) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return withSceneMutation(
        state,
        (scene) => removeAnimationKeyframe(scene, keyframeId),
        { history: true }
      );
    }),
  moveTimelineKeyframe: (keyframeId, time) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      return withSceneMutation(state, (scene) => moveAnimationKeyframe(scene, keyframeId, time), {
        history: true,
      });
    }),
  duplicateTimelineKeyframes: (keyframeIds, offset) =>
    set((state) => {
      if (!state.scene || !keyframeIds.length) {
        return {};
      }
      return withSceneMutation(
        state,
        (scene) => duplicateAnimationSelection(scene, keyframeIds, offset),
        { history: true }
      );
    }),
  setTimelineDuration: (duration) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      const timeline = state.scene.timeline ?? { duration: 0, currentTime: 0, keyframes: [], tracks: [], sequences: [], currentSequenceId: null };
      if (Math.abs(timeline.duration - duration) < 0.001) {
        return {};
      }
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          timeline: {
            ...(scene.timeline ?? { duration: 0, currentTime: 0, keyframes: [], tracks: [], sequences: [], currentSequenceId: null }),
            duration: Math.max(0, duration),
          },
        }),
        { history: true }
      );
    }),
  setTimelineTime: (time) =>
    set((state) => {
      if (!state.scene) {
        return {};
      }
      const timeline = state.scene.timeline ?? { duration: 0, currentTime: 0, keyframes: [], tracks: [], sequences: [], currentSequenceId: null };
      return withSceneMutation(
        state,
        (scene) => ({
          ...scene,
          timeline: {
            ...(scene.timeline ?? timeline),
            currentTime: Math.max(0, time),
          },
        }),
        { history: false }
      );
    }),
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
      activeAssetId: null,
      history: pushHistorySnapshot(state.history, state.scene || createDefaultScene('', '')),
      revision: state.revision + 1,
      tacticalRecreation: null,
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
