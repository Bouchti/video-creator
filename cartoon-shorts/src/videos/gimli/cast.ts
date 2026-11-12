// The Gimli Glider cast as clean-toon cards (v18 kit: walk, pedal, sit, squash, props in hand) + effect cards + overlay
// labels, staged per shot for the Blender renderer (scripts/export_gimli.ts). Everyone is always moving a little (idle bob,
// head tilts, blinks) and reacts with squash-and-stretch on the beats.
import type { Spec, Pose, Expr } from "../clean/cleantoon";
import {
  FPS, B, SX, RX, CX6, KX, GX, DX, KID_X, kidZ, DAD, CREW, NOZZLE_CREW, BOB, MAU, JET_STOP_Z, RACERS, SPECT, MECHS, VAN_STOP_Z,
  jetStrip, cruiseZ, vehiclesAt, clamp01, smooth, V3,
} from "./story";

export type Card = { o: string; spec: Spec; pose: Pose; x: number; y: number; z: number; h: number; scale?: number; roll?: number; mirror?: boolean };
export type Fx = { key: string; cw: number; ch: number; draw: (g: CanvasRenderingContext2D) => void; x: number; y: number; z: number; w: number; h: number; flat?: boolean; rot?: number; soft?: boolean; upright?: boolean };
export type Overlay = { t: "label" | "shout" | "stamp" | "q"; text: string; x: number; y: number; z: number; k: number; w: number; bg?: string; rot?: number; wob?: number };
export type Stage = { cards: Card[]; fx: Fx[]; ov: Overlay[] };

