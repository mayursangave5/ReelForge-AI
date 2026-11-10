import React from 'react';
import { CameraCue } from '../types';
import { easeInOut, kf, lerp, shake } from './anim';

export type CameraProps = {
  frame: number;
  cue?: CameraCue;
  width?: number;
  height?: number;
  children: React.ReactNode;
};

export const Camera: React.FC<CameraProps> = ({
  frame,
  cue,
  width = 1080,
  height = 1920,
  children,
}) => {
  const targetZoom = cue?.zoom ?? 1.0;
  const targetPanX = cue?.panX ?? 0;
  const targetPanY = cue?.panY ?? 0;
  const targetTilt = cue?.tilt ?? 0;
  const shakeAmp = cue?.shake ?? 0;
  const duration = cue?.durationFrames ?? 90;

  // Smooth interpolation from frame 0 to target
  const p = Math.min(1, Math.max(0, frame / Math.max(1, duration)));
  const eased = easeInOut(p);

  const zoom = lerp(1.0, targetZoom, eased);
  const panX = lerp(0, targetPanX, eased);
  const panY = lerp(0, targetPanY, eased);
  const tilt = lerp(0, targetTilt, eased);

  const s = shakeAmp > 0 ? shake(frame, 0, duration, shakeAmp) : { x: 0, y: 0 };

  const cx = width / 2;
  const cy = height / 2;

  const transform = `translate(${cx + panX + s.x}px, ${cy + panY + s.y}px) rotate(${tilt}deg) scale(${zoom}) translate(${-cx}px, ${-cy}px)`;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        transformOrigin: `${cx}px ${cy}px`,
        transform,
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
};
