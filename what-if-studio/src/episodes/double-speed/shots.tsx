import React from 'react';
import {
  Hero, Mug, Pose, basePose, poseAt, faceAt, kf, clamp, lerp, easeOut, easeIn, backOut, settle, camT, LOOKS, LEG_LEN, HEAD, joints, toWorld, rnd,
  Kitchen, KitchenIsland, KITCHEN, islandTop, stand, Stairwell, Banister, SW, stepTop, hipGround, Classroom, CLS, Rooftop, Schematic, SCH, Arrow,
  SchLabel, CountUp, Foreground, Sparkle, TitleCard, Glow, ShotProps,
} from '../../engine';

// "What if you could move at double speed?" Fourteen shots on four sets (kitchen, stairwell, classroom, rooftop) and
// the schematic. The power: Pip switches to twice his speed; he leaves a trail of cool afterimages and speed streaks,
// and the world around him looks slowed. Each shot is a pure function of its own clock t.

const PIP = LOOKS.pipHood;
const MO = LOOKS.mo;
const ICE = '#9FE6FF';

/** A run in profile: walkPose with a longer stride, a forward lean and pumping arms. */
const runPose = (x: number, phase: number, ground: number | ((x: number) => number), scale: number, facing: 1 | -1 = 1, extra: Partial<Pose> = {}): Pose => {
  const s = Math.sin(phase);
  const g = typeof ground === 'number' ? ground : ground(x);
  return {
    ...basePose,
    x,
    y: g - LEG_LEN * scale * 0.96 - Math.abs(Math.cos(phase)) * 12 * scale,
    scale,
    facing,
    yaw: facing,
    tilt: 14 * facing,
    headTilt: 3 * Math.sin(phase * 2),
    sway: 16 * Math.sin(phase + 0.8),
    legL: { a: 50 * s, b: -Math.max(0, 75 * Math.sin(phase + 1.2)) },
    legR: { a: -50 * s, b: -Math.max(0, 75 * Math.sin(phase + 1.2 + Math.PI)) },
    armL: { a: -45 * s, b: 70 },
    armR: { a: 45 * s, b: 70 },
    ...extra,
  };
};

/** The power's trail: fading cool copies of the hero at earlier moments of the same clock (pure: each is pose(t - k)). */
const Trail: React.FC<{ t: number; pose: (t: number) => Pose; n?: number; gap?: number; o?: number; look?: typeof PIP }> = ({ t, pose, n = 6, gap = 1, o = 0.55, look = PIP }) => (
  <g>
    {Array.from({ length: n }).map((_, i) => {
      const k = n - i;
      return (
        <g key={k} opacity={o * (1 - k / (n + 1))} style={{ mixBlendMode: 'screen' }}>
          <g filter="url(#blur3)">
            <Hero look={{ ...look, jacket: '#5FA8D8', jacketShade: '#4A8CBC', limb: '#5FA8D8', line: '#2C5F8A' }} pose={pose(t - k * gap)} shadow={0} rimId="rimR" />
          </g>
        </g>
      );
    })}
  </g>
);

/** Speed streaks: horizontal light lines behind a moving point (dir 1 = moving right, so the streaks trail left). */
const Streaks: React.FC<{ x: number; y: number; t: number; dir?: 1 | -1; len?: number; h?: number; n?: number; o?: number; slope?: number }> = ({ x, y, t, dir = 1, len = 520, h = 260, n = 9, o = 0.8, slope = 0 }) => (
  <g style={{ mixBlendMode: 'screen' }}>
    {Array.from({ length: n }).map((_, i) => {
      const yy = y - h / 2 + (h * (i + 0.5)) / n + (rnd(i, 3) - 0.5) * 20;
      const l = len * (0.45 + 0.55 * rnd(i, 5 + Math.floor(t / 2)));
      const x0 = x - dir * (40 + rnd(i, 7) * 60);
      return <path key={i} d={`M ${x0} ${yy} L ${x0 - dir * l} ${yy + slope * l}`} stroke={i % 3 ? ICE : '#FFFFFF'} strokeWidth={i % 3 ? 5 : 3} strokeLinecap="round" opacity={o * (0.4 + 0.6 * rnd(i, 9))} />;
    })}
  </g>
);

