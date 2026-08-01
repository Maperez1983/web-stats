import type { TacticalScene } from '../editor/core/sceneSchema';
import {
  arrowVector,
  findActorByLabelLike,
  findActorByRole,
  type NormalizedTacticalScene,
} from './normalizer';
import type {
  BallPossessionState,
  TacticalCondition,
  TacticalDependency,
  TacticalLanguageDocument,
  TacticalObjective,
  TacticalPhase,
  TacticalResult,
  TacticalStatement,
  TacticalTargetRef,
  TacticalValidationIssue,
} from './types';

type TacticalScenarioKind = 'build_up' | 'rondo' | 'wall_pass' | 'finishing' | 'technical_circuit';

type ScenarioBuildResult = {
  statements: TacticalStatement[];
  phases: TacticalPhase[];
  objectives: TacticalObjective[];
  dependencies: TacticalDependency[];
  possession: BallPossessionState;
  validationIssues: TacticalValidationIssue[];
  confidence: number;
};

function labelText(value: unknown): string {
  return String(value || '').trim().toLowerCase();
}

function sceneTitle(context: NormalizedTacticalScene) {
  return labelText(context.scene.metadata.title);
}

function hasText(context: NormalizedTacticalScene, patterns: string[]) {
  const lowered = patterns.map((item) => item.toLowerCase());
  return (
    context.actors.some((actor) => lowered.some((pattern) => labelText(actor.label).includes(pattern))) ||
    context.zones.some((zone) => lowered.some((pattern) => labelText(zone.label).includes(pattern))) ||
    context.arrows.some((arrow) => lowered.some((pattern) => labelText(arrow.label).includes(pattern)))
  );
}

function countByRole(context: NormalizedTacticalScene, role: string) {
  return context.actors.filter((actor) => actor.role === role).length;
}

function actorByRole(context: NormalizedTacticalScene, roleCandidates: string[]) {
  return (
    findActorByLabelLike(context, roleCandidates) ||
    findActorByRole(context, roleCandidates[0] || '') ||
    context.actors.find((actor) => roleCandidates.some((candidate) => labelText(actor.role).includes(candidate))) ||
    null
  );
}

function firstPlayer(context: NormalizedTacticalScene) {
  return (
    context.actors
      .filter((actor) => actor.kind !== 'ball')
      .slice()
      .sort((left, right) => left.x - right.x || left.y - right.y)[0] || null
  );
}

function firstBall(context: NormalizedTacticalScene) {
  return context.actors.find((actor) => actor.kind === 'ball') || null;
}

function firstGoalTarget(context: NormalizedTacticalScene) {
  return (
    context.zones.find((zone) => zone.kind === 'objective') ||
    context.zones.find((zone) => /goal|porter/i.test(zone.label)) ||
    null
  );
}

function actorTarget(actor: ReturnType<typeof firstPlayer> | ReturnType<typeof actorByRole> | null): TacticalTargetRef | undefined {
  return actor
    ? {
        kind: 'actor',
        actorId: actor.id,
        objectId: actor.objectId,
        label: actor.label,
      }
    : undefined;
}

function zoneTarget(zone: ReturnType<typeof firstGoalTarget> | null): TacticalTargetRef | undefined {
  return zone
    ? {
        kind: 'zone',
        zoneId: zone.id,
        objectId: zone.objectId,
        label: zone.label,
      }
    : undefined;
}

function pointTarget(point: { x: number; y: number }, label = 'Destino'): TacticalTargetRef {
  return {
    kind: 'zone',
    zoneId: `${Math.round(point.x)}-${Math.round(point.y)}`,
    label,
  };
}

function makeCondition(
  kind: TacticalCondition['kind'],
  expression: string,
  confidence: number,
  target?: TacticalTargetRef,
  subjectId?: string
): TacticalCondition {
  return { kind, expression, confidence, target, subjectId };
}

function makeResult(kind: TacticalResult['kind'], overrides: Partial<TacticalResult> = {}): TacticalResult {
  return { kind, ...overrides };
}

function makeStatement(
  id: string,
  verb: TacticalStatement['verb'],
  subjectId: string,
  result: TacticalResult,
  options: {
    target?: TacticalTargetRef;
    conditions?: TacticalCondition[];
    priority?: number;
    confidence?: number;
    phaseId?: string;
    parallelGroupId?: string;
    originObjectIds?: string[];
    duration?: number;
  } = {}
): TacticalStatement {
  return {
    id,
    verb,
    subjectId,
    target: options.target,
    conditions: options.conditions || [],
    result,
    priority: options.priority ?? 50,
    confidence: options.confidence ?? 0.9,
    duration: options.duration,
    phaseId: options.phaseId,
    parallelGroupId: options.parallelGroupId,
    originObjectIds: options.originObjectIds || [],
  };
}

