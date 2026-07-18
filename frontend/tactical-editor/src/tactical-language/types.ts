import type {
  AnimationSequence,
  AnimationTrack,
  AnimationTimeline,
  SceneLayerId,
  SceneObject,
  TacticalScene,
} from '../editor/core/sceneSchema';

export type TacticalSceneInput = TacticalScene;

export type TacticalVerb =
  | 'PASS'
  | 'RECEIVE'
  | 'CARRY'
  | 'RUN'
  | 'SUPPORT'
  | 'HOLD'
  | 'CREATE_SPACE'
  | 'OCCUPY_SPACE'
  | 'BUILD_UP'
  | 'PROGRESSION';

export type TacticalPhaseKind = 'BUILD_UP' | 'PROGRESSION';

export type TacticalTargetKind = 'actor' | 'zone' | 'ball' | 'none';

export type TacticalConditionKind =
  | 'WHEN'
  | 'IF'
  | 'AFTER'
  | 'BEFORE'
  | 'UNTIL'
  | 'WHILE'
  | 'PARALLEL_WITH'
  | 'OPTIONAL';

export type TacticalRelationKind =
  | 'after'
  | 'before'
  | 'wait_for'
  | 'blocks'
  | 'requires'
  | 'produces'
  | 'triggers'
  | 'success'
  | 'failure'
  | 'optional'
  | 'parallel'
  | 'simultaneous'
  | 'mutex';

export type TacticalIssueSeverity = 'error' | 'warning' | 'info';

export interface TacticalTargetRef {
  kind: TacticalTargetKind;
  actorId?: string;
  zoneId?: string;
  objectId?: string;
  label?: string;
}

export interface TacticalCondition {
  kind: TacticalConditionKind;
  expression: string;
  confidence: number;
  target?: TacticalTargetRef;
  subjectId?: string;
}

export interface TacticalResult {
  kind: 'BALL_POSSESSION' | 'MOVE_ACTOR' | 'OCCUPY_ZONE' | 'START_PHASE' | 'END_PHASE';
  actorId?: string;
  zoneId?: string;
  ballCarrierId?: string;
  value?: string | number | boolean;
}

export interface TacticalActorRef {
  id: string;
  objectId: string;
  kind: 'goalkeeper' | 'player' | 'ball';
  role: string;
  team: 'home' | 'away' | 'neutral' | 'joker';
  label: string;
  layerId: SceneLayerId;
  x: number;
  y: number;
  width: number;
  height: number;
  assetId: string | null;
  objectType: SceneObject['type'];
}

