// Clean-toon character kit (12 Nov 2026, owner: "the faces, the details, the quality are not looking like RicksClips3000").
// The target style (measured from reference frames, technique only, our own cast): flat 2D vector people standing in a 3D
// world. Big white round heads with an even dark ink ring; ring eyes (white discs, small pupils) that carry the acting;
// small thin mouths; hats with seams and a top button; tall bean bodies with real costume detail (stitched seams,
// hi-vis bands, breast pockets with pens, lapels, ties); single-stroke dark limbs with round hands.
// Drawn on a raw canvas in a 1000 x 1600 design box (feet at y 1560), so the engine can scale it like the other cards.
type Ctx = CanvasRenderingContext2D;
export const INK = "#241a1c";
export type Expr = "neutral" | "deadpan" | "worried" | "shock" | "grimace" | "smile" | "smirk" | "angry" | "talk";
export type Hat = "none" | "capBack" | "cap" | "flatcap" | "hardhat" | "beanie" | "bowler" | "pilot" | "helmet";
export type Held = "dipstick" | "clipboard" | "extinguisher" | "flashlight" | "map" | "jerrycan" | "spatula" | "wrench" | "nozzle";
export type Hair = "none" | "side" | "tuft" | "curly" | "bald" | "bob" | "quiff" | "spiky" | "messy" | "afro" | "ponytail" | "bun" | "mullet" | "slick" | "combover";
export type Outfit = "vest" | "coat" | "suit" | "overalls" | "jacket" | "hoodie" | "dress";
export type Spec = {
  head?: string; hat?: Hat; hatCol?: string; hair?: Hair; hairCol?: string; glasses?: boolean; mustache?: string;
  outfit: Outfit; base: string; trim?: string; shirt?: string; tie?: string; pens?: boolean; limb?: string; shoes?: string;
  /** v2 (12 Nov, close-ups): fabric pattern, accessories, painted hats, eye style */
  pattern?: "dots" | "stripes" | "check"; patCol?: string; suspenders?: string; neckerchief?: string; chain?: boolean;
  hatPattern?: "stripes"; hatGloss?: boolean; eyes?: "almond" | "ring";
  /** v5 (body bottom, limbs): trouser band colour at the bottom of the bean; white mitten hands (default) or bare dark ends */
  pants?: string; mittens?: boolean;
  /** v8 (owner: "they look like eggs ... if you can do better go ahead"): body build, and sleeves in the garment colour */
  build?: "average" | "stout" | "slim" | "broad"; sleeves?: boolean;
  /** v9 (owner: "enhance the legs and feet"): shoe type and colour, sock colour */
  footwear?: "oxford" | "boots" | "trainers" | "flats"; shoeCol?: string; socks?: string;
  /** stick = short trousers then dark stick legs (the reference look); long = full-length trousers down to the shoes */
  legStyle?: "stick" | "long";
  /** v18: kid proportions (same head, a short body), pilot uniform details (gold cuff stripes, wings badge, epaulettes), hat trim colour */
  kid?: boolean; cuffs?: string; wings?: boolean; hatTrim?: string; label?: string;
};
export type Pose = { expr?: Expr; look?: [number, number]; blink?: number; armL?: number; armR?: number; wave?: number; sweat?: boolean; tilt?: number;
  /** v2: face turn -1..1 (3/4 view: features slide to that side, hair shows on the back), upper-body lean in degrees, knee bend 0..1 */
  yaw?: number; lean?: number; knee?: number;
  /** v18 animation: walk/run phase 0..1 (+ stride 0..1), bike pedal phase (draws the bike), seated (no legs), squash
   *  (1 = rest, <1 squashed, >1 stretched), bob (upper body down, in head radii), head tilt (deg), elbow bends (deg),
   *  IK reach targets for the hands (design units), props held in the hands, extinguisher spray on/off */
  step?: number; stride?: number; pedal?: number; sit?: boolean; squash?: number; bob?: number; headTilt?: number;
  bendL?: number; bendR?: number; reachL?: [number, number]; reachR?: [number, number]; holdL?: Held; holdR?: Held; spray?: boolean };

const R = 230, CX = 500, HY = 380;                 // head radius and centre
const FEET = 1560, BODY_T = HY + 0.62 * R, BODY_B = FEET - 1.45 * R;
const W_INK = 15, SEAM = "rgba(0,0,0,0.42)";

const shade = (hex: string, k: number) => {
  const n = parseInt(hex.slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(k >= 1 ? v + (255 - v) * (k - 1) : v * k))));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};
const begin = (g: Ctx) => g.beginPath();
const inkStroke = (g: Ctx, w = W_INK) => { g.lineWidth = w; g.strokeStyle = INK; g.lineJoin = "round"; g.lineCap = "round"; g.stroke(); };
const fillInk = (g: Ctx, fill: string, w = W_INK) => { g.fillStyle = fill; g.fill(); inkStroke(g, w); };
const circle = (g: Ctx, x: number, y: number, r: number) => { begin(g); g.arc(x, y, r, 0, Math.PI * 2); };
const line = (g: Ctx, pts: [number, number][], w: number, col = INK, dash: number[] = []) => {
  begin(g); pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.setLineDash(dash); g.lineWidth = w; g.strokeStyle = col; g.lineCap = "round"; g.lineJoin = "round"; g.stroke(); g.setLineDash([]);
};
/** v8 tailored torso: a flat shoulder line with rounded corners, a waist, hips and a flat garment hem (no egg).
 *  Widths are half-widths in head radii; the jacket hem sits above the trousers, a coat hangs lower. */
const BUILDS = {
  average: { sh: 0.68, wa: 0.74, hi: 0.8, he: 0.8 },
  stout: { sh: 0.7, wa: 1.0, hi: 1.04, he: 0.96 },
  slim: { sh: 0.58, wa: 0.56, hi: 0.62, he: 0.6 },
  broad: { sh: 0.82, wa: 0.82, hi: 0.84, he: 0.82 },
};
let BLD = BUILDS.average, HEM = 0;
const JACKET_HEM = () => BODY_B - 0.5 * R;
const bodyPath = (g: Ctx, inset = 0) => {
  const t = BODY_T + inset, b = HEM - inset, h = b - t, sh = BLD.sh * R - inset, wa = BLD.wa * R - inset, hi = BLD.hi * R - inset, he = BLD.he * R - inset, rc = 0.42 * R;
  begin(g);
  g.moveTo(CX, t - 0.03 * R);
  g.quadraticCurveTo(CX + sh * 0.45, t - 0.03 * R, CX + sh * 0.84, t + 0.13 * R);                // shoulder line slopes down from the neck
  g.quadraticCurveTo(CX + sh, t + 0.2 * R, CX + sh, t + rc);                                      // soft round shoulder, no square pad
  g.bezierCurveTo(CX + sh, t + 0.48 * h, CX + wa, t + 0.48 * h, CX + wa, t + 0.6 * h);            // chest straight down to the waist
  g.bezierCurveTo(CX + wa, t + 0.7 * h, CX + hi, t + 0.74 * h, CX + hi, t + 0.88 * h);            // waist to hips (hips a touch wider)
  g.quadraticCurveTo(CX + hi, b, CX + he - 0.12 * R, b);                                           // hem corner
  g.quadraticCurveTo(CX, b + 0.03 * R, CX - he + 0.12 * R, b);                                     // a flat hem, a hint of curve
  g.quadraticCurveTo(CX - hi, b, CX - hi, t + 0.88 * h);
  g.bezierCurveTo(CX - hi, t + 0.74 * h, CX - wa, t + 0.7 * h, CX - wa, t + 0.6 * h);
  g.bezierCurveTo(CX - wa, t + 0.48 * h, CX - sh, t + 0.48 * h, CX - sh, t + rc);
  g.quadraticCurveTo(CX - sh, t + 0.2 * R, CX - sh * 0.84, t + 0.13 * R);
  g.quadraticCurveTo(CX - sh * 0.45, t - 0.03 * R, CX, t - 0.03 * R);
  g.closePath();
};
/** trousers: a separate piece under the jacket, with a crotch notch and two leg openings (cuffs) */
const trousers = (g: Ctx, s: Spec) => {
  if (s.outfit === "dress") return;
  const long = s.legStyle === "long", col = s.outfit === "overalls" ? s.base : (s.pants ?? "#4a3426"), top = JACKET_HEM() - 0.3 * R, bot = long ? FEET - 0.17 * R : BODY_B + 0.42 * R, hw = BLD.hi * R * 0.9, cw = long ? 0.17 * R : 0.2 * R;
  const path = () => {
    begin(g); g.moveTo(CX - hw, top); g.lineTo(CX + hw, top);
    g.bezierCurveTo(CX + hw, top + 0.45 * R, CX + 0.28 * R + cw + 0.02 * R, top + 0.9 * R, CX + 0.28 * R + cw, bot);
    g.lineTo(CX + 0.28 * R - cw, bot); g.lineTo(CX + 0.1 * R, top + 0.75 * R); g.quadraticCurveTo(CX, top + 0.6 * R, CX - 0.1 * R, top + 0.75 * R);
    g.lineTo(CX - 0.28 * R + cw, bot); g.lineTo(CX - 0.28 * R - cw, bot);
    g.bezierCurveTo(CX - 0.28 * R - cw - 0.02 * R, top + 0.9 * R, CX - hw, top + 0.45 * R, CX - hw, top); g.closePath();
  };
  path(); g.fillStyle = col; g.fill();
  withClip(g, path, () => {
    const cyl = g.createLinearGradient(CX - R, 0, CX + R, 0); cyl.addColorStop(0, "rgba(255,255,255,0.12)"); cyl.addColorStop(0.35, "rgba(255,255,255,0)"); cyl.addColorStop(1, "rgba(10,10,20,0.35)");
    g.fillStyle = cyl; g.fillRect(CX - 2 * R, top, 4 * R, bot - top + 10);
    line(g, [[CX, top + 0.62 * R], [CX, top]], 4, "rgba(0,0,0,0.3)");
    for (const sd of [-1, 1]) { line(g, [[CX + sd * (0.28 * R - cw), bot - 0.06 * R], [CX + sd * (0.28 * R + cw), bot - 0.06 * R]], 4, "rgba(0,0,0,0.3)"); line(g, [[CX + sd * 0.28 * R, top + 0.85 * R], [CX + sd * 0.28 * R, bot - 0.1 * R]], 3, "rgba(255,255,255,0.12)"); }
  });
  path(); inkStroke(g, W_INK);
};
const withClip = (g: Ctx, path: () => void, fn: () => void) => { g.save(); path(); g.clip(); fn(); g.restore(); };