// ---------- S1: medium, the kitchen island: Pip's elbow knocks the mug off the front edge ----------
const S1_STAND = stand(KITCHEN, 0.42, 0.4);
const S1_MUG = islandTop(0.56, 0.98);
const s1Mug = (t: number) => {
  const f = Math.max(0, t - 9);
  return { x: S1_MUG.x + f * 3.2, y: S1_MUG.y + 0.32 * f * f, rot: Math.min(f * 6, 110) };
};
export const S1: React.FC<ShotProps> = ({ t, len }) => {
  const base: Partial<Pose> = { x: S1_STAND.x, y: S1_STAND.y, scale: S1_STAND.scale, yaw: 0.5, look: 0.5, armL: { a: 12, b: -8 } };
  const pose = poseAt(t, [
    { f: 0, p: { ...base, armR: { a: 40, b: 60 }, headTilt: -4 } },
    { f: 6, p: { armR: { a: 64, b: 30 } } },
    { f: 9, p: { armR: { a: 92, b: 12 }, tilt: 4 }, ease: easeOut },
    { f: 14, p: { armR: { a: 70, b: 30 }, look: 1, headTilt: 10, tilt: 0 } },
  ]);
  const face = faceAt(t, [[0, 'happy'], [12, 'shock']]);
  const m = s1Mug(t);
  return (
    <g transform={camT(kf(t, [[0, 990], [len, 1010]]), kf(t, [[0, 600], [len, 620]]), kf(t, [[0, 1.85], [len, 1.95]]))}>
      <Kitchen t={t + 40} id="k1" />
      <Hero look={PIP} pose={{ ...pose, ...face }} rimId="rimR" shadow={0} />
      <KitchenIsland />
      {t < 10 ? <ellipse cx={S1_MUG.x} cy={S1_MUG.y + 2} rx={30} ry={7} fill="#000" opacity={0.3} /> : null}
      <g transform={`translate(${m.x} ${m.y}) scale(1.25) translate(${-m.x} ${-m.y})`}>
        <Mug x={m.x} y={m.y} rot={m.rot} f={t} steam={t < 9 ? 1 : 0} />
      </g>
      {t > 11 ? <path d={`M ${m.x - 40} ${m.y - 70} q -10 -24 4 -40 M ${m.x + 34} ${m.y - 80} q 12 -20 0 -40`} stroke="#F6EFE3" strokeWidth={4} fill="none" opacity={0.7} strokeLinecap="round" /> : null}
      <Foreground blur={10}>
        <path d="M 1260 1000 Q 1300 760 1420 700 Q 1380 820 1400 1000 Z" fill="#0E1610" />
        <path d="M 1330 1000 Q 1420 800 1560 760 Q 1480 860 1470 1000 Z" fill="#0C130E" />
      </Foreground>
    </g>
  );
};

