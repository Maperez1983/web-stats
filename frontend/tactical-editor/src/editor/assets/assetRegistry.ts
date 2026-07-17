import type {
  SceneLayerId,
  SceneObjectData,
  SceneObjectStyle,
  SceneObjectType,
} from '../core/sceneSchema';

export type AssetCategoryId =
  | 'players'
  | 'goalkeepers'
  | 'equipment'
  | 'arrows'
  | 'zones'
  | 'graphics';

export type AssetPreviewKind =
  | 'player'
  | 'goalkeeper'
  | 'ball'
  | 'cone'
  | 'pole'
  | 'goal'
  | 'miniGoal'
  | 'bench'
  | 'marker'
  | 'flag'
  | 'mannequin'
  | 'bib'
  | 'ladder'
  | 'fence'
  | 'arrow'
  | 'arrowCurve'
  | 'arrowSegmented'
  | 'arrowDashed'
  | 'arrowDouble'
  | 'route'
  | 'line'
  | 'zoneRect'
  | 'zoneCircle'
  | 'zoneEllipse'
  | 'zonePolygon'
  | 'zoneFree'
  | 'lane'
  | 'stripe'
  | 'sector'
  | 'text'
  | 'label'
  | 'icon';

export type AssetDefinition = {
  assetId: string;
  label: string;
  category: AssetCategoryId;
  type: SceneObjectType;
  layerId: SceneLayerId;
  previewKind: AssetPreviewKind;
  keywords: string[];
  defaultSize: { width: number; height: number };
  defaultStyle: Partial<SceneObjectStyle>;
  defaultData: Partial<SceneObjectData>;
};

type AssetSeed = Omit<AssetDefinition, 'keywords'> & {
  keywords?: string[];
};

const PLAYER_BASE_STYLE: Partial<SceneObjectStyle> = {
  strokeWidth: 3,
  textColor: '#f8fafc',
  fontSize: 15,
};

