import type { AnimationInterpolation, AnimationKeyframeValues, SceneObjectStyle } from '../core/sceneSchema';

function clampRatio(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

export function normalizeAnimationInterpolation(value: unknown): AnimationInterpolation {
  const raw = String(value || 'linear').toLowerCase();
  if (raw === 'ease-in' || raw === 'ease-out' || raw === 'ease-in-out' || raw === 'step') {
    return raw;
  }
  return 'linear';
}

export function applyAnimationEasing(ratio: number, easing: AnimationInterpolation): number {
  const t = clampRatio(ratio);
  switch (normalizeAnimationInterpolation(easing)) {
    case 'ease-in':
      return t * t;
    case 'ease-out':
      return 1 - (1 - t) * (1 - t);
    case 'ease-in-out':
      return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    case 'step':
      return t < 1 ? 0 : 1;
    default:
      return t;
  }
}

export function interpolateNumber(
  left: number | undefined,
  right: number | undefined,
  ratio: number,
  easing: AnimationInterpolation = 'linear'
): number | undefined {
  if (typeof left !== 'number' && typeof right !== 'number') {
    return undefined;
  }
  if (typeof left !== 'number') {
    return right;
  }
  if (typeof right !== 'number') {
    return left;
  }
  return left + (right - left) * applyAnimationEasing(ratio, easing);
}

export function interpolateBoolean(
  left: boolean | undefined,
  right: boolean | undefined,
  ratio: number
): boolean | undefined {
  if (typeof left !== 'boolean' && typeof right !== 'boolean') {
    return undefined;
  }
  if (ratio < 1) {
    return typeof left === 'boolean' ? left : right;
  }
  return typeof right === 'boolean' ? right : left;
}

export function interpolateString(
  left: string | undefined,
  right: string | undefined,
  ratio: number
): string | undefined {
  if (typeof left !== 'string' && typeof right !== 'string') {
    return undefined;
  }
  if (ratio < 1) {
    return typeof left === 'string' ? left : right;
  }
  return typeof right === 'string' ? right : left;
}

function interpolateStyleValue(
  left: SceneObjectStyle | undefined,
  right: SceneObjectStyle | undefined,
  ratio: number,
  easing: AnimationInterpolation
): SceneObjectStyle | undefined {
  if (!left && !right) {
    return undefined;
  }
  const keys = new Set([...(left ? Object.keys(left) : []), ...(right ? Object.keys(right) : [])]);
  const next: SceneObjectStyle = {};
  keys.forEach((key) => {
    const leftValue = left?.[key as keyof SceneObjectStyle];
    const rightValue = right?.[key as keyof SceneObjectStyle];
    if (Array.isArray(leftValue) || Array.isArray(rightValue)) {
      next[key as keyof SceneObjectStyle] = (ratio < 1 ? leftValue : rightValue) as never;
      return;
    }
    if (typeof leftValue === 'number' || typeof rightValue === 'number') {
      next[key as keyof SceneObjectStyle] = interpolateNumber(
        typeof leftValue === 'number' ? leftValue : undefined,
        typeof rightValue === 'number' ? rightValue : undefined,
        ratio,
        easing
      ) as never;
      return;
    }
    if (typeof leftValue === 'string' || typeof rightValue === 'string') {
      next[key as keyof SceneObjectStyle] = interpolateString(
        typeof leftValue === 'string' ? leftValue : undefined,
        typeof rightValue === 'string' ? rightValue : undefined,
        ratio
      ) as never;
      return;
    }
    next[key as keyof SceneObjectStyle] = (ratio < 1 ? leftValue : rightValue) as never;
  });
  return next;
}

function shallowMergeObject(
  left: Record<string, unknown> | undefined,
  right: Record<string, unknown> | undefined,
  ratio: number
): Record<string, unknown> | undefined {
  if (!left && !right) {
    return undefined;
  }
  const keys = new Set([...(left ? Object.keys(left) : []), ...(right ? Object.keys(right) : [])]);
  const next: Record<string, unknown> = {};
  keys.forEach((key) => {
    const leftValue = left?.[key];
    const rightValue = right?.[key];
    if (typeof leftValue === 'number' || typeof rightValue === 'number') {
      next[key] = interpolateNumber(
        typeof leftValue === 'number' ? leftValue : undefined,
        typeof rightValue === 'number' ? rightValue : undefined,
        ratio
      );
      return;
    }
    if (typeof leftValue === 'boolean' || typeof rightValue === 'boolean') {
      next[key] = interpolateBoolean(
        typeof leftValue === 'boolean' ? leftValue : undefined,
        typeof rightValue === 'boolean' ? rightValue : undefined,
        ratio
      );
      return;
    }
    if (typeof leftValue === 'string' || typeof rightValue === 'string') {
      next[key] = interpolateString(
        typeof leftValue === 'string' ? leftValue : undefined,
        typeof rightValue === 'string' ? rightValue : undefined,
        ratio
      );
      return;
    }
    next[key] = ratio < 1 ? leftValue : rightValue;
  });
  return next;
}

export function interpolateAnimationValues(
  left: AnimationKeyframeValues | undefined,
  right: AnimationKeyframeValues | undefined,
  ratio: number,
  easing: AnimationInterpolation = 'linear'
): AnimationKeyframeValues | undefined {
  if (!left && !right) {
    return undefined;
  }
  const t = clampRatio(ratio);
  const keys = new Set([...(left ? Object.keys(left) : []), ...(right ? Object.keys(right) : [])]);
  const next: AnimationKeyframeValues = {};
  keys.forEach((key) => {
    const leftValue = left?.[key as keyof AnimationKeyframeValues];
    const rightValue = right?.[key as keyof AnimationKeyframeValues];
    if (key === 'style') {
      next[key as keyof AnimationKeyframeValues] = interpolateStyleValue(
        leftValue as SceneObjectStyle | undefined,
        rightValue as SceneObjectStyle | undefined,
        t,
        easing
      ) as never;
      return;
    }
    if (key === 'data') {
      next[key as keyof AnimationKeyframeValues] = shallowMergeObject(
        leftValue as Record<string, unknown> | undefined,
        rightValue as Record<string, unknown> | undefined,
        t
      ) as never;
      return;
    }
    if (typeof leftValue === 'number' || typeof rightValue === 'number') {
      next[key as keyof AnimationKeyframeValues] = interpolateNumber(
        typeof leftValue === 'number' ? leftValue : undefined,
        typeof rightValue === 'number' ? rightValue : undefined,
        t,
        easing
      ) as never;
      return;
    }
    if (typeof leftValue === 'boolean' || typeof rightValue === 'boolean') {
      next[key as keyof AnimationKeyframeValues] = interpolateBoolean(
        typeof leftValue === 'boolean' ? leftValue : undefined,
        typeof rightValue === 'boolean' ? rightValue : undefined,
        t
      ) as never;
      return;
    }
    if (typeof leftValue === 'string' || typeof rightValue === 'string') {
      next[key as keyof AnimationKeyframeValues] = interpolateString(
        typeof leftValue === 'string' ? leftValue : undefined,
        typeof rightValue === 'string' ? rightValue : undefined,
        t
      ) as never;
      return;
    }
    next[key as keyof AnimationKeyframeValues] = (t < 1 ? leftValue : rightValue) as never;
  });
  return next;
}