function buildBaseBuildUp(context: NormalizedTacticalScene): ScenarioBuildResult {
  const goalkeeper = actorByRole(context, ['portero', 'goalkeeper']);
  const centerBackRight =
    actorByRole(context, ['central derecho', 'rcb']) ||
    context.actors.filter((actor) => actor.kind === 'player').sort((left, right) => left.x - right.x)[1] ||
    null;
  const centerBackLeft =
    actorByRole(context, ['central izquierdo', 'lcb']) ||
    context.actors.filter((actor) => actor.kind === 'player').sort((left, right) => left.x - right.x)[2] ||
    null;
  const midfielder = actorByRole(context, ['mediocentro', 'mcd']) || null;
  const rightBack = actorByRole(context, ['lateral derecho', 'rb']) || null;
  const ball = firstBall(context);
  const targetZone = firstGoalTarget(context);
  const firstArrow = context.arrows.find((arrow) => arrow.kind === 'pass') || context.arrows[0] || null;
  const secondArrow = context.arrows.find((arrow, index) => arrow.kind === 'pass' && index > 0) || null;
  const runArrow = context.arrows.find((arrow) => arrow.kind === 'run') || null;

  const buildUp = makeStatement(
    'stmt-build-up',
    'BUILD_UP',
    goalkeeper?.id || ball?.id || context.actors[0]?.id || 'scene',
    makeResult('START_PHASE'),
    {
      phaseId: 'phase-build-up',
      priority: 10,
      confidence: 1,
      originObjectIds: [goalkeeper?.objectId || ball?.objectId || context.actors[0]?.objectId || 'scene'].filter(Boolean),
    }
  );

  const firstPassTarget = actorTarget(centerBackRight) || pointTarget(firstArrow?.end || { x: 0, y: 0 }, 'Primer pase');
  const firstPass = makeStatement(
    'stmt-pass-1',
    'PASS',
    goalkeeper?.id || ball?.id || 'gk',
    makeResult('BALL_POSSESSION', { ballCarrierId: centerBackRight?.id || undefined }),
    {
      target: firstPassTarget,
      conditions: [makeCondition('WHEN', 'OpenPassingLane', 0.97, firstPassTarget, goalkeeper?.id)],
      priority: 100,
      confidence: 0.97,
      phaseId: 'phase-build-up',
      duration: 1.0,
      originObjectIds: [
        goalkeeper?.objectId || '',
        centerBackRight?.objectId || '',
        firstArrow?.objectId || '',
      ].filter(Boolean),
    }
  );

  const receive1 = makeStatement(
    'stmt-receive-1',
    'RECEIVE',
    centerBackRight?.id || 'rcb',
    makeResult('BALL_POSSESSION', { ballCarrierId: centerBackRight?.id || undefined }),
    {
      target: actorTarget(centerBackRight),
      conditions: [makeCondition('AFTER', 'stmt-pass-1', 1, actorTarget(centerBackRight), centerBackRight?.id)],
      priority: 99,
      confidence: 0.96,
      phaseId: 'phase-build-up',
      duration: 0.3,
      originObjectIds: [centerBackRight?.objectId || '', firstArrow?.objectId || ''].filter(Boolean),
    }
  );

  const carryTarget = secondArrow
    ? secondArrow.start
    : centerBackRight
      ? {
          x: centerBackRight.x + Math.max(48, centerBackRight.width * 1.2),
          y: centerBackRight.y + Math.min(40, centerBackRight.height * 0.3),
        }
      : { x: 0, y: 0 };
  const carry = makeStatement(
    'stmt-carry-1',
    'CARRY',
    centerBackRight?.id || 'rcb',
    makeResult('MOVE_ACTOR', { actorId: centerBackRight?.id || undefined, value: 'advance' }),
    {
      target: pointTarget(carryTarget, 'Conducción'),
      conditions: [makeCondition('AFTER', 'stmt-receive-1', 1, actorTarget(centerBackRight), centerBackRight?.id)],
      priority: 95,
      confidence: 0.91,
      phaseId: 'phase-progression',
      duration: 1.8,
      originObjectIds: [centerBackRight?.objectId || '', secondArrow?.objectId || ''].filter(Boolean),
    }
  );

  const supportTarget = zoneTarget(targetZone) || pointTarget(runArrow?.end || { x: 0, y: 0 }, 'Apoyo');
  const support = makeStatement(
    'stmt-support-1',
    'SUPPORT',
    rightBack?.id || midfielder?.id || 'support',
    makeResult('MOVE_ACTOR', { actorId: rightBack?.id || midfielder?.id || undefined, value: 'support' }),
    {
      target: supportTarget,
      conditions: [makeCondition('WHEN', 'BallOnRightHalfSpace', 0.9, supportTarget, rightBack?.id)],
      priority: 70,
      confidence: 0.88,
      phaseId: 'phase-build-up',
      parallelGroupId: 'support-lane',
      duration: 1.2,
      originObjectIds: [rightBack?.objectId || '', runArrow?.objectId || ''].filter(Boolean),
    }
  );

  const hold = makeStatement(
    'stmt-hold-1',
    'HOLD',
    midfielder?.id || 'mcd',
    makeResult('MOVE_ACTOR', { actorId: midfielder?.id || undefined, value: 'open-body' }),
    {
      target: actorTarget(midfielder),
      conditions: [makeCondition('WHEN', 'BallInFirstLine', 0.88, actorTarget(midfielder), midfielder?.id)],
      priority: 65,
      confidence: 0.87,
      phaseId: 'phase-build-up',
      parallelGroupId: 'support-lane',
      duration: 0.8,
      originObjectIds: [midfielder?.objectId || ''].filter(Boolean),
    }
  );

  const secondPassTarget = actorTarget(midfielder) || pointTarget(secondArrow?.end || { x: 0, y: 0 }, 'Segundo pase');
  const secondPass = makeStatement(
    'stmt-pass-2',
    'PASS',
    centerBackRight?.id || 'rcb',
    makeResult('BALL_POSSESSION', { ballCarrierId: midfielder?.id || undefined }),
    {
      target: secondPassTarget,
      conditions: [makeCondition('AFTER', 'stmt-carry-1', 1, secondPassTarget, centerBackRight?.id)],
      priority: 98,
      confidence: 0.95,
      phaseId: 'phase-progression',
      duration: 1.1,
      originObjectIds: [
        centerBackRight?.objectId || '',
        midfielder?.objectId || '',
        secondArrow?.objectId || '',
      ].filter(Boolean),
    }
  );

  const receive2 = makeStatement(
    'stmt-receive-2',
    'RECEIVE',
    midfielder?.id || 'mcd',
    makeResult('BALL_POSSESSION', { ballCarrierId: midfielder?.id || undefined }),
    {
      target: actorTarget(midfielder),
      conditions: [makeCondition('AFTER', 'stmt-pass-2', 1, actorTarget(midfielder), midfielder?.id)],
      priority: 97,
      confidence: 0.96,
      phaseId: 'phase-progression',
      duration: 0.3,
      originObjectIds: [midfielder?.objectId || '', secondArrow?.objectId || ''].filter(Boolean),
    }
  );

  const progression = makeStatement(
    'stmt-progression',
    'PROGRESSION',
    midfielder?.id || 'mcd',
    makeResult('END_PHASE'),
    {
      target: supportTarget,
      conditions: [makeCondition('AFTER', 'stmt-receive-2', 1, actorTarget(midfielder), midfielder?.id)],
      priority: 20,
      confidence: 0.9,
      phaseId: 'phase-progression',
      duration: 0,
      originObjectIds: [midfielder?.objectId || '', targetZone?.objectId || ''].filter(Boolean),
    }
  );

  const phases: TacticalPhase[] = [
    {
      id: 'phase-build-up',
      kind: 'BUILD_UP',
      label: 'Construcción',
      startTime: 0,
      endTime: 3,
      statementIds: ['stmt-build-up', 'stmt-pass-1', 'stmt-receive-1', 'stmt-support-1', 'stmt-hold-1'],
      objectiveId: targetZone?.id,
      confidence: 0.98,
    },
    {
      id: 'phase-progression',
      kind: 'PROGRESSION',
      label: 'Progresión',
      startTime: 3,
      endTime: 10,
      statementIds: ['stmt-carry-1', 'stmt-pass-2', 'stmt-receive-2', 'stmt-progression'],
      objectiveId: targetZone?.id,
      confidence: 0.95,
    },
  ];

  const objectives: TacticalObjective[] = phases.map((phase) => ({
    id: `${phase.id}-objective`,
    label: phase.label,
    kind: phase.kind,
    targetZoneId: phase.objectiveId,
    confidence: phase.confidence,
  }));

  const dependencies: TacticalDependency[] = [
    { id: 'dep-pass-1-receive-1', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-receive-1', relation: 'after' },
    { id: 'dep-receive-1-carry-1', fromStatementId: 'stmt-receive-1', toStatementId: 'stmt-carry-1', relation: 'after' },
    { id: 'dep-carry-1-pass-2', fromStatementId: 'stmt-carry-1', toStatementId: 'stmt-pass-2', relation: 'after' },
    { id: 'dep-pass-2-receive-2', fromStatementId: 'stmt-pass-2', toStatementId: 'stmt-receive-2', relation: 'after' },
    { id: 'dep-receive-2-progression', fromStatementId: 'stmt-receive-2', toStatementId: 'stmt-progression', relation: 'after' },
    { id: 'dep-support-parallel', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-support-1', relation: 'parallel' },
    { id: 'dep-hold-parallel', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-hold-1', relation: 'parallel' },
  ];

  return {
    statements: [buildUp, firstPass, receive1, carry, support, hold, secondPass, receive2, progression],
    phases,
    objectives,
    dependencies,
    possession: {
      state: 'controlled',
      carrierId: goalkeeper?.id || context.ballId || undefined,
      sourceStatementId: 'stmt-build-up',
      targetStatementId: 'stmt-pass-1',
      releaseTime: 0,
      receiveTime: 0.8,
    },
    validationIssues: [],
    confidence: 0.96,
  };
}

function buildRondo(context: NormalizedTacticalScene): ScenarioBuildResult {
  const players = context.actors.filter((actor) => actor.kind === 'player').slice().sort((left, right) => left.x - right.x);
  const ball = firstBall(context);
  const defender = context.actors.find((actor) => actor.team === 'away' || /defend|pres/i.test(actor.label) || /defend|pres/i.test(actor.role)) || null;
  const outerA = players[0] || null;
  const outerB = players[1] || null;
  const outerC = players[2] || null;
  const outerD = players[3] || null;
  const carrier = outerA || firstPlayer(context) || ball;
  const statements: TacticalStatement[] = [];
  const outerTargetA = actorTarget(outerB) || pointTarget({ x: (outerA?.x || 0) + 120, y: outerA ? outerA.y : 0 }, 'Salida');
  const outerTargetB = actorTarget(outerC) || pointTarget({ x: (outerB?.x || 0) + 90, y: outerB ? outerB.y : 0 }, 'Apoyo');
  const outerTargetC = actorTarget(outerD) || pointTarget({ x: (outerC?.x || 0) + 100, y: outerC ? outerC.y : 0 }, 'Salida');

  statements.push(
    makeStatement(
      'stmt-rondo-build',
      'BUILD_UP',
      carrier?.id || ball?.id || 'rondo',
      makeResult('START_PHASE'),
      { phaseId: 'phase-rondo', confidence: 1, priority: 10, duration: 0, originObjectIds: [carrier?.objectId || ball?.objectId || 'rondo'].filter(Boolean) }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-pass-1',
      'PASS',
      carrier?.id || 'rondo-a',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerB?.id || undefined }),
      {
        target: outerTargetA,
        conditions: [makeCondition('WHEN', 'OpenLane', 0.92, outerTargetA, carrier?.id)],
        phaseId: 'phase-rondo',
        duration: 0.85,
        confidence: 0.94,
        originObjectIds: [carrier?.objectId || '', outerB?.objectId || ''].filter(Boolean),
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-receive-1',
      'RECEIVE',
      outerB?.id || 'rondo-b',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerB?.id || undefined }),
      {
        target: actorTarget(outerB),
        conditions: [makeCondition('AFTER', 'stmt-rondo-pass-1', 1, actorTarget(outerB), outerB?.id)],
        phaseId: 'phase-rondo',
        duration: 0.25,
        confidence: 0.95,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-press-1',
      'PRESS',
      defender?.id || outerD?.id || 'defender',
      makeResult('MOVE_ACTOR', { actorId: defender?.id || outerD?.id || undefined, value: 'press' }),
      {
        target: actorTarget(outerB) || pointTarget({ x: (outerB?.x || 0) - 20, y: outerB ? outerB.y : 0 }, 'Presión'),
        conditions: [makeCondition('WHEN', 'BallInRondo', 0.85, actorTarget(outerB) || undefined, defender?.id)],
        phaseId: 'phase-rondo',
        parallelGroupId: 'rondo-pressure',
        duration: 1.2,
        confidence: 0.88,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-pass-2',
      'PASS',
      outerB?.id || 'rondo-b',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerC?.id || undefined }),
      {
        target: outerTargetB,
        conditions: [makeCondition('AFTER', 'stmt-rondo-receive-1', 1, actorTarget(outerB), outerB?.id)],
        phaseId: 'phase-rondo',
        duration: 0.85,
        confidence: 0.94,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-receive-2',
      'RECEIVE',
      outerC?.id || 'rondo-c',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerC?.id || undefined }),
      {
        target: actorTarget(outerC),
        conditions: [makeCondition('AFTER', 'stmt-rondo-pass-2', 1, actorTarget(outerC), outerC?.id)],
        phaseId: 'phase-rondo',
        duration: 0.25,
        confidence: 0.95,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-pass-3',
      'PASS',
      outerC?.id || 'rondo-c',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerA?.id || undefined }),
      {
        target: outerTargetC,
        conditions: [makeCondition('AFTER', 'stmt-rondo-receive-2', 1, actorTarget(outerC), outerC?.id)],
        phaseId: 'phase-rondo',
        duration: 0.9,
        confidence: 0.9,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-receive-3',
      'RECEIVE',
      outerA?.id || 'rondo-a',
      makeResult('BALL_POSSESSION', { ballCarrierId: outerA?.id || undefined }),
      {
        target: actorTarget(outerA),
        conditions: [makeCondition('AFTER', 'stmt-rondo-pass-3', 1, actorTarget(outerA), outerA?.id)],
        phaseId: 'phase-rondo',
        duration: 0.25,
        confidence: 0.95,
      }
    )
  );
  statements.push(
    makeStatement(
      'stmt-rondo-sequence',
      'SEQUENCE',
      outerA?.id || 'rondo-a',
      makeResult('END_PHASE'),
      {
        phaseId: 'phase-rondo',
        conditions: [makeCondition('AFTER', 'stmt-rondo-receive-3', 1, actorTarget(outerA), outerA?.id)],
        duration: 0,
        confidence: 0.92,
      }
    )
  );

  return {
    statements,
    phases: [
      {
        id: 'phase-rondo',
        kind: 'BUILD_UP',
        label: 'Rondo',
        startTime: 0,
        endTime: 8,
        statementIds: statements.map((statement) => statement.id),
        objectiveId: undefined,
        confidence: 0.92,
      },
    ],
    objectives: [],
    dependencies: [
      { id: 'dep-rondo-1', fromStatementId: 'stmt-rondo-pass-1', toStatementId: 'stmt-rondo-receive-1', relation: 'after' },
      { id: 'dep-rondo-2', fromStatementId: 'stmt-rondo-receive-1', toStatementId: 'stmt-rondo-pass-2', relation: 'after' },
      { id: 'dep-rondo-3', fromStatementId: 'stmt-rondo-pass-2', toStatementId: 'stmt-rondo-receive-2', relation: 'after' },
      { id: 'dep-rondo-4', fromStatementId: 'stmt-rondo-receive-2', toStatementId: 'stmt-rondo-pass-3', relation: 'after' },
      { id: 'dep-rondo-press', fromStatementId: 'stmt-rondo-pass-1', toStatementId: 'stmt-rondo-press-1', relation: 'parallel' },
    ],
    possession: {
      state: 'controlled',
      carrierId: outerA?.id || carrier?.id || context.ballId || undefined,
      sourceStatementId: 'stmt-rondo-build',
      targetStatementId: 'stmt-rondo-receive-3',
      releaseTime: 0,
      receiveTime: 2.7,
    },
    validationIssues: [],
    confidence: 0.93,
  };
}

