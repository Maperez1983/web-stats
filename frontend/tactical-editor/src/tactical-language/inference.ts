import type { TacticalScene } from '../editor/core/sceneSchema';
import type {
  TacticalActorRef,
  TacticalArrowRef,
  TacticalCondition,
  TacticalLanguageDocument,
  TacticalPhase,
  TacticalStatement,
  TacticalTargetRef,
  TacticalZoneRef,
} from './types';
import {
  arrowVector,
  findActorByLabelLike,
  findActorByRole,
  normalizeTacticalScene,
  type NormalizedTacticalScene,
} from './normalizer';

function arrowMatches(arrow: TacticalArrowRef, kinds: TacticalArrowRef['kind'][]): boolean {
  return kinds.includes(arrow.kind);
}

function arrowRank(arrow: TacticalArrowRef) {
  const vector = arrowVector(arrow);
  const absDx = Math.abs(vector.dx);
  const absDy = Math.abs(vector.dy);
  return absDx + absDy;
}

function nearestArrow(
  arrows: TacticalArrowRef[],
  actor: TacticalActorRef | null,
  kinds: TacticalArrowRef['kind'][]
): TacticalArrowRef | null {
  if (!actor) {
    return arrows.find((arrow) => kinds.includes(arrow.kind)) || null;
  }
  const actorPoint = {
    x: actor.x + actor.width / 2,
    y: actor.y + actor.height / 2,
  };
  return (
    arrows
      .filter((arrow) => kinds.includes(arrow.kind))
      .slice()
      .sort((left, right) => {
        const leftDistance = Math.hypot(left.start.x - actorPoint.x, left.start.y - actorPoint.y);
        const rightDistance = Math.hypot(right.start.x - actorPoint.x, right.start.y - actorPoint.y);
        if (Math.abs(leftDistance - rightDistance) > 1) {
          return leftDistance - rightDistance;
        }
        return arrowRank(right) - arrowRank(left);
      })[0] || null
  );
}

function pointToTarget(point: { x: number; y: number }): TacticalTargetRef {
  return {
    kind: 'zone',
    label: 'punto de llegada',
    zoneId: `${Math.round(point.x)}-${Math.round(point.y)}`,
  };
}

function actorTarget(actor: TacticalActorRef | null): TacticalTargetRef | undefined {
  return actor
    ? {
        kind: 'actor',
        actorId: actor.id,
        objectId: actor.objectId,
        label: actor.label,
      }
    : undefined;
}

