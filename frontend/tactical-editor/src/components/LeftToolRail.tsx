import type { EditorTool } from '../store/editorStore';
import { useEditorStore } from '../store/editorStore';

const TOOL_FAMILIES: Array<{ label: string; items: Array<{ id: EditorTool; label: string }> }> = [
  {
    label: 'Navegación',
    items: [
      { id: 'select', label: 'Seleccionar' },
      { id: 'pan', label: 'Mover vista' },
    ],
  },
  {
    label: 'Jugadores y balón',
    items: [
      { id: 'player', label: 'Jugador' },
      { id: 'goalkeeper', label: 'Portero' },
      { id: 'ball', label: 'Balón' },
      { id: 'label', label: 'Etiqueta' },
    ],
  },
  {
    label: 'Material',
    items: [
      { id: 'cone', label: 'Cono' },
      { id: 'pole', label: 'Pica' },
      { id: 'hoop', label: 'Aro' },
      { id: 'mini-goal', label: 'Miniportería' },
    ],
  },
  {
    label: 'Líneas y zonas',
    items: [
      { id: 'arrow-straight', label: 'Flecha recta' },
      { id: 'arrow-curved', label: 'Flecha curva' },
      { id: 'line-dashed', label: 'Línea discontinua' },
      { id: 'zone-rect', label: 'Zona rectangular' },
      { id: 'zone-circle', label: 'Zona circular' },
      { id: 'text', label: 'Texto' },
    ],
  },
];

export function LeftToolRail() {
  const activeTool = useEditorStore((state) => state.activeTool);
  const setTool = useEditorStore((state) => state.setTool);
  const featureEnabled = useEditorStore((state) => state.featureEnabled);

  return (
    <aside className="te-panel te-sidebar">
      {!featureEnabled ? (
        <div className="te-callout">
          <strong>Editor legacy protegido</strong>
          <span>
            Abre la URL con <code>?editor2d=1</code> para activar la base Konva sin sustituir el
            editor actual.
          </span>
        </div>
      ) : null}
      {TOOL_FAMILIES.map((family) => (
        <section key={family.label} className="te-tool-family">
          <h3>{family.label}</h3>
          <div className="te-tool-list">
            {family.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`te-tool-btn ${activeTool === item.id ? 'is-active' : ''}`}
                onClick={() => setTool(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>
      ))}
    </aside>
  );
}
