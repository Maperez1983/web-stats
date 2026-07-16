import { HISTORY_LIMIT, deepClone } from './sceneSchema';
import type { TacticalScene } from './sceneSchema';

export type HistoryState = {
  past: TacticalScene[];
  future: TacticalScene[];
  transactionBase: TacticalScene | null;
};

export function createHistoryState(): HistoryState {
  return {
    past: [],
    future: [],
    transactionBase: null,
  };
}

export function beginHistoryTransaction(history: HistoryState, scene: TacticalScene): HistoryState {
  if (history.transactionBase) {
    return history;
  }
  return {
    ...history,
    transactionBase: deepClone(scene),
  };
}

export function commitHistoryTransaction(
  history: HistoryState,
  currentScene: TacticalScene
): HistoryState {
  if (!history.transactionBase) {
    return history;
  }
  const before = JSON.stringify(history.transactionBase);
  const after = JSON.stringify(currentScene);
  if (before === after) {
    return {
      ...history,
      transactionBase: null,
    };
  }
  const past = [...history.past, history.transactionBase].slice(-HISTORY_LIMIT);
  return {
    past,
    future: [],
    transactionBase: null,
  };
}

export function pushHistorySnapshot(history: HistoryState, scene: TacticalScene): HistoryState {
  const past = [...history.past, deepClone(scene)].slice(-HISTORY_LIMIT);
  return {
    past,
    future: [],
    transactionBase: null,
  };
}

export function undoHistory(
  history: HistoryState,
  currentScene: TacticalScene
): { history: HistoryState; scene: TacticalScene | null } {
  const previous = history.past[history.past.length - 1];
  if (!previous) {
    return { history, scene: null };
  }
  return {
    scene: deepClone(previous),
    history: {
      past: history.past.slice(0, -1),
      future: [deepClone(currentScene), ...history.future].slice(0, HISTORY_LIMIT),
      transactionBase: null,
    },
  };
}

export function redoHistory(
  history: HistoryState,
  currentScene: TacticalScene
): { history: HistoryState; scene: TacticalScene | null } {
  const next = history.future[0];
  if (!next) {
    return { history, scene: null };
  }
  return {
    scene: deepClone(next),
    history: {
      past: [...history.past, deepClone(currentScene)].slice(-HISTORY_LIMIT),
      future: history.future.slice(1),
      transactionBase: null,
    },
  };
}
