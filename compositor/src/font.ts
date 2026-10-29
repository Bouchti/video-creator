import {loadFont} from '@remotion/google-fonts/Montserrat';

// One heavy geometric sans for everything: reads at phone size, holds a thick outline.
export const {fontFamily} = loadFont('normal', {weights: ['700', '800', '900'], subsets: ['latin']});

// Outline + soft drop shadow so white text survives any background (sky, water, snow).
export const outline = (px: number, color = '#000') =>
  [
    ...Array.from({length: 16}, (_, i) => {
      const a = (i / 16) * Math.PI * 2;
      return `${(Math.cos(a) * px).toFixed(1)}px ${(Math.sin(a) * px).toFixed(1)}px 0 ${color}`;
    }),
    `0 ${px * 1.6}px ${px * 3}px rgba(0,0,0,0.55)`,
  ].join(', ');
