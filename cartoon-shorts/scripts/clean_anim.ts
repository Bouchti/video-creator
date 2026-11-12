// v18 animation look-dev: the Gimli cast in their poses + walk / pedal cycles.  node scripts/clean_anim.mjs <out.png>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec, Pose } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_anim.png";
const BOB: Spec = { hat: "pilot", hatCol: "#f4f4f2", outfit: "suit", base: "#1f2a4a", tie: "#1d1b22", cuffs: "#d9a640", wings: true, mustache: "#8a8a8a", hair: "side", hairCol: "#9a9a9a", pants: "#1f2a4a", legStyle: "long" };
const MAU: Spec = { hat: "pilot", hatCol: "#f4f4f2", outfit: "suit", base: "#1f2a4a", tie: "#1d1b22", cuffs: "#d9a640", wings: true, hair: "messy", hairCol: "#2a1c18", pants: "#1f2a4a", legStyle: "long" };
const CREW: Spec = { hat: "cap", hatCol: "#e87a1e", outfit: "vest", base: "#f2c230", trim: "#d9dde2", shirt: "#3f6fb5", pants: "#2f3a5a", hair: "messy", hairCol: "#5a3418" };
const KID1: Spec = { kid: true, outfit: "hoodie", base: "#3f8ad8", hair: "messy", hairCol: "#7a4a22", trim: "#d8262e", pants: "#3a4f7a" };
const KID2: Spec = { kid: true, outfit: "hoodie", base: "#e8503a", hair: "spiky", hairCol: "#e0b040", trim: "#2f9a6a", pants: "#2f3a5a" };
const RACER: Spec = { hat: "helmet", hatCol: "#f4f4f2", hatTrim: "#d8262e", outfit: "jacket", base: "#d8262e", trim: "#f4f4f2", pants: "#d8262e", legStyle: "long" };
const DAD: Spec = { hat: "cap", hatCol: "#2f9a6a", outfit: "hoodie", base: "#f4f1ea", hair: "side", hairCol: "#5a3418", mustache: "#5a3418", pants: "#4a6a9a", build: "stout" };
const MECH: Spec = { hat: "cap", hatCol: "#1f4fa0", outfit: "overalls", base: "#2f56a8", shirt: "#e8e2d4", hair: "messy", hairCol: "#2a1c18" };
const row: [string, Spec, Pose][] = [
  ["Bob: yoke", BOB, { expr: "worried", sit: true, reachL: [400, 960], reachR: [600, 960], sweat: true }],
  ["Maurice: map", MAU, { expr: "smile", holdR: "map", armR: 55, bendR: -40, armL: 120, bendL: -30, yaw: 0.2 }],
  ["Crew: dipstick", CREW, { expr: "deadpan", holdR: "dipstick", armR: 35, bendR: -20 }],
  ["Crew: clipboard", CREW, { expr: "smirk", holdL: "clipboard", armL: 40, bendL: -60 }],
  ["Kid pedal 0", KID1, { expr: "smile", pedal: 0 }],
  ["Kid pedal .5 shock", KID2, { expr: "shock", pedal: 0.5, headTilt: -8 }],
  ["Racer: spray", RACER, { expr: "angry", holdR: "extinguisher", armR: 20, bendR: -50, spray: true, lean: -6 }],
  ["Dad: spatula", DAD, { expr: "shock", holdR: "spatula", armR: 120, armL: 150, bendL: 20, squash: 1.08 }],
  ["Mech: jerrycan", MECH, { expr: "deadpan", holdR: "jerrycan", armR: 8 }],
];
const walk: Pose[] = [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875].map((ph) => ({ expr: "worried", step: ph, stride: 0.8, armL: 20 + 25 * Math.sin(ph * Math.PI * 2), armR: 20 - 25 * Math.sin(ph * Math.PI * 2), bob: 0.06 * Math.abs(Math.cos(ph * Math.PI * 2)) }));
const cw = 1000, ch = 1600, k = 0.34;
const W = Math.round(cw * k * row.length), H = Math.round(ch * k * 2 + 80);
const cv = createCanvas(W, H), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, W, H);
row.forEach(([name, s, p], i) => { g.save(); g.translate(i * cw * k, 40); g.scale(k, k); drawClean(g, s, p); g.restore(); g.fillStyle = "#241a1c"; g.font = "bold 20px Arial"; g.textAlign = "center"; g.fillText(name, i * cw * k + cw * k / 2, 26); });
walk.forEach((p, i) => { const kk = k * 1.05; g.save(); g.translate(i * (W / 8) - 10, ch * k + 70); g.scale(kk, kk); drawClean(g, MECH, p); g.restore(); });
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