const ASSET_SEEDS: AssetSeed[] = [
  { assetId: 'player.home.front', label: 'Jugador local', category: 'players', type: 'player-home', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#2563eb', stroke: '#dbeafe' }, defaultData: { team: 'home', variant: 'front', orientation: 'front', number: '8' }, keywords: ['jugador', 'local', 'frontal'] },
  { assetId: 'player.home.back', label: 'Jugador local espalda', category: 'players', type: 'player-home', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#1d4ed8', stroke: '#bfdbfe' }, defaultData: { team: 'home', variant: 'back', orientation: 'back', number: '8' }, keywords: ['jugador', 'local', 'espalda'] },
  { assetId: 'player.home.side', label: 'Jugador local lateral', category: 'players', type: 'player-home', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#3b82f6', stroke: '#dbeafe' }, defaultData: { team: 'home', variant: 'side', orientation: 'side', number: '8' }, keywords: ['jugador', 'local', 'lateral'] },
  { assetId: 'player.away.front', label: 'Jugador visitante', category: 'players', type: 'player-away', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#f97316', stroke: '#ffedd5' }, defaultData: { team: 'away', variant: 'front', orientation: 'front', number: '11' }, keywords: ['jugador', 'visitante'] },
  { assetId: 'player.away.back', label: 'Jugador visitante espalda', category: 'players', type: 'player-away', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#ea580c', stroke: '#fed7aa' }, defaultData: { team: 'away', variant: 'back', orientation: 'back', number: '11' }, keywords: ['jugador', 'visitante', 'espalda'] },
  { assetId: 'player.away.side', label: 'Jugador visitante lateral', category: 'players', type: 'player-away', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#fb923c', stroke: '#fed7aa' }, defaultData: { team: 'away', variant: 'side', orientation: 'side', number: '11' }, keywords: ['jugador', 'visitante', 'lateral'] },
  { assetId: 'player.joker.front', label: 'Comodín', category: 'players', type: 'player-joker', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#a855f7', stroke: '#f3e8ff' }, defaultData: { team: 'joker', variant: 'front', orientation: 'front', number: 'J' }, keywords: ['comodin', 'joker'] },
  { assetId: 'player.with-ball', label: 'Jugador con balón', category: 'players', type: 'ball-carrier', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#0ea5e9', stroke: '#e0f2fe' }, defaultData: { team: 'home', variant: 'with-ball', orientation: 'front', number: '9' }, keywords: ['jugador', 'balon'] },
  { assetId: 'player.numbered', label: 'Jugador numerado', category: 'players', type: 'numbered-player', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#1d4ed8', stroke: '#dbeafe' }, defaultData: { team: 'home', variant: 'numbered', orientation: 'front', number: '10' }, keywords: ['jugador', 'numerado'] },
  { assetId: 'player.named', label: 'Jugador con nombre', category: 'players', type: 'player-home', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#2563eb', stroke: '#dbeafe' }, defaultData: { team: 'home', variant: 'named', orientation: 'front', number: '8', name: 'Jugador' }, keywords: ['jugador', 'nombre'] },
  { assetId: 'player.injured', label: 'Jugador lesionado', category: 'players', type: 'injured-player', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#ef4444', stroke: '#fee2e2' }, defaultData: { team: 'home', variant: 'injured', orientation: 'front', number: '!' }, keywords: ['jugador', 'lesionado'] },
  { assetId: 'goalkeeper.home.front', label: 'Portero local', category: 'goalkeepers', type: 'goalkeeper-home', layerId: 'players', previewKind: 'goalkeeper', defaultSize: { width: 46, height: 46 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#16a34a', stroke: '#dcfce7' }, defaultData: { team: 'home', role: 'goalkeeper', variant: 'front', orientation: 'front', number: '1' }, keywords: ['portero', 'local'] },
  { assetId: 'goalkeeper.home.back', label: 'Portero local espalda', category: 'goalkeepers', type: 'goalkeeper-home', layerId: 'players', previewKind: 'goalkeeper', defaultSize: { width: 46, height: 46 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#15803d', stroke: '#bbf7d0' }, defaultData: { team: 'home', role: 'goalkeeper', variant: 'back', orientation: 'back', number: '1' }, keywords: ['portero', 'local', 'espalda'] },
  { assetId: 'goalkeeper.away.front', label: 'Portero visitante', category: 'goalkeepers', type: 'goalkeeper-away', layerId: 'players', previewKind: 'goalkeeper', defaultSize: { width: 46, height: 46 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#f59e0b', stroke: '#fef3c7' }, defaultData: { team: 'away', role: 'goalkeeper', variant: 'front', orientation: 'front', number: '13' }, keywords: ['portero', 'visitante'] },
  { assetId: 'goalkeeper.away.back', label: 'Portero visitante espalda', category: 'goalkeepers', type: 'goalkeeper-away', layerId: 'players', previewKind: 'goalkeeper', defaultSize: { width: 46, height: 46 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#d97706', stroke: '#fde68a' }, defaultData: { team: 'away', role: 'goalkeeper', variant: 'back', orientation: 'back', number: '13' }, keywords: ['portero', 'visitante', 'espalda'] },
  { assetId: 'coach.default', label: 'Entrenador', category: 'players', type: 'coach', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#0f172a', stroke: '#cbd5e1' }, defaultData: { role: 'coach', team: 'neutral', variant: 'default', orientation: 'side', number: 'C' }, keywords: ['entrenador'] },
  { assetId: 'referee.default', label: 'Árbitro', category: 'players', type: 'referee', layerId: 'players', previewKind: 'player', defaultSize: { width: 44, height: 44 }, defaultStyle: { ...PLAYER_BASE_STYLE, fill: '#111827', stroke: '#f8fafc' }, defaultData: { role: 'referee', team: 'neutral', variant: 'default', orientation: 'front', number: 'R' }, keywords: ['arbitro'] },
  { assetId: 'ball.standard', label: 'Balón', category: 'equipment', type: 'ball', layerId: 'ball', previewKind: 'ball', defaultSize: { width: 18, height: 18 }, defaultStyle: { fill: '#ffffff', stroke: '#0f172a', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['balon'] },
  { assetId: 'cone.standard', label: 'Cono', category: 'equipment', type: 'cone', layerId: 'equipment', previewKind: 'cone', defaultSize: { width: 26, height: 30 }, defaultStyle: { fill: '#f97316', stroke: '#7c2d12', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['cono'] },
  { assetId: 'cone.high', label: 'Cono alto', category: 'equipment', type: 'high-cone', layerId: 'equipment', previewKind: 'cone', defaultSize: { width: 24, height: 42 }, defaultStyle: { fill: '#fb923c', stroke: '#7c2d12', strokeWidth: 2 }, defaultData: { variant: 'high' }, keywords: ['cono', 'alto'] },
  { assetId: 'pole.standard', label: 'Pica', category: 'equipment', type: 'pole', layerId: 'equipment', previewKind: 'pole', defaultSize: { width: 10, height: 44 }, defaultStyle: { fill: '#fbbf24', stroke: '#78350f', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['pica', 'poste'] },
  { assetId: 'hoop.standard', label: 'Aro', category: 'equipment', type: 'hoop', layerId: 'equipment', previewKind: 'icon', defaultSize: { width: 28, height: 28 }, defaultStyle: { fill: 'rgba(0,0,0,0)', stroke: '#facc15', strokeWidth: 4 }, defaultData: { variant: 'standard' }, keywords: ['aro'] },
  { assetId: 'ladder.standard', label: 'Escalera', category: 'equipment', type: 'bench', layerId: 'equipment', previewKind: 'ladder', defaultSize: { width: 120, height: 26 }, defaultStyle: { fill: 'rgba(15,23,42,0.22)', stroke: '#f8fafc', strokeWidth: 2 }, defaultData: { variant: 'ladder', steps: 6 }, keywords: ['escalera'] },
  { assetId: 'fence.standard', label: 'Valla', category: 'equipment', type: 'mini-goal', layerId: 'equipment', previewKind: 'fence', defaultSize: { width: 120, height: 26 }, defaultStyle: { fill: 'rgba(255,255,255,0.02)', stroke: '#e2e8f0', strokeWidth: 2 }, defaultData: { variant: 'fence' }, keywords: ['valla'] },
  { assetId: 'mannequin.standard', label: 'Maniquí', category: 'equipment', type: 'mannequin', layerId: 'equipment', previewKind: 'mannequin', defaultSize: { width: 24, height: 72 }, defaultStyle: { fill: 'rgba(255,255,255,0.08)', stroke: '#cbd5e1', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['maniqui'] },
  { assetId: 'bib.standard', label: 'Peto', category: 'equipment', type: 'bib', layerId: 'equipment', previewKind: 'bib', defaultSize: { width: 34, height: 40 }, defaultStyle: { fill: '#22c55e', stroke: '#14532d', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['peto'] },
  { assetId: 'mini-goal.standard', label: 'Miniportería', category: 'equipment', type: 'mini-goal', layerId: 'equipment', previewKind: 'miniGoal', defaultSize: { width: 54, height: 24 }, defaultStyle: { fill: 'rgba(255,255,255,0.04)', stroke: '#e2e8f0', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['miniporteria'] },
  { assetId: 'goal.standard', label: 'Portería reglamentaria', category: 'equipment', type: 'goal', layerId: 'equipment', previewKind: 'goal', defaultSize: { width: 80, height: 34 }, defaultStyle: { fill: 'rgba(255,255,255,0.04)', stroke: '#f8fafc', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['porteria', 'reglamentaria'] },
  { assetId: 'goal.mobile', label: 'Portería móvil', category: 'equipment', type: 'goal', layerId: 'equipment', previewKind: 'goal', defaultSize: { width: 80, height: 34 }, defaultStyle: { fill: 'rgba(255,255,255,0.02)', stroke: '#e2e8f0', strokeWidth: 2 }, defaultData: { variant: 'mobile' }, keywords: ['porteria', 'movil'] },
  { assetId: 'bench.standard', label: 'Banquillo', category: 'equipment', type: 'bench', layerId: 'equipment', previewKind: 'bench', defaultSize: { width: 96, height: 28 }, defaultStyle: { fill: 'rgba(15,23,42,0.55)', stroke: '#94a3b8', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['banquillo'] },
  { assetId: 'marker.standard', label: 'Marcador', category: 'equipment', type: 'marker', layerId: 'equipment', previewKind: 'marker', defaultSize: { width: 18, height: 18 }, defaultStyle: { fill: '#f59e0b', stroke: '#78350f', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['marcador'] },
  { assetId: 'flag.standard', label: 'Banderín', category: 'equipment', type: 'flag', layerId: 'equipment', previewKind: 'flag', defaultSize: { width: 22, height: 54 }, defaultStyle: { fill: '#f8fafc', stroke: '#0f172a', strokeWidth: 2 }, defaultData: { variant: 'standard' }, keywords: ['banderin', 'bandera'] },
  { assetId: 'arrow.straight', label: 'Flecha recta', category: 'arrows', type: 'arrow-straight', layerId: 'paths', previewKind: 'arrow', defaultSize: { width: 140, height: 24 }, defaultStyle: { stroke: '#38bdf8', strokeWidth: 4, fill: '#38bdf8' }, defaultData: { variant: 'straight', points: [0, 12, 140, 12] }, keywords: ['flecha', 'recta'] },
  { assetId: 'arrow.curved', label: 'Flecha curva', category: 'arrows', type: 'arrow-curved', layerId: 'paths', previewKind: 'arrowCurve', defaultSize: { width: 150, height: 80 }, defaultStyle: { stroke: '#22c55e', strokeWidth: 4, fill: '#22c55e' }, defaultData: { variant: 'curved', points: [0, 60, 60, 0, 150, 36] }, keywords: ['flecha', 'curva'] },
  { assetId: 'arrow.segmented', label: 'Flecha segmentada', category: 'arrows', type: 'arrow-segmented', layerId: 'paths', previewKind: 'arrowSegmented', defaultSize: { width: 150, height: 30 }, defaultStyle: { stroke: '#38bdf8', strokeWidth: 4, fill: '#38bdf8', dash: [12, 8] }, defaultData: { variant: 'segmented', points: [0, 15, 38, 15, 82, 6, 150, 15] }, keywords: ['flecha', 'segmentada'] },
  { assetId: 'arrow.dashed', label: 'Flecha discontinua', category: 'arrows', type: 'line-dashed', layerId: 'paths', previewKind: 'arrowDashed', defaultSize: { width: 140, height: 18 }, defaultStyle: { stroke: '#f8fafc', strokeWidth: 3, dash: [12, 8] }, defaultData: { variant: 'dashed', points: [0, 9, 140, 9] }, keywords: ['flecha', 'discontinua'] },
  { assetId: 'arrow.double', label: 'Flecha doble', category: 'arrows', type: 'arrow-double', layerId: 'paths', previewKind: 'arrowDouble', defaultSize: { width: 150, height: 30 }, defaultStyle: { stroke: '#38bdf8', strokeWidth: 4, fill: '#38bdf8' }, defaultData: { variant: 'double', points: [0, 15, 40, 15, 80, 6, 150, 15] }, keywords: ['flecha', 'doble'] },
  { assetId: 'arrow.pass', label: 'Flecha de pase', category: 'arrows', type: 'arrow-pass', layerId: 'paths', previewKind: 'arrow', defaultSize: { width: 140, height: 24 }, defaultStyle: { stroke: '#0ea5e9', strokeWidth: 4, fill: '#0ea5e9' }, defaultData: { variant: 'pass', points: [0, 12, 140, 12] }, keywords: ['pase'] },
  { assetId: 'arrow.run', label: 'Flecha de carrera', category: 'arrows', type: 'arrow-run', layerId: 'paths', previewKind: 'arrow', defaultSize: { width: 140, height: 24 }, defaultStyle: { stroke: '#f59e0b', strokeWidth: 4, fill: '#f59e0b' }, defaultData: { variant: 'run', points: [0, 12, 140, 12] }, keywords: ['carrera'] },
  { assetId: 'arrow.ball', label: 'Trayectoria de balón', category: 'arrows', type: 'trajectory', layerId: 'paths', previewKind: 'route', defaultSize: { width: 160, height: 80 }, defaultStyle: { stroke: '#fbbf24', strokeWidth: 4, fill: '#fbbf24' }, defaultData: { variant: 'ball', points: [0, 60, 60, 4, 120, 24, 160, 64] }, keywords: ['trayectoria', 'balon'] },
  { assetId: 'arrow.line', label: 'Línea continua', category: 'arrows', type: 'line', layerId: 'paths', previewKind: 'line', defaultSize: { width: 140, height: 18 }, defaultStyle: { stroke: '#f8fafc', strokeWidth: 3 }, defaultData: { variant: 'line', points: [0, 9, 140, 9] }, keywords: ['linea', 'continua'] },
  { assetId: 'zone.rect', label: 'Zona rectangular', category: 'zones', type: 'zone-rect', layerId: 'zones', previewKind: 'zoneRect', defaultSize: { width: 180, height: 110 }, defaultStyle: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 }, defaultData: { variant: 'rect' }, keywords: ['zona', 'rectangulo'] },
  { assetId: 'zone.circle', label: 'Zona circular', category: 'zones', type: 'zone-circle', layerId: 'zones', previewKind: 'zoneCircle', defaultSize: { width: 110, height: 110 }, defaultStyle: { fill: 'rgba(59,130,246,0.16)', stroke: '#60a5fa', strokeWidth: 2 }, defaultData: { variant: 'circle' }, keywords: ['zona', 'circulo'] },
  { assetId: 'zone.ellipse', label: 'Zona elíptica', category: 'zones', type: 'zone-ellipse', layerId: 'zones', previewKind: 'zoneEllipse', defaultSize: { width: 140, height: 90 }, defaultStyle: { fill: 'rgba(59,130,246,0.16)', stroke: '#60a5fa', strokeWidth: 2 }, defaultData: { variant: 'ellipse' }, keywords: ['zona', 'elipse'] },
  { assetId: 'zone.polygon', label: 'Zona polígono', category: 'zones', type: 'zone-polygon', layerId: 'zones', previewKind: 'zonePolygon', defaultSize: { width: 160, height: 120 }, defaultStyle: { fill: 'rgba(59,130,246,0.14)', stroke: '#60a5fa', strokeWidth: 2 }, defaultData: { variant: 'polygon', points: [0, 80, 40, 20, 80, 0, 120, 20, 160, 80, 120, 120, 40, 120] }, keywords: ['zona', 'poligono'] },
  { assetId: 'zone.free', label: 'Zona libre', category: 'zones', type: 'zone-free', layerId: 'zones', previewKind: 'zoneFree', defaultSize: { width: 160, height: 120 }, defaultStyle: { fill: 'rgba(59,130,246,0.14)', stroke: '#60a5fa', strokeWidth: 2 }, defaultData: { variant: 'free', points: [0, 90, 30, 40, 60, 20, 110, 0, 160, 16, 150, 96, 90, 120, 28, 110] }, keywords: ['zona', 'libre'] },
  { assetId: 'lane.standard', label: 'Carril', category: 'zones', type: 'lane', layerId: 'zones', previewKind: 'lane', defaultSize: { width: 120, height: 110 }, defaultStyle: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 }, defaultData: { variant: 'lane' }, keywords: ['carril'] },
  { assetId: 'stripe.horizontal', label: 'Franja horizontal', category: 'zones', type: 'stripe-h', layerId: 'zones', previewKind: 'stripe', defaultSize: { width: 180, height: 60 }, defaultStyle: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 }, defaultData: { variant: 'horizontal' }, keywords: ['franja', 'horizontal'] },
  { assetId: 'stripe.vertical', label: 'Franja vertical', category: 'zones', type: 'stripe-v', layerId: 'zones', previewKind: 'stripe', defaultSize: { width: 60, height: 180 }, defaultStyle: { fill: 'rgba(34,197,94,0.18)', stroke: '#4ade80', strokeWidth: 2 }, defaultData: { variant: 'vertical' }, keywords: ['franja', 'vertical'] },
  { assetId: 'sector.standard', label: 'Sector', category: 'zones', type: 'sector', layerId: 'zones', previewKind: 'sector', defaultSize: { width: 160, height: 120 }, defaultStyle: { fill: 'rgba(59,130,246,0.14)', stroke: '#60a5fa', strokeWidth: 2 }, defaultData: { variant: 'sector' }, keywords: ['sector'] },
  { assetId: 'text.label', label: 'Texto', category: 'graphics', type: 'text', layerId: 'texts', previewKind: 'text', defaultSize: { width: 180, height: 40 }, defaultStyle: { textColor: '#f8fafc', fontSize: 24, fontWeight: 700 }, defaultData: { label: 'Texto táctico', variant: 'text' }, keywords: ['texto'] },
  { assetId: 'label.numeric', label: 'Etiqueta numérica', category: 'graphics', type: 'label', layerId: 'texts', previewKind: 'label', defaultSize: { width: 32, height: 32 }, defaultStyle: { fill: '#0f172a', stroke: '#e2e8f0', strokeWidth: 2, textColor: '#f8fafc', fontSize: 16 }, defaultData: { label: '1', variant: 'numeric' }, keywords: ['etiqueta', 'numero'] },
  { assetId: 'icon.start', label: 'Inicio', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#14532d', stroke: '#86efac', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '▶', variant: 'start' }, keywords: ['inicio'] },
  { assetId: 'icon.end', label: 'Final', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#7f1d1d', stroke: '#fca5a5', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '■', variant: 'end' }, keywords: ['final'] },
  { assetId: 'icon.pause', label: 'Pausa', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#1e293b', stroke: '#cbd5e1', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '‖', variant: 'pause' }, keywords: ['pausa'] },
  { assetId: 'icon.target', label: 'Objetivo', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#312e81', stroke: '#c7d2fe', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '◎', variant: 'target' }, keywords: ['objetivo'] },
  { assetId: 'icon.clock', label: 'Cronómetro', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#0f172a', stroke: '#38bdf8', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '⏱', variant: 'clock' }, keywords: ['cronometro'] },
  { assetId: 'icon.alert', label: 'Atención', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#92400e', stroke: '#fde68a', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '!', variant: 'alert' }, keywords: ['atencion'] },
  { assetId: 'icon.exercise', label: 'Ejercicio', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#14532d', stroke: '#86efac', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: 'EJ', variant: 'exercise' }, keywords: ['ejercicio'] },
  { assetId: 'icon.note', label: 'Nota técnica', category: 'graphics', type: 'label', layerId: 'annotations', previewKind: 'icon', defaultSize: { width: 34, height: 34 }, defaultStyle: { fill: '#1e1b4b', stroke: '#c4b5fd', strokeWidth: 2, textColor: '#f8fafc', fontSize: 14 }, defaultData: { label: '✎', variant: 'note' }, keywords: ['nota', 'tecnica'] },
];

const DEFAULT_ASSET_ID_BY_TYPE: Record<SceneObjectType, string> = {
  player: 'player.home.front',
  goalkeeper: 'goalkeeper.home.front',
  'player-home': 'player.home.front',
  'player-away': 'player.away.front',
  'player-joker': 'player.joker.front',
  'goalkeeper-home': 'goalkeeper.home.front',
  'goalkeeper-away': 'goalkeeper.away.front',
  coach: 'coach.default',
  referee: 'referee.default',
  'injured-player': 'player.injured',
  'ball-carrier': 'player.with-ball',
  'numbered-player': 'player.numbered',
  ball: 'ball.standard',
  cone: 'cone.standard',
  'high-cone': 'cone.high',
  pole: 'pole.standard',
  goal: 'goal.standard',
  hoop: 'hoop.standard',
  'mini-goal': 'mini-goal.standard',
  bench: 'bench.standard',
  marker: 'marker.standard',
  flag: 'flag.standard',
  mannequin: 'mannequin.standard',
  bib: 'bib.standard',
  'arrow-straight': 'arrow.straight',
  'arrow-curved': 'arrow.curved',
  'arrow-segmented': 'arrow.segmented',
  'arrow-double': 'arrow.double',
  'arrow-pass': 'arrow.pass',
  'arrow-run': 'arrow.run',
  trajectory: 'arrow.ball',
  line: 'arrow.line',
  'line-dashed': 'arrow.dashed',
  'zone-rect': 'zone.rect',
  'zone-circle': 'zone.circle',
  'zone-ellipse': 'zone.ellipse',
  'zone-polygon': 'zone.polygon',
  'zone-free': 'zone.free',
  lane: 'lane.standard',
  'stripe-h': 'stripe.horizontal',
  'stripe-v': 'stripe.vertical',
  sector: 'sector.standard',
  text: 'text.label',
  label: 'label.numeric',
  'legacy-shape': 'label.numeric',
};

const ASSET_MAP = new Map<string, AssetDefinition>(
  ASSET_SEEDS.map((asset) => [
    asset.assetId,
    { ...asset, keywords: asset.keywords || [] } as AssetDefinition,
  ])
);
const ASSETS_BY_CATEGORY = ASSET_SEEDS.reduce<Record<AssetCategoryId, AssetDefinition[]>>(
  (accumulator, asset) => {
    const group = accumulator[asset.category] || [];
    group.push({ ...asset, keywords: asset.keywords || [] } as AssetDefinition);
    accumulator[asset.category] = group;
    return accumulator;
  },
  {
    players: [],
    goalkeepers: [],
    equipment: [],
    arrows: [],
    zones: [],
    graphics: [],
  }
);

export function listAssetCategories(): Array<{
  id: AssetCategoryId;
  label: string;
  count: number;
}> {
  return [
    { id: 'players', label: 'Jugadores', count: ASSETS_BY_CATEGORY.players.length },
    { id: 'goalkeepers', label: 'Porteros', count: ASSETS_BY_CATEGORY.goalkeepers.length },
    { id: 'equipment', label: 'Material', count: ASSETS_BY_CATEGORY.equipment.length },
    { id: 'arrows', label: 'Flechas', count: ASSETS_BY_CATEGORY.arrows.length },
    { id: 'zones', label: 'Zonas', count: ASSETS_BY_CATEGORY.zones.length },
    { id: 'graphics', label: 'Gráfica', count: ASSETS_BY_CATEGORY.graphics.length },
  ];
}

export function listAssets(category?: AssetCategoryId): AssetDefinition[] {
  if (category) {
    return [...ASSETS_BY_CATEGORY[category]];
  }
  return [...ASSET_SEEDS].map((asset) => ({ ...asset, keywords: asset.keywords || [] }));
}

export function searchAssets(query: string, category?: AssetCategoryId): AssetDefinition[] {
  const value = query.trim().toLowerCase();
  const source = listAssets(category);
  if (!value) {
    return source;
  }
  return source.filter((asset) =>
    [asset.label, asset.assetId, asset.category, ...asset.keywords].some((part) =>
      String(part).toLowerCase().includes(value)
    )
  );
}

export function getAssetDefinition(assetId?: string | null): AssetDefinition | null {
  if (!assetId) {
    return null;
  }
  return ASSET_MAP.get(assetId) || null;
}

export function getDefaultAssetIdForType(type: SceneObjectType, variant?: string): string {
  if (variant && type === 'player-home') {
    const mappedVariant = variant === 'back' ? 'player.home.back' : variant === 'side' ? 'player.home.side' : 'player.home.front';
    return mappedVariant;
  }
  return DEFAULT_ASSET_ID_BY_TYPE[type] || 'label.numeric';
}

export function resolveAssetId(
  assetId: string | undefined,
  type: SceneObjectType,
  variant?: string
): string {
  const normalized = String(assetId || '').trim();
  if (normalized) {
    return normalized;
  }
  return getDefaultAssetIdForType(type, variant);
}

export function resolveAssetDefinition(
  assetId: string | undefined,
  type: SceneObjectType,
  variant?: string
): AssetDefinition {
  const resolvedAssetId = resolveAssetId(assetId, type, variant);
  return (
    ASSET_MAP.get(resolvedAssetId) ||
    ASSET_MAP.get(getDefaultAssetIdForType(type, variant)) ||
    ASSET_MAP.get('label.numeric') ||
    (ASSET_SEEDS[0] as AssetDefinition)
  );
}

export function resolveAssetLayer(assetId: string | undefined, type: SceneObjectType): SceneLayerId {
  return resolveAssetDefinition(assetId, type).layerId;
}

export function assetCatalogSearch(query: string) {
  return searchAssets(query);
}

export function assetCategoryLabel(category: AssetCategoryId): string {
  return listAssetCategories().find((item) => item.id === category)?.label || category;
}

export function isKnownAssetId(assetId: string | undefined | null): assetId is string {
  return Boolean(assetId && ASSET_MAP.has(assetId));
}

export function warnUnknownAssetId(assetId: string | undefined | null) {
  if (
    typeof window !== 'undefined' &&
    window.location &&
    window.location.hostname === 'localhost' &&
    assetId &&
    !isKnownAssetId(assetId)
  ) {
    console.warn(`[tactical-editor] Unknown asset "${assetId}", falling back to vector generic renderer.`);
  }
}

export function getAssetPreviewIcon(asset: AssetDefinition): string {
  switch (asset.previewKind) {
    case 'player':
    case 'goalkeeper':
      return '◉';
    case 'ball':
      return '◍';
    case 'cone':
      return '▲';
    case 'pole':
      return '│';
    case 'goal':
      return '▭';
    case 'miniGoal':
      return '▱';
    case 'bench':
      return '▤';
    case 'marker':
      return '●';
    case 'flag':
      return '⚑';
    case 'mannequin':
      return '⟂';
    case 'bib':
      return '◫';
    case 'ladder':
      return '⋯';
    case 'fence':
      return '≣';
    case 'arrow':
    case 'arrowCurve':
    case 'arrowSegmented':
    case 'arrowDashed':
    case 'arrowDouble':
    case 'route':
    case 'line':
      return '→';
    case 'zoneRect':
    case 'zoneCircle':
    case 'zoneEllipse':
    case 'zonePolygon':
    case 'zoneFree':
    case 'lane':
    case 'stripe':
    case 'sector':
      return '▢';
    case 'text':
    case 'label':
    case 'icon':
      return '✎';
    default:
      return '◼';
  }
}
