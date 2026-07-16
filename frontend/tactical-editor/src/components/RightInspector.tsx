import { useMemo } from 'react';
import { useEditorStore, useSelectedObject } from '../store/editorStore';

const TEAM_OPTIONS = [
  { value: 'home', label: 'Local' },
  { value: 'away', label: 'Visitante' },
  { value: 'joker', label: 'Comodín' },
  { value: 'neutral', label: 'Neutro' },
] as const;

export function RightInspector() {
  const document = useEditorStore((state) => state.document);
  const scene = useEditorStore((state) => state.scene);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const activeInspector = useEditorStore((state) => state.activeInspector);
  const setInspector = useEditorStore((state) => state.setInspector);
  const setObjectColor = useEditorStore((state) => state.setObjectColor);
  const setObjectLabel = useEditorStore((state) => state.setObjectLabel);
  const setObjectTeam = useEditorStore((state) => state.setObjectTeam);
  const setObjectLock = useEditorStore((state) => state.setObjectLock);
  const setObjectVisibility = useEditorStore((state) => state.setObjectVisibility);
  const reorderSelected = useEditorStore((state) => state.reorderSelected);
  const setPitchType = useEditorStore((state) => state.setPitchType);
  const setLayerVisibility = useEditorStore((state) => state.setLayerVisibility);
  const setLayerLock = useEditorStore((state) => state.setLayerLock);
  const moveLayerOrder = useEditorStore((state) => state.moveLayerOrder);
  const selectedObject = useSelectedObject();

  const exportJobs = document?.exports.jobs || [];
  const layerRows = useMemo(
    () => (scene?.layers || []).slice().sort((a, b) => a.order - b.order),
    [scene?.layers]
  );

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
                {selectedIds.length
                  ? `${selectedIds.length} objeto(s)`
                  : 'Ningún objeto seleccionado'}
              </span>
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
            {selectedObject ? (
              <>
                <div className="te-stat-card">
                  <strong>Objeto</strong>
                  <span>{selectedObject.type}</span>
                </div>
                <div className="te-form-grid">
                  <label>
                    Color
                    <input
                      type="color"
                      value={String(selectedObject.style.fill || '#2563eb')}
                      onChange={(event) => setObjectColor(selectedObject.id, event.target.value)}
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
                  {selectedObject.type === 'player' || selectedObject.type === 'goalkeeper' ? (
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
                  ) : null}
                </div>
                <div className="te-action-row">
                  <button
                    type="button"
                    onClick={() => setObjectLock(selectedObject.id, !selectedObject.locked)}
                  >
                    {selectedObject.locked ? 'Desbloquear' : 'Bloquear'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setObjectVisibility(selectedObject.id, !selectedObject.visible)}
                  >
                    {selectedObject.visible ? 'Ocultar' : 'Mostrar'}
                  </button>
                  <button type="button" onClick={() => reorderSelected('forward')}>
                    Adelante
                  </button>
                  <button type="button" onClick={() => reorderSelected('backward')}>
                    Atrás
                  </button>
                </div>
              </>
            ) : (
              <div className="te-stat-card">
                <strong>Documento</strong>
                <span>{document?.task.title || 'Sin documento'}</span>
              </div>
            )}
          </>
        ) : null}
        {activeInspector === 'sequence' ? (
          <>
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
                  <button type="button" onClick={() => setLayerVisibility(layer.id)}>
                    {layer.visible ? 'Ocultar' : 'Mostrar'}
                  </button>
                  <button type="button" onClick={() => setLayerLock(layer.id)}>
                    {layer.locked ? 'Desbloquear' : 'Bloquear'}
                  </button>
                  <button type="button" onClick={() => moveLayerOrder(layer.id, -1)}>
                    ↑
                  </button>
                  <button type="button" onClick={() => moveLayerOrder(layer.id, 1)}>
                    ↓
                  </button>
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
