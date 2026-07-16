export type TaskEditorPanel = {
  id?: string;
  kind?: string;
  title?: string;
  image_url?: string;
  embed_url?: string;
};

export type TaskEditorTrack = {
  uid?: string;
  label?: string;
  kind?: string;
  keyframe_count?: number;
  first_at?: number;
  last_at?: number;
  moving?: boolean;
};

export type TacticalCanvasObject = Record<string, unknown> & {
  type?: string;
  left?: number;
  top?: number;
  width?: number;
  height?: number;
  scaleX?: number;
  scaleY?: number;
  radius?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  angle?: number;
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  text?: string;
  src?: string;
  visible?: boolean;
  opacity?: number;
  fontSize?: number;
  strokeDashArray?: number[];
  lockMovementX?: boolean;
  lockMovementY?: boolean;
  data?: Record<string, unknown>;
  id?: string;
  name?: string;
};

export type TacticalCanvasState = {
  version?: string;
  objects: TacticalCanvasObject[];
  sceneObjects?: Array<Record<string, unknown>>;
  schemaVersion?: number;
  [key: string]: unknown;
};

export type TaskEditorDocument = {
  task: {
    id: number;
    title: string;
    block_label: string;
    duration_minutes: number;
    workflow_status?: string;
    presentation_format?: 'club' | 'uefa';
  };
  sheet?: Record<string, unknown>;
  players: {
    groups?: Array<Record<string, unknown>>;
    summary?: string;
    total: number;
  };
  materials: {
    groups?: Array<Record<string, unknown>>;
    summary?: string;
  };
  engine: {
    single_document: boolean;
    timeline_pro?: boolean;
    shared_state?: boolean;
    single_3d_engine: boolean;
    legacy_surfaces_unified?: boolean;
    graphic_panels_count: number;
    sequence_steps_count?: number;
    track_count: number;
    keyframe_count: number;
    moving_track_count?: number;
  };
  graphic: {
    preview_2d_url?: string;
    preview_3d_url?: string;
    preview_3d_embed_url?: string;
    panels?: TaskEditorPanel[];
    canvas_state: TacticalCanvasState;
    canvas_width: number;
    canvas_height: number;
    updated_at?: string;
  };
  sequence: {
    frames: Array<Record<string, unknown>>;
    frame_cards: Array<Record<string, unknown>>;
    tracks: TaskEditorTrack[];
  };
  exports: {
    targets: Array<Record<string, unknown>>;
    jobs: Array<Record<string, unknown>>;
  };
  ai: {
    has_analysis: boolean;
    summary: string;
    preview_url?: string;
    generated?: boolean;
    provider?: string;
    model?: string;
    prompt?: string;
  };
  urls: Record<string, string>;
};