// ---------------------------------------------------------------- body + outfit
const outfit = (g: Ctx, s: Spec) => {
  const base = s.base, dark = shade(base, 0.8), trim = s.trim ?? shade(base, 0.62);
  bodyPath(g); g.fillStyle = base; g.fill();
  withClip(g, () => bodyPath(g), () => {
    // a soft shadow side (light from the upper left) and a hem shade
    // (lighting goes on last, over the details: see the end of this clip block)
    const tx = (x: number) => CX + x * R;
    if (s.outfit === "vest") {
      // hi-vis vest: two vertical reflective bands with stitched borders, one horizontal band, a centre zip
      const band = s.trim ?? "#cfd3d8";
      for (const x of [-0.5, 0.5]) { g.fillStyle = band; g.fillRect(tx(x) - 0.13 * R, BODY_T, 0.26 * R, 2.2 * R); line(g, [[tx(x) - 0.13 * R, BODY_T], [tx(x) - 0.13 * R, BODY_B]], 5, dark); line(g, [[tx(x) + 0.13 * R, BODY_T], [tx(x) + 0.13 * R, BODY_B]], 5, dark); }
      g.fillStyle = band; g.fillRect(CX - 1.2 * R, BODY_T + 1.25 * R, 2.4 * R, 0.24 * R);
      line(g, [[CX - 1.2 * R, BODY_T + 1.25 * R], [CX + 1.2 * R, BODY_T + 1.25 * R]], 5, dark); line(g, [[CX - 1.2 * R, BODY_T + 1.49 * R], [CX + 1.2 * R, BODY_T + 1.49 * R]], 5, dark);
      for (const x of [-0.5, 0.5]) line(g, [[tx(x), BODY_T + 20], [tx(x), BODY_B]], 4, SEAM, [16, 12]);
      line(g, [[CX, BODY_T + 20], [CX, BODY_B]], 6, dark);
    } else if (s.outfit === "coat") {
      // lab coat / shop coat: shirt V, tie, lapels, breast pocket with pens, buttons
      const shirt = s.shirt ?? "#eef2f6";
      begin(g); g.moveTo(CX - 0.32 * R, BODY_T); g.lineTo(CX, BODY_T + 0.95 * R); g.lineTo(CX + 0.32 * R, BODY_T); g.closePath(); g.fillStyle = shirt; g.fill();
      if (s.tie) { begin(g); g.moveTo(CX - 0.07 * R, BODY_T + 0.08 * R); g.lineTo(CX + 0.07 * R, BODY_T + 0.08 * R); g.lineTo(CX + 0.1 * R, BODY_T + 0.8 * R); g.lineTo(CX, BODY_T + 0.92 * R); g.lineTo(CX - 0.1 * R, BODY_T + 0.8 * R); g.closePath(); fillInk(g, s.tie, 6); }
      for (const sd of [-1, 1]) { begin(g); g.moveTo(CX + sd * 0.32 * R, BODY_T - 6); g.lineTo(CX + sd * 0.02 * R, BODY_T + 1.0 * R); g.lineTo(CX + sd * 0.42 * R, BODY_T + 0.42 * R); g.closePath(); g.fillStyle = shade(base, 0.93); g.fill(); inkStroke(g, 6); }
      line(g, [[CX, BODY_T + 1.0 * R], [CX, HEM + 10]], 6, INK);
      for (let k = 0; k < 3; k++) circle(g, CX + 0.1 * R, BODY_T + (1.25 + 0.42 * k) * R, 9), fillInk(g, shade(base, 0.85), 4);
      const px = CX - 0.62 * R, py = BODY_T + 0.62 * R;
      if (s.pens !== false) { line(g, [[px + 18, py + 20], [px + 18, py - 40]], 16, "#d8262e"); line(g, [[px + 48, py + 20], [px + 48, py - 34]], 16, "#2f5fb0"); }
      begin(g); g.rect(px - 10, py, 0.42 * R, 0.36 * R); fillInk(g, shade(base, 0.96), 6);
      line(g, [[px + 2, py + 16], [px - 22 + 0.42 * R, py + 16]], 3, SEAM, [10, 8]);
    } else if (s.outfit === "suit") {
      const shirt = s.shirt ?? "#f4f4f2";
      begin(g); g.moveTo(CX - 0.28 * R, BODY_T); g.lineTo(CX, BODY_T + 0.9 * R); g.lineTo(CX + 0.28 * R, BODY_T); g.closePath(); g.fillStyle = shirt; g.fill();
      begin(g); g.moveTo(CX - 0.06 * R, BODY_T + 0.06 * R); g.lineTo(CX + 0.06 * R, BODY_T + 0.06 * R); g.lineTo(CX + 0.09 * R, BODY_T + 0.74 * R); g.lineTo(CX, BODY_T + 0.86 * R); g.lineTo(CX - 0.09 * R, BODY_T + 0.74 * R); g.closePath(); fillInk(g, s.tie ?? "#d8262e", 6);
      for (const sd of [-1, 1]) { begin(g); g.moveTo(CX + sd * 0.28 * R, BODY_T - 6); g.lineTo(CX + sd * 0.03 * R, BODY_T + 0.92 * R); g.lineTo(CX + sd * 0.4 * R, BODY_T + 0.5 * R); g.lineTo(CX + sd * 0.3 * R, BODY_T + 0.3 * R); g.closePath(); g.fillStyle = shade(base, 1.18); g.fill(); inkStroke(g, 6); }
      for (let k = 0; k < 2; k++) circle(g, CX + 0.08 * R, BODY_T + (1.15 + 0.4 * k) * R, 9), fillInk(g, shade(base, 0.6), 4);
      begin(g); g.rect(CX + 0.4 * R, BODY_T + 0.62 * R, 0.34 * R, 0.08 * R); fillInk(g, shade(base, 0.85), 4);
      begin(g); g.moveTo(CX + 0.45 * R, BODY_T + 0.62 * R); g.lineTo(CX + 0.52 * R, BODY_T + 0.5 * R); g.lineTo(CX + 0.6 * R, BODY_T + 0.62 * R); g.closePath(); g.fillStyle = "#ffffff"; g.fill();
      if (s.wings) { const wx = CX - 0.5 * R, wy = BODY_T + 0.55 * R, gold = s.cuffs ?? "#d9a640";
        for (const sd of [-1, 1]) { begin(g); g.moveTo(wx, wy); g.quadraticCurveTo(wx + sd * 0.2 * R, wy - 0.1 * R, wx + sd * 0.3 * R, wy - 0.04 * R); g.quadraticCurveTo(wx + sd * 0.18 * R, wy + 0.04 * R, wx, wy + 0.04 * R); g.closePath(); fillInk(g, gold, 4); }
        circle(g, wx, wy, 0.05 * R); fillInk(g, gold, 4); }
      if (s.cuffs) for (const sd of [-1, 1]) for (const o of [0.08, 0.16]) line(g, [[CX + sd * (BLD.sh - 0.42) * R, BODY_T + o * R], [CX + sd * (BLD.sh - 0.12) * R, BODY_T + o * R + 0.03 * R]], 0.035 * R, s.cuffs);
    } else if (s.outfit === "overalls") {
      const shirt = s.shirt ?? "#e8e2d4";
      g.fillStyle = shirt; g.fillRect(CX - 2 * R, BODY_T - 50, 4 * R, 0.55 * R + 50);
      begin(g); g.rect(CX - 0.5 * R, BODY_T + 0.25 * R, R, 0.75 * R); fillInk(g, shade(base, 1.06), 7);
      line(g, [[CX - 0.42 * R, BODY_T + 0.33 * R], [CX + 0.42 * R, BODY_T + 0.33 * R], [CX + 0.42 * R, BODY_T + 0.92 * R], [CX - 0.42 * R, BODY_T + 0.92 * R], [CX - 0.42 * R, BODY_T + 0.33 * R]], 4, SEAM, [14, 10]);
      for (const sd of [-1, 1]) { line(g, [[CX + sd * 0.42 * R, BODY_T + 0.3 * R], [CX + sd * 0.78 * R, BODY_T - 10]], 34, shade(base, 0.92)); circle(g, CX + sd * 0.42 * R, BODY_T + 0.32 * R, 13); fillInk(g, "#d9a640", 5); }
      line(g, [[CX - 0.98 * R, BODY_T + 1.12 * R], [CX + 0.98 * R, BODY_T + 1.12 * R]], 4, SEAM, [14, 10]);
      begin(g); g.rect(CX - 0.2 * R, BODY_T + 0.42 * R, 0.4 * R, 0.3 * R); fillInk(g, base, 5);
      line(g, [[CX, BODY_T + 1.4 * R], [CX, BODY_B]], 5, dark);
    } else if (s.outfit === "jacket") {
      // waxed jacket: collar, zip, two flap pockets, stitched hem
      begin(g); g.moveTo(CX - 0.42 * R, BODY_T - 4); g.lineTo(CX, BODY_T + 0.32 * R); g.lineTo(CX + 0.42 * R, BODY_T - 4); g.lineTo(CX + 0.3 * R, BODY_T + 0.3 * R); g.lineTo(CX, BODY_T + 0.44 * R); g.lineTo(CX - 0.3 * R, BODY_T + 0.3 * R); g.closePath(); fillInk(g, trim, 6);
      line(g, [[CX, BODY_T + 0.44 * R], [CX, BODY_B]], 6, dark);
      for (let k = 0; k < 3; k++) { const by = BODY_T + (0.75 + 0.62 * k) * R; circle(g, CX, by, 0.11 * R); fillInk(g, "#f7f6f2", 7); circle(g, CX - 0.035 * R, by, 0.022 * R); g.fillStyle = INK; g.fill(); circle(g, CX + 0.035 * R, by, 0.022 * R); g.fill(); }
      for (const sd of [-1, 1]) { const px = CX + sd * 0.48 * R; begin(g); g.rect(px - 0.24 * R, BODY_T + 1.25 * R, 0.48 * R, 0.4 * R); fillInk(g, shade(base, 0.95), 6); begin(g); g.rect(px - 0.26 * R, BODY_T + 1.2 * R, 0.52 * R, 0.13 * R); fillInk(g, dark, 6); circle(g, px, BODY_T + 1.3 * R, 8); fillInk(g, "#d9a640", 3); }
      line(g, [[CX - R, BODY_B - 70], [CX + R, BODY_B - 70]], 4, SEAM, [14, 10]);
    } else if (s.outfit === "hoodie") {
      begin(g); g.ellipse(CX, BODY_T + 0.05 * R, 0.7 * R, 0.2 * R, 0, 0, Math.PI * 2); fillInk(g, dark, 7);
      for (const sd of [-1, 1]) line(g, [[CX + sd * 0.15 * R, BODY_T + 0.15 * R], [CX + sd * 0.17 * R, BODY_T + 0.65 * R]], 7, "#f4f1ea");
      begin(g); g.moveTo(CX - 0.6 * R, BODY_T + 1.25 * R); g.lineTo(CX + 0.6 * R, BODY_T + 1.25 * R); g.lineTo(CX + 0.75 * R, BODY_T + 1.75 * R); g.lineTo(CX - 0.75 * R, BODY_T + 1.75 * R); g.closePath(); fillInk(g, shade(base, 0.92), 6);
    } else if (s.outfit === "dress") {
      begin(g); g.ellipse(CX, BODY_T + 0.1 * R, 0.4 * R, 0.16 * R, 0, 0, Math.PI * 2); fillInk(g, s.shirt ?? "#ffffff", 6);
      for (let k = 0; k < 3; k++) circle(g, CX, BODY_T + (0.5 + 0.35 * k) * R, 8), fillInk(g, "#ffffff", 4);
      line(g, [[CX - R, BODY_T + 1.3 * R], [CX + R, BODY_T + 1.3 * R]], 12, trim);
    }
    if (s.pattern) {
      const pc = s.patCol ?? shade(base, 1.35);
      if (s.pattern === "dots") for (let y = BODY_T + 20; y < BODY_B; y += 42) for (let x = CX - 1.1 * R + ((y / 42) % 2) * 21; x < CX + 1.1 * R; x += 42) { circle(g, x, y, 7); g.fillStyle = pc; g.fill(); }
      if (s.pattern === "stripes") for (let x = CX - 1.1 * R; x < CX + 1.1 * R; x += 46) line(g, [[x, BODY_T - 20], [x + 10, BODY_B + 20]], 16, pc);
      if (s.pattern === "check") { for (let x = CX - 1.1 * R; x < CX + 1.1 * R; x += 70) line(g, [[x, BODY_T - 20], [x, BODY_B + 20]], 10, pc); for (let y = BODY_T; y < BODY_B; y += 70) line(g, [[CX - 1.2 * R, y], [CX + 1.2 * R, y]], 10, pc); }
    }
    if (s.suspenders) for (const sd of [-1, 1]) {
      const x0 = CX + sd * 0.42 * R; begin(g); g.moveTo(x0 - 22, BODY_T - 10); g.lineTo(x0 + 22, BODY_T - 10); g.lineTo(x0 + 22 + sd * 6, BODY_B); g.lineTo(x0 - 22 + sd * 6, BODY_B); g.closePath(); fillInk(g, s.suspenders, 5); line(g, [[x0, BODY_T], [x0 + sd * 6, BODY_B]], 5, "rgba(255,255,255,0.8)", [14, 12]);
      begin(g); g.rect(x0 - 24, BODY_T + 0.55 * R, 48, 40); fillInk(g, "#d9a640", 5); begin(g); g.rect(x0 - 12, BODY_T + 0.55 * R + 10, 24, 20); g.fillStyle = shade("#d9a640", 0.6); g.fill();
    }
    if (s.chain) { begin(g); g.moveTo(CX - 0.55 * R, BODY_T + 1.05 * R); g.quadraticCurveTo(CX - 0.1 * R, BODY_T + 1.45 * R, CX + 0.45 * R, BODY_T + 1.0 * R); g.lineWidth = 3; g.strokeStyle = "rgba(0,0,0,0)"; g.stroke(); for (let k = 0; k <= 14; k++) { const u = k / 14, x = (1 - u) * (1 - u) * (CX - 0.55 * R) + 2 * u * (1 - u) * (CX - 0.1 * R) + u * u * (CX + 0.45 * R), y = (1 - u) * (1 - u) * (BODY_T + 1.05 * R) + 2 * u * (1 - u) * (BODY_T + 1.45 * R) + u * u * (BODY_T + 1.0 * R); begin(g); g.ellipse(x, y, 13, 9, k % 2 ? 0.6 : -0.6, 0, Math.PI * 2); g.fillStyle = "#e8b84a"; g.fill(); g.lineWidth = 4; g.strokeStyle = "#8a6420"; g.stroke(); } circle(g, CX + 0.45 * R, BODY_T + 1.0 * R, 16); fillInk(g, "#e8b84a", 5); }
    if (s.neckerchief) {
      begin(g); g.moveTo(CX - 0.42 * R, BODY_T - 6); g.lineTo(CX + 0.42 * R, BODY_T - 6); g.lineTo(CX + 0.04 * R, BODY_T + 0.6 * R); g.closePath(); fillInk(g, s.neckerchief, 7);
      for (const [dx, dy] of [[-0.2, 0.08], [0, 0.12], [0.2, 0.08], [-0.08, 0.28], [0.12, 0.28], [0.02, 0.44]]) { circle(g, CX + dx * R, BODY_T + dy * R, 8); g.fillStyle = "#ffffff"; g.fill(); }
    }
    if (s.suspenders) for (const sd of [-1, 1]) { const x0 = CX + sd * 0.42 * R + sd * 6, hm = HEM; begin(g); g.rect(x0 - 24, hm - 56, 48, 40); fillInk(g, "#d9a640", 5); begin(g); g.rect(x0 - 12, hm - 46, 24, 20); g.fillStyle = shade("#d9a640", 0.6); g.fill(); }
    // studio key on the clothes (owner, 12 Nov: "see how the light is different like a studio even in the clothes").
    // Measured across a reference vest: a bright rim on the lit (left) edge about +45 %, the base, then a steady falloff
    // to about -30 % on the far edge: a cylinder lit from the front-left, not a flat fill.
    const x0 = CX - 1.0 * R, x1 = CX + 1.0 * R;
    const cyl = g.createLinearGradient(x0, 0, x1, 0);
    cyl.addColorStop(0, "rgba(255,255,255,0.0)"); cyl.addColorStop(0.18, "rgba(255,255,255,0.10)"); cyl.addColorStop(0.42, "rgba(255,255,255,0)");
    cyl.addColorStop(0.7, "rgba(10,20,30,0.14)"); cyl.addColorStop(1, "rgba(10,20,30,0.36)");
    g.fillStyle = cyl; g.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, HEM - BODY_T + 120);
    // the lit rim: a bright band just inside the left outline, soft on its inner side
    g.save(); bodyPath(g); g.lineWidth = 0.2 * R; g.strokeStyle = "rgba(255,255,255,0.32)";
    const rimMask = g.createLinearGradient(x0, 0, x0 + 0.5 * R, 0); rimMask.addColorStop(0, "rgba(255,255,255,0.34)"); rimMask.addColorStop(0.55, "rgba(255,255,255,0.1)"); rimMask.addColorStop(1, "rgba(255,255,255,0)");
    g.strokeStyle = rimMask; g.stroke(); g.restore();
    // top-down: a little brighter at the chest, darker toward the round bottom; the head's shadow under the chin
    const vert = g.createLinearGradient(0, BODY_T, 0, HEM); vert.addColorStop(0, "rgba(255,255,255,0.06)"); vert.addColorStop(0.55, "rgba(255,255,255,0)"); vert.addColorStop(1, "rgba(20,14,30,0.22)");
    g.fillStyle = vert; g.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, HEM - BODY_T + 120);
    const sh = g.createLinearGradient(0, BODY_T, 0, BODY_T + 0.4 * R); sh.addColorStop(0, "rgba(30,24,40,0.34)"); sh.addColorStop(1, "rgba(30,24,40,0)");
    g.fillStyle = sh; g.beginPath(); g.ellipse(CX + 0.05 * R, BODY_T, 0.9 * R, 0.4 * R, 0, 0, Math.PI * 2); g.fill();
  });
  bodyPath(g); inkStroke(g, W_INK);
};