// ---------------- the cast (v17c faces, v18 bodies) ----------------
const PILOT = { hat: "pilot", hatCol: "#f4f4f2", outfit: "suit", base: "#1f2a4a", tie: "#1d1b22", cuffs: "#d9a640", wings: true, pants: "#1f2a4a", legStyle: "long" } as const;
export const BOB_S: Spec = { ...PILOT, mustache: "#8a8a8a", hair: "side", hairCol: "#9a9a9a" };
export const MAU_S: Spec = { ...PILOT, hair: "messy", hairCol: "#2a1c18" };
const BOB_GL: Spec = { hat: "cap", hatCol: "#d8262e", outfit: "jacket", base: "#3f8ad8", mustache: "#8a8a8a", hair: "side", hairCol: "#9a9a9a" };
const CREW_S: Spec = { hat: "cap", hatCol: "#e87a1e", outfit: "vest", base: "#f2c230", trim: "#d9dde2", shirt: "#3f6fb5", pants: "#2f3a5a", hair: "messy", hairCol: "#5a3418" };
const CREW2_S: Spec = { hat: "beanie", hatCol: "#2f9a6a", outfit: "vest", base: "#f07a1e", trim: "#d9dde2", shirt: "#e8e2d4", pants: "#3a3d52", hair: "side", hairCol: "#2a1c18", mustache: "#2a1c18", build: "stout" };
const NOZ_S: Spec = { hat: "hardhat", hatCol: "#f4f4f2", hatGloss: true, outfit: "overalls", base: "#d8262e", shirt: "#e8e2d4", hair: "spiky", hairCol: "#e0b040" };
const KID1: Spec = { kid: true, outfit: "hoodie", base: "#3f8ad8", hair: "messy", hairCol: "#7a4a22", trim: "#d8262e", pants: "#3a4f7a" };
const KID2: Spec = { kid: true, outfit: "hoodie", base: "#e8503a", hair: "spiky", hairCol: "#e0b040", trim: "#2f9a6a", pants: "#2f3a5a" };
const DAD_S: Spec = { hat: "cap", hatCol: "#2f9a6a", outfit: "hoodie", base: "#f4f1ea", hair: "side", hairCol: "#5a3418", mustache: "#5a3418", pants: "#4a6a9a", build: "stout" };
const RACER = (c: string, t: string): Spec => ({ hat: "helmet", hatCol: c, hatTrim: t, outfit: "jacket", base: t, trim: "#f4f4f2", pants: t, legStyle: "long" });
const RACERS_S = [RACER("#f4f4f2", "#d8262e"), RACER("#ffd02a", "#2f6ad8"), RACER("#2a2a32", "#f07a1e")];
const FOLK: Spec[] = [
  { outfit: "dress", base: "#e86aa8", hair: "bun", hairCol: "#c8502a", lashes: true } as Spec,
  { hat: "cap", hatCol: "#2f6ad8", outfit: "jacket", base: "#d8262e", hair: "messy", hairCol: "#2a1c18", pants: "#3a4f7a" },
  { outfit: "hoodie", base: "#2f9a6a", hair: "curly", hairCol: "#5a3418", pants: "#2f3a5a" },
  { outfit: "dress", base: "#ffd02a", hair: "ponytail", hairCol: "#2a1c18", lashes: true } as Spec,
  { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#7a3ab8", hair: "side", hairCol: "#9a9a9a", mustache: "#9a9a9a", pants: "#4a3426" },
  { kid: true, outfit: "hoodie", base: "#ff9a3a", hair: "spiky", hairCol: "#2a1c18", pants: "#3a4f7a" },
  { outfit: "coat", base: "#f4f6f8", hair: "bob", hairCol: "#e0b040", lashes: true, pants: "#3a3d52" } as Spec,
  { hat: "beanie", hatCol: "#d8262e", outfit: "hoodie", base: "#3f6fb5", hair: "messy", hairCol: "#7a4a22", pants: "#2f3a5a" },
];
const MECH1: Spec = { hat: "cap", hatCol: "#1f4fa0", outfit: "overalls", base: "#2f56a8", shirt: "#e8e2d4", hair: "messy", hairCol: "#2a1c18" };
const MECH2: Spec = { hat: "cap", hatCol: "#d8262e", outfit: "overalls", base: "#2f56a8", shirt: "#e8e2d4", hair: "side", hairCol: "#7a4a22", mustache: "#7a4a22", build: "stout" };
const ADULT_H = 788, KID_H = 650;

// ---------------- life: idle motion, blinks, reactions ----------------
const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };
const q = (v: number, n = 40) => Math.round(v * n) / n;          // quantise so sprite caching still hits
const blinkAt = (f: number, seed: number) => { let s = Math.round(-50 * hh(seed, 9)); for (let n = 0; s <= f && n < 400; n++) { if (f - s >= 0 && f - s < 3) return 1; s += Math.round(48 + 60 * hh(seed * 31 + n, 13)); } return 0; };
/** a breathing bob + slow head drift: the reference characters never freeze */
const idle = (f: number, seed: number, amp = 1): Partial<Pose> => ({
  bob: q(0.035 * amp * Math.sin((f / FPS) * 3.1 + seed * 2.3)), headTilt: q(4 * amp * Math.sin((f / FPS) * 1.3 + seed), 4), blink: blinkAt(f, seed),
});
/** a reaction pop: squash on the hit, stretch on the rebound */
const popSq = (f: number, at: number, k = 0.16) => (f < at ? 1 : q(1 + k * Math.sin(Math.min(1, (f - at) / 9) * Math.PI * 2) * Math.exp(-(f - at) / 7), 50));
const walkPose = (f: number, seed: number, rate = 1.8, stride = 0.7): Partial<Pose> => {
  const ph = ((f / FPS) * rate + hh(seed, 4)) % 1;
  return { step: q(ph, 16), stride, armL: q(18 + 26 * Math.sin(ph * Math.PI * 2), 2), armR: q(18 - 26 * Math.sin(ph * Math.PI * 2), 2), bob: q(0.05 * Math.abs(Math.cos(ph * Math.PI * 2))) };
};
const card = (o: string, spec: Spec, pose: Pose, p: V3, h = ADULT_H, extra: Partial<Card> = {}): Card => ({ o, spec, pose, x: p[0], y: p[1], z: p[2], h, ...extra });

