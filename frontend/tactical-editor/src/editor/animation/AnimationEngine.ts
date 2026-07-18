import {
  createDefaultAnimationTimeline,
  deepClone,
  type AnimationKeyframeValues,
  type AnimationTrack,
  type SceneObject,
  type TacticalScene,
} from '../core/sceneSchema';
import { interpolateAnimationValues, normalizeAnimationInterpolation } from './AnimationInterpolator';
import { deriveAnimationTracksFromScene, normalizeAnimationTracks } from './AnimationTrack';

function cloneObject(object: SceneObject): SceneObject {
  return deepClone(object);
}

function buildTrackMap(scene: TacticalScene): Map<string, AnimationTrack> {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const tracks = Array.isArray(timeline.tracks) && timeline.tracks.length
    ? normalizeAnimationTracks(timeline.tracks)
    : deriveAnimationTracksFromScene(scene);
  return new Map(tracks.map((track) => [track.objectId, track]));
}

export function resolveAnimationDuration(scene: TacticalScene): number {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const trackDuration = [...buildTrackMap(scene).values()].reduce((max, track) => {
    const trackMax = track.keyframes.reduce((innerMax, keyframe) => Math.max(innerMax, keyframe.time), 0);
    return Math.max(max, trackMax);
  }, 0);
  const sceneKeyframeDuration = keyframes.reduce((max, keyframe) => Math.max(max, keyframe.time), 0);
  return Math.max(timeline.duration || 0, sceneKeyframeDuration, trackDuration);
}

function evaluateTrackValues(track: AnimationTrack, time: number): AnimationKeyframeValues | null {
  const frames = [...track.keyframes].sort((left, right) => left.time - right.time);
  if (!frames.length) {
    return null;
  }
  if (frames.length === 1 || time <= frames[0].time) {
    return deepClone(frames[0].values);
  }
  const last = frames[frames.length - 1];
  if (time >= last.time) {
    return deepClone(last.values);
  }
  const previous = [...frames].reverse().find((frame) => frame.time <= time) || frames[0];
  const next = frames.find((frame) => frame.time >= time && frame.id !== previous.id) || last;
  if (previous.id === next.id) {
    return deepClone(previous.values);
  }
  const ratio = Math.min(1, Math.max(0, (time - previous.time) / Math.max(next.time - previous.time, 1)));
  return (
    interpolateAnimationValues(
      previous.values,
      next.values,
      ratio,
      normalizeAnimationInterpolation(next.easing || next.interpolation)
    ) || deepClone(next.values)
  );
}

function applyValues(object: SceneObject, values: AnimationKeyframeValues | null): SceneObject {
  if (!values) {
    return object;
  }
  return {
    ...object,
    x: typeof values.x === 'number' ? values.x : object.x,
    y: typeof values.y === 'number' ? values.y : object.y,
    width: typeof values.width === 'number' ? values.width : object.width,
    height: typeof values.height === 'number' ? values.height : object.height,
    rotation: typeof values.rotation === 'number' ? values.rotation : object.rotation,
    scaleX: typeof values.scaleX === 'number' ? values.scaleX : object.scaleX,
    scaleY: typeof values.scaleY === 'number' ? values.scaleY : object.scaleY,
    visible: typeof values.visible === 'boolean' ? values.visible : object.visible,
    locked: typeof values.locked === 'boolean' ? values.locked : object.locked,
    zIndex: typeof values.zIndex === 'number' ? values.zIndex : object.zIndex,
    layerId: values.layerId || object.layerId,
    type: values.type || object.type,
    style: values.style ? { ...object.style, ...deepClone(values.style) } : object.style,
    data: values.data ? { ...object.data, ...deepClone(values.data) } : object.data,
  };
}

export function evaluateAnimationScene(scene: TacticalScene, time: number): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const trackMap = buildTrackMap(scene);
  const nextTime = Math.max(0, time);
  return {
    ...deepClone(scene),
    timeline: {
      ...deepClone(timeline),
      currentTime: nextTime,
    },
    objects: scene.objects.map((object) => {
      const track = trackMap.get(object.id);
      return applyValues(cloneObject(object), track ? evaluateTrackValues(track, nextTime) : null);
    }),
  };
}

export function projectAnimationScene(scene: TacticalScene, time: number): TacticalScene {
  return evaluateAnimationScene(scene, time);
}

export function sampleSceneAnimation(scene: TacticalScene, time: number): TacticalScene {
  return evaluateAnimationScene(scene, time);
}
