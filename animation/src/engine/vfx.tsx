import React from 'react';
import { rnd } from './anim';

export const FlashOverlay: React.FC<{
  frame: number;
  triggerFrame: number;
  duration?: number;
  color?: string;
  maxOpacity?: number;
}> = ({
  frame,
  triggerFrame,
  duration = 6,
  color = '#FFFFFF',
  maxOpacity = 0.95,
}) => {
  const rel = frame - triggerFrame;
  if (rel < 0 || rel >= duration) return null;

  const opacity = maxOpacity * (1 - rel / duration);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundColor: color,
        opacity,
        pointerEvents: 'none',
        zIndex: 50,
      }}
    />
  );
};

export const SpeedLines: React.FC<{
  frame: number;
  count?: number;
  width?: number;
  height?: number;
  color?: string;
  direction?: 'radial' | 'vertical';
}> = ({
  frame,
  count = 28,
  width = 1080,
  height = 1920,
  color = '#FFFFFF',
  direction = 'vertical',
}) => {
  const lines = React.useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      const x = rnd(i + 1, 1) * width;
      const length = rnd(i + 1, 2) * 350 + 150;
      const speed = rnd(i + 1, 3) * 45 + 30;
      const strokeWidth = rnd(i + 1, 4) * 3 + 1.5;
      const opacity = rnd(i + 1, 5) * 0.45 + 0.15;
      return { x, length, speed, strokeWidth, opacity };
    });
  }, [count, width]);

  if (direction === 'radial') {
    const cx = width / 2;
    const cy = height / 2;
    return (
      <svg
        width={width}
        height={height}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 20 }}
      >
        {Array.from({ length: count }).map((_, i) => {
          const angle = (i / count) * Math.PI * 2 + (frame * 0.05);
          const r1 = 300 + (rnd(i + frame, 6) * 150);
          const r2 = r1 + 350 + (rnd(i + frame, 7) * 200);
          const x1 = cx + Math.cos(angle) * r1;
          const y1 = cy + Math.sin(angle) * r1;
          const x2 = cx + Math.cos(angle) * r2;
          const y2 = cy + Math.sin(angle) * r2;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={color}
              strokeWidth={rnd(i + frame, 8) * 3 + 1}
              opacity={0.4}
              strokeLinecap="round"
            />
          );
        })}
      </svg>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 20 }}
    >
      {lines.map((line, i) => {
        const y1 = ((frame * line.speed + i * 180) % (height + line.length)) - line.length;
        const y2 = y1 + line.length;
        return (
          <line
            key={i}
            x1={line.x}
            y1={y1}
            x2={line.x}
            y2={y2}
            stroke={color}
            strokeWidth={line.strokeWidth}
            opacity={line.opacity}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
};

export const Grade: React.FC<{
  frame: number;
  width?: number;
  height?: number;
  vignette?: boolean;
  grain?: boolean;
}> = ({ frame, width = 1080, height = 1920, vignette = true, grain = true }) => {
  return (
    <svg
      width={width}
      height={height}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 40 }}
    >
      <defs>
        {vignette && (
          <radialGradient id="vignetteGrad" cx="50%" cy="50%" r="70%">
            <stop offset="45%" stopColor="#000000" stopOpacity={0} />
            <stop offset="100%" stopColor="#000000" stopOpacity={0.65} />
          </radialGradient>
        )}
        {grain && (
          <filter id="cinematicGrain" x="0" y="0" width="100%" height="100%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.85"
              numOctaves={2}
              seed={(Math.floor(frame / 2) % 67) + 1}
            />
            <feColorMatrix
              type="matrix"
              values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.05 0"
            />
          </filter>
        )}
      </defs>
      {vignette && <rect width={width} height={height} fill="url(#vignetteGrad)" />}
      {grain && <rect width={width} height={height} filter="url(#cinematicGrain)" />}
    </svg>
  );
};
