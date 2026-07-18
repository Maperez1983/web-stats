import {
  createUuid,
  deepClone,
  type AnimationSequence,
  type AnimationTrack,
  type SceneObject,
  type SceneTimelineKeyframe,
  type TacticalScene,
} from '../editor/core/sceneSchema';
import { normalizeAnimationTimeline } from '../editor/animation/AnimationSerializer';
import {
  createAnimationTrack,
  createTrackKeyframeFromSnapshot,
  normalizeAnimationTracks,
  sortTrackKeyframes,
} from '../editor/animation/AnimationTrack';
import { inferTacticalLanguage } from './inference';
import { normalizeTacticalScene, type NormalizedTacticalScene } from './normalizer';
import { resolvePossession } from './possession';
import { resolveTacticalPlan } from './resolver';
import { planTacticalTiming, type TacticalTimingPlan } from './timing';
import type {
  TacticalCompilationResult,
  TacticalLanguageDocument,
  TacticalValidationIssue,
  TacticalStatement,
} from './types';

type MotionSample = {
  time: number;
  x: number;
  y: number;
  rotation: number;
  width: number;
  height: number;
  visible: boolean;
  locked: boolean;
  zIndex: number;
  type: SceneObject['type'];
  layerId: SceneObject['layerId'];
  style: SceneObject['style'];
  data: SceneObject['data'];
};

type MotionPlan = {
  objectId: string;
  samples: MotionSample[];
};

function objectCenter(object: SceneObject) {
  return {
    x: object.x + object.width * object.scaleX * 0.5,
    y: object.y + object.height * object.scaleY * 0.5,
  };
}

function pointToObjectTopLeft(point: { x: number; y: number }, object: SceneObject) {
  return {
    x: point.x - object.width * object.scaleX * 0.5,
    y: point.y - object.height * object.scaleY * 0.5,
  };
}

function statementById(language: TacticalLanguageDocument, statementId: string): TacticalStatement | null {
  return language.statements.find((statement) => statement.id === statementId) || null;
}

function actorObject(context: NormalizedTacticalScene, actorId?: string | null): SceneObject | null {
  if (!actorId) {
    return null;
  }
  return context.scene.objects.find((object) => object.id === actorId) || null;
}

function arrowByKind(context: NormalizedTacticalScene, kind: 'pass' | 'run' | 'trajectory' | 'line', index = 0) {
  return context.arrows.filter((arrow) => arrow.kind === kind)[index] || null;
}

function toSnapshot(object: SceneObject, time: number, position?: { x: number; y: number }): MotionSample {
  const nextPosition = position || { x: object.x, y: object.y };
  return {
    time,
    x: nextPosition.x,
    y: nextPosition.y,
    rotation: object.rotation,
    width: object.width,
    height: object.height,
    visible: object.visible,
    locked: object.locked,
    zIndex: object.zIndex,
    type: object.type,
    layerId: object.layerId,
    style: deepClone(object.style),
    data: deepClone(object.data),
  };
}

function addSample(samples: MotionSample[], sample: MotionSample) {
  const next = samples.filter((item) => item.time !== sample.time);
  next.push(sample);
  next.sort((left, right) => left.time - right.time);
  return next;
}

function ensureBoundarySamples(samples: MotionSample[], object: SceneObject, duration: number) {
  const start = toSnapshot(object, 0);
  const end = toSnapshot(object, duration);
  return addSample(addSample(samples, start), end);
}

