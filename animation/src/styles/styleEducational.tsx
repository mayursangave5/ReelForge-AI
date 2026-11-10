import React from 'react';
import { Camera } from '../engine/camera';
import { Grade } from '../engine/vfx';
import { ShotDefinition } from '../types';

export const StyleEducationalRenderer: React.FC<{
  shot: ShotDefinition;
  frame: number;
  width?: number;
  height?: number;
}> = ({ shot, frame, width = 1080, height = 1920 }) => {
  const p = Math.min(1, Math.max(0, frame / Math.max(1, shot.durationFrames)));

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        background: '#0D1117',
        overflow: 'hidden',
      }}
    >
      <Camera frame={frame} cue={shot.camera} width={width} height={height}>
        <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
          {/* 3Blue1Brown coordinate grid */}
          <defs>
            <pattern id="eduGrid" width="80" height="80" patternUnits="userSpaceOnUse">
              <path d="M 80 0 L 0 0 0 80" fill="none" stroke="rgba(255, 255, 255, 0.08)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width={width} height={height} fill="url(#eduGrid)" />

          {/* Animated Function Graph */}
          {(() => {
            const points: string[] = [];
            for (let x = 120; x <= width - 120; x += 15) {
              const normX = (x - 120) / (width - 240);
              if (normX > p) break;
              const y = height * 0.55 - Math.sin(normX * Math.PI * 2.5 + frame * 0.06) * 140 - normX * 180;
              points.push(`${x},${y}`);
            }
            if (points.length < 2) return null;
            return (
              <polyline
                points={points.join(' ')}
                fill="none"
                stroke="#58A6FF"
                strokeWidth={6}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })()}

          {/* Animated Callout Badge */}
          <rect
            x={width * 0.12}
            y={height * 0.25}
            width={width * 0.76}
            height={220}
            rx={18}
            fill="rgba(22, 27, 34, 0.9)"
            stroke="#30363D"
            strokeWidth={2}
          />
          <text
            x={width * 0.18}
            y={height * 0.31}
            fill="#58A6FF"
            fontSize={36}
            fontFamily="monospace"
            fontWeight="bold"
          >
            f(t) = ASTEROID TRAJECTORY
          </text>
          <text
            x={width * 0.18}
            y={height * 0.37}
            fill="#E6EDF3"
            fontSize={42}
            fontFamily="monospace"
            fontWeight="bold"
          >
            VELOCITY: 72,000 KM/H
          </text>
        </svg>
      </Camera>
      <Grade frame={frame} width={width} height={height} />
    </div>
  );
};
