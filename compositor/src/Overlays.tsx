import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily, outline} from './font';
import {clamp, SAFE, ZONES} from './safe';
import {Arrow, Callout, Checklist, Label, Style, Title, Track} from './types';

const pop = (frame: number, from: number, to: number, fps: number) => {
  const inn = spring({frame: frame - from, fps, config: {damping: 12, mass: 0.6}});
  const out = interpolate(frame, [to - 6, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return Math.min(inn, out);
};

export const at = (track: Track | undefined, frame: number): [number, number] | null => {
  if (!track || !track.xy.length) return null;
  const i = clamp(frame - track.start, 0, track.xy.length - 1);
  const p = track.xy[Math.round(i)];
  return p && p[0] >= -0.2 && p[0] <= 1.2 && p[1] >= -0.2 && p[1] <= 1.2 ? p : null;
};

// Big hook question / chapter title in the top band: chunky white pill, slams in.
export const TitleCard: React.FC<{title: Title; style: Style; big?: boolean}> = ({title, style, big}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (frame < title.from || frame > title.to) return null;
  const k = pop(frame, title.from, title.to, fps);
  const size = height * (big ? 0.05 : 0.036);
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: height * ZONES.titleY,
          left: '50%',
          width: 'max-content',
          maxWidth: width * (1 - SAFE.left - SAFE.right),
          transform: `translate(-50%, -50%) scale(${interpolate(k, [0, 1], [1.4, 1])}) rotate(${big ? -2 : 0}deg)`,
          opacity: k,
          padding: `${size * 0.25}px ${size * 0.5}px`,
          background: big ? style.accent : 'white',
          borderRadius: size * 0.3,
          boxShadow: '0 12px 30px rgba(0,0,0,0.35)',
          fontFamily,
          fontWeight: 900,
          fontSize: size,
          lineHeight: 1.05,
          textAlign: 'center',
          textTransform: 'uppercase',
          color: '#111',
        }}
      >
        {title.text}
        {title.sub ? (
          <div style={{fontSize: size * 0.45, fontWeight: 700, marginTop: size * 0.1}}>{title.sub}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// A label pinned to a 3D anchor: dot on the part, leader line, pill above it, kept inside the safe area.
export const PinnedLabel: React.FC<{label: Label; track?: Track; style: Style}> = ({label, track, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (frame < label.from || frame > label.to) return null;
  const p = label.at ?? at(track, frame);
  if (!p) return null;
  const k = pop(frame, label.from, label.to, fps);
  const size = height * 0.026;
  const ax = p[0] * width;
  const ay = p[1] * height;
  const lx = clamp(ax, width * (SAFE.left + 0.16), width * (1 - SAFE.right - 0.16));
  const ly = clamp(ay - height * 0.11, height * ZONES.labelMinY, height * ZONES.labelMaxY);
  const lineLen = Math.hypot(ax - lx, ay - ly) * k;
  const angle = Math.atan2(ay - ly, ax - lx);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left: lx,
          top: ly,
          width: lineLen,
          height: 5,
          background: 'white',
          transformOrigin: '0 50%',
          transform: `rotate(${angle}rad)`,
          boxShadow: '0 0 6px rgba(0,0,0,0.6)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: ax - 14,
          top: ay - 14,
          width: 28,
          height: 28,
          borderRadius: 14,
          background: style.accent,
          border: '5px solid white',
          transform: `scale(${k})`,
          boxShadow: '0 0 10px rgba(0,0,0,0.5)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: lx,
          top: ly,
          transform: `translate(-50%, -50%) scale(${k})`,
          padding: `${size * 0.22}px ${size * 0.55}px`,
          background: 'white',
          borderRadius: size,
          fontFamily,
          fontWeight: 800,
          fontSize: size,
          whiteSpace: 'nowrap',
          textTransform: 'uppercase',
          color: '#111',
          boxShadow: '0 8px 20px rgba(0,0,0,0.35)',
          borderBottom: `${size * 0.16}px solid ${style.accent}`,
        }}
      >
        {label.text}
      </div>
    </AbsoluteFill>
  );
};

// "3-5 YEARS" counters and FAIL / FIXED stamps.
export const CalloutCard: React.FC<{callout: Callout; style: Style}> = ({callout, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (frame < callout.from || frame > callout.to) return null;
  const k = pop(frame, callout.from, callout.to, fps);
  const color = callout.tone === 'bad' ? style.bad : callout.tone === 'good' ? style.good : style.accent;
  const stamp = callout.kind === 'stamp';
  // shrink long words so the card always fits inside the safe width
  const fit = (width * 0.62) / (Math.max(4, callout.text.length) * 0.7);
  const size = Math.min(height * (stamp ? 0.06 : 0.07), fit);
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: height * ZONES.calloutY,
          left: '50%',
          whiteSpace: 'nowrap',
          transform: `translate(-50%, -50%) scale(${interpolate(k, [0, 1], [stamp ? 1.3 : 0.6, 1])}) rotate(${stamp ? -8 : 0}deg)`,
          opacity: k,
          fontFamily,
          fontWeight: 900,
          fontSize: size,
          color: stamp ? color : 'white',
          border: stamp ? `${size * 0.1}px solid ${color}` : undefined,
          borderRadius: size * 0.2,
          padding: stamp ? `0 ${size * 0.3}px` : undefined,
          textTransform: 'uppercase',
          textShadow: stamp ? undefined : outline(size * 0.06, color === style.accent ? '#000' : color),
          background: stamp ? 'rgba(255,255,255,0.85)' : undefined,
          maxWidth: width * 0.8,
          textAlign: 'center',
        }}
      >
        {callout.text}
      </div>
    </AbsoluteFill>
  );
};

