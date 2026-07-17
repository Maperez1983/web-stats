import { useEditorStore } from '../store/editorStore';

type TopBarProps = {
  dirty: boolean;
  saving: boolean;
  error: string | null;
  canUndo: boolean;
  canRedo: boolean;
  featureEnabled: boolean;
  onSaveBoard: () => void | Promise<void>;
  onGenerateAiPreview: () => void | Promise<void>;
  onUndo: () => void;
  onRedo: () => void;
  onExportPng: () => void;
  onExportJson: () => void;
  onImportJson: () => void;
  onCopyScene: () => void | Promise<void>;
  onFitField: () => void;
};

export function TopBar({
  dirty,
  saving,
  error,
  canUndo,
  canRedo,
  featureEnabled,
  onSaveBoard,
  onGenerateAiPreview,
  onUndo,
  onRedo,
  onExportPng,
  onExportJson,
  onImportJson,
  onCopyScene,
  onFitField,
}: TopBarProps) {
  const document = useEditorStore((state) => state.document);
  const activeViewport = useEditorStore((state) => state.activeViewport);
  const setViewport = useEditorStore((state) => state.setViewport);
  const scene = useEditorStore((state) => state.scene);
  const selectAllObjects = useEditorStore((state) => state.selectAllObjects);
  const invertSelection = useEditorStore((state) => state.invertSelection);
  const groupSelected = useEditorStore((state) => state.groupSelected);
  const ungroupSelected = useEditorStore((state) => state.ungroupSelected);
  const updatePreferences = useEditorStore((state) => state.updatePreferences);
  const addTimelineKeyframe = useEditorStore((state) => state.addTimelineKeyframe);
  const preferences = scene?.metadata.preferences;

  return (
    <header className="te-topbar te-panel">
      <div>
        <div className="te-kicker">Editor táctico premium</div>
        <h1>{document?.task.title ?? 'Nueva tarea'}</h1>
        <div className="te-pills">
          <span>{document?.task.block_label ?? 'Principal 1'}</span>
          <span>{document?.task.duration_minutes ?? 0} min</span>
          <span>{featureEnabled ? 'Motor 2D Konva' : 'Modo legacy protegido'}</span>
        </div>
        {error ? <div className="te-topbar-error">{error}</div> : null}
      </div>
      <div className="te-topbar-actions">
        <nav className="te-segmented">
          <button
            className={activeViewport === 'board2d' ? 'is-active' : ''}
            onClick={() => setViewport('board2d')}
          >
            Vista 2D
          </button>
          <button
            className={activeViewport === 'board3d' ? 'is-active' : ''}
            onClick={() => setViewport('board3d')}
          >
            Vista 3D
          </button>
          <button
            className={activeViewport === 'uefa' ? 'is-active' : ''}
            onClick={() => setViewport('uefa')}
          >
            Ficha UEFA
          </button>
        </nav>
        <div className="te-segmented">
          <button onClick={() => selectAllObjects()}>Todo</button>
          <button onClick={() => invertSelection()}>Invertir</button>
          <button onClick={() => groupSelected()}>Agrupar</button>
          <button onClick={() => ungroupSelected()}>Desagrupar</button>
          <button
            className={preferences?.snapEnabled ? 'is-active' : ''}
            onClick={() => updatePreferences({ snapEnabled: !preferences?.snapEnabled })}
          >
            Snap
          </button>
          <button
            className={preferences?.gridVisible ? 'is-active' : ''}
            onClick={() => updatePreferences({ gridVisible: !preferences?.gridVisible })}
          >
            Grid
          </button>
          <button
            className={preferences?.showGuides ? 'is-active' : ''}
            onClick={() => updatePreferences({ showGuides: !preferences?.showGuides })}
          >
            Guías
          </button>
          <button onClick={() => addTimelineKeyframe()}>Keyframe</button>
        </div>
        <div className="te-segmented">
          <button onClick={onUndo} disabled={!canUndo}>
            Deshacer
          </button>
          <button onClick={onRedo} disabled={!canRedo}>
            Rehacer
          </button>
          <button onClick={onFitField}>Ajustar campo</button>
          <button onClick={() => void onCopyScene()}>Copiar JSON</button>
          <button onClick={onImportJson}>Importar JSON</button>
          <button onClick={onExportJson}>Exportar JSON</button>
          <button onClick={onExportPng}>Exportar PNG</button>
        </div>
        <div className="te-segmented">
          <button
            className={document?.ai.generated ? 'is-active' : ''}
            onClick={() => void onGenerateAiPreview()}
          >
            {document?.ai.generated ? 'Regenerar imagen IA' : 'Generar imagen IA'}
          </button>
          <button className={dirty ? 'is-active' : ''} onClick={() => void onSaveBoard()}>
            {saving ? 'Guardando...' : dirty ? 'Guardar pizarra' : 'Pizarra guardada'}
          </button>
        </div>
      </div>
    </header>
  );
}
