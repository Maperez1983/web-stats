import { useEffect, useMemo, useState } from 'react';
import { getAssetPreviewIcon, listAssetCategories, listAssets } from '../editor/assets/assetRegistry';
import type { EditorTool } from '../store/editorStore';
import { useEditorStore } from '../store/editorStore';

type ToolGroup = {
  label: string;
  items: Array<{ id: EditorTool; label: string; hint?: string }>;
};

const TOOL_GROUPS: ToolGroup[] = [
  {
    label: 'Navegación',
    items: [
      { id: 'select', label: 'Seleccionar', hint: 'Selecciona y transforma objetos' },
      { id: 'pan', label: 'Mover vista', hint: 'Paneo de la superficie' },
    ],
  },
];

const FAVORITES_STORAGE_KEY = 'tactical-editor-asset-favorites-v1';
const RECENTS_STORAGE_KEY = 'tactical-editor-asset-recents-v1';
const RECENTS_LIMIT = 8;

function loadStoredIds(key: string): string[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.map((value) => String(value)).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function storeIds(key: string, ids: string[]) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(ids));
}

function uniqueLimited(ids: string[]) {
  return [...new Set(ids)].slice(0, RECENTS_LIMIT);
}

export function LeftToolRail() {
  const activeTool = useEditorStore((state) => state.activeTool);
  const activeAssetId = useEditorStore((state) => state.activeAssetId);
  const setTool = useEditorStore((state) => state.setTool);
  const setActiveAssetId = useEditorStore((state) => state.setActiveAssetId);
  const featureEnabled = useEditorStore((state) => state.featureEnabled);
  const [query, setQuery] = useState('');
  const [favoriteIds, setFavoriteIds] = useState<string[]>(() => loadStoredIds(FAVORITES_STORAGE_KEY));
  const [recentIds, setRecentIds] = useState<string[]>(() => loadStoredIds(RECENTS_STORAGE_KEY));

  useEffect(() => {
    storeIds(FAVORITES_STORAGE_KEY, favoriteIds);
  }, [favoriteIds]);

  useEffect(() => {
    storeIds(RECENTS_STORAGE_KEY, recentIds);
  }, [recentIds]);

  const filteredAssetGroups = useMemo(() => {
    const value = query.trim().toLowerCase();
    return listAssetCategories()
      .map((category) => {
        const assets = listAssets(category.id).filter((asset) =>
          !value
            ? true
            : [asset.label, asset.assetId, asset.category, ...asset.keywords].some((part) =>
                String(part).toLowerCase().includes(value)
              )
        );
        return { ...category, assets };
      })
      .filter((category) => category.assets.length > 0);
  }, [query]);

  const visibleFavorites = useMemo(
    () =>
      favoriteIds
        .map((assetId) => listAssets().find((asset) => asset.assetId === assetId))
        .filter((asset): asset is NonNullable<typeof asset> => Boolean(asset))
        .filter((asset) =>
          !query.trim()
            ? true
            : [asset.label, asset.assetId, asset.category, ...asset.keywords].some((part) =>
                String(part).toLowerCase().includes(query.trim().toLowerCase())
              )
        ),
    [favoriteIds, query]
  );

  const visibleRecents = useMemo(
    () =>
      recentIds
        .map((assetId) => listAssets().find((asset) => asset.assetId === assetId))
        .filter((asset): asset is NonNullable<typeof asset> => Boolean(asset))
        .filter((asset) =>
          !query.trim()
            ? true
            : [asset.label, asset.assetId, asset.category, ...asset.keywords].some((part) =>
                String(part).toLowerCase().includes(query.trim().toLowerCase())
              )
        ),
    [recentIds, query]
  );

  const setRecentAsset = (assetId: string) => {
    setRecentIds((current) => uniqueLimited([assetId, ...current.filter((item) => item !== assetId)]));
  };

  const toggleFavorite = (assetId: string) => {
    setFavoriteIds((current) =>
      current.includes(assetId)
        ? current.filter((item) => item !== assetId)
        : uniqueLimited([assetId, ...current])
    );
  };

  const activateAsset = (assetId: string, tool: EditorTool) => {
    setTool(tool);
    setActiveAssetId(assetId);
    setRecentAsset(assetId);
  };

  const renderAssetCard = (asset: ReturnType<typeof listAssets>[number]) => {
    const isActive = activeAssetId === asset.assetId;
    const isFavorite = favoriteIds.includes(asset.assetId);
    return (
      <div
        key={asset.assetId}
        role="button"
        tabIndex={0}
        draggable
        className={`te-asset-card ${isActive ? 'is-active' : ''}`}
        onClick={() => activateAsset(asset.assetId, asset.type as EditorTool)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            activateAsset(asset.assetId, asset.type as EditorTool);
          }
        }}
        onDragStart={(event) => {
          event.dataTransfer.effectAllowed = 'copy';
          event.dataTransfer.setData('application/x-tactical-editor-asset', asset.assetId);
          event.dataTransfer.setData('text/plain', asset.assetId);
          activateAsset(asset.assetId, asset.type as EditorTool);
        }}
        title={asset.assetId}
      >
        <span className="te-asset-preview" aria-hidden="true">
          {getAssetPreviewIcon(asset)}
        </span>
        <span className="te-asset-meta">
          <strong>{asset.label}</strong>
          <span>{asset.category}</span>
        </span>
        <span className="te-asset-actions">
          <span className="te-asset-badge">{asset.type}</span>
          <button
            type="button"
            className={`te-asset-star ${isFavorite ? 'is-active' : ''}`}
            onClick={(event) => {
              event.stopPropagation();
              toggleFavorite(asset.assetId);
            }}
            title={isFavorite ? 'Quitar favorito' : 'Marcar favorito'}
          >
            ★
          </button>
        </span>
      </div>
    );
  };

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

      <div className="te-library-search">
        <label>
          Biblioteca
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar jugador, material o flecha..."
          />
        </label>
      </div>

      <div className="te-tool-summary">
        <strong>Herramienta activa</strong>
        <span>{activeAssetId || activeTool}</span>
      </div>

      {TOOL_GROUPS.map((family) => (
        <section key={family.label} className="te-tool-family">
          <h3>{family.label}</h3>
          <div className="te-tool-list">
            {family.items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`te-tool-btn ${activeTool === item.id ? 'is-active' : ''}`}
                onClick={() => {
                  setTool(item.id);
                  setActiveAssetId(null);
                }}
                title={item.hint}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>
      ))}

      {visibleFavorites.length ? (
        <section className="te-tool-family">
          <h3>Favoritos</h3>
          <div className="te-asset-grid">{visibleFavorites.map(renderAssetCard)}</div>
        </section>
      ) : null}

      {visibleRecents.length ? (
        <section className="te-tool-family">
          <h3>Recientes</h3>
          <div className="te-asset-grid">{visibleRecents.map(renderAssetCard)}</div>
        </section>
      ) : null}

      {filteredAssetGroups.map((category) => (
        <section key={category.id} className="te-tool-family">
          <h3>
            {category.label} <span>({category.count})</span>
          </h3>
          <div className="te-asset-grid">{category.assets.map(renderAssetCard)}</div>
        </section>
      ))}
    </aside>
  );
}