// ---------------------------------------------------------------- head, hair, hats, face
const headPath = (g: Ctx) => { begin(g); g.ellipse(CX, HY, R * 1.02, R, 0, 0, Math.PI * 2); };
/** studio key light in front of the face, slightly above and left (owner, 12 Nov: "a light in the faces like a shadow
 *  coming from a light front of him like a studio"): a bright zone on the upper face, a smooth spherical falloff to a cool
 *  grey at the edges and the chin. Measured on reference frames: centre about 0.2 R up-left, grey by about 1.05 R. */
const keyLight = (g: Ctx, cx: number, cy: number, r: number, k = 1) => {
  const gr = g.createRadialGradient(cx - 0.16 * r, cy - 0.3 * r, 0.05 * r, cx - 0.08 * r, cy - 0.12 * r, 1.12 * r);
  gr.addColorStop(0, "rgba(255,255,255,0)"); gr.addColorStop(0.45, `rgba(92,84,100,${0.03 * k})`);
  gr.addColorStop(0.8, `rgba(84,76,96,${0.13 * k})`); gr.addColorStop(1, `rgba(72,64,88,${0.26 * k})`);
  g.fillStyle = gr; g.fillRect(cx - 2 * r, cy - 2 * r, 4 * r, 4 * r);
};
/** the soft shadow a hat brim casts on the forehead */
const brimShadow = (g: Ctx, y: number) => {
  const gr = g.createLinearGradient(0, y - 4, 0, y + 0.3 * R); gr.addColorStop(0, "rgba(40,30,40,0.32)"); gr.addColorStop(1, "rgba(40,30,40,0)");
  g.fillStyle = gr; g.fillRect(CX - 1.2 * R, y - 4, 2.4 * R, 0.32 * R);
};
const brimY = (s: Spec) => s.hat === "pilot" ? HY - 0.44 * R : s.hat === "helmet" ? HY - 0.6 * R : s.hat === "capBack" || s.hat === "cap" ? HY - 0.46 * R : s.hat === "flatcap" ? HY - 0.5 * R : s.hat === "hardhat" ? HY - 0.48 * R : s.hat === "beanie" ? HY - 0.5 * R : s.hat === "bowler" ? HY - 0.6 * R : 0;
const head = (g: Ctx, s: Spec) => {
  const col = s.head ?? "#fbfaf7";
  headPath(g); g.fillStyle = col; g.fill();
  withClip(g, () => headPath(g), () => {
    keyLight(g, CX, HY, R);
    if (s.hat && s.hat !== "none") brimShadow(g, brimY(s));
  });
  headPath(g); inkStroke(g, 0.085 * R);
};
// ---------------------------------------------------------------- hair v11 (owner, 12 Nov: "enhance the hair make it more
// personalized and like cartoons"). Every style is a few closed shapes in head units (u = x / R, v = y / R from the head
// centre), drawn as one cartoon mass: a thick ink pass under a colour pass, so only the outer silhouette is inked; then
// lit from the front-left, a glossy shine band across the crown and darker strand lines that show the comb direction.
// Back layers (bob, ponytail, mullet, afro) sit behind the head; under a hat the hair still peeks out at the temples.
type HP = [number, number] | [number, number, number];          // third value 1 = a sharp corner (lock tips)
const hx = (p: HP) => CX + p[0] * R, hy = (p: HP) => HY + p[1] * R;
const smoothClosed = (g: Ctx, pts: HP[]) => {
  const n = pts.length; g.moveTo(hx(pts[0]), hy(pts[0]));
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    const k1 = p1[2] ? 0 : 1 / 6, k2 = p2[2] ? 0 : 1 / 6;
    g.bezierCurveTo(hx(p1) + (hx(p2) - hx(p0)) * k1, hy(p1) + (hy(p2) - hy(p0)) * k1, hx(p2) - (hx(p3) - hx(p1)) * k2, hy(p2) - (hy(p3) - hy(p1)) * k2, hx(p2), hy(p2));
  }
  g.closePath();
};
const smoothOpen = (g: Ctx, pts: HP[]) => {
  g.moveTo(hx(pts[0]), hy(pts[0]));
  if (pts.length === 2) { g.lineTo(hx(pts[1]), hy(pts[1])); return; }
  for (let i = 1; i < pts.length - 1; i++) { const mx = (hx(pts[i]) + hx(pts[i + 1])) / 2, my = (hy(pts[i]) + hy(pts[i + 1])) / 2; g.quadraticCurveTo(hx(pts[i]), hy(pts[i]), i === pts.length - 2 ? hx(pts[i + 1]) : mx, i === pts.length - 2 ? hy(pts[i + 1]) : my); }
};
/** points on the head outline grown by `grow`, from angle a0 to a1 in degrees (180 = left, 270 = top, 360 = right) */
const arcP = (a0: number, a1: number, grow = 0.07, n = 11): HP[] => Array.from({ length: n }, (_, i) => { const a = ((a0 + ((a1 - a0) * i) / (n - 1)) * Math.PI) / 180; return [(1.02 + grow) * Math.cos(a), (1 + grow) * Math.sin(a)] as HP; });
const blob = (u: number, v: number, r: number, n = 8): HP[] => Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return [u + r * Math.cos(a), v + r * 0.94 * Math.sin(a)] as HP; });
/** a pointed lock rooted inside the hair at angle phi, reaching out to radius len, bending by lean degrees */
const lock = (phi: number, len: number, lean = 0, w = 10): HP[] => {
  const P2 = (a: number, r: number): HP => [1.02 * r * Math.cos((a * Math.PI) / 180), r * Math.sin((a * Math.PI) / 180)];
  const t = P2(phi + lean, len);
  return [P2(phi - w, 0.88), P2(phi - w * 0.35 + lean * 0.4, (0.9 + len) / 2 + 0.03), [t[0], t[1], 1], P2(phi + w * 0.45 + lean * 0.4, (0.9 + len) / 2 - 0.03), P2(phi + w, 0.88)];
};
const area = (pts: HP[]) => pts.reduce((a, p, i) => { const q = pts[(i + 1) % pts.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0);
const orient = (pts: HP[]) => (area(pts) < 0 ? [...pts].reverse() : pts);
const paintHair = (g: Ctx, shapes: HP[][], c: string, strands: HP[][] = [], shine = 1) => {
  if (!shapes.length) return;
  const all = shapes.map(orient), union = () => { begin(g); for (const sh of all) smoothClosed(g, sh); };
  g.save(); g.lineJoin = "round"; g.lineCap = "round";
  union(); g.lineWidth = 22; g.strokeStyle = INK; g.stroke();                 // ink silhouette (half of it is covered by the fill)
  union(); g.fillStyle = c; g.fill();
  withClip(g, union, () => {
    const gr = g.createLinearGradient(CX - 1.1 * R, HY - 1.15 * R, CX + 1.1 * R, HY + 0.5 * R);
    gr.addColorStop(0, "rgba(255,255,255,0.22)"); gr.addColorStop(0.42, "rgba(255,255,255,0)"); gr.addColorStop(1, "rgba(12,8,24,0.42)");
    g.fillStyle = gr; g.fillRect(CX - 2.5 * R, HY - 2.5 * R, 5 * R, 5 * R);
    for (const st of strands) { begin(g); smoothOpen(g, st); g.lineWidth = 6; g.strokeStyle = shade(c, 0.58); g.stroke(); }
    if (shine) for (const [a0, a1] of [[1.12, 1.32], [1.37, 1.46]]) {
      begin(g); g.ellipse(CX - 0.04 * R, HY - 0.02 * R, 0.84 * R, 0.84 * R, 0, Math.PI * a0, Math.PI * a1);
      g.lineWidth = 0.075 * R; g.strokeStyle = `rgba(255,255,255,${Math.min(0.6, 0.34 * shine)})`; g.stroke();
    }
  });
  g.restore();
};
const mirror = (pts: HP[]): HP[] => [...pts].reverse().map((p) => (p[2] ? [-p[0], p[1], 1] : [-p[0], p[1]]) as HP);
const scalpShine = (g: Ctx) => { begin(g); g.ellipse(CX - 0.36 * R, HY - 0.7 * R, 0.24 * R, 0.09 * R, -0.55, 0, Math.PI * 2); g.fillStyle = "rgba(255,255,255,0.75)"; g.fill(); circle(g, CX - 0.08 * R, HY - 0.86 * R, 0.035 * R); g.fill(); };
type HairLook = { back?: HP[][]; front: HP[][]; strands?: HP[][]; backStrands?: HP[][]; shine?: number; extra?: (g: Ctx, c: string) => void };
const hairLook = (s: Spec): HairLook => {
  const st = s.hair ?? "none", hatted = !!s.hat && s.hat !== "none", bv = hatted ? (brimY(s) - HY) / R : 0;
  const cap = (grow = 0.07): HP[] => arcP(172, 368, grow);                    // left sideburn -> over the crown -> right sideburn
  const sideClumps = (): HP[][] => [1, -1].map((sd) => { const r: HP[] = [[0.82, bv - 0.05], [1.1, bv - 0.04], [1.2, bv + 0.13, 1], [1.07, bv + 0.15], [1.13, bv + 0.31, 1], [0.99, bv + 0.27], [0.96, bv + 0.42, 1], [0.88, bv + 0.2]]; return sd > 0 ? r : mirror(r); });
  const underFringe = (): HP[][] => (["flatcap", "beanie", "hardhat", "bowler"].includes(s.hat ?? "") ? [[[-0.52, bv - 0.03], [-0.34, bv + 0.26, 1], [-0.22, bv - 0.03]], [[-0.24, bv - 0.03], [-0.04, bv + 0.21, 1], [0.08, bv - 0.03]]] : []);
  const fluff = (): HP[][] => [blob(-1.0, -0.22, 0.17), blob(-1.04, 0.04, 0.15), blob(1.0, -0.22, 0.17), blob(1.04, 0.04, 0.15)];
  const combStrands: (g: Ctx, c: string) => void = (g, c) => {
    for (const [dv, du] of [[0, 0], [0.1, 0.05], [0.2, 0.1], [0.3, 0.12]] as [number, number][]) {
      const pts: HP[] = [[-0.92, -0.32 + dv * 0.3], [-0.55, -0.93 + dv], [0.1, -1.0 + dv], [0.58 + du, -0.68 + dv * 0.6]];
      for (const [w, col] of [[17, INK], [8, c]] as [number, string][]) { begin(g); smoothOpen(g, pts); g.lineWidth = w; g.strokeStyle = col; g.lineCap = "round"; g.stroke(); }
    }
  };
  const mulletBack: HP[] = [[-0.82, 0.2], [-0.98, 0.55], [-1.0, 0.8], [-1.16, 0.98, 1], [-0.88, 0.92], [-0.72, 1.04, 1], [-0.55, 0.84], [0.55, 0.84], [0.72, 1.04, 1], [0.88, 0.92], [1.16, 0.98, 1], [1.0, 0.8], [0.98, 0.55], [0.82, 0.2]];
  const bobBack: HP[] = [[-1.2, 0.7, 1], ...arcP(178, 362, 0.15), [1.2, 0.7, 1], [0.9, 0.62], [0, 0.76], [-0.9, 0.62]];
  const curtain = (sd: number): HP[] => { const r: HP[] = [[0.84, hatted ? bv : -0.2], [1.1, hatted ? bv : -0.1], [1.05, 0.52, 1], [0.9, 0.46]]; return sd > 0 ? r : mirror(r); };
  const ponyBack: HP[] = [[0.72, -0.82], [1.1, -0.78], [1.46, -0.36], [1.52, 0.2], [1.33, 0.78, 1], [1.24, 0.26], [1.05, -0.2], [0.8, -0.45]];
  const ponyStr: HP[][] = [[[1.02, -0.68], [1.33, -0.3], [1.38, 0.4]], [[0.95, -0.55], [1.18, -0.2], [1.27, 0.35]]];
  const tie = (x: number, y: number) => (g: Ctx) => { circle(g, CX + x * R, HY + y * R, 0.085 * R); fillInk(g, "#d8262e", 7); };
  if (hatted) {
    const back = st === "bob" ? [bobBack] : st === "ponytail" ? [ponyBack] : st === "mullet" ? [mulletBack] : [];
    if (st === "none") return { front: [] };
    if (st === "bald" || st === "combover") return { front: bv < -0.2 ? fluff() : [], shine: 0 };
    if (st === "curly" || st === "afro") return { front: [-1, 1].flatMap((sd) => [blob(sd * 1.0, bv + 0.1, 0.18), blob(sd * 1.04, bv + 0.36, 0.15)]), shine: 0 };
    if (st === "bob") return { back, front: [curtain(1), curtain(-1)], shine: 0 };
    return { back, backStrands: st === "ponytail" ? ponyStr : [], front: [...sideClumps(), ...(["bun", "slick", "ponytail"].includes(st) ? [] : underFringe())], shine: 0, extra: st === "ponytail" ? tie(0.98, -0.66) : undefined };
  }
  switch (st) {
    case "side": return {
      front: [[...cap(), [0.93, 0.12, 1], [0.92, -0.3], [0.72, -0.4], [0.55, -0.32, 1], [0.36, -0.5], [0.12, -0.42, 1], [-0.12, -0.58], [-0.4, -0.72, 1], [-0.62, -0.55], [-0.86, -0.28], [-0.93, 0.12, 1]],
        [[0.02, -1.0], [0.1, -1.18], [0.34, -1.32, 1], [0.26, -1.12], [0.2, -1.0]]],
      strands: [[[-0.4, -0.72], [0.0, -0.88], [0.45, -0.75], [0.7, -0.5]], [[-0.25, -0.97], [0.2, -1.0], [0.62, -0.74]], [[-0.55, -0.62], [-0.78, -0.38]]] };
    case "quiff": return {
      front: [[...cap(), [0.93, 0.12, 1], [0.9, -0.35], [0.55, -0.6], [0.2, -0.66], [-0.3, -0.62], [-0.7, -0.45], [-0.92, 0.12, 1]],
        [[-0.68, -0.55], [-0.6, -1.05], [-0.18, -1.44], [0.45, -1.48], [0.86, -1.22], [0.95, -0.96, 1], [0.72, -1.06], [0.45, -0.86], [0.1, -0.72]]],
      strands: [[[-0.48, -0.68], [-0.32, -1.18], [0.3, -1.37], [0.76, -1.16]], [[-0.15, -0.7], [0.05, -1.07], [0.52, -1.16]]], shine: 1.3 };
    case "spiky": return {
      front: [[...cap(0.05), [0.93, 0.1, 1], [0.9, -0.3], [0.75, -0.42, 1], [0.55, -0.56, 1], [0.38, -0.36, 1], [0.18, -0.56, 1], [0.0, -0.34, 1], [-0.18, -0.56, 1], [-0.38, -0.36, 1], [-0.55, -0.56, 1], [-0.75, -0.4, 1], [-0.92, 0.1, 1]],
        ...[200, 222, 244, 266, 288, 310, 332].map((ph, i) => lock(ph, i % 2 ? 1.32 : 1.46, 7, 11))],
      strands: [[[-0.3, -0.62], [-0.4, -0.95]], [[0.25, -0.62], [0.32, -0.95]]] };
    case "messy": return {
      front: [[...arcP(170, 370, 0.08), [0.95, 0.15, 1], [0.88, -0.2], [0.72, -0.3, 1], [0.6, -0.52], [0.44, -0.33, 1], [0.25, -0.54], [0.04, -0.31, 1], [-0.15, -0.52], [-0.38, -0.32, 1], [-0.55, -0.52], [-0.75, -0.3, 1], [-0.88, -0.15], [-0.95, 0.15, 1]],
        lock(212, 1.3, -14), lock(256, 1.28, 16, 9), lock(320, 1.24, 12, 9)],
      strands: [[[-0.2, -0.95], [-0.25, -0.62]], [[0.25, -0.97], [0.32, -0.62]], [[0.62, -0.82], [0.7, -0.5]]] };
    case "curly": return {
      front: [[...arcP(170, 370, 0), [0.9, 0.05, 1], [0.8, -0.55], [-0.8, -0.55], [-0.9, 0.05, 1]],
        ...[165, 186, 207, 228, 249, 270, 291, 312, 333, 354, 375].map((a) => blob(1.0 * Math.cos((a * Math.PI) / 180), 0.97 * Math.sin((a * Math.PI) / 180), 0.25)),
        ...[-0.55, -0.2, 0.15, 0.5].map((u) => blob(u, -0.6, 0.2))],
      strands: [...[200, 240, 280, 320].map((a): HP[] => { const u = 0.85 * Math.cos((a * Math.PI) / 180), v = 0.83 * Math.sin((a * Math.PI) / 180); return [[u - 0.08, v + 0.02], [u, v - 0.08], [u + 0.09, v]]; }),
        ...[-0.37, 0.0, 0.33].map((u): HP[] => [[u - 0.07, -0.55], [u, -0.63], [u + 0.07, -0.56]])], shine: 0.8 };
    case "afro": return {
      back: [blob(0, -0.45, 1.15, 12), ...Array.from({ length: 14 }, (_, i) => { const a = (i / 14) * Math.PI * 2; return blob(1.18 * Math.cos(a), -0.45 + 1.1 * Math.sin(a), 0.3); })],
      front: [[...arcP(176, 364, 0), [0.92, 0.05, 1], [0.86, -0.42], [0.45, -0.6], [0, -0.64], [-0.45, -0.6], [-0.86, -0.42], [-0.92, 0.05, 1]], blob(-0.6, -0.55, 0.14), blob(-0.2, -0.63, 0.14), blob(0.2, -0.63, 0.14), blob(0.6, -0.55, 0.14)],
      backStrands: [[[-0.9, -1.2], [-0.8, -1.32], [-0.68, -1.22]], [[0.5, -1.4], [0.62, -1.5], [0.74, -1.38]], [[1.2, -0.6], [1.3, -0.5], [1.22, -0.38]], [[-1.3, -0.4], [-1.38, -0.28], [-1.28, -0.16]]], shine: 0.7 };
    case "bob": return {
      back: [bobBack], backStrands: [[[-1.05, 0.0], [-1.1, 0.55]], [[1.05, 0.0], [1.1, 0.55]]],
      front: [[...arcP(176, 364, 0.08), [1.04, 0.5, 1], [0.9, 0.46], [0.86, -0.2], [0.62, -0.36], [0.42, -0.3, 1], [0.21, -0.37], [0, -0.3, 1], [-0.21, -0.37], [-0.42, -0.3, 1], [-0.62, -0.36], [-0.86, -0.2], [-0.9, 0.46], [-1.04, 0.5, 1]]],
      strands: [[[0.3, -0.98], [0.25, -0.42]], [[-0.3, -0.98], [-0.25, -0.42]], [[0.95, -0.2], [0.97, 0.42]], [[-0.95, -0.2], [-0.97, 0.42]]], shine: 1.2 };
    case "ponytail": return {
      back: [ponyBack], backStrands: ponyStr,
      front: [[...arcP(184, 356, 0.06), [0.95, -0.1, 1], [0.86, -0.32], [0.5, -0.55], [0.0, -0.6], [-0.4, -0.52], [-0.75, -0.36], [-0.95, -0.1, 1]], [[-0.3, -0.62], [-0.12, -0.44], [0.02, -0.26, 1], [-0.05, -0.5], [-0.18, -0.66]]],
      strands: [[[-0.5, -0.55], [-0.2, -0.95], [0.5, -0.9]], [[0.2, -0.58], [0.5, -0.82], [0.85, -0.72]]], shine: 1.2, extra: tie(0.98, -0.66) };
    case "bun": return {
      front: [[...arcP(184, 356, 0.04), [0.95, -0.1, 1], [0.86, -0.32], [0.5, -0.55], [0.08, -0.6], [0, -0.5, 1], [-0.08, -0.6], [-0.5, -0.55], [-0.86, -0.32], [-0.95, -0.1, 1]], blob(0, -1.2, 0.33, 10)],
      strands: [[[-0.16, -1.22], [0, -1.38], [0.18, -1.22], [0.02, -1.1]], [[-0.5, -0.57], [-0.2, -0.98]], [[0.5, -0.57], [0.2, -0.98]]], shine: 1.2,
      extra: (g) => { begin(g); g.ellipse(CX, HY - 0.93 * R, 0.2 * R, 0.06 * R, 0, 0, Math.PI * 2); fillInk(g, "#d8262e", 6); } };
    case "mullet": return {
      back: [mulletBack], backStrands: [[[-1.05, 0.3], [-1.15, 0.9]], [[1.05, 0.3], [1.15, 0.9]]],
      front: [[...cap(0.07), [0.93, 0.15, 1], [0.88, -0.25], [0.66, -0.36, 1], [0.48, -0.55], [0.26, -0.38, 1], [0.05, -0.58], [-0.18, -0.38, 1], [-0.4, -0.58], [-0.62, -0.4, 1], [-0.86, -0.25], [-0.93, 0.15, 1]], lock(250, 1.24, 14, 9)],
      strands: [[[-0.3, -0.98], [-0.35, -0.65]], [[0.3, -0.98], [0.35, -0.65]]] };
    case "slick": return {
      front: [[...arcP(174, 366, 0.04), [0.92, 0.05, 1], [0.86, -0.35], [0.5, -0.55], [0.18, -0.6], [0, -0.42, 1], [-0.18, -0.6], [-0.5, -0.55], [-0.86, -0.35], [-0.92, 0.05, 1]]],
      strands: [[[-0.6, -0.55], [-0.56, -0.86], [-0.3, -1.0]], [[-0.25, -0.6], [-0.2, -0.9], [0.05, -1.03]], [[0.25, -0.6], [0.3, -0.9], [0.52, -0.96]], [[0.6, -0.52], [0.7, -0.76], [0.84, -0.76]]], shine: 1.6 };
    case "tuft": return {
      front: [[...arcP(176, 364, 0.03), [0.95, 0.05, 1], [0.9, -0.4], [0.5, -0.52], [0, -0.55], [-0.5, -0.52], [-0.9, -0.4], [-0.95, 0.05, 1]], lock(262, 1.22, -12, 8)],
      strands: [[-0.5, -0.75], [-0.2, -0.82], [0.15, -0.82], [0.5, -0.75]].map(([u, v]): HP[] => [[u, v], [u + 0.03, v - 0.07]]), shine: 0.8 };
    case "combover": return { front: fluff(), shine: 0, extra: (g, c) => { scalpShine(g); combStrands(g, c); } };
    case "bald": return { front: fluff(), shine: 0, extra: (g) => { scalpShine(g); begin(g); smoothOpen(g, [[0.04, -0.99], [0.0, -1.16], [0.14, -1.26], [0.22, -1.14], [0.1, -1.1]]); g.lineWidth = 6; g.strokeStyle = INK; g.stroke(); } };
    default: return { front: [] };
  }
};
const hairColOf = (s: Spec) => s.hairCol ?? (s.hair === "bald" || s.hair === "combover" ? "#cfc8ba" : "#2a1c18");
/** behind the head: bob, ponytail, mullet, afro */
const hairBack = (g: Ctx, s: Spec) => { const L = hairLook(s); if (L.back) paintHair(g, L.back, hairColOf(s), L.backStrands, 0); };
const hairZone = (g: Ctx, s: Spec) => {
  // a rounded hairline: everything inside the head ring except an oval face window, so the crown hair curves down
  // into the side patches at the temples (a straight cut left a flat edge across the forehead)
  const top = s.hat && s.hat !== "none" ? brimY(s) + 0.04 * R : HY - 0.48 * R, cy = HY + 0.2 * R;
  begin(g); g.ellipse(CX, HY, R * 1.02, R, 0, 0, Math.PI * 2); g.clip();
  begin(g); g.rect(CX - 2 * R, HY - 2 * R, 4 * R, 4 * R); g.ellipse(CX, cy, 0.74 * R, cy - top, 0, 0, Math.PI * 2); g.clip("evenodd");
};
const hair = (g: Ctx, s: Spec) => { if (s.hat === "helmet") return; g.save(); hairZone(g, s); hairIn(g, s); g.restore(); };
const hairIn = (g: Ctx, s: Spec) => {
  const L = hairLook(s), c = hairColOf(s);
  if (L.front.length) withClip(g, () => headPath(g), () => {
    for (const [dy, al] of [[0.24, 0.06], [0.19, 0.07], [0.14, 0.08], [0.1, 0.09], [0.07, 0.1]] as [number, number][]) {
      g.save(); g.translate(0.02 * R, dy * R); begin(g); for (const sh of L.front) smoothClosed(g, orient(sh)); g.fillStyle = `rgba(44,32,52,${al})`; g.fill(); g.restore();
    }
  });
  paintHair(g, L.front, c, L.strands, L.shine ?? 1);
  L.extra?.(g, c);
};
const hat = (g: Ctx, s: Spec) => {
  const c = s.hatCol ?? "#d8262e", dark = shade(c, 0.75);
  if (!s.hat || s.hat === "none") return;
  const dome = (y0: number, extra = 1.0) => { begin(g); g.moveTo(CX - 1.05 * R, y0); g.bezierCurveTo(CX - 1.05 * R, HY - 1.38 * R * extra, CX + 1.05 * R, HY - 1.38 * R * extra, CX + 1.05 * R, y0); g.closePath(); };
  if (s.hat === "capBack" || s.hat === "cap") {
    const y0 = HY - 0.46 * R;
    dome(y0); fillInk(g, c, W_INK);
    withClip(g, () => dome(y0), () => { for (const a of [-0.55, 0, 0.55]) line(g, [[CX + a * 1.4 * R, y0 + 20], [CX + a * 0.3 * R, HY - 1.05 * R]], 5, dark); });
    circle(g, CX, HY - 1.05 * R, 0.08 * R); fillInk(g, c, 7);
    if (s.hat === "capBack") { begin(g); g.ellipse(CX, y0 - 0.02 * R, 0.24 * R, 0.13 * R, 0, Math.PI, 0); g.closePath(); fillInk(g, "#5a3418", 7); line(g, [[CX - 0.24 * R, y0 - 0.02 * R], [CX + 0.24 * R, y0 - 0.02 * R]], 8, dark); }
    else { begin(g); g.moveTo(CX - 1.08 * R, y0); g.quadraticCurveTo(CX, y0 + 0.38 * R, CX + 1.12 * R, y0 - 0.06 * R); g.quadraticCurveTo(CX, y0 + 0.12 * R, CX - 1.08 * R, y0); g.closePath(); fillInk(g, dark, 8); }
  } else if (s.hat === "flatcap") {
    const y0 = HY - 0.56 * R;
    begin(g); g.moveTo(CX - 1.04 * R, y0 + 0.04 * R); g.bezierCurveTo(CX - 1.02 * R, HY - 1.12 * R, CX + 0.9 * R, HY - 1.18 * R, CX + 1.06 * R, y0 - 0.06 * R);
    g.quadraticCurveTo(CX, y0 + 0.02 * R, CX - 1.04 * R, y0 + 0.04 * R); g.closePath(); fillInk(g, c, W_INK);
    withClip(g, () => { begin(g); g.moveTo(CX - 1.04 * R, y0 + 0.04 * R); g.bezierCurveTo(CX - 1.02 * R, HY - 1.12 * R, CX + 0.9 * R, HY - 1.18 * R, CX + 1.06 * R, y0 - 0.06 * R); g.quadraticCurveTo(CX, y0 + 0.02 * R, CX - 1.04 * R, y0 + 0.04 * R); g.closePath(); }, () => {
      line(g, [[CX - 0.9 * R, y0 - 0.3 * R], [CX + 0.95 * R, y0 - 0.42 * R]], 5, SEAM, [14, 10]);
      line(g, [[CX - 0.2 * R, HY - 1.0 * R], [CX - 0.05 * R, y0 - 0.02 * R]], 5, dark); });
    begin(g); g.moveTo(CX - 0.98 * R, y0 + 0.02 * R); g.quadraticCurveTo(CX - 0.1 * R, y0 + 0.26 * R, CX + 0.92 * R, y0 - 0.02 * R); g.quadraticCurveTo(CX - 0.05 * R, y0 + 0.06 * R, CX - 0.98 * R, y0 + 0.02 * R); g.closePath(); fillInk(g, dark, 8);
  } else if (s.hat === "hardhat") {
    dome(HY - 0.48 * R, 1.06); fillInk(g, c, W_INK);
    line(g, [[CX, HY - 1.15 * R], [CX, HY - 0.53 * R]], 16, shade(c, 1.15));
    begin(g); g.ellipse(CX, HY - 0.48 * R, 1.25 * R, 0.1 * R, 0, 0, Math.PI * 2); fillInk(g, dark, 8);
  } else if (s.hat === "beanie") {
    dome(HY - 0.52 * R); fillInk(g, c, W_INK);
    begin(g); g.rect(CX - 1.0 * R, HY - 0.7 * R, 2.0 * R, 0.22 * R); fillInk(g, dark, 8);
    for (let k = -4; k <= 4; k++) line(g, [[CX + k * 0.21 * R, HY - 0.68 * R], [CX + k * 0.21 * R, HY - 0.5 * R]], 4, SEAM);
  } else if (s.hat === "pilot") {
    // airline captain's cap: a wide flat crown, dark band with gold braid, glossy black peak, gold wings badge
    const y0 = HY - 0.5 * R, trim = s.hatTrim ?? "#d9a640";
    begin(g); g.ellipse(CX, y0 - 0.34 * R, 1.12 * R, 0.24 * R, 0, 0, Math.PI * 2); fillInk(g, c, W_INK);
    begin(g); g.moveTo(CX - 0.98 * R, y0 - 0.34 * R); g.lineTo(CX - 0.92 * R, y0); g.lineTo(CX + 0.92 * R, y0); g.lineTo(CX + 0.98 * R, y0 - 0.34 * R); g.closePath(); fillInk(g, "#1d2236", W_INK);
    line(g, [[CX - 0.92 * R, y0 - 0.06 * R], [CX + 0.92 * R, y0 - 0.06 * R]], 0.045 * R, trim);
    begin(g); g.moveTo(CX - 0.95 * R, y0); g.quadraticCurveTo(CX, y0 + 0.32 * R, CX + 0.95 * R, y0); g.quadraticCurveTo(CX, y0 + 0.1 * R, CX - 0.95 * R, y0); g.closePath(); fillInk(g, "#121216", 8);
    line(g, [[CX - 0.6 * R, y0 + 0.1 * R], [CX + 0.6 * R, y0 + 0.1 * R]], 0.03 * R, trim);
    begin(g); g.ellipse(CX, y0 - 0.2 * R, 0.12 * R, 0.1 * R, 0, 0, Math.PI * 2); fillInk(g, trim, 6);
    for (const sd of [-1, 1]) { begin(g); g.moveTo(CX + sd * 0.1 * R, y0 - 0.22 * R); g.quadraticCurveTo(CX + sd * 0.32 * R, y0 - 0.32 * R, CX + sd * 0.42 * R, y0 - 0.26 * R); g.quadraticCurveTo(CX + sd * 0.28 * R, y0 - 0.18 * R, CX + sd * 0.1 * R, y0 - 0.16 * R); g.closePath(); fillInk(g, trim, 4); }
  } else if (s.hat === "helmet") {
    // open-face racing helmet: a glossy shell round the head down to the jaw, a face opening, a stripe, the visor up
    const trim = s.hatTrim ?? "#d8262e";
    const shell = () => { begin(g); g.moveTo(CX - 1.12 * R, HY + 0.55 * R); g.bezierCurveTo(CX - 1.25 * R, HY - 0.5 * R, CX - 0.9 * R, HY - 1.3 * R, CX, HY - 1.3 * R);
      g.bezierCurveTo(CX + 0.9 * R, HY - 1.3 * R, CX + 1.25 * R, HY - 0.5 * R, CX + 1.12 * R, HY + 0.55 * R);
      g.lineTo(CX + 0.72 * R, HY + 0.55 * R); g.bezierCurveTo(CX + 0.8 * R, HY - 0.2 * R, CX + 0.55 * R, HY - 0.62 * R, CX, HY - 0.62 * R);
      g.bezierCurveTo(CX - 0.55 * R, HY - 0.62 * R, CX - 0.8 * R, HY - 0.2 * R, CX - 0.72 * R, HY + 0.55 * R); g.closePath(); };
    shell(); fillInk(g, c, W_INK);
    withClip(g, shell, () => { begin(g); g.rect(CX - 0.16 * R, HY - 1.5 * R, 0.32 * R, 1.0 * R); g.fillStyle = trim; g.fill();
      const gr = g.createRadialGradient(CX - 0.4 * R, HY - 0.9 * R, 0.05 * R, CX, HY - 0.3 * R, 1.4 * R); gr.addColorStop(0, "rgba(255,255,255,0.55)"); gr.addColorStop(0.4, "rgba(255,255,255,0)"); gr.addColorStop(1, "rgba(20,16,30,0.3)");
      g.fillStyle = gr; g.fillRect(CX - 1.5 * R, HY - 1.5 * R, 3 * R, 2.2 * R); });
    begin(g); g.moveTo(CX - 0.82 * R, HY - 0.62 * R); g.quadraticCurveTo(CX, HY - 0.95 * R, CX + 0.82 * R, HY - 0.62 * R); g.lineWidth = 0.1 * R; g.strokeStyle = "rgba(60,70,90,0.85)"; g.stroke();
  } else if (s.hat === "bowler") {
    begin(g); g.ellipse(CX, HY - 0.62 * R, 0.8 * R, 0.55 * R, 0, Math.PI, 0); g.closePath(); fillInk(g, c, W_INK);
    line(g, [[CX - 0.8 * R, HY - 0.7 * R], [CX + 0.8 * R, HY - 0.7 * R]], 14, shade(c, 1.35));
    begin(g); g.ellipse(CX, HY - 0.6 * R, 1.12 * R, 0.12 * R, 0, 0, Math.PI * 2); fillInk(g, c, 8);
  }
};
/** painted 3D look on a hat: stripes, a soft key-light gradient and a specular glint, clipped to the crown */
const hatPaint = (g: Ctx, s: Spec) => {
  if (!s.hat || s.hat === "none" || s.hat === "flatcap") return;
  const crown = () => { if (s.hat === "bowler") { begin(g); g.ellipse(CX, HY - 0.62 * R, 0.8 * R, 0.55 * R, 0, Math.PI, 0); g.closePath(); } else { begin(g); g.moveTo(CX - 1.05 * R, HY - 0.47 * R); g.bezierCurveTo(CX - 1.05 * R, HY - 1.4 * R, CX + 1.05 * R, HY - 1.4 * R, CX + 1.05 * R, HY - 0.47 * R); g.closePath(); } };
  withClip(g, crown, () => {
    if (s.hatPattern === "stripes") for (let k = -6; k <= 6; k++) { begin(g); g.moveTo(CX + k * 0.17 * R, HY - 0.43 * R); g.quadraticCurveTo(CX + k * 0.13 * R, HY - 0.8 * R, CX + k * 0.05 * R, HY - 1.3 * R); g.lineWidth = 0.06 * R; g.strokeStyle = "rgba(255,255,255,0.85)"; g.stroke(); }
    const gr = g.createRadialGradient(CX - 0.3 * R, HY - 1.0 * R, 0.05 * R, CX, HY - 0.6 * R, 1.1 * R);
    gr.addColorStop(0, "rgba(255,255,255,0.35)"); gr.addColorStop(0.35, "rgba(255,255,255,0.05)"); gr.addColorStop(0.75, "rgba(20,16,30,0.12)"); gr.addColorStop(1, "rgba(20,16,30,0.35)");
    g.fillStyle = gr; g.fillRect(CX - 1.5 * R, HY - 1.6 * R, 3 * R, 1.6 * R);
    if (s.hatGloss) { begin(g); g.ellipse(CX - 0.32 * R, HY - 0.98 * R, 0.22 * R, 0.08 * R, -0.5, 0, Math.PI * 2); g.fillStyle = "rgba(255,255,255,0.7)"; g.fill(); }
  });
};
/** a tapered calligraphic stroke (brows, lids, mouths): thick in the middle, pointed ends */
const taper = (g: Ctx, x0: number, y0: number, x1: number, y1: number, w: number, bend = 0) => {
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2 - bend, nx = -(y1 - y0), ny = x1 - x0, L = Math.hypot(nx, ny) || 1, ux = (nx / L) * w / 2, uy = (ny / L) * w / 2;
  begin(g); g.moveTo(x0, y0); g.quadraticCurveTo(mx + ux, my + uy, x1, y1); g.quadraticCurveTo(mx - ux, my - uy, x0, y0); g.closePath(); g.fillStyle = INK; g.fill();
};
/** reference-style mustache: a thin wavy ink stroke with curled ends (light hair: coloured core inside an ink edge) */
const curlyMustache = (g: Ctx, x: number, y: number, col: string) => {
  const path = () => { begin(g); g.moveTo(x - 0.25 * R, y - 0.02 * R); g.bezierCurveTo(x - 0.27 * R, y + 0.06 * R, x - 0.16 * R, y + 0.07 * R, x - 0.1 * R, y + 0.02 * R);
    g.quadraticCurveTo(x - 0.04 * R, y - 0.05 * R, x, y); g.quadraticCurveTo(x + 0.04 * R, y - 0.05 * R, x + 0.1 * R, y + 0.02 * R);
    g.bezierCurveTo(x + 0.16 * R, y + 0.07 * R, x + 0.27 * R, y + 0.06 * R, x + 0.25 * R, y - 0.02 * R); };
  const lum = parseInt(col.slice(1, 3), 16) * 0.3 + parseInt(col.slice(3, 5), 16) * 0.59 + parseInt(col.slice(5, 7), 16) * 0.11;
  g.lineCap = "round"; g.lineJoin = "round";
  if (lum < 90) { path(); g.lineWidth = 0.06 * R; g.strokeStyle = INK; g.stroke(); return; }
  path(); g.lineWidth = 0.075 * R; g.strokeStyle = INK; g.stroke(); path(); g.lineWidth = 0.035 * R; g.strokeStyle = col; g.stroke();
};
/** the reference grin: a wide D-shaped mouth full of white teeth with ink dividers */
const toothyGrin = (g: Ctx, x: number, y: number, w: number, h: number) => {
  const path = () => { begin(g); g.moveTo(x - w, y - 0.03 * R); g.quadraticCurveTo(x, y + 0.02 * R, x + w, y - 0.03 * R); g.bezierCurveTo(x + w * 0.85, y + h, x - w * 0.85, y + h, x - w, y - 0.03 * R); g.closePath(); };
  path(); g.fillStyle = "#ffffff"; g.fill();
  withClip(g, path, () => { for (let k = -2; k <= 2; k++) line(g, [[x + k * w * 0.36, y - 0.05 * R], [x + k * w * 0.34, y + h]], 0.03 * R); });
  path(); inkStroke(g, 0.045 * R);
};
const face = (g: Ctx, s: Spec, p: Pose) => { if ((s.eyes ?? "almond") === "almond" && !["shock", "grimace"].includes(p.expr ?? "neutral") && !s.glasses) return faceAlmond(g, s, p); return faceRing(g, s, p); };
/** v2 default face (reference close-ups): small black almond eyes under heavy lid lines, thick tapered brows, a small
 *  tapered mouth; the whole face slides with the head turn (yaw) */
const faceAlmond = (g: Ctx, s: Spec, p: Pose) => {
  const e = p.expr ?? "neutral", yaw = p.yaw ?? 0, blink = p.blink ?? 0, col = s.head ?? "#fbfaf7", [lx, ly] = p.look ?? [0, 0];
  const fx = CX + yaw * 0.34 * R, ey = HY + 0.04 * R, sp = 0.27 * R * (1 - 0.15 * Math.abs(yaw));
  for (const sd of [-1, 1]) {
    const far = yaw !== 0 && Math.sign(yaw) !== sd, x = fx + sd * sp * (far ? 0.85 : 1), sq = far ? 0.8 : 1;
    if (e === "smile" || blink >= 0.9) { begin(g); g.arc(x, ey + (e === "smile" ? 0.07 : 0.02) * R, 0.11 * R * sq, Math.PI * (e === "smile" ? 1.12 : 0.1), Math.PI * (e === "smile" ? 1.88 : 0.9), e !== "smile"); g.lineWidth = 0.055 * R; g.strokeStyle = INK; g.lineCap = "round"; g.stroke(); }
    else {
      begin(g); g.ellipse(x + lx * 0.02 * R, ey + ly * 0.02 * R + 0.02 * R, 0.105 * R * sq, 0.135 * R, 0, 0, Math.PI * 2); g.fillStyle = INK; g.fill();
      const lid = e === "deadpan" || e === "smirk" ? 0.55 : e === "angry" ? 0.42 : e === "worried" ? 0.1 : 0.2;
      const yl = ey - 0.1 * R + lid * 0.24 * R, tl = e === "angry" ? -sd * 0.05 * R : e === "worried" ? sd * 0.05 * R : 0;
      g.save(); begin(g); g.ellipse(x + lx * 0.02 * R, ey + ly * 0.02 * R + 0.02 * R, 0.105 * R * sq + 2, 0.135 * R + 2, 0, 0, Math.PI * 2); g.clip(); begin(g); g.rect(x - 0.2 * R, ey - 0.25 * R, 0.4 * R, yl - (ey - 0.25 * R)); g.fillStyle = col; g.fill(); g.restore();
      taper(g, x - 0.2 * R * sq, yl - tl, x + 0.2 * R * sq, yl + tl, 0.085 * R, 0.012 * R);
    }
    const by = ey - (e === "angry" ? 0.25 : 0.3) * R, bt = e === "angry" ? -sd * 0.08 * R : e === "worried" ? sd * 0.08 * R : e === "smirk" && sd > 0 ? -0.06 * R : 0;
    taper(g, x - sd * 0.13 * R * sq, by + bt, x + sd * 0.15 * R * sq, by - bt * 0.4 - 0.02 * R, 0.085 * R, 0.03 * R);
  }
  const my = HY + (s.mustache ? 0.47 : 0.42) * R, mx = fx + yaw * 0.06 * R;
  if (s.mustache) curlyMustache(g, mx, HY + 0.33 * R, s.mustache);
  if (e === "talk" || e === "shock") { begin(g); g.ellipse(mx, my + 0.06 * R, 0.085 * R, 0.1 * R, 0, 0, Math.PI * 2); fillInk(g, "#3a1418", 6); }
  else if (e === "smile") toothyGrin(g, mx, my + 0.02 * R, 0.22 * R, 0.17 * R);
  else if (e === "angry") taper(g, mx - 0.1 * R, my + 0.08 * R, mx + 0.1 * R, my + 0.08 * R, 0.045 * R, 0.04 * R);
  else if (e === "worried") { begin(g); g.moveTo(mx - 0.12 * R, my + 0.07 * R); g.bezierCurveTo(mx - 0.04 * R, my + 0.02 * R, mx + 0.04 * R, my + 0.11 * R, mx + 0.12 * R, my + 0.05 * R); inkStroke(g, 7); }
  else if (e === "smirk") taper(g, mx - 0.1 * R, my + 0.07 * R, mx + 0.12 * R, my + 0.02 * R, 0.04 * R, -0.02 * R);
  else taper(g, mx - 0.07 * R, my + 0.06 * R, mx + 0.08 * R, my + 0.06 * R, 0.04 * R, -0.01 * R);
  if (p.sweat) { begin(g); g.moveTo(CX - 0.86 * R, HY - 0.52 * R); g.quadraticCurveTo(CX - 0.74 * R, HY - 0.3 * R, CX - 0.86 * R, HY - 0.22 * R); g.quadraticCurveTo(CX - 0.98 * R, HY - 0.3 * R, CX - 0.86 * R, HY - 0.52 * R); fillInk(g, "#9fd4ff", 6); }
};
const faceRing = (g: Ctx, s: Spec, p: Pose) => {
  const e = p.expr ?? "neutral", [lx, ly] = p.look ?? [0, 0], blink = p.blink ?? 0, col = s.head ?? "#fbfaf7";
  const ey = HY + 0.02 * R, er = 0.22 * R, ex = s.glasses ? 0.33 * R : 0.27 * R;
  const shock = e === "shock" || e === "grimace";
  for (const sd of [-1, 1]) {
    const x = CX + sd * ex;
    circle(g, x, ey, er); fillInk(g, "#ffffff", 0.055 * R);
    const pr = shock ? 0.06 * R : 0.075 * R;
    if (blink < 0.9) { circle(g, x + lx * 0.07 * R, ey + ly * 0.07 * R, pr); g.fillStyle = INK; g.fill(); }
    // lids: deadpan / angry / worried cover the top of the eye in head colour; blink closes it
    const lid = blink >= 0.9 ? 1 : e === "deadpan" ? 0.45 : e === "angry" ? 0.35 : e === "worried" ? 0.2 : blink;
    if (lid > 0.02) {
      const yl = ey - er + 2 * er * lid, tiltK = e === "angry" ? -sd * 0.12 * R : e === "worried" ? sd * 0.1 * R : 0;
      g.save(); circle(g, x, ey, er - 4); g.clip();
      begin(g); g.moveTo(x - er - 10, ey - er - 10); g.lineTo(x + er + 10, ey - er - 10); g.lineTo(x + er + 10, yl - tiltK * sd); g.lineTo(x - er - 10, yl + tiltK * sd); g.closePath(); g.fillStyle = col; g.fill(); g.restore();
      line(g, [[x - er, yl + tiltK * sd], [x + er, yl - tiltK * sd]], 8);
    }
    if (s.glasses) { circle(g, x, ey, er * 1.12); inkStroke(g, 7); }
    if (e === "angry" || e === "worried") { const k = e === "angry" ? 1 : -1; line(g, [[x - sd * 0.18 * R, ey - er - 0.08 * R + k * 0.06 * R], [x + sd * 0.16 * R, ey - er - 0.08 * R - k * 0.06 * R]], 11); }
  }
  if (s.glasses) line(g, [[CX - ex + er * 1.12, ey], [CX + ex - er * 1.12, ey]], 7);
  const my = HY + (s.mustache ? 0.5 : 0.44) * R;
  if (s.mustache) curlyMustache(g, CX, HY + 0.34 * R, s.mustache);
  if (e === "shock") { begin(g); g.ellipse(CX, my + 0.06 * R, 0.1 * R, 0.13 * R, 0, 0, Math.PI * 2); fillInk(g, "#3a1418", 7); }
  else if (e === "grimace") { begin(g); g.roundRect(CX - 0.17 * R, my - 0.03 * R, 0.34 * R, 0.2 * R, 0.07 * R); fillInk(g, "#ffffff", 0.04 * R); for (const k of [-1, 0, 1]) line(g, [[CX + k * 0.085 * R, my - 0.03 * R], [CX + k * 0.085 * R, my + 0.17 * R]], 0.025 * R); line(g, [[CX - 0.17 * R, my + 0.07 * R], [CX + 0.17 * R, my + 0.07 * R]], 0.025 * R); }
  else if (e === "smile") { begin(g); g.arc(CX, my - 0.08 * R, 0.16 * R, 0.15 * Math.PI, 0.85 * Math.PI); inkStroke(g, 8); }
  else if (e === "smirk") { begin(g); g.moveTo(CX - 0.14 * R, my + 0.02 * R); g.quadraticCurveTo(CX + 0.05 * R, my + 0.07 * R, CX + 0.17 * R, my - 0.06 * R); inkStroke(g, 8); }
  else if (e === "worried") { begin(g); g.moveTo(CX - 0.16 * R, my + 0.04 * R); g.bezierCurveTo(CX - 0.06 * R, my - 0.04 * R, CX + 0.04 * R, my + 0.1 * R, CX + 0.16 * R, my + 0.02 * R); inkStroke(g, 8); }
  else if (e === "talk") { begin(g); g.ellipse(CX + 0.02 * R, my + 0.03 * R, 0.08 * R, 0.06 * R, 0, 0, Math.PI * 2); fillInk(g, "#3a1418", 6); }
  else { begin(g); g.moveTo(CX - 0.1 * R, my + 0.02 * R); g.quadraticCurveTo(CX + 0.02 * R, my - 0.01 * R, CX + 0.14 * R, my + 0.04 * R); inkStroke(g, 8); }
  if (p.sweat) { begin(g); g.moveTo(CX + 0.86 * R, HY - 0.62 * R); g.quadraticCurveTo(CX + 0.98 * R, HY - 0.4 * R, CX + 0.86 * R, HY - 0.32 * R); g.quadraticCurveTo(CX + 0.74 * R, HY - 0.4 * R, CX + 0.86 * R, HY - 0.62 * R); fillInk(g, "#9fd4ff", 6); }
};

// ---------------------------------------------------------------- limbs (v5, measured on reference bodies)
const LIMB_W = 0.22 * R;
/** a thick noodle limb: ink outline + dark fill along a smooth curve through the points */
const noodle = (g: Ctx, pts: [number, number][], w: number, col: string) => {
  const path = () => {
    begin(g); g.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length - 1; i++) { const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2; g.quadraticCurveTo(pts[i][0], pts[i][1], i === pts.length - 2 ? pts[i + 1][0] : mx, i === pts.length - 2 ? pts[i + 1][1] : my); }
    if (pts.length === 2) g.lineTo(pts[1][0], pts[1][1]);
  };
  g.lineCap = "round"; g.lineJoin = "round";
  path(); g.lineWidth = w + 10; g.strokeStyle = INK; g.stroke();
  path(); g.lineWidth = w; g.strokeStyle = col; g.stroke();
};
const mitten = (g: Ctx, x: number, y: number, sd: number) => {
  begin(g); g.ellipse(x, y, 0.13 * R, 0.12 * R, 0, 0, Math.PI * 2); fillInk(g, "#f7f6f2", 8);
  begin(g); g.ellipse(x - sd * 0.1 * R, y - 0.05 * R, 0.05 * R, 0.07 * R, sd * 0.6, 0, Math.PI * 2); fillInk(g, "#f7f6f2", 7);
};
/** arm angle a (degrees out from hanging straight down): under 40 the arm hangs behind the body's edge, above it the arm is in front */
const armPts = (sd: number, a: number, bend = 0, reach?: [number, number]): [number, number][] => {
  const sx = CX + sd * (BLD.sh - 0.13) * R, sy = BODY_T + 0.32 * R, L1 = 1.15 * R, L2 = 1.12 * R;
  if (reach) {   // two-bone IK: the hand on the target, the elbow bent outward and down
    const dx = reach[0] - sx, dy = reach[1] - sy, d = Math.min(Math.hypot(dx, dy), L1 + L2 - 2), base = Math.atan2(dy, dx);
    const k = Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))), side = sd * (reach[1] < sy - 0.3 * R ? -1 : 1);
    const ex = sx + Math.cos(base + side * k) * L1, ey = sy + Math.sin(base + side * k) * L1;
    return [[sx, sy], [ex, ey], [sx + Math.cos(base) * d, sy + Math.sin(base) * d]];
  }
  const r1 = ((a * 0.75 + 12) * Math.PI) / 180, r2 = ((a - 2 + bend) * Math.PI) / 180;
  const ex = sx + sd * Math.sin(r1) * L1, ey = sy + Math.cos(r1) * L1, hx = ex + sd * Math.sin(r2) * L2, hy = ey + Math.cos(r2) * L2;
  return [[sx, sy], [ex, ey], [hx, hy]];
};
const drawArm = (g: Ctx, s: Spec, sd: number, a: number, bend = 0, reach?: [number, number], hold?: Held, spray = false) => {
  const pts = armPts(sd, a, bend, reach), c = s.limb ?? "#2a1a14";
  noodle(g, pts, LIMB_W, c);
  const [hx, hy] = pts[2];
  if (s.sleeves !== false && s.outfit !== "dress") {
    const long = ["jacket", "coat", "suit", "hoodie"].includes(s.outfit), col = long ? s.base : (s.shirt ?? "#f4f1ea");
    const lerp = (u: number): [number, number] => { const [a0, a1, a2] = pts; return u < 0.5 ? [a0[0] + (a1[0] - a0[0]) * u * 2, a0[1] + (a1[1] - a0[1]) * u * 2] : [a1[0] + (a2[0] - a1[0]) * (u - 0.5) * 2, a1[1] + (a2[1] - a1[1]) * (u - 0.5) * 2]; };
    const end = long ? 0.82 : 0.3, sl: [number, number][] = long ? [pts[0], pts[1], lerp(end)] : [pts[0], lerp(end)];
    noodle(g, sl, LIMB_W * 1.28, col);
    g.save(); g.lineCap = "round"; begin(g); const [x0, y0] = sl[0], [x1, y1] = sl[sl.length - 1]; g.moveTo(x0 - sd * 0.08 * R, y0); g.lineTo(x1 - sd * 0.08 * R, y1); g.lineWidth = LIMB_W * 0.35; g.strokeStyle = "rgba(255,255,255,0.18)"; g.stroke(); g.restore();
    const [cx2, cy2] = lerp(end), [px, py] = lerp(end - 0.05), ang = Math.atan2(cy2 - py, cx2 - px);
    g.save(); g.translate(cx2, cy2); g.rotate(ang); begin(g); g.roundRect(-0.07 * R, -LIMB_W * 0.7, 0.14 * R, LIMB_W * 1.4, 10); fillInk(g, shade(col, 0.72), 7);
    if (s.cuffs && long) for (const o of [-0.16, -0.26]) { begin(g); g.rect(o * R - 0.03 * R, -LIMB_W * 0.66, 0.05 * R, LIMB_W * 1.32); g.fillStyle = s.cuffs; g.fill(); }
    g.restore();
  }
  if (hold) heldProp(g, hold, hx, hy, sd, spray);
  if (s.mittens !== false) mitten(g, hx, hy, sd); else { circle(g, hx, hy, LIMB_W * 0.62); g.fillStyle = c; g.fill(); }
};
/** v18: 2D props held in a hand (drawn under the mitten so the fingers close over them) */
const heldProp = (g: Ctx, kind: Held, x: number, y: number, sd: number, spray: boolean) => {
  g.save(); g.lineJoin = "round"; g.lineCap = "round";
  if (kind === "dipstick") {   // a comically long metal drip stick with red depth marks
    begin(g); g.roundRect(x - 0.035 * R, y - 2.9 * R, 0.07 * R, 4.3 * R, 0.03 * R); fillInk(g, "#d9dde4", 7);
    for (let k = 0; k < 14; k++) line(g, [[x - 0.035 * R, y + 1.25 * R - k * 0.3 * R], [x + (k % 2 ? 0.02 : 0.035) * R, y + 1.25 * R - k * 0.3 * R]], 6, "#d8262e");
    begin(g); g.ellipse(x, y - 2.95 * R, 0.09 * R, 0.06 * R, 0, 0, Math.PI * 2); fillInk(g, "#e8c640", 6);
  } else if (kind === "clipboard") {   // board, clip, paper with the fatal factor written big
    g.translate(x - sd * 0.32 * R, y - 0.2 * R); g.rotate(-sd * 0.12);
    begin(g); g.roundRect(-0.42 * R, -0.58 * R, 0.84 * R, 1.12 * R, 0.05 * R); fillInk(g, "#b8844c", 8);
    begin(g); g.rect(-0.34 * R, -0.44 * R, 0.68 * R, 0.9 * R); fillInk(g, "#fbfaf4", 5);
    begin(g); g.roundRect(-0.16 * R, -0.66 * R, 0.32 * R, 0.16 * R, 0.04 * R); fillInk(g, "#c8ccd4", 6);
    g.fillStyle = INK; g.font = `bold ${0.17 * R}px Arial`; g.textAlign = "center"; g.fillText("x 1.77", 0, -0.12 * R);
    for (let k = 0; k < 3; k++) line(g, [[-0.26 * R, 0.06 * R + k * 0.12 * R], [0.24 * R - (k % 2) * 0.12 * R, 0.06 * R + k * 0.12 * R]], 5, "#7a7f8a");
  } else if (kind === "extinguisher") {   // red cylinder held at the waist, black hose to the nozzle in front
    g.translate(x, y);
    begin(g); g.roundRect(-0.17 * R, -0.25 * R, 0.34 * R, 0.95 * R, 0.14 * R); fillInk(g, "#d8262e", 8);
    begin(g); g.rect(-0.17 * R, 0.05 * R, 0.34 * R, 0.24 * R); g.fillStyle = "#f4f2ec"; g.fill(); begin(g); g.rect(-0.17 * R, 0.05 * R, 0.34 * R, 0.24 * R); inkStroke(g, 5);
    begin(g); g.roundRect(-0.07 * R, -0.42 * R, 0.14 * R, 0.18 * R, 0.03 * R); fillInk(g, "#2a2a30", 6);
    begin(g); g.moveTo(0.04 * R, -0.36 * R); g.quadraticCurveTo(-sd * 0.5 * R, -0.75 * R, -sd * 0.42 * R, -0.12 * R); g.lineWidth = 0.07 * R; g.strokeStyle = INK; g.stroke();
    if (spray) { const gr = g.createRadialGradient(-sd * 0.9 * R, -0.3 * R, 0, -sd * 0.9 * R, -0.3 * R, 0.7 * R); gr.addColorStop(0, "rgba(255,255,255,0.95)"); gr.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = gr; begin(g); g.ellipse(-sd * 0.9 * R, -0.3 * R, 0.7 * R, 0.45 * R, 0, 0, Math.PI * 2); g.fill(); }
  } else if (kind === "flashlight") {
    g.translate(x, y); g.rotate(-sd * 0.5);
    begin(g); g.roundRect(-0.06 * R, -0.45 * R, 0.12 * R, 0.5 * R, 0.04 * R); fillInk(g, "#2f3440", 6);
    begin(g); g.roundRect(-0.09 * R, -0.58 * R, 0.18 * R, 0.15 * R, 0.04 * R); fillInk(g, "#c8ccd4", 6);
    begin(g); g.ellipse(0, -0.6 * R, 0.07 * R, 0.03 * R, 0, 0, Math.PI * 2); g.fillStyle = "#fff6c8"; g.fill();
  } else if (kind === "map") {   // an unfolded chart with the lake and the old base marked
    g.translate(x - sd * 0.5 * R, y - 0.25 * R); g.rotate(-sd * 0.08);
    begin(g); g.rect(-0.6 * R, -0.42 * R, 1.2 * R, 0.84 * R); fillInk(g, "#f2ead2", 7);
    for (const fx of [-0.2, 0.2]) line(g, [[fx * R, -0.42 * R], [fx * R, 0.42 * R]], 3, "rgba(0,0,0,0.18)");
    begin(g); g.ellipse(0.25 * R, -0.05 * R, 0.22 * R, 0.32 * R, 0.3, 0, Math.PI * 2); g.fillStyle = "#8cc4e8"; g.fill();
    begin(g); g.moveTo(-0.5 * R, 0.3 * R); g.quadraticCurveTo(-0.2 * R, -0.1 * R, 0.0, 0.25 * R); g.lineWidth = 5; g.strokeStyle = "#c8a050"; g.stroke();
    line(g, [[-0.12 * R, -0.12 * R], [0.0, 0.0]], 9, "#d8262e"); line(g, [[0.0, -0.12 * R], [-0.12 * R, 0.0]], 9, "#d8262e");
    g.fillStyle = INK; g.font = `bold ${0.13 * R}px Arial`; g.textAlign = "center"; g.fillText("GIMLI", -0.08 * R, 0.2 * R);
  } else if (kind === "jerrycan") {
    g.translate(x, y + 0.42 * R);
    begin(g); g.roundRect(-0.3 * R, -0.36 * R, 0.6 * R, 0.78 * R, 0.07 * R); fillInk(g, "#d8262e", 8);
    line(g, [[-0.22 * R, -0.25 * R], [0.22 * R, 0.3 * R]], 5, "rgba(0,0,0,0.25)"); line(g, [[0.22 * R, -0.25 * R], [-0.22 * R, 0.3 * R]], 5, "rgba(0,0,0,0.25)");
    begin(g); g.roundRect(-0.18 * R, -0.5 * R, 0.36 * R, 0.16 * R, 0.05 * R); fillInk(g, "#d8262e", 7);
  } else if (kind === "spatula") {
    g.translate(x, y); g.rotate(sd * 0.35);
    line(g, [[0, 0.1 * R], [0, -0.75 * R]], 0.07 * R, "#6a4428");
    begin(g); g.roundRect(-0.13 * R, -1.05 * R, 0.26 * R, 0.32 * R, 0.04 * R); fillInk(g, "#c8ccd4", 6);
  } else if (kind === "wrench") {
    g.translate(x, y); g.rotate(sd * 0.6);
    line(g, [[0, 0.15 * R], [0, -0.6 * R]], 0.09 * R, "#a8adb8");
    begin(g); g.arc(0, -0.7 * R, 0.13 * R, 0.5, Math.PI * 2 - 0.5); g.lineWidth = 0.08 * R; g.strokeStyle = "#a8adb8"; g.stroke();
  } else if (kind === "nozzle") {   // the fuel hose nozzle
    g.translate(x, y); g.rotate(-sd * 0.9);
    begin(g); g.roundRect(-0.07 * R, -0.5 * R, 0.14 * R, 0.55 * R, 0.04 * R); fillInk(g, "#2a2a30", 6);
    line(g, [[0, -0.5 * R], [0, -0.85 * R]], 0.06 * R, "#c8ccd4");
  }
  g.restore();
};
const armAngles = (p: Pose): [number, number] => [p.armL ?? 6, p.wave !== undefined ? 150 + 20 * p.wave : (p.armR ?? 6)];
/** v9 legs: a soft knee curve, tapering toward the ankle, socks between the cuff and the shoe */
const legPath = (g: Ctx, pts: [number, number][], w0: number, w1: number, col: string) => {
  // a tapered tube along a quadratic through hip, knee, ankle: offset both sides, fill, ink outline
  const [a, k, c] = pts, N = 16, L: [number, number][] = [], Rr: [number, number][] = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N, x = (1 - t) * (1 - t) * a[0] + 2 * t * (1 - t) * k[0] + t * t * c[0], y = (1 - t) * (1 - t) * a[1] + 2 * t * (1 - t) * k[1] + t * t * c[1];
    const dx = 2 * (1 - t) * (k[0] - a[0]) + 2 * t * (c[0] - k[0]), dy = 2 * (1 - t) * (k[1] - a[1]) + 2 * t * (c[1] - k[1]), l = Math.hypot(dx, dy) || 1, w = (w0 + (w1 - w0) * t) / 2;
    L.push([x - (dy / l) * w, y + (dx / l) * w]); Rr.push([x + (dy / l) * w, y - (dx / l) * w]);
  }
  begin(g); [...L, ...Rr.reverse()].forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath();
  g.fillStyle = col; g.fill(); inkStroke(g, 9);
};
/** a front-view cartoon shoe under ankle x: a round toe facing the lens, a sole band, the collar and tongue, turned
 *  out a little (sd = side); boots climb higher with laces, trainers get a white sole and a stripe, oxfords a toe cap and a shine */
