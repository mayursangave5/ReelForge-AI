import React from 'react';
import { Starfield } from './particles';

export const DeepSpaceBackground: React.FC<{
  frame: number;
  width?: number;
  height?: number;
}> = ({ frame, width = 1080, height = 1920 }) => {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        background: 'radial-gradient(circle at 50% 35%, #161233 0%, #0a081a 50%, #030208 100%)',
      }}
    >
      <Starfield frame={frame} width={width} height={height} count={130} speed={0.4} />

      {/* Nebula cloud */}
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <defs>
          <radialGradient id="nebulaA" cx="30%" cy="40%" r="50%">
            <stop offset="0%" stopColor="#4A1E75" stopOpacity={0.25} />
            <stop offset="70%" stopColor="#000000" stopOpacity={0} />
          </radialGradient>
          <radialGradient id="nebulaB" cx="75%" cy="65%" r="45%">
            <stop offset="0%" stopColor="#1E4475" stopOpacity={0.22} />
            <stop offset="70%" stopColor="#000000" stopOpacity={0} />
          </radialGradient>
        </defs>
        <rect width={width} height={height} fill="url(#nebulaA)" />
        <rect width={width} height={height} fill="url(#nebulaB)" />
      </svg>
    </div>
  );
};

export const EarthOrbitalView: React.FC<{
  frame: number;
  cx?: number;
  cy?: number;
  radius?: number;
  width?: number;
  height?: number;
}> = ({
  frame,
  cx = 540,
  cy = 1350,
  radius = 580,
  width = 1080,
  height = 1920,
}) => {
  const cloudRot = (frame * 0.12) % 360;
  const continentRot = (frame * 0.08) % 360;

  return (
    <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
      <defs>
        {/* Planet 3D Sphere Shading */}
        <radialGradient id="earthSphereGrad" cx="38%" cy="32%" r="65%">
          <stop offset="0%" stopColor="#2E7CD6" />
          <stop offset="55%" stopColor="#1B4D8F" />
          <stop offset="85%" stopColor="#0B2347" />
          <stop offset="100%" stopColor="#020914" />
        </radialGradient>

        {/* Atmospheric Glow */}
        <radialGradient id="atmosphereGlow" cx="50%" cy="50%" r="50%">
          <stop offset="82%" stopColor="#6BCBFF" stopOpacity={0} />
          <stop offset="93%" stopColor="#47B0FF" stopOpacity={0.45} />
          <stop offset="100%" stopColor="#9BD8FF" stopOpacity={0.85} />
        </radialGradient>

        <clipPath id="earthClip">
          <circle cx={cx} cy={cy} r={radius} />
        </clipPath>
      </defs>

      {/* Atmospheric Halo */}
      <circle
        cx={cx}
        cy={cy}
        r={radius + 35}
        fill="url(#atmosphereGlow)"
        filter="blur(8px)"
      />

      {/* Earth Body */}
      <circle cx={cx} cy={cy} r={radius} fill="url(#earthSphereGrad)" />

      {/* Continents inside clip */}
      <g clipPath="url(#earthClip)">
        <g transform={`rotate(${continentRot} ${cx} ${cy})`} opacity={0.85}>
          {/* Stylized continent shapes */}
          <path
            d={`M ${cx - 200} ${cy - 120} Q ${cx - 80} ${cy - 240} ${cx + 100} ${cy - 180} Q ${cx + 220} ${cy - 90} ${cx + 140} ${cy + 60} Q ${cx - 40} ${cy + 180} ${cx - 180} ${cy + 90} Z`}
            fill="#3FA358"
          />
          <path
            d={`M ${cx - 360} ${cy + 60} Q ${cx - 240} ${cy - 40} ${cx - 150} ${cy + 40} Q ${cx - 190} ${cy + 190} ${cx - 300} ${cy + 220} Z`}
            fill="#38944E"
          />
          <path
            d={`M ${cx + 180} ${cy + 40} Q ${cx + 320} ${cy - 20} ${cx + 380} ${cy + 120} Q ${cx + 290} ${cy + 260} ${cx + 200} ${cy + 190} Z`}
            fill="#2E8042"
          />
        </g>

        {/* Swirling Cloud Bands */}
        <g transform={`rotate(${cloudRot} ${cx} ${cy})`} opacity={0.65}>
          <path
            d={`M ${cx - radius} ${cy - 80} Q ${cx - 200} ${cy - 180} ${cx} ${cy - 100} T ${cx + radius} ${cy - 60} L ${cx + radius} ${cy - 20} Q ${cx + 200} ${cy - 60} ${cx} ${cy - 20} Z`}
            fill="#FFFFFF"
            filter="blur(3px)"
          />
          <path
            d={`M ${cx - radius} ${cy + 120} Q ${cx - 150} ${cy + 60} ${cx + 80} ${cy + 140} T ${cx + radius} ${cy + 100} L ${cx + radius} ${cy + 150} Q ${cx + 100} ${cy + 190} ${cx - radius} ${cy + 160} Z`}
            fill="#FFFFFF"
            filter="blur(4px)"
          />
        </g>

        {/* Night Terminator Shadow (Shadowed side) */}
        <path
          d={`M ${cx} ${cy - radius} A ${radius * 0.4} ${radius} 0 0 1 ${cx} ${cy + radius} A ${radius} ${radius} 0 0 1 ${cx} ${cy - radius} Z`}
          fill="#000000"
          opacity={0.65}
        />
      </g>
    </svg>
  );
};

