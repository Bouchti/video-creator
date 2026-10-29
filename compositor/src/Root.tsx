import React from 'react';
import {Composition} from 'remotion';
import {Short} from './Short';
import {ShortProps} from './types';

const defaults: ShortProps = {fps: 30, width: 1080, height: 1920, durationInFrames: 300};

export const Root: React.FC = () => (
  <Composition
    id="Short"
    component={Short}
    defaultProps={defaults}
    fps={30}
    width={1080}
    height={1920}
    durationInFrames={300}
    // the timeline JSON decides length, size and frame rate
    calculateMetadata={({props}) => ({
      durationInFrames: props.durationInFrames,
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