const shoe = (g: Ctx, x: number, sd: number, kind: string, col: string) => {
  const hi = kind === "boots" ? 0.38 * R : kind === "trainers" ? 0.24 * R : 0.18 * R, sole = kind === "boots" ? 0.08 * R : kind === "trainers" ? 0.075 * R : 0.05 * R, w = 0.31 * R;
  g.save(); g.translate(x + sd * 0.04 * R, FEET); g.rotate(sd * 0.1);
  const upper = () => {
    begin(g); g.moveTo(-w * 0.62, -sole);
    g.lineTo(-w * 0.55, -hi); g.quadraticCurveTo(0, -hi - 0.03 * R, w * 0.55, -hi); g.lineTo(w * 0.62, -sole);   // collar across the ankle
    g.closePath();
  };
  const toe = () => { begin(g); g.ellipse(0, -sole - 0.07 * R, w, 0.14 * R, 0, 0, Math.PI * 2); };
  // sole
  begin(g); g.roundRect(-w * 1.06, -sole - 0.02 * R, w * 2.12, sole + 0.02 * R, 0.04 * R);
  fillInk(g, kind === "trainers" ? "#f4f2ec" : kind === "boots" ? "#2a1c14" : shade(col, 0.6), 8);
  if (kind === "boots") for (let k = -2; k <= 2; k++) line(g, [[k * 0.09 * R - 0.025 * R, -3], [k * 0.09 * R + 0.025 * R, -3]], 6, "#5a4030");
  // upper (shaft) then the round toe in front
  upper(); g.fillStyle = col; g.fill(); inkStroke(g, 8);
  toe(); g.fillStyle = col; g.fill();
  const lit = (path: () => void) => withClip(g, path, () => {
    const gr = g.createLinearGradient(-w * 1.1, 0, w * 1.1, 0); gr.addColorStop(0, "rgba(255,255,255,0.25)"); gr.addColorStop(0.45, "rgba(255,255,255,0)"); gr.addColorStop(1, "rgba(10,10,20,0.32)");
    g.fillStyle = gr; g.fillRect(-w * 1.2, -hi - 20, w * 2.4, hi + 30);
  });
  lit(upper); lit(toe);
  withClip(g, toe, () => {
    if (kind === "oxford") { begin(g); g.ellipse(0, -sole - 0.02 * R, w * 0.62, 0.07 * R, 0, Math.PI, 0); g.lineWidth = 5; g.strokeStyle = "rgba(0,0,0,0.4)"; g.stroke(); begin(g); g.ellipse(-w * 0.35, -sole - 0.11 * R, w * 0.28, 0.025 * R, -0.1, 0, Math.PI * 2); g.fillStyle = "rgba(255,255,255,0.6)"; g.fill(); }
    if (kind === "trainers") { begin(g); g.moveTo(-w, -sole - 0.02 * R); g.quadraticCurveTo(-w * 0.2, -sole - 0.14 * R, w * 0.5, -sole - 0.03 * R); g.lineWidth = 0.035 * R; g.strokeStyle = "#d8262e"; g.stroke(); }
    if (kind === "boots") { begin(g); g.ellipse(0, -sole - 0.07 * R, w * 0.7, 0.06 * R, 0, Math.PI, 0); g.lineWidth = 4; g.strokeStyle = "rgba(0,0,0,0.3)"; g.stroke(); }
  });
  toe(); inkStroke(g, 8);
  if (kind === "boots" || kind === "trainers") {   // tongue and laces on the front
    const lc = kind === "boots" ? "#f0e2c0" : "#3a3d52", n = kind === "boots" ? 3 : 2, top = -hi + 0.06 * R, bot = -sole - 0.17 * R;
    begin(g); g.roundRect(-0.075 * R, top - 0.03 * R, 0.15 * R, bot - top + 0.05 * R, 0.03 * R); g.fillStyle = shade(col, 0.82); g.fill();
    for (let k = 0; k < n; k++) { const yy = top + (k + 0.5) * (bot - top) / n; line(g, [[-0.065 * R, yy], [0.065 * R, yy]], 6, lc); }
  }
  g.restore();
};
const footwearOf = (s: Spec) => s.footwear ?? (s.outfit === "suit" ? "oxford" : s.outfit === "coat" ? "oxford" : s.outfit === "dress" ? "flats" : s.outfit === "hoodie" ? "trainers" : "boots");
const shoeColOf = (s: Spec, kind: string) => s.shoeCol ?? (kind === "oxford" ? "#1d1b22" : kind === "trainers" ? "#f4f2ec" : kind === "flats" ? "#7a2a32" : "#6a4428");
const legs = (g: Ctx, s: Spec, p: Pose) => {
  const c = s.limb ?? "#2a1a14", kn = p.knee ?? 0, kind = footwearOf(s), sc = shoeColOf(s, kind);
  { const sh = g.createRadialGradient(CX, FEET, 0, CX, FEET, 0.85 * R); sh.addColorStop(0, "rgba(20,20,40,0.32)"); sh.addColorStop(1, "rgba(20,20,40,0)");
    g.save(); g.translate(CX, FEET); g.scale(1, 0.16); g.translate(-CX, -FEET); g.fillStyle = sh; g.beginPath(); g.arc(CX, FEET, 0.85 * R, 0, Math.PI * 2); g.fill(); g.restore(); }
  for (const sd of [-1, 1]) {
    // v18: walk/run = the foot lifts and the knee comes up toward the lens on alternate phases; pedal = knees high,
    // feet circling on the cranks
    const ph = ((p.step ?? p.pedal ?? 0) + (sd > 0 ? 0.5 : 0)) * Math.PI * 2, lift = p.pedal !== undefined ? 0.5 + 0.5 * Math.sin(ph) : Math.max(0, Math.sin(ph)) * (p.stride ?? (p.step !== undefined ? 0.6 : 0));
    const up = p.pedal !== undefined ? (0.42 + 0.34 * lift) * R : lift * 0.5 * R;
    const hx = CX + sd * 0.27 * R, hy = BODY_B + 0.3 * R, ax = CX + sd * (p.pedal !== undefined ? 0.55 : 0.29) * R, ay = FEET - (kind === "boots" ? 0.3 * R : 0.14 * R) - up;
    const kx = CX + sd * (0.31 + (p.pedal !== undefined ? 0.12 : 0.08 * lift)) * R + kn * 0.3 * R, ky = (hy + ay) / 2 - up * 0.35;
    if (s.legStyle !== "long") legPath(g, [[hx, hy], [kx, ky], [ax, ay]], LIMB_W * 0.95, LIMB_W * 0.78, c);
    if (kind !== "boots" && s.legStyle !== "long") { const sk = s.socks ?? (kind === "trainers" ? "#f4f2ec" : "#3a3d52"); begin(g); g.roundRect(ax - LIMB_W * 0.5, ay - 0.08 * R, LIMB_W, 0.12 * R, 6); fillInk(g, sk, 7); }
    if (up > 1) { g.save(); g.translate(0, -up); shoe(g, ax, sd, kind, sc); g.restore(); } else shoe(g, ax, sd, kind, sc);
  }
};
/** v18: a bike seen head-on: the front tyre (a tall thin ellipse), the fork, mudguard, the lamp; the handlebar is drawn
 *  separately (bikeBar) after the body so the hands close on it */
