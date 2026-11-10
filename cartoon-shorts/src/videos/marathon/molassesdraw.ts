// 2D effect cards for the molasses-flood film (drawn on the Pen in canvas units, unlit, NOINK layer via cast.ts).
import { Pen, INK } from "./toon";

type P2 = [number, number];
const TAU = Math.PI * 2;
const rad = (d: number) => (d * Math.PI) / 180;
const AMBER = "#8a4a1e", AMBER_L = "#c4823e", AMBER_D = "#5a2e12";

/** a cut-away tank gauge (300 x 420): the tank outline filling with molasses to level 0..1 */
export const fxTankFill = (p: Pen, lvl: number) => {
  p.poly([[40, 70], [260, 70], [260, 400], [40, 400]], "#e9edf0", 10);
  p.ell(150, 70, 110, 22, "#cfd6dc", 8);
  const y = 400 - 320 * lvl;
  if (lvl > 0.01) { p.poly([[46, y], [254, y], [254, 394], [46, 394]], AMBER, 0); p.ell(150, y, 104, 14, AMBER_L, 0); }
  p.poly([[40, 70], [260, 70], [260, 400], [40, 400]], "rgba(0,0,0,0)", 10);
};
/** a blueprint sheet (520 x 380) with a tank drawing; flipped = drawn upside down (he holds it wrong) */
export const fxBlueprint = (p: Pen, flipped: boolean) => {
  const g = p.g;
  g.save();
  if (flipped) { g.translate(520, 380); g.rotate(Math.PI); }
  p.poly([[14, 14], [506, 10], [510, 366], [10, 370]], "#2f6fb8", 9);
  g.strokeStyle = "rgba(220,235,255,0.35)"; g.lineWidth = 2; for (let x = 40; x < 500; x += 30) { g.beginPath(); g.moveTo(x, 20); g.lineTo(x, 360); g.stroke(); }
  for (let y = 40; y < 360; y += 30) { g.beginPath(); g.moveTo(20, y); g.lineTo(500, y); g.stroke(); }
  g.strokeStyle = "#eaf3ff"; g.lineWidth = 7; g.strokeRect(150, 120, 200, 200); g.beginPath(); g.ellipse(250, 120, 100, 22, 0, 0, TAU); g.stroke();
  g.lineWidth = 4; g.beginPath(); g.moveTo(380, 120); g.lineTo(380, 320); g.moveTo(370, 120); g.lineTo(390, 120); g.moveTo(370, 320); g.lineTo(390, 320); g.stroke();
  g.fillStyle = "#eaf3ff"; g.font = "900 46px Arial"; g.textAlign = "center"; g.fillText("TANK", 250, 70);
  g.restore();
};
/** a leak: a brown ribbon running down (80 x 400), t = flow phase */
export const fxLeak = (p: Pen, t: number) => {
  const pts: P2[] = [];
  for (let i = 0; i <= 10; i++) { const y = 10 + i * 38; pts.push([40 + 10 * Math.sin(i * 0.9 + t * TAU), y]); }
  p.stroke(pts, 22, AMBER_D); p.stroke(pts, 14, AMBER);
  const d = ((t * 380) % 380) + 10; p.ell(40 + 10 * Math.sin((d / 38) * 0.9 + t * TAU), d, 12, 16, AMBER_L, 4);
};
/** a bucket (200 x 220), level 0..1 of molasses */
export const fxBucket = (p: Pen, lvl: number) => {
  p.poly([[30, 50], [170, 50], [150, 200], [50, 200]], "#9aa3ab", 8);
  if (lvl > 0.02) p.ell(100, 50 + 30 * (1 - lvl), 66 - 6 * (1 - lvl), 12, AMBER, 4);
  p.arc(100, 50, 70, 70, 190, 350, 7);
};
/** a rivet shooting out with speed lines (240 x 120), pointing +x */
export const fxRivet = (p: Pen) => {
  for (let k = 0; k < 3; k++) p.stroke([[20, 40 + k * 20], [120, 40 + k * 20]], 6, "#ffffff");
  p.ell(170, 60, 34, 30, "#7c858e", 8); p.ell(160, 50, 10, 8, "#c9d0d6", 0);
};
/** a thermometer (160 x 520) from 0 F to 50 F, reading v (F) */
export const fxThermo = (p: Pen, v: number) => {
  p.poly([[55, 30], [105, 30], [105, 400], [55, 400]], "#ffffff", 8);
  p.ell(80, 440, 56, 56, "#e2453c", 8);
  const top = 400 - (Math.max(0, Math.min(50, v)) / 50) * 350;
  p.poly([[66, top], [94, top], [94, 420], [66, 420]], "#e2453c", 0);
  for (let k = 0; k <= 5; k++) p.stroke([[105, 400 - k * 70], [130, 400 - k * 70]], 5);
  const g = p.g; g.fillStyle = INK; g.font = "900 44px Arial"; g.textAlign = "center"; g.fillText(`${Math.round(v)}°F`, 80, 520 - 6);
};
/** a thought bubble with a cartoon bomb and two shady figures in black hats (520 x 420) */
export const fxBomb = (p: Pen, t: number) => {
  p.ell(260, 180, 230, 160, "#ffffff", 10);
  p.ell(80, 360, 30, 24, "#ffffff", 8); p.ell(40, 400, 16, 13, "#ffffff", 6);
  p.ell(230, 200, 70, 70, "#2e2a36", 9); p.ell(210, 178, 18, 14, "#6a6470", 0);
  p.stroke([[270, 140], [300, 104], [330, 96]], 8, "#b8864a");
  const k = 0.7 + 0.3 * Math.sin(t * 30);
  for (let i = 0; i < 6; i++) { const a = (i / 6) * TAU; p.stroke([[334, 92], [334 + 26 * k * Math.cos(a), 92 + 26 * k * Math.sin(a)]], 6, "#ffcc33"); }
  for (const x of [370, 430]) { p.ell(x, 230, 22, 26, "#3a3346", 6); p.poly([[x - 30, 205], [x + 30, 205], [x + 22, 190], [x - 22, 190]], "#2e2a36", 5); p.poly([[x - 26, 256], [x + 26, 256], [x + 30, 320], [x - 30, 320]], "#2e2a36", 6);
    p.stroke([[x - 9, 228], [x - 3, 228]], 5, "#ffffff"); p.stroke([[x + 3, 228], [x + 9, 228]], 5, "#ffffff"); }
};
/** a newspaper front page (600 x 760) with a headline */
export const fxHeadline = (p: Pen, lines: string[]) => {
  p.poly([[20, 20], [580, 14], [586, 746], [26, 750]], "#f3edde", 9);
  const g = p.g; g.fillStyle = "#2e2a36"; g.font = "900 46px Georgia, serif"; g.textAlign = "center"; g.fillText("THE BOSTON DAILY", 300, 76);
  p.stroke([[40, 96], [560, 92]], 5, "#2e2a36");
  g.font = "900 88px Arial Black, Arial";
  lines.forEach((l, i) => g.fillText(l, 300, 200 + i * 100));
  for (let c = 0; c < 3; c++) for (let i = 0; i < 12; i++) { const x0 = 50 + c * 175, y = 200 + lines.length * 100 + i * 24; if (y > 720) continue; p.stroke([[x0, y], [x0 + 150 - (i % 5 === 4 ? 50 : 0), y - 1]], 5, "#b4ad9c"); }
};
/** sticky syrup strands between two points stretched (300 x 300), k 0..1 stretch */
/** syrup spray: brown droplets flung up from a crest or a splash (400 x 300), t = phase */
export const fxGoo = (p: Pen, t: number) => {
  for (let i = 0; i < 9; i++) {
    const a = rad(200 + i * 17), d = 40 + 150 * ((t + i * 0.13) % 1), y = 250 + d * Math.sin(a) + 90 * ((t + i * 0.13) % 1) ** 2, r = 14 * (1 - 0.5 * ((t + i * 0.13) % 1)) + 6;
    const x = 200 + d * Math.cos(a); p.ell(x, y, r, r * 1.2, i % 3 ? AMBER : AMBER_D, 4); p.ell(x - r * 0.3, y - r * 0.4, r * 0.3, r * 0.25, "#f2c27a", 0);
  }
};
/** goo around stuck shoes (360 x 160): a glossy puddle with blobs climbing the soles, k = how far he pulls */
export const fxGooFeet = (p: Pen, k: number) => {
  p.ell(180, 120, 170, 34, AMBER_D, 6); p.ell(160, 112, 90, 12, AMBER_L, 0);
  for (const x of [130, 230]) { const top = 90 - 50 * k; p.poly([[x - 26, 118], [x - 14, top + 10], [x, top], [x + 14, top + 10], [x + 26, 118]], AMBER, 6);
    for (let s = -1; s <= 1; s += 2) p.stroke([[x + s * 14, top + 6], [x + s * 22, (top + 118) / 2], [x + s * 18, 116]], 5, AMBER_D); }
};
export const fxStrands = (p: Pen, k: number) => {
  // a glossy puddle at the bottom, thin sagging strings up to the sole smear at the top (k = how far they stretch)
  p.ell(150, 262, 140, 30, AMBER, 5); p.ell(130, 256, 60, 10, AMBER_L, 0);
  const top = 250 - 200 * Math.max(0.15, k);
  for (let i = 0; i < 5; i++) { const x = 70 + i * 40, sag = 14 * Math.sin(i * 1.9); p.stroke([[x, top + 8], [x + sag, (top + 250) / 2], [x - sag * 0.5, 250]], 9 - (i % 2) * 3, AMBER_D); p.stroke([[x, top + 8], [x + sag, (top + 250) / 2], [x - sag * 0.5, 250]], 4, AMBER_L); }
  p.ell(150, top, 100, 16, AMBER, 5);
};
/** wavy scent lines rising (300 x 360) with a small heart, t = phase */
export const fxScent = (p: Pen, t: number) => {
  for (let k = 0; k < 3; k++) { const pts: P2[] = []; for (let i = 0; i <= 12; i++) { const y = 340 - i * 26; pts.push([70 + k * 80 + 18 * Math.sin(i * 0.8 + t * TAU + k), y]); } p.stroke(pts, 10, AMBER_L); }
  const y = 60 + 20 * Math.sin(t * TAU);
  p.poly([[150, y + 40], [118, y + 10], [124, y - 6], [140, y - 8], [150, y + 4], [160, y - 8], [176, y - 6], [182, y + 10]], "#e2607a", 6);
};
/** molasses barrel -> still -> bottles (720 x 360) */
export const fxStill = (p: Pen, k: number) => {
  p.poly([[30, 110], [150, 110], [160, 330], [20, 330]], "#8a4a1e", 7); p.stroke([[24, 170], [156, 170]], 7, "#4a4552"); p.stroke([[22, 270], [158, 270]], 7, "#4a4552");
  const g = p.g; g.fillStyle = "#f3edde"; g.font = "900 26px Arial"; g.textAlign = "center"; g.fillText("MOLASSES", 90, 228);
  if (k > 0.2) { p.poly([[180, 210], [250, 210], [250, 190], [290, 225], [250, 260], [250, 240], [180, 240]], "#f2c230", 6);
    p.ell(370, 250, 60, 70, "#c98a4a", 7); p.stroke([[370, 180], [370, 120], [430, 110]], 9, "#c98a4a"); }
  if (k > 0.5) { p.poly([[450, 215], [520, 215], [520, 195], [560, 230], [520, 265], [520, 245], [450, 245]], "#f2c230", 6);
    for (let i = 0; i < 3; i++) { const x = 600 + i * 40; p.poly([[x - 6, 170], [x + 6, 170], [x + 6, 210], [x + 16, 230], [x + 16, 330], [x - 16, 330], [x - 16, 230], [x - 6, 210]], "#5a8a5a", 5); } }
};
/** a seagull standing (240 x 200) */
export const fxGull = (p: Pen) => {
  p.ell(120, 110, 70, 42, "#f4f4f2", 7); p.ell(170, 72, 30, 28, "#f4f4f2", 7);
  p.poly([[196, 72], [232, 80], [196, 86]], "#f2b630", 4); p.dot(176, 66, 6);
  p.poly([[60, 100], [10, 90], [70, 130]], "#9aa3ab", 5); p.stroke([[110, 150], [104, 190]], 6, "#f2b630"); p.stroke([[136, 150], [142, 190]], 6, "#f2b630");
};
/** motion lines behind a runner (300 x 300) */
export const fxRunLines = (p: Pen, t: number) => {
  for (let k = 0; k < 5; k++) { const y = 40 + k * 55, x0 = 20 + 30 * ((t + k * 0.37) % 1); p.stroke([[x0, y], [x0 + 90 + 40 * (k % 2), y]], 9, "#ffffff"); }
};
/** a bottle labelled ALCOHOL (180 x 420) */
export const fxBottle = (p: Pen) => {
  p.poly([[70, 20], [110, 20], [110, 120], [150, 170], [150, 400], [30, 400], [30, 170], [70, 120]], "#5a8a5a", 9);
  p.poly([[36, 220], [144, 220], [144, 320], [36, 320]], "#f3edde", 6);
  const g = p.g; g.fillStyle = INK; g.font = "900 26px Arial"; g.textAlign = "center"; g.fillText("ALCOHOL", 90, 278);
};
/** a jagged shout burst (420 x 300) with text */
export const fxShout = (p: Pen, text: string, t: number) => {
  const pts: P2[] = [];
  for (let i = 0; i < 22; i++) { const a = (i / 22) * TAU, r = i % 2 ? 120 : 150 + 10 * Math.sin(t * 40 + i); pts.push([210 + r * 1.3 * Math.cos(a), 150 + r * 0.85 * Math.sin(a)]); }
  p.poly(pts, "#fff3b0", 9);
  const g = p.g; g.fillStyle = "#d9382e"; g.textAlign = "center"; g.textBaseline = "middle";
  if (text.length > 9) {
    const w = text.split(" "), k = Math.ceil(w.length / 2), a = w.slice(0, k).join(" "), b = w.slice(k).join(" ");
    const px = Math.min(60, Math.floor(560 / Math.max(a.length, b.length))); g.font = `900 ${px}px Arial Black, Arial`;
    g.fillText(a, 210, 156 - px * 0.58); g.fillText(b, 210, 156 + px * 0.58);
  } else { g.font = `900 ${text.length > 5 ? 64 : 84}px Arial Black, Arial`; g.fillText(text, 210, 156); }
};
/** a red X (300 x 300) */
export const fxCross = (p: Pen) => { p.stroke([[50, 50], [250, 250]], 34, "#d9382e"); p.stroke([[250, 50], [50, 250]], 34, "#d9382e"); };
/** a little engineer badge: a hard-hat silhouette with a compass (240 x 240) */
export const fxEngineer = (p: Pen) => {
  p.ell(120, 120, 104, 104, "#ffffff", 9);
  p.poly([[50, 150], [190, 150], [180, 130], [160, 80], [80, 80], [60, 130]], "#f2c230", 8);
  p.stroke([[120, 80], [120, 60]], 8);
};
/** a paint can with a brush stroke swoosh (240 x 240) */
export const fxPaintCan = (p: Pen) => {
  p.poly([[60, 90], [180, 90], [170, 220], [70, 220]], "#c9d0d6", 8);
  p.ell(120, 90, 60, 16, "#6e4426", 6);
  p.poly([[60, 120], [180, 120], [176, 170], [64, 170]], "#6e4426", 0);
  const g = p.g; g.fillStyle = "#f3edde"; g.font = "900 34px Arial"; g.textAlign = "center"; g.fillText("BROWN", 120, 156);
};
/** a sparkle "ta-da" (300 x 300) */
export const fxSparkle = (p: Pen, t: number) => {
  for (let i = 0; i < 4; i++) {
    const a = rad(45 + i * 90 + t * 60), x = 150 + 90 * Math.cos(a), y = 150 + 90 * Math.sin(a), s = 26 + 10 * Math.sin(t * 20 + i);
    p.poly([[x, y - s], [x + s * 0.3, y - s * 0.3], [x + s, y], [x + s * 0.3, y + s * 0.3], [x, y + s], [x - s * 0.3, y + s * 0.3], [x - s, y], [x - s * 0.3, y - s * 0.3]], "#fff3b0", 5);
  }
};
/** a calendar block with a big number and a word (260 x 300) */
export const fxCalendar = (p: Pen, big: string, word: string) => {
  p.poly([[20, 40], [240, 40], [240, 280], [20, 280]], "#ffffff", 9);
  p.poly([[20, 40], [240, 40], [240, 100], [20, 100]], "#d9382e", 9);
  for (const x of [70, 190]) p.stroke([[x, 20], [x, 60]], 12);
  const g = p.g; g.fillStyle = INK; g.textAlign = "center"; g.font = "900 120px Arial Black, Arial"; g.fillText(big, 130, 222); g.font = "900 40px Arial"; g.fillText(word, 130, 268);
};
/** a speed tag "35 MPH" with motion lines (420 x 220) */
export const fxSpeed = (p: Pen, text: string) => {
  for (let k = 0; k < 3; k++) p.stroke([[10, 70 + k * 40], [90, 70 + k * 40]], 10, "#ffffff");
  p.poly([[100, 30], [400, 30], [400, 190], [100, 190]], "#f2c230", 10);
  const g = p.g; g.fillStyle = INK; g.font = "900 84px Arial Black, Arial"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, 250, 114);
};
/** sweat drops (200 x 200) */
export const fxSweat = (p: Pen, t: number) => {
  for (let k = 0; k < 2; k++) { const y = 40 + ((t + k * 0.5) % 1) * 120; p.poly([[60 + k * 80, y], [76 + k * 80, y + 30], [60 + k * 80, y + 46], [44 + k * 80, y + 30]], "#9fd4ff", 5); }
};
/** a drop of molasses (60 x 90) */
export const fxSyrupDrop = (p: Pen) => { p.poly([[30, 6], [50, 52], [30, 84], [10, 52]], AMBER, 5); };
/** a cracked glass shard burst (300 x 300) */
export const fxShatter = (p: Pen, t: number) => {
  for (let i = 0; i < 7; i++) { const a = rad(200 + i * 22), d = 30 + 110 * t; const x = 150 + d * Math.cos(a), y = 220 + d * Math.sin(a) + 80 * t * t;
    p.poly([[x, y], [x + 16, y + 6], [x + 6, y + 20]], "#cfe8f2", 4); }
};
/** a 1919 telephone earpiece on its cord (160 x 260): a black horn with a ring */
export const fxReceiver = (p: Pen) => {
  p.poly([[40, 30], [120, 30], [104, 130], [56, 130]], "#2e2a36", 7);
  p.ell(80, 30, 40, 14, "#4a4552", 6);
  p.stroke([[80, 130], [70, 170], [96, 200], [66, 240]], 6, "#2e2a36");
};
/** a rounded label (w x h canvas) with text auto-sized to fit; bg colour, optional motion lines on the left */
export const fxLabel = (p: Pen, text: string, w: number, h: number, bg = "#f2c230", fg = INK, lines = false) => {
  const x0 = lines ? 0.18 * w : 0.04 * w;
  if (lines) for (let k = 0; k < 3; k++) p.stroke([[0.02 * w, h * (0.3 + k * 0.2)], [0.14 * w, h * (0.3 + k * 0.2)]], h * 0.05, "#ffffff");
  p.poly([[x0, 0.12 * h], [0.96 * w, 0.12 * h], [0.96 * w, 0.88 * h], [x0, 0.88 * h]], bg, h * 0.05);
  const g = p.g; let px = h * 0.5; g.font = `900 ${px}px Arial Black, Arial`;
  const room = (0.96 * w - x0) * 0.86; while (g.measureText(text).width > room && px > 10) { px -= 2; g.font = `900 ${px}px Arial Black, Arial`; }
  g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, (x0 + 0.96 * w) / 2, h * 0.52);
};
