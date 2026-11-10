import React from 'react';
import { clamp, easeInOut, lerp } from './anim';

export type Expression =
  | 'neutral'
  | 'shock'
  | 'worried'
  | 'happy'
  | 'panic'
  | 'cool'
  | 'oops';

export type Limb = { a: number; b: number };

export type CharacterPose = {
  x: number;
  y: number; // Hips
  scale: number;
  facing: 1 | -1;
  tilt: number;     // Torso lean (deg)
  headTilt: number; // Head angle (deg)
  yaw: number;      // -1 (profile left) to 0 (front) to 1 (profile right)
  armL: Limb;
  armR: Limb;
  legL: Limb;
  legR: Limb;
  expr: Expression;
  blink: number; // 0 open, 1 closed
  look: number;  // -1 to 1
  skinColor?: string;
  suitColor?: string;
  hairColor?: string;
};

export const defaultPose: CharacterPose = {
  x: 540,
  y: 1350,
  scale: 1,
  facing: 1,
  tilt: 0,
  headTilt: 0,
  yaw: 0,
  armL: { a: 15, b: -10 },
  armR: { a: -15, b: 10 },
  legL: { a: 8, b: 0 },
  legR: { a: -8, b: 0 },
  expr: 'neutral',
  blink: 0,
  look: 0,
  skinColor: '#F5D3B3',
  suitColor: '#2D3748',
  hairColor: '#1A202C',
};

const rad = (deg: number) => (deg * Math.PI) / 180;