function buildWallPass(context: NormalizedTacticalScene): ScenarioBuildResult {
  const players = context.actors.filter((actor) => actor.kind === 'player').slice().sort((left, right) => left.x - right.x);
  const a = findActorByLabelLike(context, ['a']) || players[0] || null;
  const b = findActorByLabelLike(context, ['b']) || players[1] || null;
  const ball = firstBall(context);
  const firstTarget = actorTarget(b) || pointTarget({ x: (a?.x || 0) + 120, y: a ? a.y : 0 }, 'Pared');
  const returnTarget = actorTarget(a) || pointTarget({ x: (b?.x || 0) - 120, y: b ? b.y : 0 }, 'Devolución');

  const statements = [
    makeStatement('stmt-wall-sequence', 'SEQUENCE', a?.id || 'wall-a', makeResult('START_PHASE'), {
      phaseId: 'phase-wall',
      duration: 0,
      confidence: 0.9,
    }),
    makeStatement('stmt-wall-pass-1', 'PASS', a?.id || 'wall-a', makeResult('BALL_POSSESSION', { ballCarrierId: b?.id || undefined }), {
      target: firstTarget,
      conditions: [makeCondition('WHEN', 'BallAtFoot', 0.9, firstTarget, a?.id)],
      phaseId: 'phase-wall',
      duration: 0.8,
      confidence: 0.95,
    }),
    makeStatement('stmt-wall-support', 'SUPPORT', a?.id || 'wall-a', makeResult('MOVE_ACTOR', { actorId: a?.id || undefined, value: 'run' }), {
      target: pointTarget({ x: (a?.x || 0) + 88, y: (a?.y || 0) - 18 }, 'Apoyo'),
      conditions: [makeCondition('PARALLEL_WITH', 'stmt-wall-pass-1', 0.9, actorTarget(b), a?.id)],
      phaseId: 'phase-wall',
      parallelGroupId: 'wall-combo',
      duration: 1.2,
      confidence: 0.9,
    }),
    makeStatement('stmt-wall-receive-1', 'RECEIVE', b?.id || 'wall-b', makeResult('BALL_POSSESSION', { ballCarrierId: b?.id || undefined }), {
      target: actorTarget(b),
      conditions: [makeCondition('AFTER', 'stmt-wall-pass-1', 1, actorTarget(b), b?.id)],
      phaseId: 'phase-wall',
      duration: 0.25,
      confidence: 0.95,
    }),
    makeStatement('stmt-wall-return-pass', 'RETURN_PASS', b?.id || 'wall-b', makeResult('BALL_POSSESSION', { ballCarrierId: a?.id || undefined }), {
      target: returnTarget,
      conditions: [makeCondition('AFTER', 'stmt-wall-support', 1, actorTarget(a), b?.id)],
      phaseId: 'phase-wall',
      duration: 0.75,
      confidence: 0.94,
    }),
    makeStatement('stmt-wall-receive-2', 'RECEIVE', a?.id || 'wall-a', makeResult('BALL_POSSESSION', { ballCarrierId: a?.id || undefined }), {
      target: actorTarget(a),
      conditions: [makeCondition('AFTER', 'stmt-wall-return-pass', 1, actorTarget(a), a?.id)],
      phaseId: 'phase-wall',
      duration: 0.25,
      confidence: 0.95,
    }),
  ];

  return {
    statements,
    phases: [
      {
        id: 'phase-wall',
        kind: 'BUILD_UP',
        label: 'Pared',
        startTime: 0,
        endTime: 5,
        statementIds: statements.map((statement) => statement.id),
        confidence: 0.94,
      },
    ],
    objectives: [],
    dependencies: [
      { id: 'dep-wall-1', fromStatementId: 'stmt-wall-pass-1', toStatementId: 'stmt-wall-receive-1', relation: 'after' },
      { id: 'dep-wall-2', fromStatementId: 'stmt-wall-receive-1', toStatementId: 'stmt-wall-return-pass', relation: 'after' },
      { id: 'dep-wall-3', fromStatementId: 'stmt-wall-return-pass', toStatementId: 'stmt-wall-receive-2', relation: 'after' },
      { id: 'dep-wall-support', fromStatementId: 'stmt-wall-pass-1', toStatementId: 'stmt-wall-support', relation: 'parallel' },
    ],
    possession: {
      state: 'controlled',
      carrierId: a?.id || ball?.id || undefined,
      sourceStatementId: 'stmt-wall-sequence',
      targetStatementId: 'stmt-wall-receive-2',
      releaseTime: 0,
      receiveTime: 1.8,
    },
    validationIssues: [],
    confidence: 0.94,
  };
}