function buildMotionPlans(
  context: NormalizedTacticalScene,
  language: TacticalLanguageDocument,
  timing: TacticalTimingPlan
): MotionPlan[] {
  const gk = actorObject(context, language.statements.find((statement) => statement.id === 'stmt-pass-1')?.subjectId);
  const rcb = actorObject(context, statementById(language, 'stmt-receive-1')?.subjectId);
  const mcd = actorObject(context, statementById(language, 'stmt-receive-2')?.subjectId);
  const rb = actorObject(context, statementById(language, 'stmt-support-1')?.subjectId);
  const lcb =
    context.scene.objects.find((object) =>
      /central izquierdo|lcb/i.test(String(object.data?.name || object.data?.label || ''))
    ) || null;
  const ball = context.scene.objects.find((object) => object.type === 'ball') || null;
  const supportZone = context.zones.find((zone) => /objetivo|target/i.test(zone.label)) || context.zones[0] || null;
  const pass1Arrow = arrowByKind(context, 'pass', 0);
  const pass2Arrow = arrowByKind(context, 'pass', 1) || arrowByKind(context, 'trajectory', 0);
  const runArrow = arrowByKind(context, 'run', 0);

  const pass1Target = rcb ? objectCenter(rcb) : pass1Arrow ? pass1Arrow.end : gk ? objectCenter(gk) : { x: 0, y: 0 };
  const carryEndPoint =
    pass2Arrow?.start ||
    (rcb
      ? {
          x: objectCenter(rcb).x + 88,
          y: objectCenter(rcb).y + 26,
        }
      : pass1Target);
  const pass2Target = mcd ? objectCenter(mcd) : pass2Arrow?.end || carryEndPoint;
  const supportTarget = supportZone
    ? {
        x: supportZone.x + supportZone.width * 0.5,
        y: supportZone.y + supportZone.height * 0.5,
      }
    : runArrow?.end || { x: 0, y: 0 };

  const motionPlans: MotionPlan[] = [];

  if (gk) {
    motionPlans.push({
      objectId: gk.id,
      samples: ensureBoundarySamples(
        addSample(
          addSample(
            addSample([], toSnapshot(gk, 0)),
            toSnapshot(gk, 0.8)
          ),
          toSnapshot(gk, 10)
        ),
        gk,
        timing.duration
      ),
    });
  }

  if (rcb) {
    let samples: MotionSample[] = [];
    samples = addSample(samples, toSnapshot(rcb, 0));
    samples = addSample(samples, toSnapshot(rcb, 0.8));
    samples = addSample(
      samples,
      toSnapshot(rcb, 1.0, pointToObjectTopLeft(pass1Target, rcb))
    );
    samples = addSample(
      samples,
      toSnapshot(rcb, 3.0, pointToObjectTopLeft(carryEndPoint, rcb))
    );
    samples = addSample(
      samples,
      toSnapshot(rcb, 4.1, pointToObjectTopLeft(carryEndPoint, rcb))
    );
    samples = addSample(samples, toSnapshot(rcb, timing.duration, pointToObjectTopLeft(carryEndPoint, rcb)));
    motionPlans.push({ objectId: rcb.id, samples });
  }

  if (mcd) {
    let samples: MotionSample[] = [];
    samples = addSample(samples, toSnapshot(mcd, 0));
    samples = addSample(
      samples,
      toSnapshot(mcd, 4.1, pointToObjectTopLeft(pass2Target, mcd))
    );
    samples = addSample(
      samples,
      toSnapshot(mcd, timing.duration, pointToObjectTopLeft(pass2Target, mcd))
    );
    motionPlans.push({ objectId: mcd.id, samples });
  }

  if (rb) {
    let samples: MotionSample[] = [];
    samples = addSample(samples, toSnapshot(rb, 0));
    samples = addSample(
      samples,
      toSnapshot(rb, 5.5, pointToObjectTopLeft(supportTarget, rb))
    );
    samples = addSample(
      samples,
      toSnapshot(rb, timing.duration, pointToObjectTopLeft(supportTarget, rb))
    );
    motionPlans.push({ objectId: rb.id, samples });
  }

  if (lcb) {
    let samples: MotionSample[] = [];
    samples = addSample(samples, toSnapshot(lcb as SceneObject, 0));
    samples = addSample(samples, toSnapshot(lcb as SceneObject, timing.duration));
    motionPlans.push({ objectId: (lcb as SceneObject).id, samples });
  }

  if (ball) {
    let samples: MotionSample[] = [];
    const gkPoint = gk ? objectCenter(gk) : pass1Arrow?.start || objectCenter(ball);
    const rcbPoint = rcb ? objectCenter(rcb) : pass1Target;
    const mcdPoint = mcd ? objectCenter(mcd) : pass2Target;
    samples = addSample(samples, toSnapshot(ball, 0, pointToObjectTopLeft(gkPoint, ball)));
    samples = addSample(samples, toSnapshot(ball, 0.8, pointToObjectTopLeft(rcbPoint, ball)));
    samples = addSample(samples, toSnapshot(ball, 1.0, pointToObjectTopLeft(rcbPoint, ball)));
    samples = addSample(samples, toSnapshot(ball, 3.0, pointToObjectTopLeft(rcbPoint, ball)));
    samples = addSample(samples, toSnapshot(ball, 4.1, pointToObjectTopLeft(mcdPoint, ball)));
    samples = addSample(samples, toSnapshot(ball, timing.duration, pointToObjectTopLeft(mcdPoint, ball)));
    motionPlans.push({ objectId: ball.id, samples });
  }

  return motionPlans;
}

