export type AnimationPlaybackState = {
  playing: boolean;
  loop: boolean;
  speed: number;
  timelineZoom: number;
  scrollX: number;
};

export const DEFAULT_ANIMATION_SPEEDS = [0.25, 0.5, 1, 2, 4] as const;

export function createAnimationPlaybackState(
  overrides?: Partial<AnimationPlaybackState>
): AnimationPlaybackState {
  return {
    playing: false,
    loop: true,
    speed: 1,
    timelineZoom: 1,
    scrollX: 0,
    ...overrides,
  };
}

export function normalizeAnimationSpeed(value: number): number {
  const candidate = DEFAULT_ANIMATION_SPEEDS.find((speed) => Math.abs(speed - value) < 0.001);
  return candidate || 1;
}

export function clampAnimationTime(time: number, duration: number): number {
  if (!Number.isFinite(time)) {
    return 0;
  }
  if (duration <= 0) {
    return Math.max(0, time);
  }
  return Math.min(Math.max(0, time), duration);
}

export function advanceAnimationTime(
  currentTime: number,
  elapsedMs: number,
  playback: AnimationPlaybackState,
  duration: number
): { time: number; looped: boolean } {
  const next = currentTime + (elapsedMs / 1000) * normalizeAnimationSpeed(playback.speed);
  if (!playback.loop && next >= duration) {
    return { time: duration, looped: false };
  }
  if (playback.loop && duration > 0) {
    return { time: next % duration, looped: next >= duration };
  }
  return { time: clampAnimationTime(next, duration), looped: false };
}

export function toggleAnimationBoolean(value: boolean): boolean {
  return !value;
}
