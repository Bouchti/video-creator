// The house design library for explanation diagrams. Generated diagrams (src/diagrams/generated/*.tsx) are
// written by an AI agent and may ONLY use what this file exports + React: one look for every film, and
// every primitive animates from the diagram's local frame, so a still at any frame is deterministic.
//
// Coordinates: an SVG canvas of w x h pixels (1080 x 1080 by default), origin top-left, y down.
// Every primitive takes `at` (the local frame it starts drawing) and reads the current frame from context.
import React, {createContext, useContext} from 'react';
import {fontFamily} from '../font';

export type DiagramProps = {t: number; dur: number; w: number; h: number};

export const C = {
  ink: '#1B1F2A', // outlines, text
  paper: '#FFFFFF',
  accent: '#FFD23F', // the thing to look at
  good: '#3DDC84',
  bad: '#FF4D4D',
  water: '#3FA9F5',
  air: '#BFE6FF',
  heat: '#FF7A1A',
  cold: '#7FD8FF',
  metal: '#A9B4C2',
  wood: '#C98B4E',
  skin: '#F4B183',
  plant: '#4CAF50',
  ground: '#8D6E4C',
  purple: '#9B6CFF',
  pink: '#FF6FB1',
};
export const STROKE = 10; // the house line weight (px on a 1080 canvas)

// ---------------------------------------------------------------- timing helpers
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
/** 0 -> 1 between frame `at` and `at + len`, eased (smooth start and end). */
export const ease = (t: number, at: number, len = 15) => {
  const x = clamp01((t - at) / Math.max(1, len));
  return x * x * (3 - 2 * x);
};
/** 0 -> 1 with a small overshoot (things that pop in). */
export const pop = (t: number, at: number, len = 12) => {
  const x = clamp01((t - at) / Math.max(1, len));
  if (x >= 1) return 1;
  const s = 1.70158;
  const y = x - 1;
  return 1 + (s + 1) * y * y * y + s * y * y;
};
/** a -> b between `at` and `at + len` (eased). */
export const lerp = (t: number, at: number, len: number, a: number, b: number) => a + (b - a) * ease(t, at, len);
/** A repeating 0..1 cycle every `period` frames from `at` (0 before). For flows, spins, pulses. */
export const loop = (t: number, at: number, period = 30) => (t < at ? 0 : ((t - at) % period) / period);

const Time = createContext(0);
/** The current local frame (inside a Canvas). */
export const useT = () => useContext(Time);

// ---------------------------------------------------------------- canvas
/** The diagram's root: every generated diagram returns exactly one <Canvas t={t} w={w} h={h}>. */
export const Canvas: React.FC<{t: number; w: number; h: number; children?: React.ReactNode}> = ({t, w, h, children}) => (
  <Time.Provider value={t}>
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{overflow: 'visible'}}>
      <defs>
        <filter id="kit-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#000" floodOpacity="0.35" />
        </filter>
      </defs>
      {children}
    </svg>
  </Time.Provider>
);

/** Moves / rotates / scales its children (rotation in degrees around the group's own origin x, y). */
export const Group: React.FC<{x?: number; y?: number; rotate?: number; scale?: number; opacity?: number; children?: React.ReactNode}> = ({
  x = 0,
  y = 0,
  rotate = 0,
  scale = 1,
  opacity = 1,
  children,
}) => (
  <g transform={`translate(${x} ${y}) rotate(${rotate}) scale(${scale})`} opacity={opacity}>
    {children}
  </g>
);

// ---------------------------------------------------------------- shapes: they draw themselves on at `at`
type Paint = {fill?: string; stroke?: string; width?: number; at?: number; len?: number; opacity?: number};

/** Any SVG path `d`: the outline is drawn on like a pen from `at` over `len` frames, then the fill fades in. */
export const Path: React.FC<Paint & {d: string; dashed?: boolean}> = ({
  d,
  fill = 'none',
  stroke = C.ink,
  width = STROKE,
  at = 0,
  len = 18,
  opacity = 1,
  dashed,
}) => {
  const t = useT();
  const k = ease(t, at, len);
  if (k <= 0) return null;
  const f = fill === 'none' ? 0 : ease(t, at + len * 0.6, len * 0.6);
  return (
    <g opacity={opacity}>
      {fill !== 'none' ? <path d={d} fill={fill} opacity={f} /> : null}
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={width}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        strokeDasharray={dashed ? '0.03 0.03' : '1 1'}
        strokeDashoffset={dashed ? 0 : 1 - k}
        opacity={dashed ? k : 1}
      />
    </g>
  );
};

