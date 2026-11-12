// Body look-dev: one of our characters framed like a reference body shot (vest, trousers, arms, legs).
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import { drawClean } from "../src/videos/clean/cleantoon";
const out = process.argv[2] ?? "out/clean_body.png";
const cv = createCanvas(700, 800), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D;
const bg = g.createLinearGradient(0, 0, 0, 800); bg.addColorStop(0, "#d9682a"); bg.addColorStop(0.55, "#e8a060"); bg.addColorStop(1, "#b0705a");
g.fillStyle = bg; g.fillRect(0, 0, 700, 800);
g.save(); g.translate(-30, -377); g.scale(0.76, 0.76);
drawClean(g, { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#24a89a", trim: "#5a3a22", neckerchief: "#c0353a", hair: "side", hairCol: "#5a3418", suspenders: "#3a2418", pants: "#4a3426" }, { expr: "deadpan", yaw: 0.3, armL: 6, armR: 6, knee: 0.3 });
g.restore();
fs.writeFileSync(out, cv.toBuffer("image/png")); console.log("->", out);
