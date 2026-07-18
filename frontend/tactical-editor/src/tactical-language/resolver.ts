import type {
  ExecutionBarrier,
  ExecutionConstraint,
  ExecutionEdge,
  ExecutionGroup,
  ExecutionNode,
  ExecutionWindow,
  ResolverContext,
  ResolverIssue,
  ResolverResult,
  ResolvedPlan,
  TacticalDependency,
  TacticalLanguageDocument,
  TacticalStatement,
} from './types';

function buildNode(statement: TacticalStatement): ExecutionNode {
  const isPhase = statement.verb === 'BUILD_UP' || statement.verb === 'PROGRESSION';
  const isBallEvent = statement.verb === 'PASS' || statement.verb === 'RECEIVE' || statement.verb === 'CARRY';
  const isSupport = statement.verb === 'RUN' || statement.verb === 'SUPPORT' || statement.verb === 'HOLD' || statement.verb === 'CREATE_SPACE' || statement.verb === 'OCCUPY_SPACE';
  return {
    id: `node-${statement.id}`,
    statementId: statement.id,
    kind: isPhase ? 'phase' : isBallEvent ? 'ball_event' : isSupport ? 'support' : 'action',
    actorId: statement.subjectId,
    targetId: statement.target?.actorId || statement.target?.objectId,
    zoneId: statement.target?.zoneId,
    phaseId: statement.phaseId,
    priority: statement.priority,
    confidence: statement.confidence,
    status: 'pending',
    produces: [statement.result.kind],
    requires: statement.conditions.map((condition) => condition.expression),
    blocks: [],
    trace: [],
  };
}

function relationToEdgeRelation(relation: TacticalDependency['relation']): ExecutionEdge['relation'] {
  return relation;
}