function sampleMotionPlan(plan: MotionPlan, time: number): MotionSample {
  const samples = [...plan.samples].sort((left, right) => left.time - right.time);
  if (!samples.length) {
    throw new Error(`Missing motion samples for ${plan.objectId}`);
  }
  if (time <= samples[0].time) {
    return samples[0];
  }
  const last = samples[samples.length - 1];
  if (time >= last.time) {
    return last;
  }
  const previous = [...samples].reverse().find((sample) => sample.time <= time) || samples[0];
  const next = samples.find((sample) => sample.time >= time && sample.time !== previous.time) || last;
  if (previous.time === next.time) {
    return previous;
  }
  const ratio = Math.min(1, Math.max(0, (time - previous.time) / Math.max(next.time - previous.time, 0.0001)));
  const lerp = (left: number, right: number) => left + (right - left) * ratio;
  return {
    ...previous,
    time,
    x: lerp(previous.x, next.x),
    y: lerp(previous.y, next.y),
    rotation: lerp(previous.rotation, next.rotation),
    width: lerp(previous.width, next.width),
    height: lerp(previous.height, next.height),
    zIndex: Math.round(lerp(previous.zIndex, next.zIndex)),
  };
}

function sampleSceneSnapshot(
  context: NormalizedTacticalScene,
  motionPlans: MotionPlan[],
  time: number,
  label?: string
): SceneTimelineKeyframe {
  const animatedIds = new Set(motionPlans.map((plan) => plan.objectId));
  const objects = context.scene.objects
    .filter((object) => animatedIds.has(object.id))
    .map((object) => {
      const plan = motionPlans.find((item) => item.objectId === object.id);
      const sample = plan ? sampleMotionPlan(plan, time) : null;
      return {
        id: object.id,
        type: object.type,
        layerId: object.layerId,
        x: sample?.x ?? object.x,
        y: sample?.y ?? object.y,
        width: sample?.width ?? object.width,
        height: sample?.height ?? object.height,
        rotation: sample?.rotation ?? object.rotation,
        scaleX: object.scaleX,
        scaleY: object.scaleY,
        style: deepClone(object.style),
        data: deepClone(object.data),
        visible: object.visible,
        locked: object.locked,
        zIndex: sample?.zIndex ?? object.zIndex,
      };
    });
  return {
    id: createUuid('scene-kf'),
    time,
    label,
    objectIds: objects.map((object) => object.id),
    objects,
  };
}

function buildTracks(context: NormalizedTacticalScene, motionPlans: MotionPlan[]): AnimationTrack[] {
  return motionPlans
    .map((plan) => {
      const object = context.scene.objects.find((item) => item.id === plan.objectId);
      if (!object) {
        return null;
      }
      const track = createAnimationTrack(object, {
        label: String(object.data?.label || object.data?.name || object.type),
      });
      plan.samples.forEach((sample, index) => {
        const snapshot = {
          id: object.id,
          type: sample.type,
          layerId: sample.layerId,
          x: sample.x,
          y: sample.y,
          width: sample.width,
          height: sample.height,
          rotation: sample.rotation,
          scaleX: object.scaleX,
          scaleY: object.scaleY,
          style: deepClone(sample.style),
          data: deepClone(sample.data),
          visible: sample.visible,
          locked: sample.locked,
          zIndex: sample.zIndex,
        };
        const keyframe = createTrackKeyframeFromSnapshot(snapshot, sample.time, track, {
          id: `${track.id}-${index}-${Math.round(sample.time * 100)}`,
          label: index === 0 ? 'Inicio' : undefined,
          interpolation: 'linear',
          easing: 'ease-in-out',
          source: 'manual',
        });
        track.keyframes = track.keyframes.filter((item) => item.time !== sample.time);
        track.keyframes.push(keyframe);
      });
      return sortTrackKeyframes(track);
    })
    .filter((track): track is AnimationTrack => Boolean(track));
}

