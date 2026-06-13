import { clampFloatingPosition } from '../src/lib/floatingWindowDrag';

function assertEqualPosition(
  actual: { x: number; y: number },
  expected: { x: number; y: number },
  label: string,
) {
  if (actual.x !== expected.x || actual.y !== expected.y) {
    throw new Error(
      `${label}: expected (${expected.x}, ${expected.y}), received (${actual.x}, ${actual.y})`,
    );
  }
}

const viewport = {
  viewportWidth: 1024,
  viewportHeight: 768,
  elementWidth: 380,
  elementHeight: 560,
  margin: 12,
};

assertEqualPosition(
  clampFloatingPosition({ x: 240, y: 120 }, viewport),
  { x: 240, y: 120 },
  'keeps valid drag position',
);

assertEqualPosition(
  clampFloatingPosition({ x: -200, y: -100 }, viewport),
  { x: 12, y: 12 },
  'clamps above and left of viewport',
);

assertEqualPosition(
  clampFloatingPosition({ x: 900, y: 700 }, viewport),
  { x: 632, y: 196 },
  'clamps below and right of viewport',
);

assertEqualPosition(
  clampFloatingPosition(
    { x: 100, y: 100 },
    {
      viewportWidth: 320,
      viewportHeight: 240,
      elementWidth: 380,
      elementHeight: 560,
      margin: 12,
    },
  ),
  { x: 12, y: 12 },
  'keeps oversized panel reachable',
);

console.log('AI sidebar drag position checks passed');
