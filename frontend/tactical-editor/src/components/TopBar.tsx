import { useMemo } from 'react';
import { useEditorStore } from '../store/editorStore';

type TopBarProps = {
  dirty: boolean;
  saving: boolean;
  error: string | null;
  canUndo: boolean;
  canRedo: boolean;
  featureEnabled: boolean;
  onGenerateRecreation: () => void | Promise<void>;
  onSaveBoard: () => void | Promise<void>;
  onGenerateAiPreview: () => void | Promise<void>;
  onGeneratePdf: () => void | Promise<void>;
  onPrintPdf: () => void | Promise<void>;
  onSharePdf: () => void | Promise<void>;
  onOpenDetail: () => void;
  onOpenRename: () => void;
  onOpenSaveAs: () => void;
  onOpenDuplicate: () => void;
  onDeleteTask: () => void | Promise<void>;
  onToggleVersionHistory: () => void;
  versionHistoryOpen: boolean;
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
  onGenerateRecreation,
  onSaveBoard,
  onGenerateAiPreview,
  onGeneratePdf,
  onPrintPdf,
  onSharePdf,
  onOpenDetail,
  onOpenRename,
  onOpenSaveAs,
  onOpenDuplicate,
  onDeleteTask,
  onToggleVersionHistory,
  versionHistoryOpen,
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
  const editorSurfaceMode = useEditorStore((state) => state.editorSurfaceMode);
  const setViewport = useEditorStore((state) => state.setViewport);
  const setEditorSurfaceMode = useEditorStore((state) => state.setEditorSurfaceMode);
  const scene = useEditorStore((state) => state.scene);
  const selectAllObjects = useEditorStore((state) => state.selectAllObjects);
  const compareMode = useMemo(() => {
    if (typeof window === 'undefined') {
      return { enabled: false, side: '' };
    }
    const params = new URLSearchParams(window.location.search);
    const enabled = params.get('editor_lab_compare') === '1';
    const side = String(params.get('editor_lab_compare_side') || '').trim().toLowerCase();
    return { enabled, side };
  }, []);
  const compareReadonly = compareMode.enabled && compareMode.side !== 'production';
  const invertSelection = useEditorStore((state) => state.invertSelection);
  const groupSelected = useEditorStore((state) => state.groupSelected);
  const ungroupSelected = useEditorStore((state) => state.ungroupSelected);
  const updatePreferences = useEditorStore((state) => state.updatePreferences);
  const addTimelineKeyframe = useEditorStore((state) => state.addTimelineKeyframe);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const hasSelection = selectedIds.length > 0;
  const preferences = scene?.metadata.preferences;

  return (
    <header className="te-topbar te-panel">
      <div>
        <div className="te-kicker">Editor táctico premium</div>
        <h1>{document?.task.title ?? 'Nueva tarea'}</h1>
        <div className="te-pills">
          <span>{document?.task.block_label ?? 'Principal 1'}</span>
          <span>{document?.task.duration_minutes ?? 0} min</span>
          <span>{featureEnabled ? 'Motor Konva' : 'Modo legacy protegido'}</span>
        </div>
        {error ? <div className="te-topbar-error">{error}</div> : null}
        {compareMode.enabled ? (
          <div className="te-topbar-warning" data-testid="editor-compare-warning">
            {compareReadonly
              ? 'Comparación activa: este panel está en solo lectura para evitar sobrescrituras.'
              : 'Comparación activa: este panel conserva el guardado habilitado.'}
          </div>
        ) : null}
      </div>
      <div className="te-topbar-actions">
        <div className="te-toolbar-group">
          <span className="te-toolbar-label">Modo</span>
          <nav className="te-segmented">
            <button
              type="button"
              className={editorSurfaceMode === 'edition' ? 'is-active' : ''}
              onClick={() => setEditorSurfaceMode('edition')}
            >
              Edición
            </button>
            <button
              type="button"
              className={editorSurfaceMode === 'presentation' ? 'is-active' : ''}
              onClick={() => setEditorSurfaceMode('presentation')}
            >
              Presentación
            </button>
          </nav>
          <nav className="te-segmented">
            <button
              type="button"
              data-testid="viewport-board2d"
              className={activeViewport === 'board2d' ? 'is-active' : ''}
              onClick={() => setViewport('board2d')}
            >
              Vista 2D
            </button>
            <button
              type="button"
              data-testid="viewport-board3d"
              className={activeViewport === 'board3d' ? 'is-active' : ''}
              onClick={() => setViewport('board3d')}
            >
              Vista 3D
            </button>
            <button
              type="button"
              data-testid="viewport-uefa"
              className={activeViewport === 'uefa' ? 'is-active' : ''}
              onClick={() => setViewport('uefa')}
            >
              Ficha UEFA
            </button>
          </nav>
        </div>
        <div className="te-toolbar-group">
          <span className="te-toolbar-label">Edición</span>
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
            <button
              type="button"
              data-testid="animation-add-keyframe"
              aria-label="Añadir keyframe"
              disabled={!hasSelection}
              onClick={() => addTimelineKeyframe()}
            >
              Keyframe
            </button>
            <button onClick={onUndo} disabled={!canUndo}>
              Deshacer
            </button>
            <button onClick={onRedo} disabled={!canRedo}>
              Rehacer
            </button>
            <button onClick={onFitField}>Ajustar campo</button>
          </div>
        </div>
        <div className="te-toolbar-group">
          <span className="te-toolbar-label">Archivo</span>
          <div className="te-segmented">
            <button type="button" data-testid="task-open-detail" aria-label="Abrir ficha" onClick={onOpenDetail}>
              Abrir
            </button>
            <button type="button" data-testid="task-rename" aria-label="Renombrar tarea" onClick={onOpenRename}>
              Renombrar
            </button>
            <button
              type="button"
              data-testid="task-duplicate"
              aria-label="Duplicar tarea"
              onClick={onOpenDuplicate}
            >
              Duplicar
            </button>
            <button type="button" data-testid="task-save-as" aria-label="Guardar como nueva tarea" onClick={onOpenSaveAs}>
              Guardar como
            </button>
            <button
              type="button"
              data-testid="task-delete"
              aria-label="Eliminar tarea"
              onClick={() => void onDeleteTask()}
            >
              Eliminar
            </button>
            <button
              type="button"
              data-testid="task-version-history"
              aria-label="Historial de versiones"
              className={versionHistoryOpen ? 'is-active' : ''}
              onClick={onToggleVersionHistory}
            >
              Historial
            </button>
          </div>
        </div>
        <div className="te-toolbar-group">
          <span className="te-toolbar-label">Exportar</span>
          <div className="te-segmented small">
            <button
              type="button"
              data-testid="generate-tactical-recreation"
              aria-label="Generar recreación"
              onClick={() => void onGenerateRecreation()}
            >
              Generar recreación
            </button>
            <button
              className={document?.ai.generated ? 'is-active' : ''}
              onClick={() => void onGenerateAiPreview()}
            >
              {document?.ai.generated ? 'Regenerar imagen IA' : 'Generar imagen IA'}
            </button>
            <button type="button" data-testid="task-generate-pdf" aria-label="Generar PDF" onClick={() => void onGeneratePdf()}>
              Generar PDF
            </button>
            <button type="button" data-testid="task-print-pdf" aria-label="Imprimir PDF" onClick={() => void onPrintPdf()}>
              Imprimir PDF
            </button>
            <button type="button" data-testid="task-share-pdf" aria-label="Compartir PDF" onClick={() => void onSharePdf()}>
              Compartir PDF
            </button>
            <button onClick={() => void onSaveBoard()} className={dirty ? 'is-active' : ''}>
              {saving ? 'Guardando...' : dirty ? 'Guardar pizarra' : 'Pizarra guardada'}
            </button>
            <button onClick={() => void onCopyScene()}>Copiar JSON</button>
            <button onClick={onImportJson}>Importar JSON</button>
            <button onClick={onExportJson}>Exportar JSON</button>
            <button onClick={onExportPng}>Exportar PNG</button>
          </div>
        </div>
      </div>
    </header>
  );
}
