import React from 'react';
import { Camera } from '../engine/camera';
import { CharacterRig } from '../engine/rig';
import { FlashOverlay, Grade, SpeedLines } from '../engine/vfx';
import { ShotDefinition } from '../types';

export const StyleAnimeRenderer: React.FC<{
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
        background: 'linear-gradient(135deg, #090014 0%, #19053B 50%, #4D0A5A 100%)',
        overflow: 'hidden',
      }}
    >
      <Camera frame={frame} cue={shot.camera} width={width} height={height}>
        {/* Dynamic speed lines */}
        <SpeedLines frame={frame} width={width} height={height} count={40} direction="radial" />

        <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
          {/* Action Impact diagonal shards */}
          <polygon
            points={`0,${height * 0.3} ${width},${height * 0.45} ${width},${height * 0.52} 0,${height * 0.37}`}
            fill="#FF007F"
            opacity={0.35}
          />

          {/* High action anime hero */}
          <CharacterRig
            frame={frame}
            pose={{
              x: width * 0.5,
              y: height * 0.65,
              scale: 2.1,
              suitColor: '#1A1A24',
              hairColor: '#E2E8F0',
              skinColor: '#FED7AA',
              expr: 'shock',
              headTilt: 12,
              armL: { a: -75, b: -30 },
              armR: { a: 50, b: 40 },
              tilt: -14,
            }}
          />
        </svg>
      </Camera>

      {frame < 4 && <FlashOverlay frame={frame} triggerFrame={0} duration={4} color="#FF0055" />}
      <Grade frame={frame} width={width} height={height} />
    </div>
  );
};
