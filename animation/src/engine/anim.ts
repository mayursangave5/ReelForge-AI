export const clamp = (v: number, min = 0, max = 1): number =>
  Math.min(max, Math.max(min, v));

export const lerp = (a: number, b: number, t: number): number =>
  a + (b - a) * t;

export const easeInOut = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export const easeOut = (t: number): number =>
  1 - Math.pow(1 - t, 3);

export const easeIn = (t: number): number =>
  t * t * t;

export const backOut = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

export const bounceOut = (t: number): number => {
  const n1 = 7.5625;
  const d1 = 2.75;
  if (t < 1 / d1) return n1 * t * t;
  if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
  if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
  return n1 * (t -= 2.625 / d1) * t + 0.984375;
};

export const kf = (
  f: number,
  keys: [number, number][],
  ease: (t: number) => number = easeInOut
): number => {
  if (f <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [f0, v0] = keys[i];
    const [f1, v1] = keys[i + 1];
    if (f <= f1) {
      const p = clamp((f - f0) / Math.max(1e-6, f1 - f0));
      return lerp(v0, v1, ease(p));
    }
  }
  return keys[keys.length - 1][1];
};

export const rnd = (seed: number, i: number): number =>
  Math.abs(Math.sin(seed * 37.11 + i * 19.349) * 43758.5453) % 1;

export const settle = (
  t: number,
  amp: number,
  speed = 1.4,
  decay = 8
): number =>
  t > 0 ? Math.sin(t * speed) * amp * Math.exp(-t / decay) : 0;

export const shake = (
  t: number,
  from: number,
  len = 10,
  amp = 12
): { x: number; y: number } => {
  if (t >= from && t < from + len) {
    const progress = (t - from) / len;
    const falloff = 1 - progress;
    return {
      x: Math.sin(t * 2.9) * amp * falloff,
      y: Math.cos(t * 3.7) * amp * 0.7 * falloff,
    };
  }
  return { x: 0, y: 0 };
};
