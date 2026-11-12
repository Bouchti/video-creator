// 2D effect cards for "The Man Who Took a Hoover Van Hostage" (Workington, 1993). Drawn on the toon Pen in canvas units.
import { Pen, INK } from "../marathon/toon";

type P2 = [number, number];
const TAU = Math.PI * 2;
const rad = (d: number) => (d * Math.PI) / 180;
const txt = (p: Pen, s: string, x: number, y: number, px: number, col = INK, font = "Arial Black, Arial", align: CanvasTextAlign = "center", w = 900) => {
  const g = p.g; g.fillStyle = col; g.font = `${w} ${px}px ${font}`; g.textAlign = align; g.textBaseline = "middle"; g.fillText(s, x, y);
};
const fit = (p: Pen, s: string, x: number, y: number, px: number, room: number, col = INK) => {
  const g = p.g; g.font = `900 ${px}px Arial Black, Arial`;
  while (g.measureText(s).width > room && px > 8) { px -= 2; g.font = `900 ${px}px Arial Black, Arial`; }
  txt(p, s, x, y, px, col);
};
export const HRED = "#d8262e", HBLUE = "#1f4fa0";

/** a 1990s upright vacuum cleaner (300 x 600): red bag body, grey handle, a wide base with a light */
export const fxVacuum = (p: Pen, col = HRED) => {
  p.stroke([[150, 30], [150, 140]], 22, "#5a5f6a"); p.poly([[110, 18], [190, 18], [196, 50], [104, 50]], "#3a3d47", 7);
  p.poly([[96, 130], [204, 130], [214, 430], [86, 430]], col, 9);
  p.poly([[110, 150], [140, 150], [136, 410], [104, 410]], "rgba(255,255,255,0.22)", 0);
  p.poly([[104, 250], [196, 250], [196, 300], [104, 300]], "#f4f1ea", 6); fit(p, "HOOVER", 150, 276, 30, 80, HRED);
  p.poly([[60, 430], [240, 430], [256, 540], [44, 540]], "#3a3d47", 9);
  p.poly([[70, 470], [230, 470], [236, 500], [64, 500]], "#ffe9a0", 5);
  for (const x of [70, 230]) p.ell(x, 556, 26, 26, "#1d1b22", 6);
};
/** a cardboard vacuum box (400 x 500): brown card, red band, a drawing of the cleaner and the brand */
export const fxVacBox = (p: Pen, tag = "") => {
  p.poly([[40, 120], [320, 120], [320, 480], [40, 480]], "#c99a5e", 9);
  p.poly([[320, 120], [376, 80], [376, 430], [320, 480]], "#a87a44", 9);
  p.poly([[40, 120], [96, 80], [376, 80], [320, 120]], "#ddb47a", 9);
  p.poly([[40, 150], [320, 150], [320, 230], [40, 230]], HRED, 6); fit(p, "HOOVER", 180, 192, 58, 250, "#ffffff");
  p.poly([[150, 260], [200, 260], [206, 400], [144, 400]], HRED, 5); p.stroke([[175, 250], [175, 280]], 10, "#5a5f6a"); p.poly([[124, 400], [226, 400], [234, 440], [116, 440]], "#3a3d47", 5);
  if (tag) { p.poly([[54, 300], [134, 300], [134, 350], [54, 350]], "#fff4a8", 4); fit(p, tag, 94, 326, 30, 72); }
};
/** an airline ticket (520 x 240) */
export const fxTicket = (p: Pen, line1 = "FREE FLIGHT", line2 = "LONDON → NEW YORK") => {
  p.poly([[16, 20], [504, 20], [504, 220], [16, 220]], "#fdfbf4", 8);
  p.poly([[16, 20], [504, 20], [504, 76], [16, 76]], HBLUE, 8);
  fit(p, line1, 260, 50, 40, 440, "#ffffff");
  fit(p, line2, 230, 130, 34, 380);
  for (let k = 0; k < 7; k++) p.stroke([[60 + k * 46, 180], [86 + k * 46, 180]], 6, "#8a8f9a");
  p.stroke([[410, 86], [410, 214]], 4, "#b9bcc4");
  const g = p.g; g.save(); g.translate(456, 150); g.rotate(-0.4); txt(p, "✈", 0, 0, 70, HBLUE, "Segoe UI Symbol, Arial", "center", 400); g.restore();
};
/** a jumbo jet in side view (900 x 320), nose to the right */
export const fxPlane = (p: Pen) => {
  p.poly([[300, 150], [430, 40], [490, 40], [430, 160]], "#c9ccd4", 8);
  p.poly([[60, 130], [790, 120], [860, 160], [800, 200], [70, 200], [40, 160]], "#f4f6fa", 9);
  p.poly([[60, 130], [130, 30], [180, 30], [170, 140]], HBLUE, 8);
  p.poly([[70, 182], [800, 182], [790, 198], [76, 198]], HBLUE, 0);
  for (let k = 0; k < 16; k++) p.ell(220 + k * 34, 150, 8, 10, "#3a5a8a", 3);
  p.poly([[790, 136], [836, 148], [800, 160]], "#2a3a5a", 4);
  p.poly([[420, 190], [560, 300], [620, 300], [520, 190]], "#c9ccd4", 8);
  p.ell(500, 245, 40, 20, "#9aa0ac", 6); p.ell(600, 245, 34, 18, "#9aa0ac", 6);
};
/** a balance scale (700 x 600): left pan (vacuum £119) light, right pan (two tickets £600) heavy; tilt 0..1 */
export const fxScale = (p: Pen, tilt: number) => {
  const a = rad(-16 * tilt), cx = 350, cy = 150, L = 260;
  const lx = cx - L * Math.cos(a), ly = cy - L * Math.sin(a), rx = cx + L * Math.cos(a), ry = cy + L * Math.sin(a);
  p.poly([[330, 160], [370, 160], [390, 560], [310, 560]], "#a0742a", 8); p.poly([[230, 556], [470, 556], [470, 590], [230, 590]], "#7a5420", 8);
  p.stroke([[lx, ly], [rx, ry]], 22, "#c8952e"); p.ell(cx, cy, 24, 24, "#e8b84a", 7);
  for (const [x, y, s] of [[lx, ly, 0], [rx, ry, 1]] as [number, number, number][]) {
    p.stroke([[x, y], [x - 80, y + 150]], 5, "#7a5420"); p.stroke([[x, y], [x + 80, y + 150]], 5, "#7a5420");
    p.ell(x, y + 160, 110, 26, "#e8b84a", 8);
    if (s === 0) {
      p.g.save(); p.g.translate(x - 45, y + 20); p.g.scale(0.3, 0.24); fxVacuum(p); p.g.restore();
      p.poly([[x - 60, y + 200], [x + 60, y + 200], [x + 60, y + 250], [x - 60, y + 250]], "#fff4a8", 5); fit(p, "£119", x, y + 226, 40, 110);
    } else {
      for (let k = 0; k < 2; k++) { p.g.save(); p.g.translate(x - 110 + k * 16, y + 70 - k * 34); p.g.scale(0.42, 0.42); fxTicket(p, "FREE", "USA"); p.g.restore(); }
      p.poly([[x - 60, y + 200], [x + 60, y + 200], [x + 60, y + 250], [x - 60, y + 250]], "#9be07a", 5); fit(p, "£600", x, y + 226, 40, 110);
    }
  }
};
/** a newspaper page of small ads (600 x 760): every ad a boxed-up Hoover; n = how many ads are filled in */
export const fxSmallAds = (p: Pen, n = 18) => {
  p.poly([[20, 20], [580, 20], [580, 740], [20, 740]], "#f3efe2", 8);
  fit(p, "SMALL ADS", 300, 70, 60, 520);
  p.stroke([[40, 108], [560, 108]], 5);
  const ads = ["HOOVER. UNUSED. STILL IN BOX", "HOOVER, NEVER OPENED £60", "BRAND NEW HOOVER - BOXED", "HOOVER TURBO. UNWANTED GIFT", "HOOVER, IN BOX, OFFERS", "HOOVER. NEW. NO FLIGHTS"];
  for (let i = 0; i < Math.min(n, 18); i++) {
    const c = i % 2, r = Math.floor(i / 2), x = 40 + c * 270, y = 124 + r * 68;
    p.poly([[x, y], [x + 250, y], [x + 250, y + 58], [x, y + 58]], i % 5 === 2 ? "#fff4a8" : "#ffffff", 3);
    fit(p, ads[(i * 7 + 3) % ads.length], x + 125, y + 29, 20, 230);
  }
};
/** a 7-day week (620 x 300): the boxes crossed one by one (k = days crossed), OVERTIME stamped across */
export const fxWeek = (p: Pen, k: number, stamp = false) => {
  p.poly([[10, 20], [610, 20], [610, 290], [10, 290]], "#ffffff", 8);
  p.poly([[10, 20], [610, 20], [610, 80], [10, 80]], HRED, 8); fit(p, "THIS WEEK'S SHIFTS", 310, 50, 34, 560, "#ffffff");
  const D = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
  D.forEach((d, i) => {
    const x = 22 + i * 84; p.poly([[x, 96], [x + 76, 96], [x + 76, 270], [x, 270]], i >= 5 ? "#ffe0d0" : "#f4f6fa", 4); fit(p, d, x + 38, 122, 24, 64);
    if (i < k) { p.stroke([[x + 12, 160], [x + 64, 250]], 10, HRED); p.stroke([[x + 64, 160], [x + 12, 250]], 10, HRED); }
  });
  if (stamp) { const g = p.g; g.save(); g.translate(310, 190); g.rotate(-0.18); p.poly([[-230, -46], [230, -46], [230, 46], [-230, 46]], null, 10); fit(p, "OVERTIME!", 0, 2, 74, 420, HRED); g.restore(); }
};
/** a factory wall clock (300 x 300), t = hand spin phase */
export const fxClock = (p: Pen, t: number) => {
  p.ell(150, 150, 130, 130, "#ffffff", 12);
  for (let k = 0; k < 12; k++) { const a = (k / 12) * TAU; p.stroke([[150 + 108 * Math.sin(a), 150 - 108 * Math.cos(a)], [150 + 120 * Math.sin(a), 150 - 120 * Math.cos(a)]], 6); }
  const a1 = t * TAU * 12, a2 = t * TAU;
  p.stroke([[150, 150], [150 + 90 * Math.sin(a1), 150 - 90 * Math.cos(a1)]], 8, HRED); p.stroke([[150, 150], [150 + 64 * Math.sin(a2), 150 - 64 * Math.cos(a2)]], 12);
  p.dot(150, 150, 12);
};
/** a claim form (360 x 480), optional stamp REJECTED / 14 DAYS */
export const fxForm = (p: Pen, stamp: "" | "REJECTED" | "LATE" = "", rot = -0.2) => {
  p.poly([[20, 20], [340, 20], [340, 460], [20, 460]], "#fdfbf4", 7);
  fit(p, "FREE FLIGHTS", 180, 60, 34, 290, HBLUE); fit(p, "CLAIM FORM", 180, 100, 26, 290);
  for (let k = 0; k < 8; k++) { p.stroke([[50, 150 + k * 34], [310, 150 + k * 34]], 3, "#a8acb6"); p.poly([[50, 136 + k * 34], [66, 136 + k * 34], [66, 150 + k * 34], [50, 150 + k * 34]], null, 3); }
  fit(p, "RETURN IN 14 DAYS!", 180, 434, 24, 290, HRED);
  if (stamp) { const g = p.g; g.save(); g.translate(180, 270); g.rotate(rot); g.globalAlpha = 0.9; p.poly([[-150, -44], [150, -44], [150, 44], [-150, 44]], null, 10); fit(p, stamp, 0, 2, 62, 280, HRED); g.restore(); g.globalAlpha = 1; }
};
/** a big round stamp hit: text in a red frame (520 x 220) */
export const fxStampText = (p: Pen, text: string, col = HRED) => {
  p.g.globalAlpha = 0.95; p.poly([[20, 20], [500, 20], [500, 200], [20, 200]], null, 14); p.poly([[40, 40], [480, 40], [480, 180], [40, 180]], null, 5);
  fit(p, text, 260, 112, 110, 420, col); p.g.globalAlpha = 1;
};
/** washing-machine suds (400 x 300), t = growth 0..1 */
export const fxSuds = (p: Pen, t: number) => {
  for (let k = 0; k < 14; k++) {
    const a = (k / 14) * TAU + k, d = 40 + 140 * t * (0.5 + 0.5 * ((k * 37) % 7) / 7), r = 22 + 30 * t * (0.6 + 0.4 * ((k * 13) % 5) / 5);
    p.ell(200 + d * Math.cos(a) * 0.9, 170 + d * Math.sin(a) * 0.55 - 30 * t, r, r, k % 3 ? "#ffffff" : "#e3f2ff", 4);
  }
};
/** a High Court order (380 x 500): a rolled-top paper with a red seal */
export const fxCourtOrder = (p: Pen) => {
  p.poly([[30, 40], [350, 40], [350, 470], [30, 470]], "#fbf6e6", 7);
  p.ell(190, 40, 170, 18, "#efe6c8", 6);
  fit(p, "HIGH COURT", 190, 100, 40, 300); fit(p, "ORDER", 190, 146, 36, 300);
  for (let k = 0; k < 6; k++) p.stroke([[60, 200 + k * 32], [320, 200 + k * 32]], 3, "#a8a090");
  fit(p, "RELEASE THE VAN", 190, 400, 28, 300, HRED);
  p.ell(290, 440, 34, 34, HRED, 6); p.ell(290, 440, 18, 18, "#a81c22", 0);
};
/** a gavel (300 x 200), a = swing 0..1 (1 = down) */
export const fxGavel = (p: Pen, a: number) => {
  const g = p.g; g.save(); g.translate(230, 160); g.rotate(rad(-60 + 60 * a));
  p.stroke([[0, 0], [-180, 0]], 18, "#7a4a22"); p.poly([[-210, -40], [-150, -40], [-150, 40], [-210, 40]], "#5a3418", 8);
  g.restore(); p.poly([[180, 170], [290, 170], [290, 196], [180, 196]], "#5a3418", 6);
};
/** a mug of tea (200 x 220) with steam, t = steam phase */
export const fxTea = (p: Pen, t: number) => {
  p.poly([[40, 70], [150, 70], [144, 200], [46, 200]], "#f4f1ea", 8); p.arc(160, 130, 30, 36, -80, 80, 12, INK); p.arc(160, 130, 30, 36, -80, 80, 6, "#f4f1ea");
  p.ell(95, 72, 55, 12, "#a8743e", 5); p.poly([[50, 120], [140, 120], [139, 140], [51, 140]], HBLUE, 0);
  for (let k = 0; k < 2; k++) { const u = (t + k / 2) % 1; p.stroke([[80 + k * 30, 60 - 50 * u], [70 + k * 30 + 14 * Math.sin(u * 6), 40 - 50 * u]], 6, "rgba(255,255,255,0.8)"); }
};
/** an office cardboard box with a pot plant and a desk lamp (300 x 260): the fired boss carries it */
export const fxOfficeBox = (p: Pen) => {
  p.stroke([[110, 110], [100, 40]], 6, "#5d8a3a"); p.ell(96, 40, 30, 16, "#76a64a", 5, 0, 360, -30); p.ell(130, 60, 26, 14, "#5d8a3a", 5, 0, 360, 30);
  p.stroke([[200, 110], [210, 50], [180, 30]], 8, "#3a3d47"); p.poly([[160, 20], [200, 20], [190, 46], [166, 46]], "#3a3d47", 5);
  p.poly([[30, 100], [270, 100], [256, 240], [44, 240]], "#c99a5e", 8); p.poly([[30, 100], [270, 100], [262, 124], [38, 124]], "#ddb47a", 5);
};
/** quadratic-bezier chain through control triples -> polygon points */
const curve = (segs: [P2, P2, P2][], n = 10): P2[] => {
  const out: P2[] = [];
  for (const [a, c, b] of segs) for (let i = 0; i < n; i++) { const t = i / n, u = 1 - t; out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]); }
  return out;
};
/** the horse's head looking out of the horsebox window (400 x 400): 3/4 profile, nose to the left; blink 0..1, ears 0..1, chew 0..1 */
export const fxHorse = (p: Pen, blink = 0, ears = 0.5, chew = 0) => {
  const C = "#a8643a", L = "#c98a5a", D = "#7a4424", M = "#2e1e18", j = 8 * chew;
  // mane behind the neck
  p.poly(curve([[[250, 120], [330, 140], [340, 400]], [[340, 400], [300, 400], [250, 400]], [[250, 400], [270, 250], [220, 150]]]), M, 9);
  // neck + head in one shape: crown -> forehead -> long nose -> muzzle -> chin -> jaw -> throat
  const head = curve([
    [[230, 110], [180, 96], [140, 130]], [[140, 130], [90, 175], [58, 230]], [[58, 230], [34, 268], [50, 296 + j]],
    [[50, 296 + j], [70, 318 + j], [110, 306 + j]], [[110, 306 + j], [150, 296], [190, 300]], [[190, 300], [240, 304], [250, 260]],
    [[250, 260], [255, 330], [270, 400]], [[270, 400], [200, 400], [190, 400]], [[190, 400], [300, 260], [230, 110]],
  ]);
  p.shadedFill(head, C, D, 0.6, 180, 0.4, 1.05, 1.25); p.inkRing(head, 9, 4);
  // muzzle (lighter), nostril, mouth line
  p.poly(curve([[[70, 236], [40, 262], [50, 294 + j]], [[50, 294 + j], [72, 318 + j], [112, 304 + j]], [[112, 304 + j], [118, 262], [70, 236]]]), L, 6);
  p.ell(68, 262, 9, 13, M, 0, 0, 360, -30); p.stroke([[60, 296 + j], [104, 300 + j]], 5, M);
  // white blaze down the face
  p.poly(curve([[[176, 120], [150, 140], [118, 200]], [[118, 200], [100, 236], [96, 252]], [[96, 252], [128, 220], [186, 128]]]), "#fbf6ee", 0);
  // ears (pricked by `ears`), forelock
  for (const [x, lean] of [[206, 0], [236, 1]] as [number, number][]) p.poly([[x - 16, 116], [x - 4 + 10 * lean - 18 * (1 - ears), 40 - 24 * ears], [x + 18, 112]], lean ? C : D, 8);
  p.poly(curve([[[176, 110], [150, 130], [160, 170]], [[160, 170], [190, 140], [220, 112]]]), M, 5);
  // big cartoon eye with a highlight, lid for the blink
  if (blink > 0.5) p.stroke([[170, 176], [210, 172]], 7, M);
  else { p.ell(190, 172, 22, 24 * (1 - 0.6 * blink), "#ffffff", 6); p.ell(184, 176, 12, 14, M, 0); p.ell(180, 170, 4, 4, "#ffffff", 0); }
  p.arc(192, 166, 26, 22, 200, 320, 5, M);
};
/** a big airline-route arrow with a number on it (600 x 260), e.g. 220,000 flying */
export const fxCountTag = (p: Pen, text: string, sub = "") => {
  p.poly([[20, 60], [480, 60], [480, 20], [590, 130], [480, 240], [480, 200], [20, 200]], "#f2c230", 10);
  fit(p, text, 250, sub ? 115 : 130, 84, 420); if (sub) fit(p, sub, 250, 172, 30, 420);
};
/** a red SOLD sign (520 x 300) on a stake */
export const fxSold = (p: Pen, sub = "HOOVER EUROPE") => {
  p.stroke([[260, 230], [260, 300]], 18, "#7a5420");
  p.poly([[20, 20], [500, 20], [500, 240], [20, 240]], HRED, 10);
  fit(p, "SOLD", 260, 110, 130, 440, "#ffffff"); fit(p, sub, 260, 204, 36, 440, "#ffffff");
};
/** a tick-mark tally on a wall or windscreen (400 x 240), n strokes (gate of five) */
export const fxTally = (p: Pen, n: number) => {
  for (let i = 0; i < n; i++) {
    const grp = Math.floor(i / 5), j = i % 5, x0 = 30 + grp * 130;
    if (j < 4) p.stroke([[x0 + j * 22, 40], [x0 + j * 22 - 4, 200]], 12, "#ffffff");
    else p.stroke([[x0 - 14, 170], [x0 + 86, 60]], 12, "#ffffff");
  }
};
export { INK };
