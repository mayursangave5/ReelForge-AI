export type AnimationStyle =
  | '3d_cartoon'
  | '2d_colorful'
  | 'anime'
  | 'stick_figure'
  | 'educational_motion';

export type CameraCue = {
  zoom?: number;
  panX?: number;
  panY?: number;
  shake?: number;
  tilt?: number;
  durationFrames?: number;
};

export type VfxCue = {
  frame: number;
  type: 'flash' | 'shake' | 'shockwave' | 'debris' | 'speedlines' | 'plasma_trail';
  color?: string;
  intensity?: number;
};

export type SfxCue = {
  frame: number;
  clip: string;
  volume?: number;
};

export type WordCue = {
  word: string;
  start: number; // seconds
  end: number;   // seconds
};

export type ShotDefinition = {
  id: string;
  index: number;
  startFrame: number;
  durationFrames: number;
  narration?: string;
  visualPrompt?: string;
  background?: string;
  characterAction?: string;
  camera?: CameraCue;
  vfx?: VfxCue[];
  sfx?: SfxCue[];
  style?: AnimationStyle;
};

export type ReelTimelineProps = {
  title: string;
  topic?: string;
  style: AnimationStyle;
  fps: number;
  width: number;
  height: number;
  totalDurationFrames: number;
  shots: ShotDefinition[];
  audio?: {
    voiceUrl?: string;
    musicUrl?: string;
    sfxUrls?: Record<string, string>;
  };
  captions?: WordCue[];
};