// ---------------- effects ----------------
const fxSmoke = (col: string, a: number) => (g: CanvasRenderingContext2D) => {
  for (const [x, y, r] of [[64, 70, 50], [40, 80, 34], [90, 84, 36], [60, 46, 38]] as [number, number, number][]) {
    const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, col.replace("A", String(a))); gr.addColorStop(1, col.replace("A", "0")); g.fillStyle = gr; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
  }
};
const fxSpark = (seed: number) => (g: CanvasRenderingContext2D) => {
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 60); gr.addColorStop(0, "rgba(255,255,230,1)"); gr.addColorStop(0.25, "rgba(255,200,60,0.9)"); gr.addColorStop(1, "rgba(255,120,20,0)");
  g.fillStyle = gr; g.beginPath(); g.arc(64, 64, 60, 0, Math.PI * 2); g.fill();
  g.strokeStyle = "rgba(255,240,170,1)"; g.lineWidth = 4; g.lineCap = "round";
  for (let k = 0; k < 9; k++) { const a = hh(seed, k) * Math.PI * 2, L = 30 + 30 * hh(seed, k + 9); g.beginPath(); g.moveTo(64, 64); g.lineTo(64 + Math.cos(a) * L, 64 + Math.sin(a) * L); g.stroke(); }
};
const fxFire = (g: CanvasRenderingContext2D) => {
  const gr = g.createRadialGradient(64, 96, 4, 64, 80, 64); gr.addColorStop(0, "rgba(255,250,200,1)"); gr.addColorStop(0.35, "rgba(255,170,40,0.95)"); gr.addColorStop(0.8, "rgba(230,60,20,0.6)"); gr.addColorStop(1, "rgba(200,40,10,0)");
  g.fillStyle = gr; g.beginPath(); g.moveTo(20, 120); g.quadraticCurveTo(10, 50, 50, 10); g.quadraticCurveTo(58, 50, 70, 30); g.quadraticCurveTo(110, 60, 108, 120); g.closePath(); g.fill();
};
const fxBlob = (g: CanvasRenderingContext2D) => { const gr = g.createRadialGradient(64, 64, 0, 64, 64, 62); gr.addColorStop(0, "rgba(30,24,40,0.5)"); gr.addColorStop(1, "rgba(30,24,40,0)"); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); };
const puff = (out: Stage, key: string, x: number, y: number, z: number, s: number, col = "rgba(70,70,80,A)", a = 0.8) =>
  out.fx.push({ key: `puff|${key}|${col}|${a}`, cw: 128, ch: 128, draw: fxSmoke(col, a), x, y, z, w: s, h: s, soft: true });
const shadowBlob = (out: Stage, x: number, z: number, s = 1) => out.fx.push({ key: "blob", cw: 128, ch: 128, draw: fxBlob, x, y: 0.03, z, w: 1.0 * s, h: 0.75 * s, flat: true, soft: true });
const pop = (f: number, f0: number) => (f < f0 ? 0 : Math.min(1, 1.15 * smooth((f - f0) / 6) - 0.15 * smooth((f - f0 - 6) / 6)));
const label = (out: Stage, text: string, p: V3, f: number, f0: number, f1: number, w = 0.42, bg = "#f2c230") => { if (f >= f0 && f < f1) out.ov.push({ t: "label", text, bg, x: p[0], y: p[1], z: p[2], k: pop(f, f0), w }); };
const stamp = (out: Stage, text: string, p: V3, f: number, f0: number, f1: number, w = 0.5, rot = -8) => {
  if (f < f0 || f >= f1) return; const k = 1 + 1.3 * (1 - smooth((f - f0 + 1) / 5)); out.ov.push({ t: "stamp", text, x: p[0], y: p[1], z: p[2], k, w, rot });
};
const shout = (out: Stage, text: string, p: V3, f: number, f0: number, f1: number, w = 0.36) => { if (f >= f0 && f < f1) out.ov.push({ t: "shout", text, x: p[0], y: p[1], z: p[2], k: pop(f, f0), w, wob: Math.round(((f - f0) / 3) % 2) }); };

