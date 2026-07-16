import Konva from 'konva';
import type { SceneObject } from '../core/sceneSchema';

function textColor(object: SceneObject): string {
  return String(object.style.textColor || '#f8fafc');
}

function objectStroke(object: SceneObject): string {
  return String(object.style.stroke || '#e2e8f0');
}

function objectFill(object: SceneObject): string {
  return String(object.style.fill || 'rgba(255,255,255,0.08)');
}

function renderPlayer(object: SceneObject, isGoalkeeper: boolean) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  const width = object.width;
  const height = object.height;
  group.add(
    new Konva.Circle({
      x: width / 2,
      y: height / 2,
      radius: Math.min(width, height) / 2,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 3,
      listening: false,
    })
  );
  group.add(
    new Konva.Line({
      points: [width / 2, -8, width / 2 + 10, 4, width / 2 - 10, 4],
      closed: true,
      fill: isGoalkeeper ? '#bbf7d0' : '#bfdbfe',
      opacity: 0.9,
      listening: false,
    })
  );
  group.add(
    new Konva.Text({
      x: 0,
      y: height / 2 - 9,
      width,
      align: 'center',
      text: String(object.data.number || ''),
      fontSize: object.style.fontSize ?? 15,
      fontStyle: 'bold',
      fill: textColor(object),
      listening: false,
    })
  );
  if (object.data.name) {
    group.add(
      new Konva.Text({
        x: width / 2 - 50,
        y: height + 6,
        width: 100,
        align: 'center',
        text: String(object.data.name || ''),
        fontSize: 13,
        fill: '#e2e8f0',
        listening: false,
      })
    );
  }
  return group;
}

function renderBall(object: SceneObject) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  const radius = Math.min(object.width, object.height) / 2;
  group.add(
    new Konva.Circle({
      x: radius,
      y: radius,
      radius,
      fill: '#f8fafc',
      stroke: '#0f172a',
      strokeWidth: 2,
      listening: false,
    })
  );
  group.add(
    new Konva.Line({
      points: [
        radius * 0.4,
        radius,
        radius,
        radius * 0.35,
        radius * 1.6,
        radius,
        radius,
        radius * 1.65,
        radius * 0.4,
        radius,
      ],
      closed: true,
      stroke: '#0f172a',
      strokeWidth: 1.5,
      listening: false,
    })
  );
  return group;
}

function renderCone(object: SceneObject) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  group.add(
    new Konva.RegularPolygon({
      x: object.width / 2,
      y: object.height / 2,
      sides: 3,
      radius: Math.max(object.width, object.height) / 2,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      rotation: -90,
      listening: false,
    })
  );
  return group;
}

function renderRect(object: SceneObject, config?: Partial<Konva.RectConfig>) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  group.add(
    new Konva.Rect({
      x: 0,
      y: 0,
      width: object.width,
      height: object.height,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      listening: false,
      ...config,
    })
  );
  return group;
}

function renderCircle(object: SceneObject) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  group.add(
    new Konva.Ellipse({
      x: object.width / 2,
      y: object.height / 2,
      radiusX: object.width / 2,
      radiusY: object.height / 2,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      listening: false,
    })
  );
  return group;
}

function renderText(object: SceneObject, circle = false) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  if (circle) {
    group.add(
      new Konva.Circle({
        x: object.width / 2,
        y: object.height / 2,
        radius: Math.min(object.width, object.height) / 2,
        fill: objectFill(object),
        stroke: objectStroke(object),
        strokeWidth: object.style.strokeWidth ?? 2,
      })
    );
  }
  group.add(
    new Konva.Text({
      x: 0,
      y: circle ? object.height / 2 - (object.style.fontSize ?? 16) / 2 : 0,
      width: object.width,
      height: object.height,
      align: 'center',
      verticalAlign: circle ? 'middle' : 'top',
      text: String(object.data.label || ''),
      fontSize: object.style.fontSize ?? 18,
      fontStyle: String(object.style.fontWeight || '700'),
      fill: textColor(object),
      listening: false,
    })
  );
  return group;
}

function renderArrowLike(object: SceneObject, curved = false, dashed = false) {
  const points = Array.isArray(object.data.points)
    ? object.data.points.map((value) => Number(value))
    : [0, object.height / 2, object.width, object.height / 2];
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  group.add(
    new Konva.Arrow({
      x: 0,
      y: 0,
      points,
      pointerLength: dashed ? 0 : 14,
      pointerWidth: dashed ? 0 : 12,
      stroke: objectStroke(object),
      fill: objectFill(object),
      strokeWidth: object.style.strokeWidth ?? 4,
      dash: dashed ? object.style.dash || [10, 8] : undefined,
      bezier: curved,
      listening: false,
    })
  );
  return group;
}

function renderMiniGoal(object: SceneObject) {
  const group = new Konva.Group({
    x: object.x,
    y: object.y,
    rotation: object.rotation,
    scaleX: object.scaleX,
    scaleY: object.scaleY,
    opacity: object.style.opacity ?? 1,
    visible: object.visible,
    draggable: !object.locked,
    name: object.id,
  });
  group.add(
    new Konva.Rect({
      x: 0,
      y: 0,
      width: object.width,
      height: object.height,
      fill: 'rgba(255,255,255,0.04)',
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      listening: false,
    })
  );
  group.add(
    new Konva.Line({
      points: [
        0,
        object.height,
        object.width * 0.2,
        object.height * 0.4,
        object.width * 0.8,
        object.height * 0.4,
        object.width,
        object.height,
      ],
      stroke: objectStroke(object),
      strokeWidth: 1.5,
      dash: [6, 4],
      listening: false,
    })
  );
  return group;
}

export function createKonvaNode(object: SceneObject): Konva.Group {
  switch (object.type) {
    case 'player':
      return renderPlayer(object, false);
    case 'goalkeeper':
      return renderPlayer(object, true);
    case 'ball':
      return renderBall(object);
    case 'cone':
      return renderCone(object);
    case 'pole':
      return renderRect(object, { cornerRadius: 6 });
    case 'hoop':
      return renderCircle({ ...object, style: { ...object.style, fill: 'rgba(0,0,0,0)' } });
    case 'mini-goal':
      return renderMiniGoal(object);
    case 'arrow-straight':
      return renderArrowLike(object, false, false);
    case 'arrow-curved':
      return renderArrowLike(object, true, false);
    case 'line-dashed':
      return renderArrowLike(object, false, true);
    case 'zone-rect':
      return renderRect(object, { cornerRadius: 18 });
    case 'zone-circle':
      return renderCircle(object);
    case 'text':
      return renderText(object, false);
    case 'label':
      return renderText(object, true);
    default:
      return renderRect(object, { cornerRadius: 12 });
  }
}
