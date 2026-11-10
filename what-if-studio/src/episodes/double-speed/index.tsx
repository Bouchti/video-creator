import React from 'react';
import { defineEpisode, Timeline, LookDef, HudChip } from '../../engine';
import timeline from './timeline.json';
import { S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14 } from './shots';

// The power's look, DOUBLE: the picture cools and sharpens while Pip runs at twice the speed, a 2x chip blinks,
// and thin streaks race across the top and bottom of frame. The trails and afterimages are drawn in the shots.
const doubleLook: LookDef = {
  grade: (lv) => `saturate(${1 - 0.1 * lv}) hue-rotate(${-10 * lv}deg) contrast(${1 + 0.1 * lv}) brightness(${1 + 0.03 * lv})`,
  Overlay: ({ f, p }) => (
    <g>
      {Array.from({ length: 8 }).map((_, i) => {
        const y = i % 2 ? 40 + i * 22 : 1040 - i * 22;
        const x = ((f * 110 + i * 513) % 2600) - 300;
        return <path key={i} d={`M ${x} ${y} L ${x - 300} ${y}`} stroke="#DDF2FF" strokeWidth={3} opacity={0.3 * (1 - p * 0.5)} strokeLinecap="round" />;
      })}
      <HudChip f={f} label="2×" icon="skip" />
    </g>
  ),
};

export const doubleSpeed = defineEpisode('DoubleSpeed', {
  timeline: timeline as Timeline,
  shots: { S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14 },
  looks: { double: doubleLook },
});