const rectD = (x: number, y: number, w: number, h: number, r: number) =>
  `M ${x + r} ${y} H ${x + w - r} Q ${x + w} ${y} ${x + w} ${y + r} V ${y + h - r} Q ${x + w} ${y + h} ${x + w - r} ${y + h}` +
  ` H ${x + r} Q ${x} ${y + h} ${x} ${y + h - r} V ${y + r} Q ${x} ${y} ${x + r} ${y} Z`;

/** A rounded box (x, y = top-left). */
export const Box: React.FC<Paint & {x: number; y: number; w: number; h: number; r?: number}> = ({x, y, w, h, r = 18, ...p}) => (
  <Path d={rectD(x, y, w, h, Math.min(r, w / 2, h / 2))} {...p} />
);

/** A circle (cx, cy = centre). */
export const Circle: React.FC<Paint & {cx: number; cy: number; r: number}> = ({cx, cy, r, ...p}) => (
  <Path d={`M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`} {...p} />
);

/** A straight line. */
export const Line: React.FC<Paint & {x1: number; y1: number; x2: number; y2: number; dashed?: boolean}> = ({x1, y1, x2, y2, ...p}) => (
  <Path d={`M ${x1} ${y1} L ${x2} ${y2}`} {...p} />
);

/** A smooth line through points [[x, y], ...] (closed = a filled blob). */
export const Curve: React.FC<Paint & {points: [number, number][]; closed?: boolean}> = ({points, closed, ...p}) => {
  if (points.length < 2) return null;
  let d = `M ${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length; i++) {
    const [x0, y0] = points[i - 1];
    const [x1, y1] = points[i];
    d += ` Q ${x0} ${y0} ${(x0 + x1) / 2} ${(y0 + y1) / 2}`;
  }
  const last = points[points.length - 1];
  d += ` L ${last[0]} ${last[1]}${closed ? ' Z' : ''}`;
  return <Path d={d} {...p} />;
};

// ---------------------------------------------------------------- explaining
/** A thick arrow from (x1, y1) to (x2, y2) that shoots out at `at`; optional bend (px, + bends left of travel). */
export const Arrow: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color?: string;
  at?: number;
  len?: number;
  bend?: number;
  width?: number;
}> = ({x1, y1, x2, y2, color = C.accent, at = 0, len = 14, bend = 0, width = STROKE * 2}) => {
  const t = useT();
  const k = ease(t, at, len);
  if (k <= 0) return null;
  const mx = (x1 + x2) / 2 - ((y2 - y1) / Math.hypot(x2 - x1, y2 - y1 || 1)) * bend;
  const my = (y1 + y2) / 2 + ((x2 - x1) / Math.hypot(x2 - x1 || 1, y2 - y1)) * bend;
  // the point reached so far along the quadratic curve, and the direction there
  const q = (s: number) => [
    (1 - s) * (1 - s) * x1 + 2 * (1 - s) * s * mx + s * s * x2,
    (1 - s) * (1 - s) * y1 + 2 * (1 - s) * s * my + s * s * y2,
  ];
  const steps = 24;
  let d = `M ${x1} ${y1}`;
  for (let i = 1; i <= steps; i++) {
    const [x, y] = q((i / steps) * k);
    d += ` L ${x} ${y}`;
  }
  const [hx, hy] = q(k);
  const [px, py] = q(Math.max(0, k - 0.02));
  const a = Math.atan2(hy - py, hx - px);
  const hs = width * 1.5;
  const pt = (dx: number, dy: number) => `${hx + dx * Math.cos(a) - dy * Math.sin(a)},${hy + dx * Math.sin(a) + dy * Math.cos(a)}`;
  return (
    <g>
      <path d={d} fill="none" stroke={C.ink} strokeWidth={width + 10} strokeLinecap="round" strokeLinejoin="round" />
      <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
      <polygon points={`${pt(hs * 0.9, 0)} ${pt(-hs * 0.55, hs * 0.85)} ${pt(-hs * 0.55, -hs * 0.85)}`} fill={color} stroke={C.ink} strokeWidth={5} strokeLinejoin="round" />
    </g>
  );
};

/** A word or two in a pill at (x, y) (its centre), popping in at `at`. tone: accent / good / bad / white. */
export const Label: React.FC<{x: number; y: number; text: string; at?: number; tone?: 'accent' | 'good' | 'bad' | 'white'; size?: number}> = ({
  x,
  y,
  text,
  at = 0,
  tone = 'white',
  size = 44,
}) => {
  const t = useT();
  const k = pop(t, at);
  if (k <= 0) return null;
  const bg = {accent: C.accent, good: C.good, bad: C.bad, white: C.paper}[tone];
  const w = text.length * size * 0.66 + size * 1.1;
  const h = size * 1.6;
  return (
    <g transform={`translate(${x} ${y}) scale(${k})`} filter="url(#kit-shadow)">
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={h / 2} fill={bg} stroke={C.ink} strokeWidth={5} />
      <text x={0} y={size * 0.36} textAnchor="middle" fontFamily={fontFamily} fontWeight={900} fontSize={size} fill={C.ink}>
        {text.toUpperCase()}
      </text>
    </g>
  );
};

/** A big number that counts from `from` to `to` (e.g. 0 -> 120 "°C"). */
export const Counter: React.FC<{x: number; y: number; from: number; to: number; unit?: string; at?: number; len?: number; size?: number; color?: string}> = ({
  x,
  y,
  from,
  to,
  unit = '',
  at = 0,
  len = 30,
  size = 120,
  color = C.accent,
}) => {
  const t = useT();
  if (t < at) return null;
  const v = from + (to - from) * ease(t, at, len);
  const s = pop(t, at, 10);
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <text x={0} y={0} textAnchor="middle" fontFamily={fontFamily} fontWeight={900} fontSize={size} fill={color} stroke={C.ink} strokeWidth={8} paintOrder="stroke">
        {`${Math.round(v)}${unit}`}
      </text>
    </g>
  );
};

/** Dots streaming along a polyline [[x, y], ...]: water, air, heat, electricity, blood... */
export const Flow: React.FC<{points: [number, number][]; color?: string; at?: number; speed?: number; count?: number; r?: number}> = ({
  points,
  color = C.water,
  at = 0,
  speed = 1,
  count = 8,
  r = 14,
}) => {
  const t = useT();
  if (t < at || points.length < 2) return null;
  const segs = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]));
  const total = segs.reduce((a, b) => a + b, 0) || 1;
  const fade = ease(t, at, 10);
  const dots = [];
  for (let i = 0; i < count; i++) {
    let s = (((t - at) * 6 * speed) / total + i / count) % 1;
    let d = s * total;
    let k = 0;
    while (k < segs.length - 1 && d > segs[k]) {
      d -= segs[k];
      k++;
    }
    const f = segs[k] ? d / segs[k] : 0;
    const x = points[k][0] + (points[k + 1][0] - points[k][0]) * f;
    const y = points[k][1] + (points[k + 1][1] - points[k][1]) * f;
    s = Math.min(1, Math.min(s, 1 - s) * 8); // fade at both ends
    dots.push(<circle key={i} cx={x} cy={y} r={r} fill={color} stroke={C.ink} strokeWidth={4} opacity={fade * s} />);
  }
  return <g>{dots}</g>;
};

/** An expanding ring that says "look here" at `at`. */
export const Pulse: React.FC<{cx: number; cy: number; r?: number; at?: number; color?: string}> = ({cx, cy, r = 80, at = 0, color = C.accent}) => {
  const t = useT();
  const k = ease(t, at, 18);
  if (k <= 0 || k >= 1) return null;
  return <circle cx={cx} cy={cy} r={r * (0.5 + k)} fill="none" stroke={color} strokeWidth={10} opacity={1 - k} />;
};

/** A cross (wrong) or a tick (right) stamped at (x, y). */
export const Mark: React.FC<{x: number; y: number; ok: boolean; at?: number; size?: number}> = ({x, y, ok, at = 0, size = 90}) => {
  const t = useT();
  const k = pop(t, at);
  if (k <= 0) return null;
  const s = size / 2;
  return (
    <g transform={`translate(${x} ${y}) scale(${k})`} filter="url(#kit-shadow)">
      <circle r={s * 1.2} fill={ok ? C.good : C.bad} stroke={C.ink} strokeWidth={6} />
      <path
        d={ok ? `M ${-s * 0.55} 0 L ${-s * 0.1} ${s * 0.45} L ${s * 0.6} ${-s * 0.5}` : `M ${-s * 0.5} ${-s * 0.5} L ${s * 0.5} ${s * 0.5} M ${s * 0.5} ${-s * 0.5} L ${-s * 0.5} ${s * 0.5}`}
        fill="none"
        stroke={C.paper}
        strokeWidth={s * 0.28}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </g>
  );
};
