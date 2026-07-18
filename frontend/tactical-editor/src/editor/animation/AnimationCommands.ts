import {
  createDefaultAnimationTimeline,
  createUuid,
  deepClone,
  type AnimationKeyframe,
  type AnimationTrack,
  type AnimationTimeline,
  type SceneObject,
  type TacticalScene,
} from '../core/sceneSchema';
import {
  createAnimationTrack,
  createTrackKeyframeFromSnapshot,
  deriveAnimationTracksFromScene,
  normalizeAnimationTracks,
  removeTrackKeyframe,
  sortTrackKeyframes,
  upsertTrackKeyframe,
} from './AnimationTrack';
import { createAnimationSelection, normalizeAnimationSelectionIds, type AnimationSelection } from './AnimationSelection';

function sortKeyframes(timeline: AnimationTimeline): AnimationTimeline {
  return {
    ...timeline,
    keyframes: [...(Array.isArray(timeline.keyframes) ? timeline.keyframes : [])].sort((left, right) => left.time - right.time),
    tracks: normalizeAnimationTracks(Array.isArray(timeline.tracks) ? timeline.tracks : []),
    sequences: [...(Array.isArray(timeline.sequences) ? timeline.sequences : [])].sort((left, right) => left.duration - right.duration),
  };
}

export function normalizeSceneAnimation(scene: TacticalScene): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) && timeline.tracks.length
    ? normalizeAnimationTracks(timeline.tracks)
    : deriveAnimationTracksFromScene(scene);
  const sequences = Array.isArray(timeline.sequences) ? timeline.sequences : [];
  const duration = Number.isFinite(Number(timeline.duration)) ? Number(timeline.duration) : 0;
  const maxTrackTime = tracks.reduce((max, track) => {
    const trackMax = track.keyframes.reduce((innerMax, keyframe) => Math.max(innerMax, keyframe.time), 0);
    return Math.max(max, trackMax);
  }, 0);
  const maxSceneTime = keyframes.reduce((max, keyframe) => Math.max(max, keyframe.time), 0);
  return {
    ...scene,
    timeline: sortKeyframes({
      ...timeline,
      duration: Math.max(duration, maxTrackTime, maxSceneTime),
      keyframes: [...keyframes].sort((left, right) => left.time - right.time),
      tracks,
      sequences: [...sequences],
      currentSequenceId: timeline.currentSequenceId || null,
    }),
  };
}

export function captureAnimationKeyframe(
  scene: TacticalScene,
  time: number,
  options?: { objectIds?: string[]; label?: string; source?: AnimationKeyframe['metadata']['source'] }
): {
  sceneKeyframe: TacticalScene['timeline']['keyframes'][number];
  tracks: TacticalScene['timeline']['tracks'];
} {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const objectIds = options?.objectIds?.length
    ? normalizeAnimationSelectionIds(options.objectIds)
    : scene.objects.map((object) => object.id);
  const selectedObjects = scene.objects.filter((object) => objectIds.includes(object.id));
  const now = new Date().toISOString();
  const sceneKeyframe = {
    id: createUuid('keyframe'),
    time,
    label: options?.label,
    objectIds,
    objects: selectedObjects.map((object) => ({
      id: object.id,
      type: object.type,
      layerId: object.layerId,
      x: object.x,
      y: object.y,
      width: object.width,
      height: object.height,
      rotation: object.rotation,
      scaleX: object.scaleX,
      scaleY: object.scaleY,
      style: deepClone(object.style),
      data: deepClone(object.data),
      visible: object.visible,
      locked: object.locked,
      zIndex: object.zIndex,
    })),
  };
  const trackMap = new Map<string, AnimationTrack>(tracks.map((track) => [track.objectId, deepClone(track)]));
  selectedObjects.forEach((object) => {
    const track =
      trackMap.get(object.id) ||
      createAnimationTrack(object, { label: options?.label || String(object.data.label || object.type) });
    const keyframe = createTrackKeyframeFromSnapshot(
      sceneKeyframe.objects.find((item) => item.id === object.id) || {
        id: object.id,
        type: object.type,
        layerId: object.layerId,
        x: object.x,
        y: object.y,
        width: object.width,
        height: object.height,
        rotation: object.rotation,
        scaleX: object.scaleX,
        scaleY: object.scaleY,
        style: deepClone(object.style),
        data: deepClone(object.data),
        visible: object.visible,
        locked: object.locked,
        zIndex: object.zIndex,
      },
      time,
      track,
      {
        id: sceneKeyframe.id,
        label: options?.label,
        interpolation: 'linear',
        easing: 'linear',
        source: options?.source || 'manual',
      }
    );
    trackMap.set(
      object.id,
      sortTrackKeyframes(
        upsertTrackKeyframe(track, {
          ...keyframe,
          metadata: {
            ...keyframe.metadata,
            createdAt: now,
            updatedAt: now,
          },
        })
      )
    );
  });
  return {
    sceneKeyframe,
    tracks: normalizeAnimationTracks([...trackMap.values()]),
  };
}

