import React from 'react';
import { Camera } from '../engine/camera';
import {
  CityHorizonView,
  DeepSpaceBackground,
  EarthOrbitalView,
  GroundZeroView,
} from '../engine/backgrounds';
import {
  DebrisExplosion,
  MushroomCloud,
  PlasmaTrail,
  ShockwaveRing,
} from '../engine/particles';
import { CharacterRig } from '../engine/rig';
import { FlashOverlay, Grade, SpeedLines } from '../engine/vfx';
import { ShotDefinition } from '../types';

export const Style3dCartoonRenderer: React.FC<{
  shot: ShotDefinition;
  frame: number; // Shot-relative frame
  width?: number;
  height?: number;
}> = ({ shot, frame, width = 1080, height = 1920 }) => {
  const p = Math.min(1, Math.max(0, frame / Math.max(1, shot.durationFrames)));

  // Determine subscene based on shot index and background
  const bg = shot.background || '';
  const isDeepSpace = bg.includes('space') || shot.index <= 2;
  const isEarthOrbit = bg.includes('orbit') || shot.index === 3 || shot.index === 9;
  const isCity = bg.includes('city') || shot.index === 4;
  const isImpact = bg.includes('impact') || bg.includes('crater') || (shot.index >= 5 && shot.index <= 8);
  const isScience = bg.includes('science') || shot.index >= 10;

  return (
    <div style={{ position: 'absolute', inset: 0, width, height, overflow: 'hidden' }}>
      <Camera frame={frame} cue={shot.camera} width={width} height={height}>
        {/* Background Environment */}
        {isDeepSpace ? (
          <DeepSpaceBackground frame={frame} width={width} height={height} />
        ) : isEarthOrbit ? (
          <>
            <DeepSpaceBackground frame={frame} width={width} height={height} />
            <EarthOrbitalView frame={frame} width={width} height={height} />
          </>
        ) : isCity ? (
          <CityHorizonView frame={frame} width={width} height={height} />
        ) : isImpact ? (
          <GroundZeroView frame={frame} width={width} height={height} />
        ) : (
          <DeepSpaceBackground frame={frame} width={width} height={height} />
        )}

        {/* Foreground Animated Elements */}
        {/* Asteroid in space / entry */}
        {(isDeepSpace || isEarthOrbit) && (
          <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
            <defs>
              <radialGradient id="asteroid3dGrad" cx="35%" cy="30%" r="65%">
                <stop offset="0%" stopColor="#8C827A" />
                <stop offset="40%" stopColor="#5E554E" />
                <stop offset="75%" stopColor="#3B342F" />
                <stop offset="100%" stopColor="#171412" />
              </radialGradient>
              <filter id="flameGlow">
                <feGaussianBlur stdDeviation="8" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Plasma exhaust trail */}
            <PlasmaTrail
              frame={frame}
              startX={width * 0.15}
              startY={height * 0.1}
              targetX={width * 0.82}
              targetY={height * 0.75}
              progress={p}
            />

            {/* 3D Asteroid rock with craters */}
            {(() => {
              const curX = width * 0.15 + (width * 0.82 - width * 0.15) * p;
              const curY = height * 0.1 + (height * 0.75 - height * 0.1) * p;
              const baseSize = 85 + p * 120;
              const rot = frame * 1.8;

              return (
                <g transform={`translate(${curX} ${curY}) rotate(${rot})`}>
                  {/* Outer atmospheric entry flame rim */}
                  <ellipse
                    cx={0}
                    cy={0}
                    rx={baseSize * 1.3}
                    ry={baseSize * 1.15}
                    fill="#FF4500"
                    opacity={0.7}
                    filter="url(#flameGlow)"
                  />
                  <ellipse
                    cx={0}
                    cy={0}
                    rx={baseSize * 1.15}
                    ry={baseSize * 1.05}
                    fill="#FFA500"
                    opacity={0.85}
                  />

                  {/* Rocky polygonal asteroid body */}
                  <path
                    d={`M ${-baseSize} 0 Q ${-baseSize * 0.8} ${-baseSize * 0.9} 0 ${-baseSize} Q ${baseSize * 0.7} ${-baseSize * 0.8} ${baseSize} 0 Q ${baseSize * 0.9} ${baseSize * 0.8} 0 ${baseSize} Q ${-baseSize * 0.7} ${baseSize * 0.8} ${-baseSize} 0 Z`}
                    fill="url(#asteroid3dGrad)"
                  />

                  {/* Surface craters */}
                  <circle cx={-baseSize * 0.3} cy={-baseSize * 0.2} r={baseSize * 0.22} fill="#26221F" opacity={0.75} />
                  <circle cx={baseSize * 0.25} cy={baseSize * 0.3} r={baseSize * 0.18} fill="#26221F" opacity={0.75} />
                  <circle cx={baseSize * 0.1} cy={-baseSize * 0.4} r={baseSize * 0.14} fill="#26221F" opacity={0.75} />
                </g>
              );
            })()}
          </svg>
        )}

        {/* City Characters Reacting */}
        {isCity && (
          <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
            {/* Warning siren light sweep */}
            <circle
              cx={width / 2}
              cy={height * 0.3}
              r={700}
              fill="rgba(255, 30, 0, 0.18)"
              opacity={0.5 + 0.5 * Math.sin(frame * 0.3)}
            />

            {/* Character in foreground looking up in terror */}
            <CharacterRig
              frame={frame}
              pose={{
                x: width * 0.45,
                y: height - 140,
                scale: 1.45,
                expr: 'shock',
                look: -0.8,
                headTilt: -18,
                armL: { a: -60, b: -40 },
                armR: { a: 45, b: 35 },
                tilt: -8,
              }}
            />

            {/* Second bystander pointing */}
            <CharacterRig
              frame={frame}
              pose={{
                x: width * 0.78,
                y: height - 130,
                scale: 1.3,
                facing: -1,
                expr: 'panic',
                look: 0.6,
                headTilt: 15,
                armL: { a: 70, b: 20 },
                armR: { a: -20, b: -10 },
                tilt: 6,
                suitColor: '#3C366B',
              }}
            />
          </svg>
        )}

        {/* Impact Ground Zero Explosions */}
        {isImpact && (
          <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
            {/* Blinding expanding shockwave ring */}
            <ShockwaveRing
              frame={frame}
              cx={width / 2}
              cy={height - 250}
              startFrame={0}
              durationFrames={shot.durationFrames}
              maxRadius={1800}
            />

            {/* Ejecta flying debris */}
            <DebrisExplosion
              frame={frame}
              cx={width / 2}
              cy={height - 250}
              startFrame={0}
              count={55}
            />

            {/* Rising Mushroom Cloud */}
            <MushroomCloud
              frame={frame}
              cx={width / 2}
              cy={height - 180}
              startFrame={5}
              durationFrames={shot.durationFrames}
            />
          </svg>
        )}

        {/* Scientific Diagram Overlay (for Science beat) */}
        {isScience && (
          <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
            {/* Grid background lines */}
            <defs>
              <pattern id="sciGrid" width="60" height="60" patternUnits="userSpaceOnUse">
                <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(0, 220, 255, 0.15)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width={width} height={height} fill="url(#sciGrid)" />

            {/* Holographic readout box */}
            <rect
              x={width * 0.08}
              y={height * 0.22}
              width={width * 0.84}
              height={420}
              rx={24}
              fill="rgba(5, 18, 38, 0.85)"
              stroke="#00E5FF"
              strokeWidth={3}
              filter="drop-shadow(0 0 20px rgba(0, 229, 255, 0.4))"
            />

            {/* Scientific schematic labels */}
            <text x={width * 0.14} y={height * 0.28} fill="#00E5FF" fontSize={32} fontFamily="monospace" fontWeight="bold">
              [SYSTEM ANALYSIS: KINETIC IMPACT]
            </text>
            <text x={width * 0.14} y={height * 0.33} fill="#FFFFFF" fontSize={42} fontFamily="sans-serif" fontWeight="900">
              ENERGY: 100,000,000 MEGATONS
            </text>
            <text x={width * 0.14} y={height * 0.38} fill="#FFCC00" fontSize={36} fontFamily="sans-serif" fontWeight="bold">
              BLAST RADIUS: 1,500 KM GLOBAL
            </text>
            <text x={width * 0.14} y={height * 0.43} fill="#A0AEC0" fontSize={28} fontFamily="monospace">
              ATMOSPHERIC SOOT: 15 BILLION TONS
            </text>

            {/* Animated scientific radar scan bar */}
            <line
              x1={width * 0.08}
              y1={height * 0.22 + ((frame * 6) % 420)}
              x2={width * 0.92}
              y2={height * 0.22 + ((frame * 6) % 420)}
              stroke="#00E5FF"
              strokeWidth={2}
              opacity={0.65}
            />
          </svg>
        )}

        {/* Speed lines on fast descent */}
        {shot.index === 5 && <SpeedLines frame={frame} width={width} height={height} count={35} />}
      </Camera>

      {/* Screen flash on impact */}
      {isImpact && frame < 8 && <FlashOverlay frame={frame} triggerFrame={0} duration={8} />}

      {/* Vignette & Grain */}
      <Grade frame={frame} width={width} height={height} />
    </div>
  );
};
