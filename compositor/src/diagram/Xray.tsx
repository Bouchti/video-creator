// "X-ray vision": at a why-step the 3D picture dims to a blueprint and the step's diagram draws itself over
// the object (mode 'xray', centred on its tracked anchor) or on a full blueprint card (mode 'card').
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../font';
import {DIAGRAMS} from '../diagrams';
import {clamp, ZONES} from '../safe';
import {Arrow as KArrow, C, Canvas, ease, Label} from './kit';
import {at as trackAt} from '../Overlays';
import {DiagramCue, Track} from '../types';

export const SIZE = 1080; // diagram canvas (square, px)

/** The ready-made diagram when no generated one exists (or it failed review): the cause chain, step by step. */
export const ChainDiagram: React.FC<{t: number; steps: string[]}> = ({t, steps}) => {
  const n = Math.max(1, steps.length);
  const gap = SIZE / (n + 0.4);
  const per = Math.max(18, 60);
  return (
    <Canvas t={t} w={SIZE} h={SIZE}>
      {steps.map((s, i) => {
        const y = gap * (i + 0.7);
        return (
          <g key={i}>
            <Label x={SIZE / 2} y={y} text={s} at={i * per} tone={i === n - 1 ? 'accent' : 'white'} size={Math.min(70, 1800 / Math.max(8, s.length))} />
            {i < n - 1 ? <KArrow x1={SIZE / 2} y1={y + 55} x2={SIZE / 2} y2={y + gap - 60} at={i * per + 14} color={C.paper} /> : null}
          </g>
        );
      })}
    </Canvas>
  );
};

export const DiagramBody: React.FC<{cue: DiagramCue; t: number}> = ({cue, t}) => {
  const D = DIAGRAMS[cue.id];
  const dur = cue.to - cue.from;
  if (D) return <D t={t} dur={dur} w={SIZE} h={SIZE} />;
  return <ChainDiagram t={t} steps={cue.steps ?? []} />;
};

const Grid: React.FC<{opacity: number}> = ({opacity}) => (
  <AbsoluteFill
    style={{
      opacity,
      backgroundImage:
        'linear-gradient(rgba(140,200,255,0.16) 2px, transparent 2px), linear-gradient(90deg, rgba(140,200,255,0.16) 2px, transparent 2px)',
      backgroundSize: '60px 60px',
    }}
  />
);

export const XrayDiagram: React.FC<{cue: DiagramCue; track?: Track}> = ({cue, track}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  if (frame < cue.from || frame > cue.to) return null;
  const t = frame - cue.from;
  const inn = ease(frame, cue.from, 8);
  const out = interpolate(frame, [cue.to - 6, cue.to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const k = Math.min(inn, out);
  const card = cue.mode === 'card';
  const p = trackAt(track, frame);
  // between the step title (top) and the captions (66 %): over the object when it is tracked
  const cy = clamp((p ? p[1] : 0.4) * height, height * 0.38, height * 0.42);
  const scale = (width * 0.84) / SIZE;
  // the scan line that sweeps the x-ray on
  const scan = interpolate(frame, [cue.from, cue.from + 12], [0, height], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill style={{background: card ? '#123A6B' : 'rgba(14,40,80,0.9)', opacity: k}} />
      <Grid opacity={k} />
      {t < 14 ? (
        <div style={{position: 'absolute', left: 0, top: scan - 6, width, height: 12, background: '#9BE3FF', boxShadow: '0 0 30px #9BE3FF', opacity: 0.9}} />
      ) : null}
      <div
        style={{
          position: 'absolute',
          left: (width - SIZE * scale) / 2,
          top: cy - (SIZE * scale) / 2,
          width: SIZE,
          height: SIZE,
          transform: `scale(${scale})`,
          transformOrigin: '0 0',
          opacity: k,
        }}
      >
        <DiagramBody cue={cue} t={t} />
      </div>
      {cue.title ? (
        <div
          style={{
            position: 'absolute',
            top: height * ZONES.titleY,
            left: '50%',
            transform: `translate(-50%, -50%) scale(${k})`,
            padding: '14px 34px',
            background: C.accent,
            color: C.ink,
            borderRadius: 24,
            fontFamily,
            fontWeight: 900,
            fontSize: 58,
            textTransform: 'uppercase',
            whiteSpace: 'nowrap',
            boxShadow: '0 12px 30px rgba(0,0,0,0.4)',
          }}
        >
          {cue.title}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/** A single diagram on a blueprint background: the composition the diagram agent's stills are reviewed in. */
export const DiagramPreview: React.FC<{cue: DiagramCue}> = ({cue}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: '#123A6B'}}>
      <Grid opacity={1} />
      <DiagramBody cue={cue} t={frame} />
    </AbsoluteFill>
  );
};