const BAR_Y = () => BODY_T + 1.25 * R;
const WHEEL_R = 1.0 * R;
const bikeBack = (g: Ctx, col: string) => {   // behind the rider: the rear wheel peeking out under the saddle
  const wy = FEET - WHEEL_R;
  begin(g); g.ellipse(CX, wy + 0.05 * R, 0.13 * R, WHEEL_R * 0.92, 0, 0, Math.PI * 2); fillInk(g, "#2a2a30", 9);
};
const bikeFront = (g: Ctx, col: string) => {   // in front of the legs: tyre, rim, fork, mudguard, up to the stem
  const wy = FEET - WHEEL_R;
  for (const sd of [-1, 1]) line(g, [[CX + sd * 0.16 * R, wy], [CX + sd * 0.1 * R, BAR_Y() + 0.25 * R]], 0.09 * R + 8, INK);
  for (const sd of [-1, 1]) line(g, [[CX + sd * 0.16 * R, wy], [CX + sd * 0.1 * R, BAR_Y() + 0.25 * R]], 0.09 * R, col);
  begin(g); g.ellipse(CX, wy, 0.2 * R, WHEEL_R, 0, 0, Math.PI * 2); fillInk(g, "#2a2a30", 10);
  begin(g); g.ellipse(CX, wy, 0.1 * R, WHEEL_R * 0.84, 0, 0, Math.PI * 2); g.lineWidth = 0.05 * R; g.strokeStyle = "#c8ccd4"; g.stroke();
  begin(g); g.ellipse(CX, wy, 0.12 * R, 0.12 * R, 0, 0, Math.PI * 2); fillInk(g, "#c8ccd4", 6);
  begin(g); g.ellipse(CX, wy - WHEEL_R * 0.98, 0.26 * R, 0.13 * R, 0, Math.PI, 0); fillInk(g, col, 7);
  line(g, [[CX, wy - WHEEL_R], [CX, BAR_Y() + 0.15 * R]], 0.1 * R + 8, INK); line(g, [[CX, wy - WHEEL_R], [CX, BAR_Y() + 0.15 * R]], 0.1 * R, "#c8ccd4");
  for (const sd of [-1, 1]) { begin(g); g.roundRect(CX + sd * 0.55 * R - 0.12 * R, FEET - 0.62 * R, 0.24 * R, 0.07 * R, 0.02 * R); fillInk(g, "#2a2a30", 5); }
};
const bikeBar = (g: Ctx, col: string) => {
  const y = BAR_Y();
  line(g, [[CX - 0.82 * R, y - 0.08 * R], [CX - 0.25 * R, y + 0.04 * R], [CX + 0.25 * R, y + 0.04 * R], [CX + 0.82 * R, y - 0.08 * R]], 0.075 * R + 8, INK);
  line(g, [[CX - 0.82 * R, y - 0.08 * R], [CX - 0.25 * R, y + 0.04 * R], [CX + 0.25 * R, y + 0.04 * R], [CX + 0.82 * R, y - 0.08 * R]], 0.075 * R, "#c8ccd4");
  begin(g); g.ellipse(CX, y + 0.2 * R, 0.13 * R, 0.1 * R, 0, 0, Math.PI * 2); fillInk(g, col, 7);
  begin(g); g.ellipse(CX, y + 0.2 * R, 0.07 * R, 0.05 * R, 0, 0, Math.PI * 2); g.fillStyle = "#fff6c8"; g.fill();
};

