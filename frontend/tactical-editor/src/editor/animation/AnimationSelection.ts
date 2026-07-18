export type AnimationSelection = {
  trackIds: string[];
  keyframeIds: string[];
  objectIds: string[];
  sequenceIds: string[];
};

export function createAnimationSelection(overrides?: Partial<AnimationSelection>): AnimationSelection {
  return {
    trackIds: [...new Set(overrides?.trackIds || [])],
    keyframeIds: [...new Set(overrides?.keyframeIds || [])],
    objectIds: [...new Set(overrides?.objectIds || [])],
    sequenceIds: [...new Set(overrides?.sequenceIds || [])],
  };
}

export function toggleAnimationSelection(
  ids: string[],
  id: string,
  additive: boolean
): string[] {
  if (!id) {
    return [...ids];
  }
  const selected = new Set(ids);
  if (additive && selected.has(id)) {
    selected.delete(id);
  } else if (additive) {
    selected.add(id);
  } else {
    selected.clear();
    selected.add(id);
  }
  return [...selected];
}

export function normalizeAnimationSelectionIds(ids: string[]): string[] {
  return [...new Set(ids.filter(Boolean))];
}
