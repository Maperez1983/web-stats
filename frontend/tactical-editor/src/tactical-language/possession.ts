import type {
  BallPossessionState,
  ResolvedPlan,
  TacticalLanguageDocument,
  TacticalStatement,
} from './types';

export type PossessionStep = {
  statementId: string;
  state: BallPossessionState['state'];
  carrierId?: string;
  releaseTime?: number;
  receiveTime?: number;
};

export type PossessionResolution = {
  possession: BallPossessionState;
  steps: PossessionStep[];
};

function carrierForStatement(statement: TacticalStatement): string | undefined {
  if (statement.result.kind === 'BALL_POSSESSION' && statement.result.ballCarrierId) {
    return statement.result.ballCarrierId;
  }
  if (statement.result.kind === 'MOVE_ACTOR' && statement.result.actorId) {
    return statement.result.actorId;
  }
  return statement.target?.actorId;
}

export function resolvePossession(document: TacticalLanguageDocument, plan: ResolvedPlan): PossessionResolution {
  const statements = plan.executionOrder
    .map((statementId) => document.statements.find((statement) => statement.id === statementId))
    .filter((statement): statement is TacticalStatement => Boolean(statement));

  const steps: PossessionStep[] = [];
  let carrierId = document.possession.carrierId || document.actors.find((actor) => actor.kind === 'goalkeeper')?.id;
  let releaseTime = document.possession.releaseTime ?? 0;
  let receiveTime = document.possession.receiveTime ?? 0;

  statements.forEach((statement) => {
    if (statement.verb === 'PASS') {
      const nextCarrier = carrierForStatement(statement);
      if (nextCarrier) {
        steps.push({
          statementId: statement.id,
          state: 'in_flight',
          carrierId,
          releaseTime,
          receiveTime: releaseTime + 0.8,
        });
        carrierId = nextCarrier;
        releaseTime += 0.8;
        receiveTime = releaseTime + 0.15;
      }
    } else if (statement.verb === 'RECEIVE') {
      carrierId = carrierForStatement(statement) || carrierId;
      steps.push({
        statementId: statement.id,
        state: 'receiving',
        carrierId,
        releaseTime,
        receiveTime,
      });
    } else if (statement.verb === 'CARRY') {
      steps.push({
        statementId: statement.id,
        state: 'controlled',
        carrierId,
      });
    }
  });

  return {
    possession: {
      state: 'controlled',
      carrierId,
      sourceStatementId: statements[0]?.id,
      targetStatementId: statements[statements.length - 1]?.id,
      releaseTime: document.possession.releaseTime ?? 0,
      receiveTime,
    },
    steps,
  };
}
