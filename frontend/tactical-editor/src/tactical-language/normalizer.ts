import { deepClone, type SceneObject, type TacticalScene } from '../editor/core/sceneSchema';
import type {
  TacticalActorRef,
  TacticalArrowRef,
  TacticalSceneInput,
  TacticalZoneRef,
} from './types';

type NormalizedTacticalScene = {
  scene: TacticalScene;
  actors: TacticalActorRef[];
  arrows: TacticalArrowRef[];
  zones: TacticalZoneRef[];
  ballId: string | null;
};

function textValue(object: SceneObject): string {
  return String(
    object.data?.name || object.data?.label || object.data?.role || object.data?.assetId || object.type
  )
    .trim()
    .toLowerCase();
}

function objectCenter(object: SceneObject) {
  return {
    x: object.x + object.width * object.scaleX * 0.5,
    y: object.y + object.height * object.scaleY * 0.5,
  };
}

function isArrowObject(object: SceneObject): boolean {
  return (
    object.type === 'arrow-straight' ||
    object.type === 'arrow-curved' ||
    object.type === 'arrow-segmented' ||
    object.type === 'arrow-double' ||
    object.type === 'arrow-pass' ||
    object.type === 'arrow-run' ||
    object.type === 'trajectory' ||
    object.type === 'line' ||
    object.type === 'line-dashed'
  );
}

function isZoneObject(object: SceneObject): boolean {
  return (
    object.type === 'zone-rect' ||
    object.type === 'zone-circle' ||
    object.type === 'zone-ellipse' ||
    object.type === 'zone-polygon' ||
    object.type === 'zone-free' ||
    object.type === 'lane' ||
    object.type === 'stripe-h' ||
    object.type === 'stripe-v' ||
    object.type === 'sector'
  );
}

function isPlayerLike(object: SceneObject): boolean {
  return (
    object.type === 'player' ||
    object.type === 'goalkeeper' ||
    object.type === 'player-home' ||
    object.type === 'player-away' ||
    object.type === 'player-joker' ||
    object.type === 'goalkeeper-home' ||
    object.type === 'goalkeeper-away' ||
    object.type === 'coach' ||
    object.type === 'referee' ||
    object.type === 'injured-player' ||
    object.type === 'ball-carrier' ||
    object.type === 'numbered-player'
  );
}

function isBallObject(object: SceneObject): boolean {
  return object.type === 'ball' || String(object.data?.assetId || '').includes('ball.standard');
}

function inferRole(object: SceneObject): string {
  const value = textValue(object);
  if (value.includes('goalkeeper') || value.includes('portero')) return 'goalkeeper';
  if (value.includes('central derecho') || value.includes('rcb')) return 'center-back-right';
  if (value.includes('central izquierdo') || value.includes('lcb')) return 'center-back-left';
  if (value.includes('mediocentro') || value.includes('mcd')) return 'midfielder';
  if (value.includes('lateral derecho') || value.includes('rb')) return 'fullback-right';
  if (value.includes('lateral izquierdo') || value.includes('lb')) return 'fullback-left';
  if (value.includes('interior derecho') || value.includes('ir')) return 'inside-right';
  if (value.includes('interior izquierdo') || value.includes('il')) return 'inside-left';
  if (value.includes('delantero') || value.includes('dc')) return 'attacker';
  if (value.includes('con balón') || value.includes('ball-carrier')) return 'ball-carrier';
  if (value.includes('comodín') || value.includes('joker')) return 'joker';
  return object.type;
}

function pointsFromObject(object: SceneObject) {
  const points = Array.isArray(object.data?.points) ? object.data.points.map((value) => Number(value)) : [];
  const path: Array<{ x: number; y: number }> = [];
  for (let index = 0; index < points.length; index += 2) {
    const x = Number(points[index]);
    const y = Number(points[index + 1]);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      path.push({ x: object.x + x, y: object.y + y });
    }
  }
  if (!path.length) {
    path.push(objectCenter(object));
  }
  return path;
}

function classifyArrow(object: SceneObject): 'pass' | 'run' | 'trajectory' | 'line' {
  if (object.type === 'arrow-pass') return 'pass';
  if (object.type === 'arrow-run') return 'run';
  if (object.type === 'trajectory') return 'trajectory';
  return 'line';
}

function actorFromObject(object: SceneObject): TacticalActorRef {
  return {
    id: object.id,
    objectId: object.id,
    kind: isBallObject(object) ? 'ball' : inferRole(object) === 'goalkeeper' ? 'goalkeeper' : 'player',
    role: inferRole(object),
    team: (object.data?.team as TacticalActorRef['team']) || 'home',
    label: String(object.data?.name || object.data?.label || object.data?.number || object.type),
    layerId: object.layerId,
    x: object.x,
    y: object.y,
    width: object.width,
    height: object.height,
    assetId: typeof object.data?.assetId === 'string' ? object.data.assetId : null,
    objectType: object.type,
  };
}

function zoneFromObject(object: SceneObject): TacticalZoneRef {
  const label = String(object.data?.label || object.data?.name || object.data?.variant || object.type);
  const lower = label.toLowerCase();
  return {
    id: object.id,
    objectId: object.id,
    label,
    kind: lower.includes('objetivo') || lower.includes('target')
      ? 'objective'
      : lower.includes('lane') || lower.includes('carril')
        ? 'lane'
        : lower.includes('support') || lower.includes('apoyo')
          ? 'support'
          : 'area',
    layerId: object.layerId,
    x: object.x,
    y: object.y,
    width: object.width,
    height: object.height,
  };
}

function arrowFromObject(object: SceneObject): TacticalArrowRef {
  const path = pointsFromObject(object);
  return {
    id: object.id,
    objectId: object.id,
    kind: classifyArrow(object),
    label: String(object.data?.label || object.data?.variant || object.type),
    layerId: object.layerId,
    start: path[0] || objectCenter(object),
    end: path[path.length - 1] || objectCenter(object),
    points: path,
  };
}

export function normalizeTacticalScene(input: TacticalSceneInput): NormalizedTacticalScene {
  const scene = deepClone(input);
  const actors = scene.objects.filter((object) => isPlayerLike(object) || isBallObject(object)).map(actorFromObject);
  const arrows = scene.objects.filter((object) => isArrowObject(object)).map(arrowFromObject);
  const zones = scene.objects.filter((object) => isZoneObject(object)).map(zoneFromObject);
  const ballId = actors.find((actor) => actor.kind === 'ball')?.objectId || null;
  return {
    scene,
    actors,
    arrows,
    zones,
    ballId,
  };
}

export function findActorByRole(
  context: NormalizedTacticalScene,
  role: string,
  fallback?: TacticalActorRef | null
): TacticalActorRef | null {
  return context.actors.find((actor) => actor.role === role) || fallback || null;
}

export function findActorByLabelLike(
  context: NormalizedTacticalScene,
  labels: string[]
): TacticalActorRef | null {
  const lowered = labels.map((label) => label.toLowerCase());
  return (
    context.actors.find((actor) =>
      lowered.some((label) => actor.label.toLowerCase().includes(label))
    ) || null
  );
}

export function getObjectById(scene: TacticalScene, objectId: string): SceneObject | null {
  return scene.objects.find((object) => object.id === objectId) || null;
}

export function getActorObject(context: NormalizedTacticalScene, actorId: string): SceneObject | null {
  return getObjectById(context.scene, actorId);
}

export function arrowVector(arrow: TacticalArrowRef) {
  return {
    dx: arrow.end.x - arrow.start.x,
    dy: arrow.end.y - arrow.start.y,
  };
}

export type { NormalizedTacticalScene };
