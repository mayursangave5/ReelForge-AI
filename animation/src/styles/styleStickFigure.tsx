import React from 'react';
import { Camera } from '../engine/camera';
import { CharacterRig } from '../engine/rig';
import { Grade } from '../engine/vfx';
import { ShotDefinition } from '../types';

export const StyleStickFigureRenderer: React.FC<{
  shot: ShotDefinition;
  frame: number;
  width?: number;
  height?: number;
}> = ({ shot, frame, width = 1080, height = 1920 }) => {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        background: 'radial-gradient(circle at 50% 40%, #2A2538 0%, #171421 60%, #0D0B13 100%)',
        overflow: 'hidden',
      }}
    >
      <Camera frame={frame} cue={shot.camera} width={width} height={height}>
        <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            {/* Practical lamp lighting pool */}
            <radialGradient id="lampPool" cx="50%" cy="30%" r="55%">
              <stop offset="0%" stopColor="#FFEAA7" stopOpacity={0.4} />
              <stop offset="60%" stopColor="#FFA502" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#000000" stopOpacity={0} />
            </radialGradient>
          </defs>

          {/* Hanging lamp cord & shade */}
          <line x1={width * 0.5} y1={0} x2={width * 0.5} y2={height * 0.28} stroke="#A4B0BE" strokeWidth={3} />
          <polygon
            points={`${width * 0.5 - 55},${height * 0.28 + 35} ${width * 0.5 + 55},${height * 0.28 + 35} ${width * 0.5 + 28},${height * 0.28} ${width * 0.5 - 28},${height * 0.28}`}
            fill="#F1F2F6"
          />
          <circle cx={width * 0.5} cy={height * 0.45} r={480} fill="url(#lampPool)" />

          {/* Desk / Floor */}
          <rect x={0} y={height - 320} width={width} height={320} fill="#14111E" />
          <line x1={0} y1={height - 320} x2={width} y2={height - 320} stroke="#3D3452" strokeWidth={4} />

          {/* Stick hero (Pip) */}
          <CharacterRig
            frame={frame}
            pose={{
              x: width * 0.5,
              y: height - 330,
              scale: 1.5,
              skinColor: '#F8EFBA',
              suitColor: '#E67E22',
              hairColor: '#1E272E',
              expr: 'neutral',
              armL: { a: 15 + Math.sin(frame * 0.1) * 10, b: -8 },
              armR: { a: -20, b: 25 },
              tilt: 2,
            }}
          />
        </svg>
      </Camera>
      <Grade frame={frame} width={width} height={height} />
    </div>
  );
};
