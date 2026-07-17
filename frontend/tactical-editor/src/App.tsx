import { useEffect, useRef } from 'react';
import type { ChangeEvent } from 'react';
import { BottomTimeline } from './components/BottomTimeline';
import { CanvasViewport } from './components/CanvasViewport';
import { LeftToolRail } from './components/LeftToolRail';
import { RightInspector } from './components/RightInspector';
import { TopBar } from './components/TopBar';
import { parseImportedScene } from './editor/serialization/SceneSerializer';
import { enqueueEditorJob, fetchTaskDocument, saveGraphicCanvas } from './services/api';
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
  const undo = useEditorStore((state) => state.undo);
  const redo = useEditorStore((state) => state.redo);
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
    <div className="te-app">
      <TopBar
        dirty={dirty}
        saving={saving}
        error={error}
        canUndo={history.past.length > 0}
        canRedo={history.future.length > 0}
        featureEnabled={featureEnabled}
        onSaveBoard={handleSaveBoard}
        onGenerateAiPreview={handleGenerateAiPreview}
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
