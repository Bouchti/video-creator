// Face look-dev: the full expression range on one bare head (rows 1-3), then the cast's personal faces (row 4).
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec, Expr } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_faces.png";
const exprs: Expr[] = ["neutral", "smile", "laugh", "cheeky", "smug", "smirk", "talk", "suspicious", "deadpan", "sleepy", "worried", "sad", "grimace", "panic", "shock", "angry", "yell", "excited", "love", "dizzy", "cry"];
const hero: Spec = { age: "kid", hair: "messy", hairCol: "#7a4a22", outfit: "jacket", base: "#3f8a4a", iris: "#8a5a2a" };
const cast: [string, Spec, Expr][] = [
  ["Dave", { age: "adult", stubble: true, hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#3f8a4a", mustache: "#4a3020", hair: "messy", hairCol: "#7a4a22", brows: "bushy", iris: "#4a7a3a" }, "suspicious"],
  ["Repairman", { age: "adult", hat: "cap", hatCol: "#1f4fa0", outfit: "overalls", base: "#2f56a8", hair: "messy", hairCol: "#2a1c18", teeth: "buck", iris: "#3a6ab0" }, "cheeky"],
  ["Boss", { age: "old", hair: "combover", hairCol: "#9a9a9a", outfit: "suit", base: "#5a3a6a", tie: "#d8262e", nose: "bulb", brows: "bushy", cheeks: true, iris: "#6a4a8a" }, "laugh"],
  ["Worker", { age: "adult", hat: "hardhat", hatCol: "#f2c230", outfit: "vest", base: "#9be03a", hair: "spiky", hairCol: "#e0b040", brows: "uni", browCol: "#8a6420", iris: "#2a8ab0" }, "panic"],
  ["Shop assistant", { age: "adult", hair: "bun", hairCol: "#c8502a", outfit: "coat", base: "#f4f6f8", glasses: true, lashes: true, freckles: true, brows: "thin", iris: "#2f9a6a" }, "smug"],
  ["Bailiff", { age: "old", hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#24222c", mustache: "#6a6a6a", hair: "slick", hairCol: "#6a6a6a", brows: "thick", iris: "#8a2a2a" }, "yell"],
];
const cols = 7, tw = 420, th = 440, k = 0.62;
const cv = createCanvas(cols * tw, 4 * th + 20), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, cv.width, cv.height);
const tile = (i: number, row: number, s: Spec, e: Expr, label: string) => {
  const x = i * tw, y = row * th;
  g.save(); g.beginPath(); g.rect(x, y, tw, th); g.clip(); g.translate(x + tw / 2 - 500 * k, y + 60); g.scale(k, k); drawClean(g, s, { expr: e, sweat: false }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 24px Arial"; g.textAlign = "center"; g.fillText(label, x + tw / 2, y + 30);
};
exprs.forEach((e, i) => tile(i % cols, Math.floor(i / cols), hero, e, e));
cast.forEach(([n, s, e], i) => tile(i, 3, s, e, `${n}: ${e}`));
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
