import type { TacticalScene } from '../core/sceneSchema';

export type PitchRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function getPitchRect(scene: TacticalScene): PitchRect {
  const { width, height, padding } = scene.canvas;
  const availableWidth = Math.max(1, width - padding * 2);
  const availableHeight = Math.max(1, height - padding * 2);
  const pitchRatio = Math.max(0.1, scene.pitch.width / Math.max(0.1, scene.pitch.height));
  let rectWidth = availableWidth;
  let rectHeight = rectWidth / pitchRatio;
  if (rectHeight > availableHeight) {
    rectHeight = availableHeight;
    rectWidth = rectHeight * pitchRatio;
  }
  return {
    x: padding + (availableWidth - rectWidth) / 2,
    y: padding + (availableHeight - rectHeight) / 2,
    width: rectWidth,
    height: rectHeight,
  };
}
