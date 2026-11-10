// The escalator's geometry as pure functions (shared by story.ts cameras, cast.ts riders and machine.ts meshes).
// Travel is toward +x (up), the steps span z -0.5..0.5. The tread-top ("nose") line of the upper run is h(x): a flat
// landing, a concave curve into the 30-degree incline, a convex curve onto the top landing. Every step hangs on its
// front axle C, which runs round one closed loop: the upper run (C = nose - HC), clockwise round the top drive
// sprocket, the return run underneath (upside down, 2R lower), round the bottom sprocket and up again.
// Each step keeps its tread level on the whole upper run (angle 0), turns over with the top sprocket (0 -> -PI),
// rides back inverted (-PI) and turns back with the bottom sprocket (-PI -> -2PI).
export const RISE = 4.5;
export const DEG30 = Math.PI / 6, TAN = Math.tan(DEG30), S30 = 0.5, C30 = Math.cos(DEG30);
export const P0 = 0.405;          // nominal step pitch along the chain (m)
export const HC = 0.28;           // tread top above the front axle
export const SPEED = 0.5;         // m/s
export const XB = 0;              // bottom comb (tread meets the landing)
export const X0 = -1.2;           // bottom sprocket centre
const XB1 = 1.0, RB = 1.0, RT = 1.5;
export const XB2 = XB1 + RB * S30, YB2 = RB * (1 - C30);
export const YT1 = RISE - RT * (1 - C30);
export const XT1 = XB2 + (YT1 - YB2) / TAN, XT2 = XT1 + RT * S30;
export const XT = XT2 + 1.0;      // top comb
export const XS1 = XT + 1.2;      // top (drive) sprocket centre
export const R = (10 * P0) / (2 * Math.PI); // sprocket pitch radius: 10 rollers round each sprocket
/** tread-top height of the upper run at x (0 on the bottom landing, RISE on the top one) */
export const h = (x: number) => {
  if (x <= XB1) return 0;
  if (x <= XB2) return RB - Math.sqrt(Math.max(0, RB * RB - (x - XB1) ** 2));
  if (x <= XT1) return YB2 + (x - XB2) * TAN;
  if (x <= XT2) return RISE - RT + Math.sqrt(Math.max(0, RT * RT - (XT2 - x) ** 2));
  return RISE;
};
/** slope angle of the upper run at x */
export const slope = (x: number) => { const e = 0.01; return Math.atan2(h(x + e) - h(x - e), 2 * e); };

// ---------------- the loop, sampled ----------------
type Pt = { x: number; y: number; th: number; s: number };
const pts: Pt[] = [];
const push = (x: number, y: number, th: number) => {
  const p = pts[pts.length - 1];
  pts.push({ x, y, th, s: p ? p.s + Math.hypot(x - p.x, y - p.y) : 0 });
};
const DX = 0.01;
for (let x = X0; x < XS1; x += DX) push(x, h(x) - HC, 0);                   // A: upper run
export const S_TOPSPR = (() => { push(XS1, h(XS1) - HC, 0); return pts[pts.length - 1].s; })();
const CT = { x: XS1, y: RISE - HC - R };
for (let i = 1; i <= 96; i++) { const f = (i / 96) * Math.PI; push(CT.x + R * Math.sin(f), CT.y + R * Math.cos(f), -f); } // B
export const S_RETURN = pts[pts.length - 1].s;
for (let x = XS1 - DX; x > X0; x -= DX) push(x, h(x) - HC - 2 * R, -Math.PI);  // C: return run
push(X0, h(X0) - HC - 2 * R, -Math.PI);
export const S_BOTSPR = pts[pts.length - 1].s;
const CB = { x: X0, y: -HC - R };
for (let i = 1; i <= 96; i++) { const f = (i / 96) * Math.PI; push(CB.x - R * Math.sin(f), CB.y - R * Math.cos(f), -Math.PI - f); } // D
export const LOOP = pts[pts.length - 1].s;
export const NSTEP = Math.round(LOOP / P0);
export const PITCH = LOOP / NSTEP;
export const SPROCKET_TOP = CT, SPROCKET_BOT = CB;

export type Pose = { x: number; y: number; th: number };
/** front-axle point + tread angle at loop parameter s */
export const poseAt = (s0: number): Pose => {
  const s = ((s0 % LOOP) + LOOP) % LOOP;
  let lo = 0, hi = pts.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pts[m].s <= s) lo = m; else hi = m; }
  const a = pts[lo], b = pts[hi], k = b.s > a.s ? (s - a.s) / (b.s - a.s) : 0;
  return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, th: a.th + (b.th - a.th) * k };
};
/** local step point (lx, ly) -> world (x, y) for a pose */
export const onStep = (p: Pose, lx: number, ly: number): [number, number] =>
  [p.x + lx * Math.cos(p.th) - ly * Math.sin(p.th), p.y + lx * Math.sin(p.th) + ly * Math.cos(p.th)];
/** loop parameter of the upper run at x */
export const sAtX = (x: number) => {
  let lo = 0, hi = Math.round((XS1 - X0) / DX);
  hi = Math.min(hi, pts.length - 1);
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pts[m].x <= x) lo = m; else hi = m; }
  const a = pts[lo], b = pts[hi], k = b.x > a.x ? (x - a.x) / (b.x - a.x) : 0;
  return a.s + (b.s - a.s) * k;
};
export const S_COMB_BOT = sAtX(XB), S_COMB_TOP = sAtX(XT);
/** loop parameter of step k at time t (s) */
export const stepS = (k: number, t: number) => SPEED * t + k * PITCH;
/** the step whose tread is under loop parameter s at time t (index of the step whose nose is just ahead) */
export const stepUnder = (s: number, t: number) => {
  const u = (((s - SPEED * t) % LOOP) + LOOP) % LOOP;
  return Math.ceil(u / PITCH - 1e-6) % NSTEP;
};
/** where a rider standing at loop parameter s (upper run) has their feet: on the tread, 0.2 m behind the nose */
export const feetAt = (s: number): [number, number] => {
  const p = poseAt(s);
  return [p.x - 0.2, p.y + HC];
};
export const sprocketAngle = (t: number) => -(SPEED * t) / R;

// wheel layout in step-local coordinates (front axle at the origin)
export const REAR: [number, number] = [-0.36, 0.06];
export const RW_FRONT = 0.06, RW_REAR = 0.052;
export const Z_FRONT = 0.56, Z_REAR = 0.68, Z_CHAIN = 0.62;
/** handrail: centre-line height above the tread line; newel radius; plan offset */
export const HR_UP = 0.95, HR_Z = 0.6, NEWEL_R = 0.32;
export const XA_RAIL = XB - 0.9, XB_RAIL = XT + 0.9;
/** handrail top-run height at x (flat beyond the combs) */
export const railY = (x: number) => h(Math.max(XB, Math.min(XT, x))) + HR_UP;

// ---------------- 1898: the Harrods leather belt ----------------
/** the belt runs up along +x from (HB.x0, floor) to the gallery edge (HB.x1, HB.rise), centred on z = HB.z */
export const HB = { x0: -327.5, x1: -318.0, rise: 3.6, z: -4.6, w: 0.95, speed: 0.32 };
export const beltY = (x: number) => 0.22 + ((Math.max(HB.x0, Math.min(HB.x1, x)) - HB.x0) / (HB.x1 - HB.x0)) * (HB.rise - 0.22);