// ---------- S2: macro insert, low angle: the mug mid-fall; the mitten streaks in and catches it ----------
const BigMug: React.FC<{ x: number; y: number; rot: number; slosh: number }> = ({ x, y, rot, slosh }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(5.2)`}>
    <path d="M 22 -40 q 22 2 18 18 q -4 12 -18 10" stroke="#C8C2B6" strokeWidth={10} fill="none" />
    <path d="M 22 -40 q 22 2 18 18 q -4 12 -18 10" stroke="#F4F1EA" strokeWidth={7} fill="none" />
    <rect x={-24} y={-52} width={48} height={52} rx={8} fill="#F4F1EA" />
    <rect x={-24} y={-52} width={14} height={52} rx={6} fill="#D9D2C4" />
    <rect x={-24} y={-36} width={48} height={10} fill="#FF8A3D" />
    <ellipse cx={0} cy={-50} rx={20} ry={4.5} fill="#5B3A26" />
    {/* the coffee lifting out of the mouth as it sloshes */}
    {slosh > 0 ? <path d={`M -16 -52 Q -6 ${-52 - 22 * slosh} 4 ${-54 - 10 * slosh} Q 14 ${-60 - 16 * slosh} 18 -52 Z`} fill="#6B4228" /> : null}
  </g>
);
const CATCH = 13; // the mitten closes in the pause after "Double."
const s2Hand = (t: number) => ({ x: kf(t, [[0, 2500], [CATCH - 5, 2300], [CATCH - 1, 1120], [CATCH + 1, 1060], [CATCH + 5, 1075]], easeIn), y: kf(t, [[0, 640], [CATCH - 1, 610], [CATCH + 1, 600], [CATCH + 5, 560]]) });
const DROPS2 = Array.from({ length: 9 }).map((_, i) => ({ vx: (rnd(1, i) - 0.5) * 16, vy: -10 - rnd(2, i) * 12, r: 9 + rnd(3, i) * 10 }));
export const S2: React.FC<ShotProps> = ({ t, len }) => {
  const caught = t >= CATCH;
  const fall = Math.min(t, CATCH);
  const mug = caught
    ? { x: 960 - settle(t - 9, 8, 1.6, 3) * 0, y: 470 + 0.18 * CATCH * CATCH - (t - CATCH) * 1.2, rot: 54 * Math.exp(-(t - CATCH) / 3.2) * Math.cos((t - CATCH) / 1.6) }
    : { x: 960, y: 470 + 0.18 * fall * fall, rot: 30 + fall * 2 };
  const h = s2Hand(t);
  const slosh = caught ? Math.max(0, Math.sin(((t - CATCH) / 14) * Math.PI)) : 0.3;
  return (
    <g transform={camT(960, 540, kf(t, [[0, 1.0], [len, 1.07]]))}>
      {/* the kitchen behind, huge and soft: the warm pendant and the window */}
      <g filter="url(#blur16)">
        <g transform="translate(-1300 -900) scale(2.6)">
          <Kitchen t={t + 72} id="k2" />
        </g>
      </g>
      <rect x={-400} y={-400} width={2720} height={1880} fill="#07040C" opacity={0.2} />
      <Glow x={700} y={200} r={700} o={0.25} />
      {/* the island's front edge, out of focus across the top of frame */}
      <g filter="url(#blur6)">
        <rect x={-400} y={-400} width={2720} height={560} fill="#4F5F5A" />
        <rect x={-400} y={140} width={2720} height={30} fill="#B9AE9C" />
      </g>
      {/* the coffee in the air: a few drops thrown out of the mug, falling back */}
      {caught
        ? DROPS2.map((d, i) => {
            const k = t - CATCH;
            return <circle key={i} cx={mug.x - 40 + d.vx * k} cy={mug.y - 260 + d.vy * k + 0.9 * k * k} r={d.r} fill="#6B4228" opacity={clamp(1 - k / 22)} />;
          })
        : null}
      <BigMug x={mug.x} y={mug.y + 130} rot={mug.rot} slosh={slosh} />
      {/* Pip's arm from the right on a streak, the mitten closing round the mug */}
      {t >= CATCH - 6 && t < CATCH + 3 ? <Streaks x={h.x + 260} y={h.y + 20} t={t} dir={-1} len={900} h={280} o={clamp((CATCH + 3 - t) / 4)} /> : null}
      {t >= CATCH - 6 && t < CATCH + 1 ? (
        <g opacity={0.35} style={{ mixBlendMode: 'screen' }}>
          {[1, 2, 3].map((k) => {
            const g2 = s2Hand(t - k * 0.8);
            return <ellipse key={k} cx={g2.x + 40} cy={g2.y + 20} rx={170} ry={120} fill={ICE} />;
          })}
        </g>
      ) : null}
      <g filter="url(#rimR)">
        <path d={`M ${h.x + 120} ${h.y + 60} Q ${h.x + 500} ${h.y + 200} ${h.x + 1200} ${h.y + 260}`} stroke={PIP.line} strokeWidth={230} fill="none" strokeLinecap="round" />
        <path d={`M ${h.x + 120} ${h.y + 60} Q ${h.x + 500} ${h.y + 200} ${h.x + 1200} ${h.y + 260}`} stroke={PIP.limb} strokeWidth={200} fill="none" strokeLinecap="round" />
        <ellipse cx={h.x + 60} cy={h.y + 40} rx={190} ry={140} fill={PIP.hand} stroke={PIP.line} strokeWidth={12} />
        {caught ? <ellipse cx={h.x - 80} cy={h.y - 30} rx={70} ry={110} fill={PIP.hand} stroke={PIP.line} strokeWidth={11} transform={`rotate(-25 ${h.x - 80} ${h.y - 30})`} /> : null}
      </g>
      {caught ? <Sparkle x={mug.x + 180} y={mug.y - 120} t={t - CATCH - 1} s={1.4} /> : null}
    </g>
  );
};

// ---------- S3: medium, the kitchen: Pip holds the caught mug up, smug; the steam settles ----------
const S3_STAND = stand(KITCHEN, 0.5, 0.42);
export const S3: React.FC<ShotProps> = ({ t, len }) => {
  const pose = poseAt(t, [
    { f: 0, p: { x: S3_STAND.x, y: S3_STAND.y, scale: S3_STAND.scale, yaw: 0.25, look: 0.3, armL: { a: 14, b: -8 }, armR: { a: 70, b: 70 }, squash: 0.05 } },
    { f: 4, p: { armR: { a: 112, b: 55 }, squash: -0.03 }, ease: easeOut },
    { f: 8, p: { armR: { a: 104, b: 60 }, squash: 0, headTilt: -6 } },
    { f: 30, p: { headTilt: -3 } },
  ]);
  const j = joints(pose);
  const hand = toWorld(pose, j.armR.end);
  const face = faceAt(t, [[0, 'happy'], [8, 'smug']]);
  return (
    <g transform={camT(kf(t, [[0, 960], [len, 965]]), kf(t, [[0, 560], [len, 545]]), kf(t, [[0, 1.6], [len, 1.72]]))}>
      <Kitchen t={t + 52} id="k3" veil={0.4} />
      {t < 6 ? <Trail t={t} pose={(tt) => ({ ...pose, x: pose.x + Math.max(0, 4 - tt) * 60 })} n={3} gap={1.2} o={0.45} /> : null}
      <Hero look={PIP} pose={{ ...pose, ...face }} rimId="rimR" shadow={0} />
      <g transform={`translate(${hand.x} ${hand.y - 8}) scale(1.35) translate(${-hand.x} ${-hand.y + 8})`}>
        <Mug x={hand.x + 4} y={hand.y + 22} rot={0} f={t + 20} steam={1.4} />
      </g>
      <KitchenIsland />
      <Foreground blur={12}>
        <path d="M -40 1000 Q -10 760 120 700 Q 80 820 100 1000 Z" fill="#0E1610" />
      </Foreground>
    </g>
  );
};

// ---------- S4: medium wide, the foot of the stairs: Mo points up, "race you", and sets off ----------
const SC4 = 1.0;
const BOTTOM = stepTop(1560);
const s4Mo = (t: number): Pose => {
  if (t < 12) return { ...basePose, x: 1560, y: BOTTOM - LEG_LEN * SC4, scale: SC4, facing: -1, yaw: -0.5, look: -0.6, armR: { a: 150, b: 10 }, handR: 'point', armL: { a: 10, b: -8 } };
  const p = t - 12;
  const x = 1560 - p * 6.5;
  return runPose(x, p * 0.55, hipGround, SC4, -1);
};
export const S4: React.FC<ShotProps> = ({ t, len }) => {
  const mo = s4Mo(t);
  const pip: Pose = { ...basePose, x: 1760, y: BOTTOM - LEG_LEN * SC4, scale: SC4, yaw: -0.4, look: -0.5, armL: { a: 14, b: -6 }, armR: { a: 14, b: -6 }, headTilt: kf(t, [[0, 0], [16, 6]]) };
  return (
    <g transform={camT(kf(t, [[0, 1520], [len, 1460]]), kf(t, [[0, 700], [len, 680]]), kf(t, [[0, 1.45], [len, 1.5]]))}>
      <Stairwell t={t + 20} id="sw4" />
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'neutral'], [14, 'smug']]) }} rimId="rimR" shadow={0.5} />
      <Hero look={MO} pose={{ ...mo, ...faceAt(t, [[0, 'happy']]) }} rimId="rimL" shadow={0.5} />
      <Banister />
    </g>
  );
};

// ---------- S5: wide, the stairwell: Pip is a streak up the whole flight while Mo is still on the third step ----------
const SC5 = 0.85;
const s5PipX = (t: number) => kf(t, [[0, 1700], [2, 1660], [9, 260], [12, 230]], easeIn);
const s5Pip = (t: number): Pose => {
  const x = s5PipX(t);
  if (t >= 11) return { ...basePose, x: 230, y: SW.top - LEG_LEN * SC5, scale: SC5, yaw: 0.6, look: 0.8, armL: { a: 14, b: -6 }, armR: { a: 14, b: -6 }, squash: t < 15 ? 0.06 * (1 - (t - 11) / 4) : 0 };
  return runPose(x, t * 2.4, hipGround, SC5, -1, { tilt: -22 });
};
export const S5: React.FC<ShotProps> = ({ t, len }) => {
  const mox = 1280 - t * 2.2; // Mo looks slowed: a slow-motion stride
  const mo = runPose(mox, 2 + t * 0.18, hipGround, SC5, -1, { look: -1 });
  const pip = s5Pip(t);
  const moving = t > 1 && t < 11;
  return (
    <g transform={camT(kf(t, [[0, 960], [len, 900]]), kf(t, [[0, 600], [len, 580]]), kf(t, [[0, 1.0], [len, 1.04]]))}>
      <Stairwell t={t + 70} id="sw5" />
      <Hero look={MO} pose={{ ...mo, ...faceAt(t, [[0, 'happy'], [7, 'shock']]) }} rimId="rimL" shadow={0.4} />
      {moving ? <Streaks x={pip.x} y={pip.y - 60} t={t} dir={-1} len={620} h={220} slope={-0.46} /> : null}
      {t > 1 && t < 15 ? <Trail t={t} pose={s5Pip} n={7} gap={0.8} o={clamp((15 - t) / 4) * 0.6} /> : null}
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'cool'], [11, 'smug']]) }} rimId="rimR" shadow={moving ? 0 : 0.5} />
      <Banister />
    </g>
  );
};

// ---------- S6: medium, the upper landing: Pip waits, leaning on the wall, arms folded; Mo arrives, puffing ----------
const SC6 = 0.9;
const s6Mo = (t: number): Pose => {
  if (t < 16) return runPose(lerp(700, 470, t / 16), 3 + t * 0.6, hipGround, SC6, -1);
  const p = clamp((t - 16) / 5);
  const puff = Math.sin((t - 16) / 2.2) * 2;
  return { ...basePose, x: 470, y: SW.top - LEG_LEN * SC6 + 10 * p, scale: SC6, facing: -1, yaw: -0.5, look: -0.4, tilt: -24 * easeOut(p) + puff, armL: { a: -30 * p, b: 10 }, armR: { a: -20 * p, b: 10 }, legL: { a: 8, b: -14 * p }, legR: { a: -6, b: -14 * p } };
};
export const S6: React.FC<ShotProps> = ({ t, len }) => {
  const pip = poseAt(t, [
    { f: 0, p: { x: 170, y: SW.top - LEG_LEN * SC6, scale: SC6, yaw: 0.5, look: 0.8, tilt: -7, armL: { a: 8, b: -4 }, armR: { a: 18, b: -10 }, legL: { a: 14, b: 0 }, legR: { a: -10, b: 0 } } },
    { f: 18, p: {} },
    { f: 22, p: { headTilt: 8, look: 1, armR: { a: 150, b: 24 } }, ease: easeOut },
  ]);
  const mo = s6Mo(t);
  return (
    <g transform={camT(kf(t, [[0, 360], [len, 340]]), kf(t, [[0, 300], [len, 290]]), kf(t, [[0, 1.5], [len, 1.58]]))}>
      <Stairwell t={t + 110} id="sw6" />
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'smug'], [22, 'cool']]) }} rimId="rimR" shadow={0.5} />
      <Hero look={MO} pose={{ ...mo, ...faceAt(t, [[0, 'shock'], [17, 'tired']]) }} rimId="rimL" shadow={0.5} />
      {t > 18 ? [0, 1, 2].map((k) => {
        const tt = (t - 18 + k * 5) % 15;
        return <ellipse key={k} cx={mo.x - 120 - tt * 4} cy={mo.y - 140 - tt * 2} rx={14 + tt * 1.6} ry={9 + tt} fill="#F6EFE3" opacity={0.35 * (1 - tt / 15)} />;
      }) : null}
      <Banister />
    </g>
  );
};

// ---------- S7: wide, the classroom: everyone frozen mid-moment; only Pip moves, zipping between the rows ----------
const C7 = [stand(CLS, 0.12, 0.7, 0.46), stand(CLS, 0.46, 0.7, 0.46), stand(CLS, 0.84, 0.7, 0.46)];
const s7Pip = (t: number): Pose => {
  const seg = t < 8 ? 0 : t < 26 ? 1 : 2;
  const p01 = clamp((t - 4) / 4);
  const p12 = clamp((t - 30) / 4);
  const x = t < 30 ? lerp(C7[0].x, C7[1].x, easeIn(p01)) : lerp(C7[1].x, C7[2].x, easeIn(p12));
  const sc = C7[1].scale;
  const yy = C7[1].y;
  const moving = (t > 4 && t < 8) || (t > 30 && t < 34);
  if (moving) return runPose(x, t * 2.4, yy + LEG_LEN * sc, sc, 1);
  return {
    ...basePose,
    x,
    y: yy,
    scale: sc,
    yaw: seg === 1 ? -0.3 : 0.3,
    look: seg === 1 ? -0.8 : 0.5,
    armL: seg === 1 ? { a: 120, b: 30 } : { a: 14, b: -6 },
    armR: { a: 14, b: -6 },
    headTilt: seg === 1 ? 10 : 0,
  };
};
const FrozenPlane: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g transform={`translate(${x} ${y}) rotate(-14)`}>
    <path d="M -60 0 L 70 -10 L -40 26 Z" fill="#F4F1EA" stroke="#B9C4D6" strokeWidth={3} />
    <path d="M -60 0 L 70 -10 L -20 6 Z" fill="#DCE4EE" />
    <path d="M -90 2 L -140 6 M -86 16 L -130 24" stroke="#F6EFE3" strokeWidth={3} opacity={0.4} strokeLinecap="round" />
  </g>
);
export const S7: React.FC<ShotProps> = ({ t, len }) => {
  const pip = s7Pip(t);
  const moving = (t > 4 && t < 9) || (t > 30 && t < 35);
  return (
    <g transform={camT(kf(t, [[0, 900], [len, 920]]), kf(t, [[0, 520], [len, 510]]), kf(t, [[0, 1.02], [len, 1.08]]))}>
      {/* the room's clock stopped: one constant moment of the set (no dust drift, no clock tick) */}
      <Classroom t={120} id="cls7" />
      <FrozenPlane x={1020} y={330} />
      <g transform="translate(700 470) rotate(32)">
        <rect x={-30} y={-12} width={60} height={24} rx={4} fill="#E8A3B0" />
        <rect x={-30} y={-12} width={20} height={24} rx={3} fill="#5A6A8A" />
      </g>
      {moving ? <Streaks x={pip.x} y={pip.y - 60} t={t} dir={1} len={520} h={240} /> : null}
      {(t > 4 && t < 12) || (t > 30 && t < 38) ? <Trail t={t} pose={s7Pip} n={6} gap={0.8} o={0.5} /> : null}
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'cool'], [9, 'happy'], [26, 'smug']]) }} rimId="rimL" shadow={0.4} />
    </g>
  );
};

// ---------- S8: close-up: Mo frozen mid-blink at his desk, a pencil hanging in the air beside him ----------
export const S8: React.FC<ShotProps> = ({ t, len }) => {
  const sc = 3.4 * (1 + 0.05 * clamp(t / len));
  const head = { x: 820, y: 600 };
  const pose: Pose = { ...basePose, x: head.x, y: head.y - HEAD.y * sc, scale: sc, yaw: 0.25, look: 0.4, headTilt: -4, armL: { a: 14, b: -6 }, armR: { a: 14, b: -6 }, expr: 'neutral', blink: 0.55 };
  // Pip's fingertip taps the pencil at t 14; it barely turns (the world runs slow for him)
  const tap = t > 14 ? 1 - Math.exp(-(t - 14) / 10) : 0;
  const finger = { x: kf(t, [[0, 2100], [10, 1640], [14, 1500], [20, 1560]], easeOut), y: kf(t, [[0, 760], [14, 640], [20, 660]]) };
  return (
    <g>
      <g filter="url(#blur16)">
        <g transform="translate(-500 -260) scale(1.6)">
          <Classroom t={120} id="cls8" />
        </g>
      </g>
      <rect x={0} y={0} width={1920} height={1080} fill="#07040C" opacity={0.22} />
      <Hero look={MO} pose={pose} rimId="rimL" shadow={0} />
      {/* the pencil, hanging mid-fall, with its frozen motion lines */}
      <g transform={`translate(1360 520) rotate(${-38 + 6 * tap})`}>
        <rect x={-150} y={-14} width={260} height={28} rx={4} fill="#F2C14E" />
        <rect x={-150} y={-14} width={260} height={9} fill="#FFDA7A" />
        <path d="M 110 -14 L 160 0 L 110 14 Z" fill="#E8C9A0" />
        <path d="M 145 -4 L 160 0 L 145 4 Z" fill="#2A2230" />
        <rect x={-190} y={-14} width={40} height={28} rx={4} fill="#E8A3B0" />
        <rect x={-160} y={-16} width={12} height={32} fill="#B9C4D6" />
      </g>
      {[0, 1, 2].map((k) => (
        <path key={k} d={`M ${1240 + k * 50} ${330 + k * 14} q 10 -40 0 -70`} stroke="#F6EFE3" strokeWidth={4} fill="none" opacity={0.3} strokeLinecap="round" />
      ))}
      {/* Pip's mitten from the right: one fingertip */}
      <g filter="url(#rimR)">
        <path d={`M ${finger.x + 60} ${finger.y + 40} L ${finger.x + 700} ${finger.y + 300}`} stroke={PIP.line} strokeWidth={150} strokeLinecap="round" />
        <path d={`M ${finger.x + 60} ${finger.y + 40} L ${finger.x + 700} ${finger.y + 300}`} stroke={PIP.limb} strokeWidth={128} strokeLinecap="round" />
        <ellipse cx={finger.x + 70} cy={finger.y + 40} rx={110} ry={90} fill={PIP.hand} stroke={PIP.line} strokeWidth={9} />
        <ellipse cx={finger.x - 30} cy={finger.y} rx={64} ry={30} fill={PIP.hand} stroke={PIP.line} strokeWidth={8} transform={`rotate(20 ${finger.x - 30} ${finger.y})`} />
      </g>
    </g>
  );
};

// ---------- S9: the title, wide on the roof at dusk; Pip zips across and lands ----------
const ROOF_FEET = 840;
const s9Pip = (t: number): Pose => {
  const x = kf(t, [[0, 640], [16, 640], [21, 1000], [24, 1010]], easeIn);
  if (t > 16 && t < 22) return runPose(x, t * 2.4, ROOF_FEET, 0.62, 1);
  return { ...basePose, x, y: ROOF_FEET - LEG_LEN * 0.62, scale: 0.62, yaw: t < 16 ? 0.3 : -0.1, armL: t > 26 ? { a: 150, b: 10 } : { a: 20, b: 6 }, armR: t > 26 ? { a: 150, b: 10 } : { a: 20, b: 6 }, squash: t >= 22 && t < 27 ? 0.08 * (1 - (t - 22) / 5) : 0 };
};
export const S9: React.FC<ShotProps> = ({ t, len }) => {
  const pip = s9Pip(t);
  return (
    <g transform={camT(960, kf(t, [[0, 520], [len, 545]]), kf(t, [[0, 1.0], [len, 1.07]]))}>
      <Rooftop t={t} sunX={960} sunY={690 - 40 * easeOut(clamp(t / 40))} />
      {t > 16 && t < 22 ? <Streaks x={pip.x} y={pip.y - 40} t={t} dir={1} len={360} h={140} /> : null}
      {t > 16 && t < 28 ? <Trail t={t} pose={s9Pip} n={6} gap={0.8} o={0.5} /> : null}
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'happy']]) }} rimId="rimR" shadow={0.6} />
      <TitleCard t={t} lines={['WHAT IF YOU COULD', 'MOVE AT DOUBLE SPEED?']} accent="DOUBLE" accentT={36} size={88} y={170} />
    </g>
  );
};

// ---------- S10: medium, low angle on the roof: Pip drops into a sprinter's crouch ----------
export const S10: React.FC<ShotProps> = ({ t, len }) => {
  const pose = poseAt(t, [
    { f: 0, p: { x: 900, y: 790, scale: 1.7, yaw: 0.9, look: 0.6, armL: { a: 14, b: -6 }, armR: { a: 14, b: -6 } } },
    { f: 3, p: { squash: -0.03 } },
    { f: 9, p: { y: 860, tilt: 38, headTilt: -24, squash: 0.08, legL: { a: 70, b: -110 }, legR: { a: -25, b: -40 }, armL: { a: 28, b: 0 }, armR: { a: -12, b: 0 } }, ease: easeOut },
    { f: 13, p: { tilt: 34, squash: 0.06 } },
  ]);
  return (
    <g transform={camT(kf(t, [[0, 960], [len, 990]]), 540, kf(t, [[0, 1.0], [len, 1.06]]))}>
      <Rooftop t={t + 66} sunX={1250} sunY={560} low={260} />
      <Hero look={PIP} pose={{ ...pose, ...faceAt(t, [[0, 'happy'], [7, 'cool']]) }} rimId="rimR" shadow={0} />
    </g>
  );
};

// ---------- S11, S12: the schematic: drag grows with the square of speed ----------
/** A runner drawn in the schematic's chalk line; `rate` sets how fast the legs turn over. */
const Runner: React.FC<{ x: number; y: number; t: number; rate: number; s?: number; color?: string }> = ({ x, y, t, rate, s = 1, color = SCH.line }) => {
  const ph = t * rate;
  const a = Math.sin(ph) * 38;
  const leg = (deg: number, k: number) => {
    const r = (deg * Math.PI) / 180;
    const kx = Math.sin(r) * 60;
    const ky = Math.cos(r) * 60;
    const r2 = r - (0.9 * Math.max(0, Math.sin(ph + (k ? Math.PI : 0) + 1.2)));
    return `M 0 0 L ${kx} ${ky} L ${kx + Math.sin(r2) * 60} ${ky + Math.cos(r2) * 60}`;
  };
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} stroke={color} strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" fill="none">
      <g transform="rotate(16)">
        <path d="M 0 0 L 0 -110" />
        <circle cx={6} cy={-150} r={30} />
        <path d={`M 0 -95 L ${Math.sin((-a * Math.PI) / 180) * 50} ${-95 + Math.cos((a * Math.PI) / 180) * 30} M 0 -95 L ${Math.sin((a * Math.PI) / 180) * 50} ${-95 + Math.cos((a * Math.PI) / 180) * 30}`} />
      </g>
      <path d={leg(a, 0)} />
      <path d={leg(-a, 1)} />
    </g>
  );
};
const PushArrows: React.FC<{ x: number; y: number; t: number; n: number; gap?: number; every?: number }> = ({ x, y, t, n, gap = 46, every = 5 }) => (
  <g>
    {Array.from({ length: n }).map((_, i) => {
      const yy = y - ((n - 1) * gap) / 2 + i * gap;
      return <Arrow key={i} x0={x + 300} y0={yy} x1={x} y1={yy} t={t - i * every} dur={7} color={SCH.live} bend={0} />;
    })}
  </g>
);
export const S11: React.FC<ShotProps> = ({ t, len }) => {
  const fast = t >= 30;
  return (
    <g transform={`translate(960 540) scale(${kf(t, [[0, 1], [len, 1.05]])}) translate(-960 -540)`}>
      <Schematic t={t} id="sch11" />
      <SchLabel x={960} y={150} t={t - 2} text="AIR PUSHES BACK" size={60} />
      <Runner x={620} y={560} t={t} rate={fast ? 0.9 : 0.45} s={1.5} color={fast ? ICE : SCH.line} />
      {[0, 1, 2].map((k) => (
        <path key={k} d={`M ${420 - (fast ? 60 : 0)} ${470 + k * 50} L ${300 - k * 30 - (fast ? 180 : 0)} ${470 + k * 50}`} stroke={fast ? ICE : SCH.dim} strokeWidth={6} strokeLinecap="round" opacity={0.7} />
      ))}
      <PushArrows x={760} y={460} t={t - 8} n={fast ? 4 : 1} every={4} />
      <SchLabel x={620} y={800} t={t - 4} text={fast ? 'SPEED ×2' : 'SPEED ×1'} size={56} color={fast ? ICE : SCH.line} />
      <SchLabel x={1300} y={800} t={t - 12} text={fast ? 'PUSH ×4' : 'PUSH ×1'} size={56} color={SCH.live} />
      {fast ? <Sparkle x={1300} y={700} t={t - 34} s={1} /> : null}
    </g>
  );
};
export const S12: React.FC<ShotProps> = ({ t, len }) => (
  <g transform={`translate(960 540) scale(${kf(t, [[0, 1.02], [len, 1.07]])}) translate(-960 -540)`}>
    <Schematic t={t + 63} id="sch12" />
    {/* top row: normal speed, one push */}
    <Runner x={330} y={330} t={t} rate={0.45} s={0.9} />
    <SchLabel x={330} y={470} t={t - 2} text="×1 SPEED" size={40} color={SCH.dim} />
    <PushArrows x={470} y={250} t={t - 4} n={1} />
    <SchLabel x={1050} y={270} t={t - 8} text="×1 PUSH" size={48} color={SCH.dim} />
    {/* bottom row: double speed, the arrows draw on one by one to four */}
    <Runner x={330} y={760} t={t} rate={0.9} s={0.9} color={ICE} />
    <SchLabel x={330} y={900} t={t - 10} text="×2 SPEED" size={40} color={ICE} />
    <PushArrows x={470} y={680} t={t - 14} n={4} gap={40} every={7} />
    <CountUp x={1080} y={720} t={t - 14} to={4} dur={28} size={150} color={SCH.live} format={(v) => '×' + Math.max(1, Math.round(v))} />
    <SchLabel x={1080} y={800} t={t - 40} text="THE PUSH" size={40} color={SCH.live} />
    <SchLabel x={1560} y={540} t={t - 46} text="(2v)² = 4v²" size={64} />
    <SchLabel x={1560} y={600} t={t - 52} text="drag grows with speed squared" size={28} color={SCH.dim} />
  </g>
);

// ---------- S13: close-up: "That's real." Pip, worried; the light starting to turn ----------
export const S13: React.FC<ShotProps> = ({ t, len }) => {
  const sc = 6.6 * (1 + 0.04 * clamp(t / len));
  const head = { x: 960, y: 720 };
  const red = 0.35 * clamp(t / len);
  const pose: Pose = { ...basePose, x: head.x, y: head.y - HEAD.y * sc, scale: sc, yaw: 0.12, look: 0.1, armL: { a: 14, b: -6 }, armR: { a: 14, b: -6 }, ...faceAt(t, [[0, 'worried']]) };
  return (
    <g>
      <g filter="url(#blur16)">
        <g transform="translate(-600 -560) scale(2)">
          <Rooftop t={t + 200} sunX={980} sunY={600} red={red} low={180} />
        </g>
      </g>
      <rect x={0} y={0} width={1920} height={1080} fill="#07040C" opacity={0.22} />
      <Hero look={PIP} pose={pose} rimId={t > len * 0.5 ? 'rimRed' : 'rimR'} shadow={0} />
    </g>
  );
};

// ---------- S14: wide, low angle: Pip sprints at double speed, his foot catches a vent pipe, and he tumbles ----------
const FEET14 = 905;
const PIPE = 980;
const TRIP = 44; // the foot catches the pipe just as the narrator says "trip"
const s14Pip = (t: number): Pose => {
  if (t < TRIP) return runPose(lerp(-120, PIPE - 20, t / TRIP), t * 2.4, FEET14, 1.0, 1);
  if (t < TRIP + 2) return { ...runPose(PIPE, TRIP * 2.4, FEET14, 1.0, 1), tilt: 40, armL: { a: 120, b: 20 }, armR: { a: 100, b: 20 } };
  const p = clamp((t - TRIP - 2) / 36);
  const x = lerp(PIPE, 1620, easeOut(p));
  const y = FEET14 - LEG_LEN - 40 - Math.sin(p * Math.PI) * 260;
  return {
    ...basePose,
    x,
    y,
    scale: 1.0,
    yaw: 1,
    spin: lerp(40, 520, easeOut(p)),
    armL: { a: 150, b: 20 },
    armR: { a: 140, b: 30 },
    legL: { a: 40, b: -60 },
    legR: { a: -30, b: -40 },
  };
};
export const S14: React.FC<ShotProps> = ({ t, len }) => {
  const red = easeOut(clamp((t - TRIP) / 14));
  const pip = s14Pip(t);
  const running = t < TRIP;
  return (
    <g transform={camT(kf(t, [[0, 700], [TRIP, 1000], [len, 1180]]), kf(t, [[0, 560], [TRIP, 540], [len, 470]]), kf(t, [[0, 1.0], [TRIP, 1.05], [len, 1.16]]))}>
      <Rooftop t={t + 230} sunX={1180} sunY={600} red={red} low={40} />
      {/* the vent pipe his foot catches */}
      <rect x={PIPE - 18} y={FEET14 - 46} width={36} height={52} fill="#3A3444" />
      <ellipse cx={PIPE} cy={FEET14 - 46} rx={24} ry={7} fill="#4A4454" />
      <rect x={PIPE - 18} y={FEET14 - 46} width={36} height={3} fill="#FFB46A" opacity={0.5} />
      {running ? <Streaks x={pip.x} y={pip.y - 40} t={t} dir={1} len={520} h={260} /> : null}
      <Trail t={t} pose={s14Pip} n={6} gap={0.9} o={running ? 0.5 : 0.35} />
      <Hero look={PIP} pose={{ ...pip, ...faceAt(t, [[0, 'cool'], [TRIP, 'shock']]) }} rimId={t > TRIP + 2 ? 'rimRed' : 'rimR'} shadow={running ? 0.4 : 0} />
      {t > TRIP && t < TRIP + 10 ? <Sparkle x={PIPE + 10} y={FEET14 - 60} t={t - TRIP} s={1.2} /> : null}
    </g>
  );
};