function buildTimelineKeyframes(context: NormalizedTacticalScene, motionPlans: MotionPlan[], duration: number) {
  const times = new Set<number>([0, duration]);
  motionPlans.forEach((plan) => {
    plan.samples.forEach((sample) => times.add(sample.time));
  });
  return [...times]
    .sort((left, right) => left - right)
    .map((time, index) => sampleSceneSnapshot(context, motionPlans, time, index === 0 ? 'Inicio' : `t=${time.toFixed(1)}s`));
}

export function compileTacticalRecreation(scene: TacticalScene): TacticalCompilationResult {
  const context = normalizeTacticalScene(scene);
  const language = inferTacticalLanguage(context.scene);
  const plan = resolveTacticalPlan(language);
  const possessionResolution = resolvePossession(language, plan);
  const timing = planTacticalTiming(language, plan.executionOrder, 10);
  const motionPlans = buildMotionPlans(context, language, timing);
  const tracks = normalizeAnimationTracks(buildTracks(context, motionPlans));
  const timelineKeyframes = buildTimelineKeyframes(context, motionPlans, timing.duration);
  const sequences: AnimationSequence[] = [
    {
      id: 'sequence-build-up',
      name: 'Salida de balón',
      duration: timing.duration,
      transition: 0,
      comments: 'Generada automáticamente por Tactical Language MVP.',
      trackIds: tracks.map((track) => track.id),
      keyframeIds: tracks.flatMap((track) => track.keyframes.map((keyframe) => keyframe.id)),
      metadata: {
        createdAt: scene.metadata.createdAt,
        updatedAt: scene.metadata.updatedAt,
      },
    },
  ];

  const compiledScene: TacticalScene = normalizeAnimationTimeline({
    ...deepClone(scene),
    timeline: {
      duration: timing.duration,
      currentTime: 0,
      keyframes: timelineKeyframes,
      tracks,
      sequences,
      currentSequenceId: sequences[0]?.id || null,
    },
    metadata: {
      ...deepClone(scene.metadata),
      updatedAt: new Date().toISOString(),
    },
  });

  const validationIssues: TacticalValidationIssue[] = [];
  if (!language.actors.find((actor) => actor.role === 'goalkeeper')) {
    validationIssues.push({
      id: 'missing-goalkeeper',
      severity: 'error',
      code: 'missing_goalkeeper',
      message: 'No se detectó un portero válido para la salida de balón.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Inserta un portero o asigna un objeto con rol de portero.',
    });
  }
  if (!language.actors.find((actor) => actor.role === 'center-back-right')) {
    validationIssues.push({
      id: 'missing-central-right',
      severity: 'error',
      code: 'missing_center_back_right',
      message: 'No se detectó el central derecho.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Inserta o etiqueta un central derecho.',
    });
  }
  if (!language.actors.find((actor) => actor.role === 'midfielder')) {
    validationIssues.push({
      id: 'missing-midfielder',
      severity: 'error',
      code: 'missing_midfielder',
      message: 'No se detectó el mediocentro.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Inserta o etiqueta un mediocentro.',
    });
  }
  if (!language.actors.find((actor) => actor.role === 'fullback-right')) {
    validationIssues.push({
      id: 'missing-right-back',
      severity: 'error',
      code: 'missing_right_back',
      message: 'No se detectó el lateral derecho.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Inserta o etiqueta un lateral derecho.',
    });
  }
  if (!language.zones.length) {
    validationIssues.push({
      id: 'missing-target-zone',
      severity: 'error',
      code: 'missing_target_zone',
      message: 'No se detectó una zona objetivo.',
      entityIds: [],
      relatedStatementIds: [],
      suggestion: 'Añade una zona objetivo para finalizar la secuencia.',
    });
  }

  if (validationIssues.some((issue) => issue.severity === 'error')) {
    return {
    scene: compiledScene,
    language,
    plan,
    possession: possessionResolution.possession,
    timeline: compiledScene.timeline,
    tracks,
    keyframeCount: timelineKeyframes.length,
    validationIssues,
    };
  }

  return {
    scene: compiledScene,
    language,
    plan,
    possession: possessionResolution.possession,
    timeline: compiledScene.timeline,
    tracks,
    keyframeCount: timelineKeyframes.length,
    validationIssues: [...language.validationIssues, ...validationIssues],
  };
}
