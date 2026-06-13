export interface FloatingPosition {
  x: number;
  y: number;
}

export interface FloatingBounds {
  viewportWidth: number;
  viewportHeight: number;
  elementWidth: number;
  elementHeight: number;
  margin?: number;
}

export const DEFAULT_FLOATING_MARGIN = 12;

function clampValue(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function clampFloatingPosition(
  position: FloatingPosition,
  bounds: FloatingBounds,
): FloatingPosition {
  const margin = bounds.margin ?? DEFAULT_FLOATING_MARGIN;
  const maxX = Math.max(margin, bounds.viewportWidth - bounds.elementWidth - margin);
  const maxY = Math.max(margin, bounds.viewportHeight - bounds.elementHeight - margin);

  return {
    x: clampValue(position.x, margin, maxX),
    y: clampValue(position.y, margin, maxY),
  };
}
