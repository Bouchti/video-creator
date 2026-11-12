// Close-up look-dev frame: two of our characters framed like a reference close-up (1080 x 800 crop of a 9:16 frame).
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_close.png";
const cv = createCanvas(1080, 800), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
const bg = g.createLinearGradient(0, 0, 0, 800); bg.addColorStop(0, "#d9682a"); bg.addColorStop(0.6, "#e8893a"); bg.addColorStop(1, "#c9783a");
g.fillStyle = bg; g.fillRect(0, 0, 1080, 800);
for (let k = 0; k < 14; k++) { g.fillStyle = k % 2 ? "rgba(120,40,20,0.18)" : "rgba(255,200,120,0.12)"; g.beginPath(); g.ellipse(80 * k, 120 + 40 * (k % 3), 260, 40, -0.2, 0, Math.PI * 2); g.fill(); }
// Dave: big in the foreground left, head turned right, deadpan
g.save(); g.translate(-200, 170); g.scale(0.95, 0.95); drawClean(g, { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#2f7a6a", trim: "#5a3a22", mustache: "#4a3020", neckerchief: "#c0353a", hair: "side", hairCol: "#5a3418", suspenders: "#3a2418" }, { expr: "deadpan", yaw: 0.35, armL: 10, armR: 25 }); g.restore();
// the boss: behind right, leaning on one hip, talking, turned left
g.save(); g.translate(420, 30); g.scale(0.82, 0.82); drawClean(g, { hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#c9a030", pattern: "dots", patCol: "#d9b44a", tie: "#241a1c", chain: true, hair: "side", hairCol: "#7a7a7a" }, { expr: "talk", yaw: -0.3, lean: -6, armL: 30, armR: 15 }); g.restore();
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
