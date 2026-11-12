// Age look-dev: the same expressions on a kid, an adult and an old man.  node scripts/clean_ages.mjs <out.png>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec, Expr } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_ages.png";
const exprs: Expr[] = ["neutral", "smirk", "suspicious", "angry", "sad", "panic", "shock", "laugh", "excited", "yell"];
const people: [string, Spec][] = [
  ["kid", { age: "kid", hair: "messy", hairCol: "#7a4a22", outfit: "hoodie", base: "#3f6fb5", iris: "#8a5a2a" }],
  ["adult", { age: "adult", hair: "side", hairCol: "#2a1c18", outfit: "jacket", base: "#3f8a4a", iris: "#6a4a2a", stubble: true }],
  ["adult beard", { age: "adult", face: "square", hair: "messy", hairCol: "#5a3418", outfit: "jacket", base: "#c0353a", iris: "#3a6a8a", beard: "full" }],
  ["old", { age: "old", hair: "combover", hairCol: "#b0aca4", outfit: "suit", base: "#5a3a6a", iris: "#5a5a6a", mustache: "#c8c4bc" }],
  ["old beard", { age: "old", face: "long", hair: "bald", hairCol: "#d8d4cc", outfit: "coat", base: "#6a5a4a", iris: "#4a5a6a", beard: "full", beardCol: "#e4e0d8", mustache: "#e4e0d8" }],
];
const tw = 300, th = 330, k = 0.46;
const cv = createCanvas(exprs.length * tw, people.length * th + 10), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, cv.width, cv.height);
people.forEach(([who, s], r) => exprs.forEach((e, i) => {
  const x = i * tw, y = r * th;
  g.save(); g.beginPath(); g.rect(x, y, tw, th); g.clip(); g.translate(x + tw / 2 - 500 * k, y + 40); g.scale(k, k); drawClean(g, s, { expr: e }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 20px Arial"; g.textAlign = "center"; g.fillText(`${who}: ${e}`, x + tw / 2, y + 24);
}));
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
