import React from 'react';
import {AbsoluteFill, Audio, Freeze, interpolate, OffthreadVideo, random, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from './font';
import {Captions} from './Captions';
import {CalloutCard, ChecklistCard, PinnedLabel, TitleCard} from './Overlays';
import {DEFAULT_STYLE, PunchIn, Rewind, ShortProps} from './types';

// Punch-in zoom on the beauty pass (towards a focus point), sprung in and out.
const zoomAt = (frame: number, fps: number, punches: PunchIn[]) => {
  let scale = 1;
  let focus: [number, number] = [0.5, 0.45];
  for (const p of punches) {
    if (frame < p.from - 1 || frame > p.to + 8) continue;
    const inn = spring({frame: frame - p.from, fps, config: {damping: 15, mass: 0.7}});
    const out = spring({frame: frame - p.to, fps, config: {damping: 18}});
    scale = 1 + ((p.scale ?? 1.18) - 1) * Math.max(0, inn - out);
    focus = p.focus ?? focus;
  }
  return {scale, focus};
};

const Grain: React.FC<{strength: number}> = ({strength}) => {
  const frame = useCurrentFrame();
  const seed = Math.floor(random(`g${frame}`) * 1000);
  return (
    <AbsoluteFill style={{opacity: strength, mixBlendMode: 'overlay', pointerEvents: 'none'}}>
      <svg width="100%" height="100%">
        <filter id={`n${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#n${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

const RewindFx: React.FC<{r: Rewind}> = ({r}) => {
  const frame = useCurrentFrame();
  if (frame < r.from || frame > r.to) return null;
  const jitter = (random(`j${frame}`) - 0.5) * 18;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill
        style={{
          background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 3px, transparent 3px, transparent 7px)',
          mixBlendMode: 'multiply',
        }}
      />
      <AbsoluteFill style={{background: 'rgba(40,80,255,0.12)', mixBlendMode: 'screen'}} />
      <div
        style={{
          position: 'absolute',
          top: 210 + jitter,
          left: 70,
          fontFamily,
          fontWeight: 900,
          fontSize: 92,
          color: 'white',
          textShadow: '4px 0 0 rgba(255,0,80,0.8), -4px 0 0 rgba(0,220,255,0.8)',
          opacity: frame % 10 < 7 ? 1 : 0.35,
        }}
      >
        {'◀◀ REWIND'}
      </div>
    </AbsoluteFill>
  );
};

export const Short: React.FC<ShortProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const style = {...DEFAULT_STYLE, ...(props.style ?? {})};
  const {scale, focus} = zoomAt(frame, fps, props.punchIns ?? []);
  const vignette = interpolate(scale, [1, 1.3], [0.28, 0.42]);
  const r = props.rewind;
  const rewinding = !!r && frame >= r.from && frame <= r.to;
  const source = r
    ? Math.round(interpolate(frame, [r.from, r.to], [r.sourceFrom, r.sourceTo], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}))
    : 0;
  const g = props.grade ?? {};
  const filter = `saturate(${g.saturate ?? 1}) contrast(${g.contrast ?? 1}) brightness(${g.brightness ?? 1})`;

  return (
    <AbsoluteFill style={{backgroundColor: '#0b0d12'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: `${focus[0] * 100}% ${focus[1] * 100}%`, filter}}>
        {props.video ? (
          <Freeze frame={source} active={rewinding}>
            <OffthreadVideo src={staticFile(props.video)} muted />
          </Freeze>
        ) : null}
      </AbsoluteFill>
      {r ? <RewindFx r={r} /> : null}
      <AbsoluteFill
        style={{background: `radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,${vignette}) 100%)`}}
      />
      {props.grain ? <Grain strength={props.grain} /> : null}

      {(props.labels ?? []).map((l, i) => (
        <PinnedLabel key={`l${i}`} label={l} track={l.anchor ? props.anchors?.[l.anchor] : undefined} style={style} />
      ))}
      {(props.callouts ?? []).map((c, i) => (
        <CalloutCard key={`c${i}`} callout={c} style={style} />
      ))}
      {(props.chapters ?? []).map((c, i) => (
        <TitleCard key={`t${i}`} title={c} style={style} />
      ))}
      {props.checklist ? <ChecklistCard list={props.checklist} style={style} /> : null}
      {props.hook ? <TitleCard title={props.hook} style={style} big /> : null}
      {props.endCard ? <TitleCard title={props.endCard} style={style} big /> : null}
      {props.words?.length ? <Captions words={props.words} style={style} /> : null}

      {props.audio ? <Audio src={staticFile(props.audio)} /> : null}
    </AbsoluteFill>
  );
};