/** one character, front view, in the 1000 x 1600 design box (feet at 1560) */
export const drawClean = (g: Ctx, s: Spec, p: Pose = {}) => {
  g.save();
  const sway = p.step !== undefined ? 2.5 * Math.sin(p.step * Math.PI * 2) * (p.stride ?? 0.6) : 0;
  if (p.tilt || sway) { g.translate(CX, FEET); g.rotate((((p.tilt ?? 0) + sway) * Math.PI) / 180); g.translate(-CX, -FEET); }
  // v18 squash & stretch about the feet, volume kept (x = 1 / sqrt(y))
  if (p.squash && p.squash !== 1) { const q = p.squash; g.translate(CX, FEET); g.scale(1 / Math.sqrt(q), q); g.translate(-CX, -FEET); }
  BLD = BUILDS[s.build ?? (s.outfit === "suit" ? "broad" : "average")]; HEM = s.outfit === "coat" ? BODY_B - 0.12 * R : s.outfit === "dress" ? BODY_B : JACKET_HEM();
  // v18 kid: the body below the neck squashed toward the feet, the head the same size and lowered onto it
  const KY = s.kid ? 0.68 : 1, KX = s.kid ? 0.8 : 1, headDy = (1 - KY) * (FEET - BODY_T);
  const bob = (p.bob ?? 0) * R;
  g.save(); g.translate(CX, FEET); g.scale(KX, KY); g.translate(-CX, -FEET);
  const bikeCol = s.trim ?? "#d8262e";
  if (p.pedal !== undefined) bikeBack(g, bikeCol);
  if (!p.sit) legs(g, s, p);
  g.translate(0, bob);
  trousers(g, s);
  if (p.lean) { g.translate(CX, BODY_B - 40); g.rotate((p.lean * Math.PI) / 180); g.translate(-CX, -(BODY_B - 40)); }
  const [aL, aR] = armAngles(p), reachL = p.reachL ?? (p.pedal !== undefined ? [CX - 0.8 * R, BAR_Y() - 0.08 * R] as [number, number] : undefined), reachR = p.reachR ?? (p.pedal !== undefined ? [CX + 0.8 * R, BAR_Y() - 0.08 * R] as [number, number] : undefined);
  const behind = (a: number, r?: [number, number], h?: Held) => !r && !h && a < 40;
  if (behind(aL, reachL, p.holdL)) drawArm(g, s, -1, aL, p.bendL, reachL, p.holdL, p.spray);
  if (behind(aR, reachR, p.holdR)) drawArm(g, s, 1, aR, p.bendR, reachR, p.holdR, p.spray);
  outfit(g, s);
  if (p.pedal !== undefined) { bikeFront(g, bikeCol); bikeBar(g, bikeCol); }
  if (!behind(aL, reachL, p.holdL)) drawArm(g, s, -1, aL, p.bendL, reachL, p.holdL, p.spray);
  if (!behind(aR, reachR, p.holdR)) drawArm(g, s, 1, aR, p.bendR, reachR, p.holdR, p.spray);
  g.restore();
  g.translate(0, headDy + bob * KY);
  if (p.lean) { g.translate(CX, BODY_B - 40 - headDy); g.rotate((p.lean * Math.PI) / 180); g.translate(-CX, -(BODY_B - 40 - headDy)); }
  if (p.headTilt) { g.translate(CX, HY + 0.8 * R); g.rotate((p.headTilt * Math.PI) / 180); g.translate(-CX, -(HY + 0.8 * R)); }
  hairBack(g, s); head(g, s); hair(g, s);
  const yaw = p.yaw ?? 0;
  if (yaw && s.hair && !["none", "bald", "combover"].includes(s.hair)) withClip(g, () => headPath(g), () => {   // hair on the back of a turned head
    const bx = CX - Math.sign(yaw) * 0.95 * R; begin(g); g.ellipse(bx, HY - 0.05 * R, 0.32 * R * Math.min(1, Math.abs(yaw) * 2), 0.5 * R, 0, 0, Math.PI * 2); fillInk(g, s.hairCol ?? "#5a3418", 8);
  });
  face(g, s, p); hat(g, s); hatPaint(g, s);
  g.restore();
};