// The takeaway: rules tick in one by one on the words, on a dark card in the upper half.
export const ChecklistCard: React.FC<{list: Checklist; style: Style}> = ({list, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (frame < list.from || frame > list.to) return null;
  const k = pop(frame, list.from, list.to, fps);
  const size = height * 0.03;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: height * 0.1,
          left: width * SAFE.left,
          width: width * (1 - SAFE.left - SAFE.right),
          padding: size * 0.8,
          borderRadius: size * 0.7,
          background: 'rgba(12,14,20,0.82)',
          boxShadow: '0 20px 50px rgba(0,0,0,0.4)',
          transform: `translateY(${interpolate(k, [0, 1], [-40, 0])}px)`,
          opacity: k,
          fontFamily,
        }}
      >
        {list.title ? (
          <div style={{color: style.accent, fontWeight: 900, fontSize: size * 0.85, marginBottom: size * 0.4, textTransform: 'uppercase'}}>
            {list.title}
          </div>
        ) : null}
        {list.items.map((it, i) => {
          const on = spring({frame: frame - it.from, fps, config: {damping: 12, mass: 0.5}});
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: size * 0.5,
                margin: `${size * 0.35}px 0`,
                opacity: interpolate(on, [0, 1], [0.25, 1]),
                transform: `translateX(${interpolate(on, [0, 1], [30, 0])}px)`,
              }}
            >
              <div
                style={{
                  width: size * 1.25,
                  height: size * 1.25,
                  borderRadius: size * 0.3,
                  background: frame >= it.from ? style.good : 'rgba(255,255,255,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#0b0d12',
                  fontWeight: 900,
                  fontSize: size,
                  transform: `scale(${interpolate(on, [0, 1], [0.6, 1])})`,
                  flexShrink: 0,
                }}
              >
                {frame >= it.from ? '✓' : ''}
              </div>
              <div style={{color: 'white', fontWeight: 800, fontSize: size, lineHeight: 1.1}}>{it.text}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// An explanation arrow on a prop (which way it leans, turns, is pushed, spins): a ring pulses on the object,
// then a thick arrow draws itself across it and its caption pops beside the head. It follows the object.
export const ExplainArrow: React.FC<{arrow: Arrow; track?: Track; style: Style}> = ({arrow, track, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (frame < arrow.from || frame > arrow.to) return null;
  const p = at(track, frame);
  if (!p) return null;
  const k = pop(frame, arrow.from, arrow.to, fps);
  const draw = interpolate(frame, [arrow.from + 4, arrow.from + 18], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cx = clamp(p[0] * width, width * (SAFE.left + 0.12), width * (1 - SAFE.right - 0.12));
  // ON the object (labels stop at labelMaxY; an arrow up there floated over the house, not the bike)
  const cy = clamp(p[1] * height, height * (SAFE.top + 0.1), height * ZONES.arrowMaxY);
  const L = width * 0.36;
  const stroke = width * 0.022;
  let d: string;
  let head: [number, number, number]; // x, y, direction (rad)
  if (arrow.dir === 'cw' || arrow.dir === 'ccw') {
    const r = width * 0.15;
    const sweep = 1.5 * Math.PI * draw;
    const a0 = -Math.PI * 0.75;
    const s = arrow.dir === 'cw' ? 1 : -1;
    const a1 = a0 + s * sweep;
    const x0 = cx + r * Math.cos(a0);
    const y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy + r * Math.sin(a1);
    d = `M ${x0} ${y0} A ${r} ${r} 0 ${sweep > Math.PI ? 1 : 0} ${s > 0 ? 1 : 0} ${x1} ${y1}`;
    head = [x1, y1, a1 + (s * Math.PI) / 2];
  } else {
    const v = {left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1]}[arrow.dir];
    const x0 = cx - (v[0] * L) / 2;
    const y0 = cy - (v[1] * L) / 2;
    const x1 = x0 + v[0] * L * draw;
    const y1 = y0 + v[1] * L * draw;
    d = `M ${x0} ${y0} L ${x1} ${y1}`;
    head = [x1, y1, Math.atan2(v[1], v[0])];
  }
  const hs = stroke * 2.2;
  const tip = (dx: number, dy: number) =>
    `${head[0] + dx * Math.cos(head[2]) - dy * Math.sin(head[2])},${head[1] + dx * Math.sin(head[2]) + dy * Math.cos(head[2])}`;
  const tri = `${tip(hs * 0.9, 0)} ${tip(-hs * 0.5, hs * 0.8)} ${tip(-hs * 0.5, -hs * 0.8)}`;
  const ring = interpolate(frame, [arrow.from, arrow.from + 14], [0.4, 1.25], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const ringFade = interpolate(frame, [arrow.from, arrow.from + 14], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const size = height * 0.026;
  const tx = clamp(head[0], width * (SAFE.left + 0.14), width * (1 - SAFE.right - 0.14));
  const ty = clamp(head[1] + (arrow.dir === 'down' ? size * 2 : -size * 2), height * ZONES.labelMinY, height * ZONES.labelMaxY);
  return (
    <AbsoluteFill style={{opacity: k}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <circle cx={cx} cy={cy} r={width * 0.12 * ring} fill="none" stroke="white" strokeWidth={8} opacity={ringFade} />
        <path d={d} fill="none" stroke="#111" strokeWidth={stroke + 10} strokeLinecap="round" opacity={0.55} />
        <path d={d} fill="none" stroke={style.accent} strokeWidth={stroke} strokeLinecap="round" />
        {draw > 0.05 ? <polygon points={tri} fill={style.accent} stroke="#111" strokeWidth={5} strokeLinejoin="round" /> : null}
      </svg>
      {arrow.text && draw > 0.6 ? (
        <div
          style={{
            position: 'absolute',
            left: tx,
            top: ty,
            transform: `translate(-50%, -50%) scale(${interpolate(draw, [0.6, 1], [0.6, 1])})`,
            padding: `${size * 0.22}px ${size * 0.55}px`,
            background: style.accent,
            borderRadius: size,
            fontFamily,
            fontWeight: 900,
            fontSize: size,
            whiteSpace: 'nowrap',
            textTransform: 'uppercase',
            color: '#111',
            boxShadow: '0 8px 20px rgba(0,0,0,0.35)',
          }}
        >
          {arrow.text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
