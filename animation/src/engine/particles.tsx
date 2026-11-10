import React from 'react';
import { clamp, easeOut, rnd } from './anim';

export const Starfield: React.FC<{
  frame: number;
  count?: number;
  speed?: number;
  width?: number;
  height?: number;
}> = ({ frame, count = 120, speed = 0.5, width = 1080, height = 1920 }) => {
  const stars = React.useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      const x = rnd(i + 1, 1) * width;
      const y = rnd(i + 1, 2) * height;
      const r = rnd(i + 1, 3) * 2.2 + 0.8;
      const depth = rnd(i + 1, 4) * 0.7 + 0.3;
      const color = rnd(i + 1, 5) > 0.8 ? '#AEE4FF' : rnd(i + 1, 5) > 0.6 ? '#FFE7B8' : '#FFFFFF';
      return { x, y, r, depth, color, seed: i };
    });
  }, [count, width, height]);

  return (
    <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
      {stars.map((s, idx) => {
        const curY = (s.y + frame * speed * s.depth) % height;
        const twinkle = 0.5 + 0.5 * Math.sin(frame * 0.15 + s.seed);
        return (
          <circle
            key={idx}
            cx={s.x}
            cy={curY}
            r={s.r}
            fill={s.color}
            opacity={0.3 + 0.7 * twinkle}
          />
        );
      })}
    </svg>
  );
};

export const PlasmaTrail: React.FC<{
  frame: number;
  startX: number;
  startY: number;
  targetX: number;
  targetY: number;
  progress: number;
  count?: number;
}> = ({ frame, startX, startY, targetX, targetY, progress, count = 35 }) => {
  const currentX = startX + (targetX - startX) * progress;
  const currentY = startY + (targetY - startY) * progress;
  const dirX = targetX - startX;
  const dirY = targetY - startY;
  const len = Math.sqrt(dirX * dirX + dirY * dirY) || 1;
  const normX = dirX / len;
  const normY = dirY / len;

  return (
    <g>
      {Array.from({ length: count }).map((_, i) => {
        const trailDist = (i + 1) * 8 + rnd(i + frame, 1) * 15;
        const perpDist = (rnd(i + frame, 2) - 0.5) * (14 + i * 1.8);
        const px = currentX - normX * trailDist - normY * perpDist;
        const py = currentY - normY * trailDist + normX * perpDist;
        const radius = Math.max(2, (count - i) * 1.2 * (rnd(i + frame, 3) * 0.5 + 0.5));
        const alpha = Math.max(0, 1 - i / count) * 0.8;
        const color = i < 8 ? '#FFFFFF' : i < 18 ? '#FFCC00' : '#FF4500';

        return (
          <circle
            key={i}
            cx={px}
            cy={py}
            r={radius}
            fill={color}
            opacity={alpha}
            filter="blur(1px)"
          />
        );
      })}
    </g>
  );
};

export const ShockwaveRing: React.FC<{
  frame: number;
  cx: number;
  cy: number;
  startFrame: number;
  durationFrames?: number;
  maxRadius?: number;
  color?: string;
}> = ({
  frame,
  cx,
  cy,
  startFrame,
  durationFrames = 45,
  maxRadius = 1400,
  color = '#FFF2A8',
}) => {
  const rel = frame - startFrame;
  if (rel < 0 || rel > durationFrames) return null;

  const p = rel / durationFrames;
  const eased = easeOut(p);
  const radius = eased * maxRadius;
  const strokeWidth = (1 - p) * 35 + 4;
  const opacity = (1 - p) * 0.95;

  return (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      stroke={color}
      strokeWidth={strokeWidth}
      fill="none"
      opacity={opacity}
    />
  );
};

export const DebrisExplosion: React.FC<{
  frame: number;
  cx: number;
  cy: number;
  startFrame: number;
  count?: number;
}> = ({ frame, cx, cy, startFrame, count = 40 }) => {
  const rel = frame - startFrame;
  if (rel < 0 || rel > 60) return null;

  const p = rel / 60;

  return (
    <g>
      {Array.from({ length: count }).map((_, i) => {
        const angle = rnd(i + 1, 10) * Math.PI * 2;
        const speed = rnd(i + 1, 11) * 600 + 150;
        const dist = easeOut(p) * speed;
        const gravity = p * p * 350;
        const px = cx + Math.cos(angle) * dist;
        const py = cy + Math.sin(angle) * dist + gravity;
        const size = rnd(i + 1, 12) * 12 + 4;
        const rot = frame * (rnd(i + 1, 13) * 20 - 10);
        const alpha = Math.max(0, 1 - p * 1.2);
        const color = rnd(i + 1, 14) > 0.4 ? '#FF8C00' : '#4A4A4A';

        return (
          <rect
            key={i}
            x={px - size / 2}
            y={py - size / 2}
            width={size}
            height={size}
            fill={color}
            opacity={alpha}
            transform={`rotate(${rot} ${px} ${py})`}
          />
        );
      })}
    </g>
  );
};

export const MushroomCloud: React.FC<{
  frame: number;
  cx: number;
  cy: number;
  startFrame: number;
  durationFrames?: number;
}> = ({ frame, cx, cy, startFrame, durationFrames = 90 }) => {
  const rel = frame - startFrame;
  if (rel < 0) return null;

  const p = clamp(rel / durationFrames);
  const stemHeight = easeOut(Math.min(1, p * 1.5)) * 480;
  const headRadius = easeOut(p) * 260;
  const alpha = Math.max(0.15, 1 - p * 0.6);

  return (
    <g opacity={alpha}>
      {/* Stem */}
      <path
        d={`M ${cx - 70} ${cy} C ${cx - 40} ${cy - stemHeight * 0.5}, ${cx - 90} ${cy - stemHeight}, ${cx} ${cy - stemHeight} C ${cx + 90} ${cy - stemHeight}, ${cx + 40} ${cy - stemHeight * 0.5}, ${cx + 70} ${cy} Z`}
        fill="#33221E"
        opacity={0.85}
      />
      {/* Inner fiery glow */}
      <circle
        cx={cx}
        cy={cy - stemHeight * 0.9}
        r={headRadius * 0.6}
        fill="#FF5500"
        opacity={Math.max(0, 1 - p * 2)}
        filter="blur(15px)"
      />
      {/* Cloud head lobes */}
      <circle cx={cx} cy={cy - stemHeight} r={headRadius * 0.85} fill="#261A18" />
      <circle cx={cx - headRadius * 0.5} cy={cy - stemHeight + 20} r={headRadius * 0.65} fill="#332520" />
      <circle cx={cx + headRadius * 0.5} cy={cy - stemHeight + 20} r={headRadius * 0.65} fill="#332520" />
      <circle cx={cx} cy={cy - stemHeight - 40} r={headRadius * 0.75} fill="#42302A" />
    </g>
  );
};