export function applyAnimationKeyframeCapture(
  scene: TacticalScene,
  time: number,
  options?: { objectIds?: string[]; label?: string; source?: AnimationKeyframe['metadata']['source'] }
): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const capture = captureAnimationKeyframe(scene, time, options);
  const nextKeyframes = [...keyframes.filter((keyframe) => keyframe.time !== time), capture.sceneKeyframe].sort(
    (left, right) => left.time - right.time
  );
  return normalizeSceneAnimation({
    ...scene,
    timeline: {
      ...timeline,
      duration: Math.max(timeline.duration, time),
      currentTime: time,
      keyframes: nextKeyframes,
      tracks: capture.tracks,
    },
  });
}

export function removeAnimationKeyframe(scene: TacticalScene, keyframeId: string): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const nextKeyframes = keyframes.filter((keyframe) => keyframe.id !== keyframeId);
  const nextTracks = tracks
    .map((track) => removeTrackKeyframe(track, keyframeId))
    .filter((track) => Array.isArray(track.keyframes) && track.keyframes.length > 0);
  return normalizeSceneAnimation({
    ...scene,
    timeline: {
      ...timeline,
      keyframes: nextKeyframes,
      tracks: nextTracks,
      duration: Math.max(
        nextKeyframes.reduce((max, keyframe) => Math.max(max, keyframe.time), 0),
        nextTracks.reduce(
          (max, track) => Math.max(max, track.keyframes.reduce((trackMax, keyframe) => Math.max(trackMax, keyframe.time), 0)),
          0
        )
      ),
    },
  });
}

export function moveAnimationKeyframe(
  scene: TacticalScene,
  keyframeId: string,
  nextTime: number
): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const target = keyframes.find((keyframe) => keyframe.id === keyframeId);
  if (!target) {
    return scene;
  }
  const nextKeyframes = keyframes.map((keyframe) =>
    keyframe.id === keyframeId ? { ...keyframe, time: Math.max(0, nextTime) } : keyframe
  );
  const trackUpdates = tracks.map((track) => ({
    ...track,
    keyframes: track.keyframes.map((keyframe) =>
      keyframe.id === keyframeId
        ? { ...keyframe, time: Math.max(0, nextTime) }
        : keyframe
    ),
  }));
  return normalizeSceneAnimation({
    ...scene,
    timeline: {
      ...timeline,
      duration: Math.max(timeline.duration, nextTime),
      keyframes: nextKeyframes.sort((left, right) => left.time - right.time),
      tracks: normalizeAnimationTracks(trackUpdates),
    },
  });
}

export function duplicateAnimationSelection(
  scene: TacticalScene,
  keyframeIds: string[],
  offset = 0.5
): TacticalScene {
  const timeline = scene.timeline ?? createDefaultAnimationTimeline();
  const keyframes = Array.isArray(timeline.keyframes) ? timeline.keyframes : [];
  const tracks = Array.isArray(timeline.tracks) ? timeline.tracks : [];
  const selected = new Set(keyframeIds);
  if (!selected.size) {
    return scene;
  }
  const duplicatedKeyframes = keyframes
    .filter((keyframe) => selected.has(keyframe.id))
    .map((keyframe) => ({
      ...deepClone(keyframe),
      id: createUuid('keyframe'),
      time: Math.max(0, keyframe.time + offset),
      label: keyframe.label ? `${keyframe.label} copia` : undefined,
    }));
  const trackMap = new Map(tracks.map((track) => [track.objectId, deepClone(track)]));
  duplicatedKeyframes.forEach((keyframe) => {
    keyframe.objects.forEach((snapshot) => {
      const track =
        trackMap.get(snapshot.id) ||
        createAnimationTrack(snapshot as unknown as SceneObject);
      const duplicatedTrackKeyframe = createTrackKeyframeFromSnapshot(snapshot, keyframe.time, track, {
        id: keyframe.id,
        label: keyframe.label,
        source: 'manual',
      });
      trackMap.set(snapshot.id, upsertTrackKeyframe(track, duplicatedTrackKeyframe));
    });
  });
  return normalizeSceneAnimation({
    ...scene,
    timeline: {
      ...timeline,
      keyframes: [...keyframes, ...duplicatedKeyframes].sort((left, right) => left.time - right.time),
      tracks: normalizeAnimationTracks([...trackMap.values()]),
      duration: Math.max(
        timeline.duration,
        ...duplicatedKeyframes.map((keyframe) => keyframe.time)
      ),
    },
  });
}

export function createAnimationSelectionFromIds(
  objectIds: string[],
  trackIds: string[] = [],
  keyframeIds: string[] = [],
  sequenceIds: string[] = []
): AnimationSelection {
  return createAnimationSelection({
    objectIds,
    trackIds,
    keyframeIds,
    sequenceIds,
  });
}
