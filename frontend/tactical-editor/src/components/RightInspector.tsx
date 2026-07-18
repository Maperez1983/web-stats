import { useEffect, useMemo, useState } from 'react';
import {
  assetCategoryLabel,
  getAssetDefinition,
  getAssetPreviewIcon,
  listAssets,
} from '../editor/assets/assetRegistry';
import { createObject } from '../editor/objects/ObjectFactory';
import { createDefaultScene } from '../editor/core/sceneSchema';
import type { SceneLayerId, SceneObjectType } from '../editor/core/sceneSchema';
import { useEditorStore, useSelectedObject } from '../store/editorStore';

const TEAM_OPTIONS = [
  { value: 'home', label: 'Local' },
  { value: 'away', label: 'Visitante' },
  { value: 'joker', label: 'Comodín' },
  { value: 'neutral', label: 'Neutro' },
] as const;

const OBJECT_TYPE_OPTIONS: Array<{ value: SceneObjectType; label: string }> = [
  { value: 'player', label: 'Jugador' },
  { value: 'goalkeeper', label: 'Portero' },
  { value: 'player-home', label: 'Jugador local' },
  { value: 'player-away', label: 'Jugador visitante' },
  { value: 'player-joker', label: 'Jugador comodín' },
  { value: 'goalkeeper-home', label: 'Portero local' },
  { value: 'goalkeeper-away', label: 'Portero visitante' },
  { value: 'coach', label: 'Entrenador' },
  { value: 'referee', label: 'Árbitro' },
  { value: 'injured-player', label: 'Lesionado' },
  { value: 'ball-carrier', label: 'Con balón' },
  { value: 'numbered-player', label: 'Jugador numerado' },
  { value: 'ball', label: 'Balón' },
  { value: 'cone', label: 'Cono' },
  { value: 'high-cone', label: 'Cono alto' },
  { value: 'pole', label: 'Pica' },
  { value: 'goal', label: 'Portería' },
  { value: 'mini-goal', label: 'Miniportería' },
  { value: 'bench', label: 'Banquillo' },
  { value: 'marker', label: 'Marcador' },
  { value: 'flag', label: 'Banderín' },
  { value: 'mannequin', label: 'Maniquí' },
  { value: 'bib', label: 'Peto' },
  { value: 'arrow-straight', label: 'Flecha recta' },
  { value: 'arrow-curved', label: 'Flecha curva' },
  { value: 'arrow-segmented', label: 'Flecha segmentada' },
  { value: 'arrow-double', label: 'Flecha doble' },
  { value: 'arrow-pass', label: 'Flecha de pase' },
  { value: 'arrow-run', label: 'Flecha de carrera' },
  { value: 'trajectory', label: 'Trayectoria' },
  { value: 'line', label: 'Línea' },
  { value: 'line-dashed', label: 'Línea discontinua' },
  { value: 'zone-rect', label: 'Zona rectangular' },
  { value: 'zone-circle', label: 'Zona circular' },
  { value: 'zone-ellipse', label: 'Zona elíptica' },
  { value: 'zone-polygon', label: 'Zona polígono' },
  { value: 'zone-free', label: 'Zona libre' },
  { value: 'lane', label: 'Carril' },
  { value: 'stripe-h', label: 'Franja horizontal' },
  { value: 'stripe-v', label: 'Franja vertical' },
  { value: 'sector', label: 'Sector' },
  { value: 'text', label: 'Texto' },
  { value: 'label', label: 'Etiqueta' },
];

const LOCAL_TEMPLATE_STORAGE_KEY = 'tactical-editor-local-templates-v1';

type LocalTemplate = {
  id: string;
  name: string;
  scene: ReturnType<typeof createDefaultScene>;
};

function createTemplateScene(name: string, builder: (scene: ReturnType<typeof createDefaultScene>) => void) {
  const scene = createDefaultScene(`template-${name.toLowerCase().replace(/\s+/g, '-')}`, name, 1050, 680);
  builder(scene);
  return scene;
}

