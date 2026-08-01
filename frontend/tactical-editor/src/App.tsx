import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { BottomTimeline } from './components/BottomTimeline';
import { CanvasViewport } from './components/CanvasViewport';
import { LeftToolRail } from './components/LeftToolRail';
import { RightInspector } from './components/RightInspector';
import { TopBar } from './components/TopBar';
import { parseImportedScene } from './editor/serialization/SceneSerializer';
import {
  deleteTask,
  enqueueEditorJob,
  fetchTaskDocument,
  fetchTaskVersions,
  renameTask,
  restoreTaskVersion,
  saveGraphicCanvas,
  saveTaskAs,
  type TaskEditorVersion,
} from './services/api';
import { useEditorStore } from './store/editorStore';

type AppProps = {
  documentUrl: string;
};

function downloadBlob(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function getCsrfToken() {
  if (typeof document === 'undefined') {
    return '';
  }
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export function App({ documentUrl }: AppProps) {
  const setDocument = useEditorStore((state) => state.setDocument);
  const documentData = useEditorStore((state) => state.document);
  const scene = useEditorStore((state) => state.scene);
  const dirty = useEditorStore((state) => state.dirty);
  const saving = useEditorStore((state) => state.saving);
  const revision = useEditorStore((state) => state.revision);
  const error = useEditorStore((state) => state.error);
  const history = useEditorStore((state) => state.history);
  const featureEnabled = useEditorStore((state) => state.featureEnabled);
  const editorSurfaceMode = useEditorStore((state) => state.editorSurfaceMode);
  const undo = useEditorStore((state) => state.undo);
  const redo = useEditorStore((state) => state.redo);
  const generateRecreation = useEditorStore((state) => state.generateRecreation);
  const copySelectedObjects = useEditorStore((state) => state.copySelectedObjects);
  const pasteClipboard = useEditorStore((state) => state.pasteClipboard);
  const duplicateSelectedObjects = useEditorStore((state) => state.duplicateSelectedObjects);
  const removeSelectedObjects = useEditorStore((state) => state.removeSelectedObjects);
  const clearSelection = useEditorStore((state) => state.clearSelection);
  const selectAllObjects = useEditorStore((state) => state.selectAllObjects);
  const groupSelected = useEditorStore((state) => state.groupSelected);
  const ungroupSelected = useEditorStore((state) => state.ungroupSelected);
  const reorderSelected = useEditorStore((state) => state.reorderSelected);
  const saveStart = useEditorStore((state) => state.saveStart);
  const saveSuccess = useEditorStore((state) => state.saveSuccess);
  const saveError = useEditorStore((state) => state.saveError);
  const canvasApi = useEditorStore((state) => state.canvasApi);
  const importScene = useEditorStore((state) => state.importScene);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const autosaveTimerRef = useRef<number | null>(null);
  const [saveAsOpen, setSaveAsOpen] = useState(false);
  const [saveAsTitle, setSaveAsTitle] = useState('');
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameTitle, setRenameTitle] = useState('');
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [taskVersions, setTaskVersions] = useState<TaskEditorVersion[]>([]);
  const [versionsError, setVersionsError] = useState('');

  useEffect(() => {
    let mounted = true;
    fetchTaskDocument(documentUrl)
      .then((document) => {
        if (mounted) {
          setDocument(document);
        }
      })
      .catch((loadError) => {
        console.error('[tactical-editor] load failed', loadError);
      });
    return () => {
      mounted = false;
    };
  }, [documentUrl, setDocument]);

  useEffect(() => {
    const globalWindow = window as Window & {
      __TACTICAL_EDITOR_STORE__?: typeof useEditorStore;
    };
    globalWindow.__TACTICAL_EDITOR_STORE__ = useEditorStore;
    return () => {
      if (globalWindow.__TACTICAL_EDITOR_STORE__ === useEditorStore) {
        delete globalWindow.__TACTICAL_EDITOR_STORE__;
      }
    };
  }, []);

  const handleSaveBoard = async () => {
    const payload = useEditorStore.getState().getSavePayload();
    const currentDocument = useEditorStore.getState().document;
    if (!currentDocument?.urls.graphic_save || !payload || saving) {
      return;
    }
    const savedRevision = saveStart();
    try {
      await saveGraphicCanvas(currentDocument.urls.graphic_save, {
        ...payload,
        preview_data: canvasApi?.exportPngDataUrl({ includeUi: false, pixelRatio: 2 }) || undefined,
      });
      const refreshed = await fetchTaskDocument(documentUrl);
      saveSuccess(refreshed, savedRevision);
    } catch (saveFailure) {
      const message =
        saveFailure instanceof Error ? saveFailure.message : 'No se pudo guardar la pizarra.';
      saveError(message);
      console.error('[tactical-editor] save failed', saveFailure);
    }
  };

  useEffect(() => {
    if (!featureEnabled || !dirty || saving || !documentData?.urls.graphic_save) {
      return undefined;
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      void handleSaveBoard();
    }, 1400);
    return () => {
      if (autosaveTimerRef.current) {
        window.clearTimeout(autosaveTimerRef.current);
        autosaveTimerRef.current = null;
      }
    };
  }, [featureEnabled, dirty, saving, revision, documentData?.urls.graphic_save]);

  useEffect(() => {
    let cancelled = false;
    const versionsUrl = documentData?.urls.versions;
    if (!versionsUrl) {
      setTaskVersions([]);
      setVersionsError('');
      return undefined;
    }
    void fetchTaskVersions(versionsUrl)
      .then((versions) => {
        if (!cancelled) {
          setTaskVersions(versions);
          setVersionsError('');
        }
      })
      .catch((versionsLoadError) => {
        if (!cancelled) {
          setTaskVersions([]);
          setVersionsError(
            versionsLoadError instanceof Error
              ? versionsLoadError.message
              : 'No se pudo cargar el historial de versiones.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [documentData?.task.id, documentData?.urls.versions]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tagName = String(target?.tagName || '').toLowerCase();
      const isEditable = Boolean(
        target?.isContentEditable || ['input', 'textarea', 'select'].includes(tagName)
      );
      const meta = event.metaKey || event.ctrlKey;
      if (isEditable) {
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && featureEnabled) {
        event.preventDefault();
        removeSelectedObjects();
        return;
      }
      if (event.key === 'Escape') {
        clearSelection();
        return;
      }
      if (!meta) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === 'z' && event.shiftKey) {
        event.preventDefault();
        redo();
      } else if (key === 'z') {
        event.preventDefault();
        undo();
      } else if (key === 'a' && featureEnabled) {
        event.preventDefault();
        selectAllObjects();
      } else if (key === 'g' && event.shiftKey && featureEnabled) {
        event.preventDefault();
        ungroupSelected();
      } else if (key === 'g' && featureEnabled) {
        event.preventDefault();
        groupSelected();
      } else if (key === 'c' && featureEnabled) {
        event.preventDefault();
        copySelectedObjects();
      } else if (key === 'v' && featureEnabled) {
        event.preventDefault();
        pasteClipboard();
      } else if (key === 'd' && featureEnabled) {
        event.preventDefault();
        duplicateSelectedObjects();
      } else if (key === ']' && featureEnabled) {
        event.preventDefault();
        reorderSelected('forward');
      } else if (key === '[' && featureEnabled) {
        event.preventDefault();
        reorderSelected('backward');
      } else if (key === 's') {
        event.preventDefault();
        void handleSaveBoard();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    featureEnabled,
    removeSelectedObjects,
    clearSelection,
    undo,
    redo,
    copySelectedObjects,
    pasteClipboard,
    duplicateSelectedObjects,
    selectAllObjects,
    groupSelected,
    ungroupSelected,
    reorderSelected,
    saving,
    canvasApi,
    documentData,
    scene,
  ]);

  const handleGenerateAiPreview = async () => {
    if (!documentData?.urls.export_jobs_api) {
      return;
    }
    const savedRevision = saveStart();
    try {
      await enqueueEditorJob(documentData.urls.export_jobs_api, {
        kind: 'ai_preview',
        source: 'editor_pro',
      });
      const refreshed = await fetchTaskDocument(documentUrl);
      saveSuccess(refreshed, savedRevision);
    } catch (jobError) {
      const message =
        jobError instanceof Error ? jobError.message : 'No se pudo generar la imagen IA.';
      saveError(message);
      console.error('[tactical-editor] ai preview failed', jobError);
    }
  };

  const buildTaskPdfUrl = (style: 'club' | 'uefa') => {
    const taskId = documentData?.task.id;
    if (!taskId || typeof window === 'undefined') {
      return null;
    }
    const url = new URL(`/coach/sesiones/tarea/${taskId}/pdf/`, window.location.origin);
    url.searchParams.set('style', style);
    url.searchParams.set('one_page', '1');
    return url.toString();
  };

  const openTaskPdf = (style: 'club' | 'uefa') => {
    const pdfUrl = buildTaskPdfUrl(style);
    if (!pdfUrl) {
      return;
    }
    window.open(pdfUrl, '_blank', 'noopener');
  };

  const handleGeneratePdf = () => {
    openTaskPdf('club');
  };

  const handlePrintPdf = () => {
    openTaskPdf('uefa');
  };

  const handleSharePdf = async () => {
    const taskId = documentData?.task.id;
    if (!taskId) {
      return;
    }
    const body = new URLSearchParams();
    body.set('task_kind', 'session');
    body.set('task_id', String(taskId));
    body.set('style', 'club');
    body.set('valid_days', '30');
    const csrfToken = getCsrfToken();
    try {
      const response = await fetch('/api/share/task-pdf/create/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: body.toString(),
      });
      const data = (await response.json().catch(() => ({}))) as { url?: string; error?: string };
      if (!response.ok || !data.url) {
        throw new Error(data.error || 'No se pudo crear el enlace compartido.');
      }
      try {
        await navigator.clipboard.writeText(data.url);
      } catch (clipboardError) {
        console.error('[tactical-editor] clipboard share failed', clipboardError);
      }
    } catch (shareError) {
      window.alert(shareError instanceof Error ? shareError.message : 'No se pudo compartir el PDF.');
      console.error('[tactical-editor] share pdf failed', shareError);
    }
  };

  const handleExportPng = () => {
    const dataUrl = canvasApi?.exportPngDataUrl({ includeUi: false, pixelRatio: 2 });
    if (!dataUrl) {
      return;
    }
    const anchor = document.createElement('a');
    anchor.href = dataUrl;
    anchor.download = `${documentData?.task.title || 'tarea'}-pizarra.png`;
    anchor.click();
  };

  const handleExportJson = () => {
    downloadBlob(
      `${documentData?.task.title || 'tarea'}-scene.json`,
      useEditorStore.getState().exportSceneJson(),
      'application/json'
    );
  };

  const handleCopyScene = async () => {
    try {
      await navigator.clipboard.writeText(useEditorStore.getState().exportSceneJson());
    } catch (copyError) {
      console.error('[tactical-editor] clipboard export failed', copyError);
    }
  };

  const handleOpenDetail = () => {
    const detailUrl = documentData?.urls.detail;
    if (!detailUrl) {
      return;
    }
    window.open(detailUrl, '_blank', 'noopener');
  };

  const handleOpenRename = () => {
    setRenameTitle(documentData?.task.title || 'Tarea');
    setRenameOpen(true);
  };

  const handleOpenSaveAs = () => {
    setSaveAsTitle(`${documentData?.task.title || 'Tarea'} (copia)`);
    setSaveAsOpen(true);
  };

  const handleOpenDuplicate = () => {
    handleOpenSaveAs();
  };

  const handleSubmitRename = async () => {
    if (!documentData?.urls.rename || saving) {
      return;
    }
    const title = String(renameTitle || '').trim();
    if (!title) {
      window.alert('El título no puede estar vacío.');
      return;
    }
    try {
      const response = await renameTask(documentData.urls.rename, { title });
      setRenameOpen(false);
      if (response.document) {
        setDocument(response.document);
      } else if (response.task?.title) {
        const refreshed = await fetchTaskDocument(documentUrl);
        setDocument(refreshed);
      }
    } catch (renameError) {
      window.alert(renameError instanceof Error ? renameError.message : 'No se pudo renombrar la tarea.');
      console.error('[tactical-editor] rename failed', renameError);
    }
  };

  const handleDeleteTask = async () => {
    if (!documentData?.urls.delete || saving) {
      return;
    }
    const confirmed = window.confirm('¿Eliminar esta tarea? Esta acción la archivará como borrada.');
    if (!confirmed) {
      return;
    }
    try {
      const response = await deleteTask(documentData.urls.delete);
      window.location.assign(response.redirect_url || '/coach/sesiones/');
    } catch (deleteError) {
      window.alert(deleteError instanceof Error ? deleteError.message : 'No se pudo eliminar la tarea.');
      console.error('[tactical-editor] delete failed', deleteError);
    }
  };

  const handleSubmitSaveAs = async () => {
    if (!documentData?.urls.save_as || saving) {
      return;
    }
    const title = String(saveAsTitle || '').trim() || `${documentData?.task.title || 'Tarea'} (copia)`;
    try {
      const payload = useEditorStore.getState().getSavePayload();
      if (!payload) {
        throw new Error('No hay contenido para duplicar.');
      }
      const response = await saveTaskAs(documentData.urls.save_as, {
        title,
        ...payload,
        preview_data: canvasApi?.exportPngDataUrl({ includeUi: false, pixelRatio: 2 }) || undefined,
      });
      setSaveAsOpen(false);
      window.location.assign(response.editor_url);
    } catch (saveAsError) {
      window.alert(saveAsError instanceof Error ? saveAsError.message : 'No se pudo guardar como nueva tarea.');
      console.error('[tactical-editor] save as failed', saveAsError);
    }
  };

  const handleRestoreVersion = async (backupId: number) => {
    if (!documentData?.urls.restore_version) {
      return;
    }
    const confirmed = window.confirm('¿Restaurar esta versión? La versión actual se guardará como backup.');
    if (!confirmed) {
      return;
    }
    try {
      await restoreTaskVersion(documentData.urls.restore_version, { backup_id: backupId });
      const refreshed = await fetchTaskDocument(documentUrl);
      setDocument(refreshed);
      const versionsUrl = refreshed.urls.versions;
      if (versionsUrl) {
        const versions = await fetchTaskVersions(versionsUrl);
        setTaskVersions(versions);
      }
    } catch (restoreError) {
      window.alert(restoreError instanceof Error ? restoreError.message : 'No se pudo restaurar la versión.');
      console.error('[tactical-editor] restore version failed', restoreError);
    }
  };

  const handleOpenVersionHistory = () => {
    setVersionsOpen((current) => !current);
  };

  const handleImportJson = () => fileInputRef.current?.click();

  const handleImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !documentData) return;
    try {
      const text = await file.text();
      const importedScene = parseImportedScene(text, documentData);
      importScene(importedScene);
    } catch (importError) {
      console.error('[tactical-editor] import failed', importError);
      saveError(
        importError instanceof Error ? importError.message : 'No se pudo importar la escena JSON.'
      );
    } finally {
      event.target.value = '';
    }
  };

  return (
    <div className="te-app" data-editor-surface-mode={editorSurfaceMode}>
      <TopBar
        dirty={dirty}
        saving={saving}
        error={error}
        canUndo={history.past.length > 0}
        canRedo={history.future.length > 0}
        featureEnabled={featureEnabled}
        onGenerateRecreation={generateRecreation}
        onSaveBoard={handleSaveBoard}
        onGenerateAiPreview={handleGenerateAiPreview}
      onGeneratePdf={handleGeneratePdf}
      onPrintPdf={handlePrintPdf}
      onSharePdf={handleSharePdf}
      onOpenDetail={handleOpenDetail}
      onOpenRename={handleOpenRename}
      onOpenSaveAs={handleOpenSaveAs}
      onOpenDuplicate={handleOpenDuplicate}
      onDeleteTask={handleDeleteTask}
      onToggleVersionHistory={handleOpenVersionHistory}
      versionHistoryOpen={versionsOpen}
      onUndo={undo}
      onRedo={redo}
        onExportPng={handleExportPng}
        onExportJson={handleExportJson}
        onImportJson={handleImportJson}
        onCopyScene={handleCopyScene}
        onFitField={() => canvasApi?.fitToScene()}
      />
      <LeftToolRail />
      <CanvasViewport />
      <RightInspector />
      <BottomTimeline />
      {saveAsOpen ? (
        <div className="te-modal-backdrop" role="presentation" onClick={() => setSaveAsOpen(false)}>
          <section
            className="te-modal te-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Guardar como"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="te-modal-head">
              <div>
                <div className="te-kicker">Tarea duplicada</div>
                <h2>Guardar como nueva tarea</h2>
              </div>
              <button type="button" data-testid="task-save-as-cancel" onClick={() => setSaveAsOpen(false)}>
                Cerrar
              </button>
            </header>
            <div className="te-form-grid">
              <label>
                Título
                <input
                  data-testid="task-save-as-title"
                  type="text"
                  value={saveAsTitle}
                  onChange={(event) => setSaveAsTitle(event.target.value)}
                />
              </label>
            </div>
            <div className="te-action-row wrap">
              <button type="button" onClick={() => setSaveAsOpen(false)}>
                Cancelar
              </button>
              <button type="button" data-testid="task-save-as-confirm" onClick={() => void handleSubmitSaveAs()}>
                Guardar como
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {renameOpen ? (
        <div className="te-modal-backdrop" role="presentation" onClick={() => setRenameOpen(false)}>
          <section
            className="te-modal te-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Renombrar tarea"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="te-modal-head">
              <div>
                <div className="te-kicker">Tarea</div>
                <h2>Renombrar tarea</h2>
              </div>
              <button type="button" data-testid="task-rename-cancel" onClick={() => setRenameOpen(false)}>
                Cerrar
              </button>
            </header>
            <div className="te-form-grid">
              <label>
                Título
                <input
                  data-testid="task-rename-title"
                  type="text"
                  value={renameTitle}
                  onChange={(event) => setRenameTitle(event.target.value)}
                />
              </label>
            </div>
            <div className="te-action-row wrap">
              <button type="button" onClick={() => setRenameOpen(false)}>
                Cancelar
              </button>
              <button type="button" data-testid="task-rename-confirm" onClick={() => void handleSubmitRename()}>
                Renombrar
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {versionsOpen ? (
        <div className="te-modal-backdrop" role="presentation" onClick={() => setVersionsOpen(false)}>
          <section
            className="te-modal te-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Historial de versiones"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="te-modal-head">
              <div>
                <div className="te-kicker">Historial de tareas</div>
                <h2>Versiones guardadas</h2>
              </div>
              <button type="button" onClick={() => setVersionsOpen(false)}>
                Cerrar
              </button>
            </header>
            {versionsError ? <div className="te-topbar-error">{versionsError}</div> : null}
            <div className="te-modal-list" data-testid="task-version-history-panel">
              {taskVersions.length ? (
                taskVersions.map((version) => (
                  <article key={version.id} className="te-stat-card" data-testid="task-version-entry">
                    <strong>{version.reason || 'Backup'}</strong>
                    <span>
                      {version.title || documentData?.task.title || 'Tarea'} · {version.captured_at || 'Sin fecha'}
                    </span>
                    <small>
                      {version.objects_count} objetos · {version.timeline_count} keyframes · {version.actor || 'sistema'}
                    </small>
                    <div className="te-action-row wrap">
                      <button type="button" onClick={() => void handleRestoreVersion(version.id)}>
                        Restaurar
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <div className="te-stat-card">
                  <strong>Sin versiones</strong>
                  <span>No hay backups recientes aún.</span>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/json,.json"
        hidden
        onChange={handleImportFile}
      />
    </div>
  );
}