export const CityHorizonView: React.FC<{
  frame: number;
  width?: number;
  height?: number;
}> = ({ frame, width = 1080, height = 1920 }) => {
  const buildings = React.useMemo(() => {
    const list = [];
    let currentX = 0;
    let idx = 0;
    while (currentX < width + 100) {
      const bWidth = 60 + ((idx * 37) % 80);
      const bHeight = 350 + ((idx * 83) % 450);
      list.push({ x: currentX, width: bWidth, height: bHeight, id: idx });
      currentX += bWidth - 10;
      idx++;
    }
    return list;
  }, [width]);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        background: 'linear-gradient(180deg, #120924 0%, #291240 40%, #5E2648 70%, #A84E38 100%)',
      }}
    >
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
        {/* Distant building silhouette */}
        {buildings.map((b) => (
          <rect
            key={b.id}
            x={b.x}
            y={height - b.height}
            width={b.width}
            height={b.height}
            fill="#120A1E"
          />
        ))}

        {/* Window lights */}
        {buildings.map((b) => {
          const rows = Math.floor(b.height / 35);
          const cols = Math.floor(b.width / 22);
          return Array.from({ length: Math.min(rows, 12) }).map((_, r) =>
            Array.from({ length: cols }).map((_, c) => {
              const lit = (b.id * 11 + r * 7 + c * 13) % 5 === 0;
              if (!lit) return null;
              return (
                <rect
                  key={`${b.id}-${r}-${c}`}
                  x={b.x + 8 + c * 20}
                  y={height - b.height + 25 + r * 30}
                  width={9}
                  height={14}
                  fill="#FFDE7A"
                  opacity={0.6 + 0.3 * Math.sin(frame * 0.08 + b.id + r)}
                />
              );
            })
          );
        })}

        {/* Ground level dark fog */}
        <rect x={0} y={height - 120} width={width} height={120} fill="#0A0512" />
      </svg>
    </div>
  );
};

export const GroundZeroView: React.FC<{
  frame: number;
  width?: number;
  height?: number;
}> = ({ frame, width = 1080, height = 1920 }) => {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        background: 'linear-gradient(180deg, #1C0A06 0%, #3B1208 45%, #6B1C0B 80%, #9E2F11 100%)',
      }}
    >
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <radialGradient id="magmaGlow" cx="50%" cy="85%" r="55%">
            <stop offset="0%" stopColor="#FFA600" stopOpacity={0.9} />
            <stop offset="50%" stopColor="#FF3700" stopOpacity={0.7} />
            <stop offset="100%" stopColor="#5E1005" stopOpacity={0} />
          </radialGradient>
        </defs>

        {/* Jagged crater horizon */}
        <path
          d={`M 0 ${height - 350} Q 260 ${height - 240} 540 ${height - 180} Q 820 ${height - 240} ${width} ${height - 350} L ${width} ${height} L 0 ${height} Z`}
          fill="#1F0D09"
        />

        {/* Molten lake at bottom */}
        <ellipse cx={width / 2} cy={height - 150} rx={480} ry={110} fill="url(#magmaGlow)" />

        {/* Cracks with glowing lava */}
        <path
          d={`M ${width / 2 - 250} ${height - 130} L ${width / 2 - 120} ${height - 100} L ${width / 2} ${height - 120} L ${width / 2 + 160} ${height - 90} L ${width / 2 + 320} ${height - 140}`}
          stroke="#FFCC00"
          strokeWidth={4}
          fill="none"
          filter="blur(1px)"
          opacity={0.8 + 0.2 * Math.sin(frame * 0.2)}
        />
      </svg>
    </div>
  );
};
