// 2D effect cards for the 1904 Olympic marathon film (drawn on the Pen in canvas units, unlit, NOINK layer via cast.ts).
import { Pen, INK } from "./toon";

type P2 = [number, number];
const TAU = Math.PI * 2;
const rad = (d: number) => (d * Math.PI) / 180;
const DUST = "#d9bf8f", DUST_D = "#b89a68";

/** a rolling dust cloud (600 x 400), t = churn phase 0..1, a = opacity */
export const fxDustCloud = (p: Pen, t: number, a = 0.85) => {
  const g = p.g; g.globalAlpha = a;
  for (let k = 0; k < 9; k++) {
    const ang = (k / 9) * TAU + t * TAU * 0.5, r = 70 + 30 * Math.sin(k * 2.1 + t * TAU);
    const x = 300 + 190 * Math.cos(ang) * (0.6 + 0.4 * ((k * 37) % 5) / 5), y = 230 + 90 * Math.sin(ang) * 0.8;
    p.ell(x, y, r * 1.3, r, k % 2 ? DUST : DUST_D, 0);
  }
  p.ell(300, 240, 200, 120, DUST, 0);
  g.globalAlpha = 1;
};
/** a laurel wreath seen from the front (400 x 260) */
export const fxWreath = (p: Pen) => {
  for (const s of [-1, 1]) for (let k = 0; k < 7; k++) {
    const a = rad(200 - k * 22), x = 200 + s * 150 * Math.cos(a) * -1, y = 150 + 90 * Math.sin(a) * -1;
    p.ell(200 + s * (200 - x), y, 34, 15, k % 2 ? "#5d8a3a" : "#76a64a", 5, 0, 360, s * (40 + k * 18));
  }
};
/** a gold medal on a ribbon (240 x 360) */
export const fxMedal = (p: Pen, t = 0) => {
  p.poly([[70, 10], [110, 10], [130, 170], [100, 180]], "#2f5fb0", 7);
  p.poly([[170, 10], [130, 10], [110, 170], [140, 180]], "#d9382e", 7);
  p.ell(120, 250, 90, 90, "#f2c230", 10);
  p.ell(120, 250, 60, 60, "#e8b020", 5);
  const g = p.g; g.fillStyle = "#8a6a10"; g.font = "900 54px Arial Black, Arial"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("1", 120, 254);
  if (t > 0) p.stroke([[190, 180], [225, 150]], 8, "#ffffff");
};
/** a bottle with a label (180 x 420): kind 0 = RAT POISON (skull), 1 = BRANDY */
export const fxPoison = (p: Pen, kind: number) => {
  const glass = kind === 0 ? "#4a7a4a" : "#9a5a22";
  p.poly([[70, 20], [110, 20], [110, 120], [150, 170], [150, 400], [30, 400], [30, 170], [70, 120]], glass, 9);
  p.poly([[36, 200], [144, 200], [144, 340], [36, 340]], "#f3edde", 6);
  const g = p.g; g.fillStyle = INK; g.textAlign = "center";
  if (kind === 0) {
    p.ell(90, 245, 26, 24, "#ffffff", 5); p.dot(80, 243, 6); p.dot(100, 243, 6);
    p.stroke([[66, 272], [114, 290]], 6); p.stroke([[114, 272], [66, 290]], 6);
    g.font = "900 22px Arial"; g.fillText("RAT", 90, 312); g.fillText("POISON", 90, 334);
  } else { g.font = "900 30px Arial"; g.fillText("BRANDY", 90, 280); }
};
/** two eggs (260 x 200) */
export const fxEggs = (p: Pen) => { p.ell(90, 110, 58, 74, "#fbf6e8", 8); p.ell(180, 120, 56, 70, "#f6efdc", 8); };
/** a tin cup (200 x 200) with a fizzing green mix */
export const fxCup = (p: Pen, t: number) => {
  p.poly([[40, 60], [160, 60], [146, 180], [54, 180]], "#b9c0c6", 8);
  p.ell(100, 60, 60, 16, "#7ab84a", 6);
  for (let k = 0; k < 3; k++) { const u = (t + k / 3) % 1; p.ell(70 + k * 30, 50 - 40 * u, 8 * (1 - u) + 3, 8 * (1 - u) + 3, "#a8e070", 3); }
};
/** dizzy stars and a spiral orbiting a head (400 x 260), t = spin phase */
export const fxDizzy = (p: Pen, t: number) => {
  for (let k = 0; k < 4; k++) {
    const a = t * TAU + (k / 4) * TAU, x = 200 + 160 * Math.cos(a), y = 130 + 50 * Math.sin(a), r = 28 + 6 * Math.sin(a);
    const pts: P2[] = [];
    for (let i = 0; i < 10; i++) { const b = (i / 10) * TAU - Math.PI / 2, rr = i % 2 ? r * 0.45 : r; pts.push([x + rr * Math.cos(b), y + rr * Math.sin(b)]); }
    p.poly(pts, k % 2 ? "#f2c230" : "#ffffff", 5);
  }
};
/** a hallucination bubble (420 x 340): a giant smiling egg waving */
export const fxEggDream = (p: Pen, t: number) => {
  p.ell(210, 150, 190, 130, "#e9dcff", 9);
  p.ell(60, 300, 26, 20, "#e9dcff", 6);
  p.ell(210, 160, 70, 92, "#fbf6e8", 8);
  p.dot(186, 140, 8); p.dot(234, 140, 8); p.arc(210, 170, 28, 22, 20, 160, 6);
  const w = Math.sin(t * TAU) * 20;
  p.stroke([[140, 170], [100, 130 + w]], 8); p.stroke([[280, 170], [320, 130 - w]], 8);
};
/** scissors (300 x 200), open 0..1 */
export const fxScissors = (p: Pen, o: number) => {
  const a = rad(8 + 16 * o);
  for (const s of [-1, 1]) {
    const ex = 150 + 140 * Math.cos(s * a), ey = 100 + 140 * Math.sin(s * a);
    p.poly([[150, 100 - 8], [ex, ey], [150, 100 + 8]], "#c9d0d6", 6);
    p.ell(150 - 70 * Math.cos(s * a), 100 - 70 * Math.sin(s * a) * 2, 30, 22, "#d9382e", 7);
  }
  p.dot(150, 100, 8);
};
/** a peach (160 x 160) */
export const fxPeach = (p: Pen) => { p.ell(80, 90, 62, 58, "#f4a060", 7); p.arc(80, 90, 30, 50, 250, 300, 5, "#d9783a"); p.ell(96, 30, 22, 10, "#5d8a3a", 4, 0, 360, -30); };
/** a rotten apple (180 x 180) with flies */
export const fxApple = (p: Pen, t: number, rotten = true) => {
  p.ell(90, 100, 64, 60, rotten ? "#9a8a3a" : "#d9382e", 7);
  if (rotten) { p.ell(70, 90, 18, 14, "#5a4a22", 0); p.ell(108, 118, 12, 10, "#5a4a22", 0); }
  p.stroke([[90, 44], [96, 18]], 7, "#5a3b2a");
  if (rotten) for (let k = 0; k < 2; k++) { const a = t * TAU * 2 + k * Math.PI; p.dot(90 + 70 * Math.cos(a), 40 + 20 * Math.sin(a), 6); }
};
/** a dog running in profile (420 x 300), facing +x, gallop phase 0..1, mouth open barking */
export const fxDog = (p: Pen, ph: number) => {
  // v2 (gate: "reads as a cat"): long muzzle, open snapping jaws with teeth, floppy ear, red collar, angry brow, tail up
  const s = Math.sin(ph * TAU), c = Math.cos(ph * TAU), body = "#b5824e", dark = "#6a4a2a", muz = "#e0b98a";
  const legs: [number, number, number][] = [[125, 1, 0], [148, -1, 0.5], [270, 1, 0.25], [292, -1, 0.75]];
  for (const [x, , o] of legs) { const a = Math.sin((ph + o) * TAU) * 0.6; p.stroke([[x, 165], [x + 70 * Math.sin(a), 168 + 78 * Math.cos(a)]], 24, dark); }
  p.stroke([[105, 140], [70, 95 - 20 * c], [80, 60 - 25 * c]], 14, dark);                       // tail up, wagging
  p.ell(205, 150 + 6 * s, 112, 50, body, 8);                                                       // body
  p.ell(165, 140 + 6 * s, 34, 22, dark, 0);                                                        // a dark patch
  p.poly([[268, 112 + 6 * s], [296, 104 + 6 * s], [302, 150 + 6 * s], [274, 160 + 6 * s]], "#d9382e", 6);  // red collar
  const hy = 92 + 6 * s;
  p.ell(318, hy, 46, 42, body, 8);                                                                 // head
  // the jaws: upper muzzle and an open lower jaw, teeth showing
  p.poly([[340, hy - 10], [408, hy - 2], [410, hy + 18], [342, hy + 22]], muz, 6);
  p.poly([[340, hy + 26], [402, hy + 38 + 8 * Math.abs(s)], [398, hy + 52 + 8 * Math.abs(s)], [338, hy + 44]], muz, 6);
  p.poly([[346, hy + 22], [404, hy + 20], [400, hy + 40 + 8 * Math.abs(s)], [344, hy + 30]], "#8c2a2a", 4);
  for (let k = 0; k < 4; k++) { const x = 352 + k * 13; p.poly([[x, hy + 20], [x + 8, hy + 20], [x + 4, hy + 29]], "#ffffff", 2); }
  p.dot(408, hy + 2, 9);                                                                           // nose
  p.ell(296, hy + 6, 15, 34, dark, 6, 0, 360, -18);                                                 // floppy ear
  p.ell(330, hy - 12, 11, 11, "#ffffff", 5); p.dot(333, hy - 11, 5);                                // eye
  p.stroke([[316, hy - 30], [344, hy - 20]], 7, INK);                                              // angry brow
};
/** a red rubber stamp (600 x 260) with two lines */
export const fxBanned = (p: Pen, a: string, b: string, crossed = 0) => {
  const g = p.g; g.save(); g.translate(300, 130); g.rotate(rad(-8));
  g.strokeStyle = "#d9382e"; g.lineWidth = 16; g.strokeRect(-270, -105, 540, 210);
  g.fillStyle = "#d9382e"; g.textAlign = "center"; g.textBaseline = "middle";
  g.font = "900 92px Arial Black, Arial"; g.fillText(a, 0, -40); g.font = "900 70px Arial Black, Arial"; g.fillText(b, 0, 52);
  if (crossed > 0) { g.strokeStyle = INK; g.lineWidth = 20; g.beginPath(); g.moveTo(-250, 60); g.lineTo(-250 + 500 * crossed, 60 - 20 * crossed); g.stroke(); }
  g.restore();
};
/** empty trouser pockets turned out + two dice (360 x 260) */
export const fxBroke = (p: Pen, t: number) => {
  p.poly([[30, 40], [150, 40], [130, 200], [50, 200]], "#f3edde", 7);
  p.poly([[210, 40], [330, 40], [310, 200], [230, 200]], "#f3edde", 7);
  const g = p.g; g.fillStyle = "#d9382e"; g.font = "900 70px Arial Black, Arial"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("$0", 180, 130 + 6 * Math.sin(t * TAU));
  // a moth fluttering out of the empty pocket, two dice
  const my = 40 - 30 * t, mx = 90 + 20 * Math.sin(t * TAU * 2);
  for (const s of [-1, 1]) p.ell(mx + s * 16, my, 16, 10 + 6 * Math.sin(t * TAU * 4), "#c9b9a0", 4, 0, 360, s * 30);
  p.dot(mx, my, 6);
  for (const [x, y, r] of [[250, 228, -0.3], [310, 232, 0.25]] as const) { g.save(); g.translate(x, y); g.rotate(r); p.poly([[-22, -22], [22, -22], [22, 22], [-22, 22]], "#ffffff", 5); p.dot(-9, -9, 5); p.dot(9, 9, 5); p.dot(0, 0, 5); g.restore(); }
};
/** a heart-shaped cough puff in dust colour (240 x 240) */
export const fxCoughDust = (p: Pen, t: number) => {
  for (let k = 0; k < 4; k++) { const a = rad(-20 - k * 30), d = 30 + 120 * t, r = 22 * (1 - 0.5 * t) + 8; p.ell(60 + Math.cos(a) * d, 180 + Math.sin(a) * d, r, r * 0.8, DUST, 5); }
};
/** a hot sun with heat waves (360 x 360) */
export const fxSun = (p: Pen, t: number) => {
  for (let k = 0; k < 12; k++) { const a = (k / 12) * TAU + t * 0.5; p.stroke([[180 + 110 * Math.cos(a), 180 + 110 * Math.sin(a)], [180 + 165 * Math.cos(a), 180 + 165 * Math.sin(a)]], 16, "#f29a2c"); }
  p.ell(180, 180, 95, 95, "#f2c230", 10);
  p.dot(150, 165, 9); p.dot(210, 165, 9); p.arc(180, 200, 30, 18, 200, 340, 7);
  p.ell(240, 130, 10, 16, "#7ac4f0", 4);
};
/** a thermometer reading v °F on a 0-100 scale (160 x 520) */
export const fxThermoF = (p: Pen, v: number) => {
  p.poly([[55, 30], [105, 30], [105, 400], [55, 400]], "#ffffff", 8);
  p.ell(80, 440, 56, 56, "#e2453c", 8);
  const top = 400 - (Math.max(0, Math.min(100, v)) / 100) * 350;
  p.poly([[66, top], [94, top], [94, 420], [66, 420]], "#e2453c", 0);
  for (let k = 0; k <= 5; k++) p.stroke([[105, 400 - k * 70], [130, 400 - k * 70]], 5);
  const g = p.g; g.fillStyle = INK; g.font = "900 44px Arial"; g.textAlign = "center"; g.fillText(`${Math.round(v)}°F`, 80, 520 - 6);
};
/** a steam/smoke cloud (300 x 300), grey, t 0..1 rising */
export const fxSmoke = (p: Pen, t: number) => {
  // v2: one cartoon cloud (outer ink only, no stacked rings): ink discs first, then the fills on top, a lit cap
  const g = p.g; g.globalAlpha = 0.95 * (1 - 0.55 * t);
  const B = [0, 1, 2, 3, 4, 5].map((k) => [150 + 48 * Math.cos(k * 1.05 + t * 2), 170 - 120 * t + 34 * Math.sin(k * 1.05 + t * 2), 46 + 22 * t + 6 * (k % 2)]);
  for (const [x, y, r] of B) p.ell(x, y, r + 6, (r + 6) * 0.9, "#3a3540");
  for (const [x, y, r] of B) p.ell(x, y, r, r * 0.9, "#c9c6cf");
  for (const [x, y, r] of B) p.ell(x - r * 0.2, y - r * 0.25, r * 0.62, r * 0.5, "#eeeef2");
  g.globalAlpha = 1;
};
/** a finish tape snapping (600 x 120), s = 0 intact .. 1 snapped */
export const fxTape = (p: Pen, s: number) => {
  if (s <= 0) { p.band([[10, 60], [590, 60]], "#f7f4ea", 26, 4); return; }
  p.band([[10, 60], [290 - 120 * s, 60 + 40 * s]], "#f7f4ea", 26, 4);
  p.band([[310 + 120 * s, 60 + 40 * s], [590, 60]], "#f7f4ea", 26, 4);
};
/** a star-spangled pennant flag (300 x 200), wave phase */
export const fxFlag = (p: Pen, t: number) => {
  const g = p.g;
  for (let k = 0; k < 7; k++) {
    const y0 = 20 + k * 24;
    const pts: P2[] = [];
    for (let i = 0; i <= 10; i++) { const x = 20 + i * 26; pts.push([x, y0 + 8 * Math.sin(i * 0.6 + t * TAU)]); }
    for (let i = 10; i >= 0; i--) { const x = 20 + i * 26; pts.push([x, y0 + 24 + 8 * Math.sin(i * 0.6 + t * TAU)]); }
    p.poly(pts, k % 2 ? "#f7f4ea" : "#c0353a", 0);
  }
  p.poly([[20, 20 + 8 * Math.sin(t * TAU)], [130, 20 + 8 * Math.sin(2.5 + t * TAU)], [130, 116], [20, 116]], "#2f4f8a", 0);
  g.fillStyle = "#f7f4ea"; for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) { g.beginPath(); g.arc(36 + c * 26, 40 + r * 26, 5, 0, TAU); g.fill(); }
};