export const CharacterRig: React.FC<{
  pose?: Partial<CharacterPose>;
  frame?: number;
}> = ({ pose: customPose, frame = 0 }) => {
  const pose: CharacterPose = { ...defaultPose, ...customPose };

  const {
    x,
    y,
    scale,
    facing,
    tilt,
    headTilt,
    yaw,
    armL,
    armR,
    legL,
    legR,
    expr,
    blink,
    look,
    skinColor = '#F5D3B3',
    suitColor = '#2D3748',
    hairColor = '#1A202C',
  } = pose;

  // Body metrics
  const torsoHeight = 110;
  const headRadius = 42;
  const upperArmLen = 52;
  const foreArmLen = 48;
  const thighLen = 65;
  const shinLen = 60;

  // Yaw compression
  const yawFactor = 1 - 0.35 * Math.abs(yaw);
  const shoulderSpread = 44 * yawFactor;
  const hipSpread = 22 * yawFactor;

  // Automatic blink
  const isBlinking = blink > 0.5 || (frame % 90 >= 86 && frame % 90 <= 88);

  const drawLimb = (
    rootX: number,
    rootY: number,
    limb: Limb,
    len1: number,
    len2: number,
    strokeColor: string,
    strokeW = 14
  ) => {
    const a1Rad = rad(limb.a);
    const midX = rootX + Math.sin(a1Rad) * len1 * facing;
    const midY = rootY + Math.cos(a1Rad) * len1;

    const a2Rad = rad(limb.a + limb.b);
    const endX = midX + Math.sin(a2Rad) * len2 * facing;
    const endY = midY + Math.cos(a2Rad) * len2;

    return (
      <g>
        <line
          x1={rootX}
          y1={rootY}
          x2={midX}
          y2={midY}
          stroke={strokeColor}
          strokeWidth={strokeW}
          strokeLinecap="round"
        />
        <line
          x1={midX}
          y1={midY}
          x2={endX}
          y2={endY}
          stroke={strokeColor}
          strokeWidth={strokeW}
          strokeLinecap="round"
        />
        {/* Hand / Foot cap */}
        <circle cx={endX} cy={endY} r={strokeW * 0.55} fill={skinColor} />
      </g>
    );
  };

  const headY = -torsoHeight - headRadius * 0.85;

  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <g transform={`rotate(${tilt})`}>
        {/* Back Arm (L) */}
        {drawLimb(
          -shoulderSpread,
          -torsoHeight + 15,
          armL,
          upperArmLen,
          foreArmLen,
          suitColor,
          13
        )}

        {/* Back Leg (L) */}
        {drawLimb(-hipSpread, 0, legL, thighLen, shinLen, suitColor, 15)}

        {/* Torso */}
        <path
          d={`M ${-shoulderSpread} ${-torsoHeight + 10} L ${shoulderSpread} ${-torsoHeight + 10} L ${hipSpread} 0 L ${-hipSpread} 0 Z`}
          fill={suitColor}
        />

        {/* Front Leg (R) */}
        {drawLimb(hipSpread, 0, legR, thighLen, shinLen, suitColor, 15)}

        {/* Front Arm (R) */}
        {drawLimb(
          shoulderSpread,
          -torsoHeight + 15,
          armR,
          upperArmLen,
          foreArmLen,
          suitColor,
          13
        )}

        {/* Head Group */}
        <g transform={`translate(${yaw * 12} ${headY}) rotate(${headTilt})`}>
          {/* Hair back */}
          <circle cx={-yaw * 8} cy={-8} r={headRadius + 4} fill={hairColor} />

          {/* Head Base */}
          <circle cx={0} cy={0} r={headRadius} fill={skinColor} />

          {/* Hair top / fringe */}
          <path
            d={`M ${-headRadius} ${-10} Q 0 ${-headRadius - 12} ${headRadius} ${-10} Q 0 ${-headRadius + 14} ${-headRadius} ${-10} Z`}
            fill={hairColor}
          />

          {/* Eyes & Facial Expression */}
          {isBlinking ? (
            <g stroke="#1A202C" strokeWidth={3.5} strokeLinecap="round">
              <line x1={-18 + look * 6} y1={-2} x2={-4 + look * 6} y2={-2} />
              <line x1={4 + look * 6} y1={-2} x2={18 + look * 6} y2={-2} />
            </g>
          ) : expr === 'shock' ? (
            <g>
              <ellipse cx={-11 + look * 6} cy={-3} rx={8} ry={11} fill="#1A202C" />
              <ellipse cx={11 + look * 6} cy={-3} rx={8} ry={11} fill="#1A202C" />
              <circle cx={-9 + look * 6} cy={-6} r={2.8} fill="#FFFFFF" />
              <circle cx={13 + look * 6} cy={-6} r={2.8} fill="#FFFFFF" />
              {/* Shock Mouth (O shape) */}
              <ellipse cx={0} cy={18} rx={9} ry={14} fill="#1A202C" />
            </g>
          ) : expr === 'worried' || expr === 'panic' ? (
            <g>
              <circle cx={-11 + look * 6} cy={-2} r={6} fill="#1A202C" />
              <circle cx={11 + look * 6} cy={-2} r={6} fill="#1A202C" />
              {/* Worried brows */}
              <line x1={-18} y1={-14} x2={-5} y2={-10} stroke="#1A202C" strokeWidth={3} strokeLinecap="round" />
              <line x1={5} y1={-10} x2={18} y2={-14} stroke="#1A202C" strokeWidth={3} strokeLinecap="round" />
              {/* Wavy mouth */}
              <path d="M -12 18 Q -4 14 0 18 Q 6 22 12 18" stroke="#1A202C" strokeWidth={3.5} fill="none" strokeLinecap="round" />
            </g>
          ) : expr === 'happy' ? (
            <g>
              {/* Happy curved eyes */}
              <path d="M -17 -2 Q -11 -9 -5 -2" stroke="#1A202C" strokeWidth={3.5} fill="none" strokeLinecap="round" />
              <path d="M 5 -2 Q 11 -9 17 -2" stroke="#1A202C" strokeWidth={3.5} fill="none" strokeLinecap="round" />
              {/* Smile */}
              <path d="M -12 14 Q 0 24 12 14 Z" fill="#D9534F" />
            </g>
          ) : (
            // Neutral
            <g>
              <circle cx={-11 + look * 6} cy={-2} r={5} fill="#1A202C" />
              <circle cx={11 + look * 6} cy={-2} r={5} fill="#1A202C" />
              <line x1={-8} y1={16} x2={8} y2={16} stroke="#1A202C" strokeWidth={3} strokeLinecap="round" />
            </g>
          )}
        </g>
      </g>
    </g>
  );
};
