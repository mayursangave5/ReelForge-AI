import React from 'react';
import { WordCue } from '../types';

export const Subtitles: React.FC<{
  currentSeconds: number;
  captions?: WordCue[];
  fontSize?: number;
  activeColor?: string;
  defaultColor?: string;
  yOffset?: number;
  width?: number;
}> = ({
  currentSeconds,
  captions = [],
  fontSize = 52,
  activeColor = '#FFE600',
  defaultColor = '#FFFFFF',
  yOffset = 360,
  width = 1080,
}) => {
  if (!captions || captions.length === 0) return null;

  // Find active or recent window of 4-6 words around current time
  const activeIdx = captions.findIndex(
    (c) => currentSeconds >= c.start && currentSeconds <= c.end + 0.15
  );

  let displayWords: { word: string; active: boolean }[] = [];

  if (activeIdx !== -1) {
    const start = Math.max(0, activeIdx - 2);
    const end = Math.min(captions.length, activeIdx + 4);
    displayWords = captions.slice(start, end).map((c, i) => ({
      word: c.word,
      active: start + i === activeIdx,
    }));
  } else {
    // Check if within 0.4s of a word
    const nearby = captions.find(
      (c) => Math.abs(currentSeconds - c.start) < 0.35 || Math.abs(currentSeconds - c.end) < 0.35
    );
    if (!nearby) return null;
    const nIdx = captions.indexOf(nearby);
    const start = Math.max(0, nIdx - 2);
    const end = Math.min(captions.length, nIdx + 4);
    displayWords = captions.slice(start, end).map((c, i) => ({
      word: c.word,
      active: start + i === nIdx,
    }));
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: yOffset,
        left: 0,
        width: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 60,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: '12px 16px',
          maxWidth: width * 0.88,
          backgroundColor: 'rgba(12, 10, 20, 0.72)',
          padding: '14px 28px',
          borderRadius: '24px',
          border: '1.5px solid rgba(255, 255, 255, 0.18)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.55)',
          backdropFilter: 'blur(8px)',
        }}
      >
        {displayWords.map((item, i) => {
          return (
            <span
              key={i}
              style={{
                fontFamily:
                  '"Nirmala UI", "Noto Sans Devanagari", Impact, "Arial Black", sans-serif',
                fontSize: `${fontSize}px`,
                fontWeight: 900,
                letterSpacing: '0.5px',
                color: item.active ? activeColor : defaultColor,
                transform: item.active ? 'scale(1.14)' : 'scale(1.0)',
                transition: 'transform 0.08s ease-out, color 0.08s ease-out',
                textShadow: item.active
                  ? '0 0 16px rgba(255, 230, 0, 0.6), 2px 2px 6px #000'
                  : '2px 2px 4px #000',
                display: 'inline-block',
              }}
            >
              {item.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
