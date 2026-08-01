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
  TacticalArrowRef,
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

function objectTopLeft(object: SceneObject, center: { x: number; y: number }) {
  return pointToObjectTopLeft(center, object);
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

function zoneCenter(context: NormalizedTacticalScene, zoneId?: string | null) {
  if (!zoneId) {
    return null;
  }
  const zone = context.zones.find((item) => item.id === zoneId || item.objectId === zoneId) || null;
  if (!zone) {
    return null;
  }
  return {
    x: zone.x + zone.width * 0.5,
    y: zone.y + zone.height * 0.5,
  };
}

function actorCenter(context: NormalizedTacticalScene, actorId?: string | null) {
  const object = actorObject(context, actorId);
  return object ? objectCenter(object) : null;
}

function statementDuration(timing: TacticalTimingPlan, statementId: string, fallback: number) {
  return timing.windows.find((window) => window.statementId === statementId)?.duration || fallback;
}

function targetPointForStatement(
  context: NormalizedTacticalScene,
  statement: TacticalStatement,
  currentActorPositions: Map<string, { x: number; y: number }>
) {
  if (statement.target?.kind === 'actor') {
    const target = actorObject(context, statement.target.actorId || statement.target.objectId || null);
    if (target) {
      return objectCenter(target);
    }
  }
  if (statement.target?.kind === 'zone') {
    const point = zoneCenter(context, statement.target.zoneId || statement.target.objectId || null);
    if (point) {
      return point;
    }
  }
  if (statement.target?.kind === 'ball') {
    const ball = context.scene.objects.find((object) => object.type === 'ball') || null;
    if (ball) {
      return objectCenter(ball);
    }
  }
  const originArrow = statement.originObjectIds
    .map((objectId) => context.arrows.find((arrow) => arrow.objectId === objectId))
    .find((arrow): arrow is TacticalArrowRef => Boolean(arrow));
  if (originArrow) {
    return statement.verb === 'RUN' || statement.verb === 'SUPPORT' || statement.verb === 'PRESS'
      ? originArrow.end
      : originArrow.end;
  }
  const subject = actorObject(context, statement.subjectId);
  const subjectPosition = subject ? currentActorPositions.get(subject.id) || objectCenter(subject) : null;
  if (!subjectPosition) {
    return { x: 0, y: 0 };
  }
  const distance = statement.verb === 'CARRY' ? 120 : statement.verb === 'RUN' ? 100 : statement.verb === 'PRESS' ? 80 : 72;
  const verticalOffset = statement.verb === 'SUPPORT' ? -30 : statement.verb === 'PRESS' ? 24 : 0;
  return {
    x: subjectPosition.x + distance,
    y: subjectPosition.y + verticalOffset,
  };
}

function defaultBallStartPoint(
  context: NormalizedTacticalScene,
  carrierId: string | undefined,
  currentActorPositions: Map<string, { x: number; y: number }>
) {
  const carrier = actorObject(context, carrierId || null);
  if (carrier) {
    return currentActorPositions.get(carrier.id) || objectCenter(carrier);
  }
  const ball = context.scene.objects.find((object) => object.type === 'ball');
  return ball ? objectCenter(ball) : { x: 0, y: 0 };
}

function ensureMotionPlan(plans: Map<string, MotionPlan>, object: SceneObject): MotionPlan {
  const current = plans.get(object.id);
  if (current) {
    return current;
  }
  const plan: MotionPlan = {
    objectId: object.id,
    samples: [toSnapshot(object, 0), toSnapshot(object, 0)],
  };
  plans.set(object.id, plan);
  return plan;
}

function addPlanSample(
  plans: Map<string, MotionPlan>,
  object: SceneObject,
  time: number,
  position?: { x: number; y: number },
  overrides?: Partial<MotionSample>
) {
  const plan = ensureMotionPlan(plans, object);
  const snapshot = toSnapshot(object, time, position);
  const next = {
    ...snapshot,
    ...overrides,
    time,
  };
  plan.samples = addSample(plan.samples, next);
  return next;
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
  const motionPlans = new Map<string, MotionPlan>();
  const actorObjects = context.actors
    .filter((actor) => actor.kind !== 'ball')
    .map((actor) => actorObject(context, actor.id))
    .filter((object): object is SceneObject => Boolean(object));
  const ball = context.scene.objects.find((object) => object.type === 'ball') || null;
  const duration = Math.max(0.001, timing.duration);
  const ballCarrierId = language.possession.carrierId || context.actors.find((actor) => actor.kind === 'goalkeeper')?.id;
  const currentActorPositions = new Map<string, { x: number; y: number }>();
  actorObjects.forEach((object) => {
    currentActorPositions.set(object.id, objectCenter(object));
    ensureMotionPlan(motionPlans, object);
  });
  if (ball) {
    ensureMotionPlan(motionPlans, ball);
  }

  const fallbackBallCarrier = ballCarrierId && actorObject(context, ballCarrierId) ? ballCarrierId : null;
  let activeBallCarrierId: string | null | undefined = fallbackBallCarrier;
  const statementWindows = new Map(timing.windows.map((window) => [window.statementId, window] as const));
  const statements = language.statements.filter((statement) => statement.verb !== 'BUILD_UP' && statement.verb !== 'PROGRESSION' && statement.verb !== 'SEQUENCE');

  const registerStaticBoundary = (object: SceneObject) => {
    const center = currentActorPositions.get(object.id) || objectCenter(object);
    addPlanSample(motionPlans, object, 0, objectTopLeft(object, center));
    addPlanSample(motionPlans, object, duration, objectTopLeft(object, center));
  };

  actorObjects.forEach(registerStaticBoundary);
  if (ball) {
    const center = ballCarrierId ? currentActorPositions.get(ballCarrierId) || objectCenter(ball) : objectCenter(ball);
    addPlanSample(motionPlans, ball, 0, objectTopLeft(ball, center));
    addPlanSample(motionPlans, ball, duration, objectTopLeft(ball, center));
  }

  statements.forEach((statement, index) => {
    const window = statementWindows.get(statement.id);
    const start = window?.start ?? Math.max(0, index * 0.75);
    const end = window?.end ?? Math.min(duration, start + statementDuration(timing, statement.id, 0.5));
    const subject = actorObject(context, statement.subjectId);
    const subjectPlan = subject ? motionPlans.get(subject.id) : null;
    const targetPoint = targetPointForStatement(context, statement, currentActorPositions);

    if (statement.verb === 'PASS' || statement.verb === 'RETURN_PASS') {
      const carrier = subject || (activeBallCarrierId ? actorObject(context, activeBallCarrierId) : null) || ball;
      const ballObject = ball || carrier;
      if (ballObject) {
        const startPoint = carrier ? currentActorPositions.get(carrier.id) || objectCenter(carrier) : objectCenter(ballObject);
        const receiveActor = statement.target?.kind === 'actor'
          ? actorObject(context, statement.target.actorId || statement.target.objectId || null)
          : statement.result.ballCarrierId
            ? actorObject(context, statement.result.ballCarrierId)
            : null;
        const finishPoint = receiveActor
          ? currentActorPositions.get(receiveActor.id) || objectCenter(receiveActor)
          : targetPoint;
        addPlanSample(motionPlans, ballObject, start, startPoint, {
          style: deepClone(ballObject.style),
          data: deepClone(ballObject.data),
        });
        addPlanSample(motionPlans, ballObject, end, finishPoint, {
          style: deepClone(ballObject.style),
          data: deepClone(ballObject.data),
        });
        if (receiveActor) {
          const receiveCenter = currentActorPositions.get(receiveActor.id) || objectCenter(receiveActor);
          addPlanSample(motionPlans, receiveActor, end, objectTopLeft(receiveActor, receiveCenter));
          currentActorPositions.set(receiveActor.id, receiveCenter);
        }
        activeBallCarrierId = receiveActor?.id || statement.result.ballCarrierId || statement.target?.actorId || activeBallCarrierId;
      }
      return;
    }

    if (statement.verb === 'RECEIVE') {
      if (subject && subjectPlan) {
        const position = currentActorPositions.get(subject.id) || objectCenter(subject);
        addPlanSample(motionPlans, subject, end, objectTopLeft(subject, position));
        activeBallCarrierId = subject.id;
      }
      if (ball && subject) {
        const position = currentActorPositions.get(subject.id) || objectCenter(subject);
        addPlanSample(motionPlans, ball, end, objectTopLeft(ball, position));
      }
      return;
    }

    if (statement.verb === 'CARRY') {
      if (subject && subjectPlan) {
        const startPoint = currentActorPositions.get(subject.id) || objectCenter(subject);
        const finishPoint = targetPoint;
        addPlanSample(motionPlans, subject, start, objectTopLeft(subject, startPoint));
        addPlanSample(motionPlans, subject, end, objectTopLeft(subject, finishPoint));
        currentActorPositions.set(subject.id, finishPoint);
        activeBallCarrierId = subject.id;
        if (ball) {
          addPlanSample(motionPlans, ball, start, objectTopLeft(ball, startPoint));
          addPlanSample(motionPlans, ball, end, objectTopLeft(ball, finishPoint));
        }
      }
      return;
    }

    if (statement.verb === 'RUN' || statement.verb === 'SUPPORT' || statement.verb === 'PRESS' || statement.verb === 'CREATE_SPACE' || statement.verb === 'OCCUPY_SPACE') {
      if (subject && subjectPlan) {
        const startPoint = currentActorPositions.get(subject.id) || objectCenter(subject);
        const finishPoint = targetPoint;
        addPlanSample(motionPlans, subject, start, objectTopLeft(subject, startPoint));
        addPlanSample(motionPlans, subject, end, objectTopLeft(subject, finishPoint));
        currentActorPositions.set(subject.id, finishPoint);
      }
      return;
    }

    if (statement.verb === 'HOLD') {
      if (subject && subjectPlan) {
        const holdPoint = currentActorPositions.get(subject.id) || objectCenter(subject);
        addPlanSample(motionPlans, subject, start, objectTopLeft(subject, holdPoint));
        addPlanSample(motionPlans, subject, end, objectTopLeft(subject, holdPoint));
      }
      return;
    }

    if (statement.verb === 'SHOOT') {
      if (subject && subjectPlan) {
        const releasePoint = currentActorPositions.get(subject.id) || objectCenter(subject);
        addPlanSample(motionPlans, subject, start, objectTopLeft(subject, releasePoint));
      }
      if (ball) {
        const releasePoint = subject ? currentActorPositions.get(subject.id) || objectCenter(subject) : objectCenter(ball);
        const finishPoint = statement.target?.kind === 'zone' ? targetPoint : targetPoint;
        addPlanSample(motionPlans, ball, start, objectTopLeft(ball, releasePoint));
        addPlanSample(motionPlans, ball, end, objectTopLeft(ball, finishPoint));
      }
      activeBallCarrierId = undefined;
      return;
    }
  });

  const plans = [...motionPlans.values()].map((plan) => ({
    ...plan,
    samples: plan.samples
      .filter((sample, sampleIndex, array) => sampleIndex === 0 || sample.time !== array[sampleIndex - 1].time)
      .sort((left, right) => left.time - right.time),
  }));

  return plans;
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

export function compileTacticalRecreation(
  scene: TacticalScene,
  languageOverride?: TacticalLanguageDocument
): TacticalCompilationResult {
  const context = normalizeTacticalScene(scene);
  const language = languageOverride || inferTacticalLanguage(context.scene);
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
      severity: 'warning',
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
      severity: 'warning',
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
      severity: 'warning',
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
      severity: 'warning',
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
      severity: 'warning',
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