export interface TacticalZoneRef {
  id: string;
  objectId: string;
  label: string;
  kind: 'objective' | 'support' | 'lane' | 'area';
  layerId: SceneLayerId;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TacticalArrowRef {
  id: string;
  objectId: string;
  kind: 'pass' | 'run' | 'trajectory' | 'line';
  label: string;
  layerId: SceneLayerId;
  start: { x: number; y: number };
  end: { x: number; y: number };
  points: Array<{ x: number; y: number }>;
}

export interface TacticalStatement {
  id: string;
  verb: TacticalVerb;
  subjectId: string;
  target?: TacticalTargetRef;
  conditions: TacticalCondition[];
  result: TacticalResult;
  priority: number;
  confidence: number;
  phaseId?: string;
  parallelGroupId?: string;
  originObjectIds: string[];
}

export interface TacticalDependency {
  id: string;
  fromStatementId: string;
  toStatementId: string;
  relation: TacticalRelationKind;
}

export interface TacticalObjective {
  id: string;
  label: string;
  kind: TacticalPhaseKind;
  targetZoneId?: string;
  confidence: number;
}

export interface TacticalPhase {
  id: string;
  kind: TacticalPhaseKind;
  label: string;
  startTime: number;
  endTime: number;
  statementIds: string[];
  objectiveId?: string;
  confidence: number;
}

export interface BallPossessionState {
  state: 'free' | 'controlled' | 'in_flight' | 'receiving';
  carrierId?: string;
  sourceStatementId?: string;
  targetStatementId?: string;
  releaseTime?: number;
  receiveTime?: number;
}

export interface TacticalValidationIssue {
  id: string;
  severity: TacticalIssueSeverity;
  code: string;
  message: string;
  entityIds: string[];
  relatedStatementIds: string[];
  suggestion?: string;
}

export interface ExecutionNode {
  id: string;
  statementId: string;
  kind: 'action' | 'phase' | 'ball_event' | 'support' | 'constraint';
  actorId?: string;
  targetId?: string;
  zoneId?: string;
  phaseId?: string;
  priority: number;
  confidence: number;
  status: 'pending' | 'resolved' | 'blocked' | 'conflicted';
  produces: string[];
  requires: string[];
  blocks: string[];
  trace: ResolverTraceRef[];
}

export interface ExecutionEdge {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  relation: TacticalRelationKind;
  strength: number;
  confidence: number;
}

export interface ExecutionConstraint {
  id: string;
  kind: 'time_order' | 'possession' | 'zone_access' | 'actor_state' | 'ball_state' | 'mutual_exclusion' | 'phase_boundary';
  subjectIds: string[];
  expression: string;
  severity: TacticalIssueSeverity;
  confidence: number;
}

export interface ExecutionGroup {
  id: string;
  nodeIds: string[];
  kind: 'parallel' | 'synchronized' | 'exclusive' | 'ordered';
  priority: number;
  confidence: number;
}

export interface ExecutionBarrier {
  id: string;
  kind:
    | 'ball_arrival'
    | 'pass_completion'
    | 'receive_completion'
    | 'position_reached'
    | 'phase_start'
    | 'phase_end'
    | 'transition_complete';
  subjectIds: string[];
  condition: string;
  strict: boolean;
  confidence: number;
}

export interface ExecutionWindow {
  id: string;
  nodeId: string;
  earliestStart: number;
  latestStart: number;
  earliestEnd: number;
  latestEnd: number;
  confidence: number;
}

export interface TacticalExecutionGraph {
  nodes: ExecutionNode[];
  edges: ExecutionEdge[];
  constraints: ExecutionConstraint[];
  groups: ExecutionGroup[];
  barriers: ExecutionBarrier[];
  windows: ExecutionWindow[];
}

export interface ResolverTraceRef {
  statementId: string;
  ruleId: string;
  confidence: number;
  warnings: string[];
  resolverStep:
    | 'normalization'
    | 'graph-build'
    | 'dependency-resolution'
    | 'barrier-resolution'
    | 'conflict-resolution'
    | 'possession'
    | 'timing'
    | 'compilation'
    | 'finalization';
  logicalTimestamp: number;
  originObjectIds: string[];
  originRuleId?: string;
}

export interface TacticalLanguageDocument {
  schemaVersion: number;
  language: 'tactical-language';
  documentId: string;
  metadata: {
    title: string;
    sport: 'football';
    createdAt: string;
    updatedAt: string;
  };
  actors: TacticalActorRef[];
  zones: TacticalZoneRef[];
  arrows: TacticalArrowRef[];
  statements: TacticalStatement[];
  phases: TacticalPhase[];
  objectives: TacticalObjective[];
  dependencies: TacticalDependency[];
  possession: BallPossessionState;
  confidence: number;
  validationIssues: TacticalValidationIssue[];
}

export interface TacticalCompilationResult {
  scene: TacticalScene;
  language: TacticalLanguageDocument;
  plan: ResolvedTacticalPlan;
  possession: BallPossessionState;
  timeline: AnimationTimeline;
  tracks: AnimationTrack[];
  keyframeCount: number;
  validationIssues: TacticalValidationIssue[];
}

export interface ResolverContext {
  documentId: string;
  language: TacticalLanguageDocument;
  confidenceFloor: number;
  strictMode: boolean;
}

export interface ResolverIssue {
  id: string;
  severity: TacticalIssueSeverity;
  code: string;
  message: string;
  entityIds: string[];
  relatedStatementIds: string[];
  suggestion?: string;
}

export interface ResolvedPlan {
  documentId: string;
  graph: TacticalExecutionGraph;
  executionOrder: string[];
  possession: BallPossessionState;
  warnings: ResolverIssue[];
  confidence: number;
  traceability: ResolverTraceRef[];
}

export interface ResolverResult {
  plan: ResolvedPlan;
  issues: ResolverIssue[];
  blocked: boolean;
}

export type ResolvedTacticalPlan = ResolvedPlan;
