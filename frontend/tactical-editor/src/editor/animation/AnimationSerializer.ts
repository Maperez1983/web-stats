import { createDefaultAnimationTimeline, deepClone, type AnimationTrack, type TacticalScene } from '../core/sceneSchema';
import { deriveAnimationTracksFromScene, normalizeAnimationTracks } from './AnimationTrack';

export function normalizeAnimationTimeline(scene: TacticalScene): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const rawTracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const sequences = Array.isArray(timeline.sequences) ? timeline.sequences : [];
  const normalizedTracks =
    rawTracks.length
      ? normalizeAnimationTracks(rawTracks)
      : deriveAnimationTracksFromScene(scene);
  const keyframeDuration = keyframes.reduce((max, keyframe) => Math.max(max, keyframe.time), 0);
  const trackDuration = normalizedTracks.reduce((max, track) => {
    const trackMax = track.keyframes.reduce((innerMax, keyframe) => Math.max(innerMax, keyframe.time), 0);
    return Math.max(max, trackMax);
  }, 0);
  return {
    ...scene,
    timeline: {
      ...timeline,
      duration: Math.max(timeline.duration, keyframeDuration, trackDuration),
      keyframes: [...keyframes].sort((left, right) => left.time - right.time),
      tracks: normalizedTracks.map((track) => ({
        ...track,
        keyframes: [...track.keyframes].sort((left, right) => left.time - right.time),
      })),
      sequences: [...sequences].map((sequence) => deepClone(sequence)),
      currentSequenceId: timeline.currentSequenceId || null,
    },
  };
}

export function serializeAnimationTracks(tracks: AnimationTrack[]): AnimationTrack[] {
  return tracks.map((track) => ({
    ...deepClone(track),
    keyframes: [...track.keyframes].sort((left, right) => left.time - right.time),
  }));
}

export function serializeAnimationTimeline(scene: TacticalScene): TacticalScene['timeline'] {
  return deepClone(normalizeAnimationTimeline(scene).timeline);
}
