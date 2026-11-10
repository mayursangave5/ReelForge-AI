import React from 'react';
import { Camera } from '../engine/camera';
import { CharacterRig } from '../engine/rig';
import { Grade } from '../engine/vfx';
import { ShotDefinition } from '../types';

export const Style2dColorfulRenderer: React.FC<{
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
        background: 'linear-gradient(180deg, #1A1F38 0%, #2D325A 45%, #FF7B54 85%, #FFB26B 100%)',
        overflow: 'hidden',
      }}
    >
      <Camera frame={frame} cue={shot.camera} width={width} height={height}>
        <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
          {/* Flat vector sun */}
          <circle cx={width * 0.5} cy={height * 0.42} r={180} fill="#FFEAA7" opacity={0.9} />

          {/* Isometric styled vector mountains */}
          <polygon
            points={`0,${height - 300} 380,${height - 750} 720,${height - 400} 1080,${height - 680} 1080,${height} 0,${height}`}
            fill="#341F97"
            opacity={0.7}
          />
          <polygon
            points={`180,${height - 200} 540,${height - 600} 920,${height - 300} 1080,${height - 450} 1080,${height} 0,${height}`}
            fill="#10AC84"
            opacity={0.85}
          />

          {/* Clean flat ground */}
          <rect x={0} y={height - 240} width={width} height={240} fill="#1DD1A1" />

          {/* Kurzgesagt style animated character */}
          <CharacterRig
            frame={frame}
            pose={{
              x: width * 0.5 + Math.sin(frame * 0.1) * 35,
              y: height - 260,
              scale: 1.6,
              suitColor: '#FF6B6B',
              skinColor: '#F8EFBA',
              expr: shot.index % 2 === 0 ? 'happy' : 'shock',
              armL: { a: Math.sin(frame * 0.2) * 30, b: 15 },
              armR: { a: -Math.sin(frame * 0.2) * 30, b: -15 },
              tilt: Math.sin(frame * 0.15) * 4,
            }}
          />
        </svg>
      </Camera>
      <Grade frame={frame} width={width} height={height} />
    </div>
  );
};
