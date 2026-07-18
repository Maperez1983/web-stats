import {
  createDefaultAnimationTimeline,
  createUuid,
  deepClone,
  type AnimationKeyframe,
  type AnimationTrack,
  type SceneObject,
  type SceneTimelineKeyframe,
  type TacticalScene,
} from '../core/sceneSchema';
import { normalizeAnimationInterpolation } from './AnimationInterpolator';

function buildValuesFromSnapshot(snapshot: SceneTimelineKeyframe['objects'][number]): AnimationKeyframe['values'] {
  return {
    x: snapshot.x,
    y: snapshot.y,
    width: snapshot.width,
    height: snapshot.height,
    rotation: snapshot.rotation,
    scaleX: snapshot.scaleX,
    scaleY: snapshot.scaleY,
    visible: snapshot.visible,
    locked: snapshot.locked,
    zIndex: snapshot.zIndex,
    style: deepClone(snapshot.style),
    data: deepClone(snapshot.data),
  };
}

export function createAnimationTrack(object: SceneObject, options?: { label?: string }): AnimationTrack {
  const now = new Date().toISOString();
  return {
    id: createUuid('track'),
    objectId: object.id,
    objectType: object.type,
    layerId: object.layerId,
    label: options?.label || String(object.data.label || object.data.name || object.type),
    visible: object.visible,
    locked: object.locked,
    keyframes: [],
    metadata: {
      createdAt: now,
      updatedAt: now,
      sequenceIds: [],
    },
  };
}

export function createAnimationKeyframe(
  objectId: string,
  trackId: string,
  time: number,
  values: AnimationKeyframe['values'],
  options?: {
    id?: string;
    label?: string;
    interpolation?: AnimationKeyframe['interpolation'];
    easing?: AnimationKeyframe['easing'];
    source?: AnimationKeyframe['metadata']['source'];
  }
): AnimationKeyframe {
  const now = new Date().toISOString();
  const interpolation = normalizeAnimationInterpolation(options?.interpolation || 'linear');
  const easing = normalizeAnimationInterpolation(options?.easing || interpolation);
  return {
    id: options?.id || createUuid('anim'),
    time,
    values: deepClone(values),
    interpolation,
    easing,
    metadata: {
      objectId,
      trackId,
      label: options?.label,
      createdAt: now,
      updatedAt: now,
      source: options?.source || 'manual',
    },
  };
}

export function sortTrackKeyframes(track: AnimationTrack): AnimationTrack {
  return {
    ...track,
    keyframes: [...track.keyframes].sort((left, right) => left.time - right.time),
    metadata: {
      ...track.metadata,
      updatedAt: new Date().toISOString(),
    },
  };
}

export function upsertTrackKeyframe(
  track: AnimationTrack,
  keyframe: AnimationKeyframe
): AnimationTrack {
  const nextKeyframes = track.keyframes.filter((item) => item.id !== keyframe.id);
  nextKeyframes.push(keyframe);
  return sortTrackKeyframes({
    ...track,
    keyframes: nextKeyframes,
  });
}

export function removeTrackKeyframe(track: AnimationTrack, keyframeId: string): AnimationTrack {
  return {
    ...track,
    keyframes: track.keyframes.filter((item) => item.id !== keyframeId),
    metadata: {
      ...track.metadata,
      updatedAt: new Date().toISOString(),
    },
  };
}

export function createTrackKeyframeFromSnapshot(
  snapshot: SceneTimelineKeyframe['objects'][number],
  time: number,
  track: AnimationTrack,
  options?: {
    id?: string;
    label?: string;
    interpolation?: AnimationKeyframe['interpolation'];
    easing?: AnimationKeyframe['easing'];
    source?: AnimationKeyframe['metadata']['source'];
  }
): AnimationKeyframe {
  return createAnimationKeyframe(snapshot.id, track.id, time, buildValuesFromSnapshot(snapshot), {
    id: options?.id,
    label: options?.label,
    interpolation: options?.interpolation,
    easing: options?.easing,
    source: options?.source,
  });
}

export function deriveAnimationTracksFromScene(scene: TacticalScene): AnimationTrack[] {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const trackMap = new Map<string, AnimationTrack>();
  const frames = [...keyframes].sort((left, right) => left.time - right.time);
  frames.forEach((frame) => {
    const rawFrame = frame as SceneTimelineKeyframe & Record<string, unknown>;
    const legacyCanvasState = rawFrame.canvas_state as Record<string, unknown> | undefined;
    const snapshotList = Array.isArray(rawFrame.objects)
      ? rawFrame.objects
      : Array.isArray(legacyCanvasState?.objects)
        ? (legacyCanvasState.objects as SceneTimelineKeyframe['objects'])
        : [];
    snapshotList.forEach((snapshot) => {
      if (!snapshot || typeof snapshot.id !== 'string') {
        return;
      }
      const existing = trackMap.get(snapshot.id);
      const track =
        existing ||
        createAnimationTrack(
          {
            ...snapshot,
            style: deepClone(snapshot.style),
            data: deepClone(snapshot.data),
          },
          { label: frame.label || String(snapshot.data.label || snapshot.data.name || snapshot.type) }
        );
      const nextKeyframe = createTrackKeyframeFromSnapshot(snapshot, frame.time, track, {
        label: frame.label,
        source: 'legacy',
      });
      trackMap.set(snapshot.id, upsertTrackKeyframe(track, nextKeyframe));
    });
  });
  return [...trackMap.values()].map((track) => sortTrackKeyframes(track));
}

export function normalizeAnimationTracks(tracks: AnimationTrack[]): AnimationTrack[] {
  return [...tracks]
    .filter((track): track is AnimationTrack => Boolean(track && Array.isArray(track.keyframes)))
    .map((track) => sortTrackKeyframes(track))
    .sort((left, right) => left.objectId.localeCompare(right.objectId));
}

export function collectTrackKeyframeIds(tracks: AnimationTrack[]): string[] {
  return tracks.flatMap((track) => track.keyframes.map((keyframe) => keyframe.id));
}
