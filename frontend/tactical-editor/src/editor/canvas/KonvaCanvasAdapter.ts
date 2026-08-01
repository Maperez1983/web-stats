import type { CanvasAdapter, CanvasAdapterDependencies } from './CanvasAdapter';
import { createCanvasAdapter } from './CanvasAdapter';

export function createKonvaCanvasAdapter(dependencies: CanvasAdapterDependencies): CanvasAdapter {
  return createCanvasAdapter('konva', dependencies);
}