function topologicalOrder(nodes: ExecutionNode[], edges: ExecutionEdge[]): { order: string[]; blocked: boolean; issues: ResolverIssue[] } {
  const incoming = new Map<string, number>(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map<string, string[]>(nodes.map((node) => [node.id, []]));
  edges.forEach((edge) => {
    incoming.set(edge.toNodeId, (incoming.get(edge.toNodeId) || 0) + 1);
    outgoing.set(edge.fromNodeId, [...(outgoing.get(edge.fromNodeId) || []), edge.toNodeId]);
  });
  const queue = nodes
    .filter((node) => (incoming.get(node.id) || 0) === 0)
    .sort((left, right) => right.priority - left.priority);
  const order: string[] = [];
  const issues: ResolverIssue[] = [];

  while (queue.length) {
    const next = queue.shift()!;
    order.push(next.id);
    (outgoing.get(next.id) || []).forEach((targetId) => {
      incoming.set(targetId, Math.max(0, (incoming.get(targetId) || 0) - 1));
      if ((incoming.get(targetId) || 0) === 0) {
        const targetNode = nodes.find((node) => node.id === targetId);
        if (targetNode) {
          queue.push(targetNode);
          queue.sort((left, right) => right.priority - left.priority);
        }
      }
    });
  }

  if (order.length !== nodes.length) {
    issues.push({
      id: 'resolver-cycle',
      severity: 'error',
      code: 'cycle_detected',
      message: 'Se detectó un ciclo en las dependencias tácticas.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Revisa las dependencias AFTER / BEFORE de las acciones.',
    });
    return { order: nodes.map((node) => node.id), blocked: true, issues };
  }

  return { order, blocked: false, issues };
}

function buildGroups(statements: TacticalStatement[]): ExecutionGroup[] {
  const parallelStatements = statements.filter((statement) => Boolean(statement.parallelGroupId));
  const groups = new Map<string, ExecutionGroup>();
  parallelStatements.forEach((statement) => {
    const groupId = statement.parallelGroupId || 'parallel';
    const current = groups.get(groupId) || {
      id: groupId,
      nodeIds: [],
      kind: 'parallel' as const,
      priority: statement.priority,
      confidence: statement.confidence,
    };
    current.nodeIds.push(`node-${statement.id}`);
    current.priority = Math.max(current.priority, statement.priority);
    current.confidence = Math.max(current.confidence, statement.confidence);
    groups.set(groupId, current);
  });
  return [...groups.values()];
}

function buildWindows(nodes: ExecutionNode[], order: string[]): ExecutionWindow[] {
  const windows = new Map<string, ExecutionWindow>();
  let currentTime = 0;
  order.forEach((nodeId) => {
    const node = nodes.find((item) => item.id === nodeId);
    if (!node) {
      return;
    }
    const baseDuration = node.kind === 'phase' ? 0.001 : node.kind === 'ball_event' ? 0.5 : 0.75;
    const start = currentTime;
    const end = currentTime + baseDuration;
    windows.set(nodeId, {
      id: `window-${nodeId}`,
      nodeId,
      earliestStart: start,
      latestStart: start,
      earliestEnd: end,
      latestEnd: end,
      confidence: node.confidence,
    });
    currentTime = end;
  });
  return [...windows.values()];
}

function buildBarriers(statements: TacticalStatement[]): ExecutionBarrier[] {
  const barriers: ExecutionBarrier[] = [];
  statements.forEach((statement) => {
    if (statement.verb === 'PASS') {
      barriers.push({
        id: `barrier-${statement.id}-ball-arrival`,
        kind: 'ball_arrival',
        subjectIds: [statement.id],
        condition: 'ball reaches the target actor or target zone',
        strict: true,
        confidence: statement.confidence,
      });
    }
    if (statement.verb === 'RECEIVE') {
      barriers.push({
        id: `barrier-${statement.id}-receive`,
        kind: 'receive_completion',
        subjectIds: [statement.id],
        condition: 'receiving actor controls the ball',
        strict: true,
        confidence: statement.confidence,
      });
    }
  });
  return barriers;
}

function buildConstraints(statements: TacticalStatement[]): ExecutionConstraint[] {
  return statements.flatMap((statement) =>
    statement.conditions.map((condition, index) => ({
      id: `constraint-${statement.id}-${index}`,
      kind:
        condition.kind === 'WHEN' ||
        condition.kind === 'IF' ||
        condition.kind === 'AFTER' ||
        condition.kind === 'BEFORE'
          ? 'time_order'
          : condition.kind === 'PARALLEL_WITH'
            ? 'mutual_exclusion'
            : 'actor_state',
      subjectIds: [statement.subjectId],
      expression: condition.expression,
      severity: 'info' as const,
      confidence: condition.confidence,
    }))
  );
}

export function resolveTacticalPlan(document: TacticalLanguageDocument, _context?: ResolverContext): ResolvedPlan {
  const nodes = document.statements.map(buildNode);
  const statementById = new Map(document.statements.map((statement) => [statement.id, statement]));
  const edges = document.dependencies.map((dependency) => ({
    id: dependency.id,
    fromNodeId: `node-${dependency.fromStatementId}`,
    toNodeId: `node-${dependency.toStatementId}`,
    relation: relationToEdgeRelation(dependency.relation),
    strength: dependency.relation === 'mutex' ? 1 : 0.8,
    confidence: 0.95,
  }));
  const groupedStatements = buildGroups(document.statements);
  const windows = buildWindows(nodes, topologicalOrder(nodes, edges).order);
  const barriers = buildBarriers(document.statements);
  const constraints = buildConstraints(document.statements);
  const topo = topologicalOrder(nodes, edges);
  const issues: ResolverIssue[] = [...topo.issues];
  const orderedStatements = topo.order
    .map((nodeId) => statementById.get(nodes.find((node) => node.id === nodeId)?.statementId || ''))
    .filter((statement): statement is TacticalStatement => Boolean(statement));

  const traceability = orderedStatements.map((statement, index) => ({
    statementId: statement.id,
    ruleId: statement.verb.toLowerCase(),
    confidence: statement.confidence,
    warnings: [],
    resolverStep: 'dependency-resolution' as const,
    logicalTimestamp: index + 1,
    originObjectIds: statement.originObjectIds,
    originRuleId: statement.originObjectIds[0] || undefined,
  }));

  const graph = {
    nodes,
    edges,
    constraints,
    groups: groupedStatements,
    barriers,
    windows,
  };

  if (document.validationIssues.some((issue) => issue.severity === 'error')) {
    issues.push(
      ...document.validationIssues.map((issue) => ({
        id: issue.id,
        severity: issue.severity,
        code: issue.code,
        message: issue.message,
        entityIds: issue.entityIds,
        relatedStatementIds: issue.relatedStatementIds,
        suggestion: issue.suggestion,
      }))
    );
  }

  return {
    documentId: document.documentId,
    graph,
    executionOrder: orderedStatements.map((statement) => statement.id),
    possession: document.possession,
    warnings: issues,
    confidence: document.confidence,
    traceability,
  };
}
