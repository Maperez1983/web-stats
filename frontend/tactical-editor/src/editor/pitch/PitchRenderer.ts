import Konva from 'konva';
import type { TacticalScene } from '../core/sceneSchema';

export type PitchRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function getPitchRect(scene: TacticalScene): PitchRect {
  const { width, height, padding } = scene.canvas;
  if (scene.pitch.type === 'half') {
    return { x: padding, y: padding, width: width - padding * 2, height: height - padding * 2 };
  }
  if (scene.pitch.type === 'attacking-third') {
    return { x: padding, y: padding, width: width - padding * 2, height: height - padding * 2 };
  }
  return { x: padding, y: padding, width: width - padding * 2, height: height - padding * 2 };
}

function addGoal(layer: Konva.Layer, rect: PitchRect, side: 'left' | 'right') {
  const goalDepth = 14;
  const goalWidth = rect.height * 0.13;
  const y = rect.y + rect.height / 2 - goalWidth / 2;
  const x = side === 'left' ? rect.x - goalDepth : rect.x + rect.width;
  layer.add(
    new Konva.Rect({
      x,
      y,
      width: goalDepth,
      height: goalWidth,
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
}

function addFullPitch(layer: Konva.Layer, rect: PitchRect) {
  const midX = rect.x + rect.width / 2;
  const boxDepth = rect.width * 0.165;
  const boxHeight = rect.height * 0.56;
  const smallDepth = rect.width * 0.06;
  const smallHeight = rect.height * 0.24;
  const centerY = rect.y + rect.height / 2;
  const arcRadius = rect.height * 0.145;

  layer.add(
    new Konva.Line({
      points: [midX, rect.y, midX, rect.y + rect.height],
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
  layer.add(
    new Konva.Circle({
      x: midX,
      y: centerY,
      radius: rect.height * 0.14,
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
  layer.add(
    new Konva.Circle({ x: midX, y: centerY, radius: 3, fill: '#f8fafc', listening: false })
  );

  [
    { x: rect.x, penaltyX: rect.x + rect.width * 0.11 },
    { x: rect.x + rect.width - boxDepth, penaltyX: rect.x + rect.width - rect.width * 0.11 },
  ].forEach((side, index) => {
    layer.add(
      new Konva.Rect({
        x: side.x,
        y: centerY - boxHeight / 2,
        width: boxDepth,
        height: boxHeight,
        stroke: '#f8fafc',
        strokeWidth: 2,
        listening: false,
      })
    );
    layer.add(
      new Konva.Rect({
        x: index === 0 ? rect.x : rect.x + rect.width - smallDepth,
        y: centerY - smallHeight / 2,
        width: smallDepth,
        height: smallHeight,
        stroke: '#f8fafc',
        strokeWidth: 2,
        listening: false,
      })
    );
    layer.add(
      new Konva.Circle({
        x: side.penaltyX,
        y: centerY,
        radius: 3,
        fill: '#f8fafc',
        listening: false,
      })
    );
    layer.add(
      new Konva.Arc({
        x: side.penaltyX,
        y: centerY,
        innerRadius: arcRadius,
        outerRadius: arcRadius,
        angle: 106,
        rotation: index === 0 ? -53 : 127,
        stroke: '#f8fafc',
        strokeWidth: 2,
        listening: false,
      })
    );
  });

  addGoal(layer, rect, 'left');
  addGoal(layer, rect, 'right');
}

function addHalfPitch(layer: Konva.Layer, rect: PitchRect) {
  const goalLineX = rect.x;
  const boxDepth = rect.width * 0.26;
  const boxHeight = rect.height * 0.56;
  const smallDepth = rect.width * 0.1;
  const smallHeight = rect.height * 0.24;
  const centerY = rect.y + rect.height / 2;
  const penaltyX = rect.x + rect.width * 0.17;
  const arcRadius = rect.height * 0.145;
  layer.add(
    new Konva.Rect({
      x: goalLineX,
      y: centerY - boxHeight / 2,
      width: boxDepth,
      height: boxHeight,
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
  layer.add(
    new Konva.Rect({
      x: goalLineX,
      y: centerY - smallHeight / 2,
      width: smallDepth,
      height: smallHeight,
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
  layer.add(
    new Konva.Circle({ x: penaltyX, y: centerY, radius: 3, fill: '#f8fafc', listening: false })
  );
  layer.add(
    new Konva.Arc({
      x: penaltyX,
      y: centerY,
      innerRadius: arcRadius,
      outerRadius: arcRadius,
      angle: 106,
      rotation: -53,
      stroke: '#f8fafc',
      strokeWidth: 2,
      listening: false,
    })
  );
  layer.add(
    new Konva.Line({
      points: [rect.x + rect.width * 0.5, rect.y, rect.x + rect.width * 0.5, rect.y + rect.height],
      stroke: 'rgba(248,250,252,0.35)',
      strokeWidth: 2,
      dash: [12, 12],
      listening: false,
    })
  );
  addGoal(layer, rect, 'left');
}

function addAttackingThird(layer: Konva.Layer, rect: PitchRect) {
  addHalfPitch(layer, rect);
  layer.add(
    new Konva.Line({
      points: [
        rect.x + rect.width * 0.66,
        rect.y,
        rect.x + rect.width * 0.66,
        rect.y + rect.height,
      ],
      stroke: 'rgba(248,250,252,0.35)',
      strokeWidth: 2,
      dash: [12, 12],
      listening: false,
    })
  );
}

export function drawPitchLayer(layer: Konva.Layer, scene: TacticalScene) {
  layer.destroyChildren();
  const rect = getPitchRect(scene);
  layer.add(
    new Konva.Rect({
      x: 0,
      y: 0,
      width: scene.canvas.width,
      height: scene.canvas.height,
      fillLinearGradientStartPoint: { x: 0, y: 0 },
      fillLinearGradientEndPoint: { x: 0, y: scene.canvas.height },
      fillLinearGradientColorStops: [0, '#0b3d22', 1, '#0a2e1b'],
      listening: false,
    })
  );
  layer.add(
    new Konva.Rect({
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      stroke: '#f8fafc',
      strokeWidth: 2.5,
      listening: false,
    })
  );

  const stripes = 10;
  const stripeWidth = rect.width / stripes;
  for (let index = 0; index < stripes; index += 1) {
    layer.add(
      new Konva.Rect({
        x: rect.x + stripeWidth * index,
        y: rect.y,
        width: stripeWidth,
        height: rect.height,
        fill: index % 2 === 0 ? 'rgba(255,255,255,0.045)' : 'rgba(255,255,255,0.015)',
        listening: false,
      })
    );
  }

  layer.add(
    new Konva.Rect({
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      stroke: 'rgba(255,255,255,0.08)',
      strokeWidth: 6,
      listening: false,
    })
  );

  if (scene.pitch.type === 'half') {
    addHalfPitch(layer, rect);
  } else if (scene.pitch.type === 'attacking-third') {
    addAttackingThird(layer, rect);
  } else {
    addFullPitch(layer, rect);
  }

  [
    [rect.x, rect.y],
    [rect.x + rect.width, rect.y],
    [rect.x, rect.y + rect.height],
    [rect.x + rect.width, rect.y + rect.height],
  ].forEach(([x, y]) => {
    layer.add(
      new Konva.Arc({
        x,
        y,
        innerRadius: 12,
        outerRadius: 12,
        angle: 90,
        rotation: x === rect.x ? (y === rect.y ? 0 : 270) : y === rect.y ? 90 : 180,
        stroke: '#f8fafc',
        strokeWidth: 2,
        listening: false,
      })
    );
  });

  layer.batchDraw();
}
