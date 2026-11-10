import React from 'react';
import { AbsoluteFill, Audio, staticFile, useCurrentFrame } from 'remotion';
import { Subtitles } from '../engine/subtitles';
import { Style3dCartoonRenderer } from '../styles/style3dCartoon';
import { Style2dColorfulRenderer } from '../styles/style2dColorful';
import { StyleAnimeRenderer } from '../styles/styleAnime';
import { StyleStickFigureRenderer } from '../styles/styleStickFigure';
import { StyleEducationalRenderer } from '../styles/styleEducational';
import { ReelTimelineProps } from '../types';

export const ReelComposition: React.FC<ReelTimelineProps> = (props) => {
  const {
    style = '3d_cartoon',
    width = 1080,
    height = 1920,
    fps = 30,
    shots = [],
    audio,
    captions = [],
  } = props;

  const frame = useCurrentFrame();
  const currentSeconds = frame / fps;

  // Find active shot
  const activeShot =
    shots.find(
      (s) => frame >= s.startFrame && frame < s.startFrame + s.durationFrames
    ) || shots[shots.length - 1] || {
      id: 'default',
      index: 1,
      startFrame: 0,
      durationFrames: 90,
      background: 'space',
      style,
    };

  const shotRelativeFrame = Math.max(0, frame - activeShot.startFrame);
  const activeStyle = activeShot.style || style;

  // Render appropriate style
  const renderStyle = () => {
    switch (activeStyle) {
      case '2d_colorful':
        return <Style2dColorfulRenderer shot={activeShot} frame={shotRelativeFrame} width={width} height={height} />;
      case 'anime':
        return <StyleAnimeRenderer shot={activeShot} frame={shotRelativeFrame} width={width} height={height} />;
      case 'stick_figure':
        return <StyleStickFigureRenderer shot={activeShot} frame={shotRelativeFrame} width={width} height={height} />;
      case 'educational_motion':
        return <StyleEducationalRenderer shot={activeShot} frame={shotRelativeFrame} width={width} height={height} />;
      case '3d_cartoon':
      default:
        return <Style3dCartoonRenderer shot={activeShot} frame={shotRelativeFrame} width={width} height={height} />;
    }
  };

  return (
    <AbsoluteFill style={{ width, height, backgroundColor: '#000000', overflow: 'hidden' }}>
      {/* Visual Animation */}
      {renderStyle()}

      {/* Kinetic Subtitles */}
      <Subtitles
        currentSeconds={currentSeconds}
        captions={captions}
        width={width}
      />

      {/* Audio Stems */}
      {audio?.voiceUrl && (
        <Audio
          src={audio.voiceUrl.startsWith('http') || audio.voiceUrl.startsWith('/') ? audio.voiceUrl : staticFile(audio.voiceUrl)}
          volume={1.0}
        />
      )}

      {audio?.musicUrl && (
        <Audio
          src={audio.musicUrl.startsWith('http') || audio.musicUrl.startsWith('/') ? audio.musicUrl : staticFile(audio.musicUrl)}
          volume={0.25}
        />
      )}
    </AbsoluteFill>
  );
};
