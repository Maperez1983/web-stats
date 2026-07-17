import Konva from 'konva';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { drawPitchLayer } from '../editor/pitch/PitchRenderer';
import { normalizeSelectionBox } from '../editor/core/SelectionManager';
import {
  isSelectableObject,
  projectSceneAtTime,
  snapObjectPosition,
  selectableObjects,
} from '../editor/core/editorOperations';
import { createKonvaNode } from '../editor/objects/ObjectRenderer';
import { useEditorStore } from '../store/editorStore';
import type { CanvasApi } from '../store/editorStore';
import type { SceneLayerId, SceneObject } from '../editor/core/sceneSchema';
import type { TacticalCanvasObject } from '../domain/taskDocument';
import { sceneToLegacyCanvasState } from '../editor/serialization/SceneSerializer';

type DragState = {
  id: string;
  offsetX: number;
  offsetY: number;
};

type StageMode = 'idle' | 'selecting' | 'panning' | 'dragging';

type NodeDragState = {
  id: string;
  ids: string[];
  anchorId: string;
  offsetX: number;
  offsetY: number;
  startPointerX: number;
  startPointerY: number;
  basePositions: Map<string, { x: number; y: number }>;
};

type SelectionBoxState = {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  additive: boolean;
} | null;

type ContextMenuState = {
  x: number;
  y: number;
} | null;

type StagePointerLikeEvent = {
  clientX: number;
  clientY: number;
  button?: number;
  shiftKey: boolean;
  metaKey?: boolean;
  ctrlKey?: boolean;
};

function layerOrder(sceneLayers: Array<{ id: SceneLayerId; order: number }>): SceneLayerId[] {
  return ['pitch', ...[...sceneLayers].sort((left, right) => left.order - right.order).map((layer) => layer.id)]
    .filter((layerId, index, all) => all.indexOf(layerId) === index) as SceneLayerId[];
}

function computeFitViewport(scene: {
  canvas: { width: number; height: number };
  viewport: { zoom: number; x: number; y: number };
} | null, width: number, height: number) {
  if (!scene || !width || !height) {
    return null;
  }
  const padding = Math.max(32, Math.round(Math.min(width, height) * 0.05));
  const availableWidth = Math.max(1, width - padding * 2);
  const availableHeight = Math.max(1, height - padding * 2);
  const scale = Math.min(availableWidth / scene.canvas.width, availableHeight / scene.canvas.height);
  const fittedWidth = scene.canvas.width * scale;
  const fittedHeight = scene.canvas.height * scale;
  return {
    zoom: scale,
    x: padding + (availableWidth - fittedWidth) / 2,
    y: padding + (availableHeight - fittedHeight) / 2,
  };
}

function resolveInteractiveNode(node: Konva.Node | null, nodeMap: Map<string, Konva.Node>) {
  let current: Konva.Node | null = node;
  while (current) {
    if (current.name() && nodeMap.has(current.name())) {
      return current;
    }
    current = current.getParent();
  }
  return null;
}

function findInteractiveNodeAtPointer(
  stage: Konva.Stage,
  pointer: { x: number; y: number },
  nodeMap: Map<string, Konva.Node>,
  orderedObjects: Array<{ id: string }>
) {
  const hit = resolveInteractiveNode(stage.getIntersection(pointer), nodeMap);
  if (hit) {
    return hit;
  }
  for (let index = orderedObjects.length - 1; index >= 0; index -= 1) {
    const object = orderedObjects[index];
    const node = nodeMap.get(object.id);
    if (!node) {
      continue;
    }
    const rect = node.getClientRect({ relativeTo: stage });
    if (
      pointer.x >= rect.x &&
      pointer.x <= rect.x + rect.width &&
      pointer.y >= rect.y &&
      pointer.y <= rect.y + rect.height
    ) {
      return node;
    }
  }
  return null;
}

