// Hair look-dev: every style bare-headed (row 1-2), then the same people under hats (row 3).  node scripts/clean_hair.mjs <out.png>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec, Hair, Expr } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_hair.png";
const bare: [Hair, string, Expr, Partial<Spec>][] = [
  ["side", "#5a3418", "smirk", {}], ["quiff", "#1e1a1c", "smile", {}], ["spiky", "#e0b040", "talk", {}], ["messy", "#8a4a22", "worried", {}],
  ["curly", "#2a1c18", "smile", {}], ["afro", "#3a2418", "neutral", {}], ["bob", "#c8502a", "neutral", {}], ["ponytail", "#e8c870", "smile", {}],
  ["bun", "#6a4a3a", "deadpan", { glasses: true }], ["mullet", "#7a4a22", "smirk", { mustache: "#6a3a1a" }], ["slick", "#16141a", "deadpan", {}], ["tuft", "#4a3426", "angry", {}],
  ["combover", "#9a9a9a", "worried", {}], ["bald", "#c9c3b5", "shock", { mustache: "#9a9a9a" }],
];
const hatted: [Hair, string, Partial<Spec>][] = [
  ["mullet", "#7a4a22", { hat: "flatcap", hatCol: "#7a6448" }], ["messy", "#2a1c18", { hat: "cap", hatCol: "#1f4fa0" }], ["spiky", "#e0b040", { hat: "hardhat", hatCol: "#f2c230" }],
  ["ponytail", "#c8502a", { hat: "cap", hatCol: "#d8262e" }], ["bob", "#8a4a22", { hat: "beanie", hatCol: "#2f8a7a" }], ["slick", "#6a6a6a", { hat: "bowler", hatCol: "#2a2a30", hatGloss: true }],
  ["curly", "#2a1c18", { hat: "beanie", hatCol: "#c0353a" }],
];
const cols = 7, tw = 330, th = 380, k = 0.62;
const cv = createCanvas(cols * tw, 3 * th), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, cv.width, cv.height);
const tile = (i: number, row: number, s: Spec, e: Expr, label: string, yaw = 0) => {
  const x = i * tw, y = row * th;
  g.save(); g.beginPath(); g.rect(x, y, tw, th); g.clip(); g.translate(x + tw / 2 - 500 * k * 0.5, y + 34); g.scale(k * 0.5 / 0.5 * 0.5, k * 0.5 / 0.5 * 0.5);
  g.translate(0, 0); drawClean(g, s, { expr: e, yaw, look: [0, 0] }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 22px Arial"; g.textAlign = "center"; g.fillText(label, x + tw / 2, y + 24);
};
bare.forEach(([h, c, e, extra], i) => tile(i % cols, Math.floor(i / cols), { hair: h, hairCol: c, outfit: "jacket", base: ["#3f8a4a", "#2f56a8", "#7b3fb0", "#c0353a", "#2f8a7a", "#d9a640", "#5a3a6a"][i % 7], ...extra } as Spec, e, h, i % 3 === 1 ? 0.3 : 0));
hatted.forEach(([h, c, extra], i) => tile(i, 2, { hair: h, hairCol: c, outfit: "jacket", base: "#3f6f8a", ...extra } as Spec, "neutral", `${h} + ${extra.hat}`));
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