function buildFinishing(context: NormalizedTacticalScene): ScenarioBuildResult {
  const midfielder = actorByRole(context, ['mediocentro', 'mcd', 'medio']) || firstPlayer(context);
  const attacker =
    actorByRole(context, ['delantero', 'attacker', 'forward']) ||
    context.actors.filter((actor) => actor.kind !== 'ball').slice().sort((left, right) => right.x - left.x)[0] ||
    null;
  const ball = firstBall(context);
  const goalZone = firstGoalTarget(context);
  const passTarget = actorTarget(attacker) || zoneTarget(goalZone) || pointTarget({ x: (attacker?.x || 0) + 100, y: attacker ? attacker.y : 0 }, 'Atacante');
  const goalTarget = zoneTarget(goalZone) || pointTarget({ x: 980, y: attacker ? attacker.y : 0 }, 'Gol');

  const statements = [
    makeStatement('stmt-finish-sequence', 'SEQUENCE', midfielder?.id || 'finish', makeResult('START_PHASE'), {
      phaseId: 'phase-finish',
      duration: 0,
      confidence: 0.92,
    }),
    makeStatement('stmt-finish-pass', 'PASS', midfielder?.id || 'finish-mid', makeResult('BALL_POSSESSION', { ballCarrierId: attacker?.id || undefined }), {
      target: passTarget,
      conditions: [makeCondition('WHEN', 'OpenLaneToAttacker', 0.93, passTarget, midfielder?.id)],
      phaseId: 'phase-finish',
      duration: 0.95,
      confidence: 0.95,
    }),
    makeStatement('stmt-finish-receive', 'RECEIVE', attacker?.id || 'finish-attacker', makeResult('BALL_POSSESSION', { ballCarrierId: attacker?.id || undefined }), {
      target: actorTarget(attacker),
      conditions: [makeCondition('AFTER', 'stmt-finish-pass', 1, actorTarget(attacker), attacker?.id)],
      phaseId: 'phase-finish',
      duration: 0.25,
      confidence: 0.96,
    }),
    makeStatement('stmt-finish-shoot', 'SHOOT', attacker?.id || 'finish-attacker', makeResult('BALL_POSSESSION', { ballCarrierId: undefined, value: 'shot' }), {
      target: goalTarget,
      conditions: [makeCondition('AFTER', 'stmt-finish-receive', 1, actorTarget(attacker), attacker?.id)],
      phaseId: 'phase-finish',
      duration: 1.1,
      confidence: 0.98,
    }),
    makeStatement('stmt-finish-hold', 'HOLD', midfielder?.id || 'finish-mid', makeResult('MOVE_ACTOR', { actorId: midfielder?.id || undefined, value: 'support' }), {
      target: actorTarget(midfielder),
      conditions: [makeCondition('WHILE', 'BallInAttackZone', 0.82, goalTarget, midfielder?.id)],
      phaseId: 'phase-finish',
      parallelGroupId: 'finish-support',
      duration: 1.6,
      confidence: 0.84,
    }),
  ];

  return {
    statements,
    phases: [
      {
        id: 'phase-finish',
        kind: 'PROGRESSION',
        label: 'Finalización',
        startTime: 0,
        endTime: 6,
        statementIds: statements.map((statement) => statement.id),
        objectiveId: goalZone?.id,
        confidence: 0.97,
      },
    ],
    objectives: [
      {
        id: 'phase-finish-objective',
        label: 'Finalización',
        kind: 'PROGRESSION',
        targetZoneId: goalZone?.id,
        confidence: 0.97,
      },
    ],
    dependencies: [
      { id: 'dep-finish-pass', fromStatementId: 'stmt-finish-pass', toStatementId: 'stmt-finish-receive', relation: 'after' },
      { id: 'dep-finish-receive', fromStatementId: 'stmt-finish-receive', toStatementId: 'stmt-finish-shoot', relation: 'after' },
      { id: 'dep-finish-hold', fromStatementId: 'stmt-finish-pass', toStatementId: 'stmt-finish-hold', relation: 'parallel' },
    ],
    possession: {
      state: 'free',
      carrierId: undefined,
      sourceStatementId: 'stmt-finish-pass',
      targetStatementId: 'stmt-finish-shoot',
      releaseTime: 0,
      receiveTime: 1.2,
    },
    validationIssues: [],
    confidence: 0.97,
  };
}

