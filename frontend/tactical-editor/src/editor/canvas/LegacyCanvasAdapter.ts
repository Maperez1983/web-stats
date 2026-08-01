import type { CanvasAdapter, CanvasAdapterDependencies } from './CanvasAdapter';
import { createCanvasAdapter } from './CanvasAdapter';

export function createLegacyCanvasAdapter(dependencies: CanvasAdapterDependencies): CanvasAdapter {
  return createCanvasAdapter('legacy', dependencies);
}