function rectIntersectsBox(rect: { x: number; y: number; width: number; height: number }, box: {
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  return !(
    rect.x + rect.width < box.x ||
    rect.y + rect.height < box.y ||
    rect.x > box.x + box.width ||
    rect.y > box.y + box.height
  );
}

function pointerFromEvent(
  stage: Konva.Stage,
  container: HTMLDivElement,
  event: StagePointerLikeEvent
) {
  const pointer = stage.getPointerPosition();
  if (pointer) {
    return pointer;
  }
  const rect = container.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
}

function numberValue(value: unknown, fallback = 0): number {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function colorValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function objectId(object: TacticalCanvasObject, index: number): string {
  return String(object.id || object.name || object.data?.id || `obj-${index + 1}`);
}

function objectBounds(object: TacticalCanvasObject) {
  const scaleX = numberValue(object.scaleX, 1);
  const scaleY = numberValue(object.scaleY, 1);
  const width =
    object.type === 'circle'
      ? numberValue(object.radius, 18) * 2 * scaleX
      : Math.max(18, numberValue(object.width, 36) * scaleX);
  const height =
    object.type === 'circle'
      ? numberValue(object.radius, 18) * 2 * scaleY
      : Math.max(18, numberValue(object.height, 36) * scaleY);
  return {
    left: numberValue(object.left, 0),
    top: numberValue(object.top, 0),
    width,
    height,
  };
}

function renderCanvasObject(object: TacticalCanvasObject, index: number, selected: boolean) {
  const id = objectId(object, index);
  const bounds = objectBounds(object);
  const stroke = colorValue(object.stroke, selected ? '#38bdf8' : '#e2e8f0');
  const strokeWidth = selected ? 3 : Math.max(1, numberValue(object.strokeWidth, 2));
  const fill = colorValue(
    object.fill,
    object.type === 'line' ? 'transparent' : 'rgba(255,255,255,0.08)'
  );
  const angle = numberValue(object.angle, 0);
  const transform = angle
    ? `rotate(${angle} ${bounds.left + bounds.width / 2} ${bounds.top + bounds.height / 2})`
    : undefined;
  const common = {
    key: id,
    transform,
    opacity: numberValue(object.opacity, 1),
  };

  if (object.type === 'circle') {
    return (
      <ellipse
        {...common}
        cx={bounds.left + bounds.width / 2}
        cy={bounds.top + bounds.height / 2}
        rx={bounds.width / 2}
        ry={bounds.height / 2}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
    );
  }

  if (object.type === 'triangle') {
    const x = bounds.left;
    const y = bounds.top;
    const points = `${x + bounds.width / 2},${y} ${x + bounds.width},${y + bounds.height} ${x},${y + bounds.height}`;
    return (
      <polygon {...common} points={points} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
    );
  }

  if (object.type === 'line') {
    return (
      <line
        {...common}
        x1={bounds.left + numberValue(object.x1, 0)}
        y1={bounds.top + numberValue(object.y1, 0)}
        x2={bounds.left + numberValue(object.x2, bounds.width)}
        y2={bounds.top + numberValue(object.y2, 0)}
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
    );
  }

  if (object.type === 'textbox' || object.type === 'i-text' || object.type === 'text') {
    return (
      <text
        {...common}
        x={bounds.left}
        y={bounds.top + Math.max(18, bounds.height * 0.75)}
        fill={colorValue(object.fill, '#f8fafc')}
        fontSize={Math.max(14, numberValue(object.fontSize, 18))}
        fontWeight={700}
      >
        {String(object.text || 'Texto')}
      </text>
    );
  }

  if (
    (object.type === 'image' || object.type === 'sprite') &&
    typeof object.src === 'string' &&
    object.src
  ) {
    return (
      <image
        {...common}
        href={object.src}
        x={bounds.left}
        y={bounds.top}
        width={bounds.width}
        height={bounds.height}
        preserveAspectRatio="xMidYMid meet"
      />
    );
  }

  return (
    <rect
      {...common}
      x={bounds.left}
      y={bounds.top}
      width={bounds.width}
      height={bounds.height}
      rx={Math.min(12, bounds.width * 0.18)}
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
    />
  );
}

function LegacyCanvasViewport() {
  const document = useEditorStore((state) => state.document);
  const activeViewport = useEditorStore((state) => state.activeViewport);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const selectSingle = useEditorStore((state) => state.selectSingle);
  const scene = useEditorStore((state) => state.scene);
  const error = useEditorStore((state) => state.error);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  const legacyState = useMemo(() => (scene ? sceneToLegacyCanvasState(scene) : null), [scene]);
  const previewImageUrl =
    activeViewport === 'board3d'
      ? document?.graphic.preview_3d_url || document?.graphic.preview_2d_url
      : activeViewport === 'uefa'
        ? document?.ai.preview_url || document?.graphic.preview_2d_url
        : undefined;
  const boardObjects = useMemo(
    () => (Array.isArray(legacyState?.objects) ? legacyState.objects : []),
    [legacyState]
  );
  const canvasWidth = scene?.canvas.width || document?.graphic.canvas_width || 1280;
  const canvasHeight = scene?.canvas.height || document?.graphic.canvas_height || 720;
  const embed3dUrl = document?.graphic.preview_3d_embed_url || '';

  useEffect(() => {
    if (
      activeViewport !== 'board3d' ||
      !embed3dUrl ||
      !iframeRef.current?.contentWindow ||
      !legacyState
    ) {
      return;
    }
    iframeRef.current.contentWindow.postMessage(
      {
        type: 'task-editor-sync-3d',
        canvasState: legacyState,
        canvasWidth,
        canvasHeight,
        animationFrames: [],
      },
      '*'
    );
  }, [activeViewport, embed3dUrl, legacyState, canvasWidth, canvasHeight]);

  const beginDrag = (
    event: ReactPointerEvent<SVGRectElement>,
    object: TacticalCanvasObject,
    index: number
  ) => {
    if (activeViewport !== 'board2d' || !svgRef.current) {
      return;
    }
    const id = objectId(object, index);
    const bounds = objectBounds(object);
    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = canvasWidth / Math.max(rect.width, 1);
    const scaleY = canvasHeight / Math.max(rect.height, 1);
    selectSingle(id);
    setDragState({
      id,
      offsetX: (event.clientX - rect.left) * scaleX - bounds.left,
      offsetY: (event.clientY - rect.top) * scaleY - bounds.top,
    });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!dragState || !svgRef.current || !scene) {
      return;
    }
    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = canvasWidth / Math.max(rect.width, 1);
    const scaleY = canvasHeight / Math.max(rect.height, 1);
    const nextLeft = Math.max(0, (event.clientX - rect.left) * scaleX - dragState.offsetX);
    const nextTop = Math.max(0, (event.clientY - rect.top) * scaleY - dragState.offsetY);
    useEditorStore.getState().patchSceneObject(dragState.id, { x: nextLeft, y: nextTop });
  };

  const endDrag = () => setDragState(null);

  return (
    <section className="te-panel te-canvas">
      <div className="te-panel-head">
        <h2>Canvas central</h2>
        <span>Legacy fallback</span>
      </div>
      <div className="te-canvas-stage">
        {activeViewport === 'board2d' ? (
          <svg
            ref={svgRef}
            className="te-board-svg"
            viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
            onPointerMove={handlePointerMove}
            onPointerUp={endDrag}
            onPointerLeave={endDrag}
            onClick={() => selectSingle(null)}
          >
            <rect x="0" y="0" width={canvasWidth} height={canvasHeight} fill="#0a3b1e" />
            {previewImageUrl ? (
              <image
                href={previewImageUrl}
                x="0"
                y="0"
                width={canvasWidth}
                height={canvasHeight}
                preserveAspectRatio="none"
                opacity="0.88"
              />
            ) : null}
            {boardObjects.map((object, index) => {
              const id = objectId(object, index);
              const bounds = objectBounds(object);
              const isSelected = selectedIds.includes(id);
              return (
                <g key={`layer-${id}`}>
                  {renderCanvasObject(object, index, isSelected)}
                  <rect
                    x={bounds.left}
                    y={bounds.top}
                    width={Math.max(18, bounds.width)}
                    height={Math.max(18, bounds.height)}
                    fill="transparent"
                    stroke={isSelected ? '#38bdf8' : 'transparent'}
                    strokeWidth={isSelected ? 2 : 0}
                    onPointerDown={(event) => beginDrag(event, object, index)}
                  />
                </g>
              );
            })}
          </svg>
        ) : activeViewport === 'board3d' && embed3dUrl ? (
          <iframe
            ref={iframeRef}
            src={embed3dUrl}
            title="Vista 3D sincronizada"
            className="te-canvas-iframe"
          />
        ) : previewImageUrl ? (
          <img src={previewImageUrl} alt="Preview tactica" className="te-canvas-image" />
        ) : null}
        <div className="te-canvas-overlay">
          <strong>Modo legacy</strong>
          <span>Activa `?editor2d=1` para usar el motor Konva de la nueva base profesional.</span>
          {error ? <span className="te-error-text">{error}</span> : null}
        </div>
      </div>
    </section>
  );
}

function sceneObjectFromNode(object: SceneObject, node: Konva.Node): SceneObject {
  const scaleX = node.scaleX();
  const scaleY = node.scaleY();
  const nextData = { ...object.data };
  if (Array.isArray(object.data.points)) {
    nextData.points = object.data.points.map(
      (value, index) => Number(value) * (index % 2 === 0 ? scaleX : scaleY)
    );
  }
  return {
    ...object,
    x: node.x(),
    y: node.y(),
    width: Math.max(4, object.width * scaleX),
    height: Math.max(4, object.height * scaleY),
    rotation: node.rotation(),
    scaleX: 1,
    scaleY: 1,
    data: nextData,
  };
}

export function CanvasViewport() {
  const featureEnabled = useEditorStore((state) => state.featureEnabled);
  const document = useEditorStore((state) => state.document);
  const activeViewport = useEditorStore((state) => state.activeViewport);
  const activeTool = useEditorStore((state) => state.activeTool);
  const scene = useEditorStore((state) => state.scene);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const snapGuides = useEditorStore((state) => state.snapGuides);
  const error = useEditorStore((state) => state.error);
  const selectSingle = useEditorStore((state) => state.selectSingle);
  const setSelection = useEditorStore((state) => state.setSelection);
  const toggleObjectSelection = useEditorStore((state) => state.toggleObjectSelection);
  const addSceneObject = useEditorStore((state) => state.addSceneObject);
  const replaceSceneObject = useEditorStore((state) => state.replaceSceneObject);
  const copySelectedObjects = useEditorStore((state) => state.copySelectedObjects);
  const pasteClipboard = useEditorStore((state) => state.pasteClipboard);
  const duplicateSelectedObjects = useEditorStore((state) => state.duplicateSelectedObjects);
  const removeSelectedObjects = useEditorStore((state) => state.removeSelectedObjects);
  const setSelectionVisibility = useEditorStore((state) => state.setSelectionVisibility);
  const setSelectionLock = useEditorStore((state) => state.setSelectionLock);
  const moveSelectionToLayer = useEditorStore((state) => state.moveSelectionToLayer);
  const groupSelected = useEditorStore((state) => state.groupSelected);
  const ungroupSelected = useEditorStore((state) => state.ungroupSelected);
  const reorderSelected = useEditorStore((state) => state.reorderSelected);
  const setSnapGuides = useEditorStore((state) => state.setSnapGuides);
  const setInspector = useEditorStore((state) => state.setInspector);
  const beginTransaction = useEditorStore((state) => state.beginTransaction);
  const commitTransaction = useEditorStore((state) => state.commitTransaction);
  const setSceneViewport = useEditorStore((state) => state.setSceneViewport);
  const setCanvasApi = useEditorStore((state) => state.setCanvasApi);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const layersRef = useRef<Record<string, Konva.Layer>>({});
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const selectionRectRef = useRef<Konva.Rect | null>(null);
  const snapGuideGroupRef = useRef<Konva.Group | null>(null);
  const nodeMapRef = useRef(new Map<string, Konva.Node>());
  const sizeRef = useRef({ width: 0, height: 0 });
  const stageModeRef = useRef<StageMode>('idle');
  const nodeDragRef = useRef<NodeDragState | null>(null);
  const dragSelectionRef = useRef<SelectionBoxState>(null);
  const panOriginRef = useRef<{
    x: number;
    y: number;
    viewportX: number;
    viewportY: number;
  } | null>(null);
  const isSpacePressedRef = useRef(false);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null);
  const lastAutoFitSignatureRef = useRef<string>('');
  const contextMenuRef = useRef<HTMLDivElement | null>(null);
  const previewImageUrl = document?.graphic.preview_2d_url || document?.ai.preview_url || '';
  const embed3dUrl = document?.graphic.preview_3d_embed_url || '';
  const renderScene = useMemo(
    () => (scene ? projectSceneAtTime(scene, scene.timeline.currentTime) : null),
    [scene]
  );

  useEffect(() => {
    if (!featureEnabled || !containerRef.current) {
      return undefined;
    }
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const width = Math.max(1, Math.round(entry.contentRect.width));
      const height = Math.max(1, Math.round(entry.contentRect.height));
      setContainerSize({ width, height });
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, [featureEnabled]);

  useEffect(() => {
    if (!featureEnabled || !containerRef.current) {
      return;
    }
    const rect = containerRef.current.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }
    setContainerSize({
      width: Math.max(1, Math.round(rect.width)),
      height: Math.max(1, Math.round(rect.height)),
    });
  }, [featureEnabled, activeViewport]);

  useEffect(() => {
    if (
      !featureEnabled ||
      !containerRef.current ||
      stageRef.current ||
      !containerSize.width ||
      !containerSize.height
    ) {
      return undefined;
    }
    const stage = new Konva.Stage({
      container: containerRef.current,
      width: containerSize.width,
      height: containerSize.height,
    });
    stageRef.current = stage;
    sizeRef.current = containerSize;

    const pitchLayer = new Konva.Layer();
    const zonesLayer = new Konva.Layer();
    const pathsLayer = new Konva.Layer();
    const equipmentLayer = new Konva.Layer();
    const playersLayer = new Konva.Layer();
    const ballLayer = new Konva.Layer();
    const textsLayer = new Konva.Layer();
    const annotationsLayer = new Konva.Layer();
    const uiLayer = new Konva.Layer();
    const snapGuideGroup = new Konva.Group({
      visible: false,
      listening: false,
    });
    const transformer = new Konva.Transformer({
      rotateEnabled: true,
      enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right'],
      borderStroke: '#38bdf8',
      anchorStroke: '#38bdf8',
      anchorFill: '#020617',
      anchorSize: 8,
      ignoreStroke: true,
    });
    const selectionRect = new Konva.Rect({
      fill: 'rgba(56,189,248,0.14)',
      stroke: '#38bdf8',
      strokeWidth: 1,
      dash: [10, 6],
      visible: false,
      listening: false,
    });

    uiLayer.add(selectionRect);
    uiLayer.add(snapGuideGroup);
    uiLayer.add(transformer);
    stage.add(
      pitchLayer,
      zonesLayer,
      pathsLayer,
      equipmentLayer,
      playersLayer,
      ballLayer,
      textsLayer,
      annotationsLayer,
      uiLayer
    );
    layersRef.current = {
      pitch: pitchLayer,
      zones: zonesLayer,
      paths: pathsLayer,
      equipment: equipmentLayer,
      players: playersLayer,
      ball: ballLayer,
      texts: textsLayer,
      annotations: annotationsLayer,
      ui: uiLayer,
    };
    transformerRef.current = transformer;
    selectionRectRef.current = selectionRect;
    snapGuideGroupRef.current = snapGuideGroup;

    const handleMouseDown = (event: Konva.KonvaEventObject<MouseEvent>) => {
      handleStagePointerDown(event.evt as StagePointerLikeEvent);
    };
    const handleMouseMove = (event: Konva.KonvaEventObject<MouseEvent>) => {
      handleStagePointerMove(event.evt as StagePointerLikeEvent);
    };
    const handleMouseUp = (event: Konva.KonvaEventObject<MouseEvent>) => {
      handleStagePointerUp(event.evt as StagePointerLikeEvent);
    };

    stage.on('mousedown', handleMouseDown);
    stage.on('mousemove', handleMouseMove);
    stage.on('mouseup', handleMouseUp);

    return () => {
      stage.off('mousedown', handleMouseDown);
      stage.off('mousemove', handleMouseMove);
      stage.off('mouseup', handleMouseUp);
      stage.destroy();
      stageRef.current = null;
      nodeMapRef.current.clear();
      layersRef.current = {};
      transformerRef.current = null;
      selectionRectRef.current = null;
      snapGuideGroupRef.current = null;
    };
  }, [featureEnabled, containerSize]);

  useEffect(() => {
    if (!featureEnabled || !stageRef.current || !scene) {
      return;
    }
    if (containerSize.width && containerSize.height) {
      stageRef.current.size(containerSize);
    }
  }, [featureEnabled, containerSize, scene]);

  const fitToScene = useCallback(() => {
    const currentScene = useEditorStore.getState().scene;
    if (!currentScene || !containerSize.width || !containerSize.height) {
      return;
    }
    const viewport = computeFitViewport(currentScene, containerSize.width, containerSize.height);
    if (!viewport) {
      return;
    }
    setSceneViewport(viewport);
  }, [containerSize.width, containerSize.height, setSceneViewport]);

  useEffect(() => {
    if (!featureEnabled) {
      return;
    }
    const canvasApi: CanvasApi = {
      exportPngDataUrl: (options) => {
        const stage = stageRef.current;
        const transformer = transformerRef.current;
        const selectionRect = selectionRectRef.current;
        const snapGuideGroup = snapGuideGroupRef.current;
        if (!stage) return null;
        const previousTransformerVisible = transformer?.visible() ?? false;
        const previousSelectionVisible = selectionRect?.visible() ?? false;
        const previousGuidesVisible = snapGuideGroup?.visible() ?? false;
        if (!options?.includeUi) {
          transformer?.hide();
          selectionRect?.hide();
          snapGuideGroup?.hide();
        }
        const dataUrl = stage.toDataURL({
          pixelRatio: options?.pixelRatio || 2,
          mimeType: 'image/png',
        });
        if (!options?.includeUi) {
          if (previousTransformerVisible) transformer?.show();
          if (previousSelectionVisible) selectionRect?.show();
          if (previousGuidesVisible) snapGuideGroup?.show();
          layersRef.current.ui?.batchDraw();
        }
        return dataUrl;
      },
      fitToScene,
    };
    setCanvasApi(canvasApi);
    return () => {
      setCanvasApi(null);
    };
  }, [featureEnabled, fitToScene, setCanvasApi]);

  useEffect(() => {
    if (!featureEnabled || !scene || !containerSize.width || !containerSize.height) {
      return;
    }
    const signature = `${scene.documentId}:${scene.canvas.width}x${scene.canvas.height}:${containerSize.width}x${containerSize.height}`;
    if (lastAutoFitSignatureRef.current === signature) {
      return;
    }
    lastAutoFitSignatureRef.current = signature;
    fitToScene();
  }, [featureEnabled, scene?.documentId, scene?.canvas.width, scene?.canvas.height, containerSize.width, containerSize.height, fitToScene]);

  useEffect(() => {
    if (!featureEnabled || !renderScene || !stageRef.current) {
      return;
    }
    if (stageModeRef.current === 'dragging' && nodeDragRef.current) {
      return;
    }

    layerOrder(renderScene.layers).forEach((layerId) => {
      const layer = layersRef.current[layerId];
      if (!layer) return;
      layer.position({ x: renderScene.viewport.x, y: renderScene.viewport.y });
      layer.scale({ x: renderScene.viewport.zoom, y: renderScene.viewport.zoom });
    });
    drawPitchLayer(layersRef.current.pitch, renderScene);
    const layerMeta = new Map(renderScene.layers.map((layer) => [layer.id, layer]));
    nodeMapRef.current.clear();

    layerOrder(renderScene.layers).forEach((layerId) => {
      if (layerId === 'pitch') return;
      const layer = layersRef.current[layerId];
      if (!layer) return;
      layer.destroyChildren();
    });

    renderScene.objects
      .slice()
      .sort((a, b) => {
        const layerA = layerMeta.get(a.layerId)?.order ?? 0;
        const layerB = layerMeta.get(b.layerId)?.order ?? 0;
        if (layerA !== layerB) return layerA - layerB;
        return a.zIndex - b.zIndex;
      })
      .forEach((object) => {
        const layerInfo = layerMeta.get(object.layerId);
        if (!layerInfo?.visible) return;
        const layer = layersRef.current[object.layerId];
        if (!layer) return;
        const node = createKonvaNode({
          ...object,
          locked: object.locked || Boolean(layerInfo.locked),
        });
        node.draggable(!(object.locked || Boolean(layerInfo.locked)));
        node.on('mousedown touchstart', (event) => {
          const additive = Boolean(event.evt.shiftKey || event.evt.metaKey || event.evt.ctrlKey);
          const currentStore = useEditorStore.getState();
          if (additive) {
            toggleObjectSelection(object.id, true);
            return;
          }
          if (currentStore.selectedIds.includes(object.id) && currentStore.selectedIds.length > 1) {
            return;
          }
          currentStore.selectSingle(object.id);
        });
        node.on('dragstart', () => {
          stageModeRef.current = 'dragging';
          beginTransaction();
          const currentStore = useEditorStore.getState();
          const selectedIds = currentStore.scene
            ? selectableObjects(renderScene)
                .map((item) => item.id)
                .filter((id) => currentStore.selectedIds.includes(id))
            : [object.id];
          const ids = selectedIds.includes(object.id) && selectedIds.length > 1 ? selectedIds : [object.id];
          const basePositions = new Map(
            ids.map((id) => {
              const current = currentStore.scene?.objects.find((item) => item.id === id);
              return [id, { x: current?.x ?? 0, y: current?.y ?? 0 }];
            })
          );
          nodeDragRef.current = {
            id: object.id,
            ids,
            anchorId: object.id,
            offsetX: node.x() - object.x,
            offsetY: node.y() - object.y,
            startPointerX: node.x(),
            startPointerY: node.y(),
            basePositions,
          };
        });
        node.on('dragmove', (dragEvent) => {
          const drag = nodeDragRef.current;
          const currentStore = useEditorStore.getState();
          const currentScene = currentStore.scene;
          if (!drag || !currentScene) {
            replaceSceneObject(object.id, sceneObjectFromNode(object, node), { history: false });
            return;
          }
          const anchorBase = drag.basePositions.get(drag.anchorId) || { x: object.x, y: object.y };
          const anchorObject = currentScene.objects.find((item) => item.id === drag.anchorId);
          const snapped = anchorObject
            ? snapObjectPosition(
                currentScene,
                {
                  ...anchorObject,
                  x: node.x(),
                  y: node.y(),
                },
                currentScene.metadata.preferences,
                { movingIds: drag.ids, ignore: Boolean(dragEvent.evt.altKey) }
              )
            : { x: node.x(), y: node.y(), guides: [] };
          const deltaX = snapped.x - anchorBase.x;
          const deltaY = snapped.y - anchorBase.y;
          setSnapGuides(snapped.guides);
          drag.ids.forEach((id) => {
            const base = drag.basePositions.get(id);
            const item = currentScene.objects.find((entry) => entry.id === id);
            if (!base || !item) {
              return;
            }
            const nextNode = nodeMapRef.current.get(id);
            const nextX = base.x + deltaX;
            const nextY = base.y + deltaY;
            if (nextNode) {
              nextNode.position({ x: nextX, y: nextY });
            }
            replaceSceneObject(
              id,
              {
                ...item,
                x: nextX,
                y: nextY,
              },
              { history: false }
            );
          });
        });
        node.on('dragend', () => {
          const drag = nodeDragRef.current;
          const currentStore = useEditorStore.getState();
          if (drag && currentStore.scene) {
            drag.ids.forEach((id) => {
              const item = currentStore.scene?.objects.find((entry) => entry.id === id);
              const nextNode = nodeMapRef.current.get(id);
              if (item && nextNode) {
                replaceSceneObject(id, sceneObjectFromNode(item, nextNode), { history: false });
              }
            });
          } else {
            replaceSceneObject(object.id, sceneObjectFromNode(object, node), { history: false });
          }
          setSnapGuides([]);
          commitTransaction();
          stageModeRef.current = 'idle';
        });
        node.on('transformstart', () => beginTransaction());
        node.on('transformend', () => {
          replaceSceneObject(object.id, sceneObjectFromNode(object, node), { history: false });
          commitTransaction();
        });
        layer.add(node);
        nodeMapRef.current.set(object.id, node);
      });

    layerOrder(renderScene.layers).forEach((layerId) => {
      if (layerId === 'pitch') return;
      layersRef.current[layerId]?.batchDraw();
    });
    layersRef.current.ui?.batchDraw();
  }, [
    featureEnabled,
    renderScene,
    toggleObjectSelection,
    beginTransaction,
    commitTransaction,
    replaceSceneObject,
    setSnapGuides,
  ]);

  useEffect(() => {
    if (!featureEnabled || !scene) {
      return;
    }
    const nodes = selectedIds
      .map((id) => nodeMapRef.current.get(id))
      .filter((node): node is Konva.Node => Boolean(node));
    transformerRef.current?.nodes(nodes);
    layersRef.current.ui?.batchDraw();
  }, [featureEnabled, selectedIds, scene]);

  useEffect(() => {
    if (!featureEnabled || !scene || !stageRef.current) {
      return;
    }
    const guideGroup = snapGuideGroupRef.current;
    if (!guideGroup) {
      return;
    }
    guideGroup.destroyChildren();
    const showGuides = Boolean(scene.metadata.preferences.showGuides);
    if (showGuides && snapGuides.length) {
      snapGuides.forEach((guide) => {
        guideGroup.add(
          new Konva.Line({
            points: [guide.x1, guide.y1, guide.x2, guide.y2],
            stroke: '#f59e0b',
            strokeWidth: 1.5,
            dash: [10, 6],
            opacity: 0.92,
            listening: false,
          })
        );
      });
      guideGroup.visible(true);
    } else {
      guideGroup.visible(false);
    }
    layersRef.current.ui?.batchDraw();
  }, [featureEnabled, scene?.metadata.preferences.showGuides, snapGuides]);

  useEffect(() => {
    if (!featureEnabled || !stageRef.current) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === ' ') {
        isSpacePressedRef.current = true;
      }
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === ' ') {
        isSpacePressedRef.current = false;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [featureEnabled]);

  useEffect(() => {
    if (!contextMenu) {
      return undefined;
    }
    const closeMenu = (event: MouseEvent) => {
      if (contextMenuRef.current && event.target instanceof Node && contextMenuRef.current.contains(event.target)) {
        return;
      }
      setContextMenu(null);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setContextMenu(null);
      }
    };
    window.addEventListener('mousedown', closeMenu, true);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('mousedown', closeMenu, true);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [contextMenu]);

  useEffect(() => {
    if (!featureEnabled || !scene || !stageRef.current) {
      return;
    }
    const stage = stageRef.current;
    const handleWheel = (event: Konva.KonvaEventObject<WheelEvent>) => {
      event.evt.preventDefault();
      const pointer = stage.getPointerPosition();
      if (!pointer) return;
      const oldZoom = scene.viewport.zoom;
      const pointerTo = {
        x: (pointer.x - scene.viewport.x) / oldZoom,
        y: (pointer.y - scene.viewport.y) / oldZoom,
      };
      const direction = event.evt.deltaY > 0 ? -1 : 1;
      const nextZoom = Math.min(4, Math.max(0.35, oldZoom * (direction > 0 ? 1.08 : 0.92)));
      const x = pointer.x - pointerTo.x * nextZoom;
      const y = pointer.y - pointerTo.y * nextZoom;
      setSceneViewport({ zoom: nextZoom, x, y });
    };
    stage.on('wheel', handleWheel);
    return () => {
      stage.off('wheel', handleWheel);
    };
  }, [featureEnabled, scene, setSceneViewport]);

  const handleStagePointerDown = useCallback(
    (event: StagePointerLikeEvent) => {
      const store = useEditorStore.getState();
      if (!store.featureEnabled || !stageRef.current || !store.scene || store.activeViewport !== 'board2d') {
        return;
      }
      if (event.button === 2) {
        return;
      }
      const stage = stageRef.current;
      const container = containerRef.current;
      if (!container) return;
      const pointer = pointerFromEvent(stage, container, event);
      if (!pointer) return;
      const target = findInteractiveNodeAtPointer(
        stage,
        pointer,
        nodeMapRef.current,
        store.scene.objects
      );
      if (store.activeTool !== 'select' && store.activeTool !== 'pan') {
        const scenePoint = {
          x: (pointer.x - store.scene.viewport.x) / store.scene.viewport.zoom,
          y: (pointer.y - store.scene.viewport.y) / store.scene.viewport.zoom,
        };
        store.addSceneObject(store.activeTool as SceneObject['type'], {
          x: scenePoint.x - 20,
          y: scenePoint.y - 20,
        });
        return;
      }
      if (store.activeTool === 'pan' || isSpacePressedRef.current) {
        stageModeRef.current = 'panning';
        panOriginRef.current = {
          x: event.clientX,
          y: event.clientY,
          viewportX: store.scene.viewport.x,
          viewportY: store.scene.viewport.y,
        };
        return;
      }
      if (target) {
        const objectId = String(target.name());
        const node = nodeMapRef.current.get(objectId);
        const object = store.scene.objects.find((item) => item.id === objectId);
        if (node && object && !object.locked) {
          const scenePoint = {
            x: (pointer.x - store.scene.viewport.x) / store.scene.viewport.zoom,
            y: (pointer.y - store.scene.viewport.y) / store.scene.viewport.zoom,
          };
          stageModeRef.current = 'dragging';
          nodeDragRef.current = {
            id: objectId,
            ids: [objectId],
            anchorId: objectId,
            offsetX: scenePoint.x - node.x(),
            offsetY: scenePoint.y - node.y(),
            startPointerX: scenePoint.x,
            startPointerY: scenePoint.y,
            basePositions: new Map([[objectId, { x: node.x(), y: node.y() }]]),
          };
          beginTransaction();
        }
        return;
      }
      setContextMenu(null);
      stageModeRef.current = 'selecting';
      dragSelectionRef.current = {
        startX: pointer.x,
        startY: pointer.y,
        endX: pointer.x,
        endY: pointer.y,
        additive: Boolean(event.shiftKey || event.metaKey || event.ctrlKey),
      };
      if (selectionRectRef.current) {
        selectionRectRef.current.visible(true);
        selectionRectRef.current.position({ x: pointer.x, y: pointer.y });
        selectionRectRef.current.size({ width: 0, height: 0 });
        layersRef.current.ui?.batchDraw();
      }
      if (!(event.shiftKey || event.metaKey || event.ctrlKey)) {
        store.selectSingle(null);
      }
    },
    []
  );

  const openContextMenu = useCallback(
    (event: StagePointerLikeEvent) => {
      const store = useEditorStore.getState();
      if (!store.featureEnabled || !store.scene || store.activeViewport !== 'board2d') {
        return;
      }
      const stage = stageRef.current;
      const container = containerRef.current;
      if (!stage || !container) return;
      const pointer = pointerFromEvent(stage, container, event);
      if (!pointer) return;
      const target = findInteractiveNodeAtPointer(
        stage,
        pointer,
        nodeMapRef.current,
        store.scene.objects
      );
      if (target) {
        const objectId = String(target.name());
        const object = store.scene.objects.find((item) => item.id === objectId);
        if (object && isSelectableObject(store.scene, object) && !store.selectedIds.includes(objectId)) {
          store.selectSingle(objectId);
        }
      } else if (!event.shiftKey && !event.metaKey && !event.ctrlKey) {
        store.selectSingle(null);
      }
      setContextMenu({
        x: Math.min(pointer.x + 8, Math.max(8, container.clientWidth - 260)),
        y: Math.min(pointer.y + 8, Math.max(8, container.clientHeight - 260)),
      });
    },
    []
  );

  const handleStagePointerMove = useCallback(
    (event: StagePointerLikeEvent) => {
      const store = useEditorStore.getState();
      if (!store.featureEnabled || !store.scene || !stageRef.current || store.activeViewport !== 'board2d') {
        return;
      }
      const stage = stageRef.current;
      const container = containerRef.current;
      if (!container) return;
      const pointer = pointerFromEvent(stage, container, event);
      if (!pointer) return;
      if (stageModeRef.current === 'panning' && panOriginRef.current) {
        const dx = event.clientX - panOriginRef.current.x;
        const dy = event.clientY - panOriginRef.current.y;
        store.setSceneViewport({
          x: panOriginRef.current.viewportX + dx,
          y: panOriginRef.current.viewportY + dy,
        });
        return;
      }
      if (stageModeRef.current === 'dragging' && nodeDragRef.current) {
        const drag = nodeDragRef.current;
        const node = nodeMapRef.current.get(drag.id);
        if (!node) return;
        const object = store.scene.objects.find((item) => item.id === drag.id);
        const scenePoint = {
          x: (pointer.x - store.scene.viewport.x) / store.scene.viewport.zoom,
          y: (pointer.y - store.scene.viewport.y) / store.scene.viewport.zoom,
        };
        node.position({
          x: scenePoint.x - drag.offsetX,
          y: scenePoint.y - drag.offsetY,
        });
        node.getLayer()?.batchDraw();
        if (object) {
          replaceSceneObject(drag.id, sceneObjectFromNode(object, node), { history: false });
        }
        return;
      }
      if (
        stageModeRef.current !== 'selecting' ||
        !dragSelectionRef.current ||
        !selectionRectRef.current
      ) {
        return;
      }
      dragSelectionRef.current = {
        ...dragSelectionRef.current,
        endX: pointer.x,
        endY: pointer.y,
      };
      const normalized = normalizeSelectionBox({
        x: dragSelectionRef.current.startX,
        y: dragSelectionRef.current.startY,
        width: dragSelectionRef.current.endX - dragSelectionRef.current.startX,
        height: dragSelectionRef.current.endY - dragSelectionRef.current.startY,
      });
      selectionRectRef.current.position({ x: normalized.x, y: normalized.y });
      selectionRectRef.current.size({ width: normalized.width, height: normalized.height });
      layersRef.current.ui?.batchDraw();
    },
    []
  );

  const handleStagePointerUp = useCallback(
    (event: StagePointerLikeEvent) => {
      const store = useEditorStore.getState();
      if (!store.featureEnabled || !store.scene || store.activeViewport !== 'board2d') {
        return;
      }
      if (stageModeRef.current === 'selecting' && dragSelectionRef.current) {
        const stage = stageRef.current;
        if (!stage) return;
        const normalizedScreen = normalizeSelectionBox({
          x: dragSelectionRef.current.startX,
          y: dragSelectionRef.current.startY,
          width: dragSelectionRef.current.endX - dragSelectionRef.current.startX,
          height: dragSelectionRef.current.endY - dragSelectionRef.current.startY,
        });
        const selectableIds = new Set(selectableObjects(store.scene).map((object) => object.id));
        const ids = store.scene.objects
          .filter((object) => selectableIds.has(object.id))
          .map((object) => nodeMapRef.current.get(object.id))
          .filter((node): node is Konva.Node => Boolean(node))
          .filter((node) =>
            rectIntersectsBox(node.getClientRect({ relativeTo: stage }), normalizedScreen)
          )
          .map((node) => String(node.name()))
          .filter(Boolean);
        const nextSelection = dragSelectionRef.current.additive
          ? [...new Set([...store.selectedIds, ...ids])]
          : ids;
        store.setSelection(nextSelection);
      }
      if (stageModeRef.current === 'dragging' && nodeDragRef.current) {
        const drag = nodeDragRef.current;
        const node = nodeMapRef.current.get(drag.anchorId);
        const object = store.scene.objects.find((item) => item.id === drag.anchorId);
        if (node && object) {
          replaceSceneObject(drag.anchorId, sceneObjectFromNode(object, node), { history: false });
        }
        commitTransaction();
      }
      stageModeRef.current = 'idle';
      panOriginRef.current = null;
      nodeDragRef.current = null;
      dragSelectionRef.current = null;
      setSnapGuides([]);
      if (selectionRectRef.current) {
        selectionRectRef.current.visible(false);
        layersRef.current.ui?.batchDraw();
      }
    },
    []
  );

  const boardObjectsCount = renderScene?.objects.length || 0;
  const selectedLayerId = scene && selectedIds.length
    ? scene.objects.find((object) => object.id === selectedIds[0])?.layerId || 'players'
    : 'players';

  const handleMoveToLayer = () => {
    const store = useEditorStore.getState();
    if (!store.selectedIds.length || !store.scene) {
      return;
    }
    const targetLayer = window.prompt(
      'Mover selección a capa',
      String(
        store.scene.objects.find((object) => object.id === store.selectedIds[0])?.layerId ||
          selectedLayerId
      )
    );
    if (!targetLayer) {
      return;
    }
    moveSelectionToLayer(targetLayer as SceneLayerId);
    setContextMenu(null);
  };

  if (!featureEnabled) {
    return <LegacyCanvasViewport />;
  }

  return (
    <section className="te-panel te-canvas">
      <div className="te-panel-head">
        <h2>Campo táctico</h2>
        <span>Konva · esquema v1 · {scene?.pitch.type || 'full'}</span>
      </div>
      <div
        ref={containerRef}
        className={`te-canvas-stage te-konva-stage ${activeViewport === 'board2d' ? '' : 'is-hidden'}`}
        onContextMenu={(event) => {
          event.preventDefault();
          openContextMenu({
            clientX: event.clientX,
            clientY: event.clientY,
            shiftKey: event.shiftKey,
            metaKey: event.metaKey,
            ctrlKey: event.ctrlKey,
          });
        }}
      />
      {activeViewport === 'board3d' && embed3dUrl ? (
        <iframe
          src={embed3dUrl}
          title="Vista 3D sincronizada"
          className="te-canvas-iframe te-canvas-alt"
        />
      ) : null}
      {activeViewport === 'uefa' && previewImageUrl ? (
        <img
          src={previewImageUrl}
          alt="Vista de presentación"
          className="te-canvas-image te-canvas-alt"
        />
      ) : null}
      <div className="te-canvas-overlay">
        <strong>Editor 2D profesional</strong>
        <span>
          {activeViewport === 'board2d'
            ? 'Canvas modular con capas, selección, zoom, paneo y persistencia sobre el mismo `canvas_state` legado.'
            : activeViewport === 'board3d'
              ? 'La vista 3D sigue consumiendo la misma escena guardada y el embed actual del sistema.'
              : 'La ficha sigue usando la preview persistida del backend para mantener compatibilidad.'}
        </span>
        {error ? <span className="te-error-text">{error}</span> : null}
      </div>
      <div className="te-canvas-footer">
        <div className="te-stat-card">
          <strong>Objetos</strong>
          <span>{boardObjectsCount} elementos en escena</span>
        </div>
        <div className="te-stat-card">
          <strong>Selección</strong>
          <span>{selectedIds.length ? `${selectedIds.length} activos` : 'Sin selección'}</span>
        </div>
        <div className="te-stat-card">
          <strong>3D</strong>
          <span>{document?.graphic.preview_3d_embed_url ? 'Sincronizable' : 'Pendiente'}</span>
        </div>
      </div>
      {contextMenu ? (
        <div
          ref={contextMenuRef}
          className="te-context-menu"
          style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
          onContextMenu={(event) => event.preventDefault()}
        >
          <button
            type="button"
            onClick={() => {
              copySelectedObjects();
              setContextMenu(null);
            }}
          >
            Copiar
          </button>
          <button
            type="button"
            onClick={() => {
              pasteClipboard();
              setContextMenu(null);
            }}
          >
            Pegar
          </button>
          <button
            type="button"
            onClick={() => {
              duplicateSelectedObjects();
              setContextMenu(null);
            }}
          >
            Duplicar
          </button>
          <button
            type="button"
            onClick={() => {
              removeSelectedObjects();
              setContextMenu(null);
            }}
          >
            Eliminar
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectionLock(true);
              setContextMenu(null);
            }}
          >
            Bloquear
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectionVisibility(false);
              setContextMenu(null);
            }}
          >
            Ocultar
          </button>
          <button
            type="button"
            onClick={() => {
              groupSelected();
              setContextMenu(null);
            }}
          >
            Agrupar
          </button>
          <button
            type="button"
            onClick={() => {
              ungroupSelected();
              setContextMenu(null);
            }}
          >
            Desagrupar
          </button>
          <button
            type="button"
            onClick={() => {
              reorderSelected('front');
              setContextMenu(null);
            }}
          >
            Traer al frente
          </button>
          <button
            type="button"
            onClick={() => {
              reorderSelected('back');
              setContextMenu(null);
            }}
          >
            Enviar al fondo
          </button>
          <button type="button" onClick={handleMoveToLayer}>
            Mover a capa
          </button>
          <button
            type="button"
            onClick={() => {
              setInspector('properties');
              setContextMenu(null);
            }}
          >
            Abrir inspector
          </button>
        </div>
      ) : null}
    </section>
  );
}