function buildTechnicalCircuit(context: NormalizedTacticalScene): ScenarioBuildResult {
  const carrier = actorByRole(context, ['portero', 'goalkeeper', 'jugador con balón']) || firstPlayer(context);
  const support = actorByRole(context, ['mediocentro', 'mcd', 'interior']) || context.actors.filter((actor) => actor.kind !== 'ball').slice().sort((left, right) => left.x - right.x)[1] || null;
  const runner = actorByRole(context, ['lateral', 'extremo']) || context.actors.filter((actor) => actor.kind !== 'ball').slice().sort((left, right) => left.x - right.x)[2] || null;
  const receiver = actorByRole(context, ['delantero', 'attacker']) || context.actors.filter((actor) => actor.kind !== 'ball').slice().sort((left, right) => right.x - left.x)[0] || null;
  const ball = firstBall(context);
  const zone = firstGoalTarget(context);

  const statements = [
    makeStatement('stmt-circuit-sequence', 'SEQUENCE', carrier?.id || 'circuit', makeResult('START_PHASE'), {
      phaseId: 'phase-circuit',
      duration: 0,
      confidence: 0.92,
    }),
    makeStatement('stmt-circuit-carry', 'CARRY', carrier?.id || 'circuit-carrier', makeResult('MOVE_ACTOR', { actorId: carrier?.id || undefined, value: 'dribble' }), {
      target: pointTarget({ x: (carrier?.x || 0) + 120, y: carrier ? carrier.y : 0 }, 'Conducción'),
      conditions: [makeCondition('WHEN', 'BallAtFeet', 0.92, actorTarget(carrier), carrier?.id)],
      phaseId: 'phase-circuit',
      duration: 1.8,
      confidence: 0.94,
    }),
    makeStatement('stmt-circuit-pass', 'PASS', carrier?.id || 'circuit-carrier', makeResult('BALL_POSSESSION', { ballCarrierId: support?.id || undefined }), {
      target: actorTarget(support) || pointTarget({ x: (support?.x || 0) + 40, y: support ? support.y : 0 }, 'Pase'),
      conditions: [makeCondition('AFTER', 'stmt-circuit-carry', 1, actorTarget(carrier), carrier?.id)],
      phaseId: 'phase-circuit',
      duration: 1.0,
      confidence: 0.95,
    }),
    makeStatement('stmt-circuit-run', 'RUN', runner?.id || 'circuit-runner', makeResult('MOVE_ACTOR', { actorId: runner?.id || undefined, value: 'run' }), {
      target: pointTarget({ x: (runner?.x || 0) + 120, y: (runner?.y || 0) + 40 }, 'Carrera'),
      conditions: [makeCondition('WHEN', 'BallInPlay', 0.88, actorTarget(runner), runner?.id)],
      phaseId: 'phase-circuit',
      parallelGroupId: 'circuit-movement',
      duration: 1.6,
      confidence: 0.9,
    }),
    makeStatement('stmt-circuit-receive', 'RECEIVE', support?.id || 'circuit-support', makeResult('BALL_POSSESSION', { ballCarrierId: support?.id || undefined }), {
      target: actorTarget(support),
      conditions: [makeCondition('AFTER', 'stmt-circuit-pass', 1, actorTarget(support), support?.id)],
      phaseId: 'phase-circuit',
      duration: 0.3,
      confidence: 0.95,
    }),
    makeStatement('stmt-circuit-second-pass', 'PASS', support?.id || 'circuit-support', makeResult('BALL_POSSESSION', { ballCarrierId: receiver?.id || undefined }), {
      target: actorTarget(receiver) || zoneTarget(zone) || pointTarget({ x: (receiver?.x || 0) + 150, y: receiver ? receiver.y : 0 }, 'Segundo pase'),
      conditions: [makeCondition('AFTER', 'stmt-circuit-receive', 1, actorTarget(support), support?.id)],
      phaseId: 'phase-circuit',
      duration: 0.9,
      confidence: 0.95,
    }),
    makeStatement('stmt-circuit-objective', 'OCCUPY_SPACE', receiver?.id || 'circuit-receiver', makeResult('OCCUPY_ZONE', { zoneId: zone?.id, value: 'target' }), {
      target: zoneTarget(zone) || pointTarget({ x: 860, y: 260 }, 'Zona objetivo'),
      conditions: [makeCondition('AFTER', 'stmt-circuit-second-pass', 1, zoneTarget(zone), receiver?.id)],
      phaseId: 'phase-circuit',
      parallelGroupId: 'circuit-movement',
      duration: 1.4,
      confidence: 0.89,
    }),
  ];

  return {
    statements,
    phases: [
      {
        id: 'phase-circuit',
        kind: 'BUILD_UP',
        label: 'Circuito técnico',
        startTime: 0,
        endTime: 10,
        statementIds: statements.map((statement) => statement.id),
        objectiveId: zone?.id,
        confidence: 0.95,
      },
    ],
    objectives: [
      {
        id: 'phase-circuit-objective',
        label: 'Zona objetivo',
        kind: 'BUILD_UP',
        targetZoneId: zone?.id,
        confidence: 0.95,
      },
    ],
    dependencies: [
      { id: 'dep-circuit-carry-pass', fromStatementId: 'stmt-circuit-carry', toStatementId: 'stmt-circuit-pass', relation: 'after' },
      { id: 'dep-circuit-pass-receive', fromStatementId: 'stmt-circuit-pass', toStatementId: 'stmt-circuit-receive', relation: 'after' },
      { id: 'dep-circuit-receive-second', fromStatementId: 'stmt-circuit-receive', toStatementId: 'stmt-circuit-second-pass', relation: 'after' },
      { id: 'dep-circuit-second-objective', fromStatementId: 'stmt-circuit-second-pass', toStatementId: 'stmt-circuit-objective', relation: 'after' },
      { id: 'dep-circuit-run', fromStatementId: 'stmt-circuit-carry', toStatementId: 'stmt-circuit-run', relation: 'parallel' },
    ],
    possession: {
      state: 'controlled',
      carrierId: receiver?.id || support?.id || carrier?.id || undefined,
      sourceStatementId: 'stmt-circuit-carry',
      targetStatementId: 'stmt-circuit-objective',
      releaseTime: 0,
      receiveTime: 2.8,
    },
    validationIssues: [],
    confidence: 0.95,
  };
}

