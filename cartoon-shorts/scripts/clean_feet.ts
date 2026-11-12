// Legs and feet: the three shoe types, stick legs (A) and full-length trousers (B), full figures.
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean, Spec } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_feet.png";
const k = 0.42, cv = createCanvas(Math.round(6 * 1000 * k), Math.round(1600 * k) + 60), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
g.fillStyle = "#cfe3f5"; g.fillRect(0, 0, cv.width, cv.height);
const base: [string, Spec][] = [
  ["boots", { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#3f8a4a", pants: "#4a3426", footwear: "boots", mustache: "#4a3020" }],
  ["oxfords", { hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#24222c", pants: "#24222c", footwear: "oxford", tie: "#d8262e" }],
  ["trainers", { hair: "curly", hairCol: "#2a1c18", outfit: "hoodie", base: "#7b3fb0", pants: "#3a4f7a", footwear: "trainers" }],
];
[...base.map(([n, s]) => [`A stick legs: ${n}`, s] as [string, Spec]), ...base.map(([n, s]) => [`B long trousers: ${n}`, { ...s, legStyle: "long" }] as [string, Spec])].forEach(([name, s], i) => {
  g.save(); g.translate(i * 1000 * k, 50); g.scale(k, k); drawClean(g, s, { expr: "neutral" }); g.restore();
  g.fillStyle = "#241a1c"; g.font = "bold 22px Arial"; g.textAlign = "center"; g.fillText(name, i * 1000 * k + 500 * k, 30);
});
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