function defaultTemplates(): LocalTemplate[] {
  return [
    {
      id: 'empty',
      name: 'Campo vacío',
      scene: createTemplateScene('Campo vacío', () => undefined),
    },
    {
      id: 'rondo',
      name: 'Rondo',
      scene: createTemplateScene('Rondo', (scene) => {
        scene.objects.push(createObject('player-home', { x: 260, y: 220 }));
        scene.objects.push(createObject('player-home', { x: 360, y: 160 }));
        scene.objects.push(createObject('player-away', { x: 480, y: 260 }));
        scene.objects.push(createObject('ball', { x: 415, y: 208 }));
      }),
    },
    {
      id: 'possession',
      name: 'Posesión',
      scene: createTemplateScene('Posesión', (scene) => {
        scene.objects.push(createObject('player-home', { x: 180, y: 200 }));
        scene.objects.push(createObject('player-home', { x: 300, y: 280 }));
        scene.objects.push(createObject('player-away', { x: 470, y: 180 }));
        scene.objects.push(createObject('player-away', { x: 600, y: 260 }));
        scene.objects.push(createObject('ball', { x: 395, y: 218 }));
      }),
    },
    {
      id: 'finalization',
      name: 'Finalización',
      scene: createTemplateScene('Finalización', (scene) => {
        scene.objects.push(createObject('goal', { x: 820, y: 248 }));
        scene.objects.push(createObject('ball-carrier', { x: 460, y: 250 }));
        scene.objects.push(createObject('player-away', { x: 560, y: 190 }));
        scene.objects.push(createObject('arrow-run', { x: 500, y: 255 }));
      }),
    },
    {
      id: 'transition',
      name: 'Transición',
      scene: createTemplateScene('Transición', (scene) => {
        scene.objects.push(createObject('player-home', { x: 260, y: 200 }));
        scene.objects.push(createObject('player-home', { x: 360, y: 320 }));
        scene.objects.push(createObject('player-away', { x: 580, y: 220 }));
        scene.objects.push(createObject('arrow-pass', { x: 300, y: 220 }));
      }),
    },
  ];
}

function loadTemplates(): LocalTemplate[] {
  if (typeof window === 'undefined') {
    return defaultTemplates();
  }
  try {
    const raw = window.localStorage.getItem(LOCAL_TEMPLATE_STORAGE_KEY);
    if (!raw) {
      return defaultTemplates();
    }
    const parsed = JSON.parse(raw) as LocalTemplate[];
    if (!Array.isArray(parsed) || !parsed.length) {
      return defaultTemplates();
    }
    return parsed;
  } catch {
    return defaultTemplates();
  }
}

function saveTemplates(templates: LocalTemplate[]) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(LOCAL_TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
}

function assetCategoryForObjectType(type: SceneObjectType) {
  if (
    type === 'player' ||
    type === 'player-home' ||
    type === 'player-away' ||
    type === 'player-joker' ||
    type === 'goalkeeper' ||
    type === 'goalkeeper-home' ||
    type === 'goalkeeper-away' ||
    type === 'coach' ||
    type === 'referee' ||
    type === 'injured-player' ||
    type === 'ball-carrier' ||
    type === 'numbered-player'
  ) {
    return type.includes('goalkeeper') ? 'goalkeepers' : 'players';
  }
  if (
    type === 'ball' ||
    type === 'cone' ||
    type === 'high-cone' ||
    type === 'pole' ||
    type === 'goal' ||
    type === 'mini-goal' ||
    type === 'bench' ||
    type === 'marker' ||
    type === 'flag' ||
    type === 'mannequin' ||
    type === 'bib' ||
    type === 'hoop'
  ) {
    return 'equipment';
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
    return 'arrows';
  }
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
  return 'graphics';
}

