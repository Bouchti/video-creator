// Look-dev sheet for the clean-toon kit: our own cast + Dave's expression range.  node scripts/clean_sheet.mjs <out.png>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec, Expr } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_sheet.png";
const cast: [string, Spec, Expr, Record<string, number>][] = [
  ["Dave", { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#3f8a4a", trim: "#5a3a22", mustache: "#4a3020", neckerchief: "#c0353a", hair: "messy", hairCol: "#7a4a22" }, "deadpan", { yaw: -0.45, lean: 3 }],
  ["Repairman", { hat: "cap", hatCol: "#1f4fa0", hatGloss: true, outfit: "overalls", base: "#2f56a8", shirt: "#f4f1ea", hair: "messy", hairCol: "#2a1c18" }, "smirk", { yaw: 0.4 }],
  ["Boss", { hair: "combover", hairCol: "#9a9a9a", outfit: "suit", base: "#5a3a6a", pattern: "dots", tie: "#d8262e", chain: true, build: "stout" }, "smile", { yaw: 0.2, lean: -4 }],
  ["Worker", { hat: "hardhat", hatCol: "#f2c230", hatGloss: true, outfit: "vest", base: "#9be03a", trim: "#d9dde2", build: "broad", shirt: "#3f6fb5", pants: "#2f3a5a", hair: "spiky", hairCol: "#e0b040" }, "worried", { knee: 0.5 }],
  ["Shop assistant", { hair: "bun", hairCol: "#c8502a", outfit: "coat", base: "#f4f6f8", tie: "#2f5fb0", pens: true, glasses: true, build: "slim", pants: "#3a3d52" }, "neutral", { yaw: -0.3 }],
  ["Bailiff", { hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#24222c", tie: "#f4f4f2", mustache: "#6a6a6a", suspenders: "#7a2a32", hair: "slick", hairCol: "#6a6a6a" }, "angry", { yaw: 0.35 }],
];
const exprs: Expr[] = ["neutral", "deadpan", "worried", "shock", "grimace", "smile", "smirk", "angry"];
const cw = 1000, ch = 1600, k = 0.42;
const W = Math.round(cw * k * 6), H = Math.round(ch * k + 760 * 0.55 + 120);
const cv = createCanvas(W, H), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, W, H);
cast.forEach(([name, s, e, extra], i) => {
  g.save(); g.translate(i * cw * k, 40); g.scale(k, k); drawClean(g, s, { expr: e, ...extra, armR: i === 2 ? undefined : 8, wave: i === 2 ? 0.5 : undefined, sweat: e === "worried" }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 26px Arial"; g.textAlign = "center"; g.fillText(name, i * cw * k + cw * k / 2, 30);
});
const y0 = ch * k + 80, kk = 0.55;
exprs.forEach((e, i) => {
  g.save(); g.translate(i * (W / 8) - 120, y0 - 40); g.scale(kk, kk); g.beginPath(); g.rect(0, 0, 1000, 760); g.clip(); drawClean(g, cast[0][1], { expr: e, yaw: i % 2 ? -0.35 : 0.2, sweat: e === "worried" || e === "grimace", look: e === "smirk" ? [0.8, 0] : [0, 0] }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 24px Arial"; g.textAlign = "center"; g.fillText(e, i * (W / 8) + W / 16, H - 16);
});
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("sheet ->", out);