// ---------------- staging per shot ----------------
export const stage = (id: number, f: number): Stage => {
  const out: Stage = { cards: [], fx: [], ov: [] };
  const t = f / FPS;
  const kids = (shock: boolean) => {
    [KID1, KID2].forEach((s, i) => {
      const ph = q(((t * 2.4 + i * 0.37) % 1), 16), z = kidZ(f) + (i ? -1.2 : 0);
      out.cards.push(card(`kid${i}`, s, { expr: shock ? (i ? "shock" : "worried") : "smile", pedal: ph, ...idle(f, 3 + i, 0.6), bob: q(0.03 * Math.sin(ph * Math.PI * 4)), headTilt: shock ? (i ? -8 : 6) : 0 }, [KID_X[i], 0, z], KID_H));
      shadowBlob(out, KID_X[i], z, 1.1);
    });
  };
  const pilots = (bobE: Expr, mauE: Expr, bobX: Partial<Pose> = {}, mauX: Partial<Pose> = {}) => {
    out.cards.push(card("bob", BOB_S, { expr: bobE, sit: true, reachL: [420, 1010], reachR: [600, 1010], ...idle(f, 1), ...bobX }, BOB));
    out.cards.push(card("mau", MAU_S, { expr: mauE, sit: true, reachL: [400, 1010], reachR: [580, 1010], ...idle(f, 2), ...mauX }, MAU));
  };
  switch (id) {
    case 1: {   // hook: the kids pedalling flat out at us, looking back in horror
      kids(f > 18);
      break;
    }
    case 2: {   // ground crew walking under the jet, a second one by the carts
      const z = -6 + 1.5 * ((f - 87) / FPS);
      out.cards.push(card("crew", CREW_S, { expr: "neutral", ...walkPose(f, 1), yaw: 0.3 }, [CREW[0], 0, z])); shadowBlob(out, CREW[0], z);
      break;
    }
    case 3: {   // the captain tapping the blank gauge
      const tap = f >= 226 ? q(Math.abs(Math.sin((f - 226) * 0.45)) * 18, 2) : 0;
      out.cards.push(card("bob", BOB_S, { expr: f < 240 ? "deadpan" : "worried", sit: true, armR: 78 + tap, bendR: -40, reachL: [420, 1010], ...idle(f, 1), headTilt: f > 240 ? -8 : 0 }, BOB));
      break;
    }
    case 4: {   // the crewman pulling the dipstick down out of the wing
      const pull = smooth((f - 290) / 50);
      out.cards.push(card("crew", CREW_S, { expr: f < B.dipstick ? "neutral" : "smirk", holdR: "dipstick", armR: q(168 - 48 * pull, 1), bendR: q(-10 - 20 * pull, 1), armL: 20, ...idle(f, 1), squash: popSq(f, B.dipstick, 0.08) }, CREW));
      shadowBlob(out, CREW[0], CREW[2]);
      break;
    }
    case 5: {   // reading the stick; "KILOS" over the tank in the wing
      out.cards.push(card("crew", CREW_S, { expr: "suspicious", holdR: "dipstick", armR: 120, bendR: -30, ...idle(f, 1), look: [0.6, -0.3] }, CREW)); shadowBlob(out, CREW[0], CREW[2]);
      label(out, "KILOS", [RX - 8.6, 4.6, -2.0], f, B.kilos - 3, 481, 0.4, "#5ab0ff");
      break;
    }
    case 6: {   // the clipboard: "x 1.77"; "POUNDS"
      out.cards.push(card("crew", CREW_S, { expr: f < B.pounds ? "smirk" : "smile", holdL: "clipboard", armL: 40, bendL: -60, armR: 20, ...idle(f, 1), headTilt: q(5 * Math.sin(t * 6), 2), squash: popSq(f, B.pounds, 0.1) }, CREW));
      label(out, "POUNDS", [CREW[0] - 0.4, 2.3, CREW[2]], f, B.pounds - 2, 542, 0.42, "#f2c230");
      break;
    }
    case 7: {   // the nozzle in the wing; LESS THAN HALF
      out.cards.push(card("noz", NOZ_S, { expr: "smile", holdR: "nozzle", armR: 150, bendR: -30, armL: 25, ...idle(f, 6) }, NOZZLE_CREW)); shadowBlob(out, NOZZLE_CREW[0], NOZZLE_CREW[2]);
      stamp(out, "LESS THAN HALF", [RX - 11.5, 4.2, -0.5], f, B.half, 626, 0.62, -7);
      break;
    }
    case 8: {   // Ottawa: a new crewman, the same stick, the same maths, a confident nod
      const nod = f > 668 ? q(6 * Math.sin((f - 668) * 0.5), 2) : 0;
      out.cards.push(card("crew2", CREW2_S, { expr: f < B.same ? "smile" : "smirk", holdR: "dipstick", armR: 120, bendR: -30, holdL: "clipboard", armL: 40, bendL: -60, ...idle(f, 7), headTilt: nod }, CREW));
      shadowBlob(out, CREW[0], CREW[2]);
      stamp(out, "SAME MISTAKE", [CREW[0] + 0.2, 2.6, CREW[2]], f, B.same, 716, 0.62, 6);
      break;
    }
    case 9: label(out, "41,000 FT", [KX - 4, 9, cruiseZ(f) - 4], f, 722, 762, 0.42, "#ffffff"); break;
    case 10: {  // BONG: both pilots snap round
      const hit = B.bong + 3;
      pilots(f < hit ? "neutral" : "shock", f < hit ? "smirk" : "shock", { squash: popSq(f, hit, 0.12), headTilt: f < hit ? 0 : -10, sweat: f > hit + 20 }, { squash: popSq(f, hit + 2, 0.12), headTilt: f < hit ? 0 : 9 });
      shout(out, "BONG!", [CX6, 1.85, 1.2], f, B.bong, B.bong + 30, 0.42);
      break;
    }
    case 11: case 12: {   // an engine dies: the fan winds down, smoke puffs trail back from the exhaust
      const sx = id === 11 ? 1 : -1, at = id === 11 ? B.left - 26 : B.right - 22;
      for (let k = 0; k < 6; k++) {
        const te = at + k * 4; if (f < te) continue;
        const age = (f - te) / FPS; puff(out, `eng${id}${k}`, KX + sx * 8.1, 1.45 + 0.6 * age, cruiseZ(te) - 0.8 - 2 * age, 1.4 + 3.5 * age, "rgba(60,60,66,A)", Math.max(0, 0.85 - 0.5 * age));
      }
      break;
    }
    case 13: pilots(f < B.black ? "worried" : "deadpan", f < B.black ? "worried" : "deadpan", { look: f > B.black + 6 ? [0.7, 0] : [0, 0] }, { look: f > B.black + 10 ? [-0.7, 0] : [0, 0] }); break;
    case 14: {  // Bob in his glider, waving, the barrel roll on "for fun"
      const v = vehiclesAt(14, f).glider; if (!v) break;
      const roll = v.roll ?? 0, by = -0.12;
      out.cards.push(card("bobgl", BOB_GL, { expr: f < B.fun ? "smile" : "smile", sit: true, wave: q(Math.sin(t * 7), 4), armL: 20, ...idle(f, 1, 0.5) }, [v.x - Math.sin(roll) * by, v.y! + Math.cos(roll) * by, v.z + 2.0], 500, { roll: -roll }));
      break;
    }
    case 15: {  // the co-pilot's chart and his pointing finger: GIMLI
      pilots("worried", f < B.gimli ? "neutral" : "smile", { yaw: -0.4, headTilt: f > B.gimli ? -6 : 0 }, { holdR: "map", armR: 55, bendR: -40, armL: q(f > 1215 ? 120 : 30, 1), bendL: -30, reachL: undefined, reachR: undefined, yaw: 0.25, squash: popSq(f, B.gimli, 0.1) });
      break;
    }
    case 16: {  // Family Day: folks milling about the pits, kids running, a couple walking to the banner
      const spots: [number, number][] = [[-24, 356], [-20.5, 364], [-29, 372], [-14, 352], [-33, 386], [-18, 380], [-26, 398], [-11, 370], [-36, 362], [-22, 345]];
      spots.forEach(([x, z], i) => {
        const moving = i % 3 === 0, zz = moving ? z + 1.6 * Math.sin(t * 0.8 + i) : z;
        out.cards.push(card(`folk${i}`, FOLK[i % FOLK.length], { expr: (["smile", "neutral", "smirk"] as Expr[])[i % 3], ...(moving ? walkPose(f, i) : idle(f, i)), wave: i === 4 ? q(Math.sin(t * 6), 4) : undefined }, [x, 0, zz], FOLK[i % FOLK.length].kid ? KID_H : ADULT_H));
        shadowBlob(out, x, zz);
      });
      out.cards.push(card("dad", DAD_S, { expr: "smile", holdR: "spatula", armR: 60, bendR: -30, ...idle(f, 9) }, DAD)); shadowBlob(out, DAD[0], DAD[2]);
      break;
    }
    case 17: {  // burnout smoke off the slicks, then the launch
      const v = vehiclesAt(17, f);
      for (const d of [v.drag, v.drag2]) if (d && f < 1440) for (let k = 0; k < 3; k++) puff(out, `bo${k}`, d.x + (k % 2 ? 1.6 : -1.6) + 0.04 * (f - 1414) * (k % 2 ? 1 : -1), 0.5 + 0.2 * k, d.z + 2.3 + 0.3 * k, Math.min(2.6, 1.0 + 0.08 * (f - 1414) + 0.3 * k), "rgba(245,245,245,A)", 0.6);
      break;
    }
    case 18: kids(false); break;
    case 19: {  // the dad at his BBQ: turns, freezes, the spatula drops; behind him the jet coming in without a sound
      const turned = f >= 1500, drop = f >= 1520;
      out.cards.push(card("dad", DAD_S, { expr: turned ? "shock" : "smile", holdR: drop ? undefined : "spatula", armR: drop ? 150 : 60, bendR: drop ? 10 : -30, armL: drop ? 150 : 15, bendL: drop ? 10 : 0, ...idle(f, 9), squash: popSq(f, 1520, 0.16), headTilt: turned ? -6 : 0 }, DAD));
      shadowBlob(out, DAD[0], DAD[2]);
      out.cards.push(card("mom", FOLK[0], { expr: turned ? "shock" : "smile", ...idle(f, 11), armL: turned ? 160 : 10, bendL: 30, armR: turned ? 160 : 10, bendR: 30 }, [DAD[0] - 0.95, 0, DAD[2] - 2.3])); shadowBlob(out, DAD[0] - 0.95, DAD[2] - 2.3);
      break;
    }
    case 20: {  // Bob hauling the yoke over, crossed controls, sweating
      const k = smooth((f - 1580) / 30), sway = q(Math.sin(t * 9) * 12, 1);
      pilots("angry", "worried", { reachL: [420 - 40 * k, 990 + 60 * k + sway], reachR: [600 - 40 * k, 1060 - 60 * k - sway], lean: q(-8 * k, 1), sweat: true, squash: popSq(f, 1628, 0.08) }, { look: [0.8, 0], sweat: true });
      break;
    }
    case 22: case 23: {   // sparks under the nose while it scrapes; the crowd ducks
      const j = jetStrip(f);
      if (j && !j.nose && f < B.stop) for (let k = 0; k < 5; k++) {
        const s = 0.9 + 1.6 * hh(f + k, 3); out.fx.push({ key: `spark|${(f + k) % 6}`, cw: 128, ch: 128, draw: fxSpark((f + k) % 6), x: j.x + (hh(f, k) - 0.5) * 1.4, y: 0.35 + 0.5 * hh(f, k + 3), z: j.z + 19 - 2.2 * k - 3 * hh(f, k + 7), w: s, h: s, soft: true });
        puff(out, `dust${k}`, j.x + (k - 2) * 1.2, 0.6, j.z + 14 - 3 * k, 2.5 + k * 0.4, "rgba(200,190,170,A)", 0.55);
      }
      if (id === 23) SPECT.forEach((p, i) => {
        const duck = f >= 1790 + i * 3;
        out.cards.push(card(`sp${i}`, FOLK[(i + 2) % FOLK.length], { expr: duck ? "shock" : "worried", ...idle(f, 20 + i), armL: duck ? 165 : 20, bendL: duck ? 40 : 0, armR: duck ? 165 : 20, bendR: duck ? 40 : 0, squash: duck ? q(0.86 + 0.04 * Math.sin(f * 0.8 + i), 50) : 1 }, p, FOLK[(i + 2) % FOLK.length].kid ? KID_H : ADULT_H));
        shadowBlob(out, p[0], p[2]);
      });
      break;
    }
    case 24: {  // racers blasting extinguishers at the smoking nose
      const nz = JET_STOP_Z + 21.5, out_ = f >= B.fire + 6;
      if (!out_) { const s = 1.8 + 0.3 * Math.sin(f * 0.9); out.fx.push({ key: "fire", cw: 128, ch: 128, draw: fxFire, x: 0, y: 0.9, z: nz, w: s, h: s * 1.2, soft: true, upright: true }); }
      for (let k = 0; k < 3; k++) puff(out, `smk${k}`, 0.4 * (k - 1), 3.0 + 1.1 * k + 0.03 * (f - 1844), nz - 1.0 - 0.6 * k, 1.8 + 0.5 * k, "rgba(50,50,56,A)", out_ ? 0.25 : 0.55);
      RACERS.forEach((p, i) => {
        const run_ = f < 1858 + i * 4, z = run_ ? p[2] + 4 * (1 - (f - 1844) / (14 + i * 4)) : p[2];
        out.cards.push(card(`racer${i}`, RACERS_S[i], { expr: "angry", holdR: "extinguisher", armR: 22, bendR: -55, spray: !run_, ...(run_ ? walkPose(f, i, 3, 0.9) : idle(f, 30 + i)), lean: run_ ? -8 : -5 }, [p[0], 0, z]));
        shadowBlob(out, p[0], z);
        if (!run_) for (let k = 0; k < 3; k++) puff(out, `spray${i}${k}`, p[0] + (0 - p[0]) * (0.45 + 0.2 * k), 1.0 + 0.2 * k, z + (nz - z) * (0.45 + 0.2 * k), 0.7 + 0.4 * k, "rgba(255,255,255,A)", 0.7);
      });
      break;
    }
    case 25: {  // Bob's thumbs-up in front of the nose; passengers round the jet; one more down the steep slide
      out.cards.push(card("bob", BOB_S, { expr: "smile", armR: 150, bendR: -20, ...idle(f, 1), squash: popSq(f, B.survive, 0.1) }, [1.8, 0, JET_STOP_Z + 29])); shadowBlob(out, 1.8, JET_STOP_Z + 29);
      out.cards.push(card("mau", MAU_S, { expr: "smile", ...idle(f, 2), wave: q(Math.sin(t * 5), 4) }, [-1.2, 0, JET_STOP_Z + 28])); shadowBlob(out, -1.2, JET_STOP_Z + 28);
      const pax: [number, number][] = [[7, 236], [8.5, 240], [10, 233], [6, 244], [11.5, 238], [9, 229]];
      pax.forEach(([x, z], i) => { out.cards.push(card(`pax${i}`, FOLK[(i + 1) % FOLK.length], { expr: i % 2 ? "smile" : "worried", ...idle(f, 40 + i), wave: i === 2 ? q(Math.sin(t * 6), 4) : undefined }, [x, 0, z], FOLK[(i + 1) % FOLK.length].kid ? KID_H : ADULT_H)); shadowBlob(out, x, z); });
      const s = clamp01((f - 1900) / 30), a = (48 * Math.PI) / 180, L = 8.6 * s;
      out.cards.push(card("slider", FOLK[3], { expr: "shock", sit: true, armL: 150, armR: 150 }, [2.55 + L * Math.cos(a), Math.max(0, 6.05 - L * Math.sin(a) - 0.3), JET_STOP_Z - 11.2]));
      break;
    }
    case 27: {  // the van has stopped: the mechanics, the upside-down empty jerrycan, two deadpan faces
      if (f < B.empty) break;
      const look = f > 2072;
      out.cards.push(card("mech1", MECH1, { expr: "deadpan", holdR: "jerrycan", armR: 105, bendR: 40, ...idle(f, 50), yaw: look ? 0.45 : 0 }, MECHS[0])); shadowBlob(out, MECHS[0][0], MECHS[0][2]);
      out.cards.push(card("mech2", MECH2, { expr: f > 2062 ? "deadpan" : "worried", ...idle(f, 51), armL: 20, armR: 20, yaw: look ? -0.45 : 0, look: look ? [-0.8, 0] : [0, 0] }, MECHS[1])); shadowBlob(out, MECHS[1][0], MECHS[1][2]);
      break;
    }
  }
  return out;
};