export function RightInspector() {
  const document = useEditorStore((state) => state.document);
  const scene = useEditorStore((state) => state.scene);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const tacticalRecreation = useEditorStore((state) => state.tacticalRecreation);
  const generateRecreation = useEditorStore((state) => state.generateRecreation);
  const activeInspector = useEditorStore((state) => state.activeInspector);
  const setInspector = useEditorStore((state) => state.setInspector);
  const setObjectColor = useEditorStore((state) => state.setObjectColor);
  const setObjectStrokeColor = useEditorStore((state) => state.setObjectStrokeColor);
  const setObjectOpacity = useEditorStore((state) => state.setObjectOpacity);
  const setObjectRotation = useEditorStore((state) => state.setObjectRotation);
  const setObjectSize = useEditorStore((state) => state.setObjectSize);
  const setObjectPoints = useEditorStore((state) => state.setObjectPoints);
  const setObjectLabel = useEditorStore((state) => state.setObjectLabel);
  const setObjectName = useEditorStore((state) => state.setObjectName);
  const setObjectTeam = useEditorStore((state) => state.setObjectTeam);
  const setObjectAsset = useEditorStore((state) => state.setObjectAsset);
  const setObjectLock = useEditorStore((state) => state.setObjectLock);
  const setObjectVisibility = useEditorStore((state) => state.setObjectVisibility);
  const setObjectLayer = useEditorStore((state) => state.setObjectLayer);
  const reorderSelected = useEditorStore((state) => state.reorderSelected);
  const alignSelected = useEditorStore((state) => state.alignSelected);
  const distributeSelected = useEditorStore((state) => state.distributeSelected);
  const equalizeSelectedSize = useEditorStore((state) => state.equalizeSelectedSize);
  const centerSelectedInField = useEditorStore((state) => state.centerSelectedInField);
  const groupSelected = useEditorStore((state) => state.groupSelected);
  const ungroupSelected = useEditorStore((state) => state.ungroupSelected);
  const selectAllObjects = useEditorStore((state) => state.selectAllObjects);
  const invertSelection = useEditorStore((state) => state.invertSelection);
  const selectSingle = useEditorStore((state) => state.selectSingle);
  const selectObjectsByType = useEditorStore((state) => state.selectObjectsByType);
  const selectObjectsByLayer = useEditorStore((state) => state.selectObjectsByLayer);
  const setPitchType = useEditorStore((state) => state.setPitchType);
  const setLayerVisibility = useEditorStore((state) => state.setLayerVisibility);
  const setLayerLock = useEditorStore((state) => state.setLayerLock);
  const moveLayerOrder = useEditorStore((state) => state.moveLayerOrder);
  const createLayer = useEditorStore((state) => state.createLayer);
  const renameLayer = useEditorStore((state) => state.renameLayer);
  const duplicateLayer = useEditorStore((state) => state.duplicateLayer);
  const removeLayer = useEditorStore((state) => state.removeLayer);
  const moveSelectionToLayer = useEditorStore((state) => state.moveSelectionToLayer);
  const updatePreferences = useEditorStore((state) => state.updatePreferences);
  const addTimelineKeyframe = useEditorStore((state) => state.addTimelineKeyframe);
  const removeTimelineKeyframe = useEditorStore((state) => state.removeTimelineKeyframe);
  const setTimelineTime = useEditorStore((state) => state.setTimelineTime);
  const selectedObject = useSelectedObject();
  const selectedSceneObjects = useMemo(
    () => (scene?.objects || []).filter((object) => selectedIds.includes(object.id)),
    [scene?.objects, selectedIds]
  );
  const hasSelection = selectedSceneObjects.length > 0;
  const hasMultipleSelection = selectedSceneObjects.length > 1;
  const selectableSceneObjects = useMemo(
    () =>
      (scene?.objects || [])
        .filter(
          (object) =>
            object.visible &&
            !object.locked &&
            object.layerId !== 'pitch' &&
            (scene?.layers || []).find((layer) => layer.id === object.layerId)?.visible !== false &&
            (scene?.layers || []).find((layer) => layer.id === object.layerId)?.locked !== true
        )
        .slice()
        .sort((left, right) => left.zIndex - right.zIndex),
    [scene?.layers, scene?.objects]
  );
  const exportJobs = document?.exports.jobs || [];
  const layerRows = useMemo(
    () => (scene?.layers || []).slice().sort((a, b) => a.order - b.order),
    [scene?.layers]
  );
  const preferences = scene?.metadata.preferences;
  const [templates, setTemplatesState] = useState<LocalTemplate[]>(() => loadTemplates());

  useEffect(() => {
    saveTemplates(templates);
  }, [templates]);

  const saveCurrentAsTemplate = () => {
    if (!scene) {
      return;
    }
    const name = window.prompt('Nombre de la plantilla', scene.metadata.title || 'Plantilla');
    if (!name) {
      return;
    }
    const nextTemplate: LocalTemplate = {
      id: `tpl-${Date.now()}`,
      name,
      scene: {
        ...scene,
        metadata: { ...scene.metadata, title: name },
      },
    };
    setTemplatesState((current) => [...current.filter((item) => item.name !== name), nextTemplate]);
  };

  const applyTemplate = (template: LocalTemplate) => {
    useEditorStore.getState().importScene(template.scene);
  };

  const renameTemplate = (id: string) => {
    const template = templates.find((item) => item.id === id);
    if (!template) {
      return;
    }
    const name = window.prompt('Nuevo nombre', template.name);
    if (!name) {
      return;
    }
    setTemplatesState((current) =>
      current.map((item) => (item.id === id ? { ...item, name, scene: { ...item.scene, metadata: { ...item.scene.metadata, title: name } } } : item))
    );
  };

  const duplicateTemplate = (id: string) => {
    const template = templates.find((item) => item.id === id);
    if (!template) {
      return;
    }
    const name = `${template.name} copia`;
    setTemplatesState((current) => [
      ...current,
      {
        id: `tpl-${Date.now()}`,
        name,
        scene: {
          ...template.scene,
          metadata: { ...template.scene.metadata, title: name },
        },
      },
    ]);
  };

  const deleteTemplate = (id: string) => {
    setTemplatesState((current) => current.filter((item) => item.id !== id));
  };

  const selectedLayerId = selectedObject?.layerId || selectedSceneObjects[0]?.layerId || 'players';
  const currentAsset = selectedObject
    ? getAssetDefinition(String(selectedObject.data.assetId || ''))
    : null;
  const assetCategory = selectedObject ? assetCategoryForObjectType(selectedObject.type) : null;
  const assetOptions = selectedObject
    ? listAssets(assetCategory || undefined).filter((asset) =>
        assetCategory ? asset.category === assetCategory : true
      )
    : [];

  return (
    <aside className="te-panel te-inspector">
      <div className="te-panel-head">
        <h2>Inspector</h2>
        <div className="te-segmented small">
          <button
            className={activeInspector === 'properties' ? 'is-active' : ''}
            onClick={() => setInspector('properties')}
          >
            Props
          </button>
          <button
            className={activeInspector === 'sequence' ? 'is-active' : ''}
            onClick={() => setInspector('sequence')}
          >
            Capas
          </button>
          <button
            className={activeInspector === 'exports' ? 'is-active' : ''}
            onClick={() => setInspector('exports')}
          >
            Export
          </button>
        </div>
      </div>
      <div className="te-inspector-body">
        {activeInspector === 'properties' ? (
          <>
            <div className="te-stat-card">
              <strong>Selección</strong>
              <span>
                {selectedSceneObjects.length
                  ? `${selectedSceneObjects.length} objeto(s)`
                  : 'Ningún objeto seleccionado'}
              </span>
            </div>
            <div className="te-stat-card">
              <strong>Recreación automática</strong>
              <span>
                {tacticalRecreation
                  ? `${tacticalRecreation.language.statements.length} acciones · ${tacticalRecreation.plan.executionOrder.length} pasos`
                  : 'Pendiente de generar'}
              </span>
              {tacticalRecreation ? (
                <div className="te-metadata-list">
                  <div>
                    <strong>Posesión</strong>
                    <span>
                      {tacticalRecreation.possession.carrierId || 'Sin portador'} ·{' '}
                      {tacticalRecreation.possession.state}
                    </span>
                  </div>
                  <div>
                    <strong>Warnings</strong>
                    <span>{tacticalRecreation.plan.warnings.length}</span>
                  </div>
                  <div>
                    <strong>Keyframes</strong>
                    <span>{tacticalRecreation.keyframeCount}</span>
                  </div>
                </div>
              ) : null}
              <button type="button" data-testid="inspector-generate-recreation" onClick={() => generateRecreation()}>
                Generar recreación
              </button>
            </div>
            <div className="te-action-row wrap">
              <button type="button" onClick={() => selectAllObjects()}>
                Seleccionar todo
              </button>
              <button type="button" onClick={() => invertSelection()}>
                Invertir
              </button>
              <button type="button" onClick={() => setTimelineTime(scene?.timeline?.currentTime || 0)}>
                Reset tiempo
              </button>
            </div>
            <div className="te-stat-card">
              <strong>Selección por tipo</strong>
              <span>Objetos visibles y desbloqueados</span>
              <label className="te-form-grid">
                Tipo
                <select
                  defaultValue=""
                  onChange={(event) => {
                    const value = event.target.value as SceneObjectType;
                    if (!value) {
                      return;
                    }
                    selectObjectsByType(value);
                    event.target.value = '';
                  }}
                >
                  <option value="">Seleccionar por tipo…</option>
                  {OBJECT_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="te-stat-card">
              <strong>Selección por objeto</strong>
              <span>Objetos visibles y desbloqueados</span>
              <div className="te-layer-objects" aria-label="Objetos de la escena">
                {selectableSceneObjects.map((object) => (
                  <button
                    key={object.id}
                    type="button"
                    data-testid={`scene-object-${object.id}`}
                    className={selectedIds.includes(object.id) ? 'is-active is-selected' : ''}
                    aria-label={`Seleccionar ${object.data.name || object.data.label || object.type}`}
                    aria-pressed={selectedIds.includes(object.id)}
                    aria-selected={selectedIds.includes(object.id)}
                    onClick={() => selectSingle(object.id)}
                  >
                    <span>{object.data.name || object.data.label || object.type}</span>
                    <small>{object.type}</small>
                  </button>
                ))}
              </div>
            </div>
            <div className="te-stat-card">
              <strong>Tipo de campo</strong>
              <select
                value={scene?.pitch.type || 'full'}
                onChange={(event) =>
                  setPitchType(event.target.value as 'full' | 'half' | 'attacking-third' | 'custom')
                }
              >
                <option value="full">Campo completo</option>
                <option value="half">Medio campo</option>
                <option value="attacking-third">Tercio ofensivo</option>
                <option value="custom">Personalizado</option>
              </select>
            </div>
            <div className="te-stat-card">
              <strong>Snapping</strong>
              <div className="te-form-grid">
                <label>
                  Activado
                  <select
                    value={preferences?.snapEnabled ? '1' : '0'}
                    onChange={(event) => updatePreferences({ snapEnabled: event.target.value === '1' })}
                  >
                    <option value="1">Sí</option>
                    <option value="0">No</option>
                  </select>
                </label>
                <label>
                  Distancia
                  <input
                    type="number"
                    min="0"
                    max="80"
                    value={preferences?.snapDistance ?? 8}
                    onChange={(event) => updatePreferences({ snapDistance: Number(event.target.value) })}
                  />
                </label>
                <label>
                  Cuadrícula
                  <select
                    value={preferences?.gridVisible ? '1' : '0'}
                    onChange={(event) => updatePreferences({ gridVisible: event.target.value === '1' })}
                  >
                    <option value="1">Visible</option>
                    <option value="0">Oculta</option>
                  </select>
                </label>
                <label>
                  Tamaño grid
                  <input
                    type="number"
                    min="4"
                    max="100"
                    value={preferences?.gridSize ?? 20}
                    onChange={(event) => updatePreferences({ gridSize: Number(event.target.value) })}
                  />
                </label>
              </div>
            </div>
            {selectedObject ? (
              <>
                <div className="te-stat-card">
                  <strong>Objeto</strong>
                  <span>{selectedObject.type}</span>
                </div>
                <div className="te-form-grid">
                  <label className="te-asset-selector">
                    Asset
                    <select
                      value={String(selectedObject.data.assetId || currentAsset?.assetId || '')}
                      onChange={(event) => setObjectAsset(selectedObject.id, event.target.value)}
                    >
                      <option value="">Automático</option>
                      {assetOptions.map((asset) => (
                        <option key={asset.assetId} value={asset.assetId}>
                          {assetCategoryLabel(asset.category)} · {asset.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Nombre
                    <input
                      type="text"
                      value={String(selectedObject.data.name || '')}
                      onChange={(event) => setObjectName(selectedObject.id, event.target.value)}
                    />
                  </label>
                  <label>
                    Etiqueta
                    <input
                      type="text"
                      value={String(selectedObject.data.label || selectedObject.data.number || '')}
                      onChange={(event) => setObjectLabel(selectedObject.id, event.target.value)}
                    />
                  </label>
                  <label>
                    Capa
                    <select
                      value={selectedLayerId}
                      onChange={(event) =>
                        setObjectLayer(selectedObject.id, event.target.value as SceneLayerId)
                      }
                    >
                      {(scene?.layers || []).map((layer) => (
                        <option key={layer.id} value={layer.id}>
                          {layer.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    X
                    <input
                      type="number"
                      value={Math.round(selectedObject.x)}
                      onChange={(event) =>
                        useEditorStore.getState().patchSceneObject(selectedObject.id, {
                          x: Number(event.target.value),
                        }, { history: true })
                      }
                    />
                  </label>
                  <label>
                    Y
                    <input
                      type="number"
                      value={Math.round(selectedObject.y)}
                      onChange={(event) =>
                        useEditorStore.getState().patchSceneObject(selectedObject.id, {
                          y: Number(event.target.value),
                        }, { history: true })
                      }
                    />
                  </label>
                  <label>
                    Ancho
                    <input
                      type="number"
                      min="4"
                      value={Math.round(selectedObject.width)}
                      onChange={(event) =>
                        setObjectSize(selectedObject.id, Number(event.target.value), selectedObject.height)
                      }
                    />
                  </label>
                  <label>
                    Alto
                    <input
                      type="number"
                      min="4"
                      value={Math.round(selectedObject.height)}
                      onChange={(event) =>
                        setObjectSize(selectedObject.id, selectedObject.width, Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Rotación
                    <input
                      type="number"
                      value={Math.round(selectedObject.rotation)}
                      onChange={(event) =>
                        setObjectRotation(selectedObject.id, Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Opacidad
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={selectedObject.style.opacity ?? 1}
                      onChange={(event) =>
                        setObjectOpacity(selectedObject.id, Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Color
                    <input
                      type="color"
                      value={String(selectedObject.style.fill || '#2563eb')}
                      onChange={(event) => setObjectColor(selectedObject.id, event.target.value)}
                    />
                  </label>
                  <label>
                    Borde
                    <input
                      type="color"
                      value={String(selectedObject.style.stroke || '#e2e8f0')}
                      onChange={(event) => setObjectStrokeColor(selectedObject.id, event.target.value)}
                    />
                  </label>
                </div>
                {currentAsset ? (
                  <div className="te-asset-detail">
                    <span className="te-asset-preview is-inline" aria-hidden="true">
                      {getAssetPreviewIcon(currentAsset)}
                    </span>
                    <div>
                      <strong>{currentAsset.label}</strong>
                      <span>{currentAsset.assetId}</span>
                    </div>
                  </div>
                ) : null}
                {selectedObject.type === 'player' ||
                selectedObject.type === 'goalkeeper' ||
                selectedObject.type === 'player-home' ||
                selectedObject.type === 'player-away' ||
                selectedObject.type === 'player-joker' ||
                selectedObject.type === 'goalkeeper-home' ||
                selectedObject.type === 'goalkeeper-away' ||
                selectedObject.type === 'coach' ||
                selectedObject.type === 'referee' ||
                selectedObject.type === 'injured-player' ||
                selectedObject.type === 'ball-carrier' ||
                selectedObject.type === 'numbered-player' ? (
                  <div className="te-form-grid">
                    <label>
                      Equipo
                      <select
                        value={String(selectedObject.data.team || 'home')}
                        onChange={(event) =>
                          setObjectTeam(
                            selectedObject.id,
                            event.target.value as 'home' | 'away' | 'neutral' | 'joker'
                          )
                        }
                      >
                        {TEAM_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Dorsal
                      <input
                        type="text"
                        value={String(selectedObject.data.number || '')}
                        onChange={(event) =>
                          useEditorStore.getState().patchSceneObject(selectedObject.id, {
                            data: { number: event.target.value },
                          }, { history: true })
                        }
                      />
                    </label>
                    <label>
                      Rol
                      <input
                        type="text"
                        value={String(selectedObject.data.role || '')}
                        onChange={(event) =>
                          useEditorStore.getState().patchSceneObject(selectedObject.id, {
                            data: { role: event.target.value },
                          }, { history: true })
                        }
                      />
                    </label>
                  </div>
                ) : null}
                {Array.isArray(selectedObject.data.points) ? (
                  <div className="te-stat-card">
                    <strong>Puntos</strong>
                    <span>{selectedObject.data.points.length / 2} nodos lógicos</span>
                    <div className="te-action-row wrap">
                      <button type="button" onClick={() => setObjectPoints(selectedObject.id, [0, 0, selectedObject.width, selectedObject.height / 2])}>
                        Simplificar
                      </button>
                      <button type="button" onClick={() => setObjectPoints(selectedObject.id, [0, selectedObject.height / 2, selectedObject.width * 0.4, 0, selectedObject.width, selectedObject.height / 2])}>
                        Curva básica
                      </button>
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="te-stat-card">
                <strong>Documento</strong>
                <span>{document?.task.title || 'Sin documento'}</span>
              </div>
            )}
            {hasSelection ? (
              <>
                <div className="te-action-row wrap">
                  {selectedObject ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setObjectLock(selectedObject.id, !selectedObject.locked)}
                      >
                        {selectedObject.locked ? 'Desbloquear' : 'Bloquear'}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setObjectVisibility(selectedObject.id, !selectedObject.visible)
                        }
                      >
                        {selectedObject.visible ? 'Ocultar' : 'Mostrar'}
                      </button>
                    </>
                  ) : null}
                  <button type="button" onClick={() => reorderSelected('front')}>
                    Traer al frente
                  </button>
                  <button type="button" onClick={() => reorderSelected('forward')}>
                    Adelante
                  </button>
                  <button type="button" onClick={() => reorderSelected('backward')}>
                    Atrás
                  </button>
                  <button type="button" onClick={() => reorderSelected('back')}>
                    Enviar al fondo
                  </button>
                </div>
                {(hasMultipleSelection || selectedObject) ? (
                  <div className="te-action-row wrap">
                    <button type="button" onClick={() => alignSelected('left')}>
                      Alinear izq.
                    </button>
                    <button type="button" onClick={() => alignSelected('center-x')}>
                      Centrar horiz.
                    </button>
                    <button type="button" onClick={() => alignSelected('right')}>
                      Alinear der.
                    </button>
                    <button type="button" onClick={() => alignSelected('top')}>
                      Alinear arriba
                    </button>
                    <button type="button" onClick={() => alignSelected('center-y')}>
                      Centrar vert.
                    </button>
                    <button type="button" onClick={() => alignSelected('bottom')}>
                      Alinear abajo
                    </button>
                  </div>
                ) : null}
                {(hasMultipleSelection || selectedObject) ? (
                  <div className="te-action-row wrap">
                    <button type="button" onClick={() => distributeSelected('horizontal')}>
                      Distribuir H
                    </button>
                    <button type="button" onClick={() => distributeSelected('vertical')}>
                      Distribuir V
                    </button>
                    <button type="button" onClick={() => equalizeSelectedSize('width')}>
                      Igualar ancho
                    </button>
                    <button type="button" onClick={() => equalizeSelectedSize('height')}>
                      Igualar alto
                    </button>
                    <button type="button" onClick={() => equalizeSelectedSize('both')}>
                      Igualar tamaño
                    </button>
                    <button type="button" onClick={() => centerSelectedInField()}>
                      Centrar campo
                    </button>
                  </div>
                ) : null}
                <div className="te-action-row wrap">
                  <button type="button" onClick={() => groupSelected()}>
                    Agrupar
                  </button>
                  <button type="button" onClick={() => ungroupSelected()}>
                    Desagrupar
                  </button>
                  <button type="button" onClick={() => moveSelectionToLayer(selectedLayerId)}>
                    Mover capa
                  </button>
                </div>
              </>
            ) : null}
          </>
        ) : null}
        {activeInspector === 'sequence' ? (
          <>
            <div className="te-stat-card">
              <strong>Capas</strong>
              <span>{scene?.layers.length || 0} capas activas</span>
            </div>
            <div className="te-action-row wrap">
              <button type="button" onClick={() => createLayer('Nueva capa')}>
                Añadir capa
              </button>
              <button type="button" onClick={() => addTimelineKeyframe()}>
                Guardar keyframe
              </button>
            </div>
            {layerRows.map((layer) => (
              <div key={layer.id} className="te-layer-row">
                <div>
                  <strong>{layer.name}</strong>
                  <span>
                    {scene?.objects.filter((object) => object.layerId === layer.id).length || 0}{' '}
                    objetos
                  </span>
                </div>
                <div className="te-layer-actions">
                  <button type="button" onClick={() => selectObjectsByLayer(layer.id)}>
                    Seleccionar
                  </button>
                  <button type="button" onClick={() => setLayerVisibility(layer.id)}>
                    {layer.visible ? 'Ocultar' : 'Mostrar'}
                  </button>
                  <button type="button" onClick={() => setLayerLock(layer.id)}>
                    {layer.locked ? 'Desbloquear' : 'Bloquear'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const name = window.prompt('Renombrar capa', layer.name);
                      if (name) renameLayer(layer.id, name);
                    }}
                  >
                    Renombrar
                  </button>
                  <button type="button" onClick={() => duplicateLayer(layer.id)}>
                    Duplicar
                  </button>
                  <button type="button" onClick={() => removeLayer(layer.id)}>
                    Eliminar
                  </button>
                  <button type="button" onClick={() => moveLayerOrder(layer.id, -1)}>
                    ↑
                  </button>
                  <button type="button" onClick={() => moveLayerOrder(layer.id, 1)}>
                    ↓
                  </button>
                </div>
                <div className="te-layer-objects" aria-label={`Objetos de ${layer.name}`}>
                  {(scene?.objects || [])
                    .filter((object) => object.layerId === layer.id)
                    .slice()
                    .sort((left, right) => left.zIndex - right.zIndex)
                    .map((object) => (
                      <button
                        key={object.id}
                        type="button"
                        data-testid={`scene-object-${object.id}`}
                        className={selectedIds.includes(object.id) ? 'is-active is-selected' : ''}
                        aria-label={`Seleccionar ${object.data.name || object.data.label || object.type}`}
                        aria-pressed={selectedIds.includes(object.id)}
                        aria-selected={selectedIds.includes(object.id)}
                        onClick={() => selectSingle(object.id)}
                      >
                        <span>{object.data.name || object.data.label || object.type}</span>
                        <small>{object.type}</small>
                      </button>
                    ))}
                </div>
              </div>
            ))}
          </>
        ) : null}
        {activeInspector === 'exports' ? (
          <>
            <div className="te-stat-card">
              <strong>Estado IA</strong>
              <span>
                {document?.ai.generated
                  ? 'Imagen generada'
                  : document?.ai.has_analysis
                    ? 'Lista para generar'
                    : 'Pendiente'}
              </span>
            </div>
            <div className="te-stat-card">
              <strong>Escena</strong>
              <span>{scene?.timeline?.keyframes?.length || 0} keyframes guardados</span>
            </div>
            <div className="te-stat-card">
              <strong>Plantillas locales</strong>
              <span>{templates.length} disponibles</span>
            </div>
            <div className="te-action-row wrap">
              <button type="button" onClick={saveCurrentAsTemplate}>
                Guardar como plantilla
              </button>
              <button type="button" onClick={() => setTemplatesState(defaultTemplates())}>
                Restablecer plantillas
              </button>
            </div>
            {templates.map((template) => (
              <div key={template.id} className="te-stat-card">
                <strong>{template.name}</strong>
                <span>{template.scene.objects.length} objetos</span>
                <div className="te-action-row wrap">
                  <button type="button" onClick={() => applyTemplate(template)}>
                    Abrir
                  </button>
                  <button type="button" onClick={() => duplicateTemplate(template.id)}>
                    Duplicar
                  </button>
                  <button type="button" onClick={() => renameTemplate(template.id)}>
                    Renombrar
                  </button>
                  <button type="button" onClick={() => deleteTemplate(template.id)}>
                    Eliminar
                  </button>
                </div>
              </div>
            ))}
            {(document?.exports.targets || []).map((target, index) => (
              <div key={`${String(target.kind || 'target')}-${index}`} className="te-stat-card">
                <strong>{String(target.label || 'Export')}</strong>
                <span>{String(target.state || 'pending')}</span>
              </div>
            ))}
            {exportJobs.map((job, index) => (
              <div key={`${job.id || 'job'}-${index}`} className="te-stat-card">
                <strong>{String(job.kind_label || job.kind || 'Export')}</strong>
                <span>{String(job.status_label || job.status || '')}</span>
              </div>
            ))}
          </>
        ) : null}
      </div>
    </aside>
  );
}