function detectScenario(context: NormalizedTacticalScene): TacticalScenarioKind {
  const title = sceneTitle(context);
  if (title.includes('pared') || title.includes('wall')) return 'wall_pass';
  if (title.includes('fin')) return 'finishing';
  if (title.includes('rondo')) return 'rondo';
  if (title.includes('circuit') || title.includes('tecnico') || title.includes('técnico')) return 'technical_circuit';
  if (hasText(context, ['goal', 'porteria', 'mini-goal', 'miniporteria'])) return 'finishing';
  if (hasText(context, ['pared', 'wall'])) return 'wall_pass';
  if (hasText(context, ['rondo'])) return 'rondo';
  if (hasText(context, ['circuit', 'drill'])) return 'technical_circuit';
  if (countByRole(context, 'goalkeeper') && countByRole(context, 'player') >= 4) return 'build_up';
  if (context.actors.filter((actor) => actor.team === 'away').length >= 1 && context.actors.length <= 8) return 'rondo';
  return 'build_up';
}

export function buildTacticalLanguageDocument(context: NormalizedTacticalScene): TacticalLanguageDocument {
  const scenario = detectScenario(context);
  const buildResult =
    scenario === 'rondo'
      ? buildRondo(context)
      : scenario === 'wall_pass'
        ? buildWallPass(context)
        : scenario === 'finishing'
          ? buildFinishing(context)
          : scenario === 'technical_circuit'
            ? buildTechnicalCircuit(context)
            : buildBaseBuildUp(context);

  return {
    schemaVersion: 1,
    language: 'tactical-language',
    documentId: context.scene.documentId,
    metadata: {
      title: context.scene.metadata.title || 'Salida de balón',
      sport: 'football',
      createdAt: context.scene.metadata.createdAt,
      updatedAt: context.scene.metadata.updatedAt,
    },
    actors: context.actors,
    zones: context.zones,
    arrows: context.arrows,
    statements: buildResult.statements,
    phases: buildResult.phases,
    objectives: buildResult.objectives,
    dependencies: buildResult.dependencies,
    possession: buildResult.possession,
    confidence: buildResult.confidence,
    validationIssues: buildResult.validationIssues,
  };
}

export type { TacticalScenarioKind };
