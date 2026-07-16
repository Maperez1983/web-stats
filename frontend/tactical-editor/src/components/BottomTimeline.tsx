import { useEditorStore } from '../store/editorStore';

export function BottomTimeline() {
  const scene = useEditorStore((state) => state.scene);
  const cards = scene?.timeline.keyframes || [];

  return (
    <section className="te-panel te-timeline">
      <div className="te-panel-head">
        <h2>Timeline reservada</h2>
        <span>{cards.length} keyframes</span>
      </div>
      <div className="te-timeline-ruler">
        {cards.length ? (
          cards.slice(0, 10).map((card, index) => (
            <div key={`${String(card.title || 'step')}-${index}`} className="te-tick">
              <strong>{String(card.title || `Paso ${index + 1}`)}</strong>
              <span>{String(card.subtitle || card.label || '')}</span>
            </div>
          ))
        ) : (
          <>
            <div className="te-tick">
              <strong>Timeline futura</strong>
              <span>
                La escena ya guarda `timeline.keyframes` y `viewport`, lista para sincronizar
                animaciones.
              </span>
            </div>
            <div className="te-tick">
              <strong>Compatibilidad 3D</strong>
              <span>
                El guardado mantiene `canvas_state.objects` legacy y añade `sceneObjects`
                versionados para el motor nuevo.
              </span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