function zoneTarget(zone: TacticalZoneRef | null): TacticalTargetRef | undefined {
  return zone
    ? {
        kind: 'zone',
        zoneId: zone.id,
        objectId: zone.objectId,
        label: zone.label,
      }
    : undefined;
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

function makeStatement(
  id: string,
  verb: TacticalStatement['verb'],
  subjectId: string,
  result: TacticalStatement['result'],
  options: {
    target?: TacticalTargetRef;
    conditions?: TacticalCondition[];
    priority?: number;
    confidence?: number;
    phaseId?: string;
    parallelGroupId?: string;
    originObjectIds?: string[];
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
    phaseId: options.phaseId,
    parallelGroupId: options.parallelGroupId,
    originObjectIds: options.originObjectIds || [],
  };
}

function actorByRole(context: NormalizedTacticalScene, roleCandidates: string[]): TacticalActorRef | null {
  const byLabel = findActorByLabelLike(context, roleCandidates);
  if (byLabel) {
    return byLabel;
  }
  return (
    context.actors.find((actor) =>
      roleCandidates.some((candidate) => actor.role.toLowerCase().includes(candidate))
    ) || null
  );
}

function buildStatements(context: NormalizedTacticalScene) {
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
  const ball = context.actors.find((actor) => actor.kind === 'ball') || null;
  const targetZone =
    context.zones.find((zone) => /objetivo|target/i.test(zone.label)) || context.zones[0] || null;

  const passArrows = context.arrows.filter((arrow) => arrowMatches(arrow, ['pass']));
  const runArrows = context.arrows.filter((arrow) => arrowMatches(arrow, ['run']));
  const trajectoryArrows = context.arrows.filter((arrow) => arrowMatches(arrow, ['trajectory', 'line']));

  const firstPassArrow =
    nearestArrow(passArrows, goalkeeper, ['pass']) ||
    nearestArrow(trajectoryArrows, goalkeeper, ['trajectory', 'line']);
  const secondPassArrow =
    passArrows.find((arrow) => arrow.id !== firstPassArrow?.id) ||
    trajectoryArrows.find((arrow) => arrow.id !== firstPassArrow?.id) ||
    firstPassArrow;
  const supportArrow =
    nearestArrow(runArrows, rightBack, ['run']) ||
    nearestArrow(trajectoryArrows, rightBack, ['trajectory']) ||
    runArrows.find((arrow) => arrow.id !== secondPassArrow?.id) ||
    null;

  const buildUp = makeStatement(
    'stmt-build-up',
    'BUILD_UP',
    goalkeeper?.id || ball?.id || context.actors[0]?.id || 'scene',
    { kind: 'START_PHASE' },
    {
      phaseId: 'phase-build-up',
      priority: 10,
      confidence: 1,
      originObjectIds: [goalkeeper?.objectId || ball?.objectId || context.actors[0]?.objectId || 'scene'],
    }
  );

  const firstPassTarget = actorTarget(centerBackRight) || pointToTarget(firstPassArrow?.end || { x: 0, y: 0 });
  const firstPass = makeStatement(
    'stmt-pass-1',
    'PASS',
    goalkeeper?.id || ball?.id || 'gk',
    { kind: 'BALL_POSSESSION', ballCarrierId: centerBackRight?.id || undefined },
    {
      target: firstPassTarget,
      conditions: [makeCondition('WHEN', 'OpenPassingLane', 0.97, firstPassTarget, goalkeeper?.id)],
      priority: 100,
      confidence: 0.97,
      phaseId: 'phase-build-up',
      originObjectIds: [
        goalkeeper?.objectId || '',
        centerBackRight?.objectId || '',
        firstPassArrow?.objectId || '',
      ].filter(Boolean),
    }
  );

  const receive1 = makeStatement(
    'stmt-receive-1',
    'RECEIVE',
    centerBackRight?.id || 'rcb',
    { kind: 'BALL_POSSESSION', ballCarrierId: centerBackRight?.id || undefined },
    {
      target: actorTarget(centerBackRight),
      conditions: [makeCondition('AFTER', 'stmt-pass-1', 1, actorTarget(centerBackRight), centerBackRight?.id)],
      priority: 99,
      confidence: 0.96,
      phaseId: 'phase-build-up',
      originObjectIds: [centerBackRight?.objectId || '', firstPassArrow?.objectId || ''].filter(Boolean),
    }
  );

  const carryEnd = secondPassArrow ? secondPassArrow.start : centerBackRight
    ? {
        x: centerBackRight.x + Math.max(42, centerBackRight.width * 1.6),
        y: centerBackRight.y + Math.min(36, centerBackRight.height * 0.25),
      }
    : { x: 0, y: 0 };
  const carry = makeStatement(
    'stmt-carry-1',
    'CARRY',
    centerBackRight?.id || 'rcb',
    { kind: 'MOVE_ACTOR', actorId: centerBackRight?.id || undefined, value: 'advance' },
    {
      target: pointToTarget(carryEnd),
      conditions: [makeCondition('AFTER', 'stmt-receive-1', 1, actorTarget(centerBackRight), centerBackRight?.id)],
      priority: 95,
      confidence: 0.91,
      phaseId: 'phase-progression',
      originObjectIds: [centerBackRight?.objectId || '', secondPassArrow?.objectId || ''].filter(Boolean),
    }
  );

  const supportTarget = zoneTarget(targetZone) || pointToTarget(supportArrow?.end || { x: 0, y: 0 });
  const support = makeStatement(
    'stmt-support-1',
    'SUPPORT',
    rightBack?.id || midfielder?.id || 'support',
    { kind: 'MOVE_ACTOR', actorId: rightBack?.id || midfielder?.id || undefined, value: 'support' },
    {
      target: supportTarget,
      conditions: [makeCondition('WHEN', 'BallOnRightHalfSpace', 0.9, supportTarget, rightBack?.id)],
      priority: 70,
      confidence: 0.88,
      phaseId: 'phase-build-up',
      parallelGroupId: 'support-lane',
      originObjectIds: [rightBack?.objectId || '', supportArrow?.objectId || ''].filter(Boolean),
    }
  );

  const midfieldSupport = makeStatement(
    'stmt-hold-1',
    'HOLD',
    midfielder?.id || 'mcd',
    { kind: 'MOVE_ACTOR', actorId: midfielder?.id || undefined, value: 'open-body' },
    {
      target: actorTarget(midfielder),
      conditions: [makeCondition('WHEN', 'BallInFirstLine', 0.88, actorTarget(midfielder), midfielder?.id)],
      priority: 65,
      confidence: 0.87,
      phaseId: 'phase-build-up',
      parallelGroupId: 'support-lane',
      originObjectIds: [midfielder?.objectId || ''].filter(Boolean),
    }
  );

  const secondPassTarget = actorTarget(midfielder) || pointToTarget(secondPassArrow?.end || { x: 0, y: 0 });
  const secondPass = makeStatement(
    'stmt-pass-2',
    'PASS',
    centerBackRight?.id || 'rcb',
    { kind: 'BALL_POSSESSION', ballCarrierId: midfielder?.id || undefined },
    {
      target: secondPassTarget,
      conditions: [makeCondition('AFTER', 'stmt-carry-1', 1, secondPassTarget, centerBackRight?.id)],
      priority: 98,
      confidence: 0.95,
      phaseId: 'phase-progression',
      originObjectIds: [
        centerBackRight?.objectId || '',
        midfielder?.objectId || '',
        secondPassArrow?.objectId || '',
      ].filter(Boolean),
    }
  );

  const receive2 = makeStatement(
    'stmt-receive-2',
    'RECEIVE',
    midfielder?.id || 'mcd',
    { kind: 'BALL_POSSESSION', ballCarrierId: midfielder?.id || undefined },
    {
      target: actorTarget(midfielder),
      conditions: [makeCondition('AFTER', 'stmt-pass-2', 1, actorTarget(midfielder), midfielder?.id)],
      priority: 97,
      confidence: 0.96,
      phaseId: 'phase-progression',
      originObjectIds: [midfielder?.objectId || '', secondPassArrow?.objectId || ''].filter(Boolean),
    }
  );

  const progression = makeStatement(
    'stmt-progression',
    'PROGRESSION',
    midfielder?.id || 'mcd',
    { kind: 'END_PHASE' },
    {
      target: supportTarget,
      conditions: [makeCondition('AFTER', 'stmt-receive-2', 1, actorTarget(midfielder), midfielder?.id)],
      priority: 20,
      confidence: 0.9,
      phaseId: 'phase-progression',
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

  return {
    goalkeeper,
    centerBackRight,
    centerBackLeft,
    midfielder,
    rightBack,
    ball,
    targetZone,
    passArrows,
    runArrows,
    trajectoryArrows,
    statements: [buildUp, firstPass, receive1, carry, support, midfieldSupport, secondPass, receive2, progression],
    phases,
  };
}

export function inferTacticalLanguage(scene: TacticalScene): TacticalLanguageDocument {
  const context = normalizeTacticalScene(scene);
  const inference = buildStatements(context);
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
    statements: inference.statements,
    phases: inference.phases,
    objectives: inference.phases.map((phase) => ({
      id: `${phase.id}-objective`,
      label: phase.label,
      kind: phase.kind,
      targetZoneId: phase.objectiveId,
      confidence: phase.confidence,
    })),
    dependencies: [
      { id: 'dep-pass-1-receive-1', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-receive-1', relation: 'after' },
      { id: 'dep-receive-1-carry-1', fromStatementId: 'stmt-receive-1', toStatementId: 'stmt-carry-1', relation: 'after' },
      { id: 'dep-carry-1-pass-2', fromStatementId: 'stmt-carry-1', toStatementId: 'stmt-pass-2', relation: 'after' },
      { id: 'dep-pass-2-receive-2', fromStatementId: 'stmt-pass-2', toStatementId: 'stmt-receive-2', relation: 'after' },
      { id: 'dep-receive-2-progression', fromStatementId: 'stmt-receive-2', toStatementId: 'stmt-progression', relation: 'after' },
      { id: 'dep-support-parallel', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-support-1', relation: 'parallel' },
      { id: 'dep-hold-parallel', fromStatementId: 'stmt-pass-1', toStatementId: 'stmt-hold-1', relation: 'parallel' },
    ],
    possession: {
      state: 'controlled',
      carrierId: inference.goalkeeper?.id || context.ballId || undefined,
      sourceStatementId: 'stmt-build-up',
      targetStatementId: 'stmt-pass-1',
      releaseTime: 0,
      receiveTime: 0.8,
    },
    confidence: 0.96,
    validationIssues: [],
  };
}
