import React from 'react';
import { Composition } from 'remotion';
import { ReelComposition } from './compositions/ReelComposition';
import { AsteroidReel, asteroidDefaultProps } from './compositions/AsteroidReel';

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="Reel"
        component={ReelComposition}
        durationInFrames={1500}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={asteroidDefaultProps}
      />
      <Composition
        id="AsteroidImpact"
        component={AsteroidReel}
        durationInFrames={1500}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={asteroidDefaultProps}
      />
    </>
  );
};
