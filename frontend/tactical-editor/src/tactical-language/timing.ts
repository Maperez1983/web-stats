import type { TacticalLanguageDocument, TacticalPhase, TacticalStatement } from './types';
import { getVerbMeta } from './vocabulary';

export interface TacticalTimingWindow {
  statementId: string;
  start: number;
  end: number;
  duration: number;
}

export interface TacticalTimingPlan {
  duration: number;
  currentTime: number;
  windows: TacticalTimingWindow[];
  phases: TacticalPhase[];
}

function clampWindow(start: number, end: number, duration: number): TacticalTimingWindow {
  const safeStart = Math.max(0, start);
  const safeEnd = Math.max(safeStart, Math.min(duration, end));
  return {
    statementId: '',
    start: safeStart,
    end: safeEnd,
    duration: safeEnd - safeStart,
  };
}

function statementById(document: TacticalLanguageDocument, statementId: string): TacticalStatement | null {
  return document.statements.find((statement) => statement.id === statementId) || null;
}

export function planTacticalTiming(
  document: TacticalLanguageDocument,
  executionOrder: string[],
  durationTarget = 10
): TacticalTimingPlan {
  const windows: TacticalTimingWindow[] = [];
  const statements = executionOrder
    .map((statementId) => statementById(document, statementId))
    .filter((statement): statement is TacticalStatement => Boolean(statement));

  const startTimes = new Map<string, number>();
  const endTimes = new Map<string, number>();
  let cursor = 0;

  statements.forEach((statement) => {
    const verbMeta = getVerbMeta(statement.verb);
    let start = cursor;
    let end = cursor;

    if (statement.verb === 'BUILD_UP') {
      start = 0;
      end = 0;
    } else if (statement.verb === 'PASS') {
      start = cursor;
      end = cursor + verbMeta.defaultDuration;
      cursor = end;
    } else if (statement.verb === 'RECEIVE') {
      start = Math.max(0, cursor - 0.05);
      end = start + verbMeta.defaultDuration;
      cursor = end;
    } else if (statement.verb === 'CARRY') {
      start = cursor;
      end = cursor + verbMeta.defaultDuration;
      cursor = end;
    } else if (statement.verb === 'RUN') {
      start = Math.max(0.4, cursor - 0.7);
      end = Math.max(start + verbMeta.defaultDuration, 5.5);
    } else if (statement.verb === 'SUPPORT') {
      start = Math.max(0.25, cursor - 0.55);
      end = Math.max(start + verbMeta.defaultDuration, 3.0);
    } else if (statement.verb === 'HOLD') {
      start = 0;
      end = 3;
    } else if (statement.verb === 'CREATE_SPACE' || statement.verb === 'OCCUPY_SPACE') {
      start = Math.max(0.5, cursor - 0.3);
      end = Math.max(start + verbMeta.defaultDuration, 4.5);
    } else if (statement.verb === 'PROGRESSION') {
      start = Math.max(cursor, 3);
      end = durationTarget;
    }

    const window = clampWindow(start, end, durationTarget);
    window.statementId = statement.id;
    startTimes.set(statement.id, window.start);
    endTimes.set(statement.id, window.end);
    windows.push(window);
  });

  const phases = document.phases.map((phase) => {
    const phaseStatements = phase.statementIds
      .map((statementId) => statementById(document, statementId))
      .filter((statement): statement is TacticalStatement => Boolean(statement));
    const first = phaseStatements[0];
    const last = phaseStatements[phaseStatements.length - 1];
    return {
      ...phase,
      startTime: first ? startTimes.get(first.id) || phase.startTime : phase.startTime,
      endTime: last ? endTimes.get(last.id) || phase.endTime : phase.endTime,
    };
  });

  return {
    duration: durationTarget,
    currentTime: 0,
    windows,
    phases,
  };
}
