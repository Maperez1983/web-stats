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
  const orientation = String(object.data.orientation || object.data.variant || 'front');
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
    new Konva.Rect({
      x: width * 0.17,
      y: height * 0.18,
      width: width * 0.66,
      height: height * 0.68,
      cornerRadius: Math.min(width, height) * 0.12,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 3,
      listening: false,
    })
  );
  group.add(
    new Konva.Line({
      points:
        orientation === 'side'
          ? [width * 0.22, height * 0.26, width * 0.12, height * 0.42, width * 0.22, height * 0.58]
          : [width * 0.18, height * 0.28, width / 2, height * 0.1, width * 0.82, height * 0.28],
      closed: true,
      fill: isGoalkeeper ? '#bbf7d0' : '#bfdbfe',
      stroke: objectStroke(object),
      strokeWidth: 1.2,
      opacity: 0.9,
      listening: false,
    })
  );
  group.add(
    new Konva.Circle({
      x: width / 2,
      y: height * 0.18,
      radius: Math.max(6, Math.min(width, height) * 0.12),
      fill: '#f8fafc',
      stroke: objectStroke(object),
      strokeWidth: 1.2,
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
  if (orientation !== 'front' && orientation !== 'back') {
    group.add(
      new Konva.Line({
        points: [width * 0.56, height * 0.28, width * 0.86, height * 0.52],
        stroke: objectStroke(object),
        strokeWidth: 1.8,
        listening: false,
      })
    );
  }
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

function renderGoal(object: SceneObject) {
  const group = renderRect(object, { cornerRadius: 6 });
  group.add(
    new Konva.Line({
      points: [8, object.height - 6, 16, 6, object.width - 16, 6, object.width - 8, object.height - 6],
      stroke: objectStroke(object),
      strokeWidth: 2,
      listening: false,
    })
  );
  return group;
}

function renderPoleLike(object: SceneObject, flag = false) {
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
    new Konva.Line({
      points: [object.width / 2, object.height, object.width / 2, 4],
      stroke: objectStroke(object),
      strokeWidth: 3,
      listening: false,
    })
  );
  if (flag) {
    group.add(
      new Konva.Line({
        points: [object.width / 2, 8, object.width - 6, 14, object.width / 2, 20],
        closed: true,
        fill: objectFill(object),
        stroke: objectStroke(object),
        strokeWidth: 2,
        listening: false,
      })
    );
  } else {
    group.add(
      new Konva.Rect({
        x: object.width / 2 - 6,
        y: object.height - 14,
        width: 12,
        height: 10,
        fill: objectFill(object),
        stroke: objectStroke(object),
        strokeWidth: 2,
        listening: false,
      })
    );
  }
  return group;
}

function renderPolygonZone(object: SceneObject) {
  const points =
    Array.isArray(object.data.points) && object.data.points.length >= 6
      ? object.data.points.map((value) => Number(value))
      : [0, object.height * 0.72, object.width * 0.2, object.height * 0.18, object.width * 0.55, 0, object.width, object.height * 0.25, object.width * 0.85, object.height, object.width * 0.15, object.height];
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
    new Konva.Line({
      points,
      closed: true,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      dash: object.style.dash,
      tension: object.type === 'zone-free' ? 0.4 : 0,
      listening: false,
    })
  );
  return group;
}

function renderSector(object: SceneObject) {
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
    new Konva.Line({
      points: [
        0,
        object.height,
        object.width * 0.25,
        18,
        object.width * 0.5,
        0,
        object.width * 0.75,
        18,
        object.width,
        object.height,
      ],
      closed: true,
      fill: objectFill(object),
      stroke: objectStroke(object),
      strokeWidth: object.style.strokeWidth ?? 2,
      listening: false,
    })
  );
  return group;
}

export function createKonvaNode(object: SceneObject): Konva.Group {
  switch (object.type) {
    case 'player':
    case 'player-home':
    case 'player-away':
    case 'player-joker':
    case 'coach':
    case 'referee':
    case 'injured-player':
    case 'ball-carrier':
    case 'numbered-player':
      return renderPlayer(object, false);
    case 'goalkeeper':
    case 'goalkeeper-home':
    case 'goalkeeper-away':
      return renderPlayer(object, true);
    case 'ball':
      return renderBall(object);
    case 'cone':
    case 'high-cone':
      return renderCone(object);
    case 'pole':
      return renderPoleLike(object);
    case 'flag':
      return renderPoleLike(object, true);
    case 'hoop':
      return renderCircle({ ...object, style: { ...object.style, fill: 'rgba(0,0,0,0)' } });
    case 'mini-goal':
      return renderMiniGoal(object);
    case 'goal':
      return renderGoal(object);
    case 'bench':
    case 'bib':
      return renderRect(object, { cornerRadius: 10 });
    case 'marker':
      return renderCircle({
        ...object,
        width: 18,
        height: 18,
        style: { ...object.style, fill: objectFill(object), stroke: objectStroke(object) },
      });
    case 'arrow-straight':
    case 'arrow-pass':
    case 'arrow-run':
      return renderArrowLike(object, false, false);
    case 'arrow-curved':
    case 'trajectory':
      return renderArrowLike(object, true, false);
    case 'arrow-segmented':
    case 'arrow-double':
      return renderArrowLike(object, false, false);
    case 'line-dashed':
    case 'line':
      return renderArrowLike(object, false, true);
    case 'zone-rect':
    case 'lane':
    case 'stripe-h':
    case 'stripe-v':
      return renderRect(object, { cornerRadius: 18 });
    case 'zone-circle':
    case 'zone-ellipse':
      return renderCircle(object);
    case 'zone-polygon':
    case 'zone-free':
      return renderPolygonZone(object);
    case 'sector':
      return renderSector(object);
    case 'text':
      return renderText(object, false);
    case 'label':
      return renderText(object, true);
    default:
      return renderRect(object, { cornerRadius: 12 });
  }
}
