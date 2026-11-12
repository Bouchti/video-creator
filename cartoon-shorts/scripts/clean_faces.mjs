// scripts/clean_faces.ts
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";

// src/videos/clean/cleantoon.ts
var INK = "#241a1c";
var R = 230;
var CX = 500;
var HY = 380;
var FEET = 1560;
var BODY_T = HY + 0.62 * R;
var BODY_B = FEET - 1.45 * R;
var W_INK = 15;
var SEAM = "rgba(0,0,0,0.42)";
var shade = (hex, k2) => {
  const n = parseInt(hex.slice(1), 16), c = [n >> 16 & 255, n >> 8 & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(k2 >= 1 ? v + (255 - v) * (k2 - 1) : v * k2))));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};
var begin = (g2) => g2.beginPath();
var inkStroke = (g2, w = W_INK) => {
  g2.lineWidth = w;
  g2.strokeStyle = INK;
  g2.lineJoin = "round";
  g2.lineCap = "round";
  g2.stroke();
};
var fillInk = (g2, fill, w = W_INK) => {
  g2.fillStyle = fill;
  g2.fill();
  inkStroke(g2, w);
};
var circle = (g2, x, y, r) => {
  begin(g2);
  g2.arc(x, y, r, 0, Math.PI * 2);
};
var line = (g2, pts, w, col = INK, dash = []) => {
  begin(g2);
  pts.forEach(([x, y], i) => i ? g2.lineTo(x, y) : g2.moveTo(x, y));
  g2.setLineDash(dash);
  g2.lineWidth = w;
  g2.strokeStyle = col;
  g2.lineCap = "round";
  g2.lineJoin = "round";
  g2.stroke();
  g2.setLineDash([]);
};
var BUILDS = {
  average: { sh: 0.68, wa: 0.74, hi: 0.8, he: 0.8 },
  stout: { sh: 0.7, wa: 1, hi: 1.04, he: 0.96 },
  slim: { sh: 0.58, wa: 0.56, hi: 0.62, he: 0.6 },
  broad: { sh: 0.82, wa: 0.82, hi: 0.84, he: 0.82 }
};
var BLD = BUILDS.average;
var HEM = 0;
var JACKET_HEM = () => BODY_B - 0.5 * R;
var bodyPath = (g2, inset = 0) => {
  const t = BODY_T + inset, b = HEM - inset, h = b - t, sh = BLD.sh * R - inset, wa = BLD.wa * R - inset, hi = BLD.hi * R - inset, he = BLD.he * R - inset, rc = 0.42 * R;
  begin(g2);
  g2.moveTo(CX, t - 0.03 * R);
  g2.quadraticCurveTo(CX + sh * 0.45, t - 0.03 * R, CX + sh * 0.84, t + 0.13 * R);
  g2.quadraticCurveTo(CX + sh, t + 0.2 * R, CX + sh, t + rc);
  g2.bezierCurveTo(CX + sh, t + 0.48 * h, CX + wa, t + 0.48 * h, CX + wa, t + 0.6 * h);
  g2.bezierCurveTo(CX + wa, t + 0.7 * h, CX + hi, t + 0.74 * h, CX + hi, t + 0.88 * h);
  g2.quadraticCurveTo(CX + hi, b, CX + he - 0.12 * R, b);
  g2.quadraticCurveTo(CX, b + 0.03 * R, CX - he + 0.12 * R, b);
  g2.quadraticCurveTo(CX - hi, b, CX - hi, t + 0.88 * h);
  g2.bezierCurveTo(CX - hi, t + 0.74 * h, CX - wa, t + 0.7 * h, CX - wa, t + 0.6 * h);
  g2.bezierCurveTo(CX - wa, t + 0.48 * h, CX - sh, t + 0.48 * h, CX - sh, t + rc);
  g2.quadraticCurveTo(CX - sh, t + 0.2 * R, CX - sh * 0.84, t + 0.13 * R);
  g2.quadraticCurveTo(CX - sh * 0.45, t - 0.03 * R, CX, t - 0.03 * R);
  g2.closePath();
};
var trousers = (g2, s) => {
  if (s.outfit === "dress") return;
  const long = s.legStyle === "long", col = s.outfit === "overalls" ? s.base : s.pants ?? "#4a3426", top = JACKET_HEM() - 0.3 * R, bot = long ? FEET - 0.17 * R : BODY_B + 0.42 * R, hw = BLD.hi * R * 0.9, cw = long ? 0.17 * R : 0.2 * R;
  const path = () => {
    begin(g2);
    g2.moveTo(CX - hw, top);
    g2.lineTo(CX + hw, top);
    g2.bezierCurveTo(CX + hw, top + 0.45 * R, CX + 0.28 * R + cw + 0.02 * R, top + 0.9 * R, CX + 0.28 * R + cw, bot);
    g2.lineTo(CX + 0.28 * R - cw, bot);
    g2.lineTo(CX + 0.1 * R, top + 0.75 * R);
    g2.quadraticCurveTo(CX, top + 0.6 * R, CX - 0.1 * R, top + 0.75 * R);
    g2.lineTo(CX - 0.28 * R + cw, bot);
    g2.lineTo(CX - 0.28 * R - cw, bot);
    g2.bezierCurveTo(CX - 0.28 * R - cw - 0.02 * R, top + 0.9 * R, CX - hw, top + 0.45 * R, CX - hw, top);
    g2.closePath();
  };
  path();
  g2.fillStyle = col;
  g2.fill();
  withClip(g2, path, () => {
    const cyl = g2.createLinearGradient(CX - R, 0, CX + R, 0);
    cyl.addColorStop(0, "rgba(255,255,255,0.12)");
    cyl.addColorStop(0.35, "rgba(255,255,255,0)");
    cyl.addColorStop(1, "rgba(10,10,20,0.35)");
    g2.fillStyle = cyl;
    g2.fillRect(CX - 2 * R, top, 4 * R, bot - top + 10);
    line(g2, [[CX, top + 0.62 * R], [CX, top]], 4, "rgba(0,0,0,0.3)");
    for (const sd of [-1, 1]) {
      line(g2, [[CX + sd * (0.28 * R - cw), bot - 0.06 * R], [CX + sd * (0.28 * R + cw), bot - 0.06 * R]], 4, "rgba(0,0,0,0.3)");
      line(g2, [[CX + sd * 0.28 * R, top + 0.85 * R], [CX + sd * 0.28 * R, bot - 0.1 * R]], 3, "rgba(255,255,255,0.12)");
    }
  });
  path();
  inkStroke(g2, W_INK);
};
var withClip = (g2, path, fn) => {
  g2.save();
  path();
  g2.clip();
  fn();
  g2.restore();
};
var outfit = (g2, s) => {
  const base = s.base, dark = shade(base, 0.8), trim = s.trim ?? shade(base, 0.62);
  bodyPath(g2);
  g2.fillStyle = base;
  g2.fill();
  withClip(g2, () => bodyPath(g2), () => {
    const tx = (x) => CX + x * R;
    if (s.outfit === "vest") {
      const band = s.trim ?? "#cfd3d8";
      for (const x of [-0.5, 0.5]) {
        g2.fillStyle = band;
        g2.fillRect(tx(x) - 0.13 * R, BODY_T, 0.26 * R, 2.2 * R);
        line(g2, [[tx(x) - 0.13 * R, BODY_T], [tx(x) - 0.13 * R, BODY_B]], 5, dark);
        line(g2, [[tx(x) + 0.13 * R, BODY_T], [tx(x) + 0.13 * R, BODY_B]], 5, dark);
      }
      g2.fillStyle = band;
      g2.fillRect(CX - 1.2 * R, BODY_T + 1.25 * R, 2.4 * R, 0.24 * R);
      line(g2, [[CX - 1.2 * R, BODY_T + 1.25 * R], [CX + 1.2 * R, BODY_T + 1.25 * R]], 5, dark);
      line(g2, [[CX - 1.2 * R, BODY_T + 1.49 * R], [CX + 1.2 * R, BODY_T + 1.49 * R]], 5, dark);
      for (const x of [-0.5, 0.5]) line(g2, [[tx(x), BODY_T + 20], [tx(x), BODY_B]], 4, SEAM, [16, 12]);
      line(g2, [[CX, BODY_T + 20], [CX, BODY_B]], 6, dark);
    } else if (s.outfit === "coat") {
      const shirt = s.shirt ?? "#eef2f6";
      begin(g2);
      g2.moveTo(CX - 0.32 * R, BODY_T);
      g2.lineTo(CX, BODY_T + 0.95 * R);
      g2.lineTo(CX + 0.32 * R, BODY_T);
      g2.closePath();
      g2.fillStyle = shirt;
      g2.fill();
      if (s.tie) {
        begin(g2);
        g2.moveTo(CX - 0.07 * R, BODY_T + 0.08 * R);
        g2.lineTo(CX + 0.07 * R, BODY_T + 0.08 * R);
        g2.lineTo(CX + 0.1 * R, BODY_T + 0.8 * R);
        g2.lineTo(CX, BODY_T + 0.92 * R);
        g2.lineTo(CX - 0.1 * R, BODY_T + 0.8 * R);
        g2.closePath();
        fillInk(g2, s.tie, 6);
      }
      for (const sd of [-1, 1]) {
        begin(g2);
        g2.moveTo(CX + sd * 0.32 * R, BODY_T - 6);
        g2.lineTo(CX + sd * 0.02 * R, BODY_T + 1 * R);
        g2.lineTo(CX + sd * 0.42 * R, BODY_T + 0.42 * R);
        g2.closePath();
        g2.fillStyle = shade(base, 0.93);
        g2.fill();
        inkStroke(g2, 6);
      }
      line(g2, [[CX, BODY_T + 1 * R], [CX, HEM + 10]], 6, INK);
      for (let k2 = 0; k2 < 3; k2++) circle(g2, CX + 0.1 * R, BODY_T + (1.25 + 0.42 * k2) * R, 9), fillInk(g2, shade(base, 0.85), 4);
      const px = CX - 0.62 * R, py = BODY_T + 0.62 * R;
      if (s.pens !== false) {
        line(g2, [[px + 18, py + 20], [px + 18, py - 40]], 16, "#d8262e");
        line(g2, [[px + 48, py + 20], [px + 48, py - 34]], 16, "#2f5fb0");
      }
      begin(g2);
      g2.rect(px - 10, py, 0.42 * R, 0.36 * R);
      fillInk(g2, shade(base, 0.96), 6);
      line(g2, [[px + 2, py + 16], [px - 22 + 0.42 * R, py + 16]], 3, SEAM, [10, 8]);
    } else if (s.outfit === "suit") {
      const shirt = s.shirt ?? "#f4f4f2";
      begin(g2);
      g2.moveTo(CX - 0.28 * R, BODY_T);
      g2.lineTo(CX, BODY_T + 0.9 * R);
      g2.lineTo(CX + 0.28 * R, BODY_T);
      g2.closePath();
      g2.fillStyle = shirt;
      g2.fill();
      begin(g2);
      g2.moveTo(CX - 0.06 * R, BODY_T + 0.06 * R);
      g2.lineTo(CX + 0.06 * R, BODY_T + 0.06 * R);
      g2.lineTo(CX + 0.09 * R, BODY_T + 0.74 * R);
      g2.lineTo(CX, BODY_T + 0.86 * R);
      g2.lineTo(CX - 0.09 * R, BODY_T + 0.74 * R);
      g2.closePath();
      fillInk(g2, s.tie ?? "#d8262e", 6);
      for (const sd of [-1, 1]) {
        begin(g2);
        g2.moveTo(CX + sd * 0.28 * R, BODY_T - 6);
        g2.lineTo(CX + sd * 0.03 * R, BODY_T + 0.92 * R);
        g2.lineTo(CX + sd * 0.4 * R, BODY_T + 0.5 * R);
        g2.lineTo(CX + sd * 0.3 * R, BODY_T + 0.3 * R);
        g2.closePath();
        g2.fillStyle = shade(base, 1.18);
        g2.fill();
        inkStroke(g2, 6);
      }
      for (let k2 = 0; k2 < 2; k2++) circle(g2, CX + 0.08 * R, BODY_T + (1.15 + 0.4 * k2) * R, 9), fillInk(g2, shade(base, 0.6), 4);
      begin(g2);
      g2.rect(CX + 0.4 * R, BODY_T + 0.62 * R, 0.34 * R, 0.08 * R);
      fillInk(g2, shade(base, 0.85), 4);
      begin(g2);
      g2.moveTo(CX + 0.45 * R, BODY_T + 0.62 * R);
      g2.lineTo(CX + 0.52 * R, BODY_T + 0.5 * R);
      g2.lineTo(CX + 0.6 * R, BODY_T + 0.62 * R);
      g2.closePath();
      g2.fillStyle = "#ffffff";
      g2.fill();
    } else if (s.outfit === "overalls") {
      const shirt = s.shirt ?? "#e8e2d4";
      g2.fillStyle = shirt;
      g2.fillRect(CX - 2 * R, BODY_T - 50, 4 * R, 0.55 * R + 50);
      begin(g2);
      g2.rect(CX - 0.5 * R, BODY_T + 0.25 * R, R, 0.75 * R);
      fillInk(g2, shade(base, 1.06), 7);
      line(g2, [[CX - 0.42 * R, BODY_T + 0.33 * R], [CX + 0.42 * R, BODY_T + 0.33 * R], [CX + 0.42 * R, BODY_T + 0.92 * R], [CX - 0.42 * R, BODY_T + 0.92 * R], [CX - 0.42 * R, BODY_T + 0.33 * R]], 4, SEAM, [14, 10]);
      for (const sd of [-1, 1]) {
        line(g2, [[CX + sd * 0.42 * R, BODY_T + 0.3 * R], [CX + sd * 0.78 * R, BODY_T - 10]], 34, shade(base, 0.92));
        circle(g2, CX + sd * 0.42 * R, BODY_T + 0.32 * R, 13);
        fillInk(g2, "#d9a640", 5);
      }
      line(g2, [[CX - 0.98 * R, BODY_T + 1.12 * R], [CX + 0.98 * R, BODY_T + 1.12 * R]], 4, SEAM, [14, 10]);
      begin(g2);
      g2.rect(CX - 0.2 * R, BODY_T + 0.42 * R, 0.4 * R, 0.3 * R);
      fillInk(g2, base, 5);
      line(g2, [[CX, BODY_T + 1.4 * R], [CX, BODY_B]], 5, dark);
    } else if (s.outfit === "jacket") {
      begin(g2);
      g2.moveTo(CX - 0.42 * R, BODY_T - 4);
      g2.lineTo(CX, BODY_T + 0.32 * R);
      g2.lineTo(CX + 0.42 * R, BODY_T - 4);
      g2.lineTo(CX + 0.3 * R, BODY_T + 0.3 * R);
      g2.lineTo(CX, BODY_T + 0.44 * R);
      g2.lineTo(CX - 0.3 * R, BODY_T + 0.3 * R);
      g2.closePath();
      fillInk(g2, trim, 6);
      line(g2, [[CX, BODY_T + 0.44 * R], [CX, BODY_B]], 6, dark);
      for (let k2 = 0; k2 < 3; k2++) {
        const by = BODY_T + (0.75 + 0.62 * k2) * R;
        circle(g2, CX, by, 0.11 * R);
        fillInk(g2, "#f7f6f2", 7);
        circle(g2, CX - 0.035 * R, by, 0.022 * R);
        g2.fillStyle = INK;
        g2.fill();
        circle(g2, CX + 0.035 * R, by, 0.022 * R);
        g2.fill();
      }
      for (const sd of [-1, 1]) {
        const px = CX + sd * 0.48 * R;
        begin(g2);
        g2.rect(px - 0.24 * R, BODY_T + 1.25 * R, 0.48 * R, 0.4 * R);
        fillInk(g2, shade(base, 0.95), 6);
        begin(g2);
        g2.rect(px - 0.26 * R, BODY_T + 1.2 * R, 0.52 * R, 0.13 * R);
        fillInk(g2, dark, 6);
        circle(g2, px, BODY_T + 1.3 * R, 8);
        fillInk(g2, "#d9a640", 3);
      }
      line(g2, [[CX - R, BODY_B - 70], [CX + R, BODY_B - 70]], 4, SEAM, [14, 10]);
    } else if (s.outfit === "hoodie") {
      begin(g2);
      g2.ellipse(CX, BODY_T + 0.05 * R, 0.7 * R, 0.2 * R, 0, 0, Math.PI * 2);
      fillInk(g2, dark, 7);
      for (const sd of [-1, 1]) line(g2, [[CX + sd * 0.15 * R, BODY_T + 0.15 * R], [CX + sd * 0.17 * R, BODY_T + 0.65 * R]], 7, "#f4f1ea");
      begin(g2);
      g2.moveTo(CX - 0.6 * R, BODY_T + 1.25 * R);
      g2.lineTo(CX + 0.6 * R, BODY_T + 1.25 * R);
      g2.lineTo(CX + 0.75 * R, BODY_T + 1.75 * R);
      g2.lineTo(CX - 0.75 * R, BODY_T + 1.75 * R);
      g2.closePath();
      fillInk(g2, shade(base, 0.92), 6);
    } else if (s.outfit === "dress") {
      begin(g2);
      g2.ellipse(CX, BODY_T + 0.1 * R, 0.4 * R, 0.16 * R, 0, 0, Math.PI * 2);
      fillInk(g2, s.shirt ?? "#ffffff", 6);
      for (let k2 = 0; k2 < 3; k2++) circle(g2, CX, BODY_T + (0.5 + 0.35 * k2) * R, 8), fillInk(g2, "#ffffff", 4);
      line(g2, [[CX - R, BODY_T + 1.3 * R], [CX + R, BODY_T + 1.3 * R]], 12, trim);
    }
    if (s.pattern) {
      const pc = s.patCol ?? shade(base, 1.35);
      if (s.pattern === "dots") for (let y = BODY_T + 20; y < BODY_B; y += 42) for (let x = CX - 1.1 * R + y / 42 % 2 * 21; x < CX + 1.1 * R; x += 42) {
        circle(g2, x, y, 7);
        g2.fillStyle = pc;
        g2.fill();
      }
      if (s.pattern === "stripes") for (let x = CX - 1.1 * R; x < CX + 1.1 * R; x += 46) line(g2, [[x, BODY_T - 20], [x + 10, BODY_B + 20]], 16, pc);
      if (s.pattern === "check") {
        for (let x = CX - 1.1 * R; x < CX + 1.1 * R; x += 70) line(g2, [[x, BODY_T - 20], [x, BODY_B + 20]], 10, pc);
        for (let y = BODY_T; y < BODY_B; y += 70) line(g2, [[CX - 1.2 * R, y], [CX + 1.2 * R, y]], 10, pc);
      }
    }
    if (s.suspenders) for (const sd of [-1, 1]) {
      const x02 = CX + sd * 0.42 * R;
      begin(g2);
      g2.moveTo(x02 - 22, BODY_T - 10);
      g2.lineTo(x02 + 22, BODY_T - 10);
      g2.lineTo(x02 + 22 + sd * 6, BODY_B);
      g2.lineTo(x02 - 22 + sd * 6, BODY_B);
      g2.closePath();
      fillInk(g2, s.suspenders, 5);
      line(g2, [[x02, BODY_T], [x02 + sd * 6, BODY_B]], 5, "rgba(255,255,255,0.8)", [14, 12]);
      begin(g2);
      g2.rect(x02 - 24, BODY_T + 0.55 * R, 48, 40);
      fillInk(g2, "#d9a640", 5);
      begin(g2);
      g2.rect(x02 - 12, BODY_T + 0.55 * R + 10, 24, 20);
      g2.fillStyle = shade("#d9a640", 0.6);
      g2.fill();
    }
    if (s.chain) {
      begin(g2);
      g2.moveTo(CX - 0.55 * R, BODY_T + 1.05 * R);
      g2.quadraticCurveTo(CX - 0.1 * R, BODY_T + 1.45 * R, CX + 0.45 * R, BODY_T + 1 * R);
      g2.lineWidth = 3;
      g2.strokeStyle = "rgba(0,0,0,0)";
      g2.stroke();
      for (let k2 = 0; k2 <= 14; k2++) {
        const u = k2 / 14, x = (1 - u) * (1 - u) * (CX - 0.55 * R) + 2 * u * (1 - u) * (CX - 0.1 * R) + u * u * (CX + 0.45 * R), y = (1 - u) * (1 - u) * (BODY_T + 1.05 * R) + 2 * u * (1 - u) * (BODY_T + 1.45 * R) + u * u * (BODY_T + 1 * R);
        begin(g2);
        g2.ellipse(x, y, 13, 9, k2 % 2 ? 0.6 : -0.6, 0, Math.PI * 2);
        g2.fillStyle = "#e8b84a";
        g2.fill();
        g2.lineWidth = 4;
        g2.strokeStyle = "#8a6420";
        g2.stroke();
      }
      circle(g2, CX + 0.45 * R, BODY_T + 1 * R, 16);
      fillInk(g2, "#e8b84a", 5);
    }
    if (s.neckerchief) {
      begin(g2);
      g2.moveTo(CX - 0.42 * R, BODY_T - 6);
      g2.lineTo(CX + 0.42 * R, BODY_T - 6);
      g2.lineTo(CX + 0.04 * R, BODY_T + 0.6 * R);
      g2.closePath();
      fillInk(g2, s.neckerchief, 7);
      for (const [dx, dy] of [[-0.2, 0.08], [0, 0.12], [0.2, 0.08], [-0.08, 0.28], [0.12, 0.28], [0.02, 0.44]]) {
        circle(g2, CX + dx * R, BODY_T + dy * R, 8);
        g2.fillStyle = "#ffffff";
        g2.fill();
      }
    }
    if (s.suspenders) for (const sd of [-1, 1]) {
      const x02 = CX + sd * 0.42 * R + sd * 6, hm = HEM;
      begin(g2);
      g2.rect(x02 - 24, hm - 56, 48, 40);
      fillInk(g2, "#d9a640", 5);
      begin(g2);
      g2.rect(x02 - 12, hm - 46, 24, 20);
      g2.fillStyle = shade("#d9a640", 0.6);
      g2.fill();
    }
    const x0 = CX - 1 * R, x1 = CX + 1 * R;
    const cyl = g2.createLinearGradient(x0, 0, x1, 0);
    cyl.addColorStop(0, "rgba(255,255,255,0.0)");
    cyl.addColorStop(0.18, "rgba(255,255,255,0.10)");
    cyl.addColorStop(0.42, "rgba(255,255,255,0)");
    cyl.addColorStop(0.7, "rgba(10,20,30,0.14)");
    cyl.addColorStop(1, "rgba(10,20,30,0.36)");
    g2.fillStyle = cyl;
    g2.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, HEM - BODY_T + 120);
    g2.save();
    bodyPath(g2);
    g2.lineWidth = 0.2 * R;
    g2.strokeStyle = "rgba(255,255,255,0.32)";
    const rimMask = g2.createLinearGradient(x0, 0, x0 + 0.5 * R, 0);
    rimMask.addColorStop(0, "rgba(255,255,255,0.34)");
    rimMask.addColorStop(0.55, "rgba(255,255,255,0.1)");
    rimMask.addColorStop(1, "rgba(255,255,255,0)");
    g2.strokeStyle = rimMask;
    g2.stroke();
    g2.restore();
    const vert = g2.createLinearGradient(0, BODY_T, 0, HEM);
    vert.addColorStop(0, "rgba(255,255,255,0.06)");
    vert.addColorStop(0.55, "rgba(255,255,255,0)");
    vert.addColorStop(1, "rgba(20,14,30,0.22)");
    g2.fillStyle = vert;
    g2.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, HEM - BODY_T + 120);
    const sh = g2.createLinearGradient(0, BODY_T, 0, BODY_T + 0.4 * R);
    sh.addColorStop(0, "rgba(30,24,40,0.34)");
    sh.addColorStop(1, "rgba(30,24,40,0)");
    g2.fillStyle = sh;
    g2.beginPath();
    g2.ellipse(CX + 0.05 * R, BODY_T, 0.9 * R, 0.4 * R, 0, 0, Math.PI * 2);
    g2.fill();
  });
  bodyPath(g2);
  inkStroke(g2, W_INK);
};
var headPath = (g2) => {
  begin(g2);
  g2.ellipse(CX, HY, R * 1.02, R, 0, 0, Math.PI * 2);
};
var keyLight = (g2, cx, cy, r, k2 = 1) => {
  const gr = g2.createRadialGradient(cx - 0.16 * r, cy - 0.3 * r, 0.05 * r, cx - 0.08 * r, cy - 0.12 * r, 1.12 * r);
  gr.addColorStop(0, "rgba(255,255,255,0)");
  gr.addColorStop(0.45, `rgba(92,84,100,${0.03 * k2})`);
  gr.addColorStop(0.8, `rgba(84,76,96,${0.13 * k2})`);
  gr.addColorStop(1, `rgba(72,64,88,${0.26 * k2})`);
  g2.fillStyle = gr;
  g2.fillRect(cx - 2 * r, cy - 2 * r, 4 * r, 4 * r);
};
var brimShadow = (g2, y) => {
  const gr = g2.createLinearGradient(0, y - 4, 0, y + 0.3 * R);
  gr.addColorStop(0, "rgba(40,30,40,0.32)");
  gr.addColorStop(1, "rgba(40,30,40,0)");
  g2.fillStyle = gr;
  g2.fillRect(CX - 1.2 * R, y - 4, 2.4 * R, 0.32 * R);
};
var brimY = (s) => s.hat === "capBack" || s.hat === "cap" ? HY - 0.22 * R : s.hat === "flatcap" ? HY - 0.22 * R : s.hat === "hardhat" ? HY - 0.25 * R : s.hat === "beanie" ? HY - 0.24 * R : s.hat === "bowler" ? HY - 0.55 * R : 0;
var head = (g2, s) => {
  const col = s.head ?? "#fbfaf7";
  headPath(g2);
  g2.fillStyle = col;
  g2.fill();
  withClip(g2, () => headPath(g2), () => {
    keyLight(g2, CX, HY, R);
    if (s.hat && s.hat !== "none") brimShadow(g2, brimY(s));
  });
  headPath(g2);
  inkStroke(g2, W_INK);
};
var hx = (p) => CX + p[0] * R;
var hy = (p) => HY + p[1] * R;
var smoothClosed = (g2, pts) => {
  const n = pts.length;
  g2.moveTo(hx(pts[0]), hy(pts[0]));
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    const k1 = p1[2] ? 0 : 1 / 6, k2 = p2[2] ? 0 : 1 / 6;
    g2.bezierCurveTo(hx(p1) + (hx(p2) - hx(p0)) * k1, hy(p1) + (hy(p2) - hy(p0)) * k1, hx(p2) - (hx(p3) - hx(p1)) * k2, hy(p2) - (hy(p3) - hy(p1)) * k2, hx(p2), hy(p2));
  }
  g2.closePath();
};
var smoothOpen = (g2, pts) => {
  g2.moveTo(hx(pts[0]), hy(pts[0]));
  if (pts.length === 2) {
    g2.lineTo(hx(pts[1]), hy(pts[1]));
    return;
  }
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (hx(pts[i]) + hx(pts[i + 1])) / 2, my = (hy(pts[i]) + hy(pts[i + 1])) / 2;
    g2.quadraticCurveTo(hx(pts[i]), hy(pts[i]), i === pts.length - 2 ? hx(pts[i + 1]) : mx, i === pts.length - 2 ? hy(pts[i + 1]) : my);
  }
};
var arcP = (a0, a1, grow = 0.07, n = 11) => Array.from({ length: n }, (_, i) => {
  const a = (a0 + (a1 - a0) * i / (n - 1)) * Math.PI / 180;
  return [(1.02 + grow) * Math.cos(a), (1 + grow) * Math.sin(a)];
});
var blob = (u, v, r, n = 8) => Array.from({ length: n }, (_, i) => {
  const a = i / n * Math.PI * 2;
  return [u + r * Math.cos(a), v + r * 0.94 * Math.sin(a)];
});
var lock = (phi, len, lean = 0, w = 10) => {
  const P2 = (a, r) => [1.02 * r * Math.cos(a * Math.PI / 180), r * Math.sin(a * Math.PI / 180)];
  const t = P2(phi + lean, len);
  return [P2(phi - w, 0.88), P2(phi - w * 0.35 + lean * 0.4, (0.9 + len) / 2 + 0.03), [t[0], t[1], 1], P2(phi + w * 0.45 + lean * 0.4, (0.9 + len) / 2 - 0.03), P2(phi + w, 0.88)];
};
var area = (pts) => pts.reduce((a, p, i) => {
  const q = pts[(i + 1) % pts.length];
  return a + p[0] * q[1] - q[0] * p[1];
}, 0);
var orient = (pts) => area(pts) < 0 ? [...pts].reverse() : pts;
var paintHair = (g2, shapes, c, strands = [], shine = 1) => {
  if (!shapes.length) return;
  const all = shapes.map(orient), union = () => {
    begin(g2);
    for (const sh of all) smoothClosed(g2, sh);
  };
  g2.save();
  g2.lineJoin = "round";
  g2.lineCap = "round";
  union();
  g2.lineWidth = 22;
  g2.strokeStyle = INK;
  g2.stroke();
  union();
  g2.fillStyle = c;
  g2.fill();
  withClip(g2, union, () => {
    const gr = g2.createLinearGradient(CX - 1.1 * R, HY - 1.15 * R, CX + 1.1 * R, HY + 0.5 * R);
    gr.addColorStop(0, "rgba(255,255,255,0.22)");
    gr.addColorStop(0.42, "rgba(255,255,255,0)");
    gr.addColorStop(1, "rgba(12,8,24,0.42)");
    g2.fillStyle = gr;
    g2.fillRect(CX - 2.5 * R, HY - 2.5 * R, 5 * R, 5 * R);
    for (const st of strands) {
      begin(g2);
      smoothOpen(g2, st);
      g2.lineWidth = 6;
      g2.strokeStyle = shade(c, 0.58);
      g2.stroke();
    }
    if (shine) for (const [a0, a1] of [[1.12, 1.32], [1.37, 1.46]]) {
      begin(g2);
      g2.ellipse(CX - 0.04 * R, HY - 0.02 * R, 0.84 * R, 0.84 * R, 0, Math.PI * a0, Math.PI * a1);
      g2.lineWidth = 0.075 * R;
      g2.strokeStyle = `rgba(255,255,255,${Math.min(0.6, 0.34 * shine)})`;
      g2.stroke();
    }
  });
  g2.restore();
};
var mirror = (pts) => [...pts].reverse().map((p) => p[2] ? [-p[0], p[1], 1] : [-p[0], p[1]]);
var scalpShine = (g2) => {
  begin(g2);
  g2.ellipse(CX - 0.36 * R, HY - 0.7 * R, 0.24 * R, 0.09 * R, -0.55, 0, Math.PI * 2);
  g2.fillStyle = "rgba(255,255,255,0.75)";
  g2.fill();
  circle(g2, CX - 0.08 * R, HY - 0.86 * R, 0.035 * R);
  g2.fill();
};
var hairLook = (s) => {
  const st = s.hair ?? "none", hatted = !!s.hat && s.hat !== "none", bv = hatted ? (brimY(s) - HY) / R : 0;
  const cap = (grow = 0.07) => arcP(172, 368, grow);
  const sideClumps = () => [1, -1].map((sd) => {
    const r = [[0.82, bv - 0.05], [1.1, bv - 0.04], [1.2, bv + 0.13, 1], [1.07, bv + 0.15], [1.13, bv + 0.31, 1], [0.99, bv + 0.27], [0.96, bv + 0.42, 1], [0.88, bv + 0.2]];
    return sd > 0 ? r : mirror(r);
  });
  const underFringe = () => ["flatcap", "beanie", "hardhat", "bowler"].includes(s.hat ?? "") ? [[[-0.52, bv - 0.03], [-0.34, bv + 0.26, 1], [-0.22, bv - 0.03]], [[-0.24, bv - 0.03], [-0.04, bv + 0.21, 1], [0.08, bv - 0.03]]] : [];
  const fluff = () => [blob(-1, -0.22, 0.17), blob(-1.04, 0.04, 0.15), blob(1, -0.22, 0.17), blob(1.04, 0.04, 0.15)];
  const combStrands = (g2, c) => {
    for (const [dv, du] of [[0, 0], [0.1, 0.05], [0.2, 0.1], [0.3, 0.12]]) {
      const pts = [[-0.92, -0.32 + dv * 0.3], [-0.55, -0.93 + dv], [0.1, -1 + dv], [0.58 + du, -0.68 + dv * 0.6]];
      for (const [w, col] of [[17, INK], [8, c]]) {
        begin(g2);
        smoothOpen(g2, pts);
        g2.lineWidth = w;
        g2.strokeStyle = col;
        g2.lineCap = "round";
        g2.stroke();
      }
    }
  };
  const mulletBack = [[-0.82, 0.2], [-0.98, 0.55], [-1, 0.8], [-1.16, 0.98, 1], [-0.88, 0.92], [-0.72, 1.04, 1], [-0.55, 0.84], [0.55, 0.84], [0.72, 1.04, 1], [0.88, 0.92], [1.16, 0.98, 1], [1, 0.8], [0.98, 0.55], [0.82, 0.2]];
  const bobBack = [[-1.2, 0.7, 1], ...arcP(178, 362, 0.15), [1.2, 0.7, 1], [0.9, 0.62], [0, 0.76], [-0.9, 0.62]];
  const curtain = (sd) => {
    const r = [[0.84, hatted ? bv : -0.2], [1.1, hatted ? bv : -0.1], [1.05, 0.52, 1], [0.9, 0.46]];
    return sd > 0 ? r : mirror(r);
  };
  const ponyBack = [[0.72, -0.82], [1.1, -0.78], [1.46, -0.36], [1.52, 0.2], [1.33, 0.78, 1], [1.24, 0.26], [1.05, -0.2], [0.8, -0.45]];
  const ponyStr = [[[1.02, -0.68], [1.33, -0.3], [1.38, 0.4]], [[0.95, -0.55], [1.18, -0.2], [1.27, 0.35]]];
  const tie = (x, y) => (g2) => {
    circle(g2, CX + x * R, HY + y * R, 0.085 * R);
    fillInk(g2, "#d8262e", 7);
  };
  if (hatted) {
    const back = st === "bob" ? [bobBack] : st === "ponytail" ? [ponyBack] : st === "mullet" ? [mulletBack] : [];
    if (st === "none") return { front: [] };
    if (st === "bald" || st === "combover") return { front: bv < -0.2 ? fluff() : [], shine: 0 };
    if (st === "curly" || st === "afro") return { front: [-1, 1].flatMap((sd) => [blob(sd * 1, bv + 0.1, 0.18), blob(sd * 1.04, bv + 0.36, 0.15)]), shine: 0 };
    if (st === "bob") return { back, front: [curtain(1), curtain(-1)], shine: 0 };
    return { back, backStrands: st === "ponytail" ? ponyStr : [], front: [...sideClumps(), ...["bun", "slick", "ponytail"].includes(st) ? [] : underFringe()], shine: 0, extra: st === "ponytail" ? tie(0.98, -0.66) : void 0 };
  }
  switch (st) {
    case "side":
      return {
        front: [
          [...cap(), [0.93, 0.12, 1], [0.92, -0.3], [0.72, -0.4], [0.55, -0.32, 1], [0.36, -0.5], [0.12, -0.42, 1], [-0.12, -0.58], [-0.4, -0.72, 1], [-0.62, -0.55], [-0.86, -0.28], [-0.93, 0.12, 1]],
          [[0.02, -1], [0.1, -1.18], [0.34, -1.32, 1], [0.26, -1.12], [0.2, -1]]
        ],
        strands: [[[-0.4, -0.72], [0, -0.88], [0.45, -0.75], [0.7, -0.5]], [[-0.25, -0.97], [0.2, -1], [0.62, -0.74]], [[-0.55, -0.62], [-0.78, -0.38]]]
      };
    case "quiff":
      return {
        front: [
          [...cap(), [0.93, 0.12, 1], [0.9, -0.35], [0.55, -0.6], [0.2, -0.66], [-0.3, -0.62], [-0.7, -0.45], [-0.92, 0.12, 1]],
          [[-0.68, -0.55], [-0.6, -1.05], [-0.18, -1.44], [0.45, -1.48], [0.86, -1.22], [0.95, -0.96, 1], [0.72, -1.06], [0.45, -0.86], [0.1, -0.72]]
        ],
        strands: [[[-0.48, -0.68], [-0.32, -1.18], [0.3, -1.37], [0.76, -1.16]], [[-0.15, -0.7], [0.05, -1.07], [0.52, -1.16]]],
        shine: 1.3
      };
    case "spiky":
      return {
        front: [
          [...cap(0.05), [0.93, 0.1, 1], [0.9, -0.3], [0.75, -0.42, 1], [0.55, -0.56, 1], [0.38, -0.36, 1], [0.18, -0.56, 1], [0, -0.34, 1], [-0.18, -0.56, 1], [-0.38, -0.36, 1], [-0.55, -0.56, 1], [-0.75, -0.4, 1], [-0.92, 0.1, 1]],
          ...[200, 222, 244, 266, 288, 310, 332].map((ph, i) => lock(ph, i % 2 ? 1.32 : 1.46, 7, 11))
        ],
        strands: [[[-0.3, -0.62], [-0.4, -0.95]], [[0.25, -0.62], [0.32, -0.95]]]
      };
    case "messy":
      return {
        front: [
          [...arcP(170, 370, 0.08), [0.95, 0.15, 1], [0.88, -0.2], [0.72, -0.3, 1], [0.6, -0.52], [0.44, -0.33, 1], [0.25, -0.54], [0.04, -0.31, 1], [-0.15, -0.52], [-0.38, -0.32, 1], [-0.55, -0.52], [-0.75, -0.3, 1], [-0.88, -0.15], [-0.95, 0.15, 1]],
          lock(212, 1.3, -14),
          lock(256, 1.28, 16, 9),
          lock(320, 1.24, 12, 9)
        ],
        strands: [[[-0.2, -0.95], [-0.25, -0.62]], [[0.25, -0.97], [0.32, -0.62]], [[0.62, -0.82], [0.7, -0.5]]]
      };
    case "curly":
      return {
        front: [
          [...arcP(170, 370, 0), [0.9, 0.05, 1], [0.8, -0.55], [-0.8, -0.55], [-0.9, 0.05, 1]],
          ...[165, 186, 207, 228, 249, 270, 291, 312, 333, 354, 375].map((a) => blob(1 * Math.cos(a * Math.PI / 180), 0.97 * Math.sin(a * Math.PI / 180), 0.25)),
          ...[-0.55, -0.2, 0.15, 0.5].map((u) => blob(u, -0.6, 0.2))
        ],
        strands: [
          ...[200, 240, 280, 320].map((a) => {
            const u = 0.85 * Math.cos(a * Math.PI / 180), v = 0.83 * Math.sin(a * Math.PI / 180);
            return [[u - 0.08, v + 0.02], [u, v - 0.08], [u + 0.09, v]];
          }),
          ...[-0.37, 0, 0.33].map((u) => [[u - 0.07, -0.55], [u, -0.63], [u + 0.07, -0.56]])
        ],
        shine: 0.8
      };
    case "afro":
      return {
        back: [blob(0, -0.45, 1.15, 12), ...Array.from({ length: 14 }, (_, i) => {
          const a = i / 14 * Math.PI * 2;
          return blob(1.18 * Math.cos(a), -0.45 + 1.1 * Math.sin(a), 0.3);
        })],
        front: [[...arcP(176, 364, 0), [0.92, 0.05, 1], [0.86, -0.42], [0.45, -0.6], [0, -0.64], [-0.45, -0.6], [-0.86, -0.42], [-0.92, 0.05, 1]], blob(-0.6, -0.55, 0.14), blob(-0.2, -0.63, 0.14), blob(0.2, -0.63, 0.14), blob(0.6, -0.55, 0.14)],
        backStrands: [[[-0.9, -1.2], [-0.8, -1.32], [-0.68, -1.22]], [[0.5, -1.4], [0.62, -1.5], [0.74, -1.38]], [[1.2, -0.6], [1.3, -0.5], [1.22, -0.38]], [[-1.3, -0.4], [-1.38, -0.28], [-1.28, -0.16]]],
        shine: 0.7
      };
    case "bob":
      return {
        back: [bobBack],
        backStrands: [[[-1.05, 0], [-1.1, 0.55]], [[1.05, 0], [1.1, 0.55]]],
        front: [[...arcP(176, 364, 0.08), [1.04, 0.5, 1], [0.9, 0.46], [0.86, -0.2], [0.62, -0.36], [0.42, -0.3, 1], [0.21, -0.37], [0, -0.3, 1], [-0.21, -0.37], [-0.42, -0.3, 1], [-0.62, -0.36], [-0.86, -0.2], [-0.9, 0.46], [-1.04, 0.5, 1]]],
        strands: [[[0.3, -0.98], [0.25, -0.42]], [[-0.3, -0.98], [-0.25, -0.42]], [[0.95, -0.2], [0.97, 0.42]], [[-0.95, -0.2], [-0.97, 0.42]]],
        shine: 1.2
      };
    case "ponytail":
      return {
        back: [ponyBack],
        backStrands: ponyStr,
        front: [[...arcP(184, 356, 0.06), [0.95, -0.1, 1], [0.86, -0.32], [0.5, -0.55], [0, -0.6], [-0.4, -0.52], [-0.75, -0.36], [-0.95, -0.1, 1]], [[-0.3, -0.62], [-0.12, -0.44], [0.02, -0.26, 1], [-0.05, -0.5], [-0.18, -0.66]]],
        strands: [[[-0.5, -0.55], [-0.2, -0.95], [0.5, -0.9]], [[0.2, -0.58], [0.5, -0.82], [0.85, -0.72]]],
        shine: 1.2,
        extra: tie(0.98, -0.66)
      };
    case "bun":
      return {
        front: [[...arcP(184, 356, 0.04), [0.95, -0.1, 1], [0.86, -0.32], [0.5, -0.55], [0.08, -0.6], [0, -0.5, 1], [-0.08, -0.6], [-0.5, -0.55], [-0.86, -0.32], [-0.95, -0.1, 1]], blob(0, -1.2, 0.33, 10)],
        strands: [[[-0.16, -1.22], [0, -1.38], [0.18, -1.22], [0.02, -1.1]], [[-0.5, -0.57], [-0.2, -0.98]], [[0.5, -0.57], [0.2, -0.98]]],
        shine: 1.2,
        extra: (g2) => {
          begin(g2);
          g2.ellipse(CX, HY - 0.93 * R, 0.2 * R, 0.06 * R, 0, 0, Math.PI * 2);
          fillInk(g2, "#d8262e", 6);
        }
      };
    case "mullet":
      return {
        back: [mulletBack],
        backStrands: [[[-1.05, 0.3], [-1.15, 0.9]], [[1.05, 0.3], [1.15, 0.9]]],
        front: [[...cap(0.07), [0.93, 0.15, 1], [0.88, -0.25], [0.66, -0.36, 1], [0.48, -0.55], [0.26, -0.38, 1], [0.05, -0.58], [-0.18, -0.38, 1], [-0.4, -0.58], [-0.62, -0.4, 1], [-0.86, -0.25], [-0.93, 0.15, 1]], lock(250, 1.24, 14, 9)],
        strands: [[[-0.3, -0.98], [-0.35, -0.65]], [[0.3, -0.98], [0.35, -0.65]]]
      };
    case "slick":
      return {
        front: [[...arcP(174, 366, 0.04), [0.92, 0.05, 1], [0.86, -0.35], [0.5, -0.55], [0.18, -0.6], [0, -0.42, 1], [-0.18, -0.6], [-0.5, -0.55], [-0.86, -0.35], [-0.92, 0.05, 1]]],
        strands: [[[-0.6, -0.55], [-0.56, -0.86], [-0.3, -1]], [[-0.25, -0.6], [-0.2, -0.9], [0.05, -1.03]], [[0.25, -0.6], [0.3, -0.9], [0.52, -0.96]], [[0.6, -0.52], [0.7, -0.76], [0.84, -0.76]]],
        shine: 1.6
      };
    case "tuft":
      return {
        front: [[...arcP(176, 364, 0.03), [0.95, 0.05, 1], [0.9, -0.4], [0.5, -0.52], [0, -0.55], [-0.5, -0.52], [-0.9, -0.4], [-0.95, 0.05, 1]], lock(262, 1.22, -12, 8)],
        strands: [[-0.5, -0.75], [-0.2, -0.82], [0.15, -0.82], [0.5, -0.75]].map(([u, v]) => [[u, v], [u + 0.03, v - 0.07]]),
        shine: 0.8
      };
    case "combover":
      return { front: fluff(), shine: 0, extra: (g2, c) => {
        scalpShine(g2);
        combStrands(g2, c);
      } };
    case "bald":
      return { front: fluff(), shine: 0, extra: (g2) => {
        scalpShine(g2);
        begin(g2);
        smoothOpen(g2, [[0.04, -0.99], [0, -1.16], [0.14, -1.26], [0.22, -1.14], [0.1, -1.1]]);
        g2.lineWidth = 6;
        g2.strokeStyle = INK;
        g2.stroke();
      } };
    default:
      return { front: [] };
  }
};
var hairColOf = (s) => s.hairCol ?? (s.hair === "bald" || s.hair === "combover" ? "#cfc8ba" : "#2a1c18");
var hairBack = (g2, s) => {
  const L = hairLook(s);
  if (L.back) paintHair(g2, L.back, hairColOf(s), L.backStrands, 0);
};
var hair = (g2, s) => {
  const L = hairLook(s), c = hairColOf(s);
  if (L.front.length) withClip(g2, () => headPath(g2), () => {
    for (const [dy, al] of [[0.24, 0.06], [0.19, 0.07], [0.14, 0.08], [0.1, 0.09], [0.07, 0.1]]) {
      g2.save();
      g2.translate(0.02 * R, dy * R);
      begin(g2);
      for (const sh of L.front) smoothClosed(g2, orient(sh));
      g2.fillStyle = `rgba(44,32,52,${al})`;
      g2.fill();
      g2.restore();
    }
  });
  paintHair(g2, L.front, c, L.strands, L.shine ?? 1);
  L.extra?.(g2, c);
};
var hat = (g2, s) => {
  const c = s.hatCol ?? "#d8262e", dark = shade(c, 0.75);
  if (!s.hat || s.hat === "none") return;
  const dome = (y0, extra = 1) => {
    begin(g2);
    g2.moveTo(CX - 1.05 * R, y0);
    g2.bezierCurveTo(CX - 1.05 * R, HY - 1.38 * R * extra, CX + 1.05 * R, HY - 1.38 * R * extra, CX + 1.05 * R, y0);
    g2.closePath();
  };
  if (s.hat === "capBack" || s.hat === "cap") {
    const y0 = HY - 0.22 * R;
    dome(y0);
    fillInk(g2, c, W_INK);
    withClip(g2, () => dome(y0), () => {
      for (const a of [-0.55, 0, 0.55]) line(g2, [[CX + a * 1.4 * R, y0 + 20], [CX + a * 0.3 * R, HY - 1.05 * R]], 5, dark);
    });
    circle(g2, CX, HY - 1.05 * R, 0.08 * R);
    fillInk(g2, c, 7);
    if (s.hat === "capBack") {
      begin(g2);
      g2.ellipse(CX, y0 - 0.02 * R, 0.24 * R, 0.13 * R, 0, Math.PI, 0);
      g2.closePath();
      fillInk(g2, "#5a3418", 7);
      line(g2, [[CX - 0.24 * R, y0 - 0.02 * R], [CX + 0.24 * R, y0 - 0.02 * R]], 8, dark);
    } else {
      begin(g2);
      g2.moveTo(CX - 1.08 * R, y0);
      g2.quadraticCurveTo(CX, y0 + 0.38 * R, CX + 1.12 * R, y0 - 0.06 * R);
      g2.quadraticCurveTo(CX, y0 + 0.12 * R, CX - 1.08 * R, y0);
      g2.closePath();
      fillInk(g2, dark, 8);
    }
  } else if (s.hat === "flatcap") {
    const y0 = HY - 0.3 * R;
    begin(g2);
    g2.moveTo(CX - 1.04 * R, y0 + 0.04 * R);
    g2.bezierCurveTo(CX - 1.02 * R, HY - 1.12 * R, CX + 0.9 * R, HY - 1.18 * R, CX + 1.06 * R, y0 - 0.06 * R);
    g2.quadraticCurveTo(CX, y0 + 0.02 * R, CX - 1.04 * R, y0 + 0.04 * R);
    g2.closePath();
    fillInk(g2, c, W_INK);
    withClip(g2, () => {
      begin(g2);
      g2.moveTo(CX - 1.04 * R, y0 + 0.04 * R);
      g2.bezierCurveTo(CX - 1.02 * R, HY - 1.12 * R, CX + 0.9 * R, HY - 1.18 * R, CX + 1.06 * R, y0 - 0.06 * R);
      g2.quadraticCurveTo(CX, y0 + 0.02 * R, CX - 1.04 * R, y0 + 0.04 * R);
      g2.closePath();
    }, () => {
      line(g2, [[CX - 0.9 * R, y0 - 0.3 * R], [CX + 0.95 * R, y0 - 0.42 * R]], 5, SEAM, [14, 10]);
      line(g2, [[CX - 0.2 * R, HY - 1 * R], [CX - 0.05 * R, y0 - 0.02 * R]], 5, dark);
    });
    begin(g2);
    g2.moveTo(CX - 0.98 * R, y0 + 0.02 * R);
    g2.quadraticCurveTo(CX - 0.1 * R, y0 + 0.26 * R, CX + 0.92 * R, y0 - 0.02 * R);
    g2.quadraticCurveTo(CX - 0.05 * R, y0 + 0.06 * R, CX - 0.98 * R, y0 + 0.02 * R);
    g2.closePath();
    fillInk(g2, dark, 8);
  } else if (s.hat === "hardhat") {
    dome(HY - 0.25 * R, 1.06);
    fillInk(g2, c, W_INK);
    line(g2, [[CX, HY - 1.15 * R], [CX, HY - 0.3 * R]], 16, shade(c, 1.15));
    begin(g2);
    g2.ellipse(CX, HY - 0.25 * R, 1.25 * R, 0.1 * R, 0, 0, Math.PI * 2);
    fillInk(g2, dark, 8);
  } else if (s.hat === "beanie") {
    dome(HY - 0.3 * R);
    fillInk(g2, c, W_INK);
    begin(g2);
    g2.rect(CX - 1.06 * R, HY - 0.48 * R, 2.12 * R, 0.24 * R);
    fillInk(g2, dark, 8);
    for (let k2 = -4; k2 <= 4; k2++) line(g2, [[CX + k2 * 0.22 * R, HY - 0.46 * R], [CX + k2 * 0.22 * R, HY - 0.27 * R]], 4, SEAM);
  } else if (s.hat === "bowler") {
    begin(g2);
    g2.ellipse(CX, HY - 0.62 * R, 0.8 * R, 0.55 * R, 0, Math.PI, 0);
    g2.closePath();
    fillInk(g2, c, W_INK);
    line(g2, [[CX - 0.8 * R, HY - 0.7 * R], [CX + 0.8 * R, HY - 0.7 * R]], 14, shade(c, 1.35));
    begin(g2);
    g2.ellipse(CX, HY - 0.6 * R, 1.12 * R, 0.12 * R, 0, 0, Math.PI * 2);
    fillInk(g2, c, 8);
  }
};
var hatPaint = (g2, s) => {
  if (!s.hat || s.hat === "none" || s.hat === "flatcap") return;
  const crown = () => {
    if (s.hat === "bowler") {
      begin(g2);
      g2.ellipse(CX, HY - 0.62 * R, 0.8 * R, 0.55 * R, 0, Math.PI, 0);
      g2.closePath();
    } else {
      begin(g2);
      g2.moveTo(CX - 1.05 * R, HY - 0.24 * R);
      g2.bezierCurveTo(CX - 1.05 * R, HY - 1.4 * R, CX + 1.05 * R, HY - 1.4 * R, CX + 1.05 * R, HY - 0.24 * R);
      g2.closePath();
    }
  };
  withClip(g2, crown, () => {
    if (s.hatPattern === "stripes") for (let k2 = -6; k2 <= 6; k2++) {
      begin(g2);
      g2.moveTo(CX + k2 * 0.17 * R, HY - 0.2 * R);
      g2.quadraticCurveTo(CX + k2 * 0.13 * R, HY - 0.8 * R, CX + k2 * 0.05 * R, HY - 1.3 * R);
      g2.lineWidth = 0.06 * R;
      g2.strokeStyle = "rgba(255,255,255,0.85)";
      g2.stroke();
    }
    const gr = g2.createRadialGradient(CX - 0.3 * R, HY - 1 * R, 0.05 * R, CX, HY - 0.6 * R, 1.1 * R);
    gr.addColorStop(0, "rgba(255,255,255,0.35)");
    gr.addColorStop(0.35, "rgba(255,255,255,0.05)");
    gr.addColorStop(0.75, "rgba(20,16,30,0.12)");
    gr.addColorStop(1, "rgba(20,16,30,0.35)");
    g2.fillStyle = gr;
    g2.fillRect(CX - 1.5 * R, HY - 1.6 * R, 3 * R, 1.6 * R);
    if (s.hatGloss) {
      begin(g2);
      g2.ellipse(CX - 0.32 * R, HY - 0.98 * R, 0.22 * R, 0.08 * R, -0.5, 0, Math.PI * 2);
      g2.fillStyle = "rgba(255,255,255,0.7)";
      g2.fill();
    }
  });
};
var taper = (g2, x0, y0, x1, y1, w, bend = 0) => {
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2 - bend, nx = -(y1 - y0), ny = x1 - x0, L = Math.hypot(nx, ny) || 1, ux = nx / L * w / 2, uy = ny / L * w / 2;
  begin(g2);
  g2.moveTo(x0, y0);
  g2.quadraticCurveTo(mx + ux, my + uy, x1, y1);
  g2.quadraticCurveTo(mx - ux, my - uy, x0, y0);
  g2.closePath();
  g2.fillStyle = INK;
  g2.fill();
};
var FUN = {
  neutral: { open: 0.14, low: 0, tilt: 0, es: 1, ps: 1, bY: 0, bIn: 0, arch: 0.03, asym: 0, mouth: "line", mo: 0 },
  deadpan: { open: 0.52, low: 0.12, tilt: 0, es: 1, ps: 0.9, bY: 0.05, bIn: 0, arch: 0, asym: 0, mouth: "flat", mo: 0 },
  worried: { open: 0.04, low: 0, tilt: -0.45, es: 1.06, ps: 0.8, bY: -0.05, bIn: 0.09, arch: 0.02, asym: 0, mouth: "wavy", mo: 0, drops: 1 },
  shock: { open: 0, low: 0, tilt: 0, es: 1.28, ps: 0.46, bY: -0.17, bIn: 0.03, arch: 0.07, asym: 0, mouth: "O", mo: 1 },
  grimace: { open: 0.08, low: 0.05, tilt: -0.2, es: 1.12, ps: 0.55, bY: -0.07, bIn: 0.07, arch: 0.02, asym: 0, mouth: "teeth", mo: 0, drops: 1 },
  smile: { open: 0.08, low: 0.38, tilt: 0, es: 1, ps: 1.05, bY: -0.04, bIn: 0, arch: 0.06, asym: 0, mouth: "grin", mo: 0.5, blush: true },
  smirk: { open: 0.42, low: 0.16, tilt: 0, es: 1, ps: 1, bY: 0, bIn: 0, arch: 0.03, asym: 0.09, mouth: "smirk", mo: 0 },
  angry: { open: 0.3, low: 0.08, tilt: 0.6, es: 1, ps: 0.8, bY: 0.05, bIn: -0.12, arch: -0.01, asym: 0, mouth: "growl", mo: 0 },
  talk: { open: 0.12, low: 0.05, tilt: 0, es: 1, ps: 1, bY: -0.03, bIn: 0.01, arch: 0.04, asym: 0, mouth: "O", mo: 0.6 },
  laugh: { open: 0, low: 0, tilt: 0, es: 1, ps: 1, happy: true, bY: -0.09, bIn: 0.02, arch: 0.07, asym: 0, mouth: "grin", mo: 1, blush: true },
  yell: { open: 0.02, low: 0.1, tilt: 0.45, es: 1.1, ps: 0.52, bY: 0.03, bIn: -0.14, arch: -0.02, asym: 0, mouth: "yell", mo: 1 },
  sad: { open: 0.28, low: 0, tilt: -0.55, es: 1.05, ps: 1.2, bY: -0.02, bIn: 0.11, arch: 0, asym: 0, mouth: "frown", mo: 0 },
  suspicious: { open: 0.55, low: 0.32, tilt: 0.1, es: 1, ps: 0.9, bY: 0.02, bIn: -0.04, arch: 0.01, asym: -0.08, mouth: "side", mo: 0, look: [0.75, 0] },
  smug: { open: 0.5, low: 0.12, tilt: -0.05, es: 1, ps: 1, bY: -0.02, bIn: 0.02, arch: 0.05, asym: 0.1, mouth: "smug", mo: 0, look: [-0.3, -0.2] },
  panic: { open: 0, low: 0, tilt: -0.3, es: 1.22, ps: 0.42, bY: -0.13, bIn: 0.1, arch: 0.03, asym: 0, mouth: "wavyOpen", mo: 1, drops: 3 },
  sleepy: { open: 0.72, low: 0.12, tilt: -0.1, es: 1, ps: 1, bY: 0.06, bIn: 0.02, arch: 0, asym: 0, mouth: "O", mo: 0.22 },
  cheeky: { open: 0.12, low: 0.32, tilt: 0, es: 1, ps: 1.05, wink: 1, bY: -0.04, bIn: 0, arch: 0.05, asym: 0.07, mouth: "tongue", mo: 0, blush: true }
};
var MOUTH_IN = "#5a1822";
var TONGUE = "#e8707e";
var BROW_PASS = [];
var browShape = (g2, x0, y0, x1, y1, w, bend, col, bushy, halo = 12) => {
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2 - bend, nx = -(y1 - y0), ny = x1 - x0, L = Math.hypot(nx, ny) || 1, ux = nx / L * w / 2, uy = ny / L * w / 2;
  const path = () => {
    begin(g2);
    g2.moveTo(x0 + ux * 0.6, y0 + uy * 0.6);
    g2.quadraticCurveTo(mx + ux, my + uy, x1, y1);
    g2.quadraticCurveTo(mx - ux, my - uy, x0 - ux * 0.6, y0 - uy * 0.6);
    g2.closePath();
  };
  if (halo > 0) {
    path();
    g2.lineJoin = "round";
    g2.lineWidth = halo;
    g2.strokeStyle = "#fbfaf7";
    g2.stroke();
  }
  path();
  g2.fillStyle = col;
  g2.fill();
  if (col !== INK) {
    g2.lineWidth = 4;
    g2.strokeStyle = INK;
    g2.stroke();
  }
  if (bushy) for (const t of [0.2, 0.45, 0.7]) {
    const bx = (1 - t) * (1 - t) * x0 + 2 * t * (1 - t) * mx + t * t * x1, by = (1 - t) * (1 - t) * y0 + 2 * t * (1 - t) * my + t * t * y1;
    line(g2, [[bx - ux * 0.6, by - uy * 0.6], [bx - ux * 1.3 + (x1 - x0) * 0.08, by - uy * 1.3 + (y1 - y0) * 0.08]], 7, col);
  }
};
var drop = (g2, x, y, k2 = 1) => {
  begin(g2);
  g2.moveTo(x, y - 0.16 * R * k2);
  g2.quadraticCurveTo(x + 0.11 * R * k2, y + 0.02 * R * k2, x, y + 0.06 * R * k2);
  g2.quadraticCurveTo(x - 0.11 * R * k2, y + 0.02 * R * k2, x, y - 0.16 * R * k2);
  fillInk(g2, "#9fd4ff", 6);
  circle(g2, x - 0.025 * R * k2, y - 0.01 * R * k2, 0.018 * R * k2);
  g2.fillStyle = "#ffffff";
  g2.fill();
};
var mouthFun = (g2, kind, mx, my, mw, o, s) => {
  const dimple = (x, y, sd) => line(g2, [[x, y - 0.03 * R], [x + sd * 0.015 * R, y + 0.02 * R]], 5);
  const filled = (path, inside, inkW = 7) => {
    path();
    g2.fillStyle = MOUTH_IN;
    g2.fill();
    withClip(g2, path, inside);
    path();
    inkStroke(g2, inkW);
  };
  const toothLines = (x0, x1, y0, y1, n) => {
    for (let i = 1; i < n; i++) {
      const x = x0 + (x1 - x0) * i / n;
      line(g2, [[x, y0], [x, y1]], 4);
    }
  };
  switch (kind) {
    case "line":
      taper(g2, mx - mw * 0.75, my, mx + mw * 0.75, my - 0.01 * R, 0.045 * R, -0.025 * R);
      break;
    case "flat":
      taper(g2, mx - mw * 0.6, my + 0.02 * R, mx + mw * 0.6, my + 0.02 * R, 0.04 * R, 0);
      break;
    case "frown":
      taper(g2, mx - mw * 0.8, my + 0.08 * R, mx + mw * 0.8, my + 0.08 * R, 0.05 * R, 0.09 * R);
      break;
    case "side":
      taper(g2, mx - mw * 0.1, my + 0.03 * R, mx + mw * 0.95, my + 0.05 * R, 0.04 * R, 0.01 * R);
      break;
    case "smirk":
      taper(g2, mx - mw * 0.55, my + 0.04 * R, mx + mw, my - 0.05 * R, 0.045 * R, -0.04 * R);
      dimple(mx + mw + 0.03 * R, my - 0.07 * R, 1);
      break;
    case "smug":
      taper(g2, mx - mw * 0.75, my - 0.01 * R, mx + mw * 1.05, my - 0.09 * R, 0.055 * R, -0.08 * R);
      dimple(mx + mw * 1.05 + 0.03 * R, my - 0.1 * R, 1);
      dimple(mx - mw * 0.75 - 0.03 * R, my - 0.02 * R, -1);
      break;
    case "wavy": {
      begin(g2);
      g2.moveTo(mx - mw, my + 0.05 * R);
      for (let i = 0; i < 4; i++) {
        const x0 = mx - mw + 2 * mw * i / 4, x1 = x0 + 2 * mw / 4;
        g2.quadraticCurveTo((x0 + x1) / 2, my + 0.05 * R + (i % 2 ? 0.045 : -0.045) * R, x1, my + 0.05 * R);
      }
      inkStroke(g2, 7);
      break;
    }
    case "grin": {
      const w = mw * (1 + 0.25 * o), top = my - 0.04 * R, bot = my + (0.08 + 0.24 * o) * R;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, top - 0.02 * R);
        g2.quadraticCurveTo(mx, top + 0.07 * R, mx + w, top - 0.02 * R);
        g2.quadraticCurveTo(mx + w * 0.92, bot, mx, bot);
        g2.quadraticCurveTo(mx - w * 0.92, bot, mx - w, top - 0.02 * R);
        g2.closePath();
      };
      filled(path, () => {
        begin(g2);
        g2.moveTo(mx - w, top - 0.1 * R);
        g2.lineTo(mx + w, top - 0.1 * R);
        g2.lineTo(mx + w, top + 0.03 * R);
        g2.quadraticCurveTo(mx, top + 0.13 * R, mx - w, top + 0.03 * R);
        g2.closePath();
        g2.fillStyle = "#ffffff";
        g2.fill();
        begin(g2);
        g2.moveTo(mx - w, top + 0.03 * R);
        g2.quadraticCurveTo(mx, top + 0.13 * R, mx + w, top + 0.03 * R);
        g2.lineWidth = 4;
        g2.strokeStyle = INK;
        g2.stroke();
        if (o > 0.3) {
          begin(g2);
          g2.ellipse(mx + 0.02 * R, bot + 0.01 * R, w * 0.55, (0.05 + 0.06 * o) * R, 0, 0, Math.PI * 2);
          g2.fillStyle = TONGUE;
          g2.fill();
        }
      });
      dimple(mx - w - 0.03 * R, top - 0.03 * R, -1);
      dimple(mx + w + 0.03 * R, top - 0.03 * R, 1);
      break;
    }
    case "O": {
      const rx = (0.055 + 0.045 * o) * R, ry = (0.035 + 0.14 * o) * R, cy = my + 0.03 * R + ry * 0.3;
      filled(() => {
        begin(g2);
        g2.ellipse(mx, cy, rx, ry, 0, 0, Math.PI * 2);
      }, () => {
        if (o > 0.3) {
          begin(g2);
          g2.ellipse(mx, cy + ry * 0.95, rx * 0.8, ry * 0.5, 0, 0, Math.PI * 2);
          g2.fillStyle = TONGUE;
          g2.fill();
        }
      });
      break;
    }
    case "yell": {
      const w = mw * 1.15, top = my - 0.06 * R, bot = my + 0.32 * R;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, top);
        g2.quadraticCurveTo(mx, top - 0.03 * R, mx + w, top);
        g2.quadraticCurveTo(mx + w * 0.95, bot, mx, bot);
        g2.quadraticCurveTo(mx - w * 0.95, bot, mx - w, top);
        g2.closePath();
      };
      filled(path, () => {
        g2.fillStyle = "#ffffff";
        g2.fillRect(mx - w, top - 0.05 * R, 2 * w, 0.11 * R);
        line(g2, [[mx - w, top + 0.06 * R], [mx + w, top + 0.06 * R]], 4);
        toothLines(mx - w, mx + w, top - 0.05 * R, top + 0.06 * R, 6);
        begin(g2);
        g2.ellipse(mx, bot - 0.01 * R, w * 0.62, 0.1 * R, 0, 0, Math.PI * 2);
        g2.fillStyle = TONGUE;
        g2.fill();
      }, 8);
      break;
    }
    case "teeth":
    case "wavyOpen": {
      const w = mw * 1.3, t0 = my - 0.06 * R, t1 = my + 0.14 * R, wav = kind === "wavyOpen" ? 0.03 * R : 0;
      const edge = (y, dir) => {
        const n = 5;
        for (let i = 1; i <= n; i++) {
          const x = mx - w * dir + 2 * w * dir * i / n;
          g2.lineTo(x, y + (i % 2 ? wav : -wav));
        }
      };
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, t0);
        edge(t0, 1);
        g2.lineTo(mx + w, t1);
        edge(t1, -1);
        g2.closePath();
      };
      path();
      g2.fillStyle = "#ffffff";
      g2.fill();
      withClip(g2, path, () => {
        line(g2, [[mx - w, (t0 + t1) / 2], [mx + w, (t0 + t1) / 2]], 5);
        toothLines(mx - w, mx + w, t0 - 0.05 * R, t1 + 0.05 * R, 6);
      });
      path();
      g2.lineJoin = "round";
      inkStroke(g2, 7);
      break;
    }
    case "growl": {
      const w = mw;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, my + 0.08 * R);
        g2.quadraticCurveTo(mx, my - 0.08 * R, mx + w, my + 0.08 * R);
        g2.lineTo(mx + w * 0.82, my + 0.16 * R);
        g2.quadraticCurveTo(mx, my + 0.05 * R, mx - w * 0.82, my + 0.16 * R);
        g2.closePath();
      };
      path();
      g2.fillStyle = "#ffffff";
      g2.fill();
      withClip(g2, path, () => {
        begin(g2);
        g2.moveTo(mx - w, my + 0.12 * R);
        g2.quadraticCurveTo(mx, my - 0.01 * R, mx + w, my + 0.12 * R);
        g2.lineWidth = 4;
        g2.strokeStyle = INK;
        g2.stroke();
        toothLines(mx - w, mx + w, my - 0.1 * R, my + 0.2 * R, 5);
      });
      path();
      inkStroke(g2, 7);
      break;
    }
    case "tongue": {
      begin(g2);
      g2.moveTo(mx - 0.055 * R, my - 0.01 * R);
      g2.lineTo(mx - 0.06 * R, my + 0.1 * R);
      g2.arc(mx, my + 0.1 * R, 0.06 * R, Math.PI, 0, true);
      g2.lineTo(mx + 0.055 * R, my - 0.01 * R);
      g2.closePath();
      fillInk(g2, TONGUE, 6);
      line(g2, [[mx, my + 0.02 * R], [mx, my + 0.1 * R]], 4, "rgba(120,20,40,0.6)");
      taper(g2, mx - mw, my - 0.04 * R, mx + mw, my - 0.04 * R, 0.05 * R, -0.07 * R);
      dimple(mx + mw + 0.03 * R, my - 0.06 * R, 1);
      break;
    }
  }
  if (s.teeth === "buck" && ["line", "flat", "smirk", "smug", "side", "frown", "tongue"].includes(kind)) {
    for (const sd of [-1, 1]) {
      begin(g2);
      g2.roundRect(mx + (sd < 0 ? -0.07 : 5e-3) * R, my + 0.01 * R, 0.065 * R, 0.09 * R, 0.015 * R);
      fillInk(g2, "#ffffff", 5);
    }
  }
};
var faceFun = (g2, s, p) => {
  const e = p.expr ?? "neutral", F = FUN[e] ?? FUN.neutral, yaw = p.yaw ?? 0, blink = p.blink ?? 0, skin = s.head ?? "#fbfaf7";
  const [lx, ly] = p.look ?? F.look ?? [0, 0], k2 = s.eyeScale ?? 1;
  const fx = CX + yaw * 0.34 * R, ey = HY + 0.1 * R, ew = 0.15 * R * k2, eh = 0.2 * R * k2, sp = 0.255 * R * Math.max(1, k2 * 0.95) * (1 - 0.12 * Math.abs(yaw));
  const hcN = parseInt(hairColOf(s).slice(1), 16), lum = (0.3 * (hcN >> 16 & 255) + 0.59 * (hcN >> 8 & 255) + 0.11 * (hcN & 255)) / 255;
  const bc = s.browCol ?? (s.hair && s.hair !== "none" && lum > 0.42 ? shade(hairColOf(s), 0.78) : INK);
  if (F.blush || s.cheeks) for (const sd of [-1, 1]) {
    const bx = fx + sd * 0.48 * R, by = ey + 0.32 * R, gr = g2.createRadialGradient(bx, by, 0, bx, by, 0.17 * R);
    gr.addColorStop(0, `rgba(255,105,120,${F.blush ? 0.45 : 0.3})`);
    gr.addColorStop(1, "rgba(255,105,120,0)");
    g2.save();
    g2.translate(bx, by);
    g2.scale(1, 0.55);
    g2.translate(-bx, -by);
    g2.fillStyle = gr;
    circle(g2, bx, by, 0.17 * R);
    g2.fill();
    g2.restore();
  }
  if (s.freckles) for (const sd of [-1, 1]) for (const [dx, dy] of [[0.36, 0.28], [0.45, 0.33], [0.53, 0.27], [0.43, 0.24]]) {
    circle(g2, fx + sd * dx * R, ey + dy * R, 0.014 * R);
    g2.fillStyle = "rgba(150,80,50,0.7)";
    g2.fill();
  }
  const inner = [];
  for (const sd of [-1, 1]) {
    const far = yaw !== 0 && Math.sign(yaw) !== sd, sq = far ? 0.82 : 1, x = fx + sd * sp * (far ? 0.86 : 1);
    const w = ew * F.es * sq, h = eh * F.es;
    if (blink >= 0.9 || F.happy || F.wink === sd) {
      begin(g2);
      if (F.happy || F.wink === sd) g2.arc(x, ey + 0.09 * R, w * 0.95, Math.PI * 1.15, Math.PI * 1.85);
      else g2.arc(x, ey - 0.04 * R, w * 0.95, Math.PI * 0.15, Math.PI * 0.85);
      g2.lineWidth = 0.05 * R;
      g2.strokeStyle = INK;
      g2.lineCap = "round";
      g2.stroke();
    } else {
      const eye = () => {
        begin(g2);
        g2.ellipse(x, ey, w, h, 0, 0, Math.PI * 2);
      };
      eye();
      g2.fillStyle = "#ffffff";
      g2.fill();
      withClip(g2, eye, () => {
        const pr = 0.088 * R * F.ps * sq * k2, px = x + lx * (w - pr) * 0.78, py = ey + ly * (h - pr) * 0.6 + 0.03 * R;
        if (s.iris) {
          circle(g2, px, py, pr * 1.55);
          g2.fillStyle = s.iris;
          g2.fill();
          circle(g2, px, py, pr * 1.55);
          g2.lineWidth = 3;
          g2.strokeStyle = "rgba(0,0,0,0.35)";
          g2.stroke();
        }
        circle(g2, px, py, pr);
        g2.fillStyle = INK;
        g2.fill();
        circle(g2, px - pr * 0.4 - 2, py - pr * 0.45, Math.max(4, pr * 0.38));
        g2.fillStyle = "#ffffff";
        g2.fill();
        circle(g2, px + pr * 0.42, py + pr * 0.42, Math.max(2.5, pr * 0.16));
        g2.fill();
        const sh = g2.createLinearGradient(0, ey - h, 0, ey - h * 0.25);
        sh.addColorStop(0, "rgba(40,30,60,0.24)");
        sh.addColorStop(1, "rgba(40,30,60,0)");
        g2.fillStyle = sh;
        g2.fillRect(x - w - 5, ey - h - 5, 2 * w + 10, h);
        const open = Math.max(F.open, blink);
        if (open > 0.02) {
          const yl = ey - h + 2 * h * open, ti = F.tilt * h * 0.55, xi2 = x - sd * w, xo2 = x + sd * w, yi2 = yl + ti, yo2 = yl - ti;
          begin(g2);
          g2.moveTo(xi2 - sd * 8, ey - h - 8);
          g2.lineTo(xo2 + sd * 8, ey - h - 8);
          g2.lineTo(xo2 + sd * 8, yo2);
          g2.lineTo(xi2 - sd * 8, yi2);
          g2.closePath();
          g2.fillStyle = skin;
          g2.fill();
          line(g2, [[xi2, yi2], [xo2, yo2]], 0.045 * R);
        }
        if (F.low > 0.02) {
          const yb = ey + h - 2 * h * F.low;
          begin(g2);
          g2.moveTo(x - w - 8, ey + h + 8);
          g2.lineTo(x - w - 8, yb + 0.05 * R);
          g2.quadraticCurveTo(x, yb - 0.07 * R, x + w + 8, yb + 0.05 * R);
          g2.lineTo(x + w + 8, ey + h + 8);
          g2.closePath();
          g2.fillStyle = skin;
          g2.fill();
          begin(g2);
          g2.moveTo(x - w, yb + 0.04 * R);
          g2.quadraticCurveTo(x, yb - 0.06 * R, x + w, yb + 0.04 * R);
          g2.lineWidth = 5;
          g2.strokeStyle = INK;
          g2.stroke();
        }
      });
      eye();
      inkStroke(g2, 8);
      if (s.lashes) for (let i = 0; i < 3; i++) {
        const a = -Math.PI / 2 + sd * (0.55 + i * 0.3);
        line(g2, [[x + Math.cos(a) * w, ey + Math.sin(a) * h], [x + Math.cos(a) * (w + 0.07 * R), ey + Math.sin(a) * (h + 0.06 * R)]], 6);
      }
      if (s.glasses) {
        const gr = Math.max(w, h) * 1.2;
        circle(g2, x, ey, gr);
        inkStroke(g2, 7);
        begin(g2);
        g2.arc(x, ey, gr * 0.78, Math.PI * 1.15, Math.PI * 1.4);
        g2.lineWidth = 6;
        g2.strokeStyle = "rgba(255,255,255,0.9)";
        g2.stroke();
      }
    }
    if (s.glasses && (blink >= 0.9 || F.happy || F.wink === sd)) {
      circle(g2, x, ey, Math.max(w, h) * 1.2);
      inkStroke(g2, 7);
    }
    const bw = s.brows === "thin" ? 0.05 * R : s.brows === "bushy" ? 0.12 * R : 0.09 * R;
    const by = ey - h - 0.09 * R + F.bY * R - (sd > 0 ? F.asym : -F.asym * 0.4) * R - (s.glasses ? 0.05 * R : 0);
    const xi = x - sd * 0.12 * R * sq, xo = x + sd * 0.18 * R * sq, yi = by - F.bIn * R, yo = by + 0.02 * R + F.bIn * 0.25 * R;
    BROW_PASS.push(() => browShape(g2, xi, yi, xo, yo, bw, (F.arch + 0.02) * R, bc, s.brows === "bushy"));
    inner.push([xi, yi]);
  }
  if (s.brows === "uni") BROW_PASS.push(() => line(g2, [inner[0], [(inner[0][0] + inner[1][0]) / 2, Math.min(inner[0][1], inner[1][1]) + 0.02 * R], inner[1]], 0.06 * R, bc));
  if (s.glasses) {
    const gr = eh * F.es * 1.2;
    line(g2, [[fx - sp + gr * 0.98, ey - 0.02 * R], [fx, ey - 0.06 * R], [fx + sp - gr * 0.98, ey - 0.02 * R]], 7);
  }
  const my = HY + 0.57 * R, mx = fx + yaw * 0.06 * R, mw = 0.17 * R * (s.mouthW ?? 1);
  mouthFun(g2, F.mouth, mx, my, mw, e === "talk" ? p.mouth ?? F.mo : F.mo, s);
  if (s.mustache) {
    const ty = my - 0.06 * R - (F.mouth === "yell" || F.mo > 0.7 ? 0.04 * R : 0);
    begin(g2);
    g2.moveTo(mx - 0.26 * R, ty + 0.02 * R);
    g2.quadraticCurveTo(mx - 0.12 * R, ty - 0.17 * R, mx, ty - 0.08 * R);
    g2.quadraticCurveTo(mx + 0.12 * R, ty - 0.17 * R, mx + 0.26 * R, ty + 0.02 * R);
    g2.quadraticCurveTo(mx + 0.1 * R, ty - 0.02 * R, mx, ty - 0.04 * R);
    g2.quadraticCurveTo(mx - 0.1 * R, ty - 0.02 * R, mx - 0.26 * R, ty + 0.02 * R);
    g2.closePath();
    fillInk(g2, s.mustache, 6);
  }
  const nx = fx + yaw * 0.12 * R, ny = ey + 0.28 * R;
  if (s.nose === "button" || s.nose === "bulb") {
    const big = s.nose === "bulb", rx = (big ? 0.13 : 0.075) * R, ry = (big ? 0.105 : 0.058) * R;
    begin(g2);
    g2.ellipse(nx, ny + (big ? 0.03 * R : 0), rx, ry, 0, 0, Math.PI * 2);
    fillInk(g2, big ? "#f2b4a6" : shade(skin, 0.93), 6);
    begin(g2);
    g2.ellipse(nx - rx * 0.35, ny + (big ? 0.03 * R : 0) - ry * 0.35, rx * 0.3, ry * 0.22, -0.4, 0, Math.PI * 2);
    g2.fillStyle = "rgba(255,255,255,0.75)";
    g2.fill();
  }
  const drops = p.sweat ? Math.max(1, F.drops ?? 1) : (F.drops ?? 0) > 1 ? F.drops ?? 0 : 0;
  [[0.86, -0.5, 1], [-0.9, -0.36, 0.8], [0.97, -0.12, 0.7]].slice(0, drops).forEach(([u, v, kk]) => drop(g2, CX + u * R, HY + v * R, kk));
};
var ANIME = {
  neutral: { eye: "normal", open: 0, tilt: 0, low: 0, ps: 1, bY: 0, bIn: 0, asym: 0, arch: 0.02, mouth: "small", mo: 0 },
  smile: { eye: "arc", open: 0, tilt: 0, low: 0, ps: 1, bY: -0.03, bIn: 0, asym: 0, arch: 0.04, mouth: "openSmall", mo: 0.6, blush: true },
  laugh: { eye: "gt", open: 0, tilt: 0, low: 0, ps: 1, bY: -0.06, bIn: 0.03, asym: 0, arch: 0.04, mouth: "openBig", mo: 1, blush: true },
  cheeky: { eye: "normal", open: 0.05, tilt: 0, low: 0.15, ps: 1, wink: 1, bY: -0.03, bIn: 0, asym: 0.06, arch: 0.04, mouth: "tongue", mo: 0, blush: true, sparkle: true },
  smug: { eye: "normal", open: 0.48, tilt: -0.1, low: 0.12, ps: 0.9, bY: -0.02, bIn: 0.02, asym: 0.08, arch: 0.04, mouth: "cat", mo: 0, blush: true, look: [-0.4, 0] },
  smirk: { eye: "normal", open: 0.34, tilt: 0.1, low: 0.08, ps: 0.9, bY: 0, bIn: -0.02, asym: 0.1, arch: 0.03, mouth: "smirkFang", mo: 0 },
  talk: { eye: "normal", open: 0.05, tilt: 0, low: 0, ps: 1, bY: -0.02, bIn: 0.01, asym: 0, arch: 0.03, mouth: "openSmall", mo: 0.6 },
  suspicious: { eye: "normal", open: 0.46, tilt: 0.12, low: 0.3, ps: 0.82, bY: 0.02, bIn: -0.04, asym: -0.08, arch: 0.01, mouth: "flat", mo: 0, look: [0.85, 0] },
  deadpan: { eye: "dot", open: 0, tilt: 0, low: 0, ps: 1, bY: 0.03, bIn: 0, asym: 0, arch: 0, mouth: "flat", mo: 0 },
  sleepy: { eye: "line", open: 0, tilt: 0, low: 0, ps: 1, bY: 0.04, bIn: 0.02, asym: 0, arch: 0, mouth: "tri", mo: 0, bubble: true },
  worried: { eye: "normal", open: 0.02, tilt: -0.4, low: 0, ps: 1.08, bY: -0.05, bIn: 0.09, asym: 0, arch: 0.02, mouth: "wavy", mo: 0, sweat: 1 },
  sad: { eye: "normal", open: 0.1, tilt: -0.55, low: 0, ps: 1.04, pool: true, bY: -0.03, bIn: 0.11, asym: 0, arch: 0, mouth: "wavyOpen", mo: 0.5, tears: true },
  cry: { eye: "T", open: 0, tilt: 0, low: 0, ps: 1, bY: -0.02, bIn: 0.1, asym: 0, arch: 0, mouth: "wavyOpen", mo: 0.6, tears: true },
  grimace: { eye: "normal", open: 0, tilt: -0.2, low: 0, ps: 1, es: 1.08, pin: true, bY: -0.05, bIn: 0.06, asym: 0, arch: 0.02, mouth: "sharkClosed", mo: 0, gloom: true, sweat: 1 },
  panic: { eye: "normal", open: 0, tilt: -0.3, low: 0, ps: 0.4, es: 1.12, shake: true, bY: -0.12, bIn: 0.08, asym: 0, arch: 0.03, mouth: "wavyOpen", mo: 1, sweat: 3 },
  dizzy: { eye: "spiral", open: 0, tilt: 0, low: 0, ps: 1, bY: -0.06, bIn: 0.04, asym: 0, arch: 0.03, mouth: "wavyOpen", mo: 0.6 },
  shock: { eye: "normal", open: 0, tilt: 0, low: 0, ps: 1, es: 1.15, pin: true, bY: -0.16, bIn: 0.02, asym: 0, arch: 0.06, mouth: "jaw", mo: 1, pale: true },
  angry: { eye: "normal", open: 0.26, tilt: 0.65, low: 0.05, ps: 0.68, bY: 0.04, bIn: -0.12, asym: 0, arch: -0.01, mouth: "sharkClosed", mo: 0, vein: true },
  yell: { eye: "rage", open: 0, tilt: 0, low: 0, ps: 1, bY: 0.03, bIn: -0.14, asym: 0, arch: -0.02, mouth: "shark", mo: 1, vein: true },
  excited: { eye: "normal", open: 0, tilt: 0, low: 0, ps: 1.08, es: 1.08, stars: true, bY: -0.08, bIn: 0.02, asym: 0, arch: 0.05, mouth: "openBig", mo: 0.8, blush: true, sparkle: true },
  love: { eye: "heart", open: 0, tilt: 0, low: 0, ps: 1, bY: -0.05, bIn: 0.04, asym: 0, arch: 0.04, mouth: "cat", mo: 0, blush: true }
};
var veinMark = (g2, cx, cy, k2 = 1) => {
  for (const [a, b] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    for (const [w, col] of [[0.06 * R * k2, "#fbfaf7"], [0.035 * R * k2, "#e02838"]]) {
      begin(g2);
      g2.moveTo(cx + a * 0.045 * R * k2, cy + b * 0.14 * R * k2);
      g2.quadraticCurveTo(cx + a * 0.045 * R * k2, cy + b * 0.045 * R * k2, cx + a * 0.14 * R * k2, cy + b * 0.045 * R * k2);
      g2.lineWidth = w;
      g2.strokeStyle = col;
      g2.lineCap = "round";
      g2.stroke();
    }
  }
};
var sparkleMark = (g2, x, y, r) => {
  begin(g2);
  g2.moveTo(x, y - r);
  g2.quadraticCurveTo(x, y, x + r, y);
  g2.quadraticCurveTo(x, y, x, y + r);
  g2.quadraticCurveTo(x, y, x - r, y);
  g2.quadraticCurveTo(x, y, x, y - r);
  g2.closePath();
  g2.fillStyle = "#fff6b0";
  g2.fill();
  g2.lineWidth = 4;
  g2.strokeStyle = "#e8b020";
  g2.stroke();
};
var mouthAnime = (g2, kind, mx, my, o) => {
  const fillMouth = (path, inside, w = 6) => {
    path();
    g2.fillStyle = MOUTH_IN;
    g2.fill();
    if (inside) withClip(g2, path, inside);
    path();
    g2.lineJoin = "round";
    inkStroke(g2, w);
  };
  const tongue = (x, y, rx, ry) => {
    begin(g2);
    g2.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    g2.fillStyle = TONGUE;
    g2.fill();
  };
  switch (kind) {
    case "small":
      taper(g2, mx - 0.07 * R, my, mx + 0.07 * R, my, 0.028 * R, -0.012 * R);
      break;
    case "flat":
      line(g2, [[mx - 0.06 * R, my + 0.01 * R], [mx + 0.06 * R, my + 0.01 * R]], 0.025 * R);
      break;
    case "cat":
    case "tongue": {
      if (kind === "tongue") {
        begin(g2);
        g2.moveTo(mx - 0.03 * R, my + 0.02 * R);
        g2.lineTo(mx - 0.035 * R, my + 0.09 * R);
        g2.arc(mx + 5e-3 * R, my + 0.09 * R, 0.04 * R, Math.PI, 0, true);
        g2.lineTo(mx + 0.04 * R, my + 0.02 * R);
        g2.closePath();
        fillInk(g2, TONGUE, 5);
      }
      begin(g2);
      g2.moveTo(mx - 0.11 * R, my - 0.02 * R);
      g2.quadraticCurveTo(mx - 0.055 * R, my + 0.07 * R, mx, my);
      g2.quadraticCurveTo(mx + 0.055 * R, my + 0.07 * R, mx + 0.11 * R, my - 0.02 * R);
      inkStroke(g2, 7);
      break;
    }
    case "smirkFang": {
      taper(g2, mx - 0.06 * R, my + 0.02 * R, mx + 0.12 * R, my - 0.05 * R, 0.03 * R, -0.03 * R);
      begin(g2);
      g2.moveTo(mx + 0.035 * R, my - 5e-3 * R);
      g2.lineTo(mx + 0.075 * R, my - 0.02 * R);
      g2.lineTo(mx + 0.06 * R, my + 0.05 * R);
      g2.closePath();
      fillInk(g2, "#ffffff", 4);
      break;
    }
    case "openSmall":
    case "openBig": {
      const big = kind === "openBig", w = (big ? 0.15 : 0.06 + 0.04 * o) * R, d = (big ? 0.3 : 0.06 + 0.12 * o) * R, top = my - 0.03 * R;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, top);
        g2.quadraticCurveTo(mx, top + 0.025 * R, mx + w, top);
        g2.quadraticCurveTo(mx + w * 0.85, top + d * 1.35, mx, top + d);
        g2.quadraticCurveTo(mx - w * 0.85, top + d * 1.35, mx - w, top);
        g2.closePath();
      };
      fillMouth(path, () => tongue(mx + 0.01 * R, top + d * 1, w * 0.62, d * 0.38));
      break;
    }
    case "tri": {
      begin(g2);
      g2.moveTo(mx - 0.035 * R, my + 0.04 * R);
      g2.lineTo(mx + 0.035 * R, my + 0.04 * R);
      g2.lineTo(mx, my - 0.025 * R);
      g2.closePath();
      g2.fillStyle = MOUTH_IN;
      g2.fill();
      g2.lineJoin = "round";
      inkStroke(g2, 5);
      break;
    }
    case "jaw": {
      const path = () => {
        begin(g2);
        g2.moveTo(mx - 0.085 * R, my - 0.04 * R);
        g2.quadraticCurveTo(mx, my - 0.07 * R, mx + 0.085 * R, my - 0.04 * R);
        g2.lineTo(mx + 0.13 * R, HY + 0.86 * R);
        g2.quadraticCurveTo(mx, HY + 1.02 * R, mx - 0.13 * R, HY + 0.86 * R);
        g2.closePath();
      };
      fillMouth(path, () => tongue(mx, HY + 0.92 * R, 0.1 * R, 0.07 * R), 7);
      break;
    }
    case "shark": {
      const w = 0.21 * R, top = my - 0.08 * R, bot = my + 0.26 * R;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, top);
        g2.quadraticCurveTo(mx, top - 0.04 * R, mx + w, top);
        g2.quadraticCurveTo(mx + w * 0.9, bot, mx, bot);
        g2.quadraticCurveTo(mx - w * 0.9, bot, mx - w, top);
        g2.closePath();
      };
      fillMouth(path, () => {
        tongue(mx, bot, w * 0.6, 0.09 * R);
        for (const [y0, dir] of [[top - 0.03 * R, 1], [bot + 0.02 * R, -1]]) {
          begin(g2);
          g2.moveTo(mx - w, y0);
          const n = 7;
          for (let i = 0; i < n; i++) {
            const xa = mx - w + 2 * w * i / n;
            g2.lineTo(xa + w / n, y0 + dir * 0.09 * R);
            g2.lineTo(xa + 2 * w / n, y0);
          }
          g2.closePath();
          g2.fillStyle = "#ffffff";
          g2.fill();
          g2.lineWidth = 3;
          g2.strokeStyle = INK;
          g2.stroke();
        }
      }, 8);
      break;
    }
    case "sharkClosed": {
      const path = () => {
        begin(g2);
        g2.roundRect(mx - 0.15 * R, my - 0.045 * R, 0.3 * R, 0.11 * R, 0.035 * R);
      };
      path();
      g2.fillStyle = "#ffffff";
      g2.fill();
      withClip(g2, path, () => {
        begin(g2);
        g2.moveTo(mx - 0.16 * R, my + 0.01 * R);
        for (let i = 0; i < 8; i++) g2.lineTo(mx - 0.15 * R + 0.3 * R * (i + 0.5) / 8, my + (i % 2 ? 0.05 : -0.035) * R);
        g2.lineWidth = 4;
        g2.strokeStyle = INK;
        g2.stroke();
      });
      path();
      inkStroke(g2, 6);
      break;
    }
    case "wavy": {
      begin(g2);
      g2.moveTo(mx - 0.1 * R, my + 0.01 * R);
      for (let i = 0; i < 4; i++) {
        const x0 = mx - 0.1 * R + 0.2 * R * i / 4, x1 = x0 + 0.05 * R;
        g2.quadraticCurveTo((x0 + x1) / 2, my + 0.01 * R + (i % 2 ? 0.03 : -0.03) * R, x1, my + 0.01 * R);
      }
      inkStroke(g2, 6);
      break;
    }
    case "wavyOpen": {
      const w = (0.08 + 0.05 * o) * R, t0 = my - 0.03 * R, t1 = my + (0.06 + 0.1 * o) * R, wav = 0.018 * R;
      const path = () => {
        begin(g2);
        g2.moveTo(mx - w, t0);
        for (let i = 1; i <= 4; i++) g2.quadraticCurveTo(mx - w + 2 * w * (i - 0.5) / 4, t0 + (i % 2 ? -wav : wav) * 2, mx - w + 2 * w * i / 4, t0);
        g2.quadraticCurveTo(mx + w * 1.05, (t0 + t1) / 2, mx + w * 0.8, t1);
        for (let i = 1; i <= 3; i++) g2.quadraticCurveTo(mx + w * 0.8 - 1.6 * w * (i - 0.5) / 3, t1 + (i % 2 ? wav : -wav) * 2, mx + w * 0.8 - 1.6 * w * i / 3, t1);
        g2.quadraticCurveTo(mx - w * 1.05, (t0 + t1) / 2, mx - w, t0);
        g2.closePath();
      };
      fillMouth(path, () => tongue(mx, t1, w * 0.5, 0.04 * R));
      break;
    }
  }
};
var faceAnime = (g2, s, p) => {
  const e = p.expr ?? "neutral", A = ANIME[e] ?? ANIME.neutral, yaw = p.yaw ?? 0, blink = p.blink ?? 0, skin = s.head ?? "#fbfaf7";
  const [lx, ly] = p.look ?? A.look ?? [0, 0], k2 = s.eyeScale ?? 1, iris = s.iris ?? "#7a4a2a";
  const fx = CX + yaw * 0.34 * R, ey = HY + 0.13 * R, sp = 0.33 * R * (1 - 0.12 * Math.abs(yaw));
  const hcN = parseInt(hairColOf(s).slice(1), 16), lum = (0.3 * (hcN >> 16 & 255) + 0.59 * (hcN >> 8 & 255) + 0.11 * (hcN & 255)) / 255;
  const bc = s.browCol ?? (s.hair && s.hair !== "none" && lum > 0.42 ? shade(hairColOf(s), 0.78) : INK);
  if (A.pale || A.gloom) withClip(g2, () => headPath(g2), () => {
    const c0 = A.gloom ? "70,50,130" : "90,130,220", gr = g2.createLinearGradient(0, HY - 0.6 * R, 0, ey + 0.12 * R);
    gr.addColorStop(0, `rgba(${c0},0)`);
    gr.addColorStop(0.4, `rgba(${c0},0.42)`);
    gr.addColorStop(1, `rgba(${c0},0)`);
    g2.fillStyle = gr;
    g2.fillRect(CX - 1.2 * R, HY - 0.6 * R, 2.4 * R, 0.9 * R);
    if (A.gloom) for (let x = CX - 0.7 * R; x <= CX + 0.7 * R; x += 0.09 * R) line(g2, [[x, HY - R], [x, HY - 0.25 * R + Math.sin(x) * 0.05 * R]], 4, "rgba(60,40,120,0.55)");
  });
  if (A.blush || s.cheeks) for (const sd of [-1, 1]) {
    const bx = fx + sd * 0.5 * R, by = ey + 0.26 * R, gr = g2.createRadialGradient(bx, by, 0, bx, by, 0.16 * R);
    gr.addColorStop(0, "rgba(255,110,130,0.5)");
    gr.addColorStop(1, "rgba(255,110,130,0)");
    g2.save();
    g2.translate(bx, by);
    g2.scale(1, 0.5);
    g2.translate(-bx, -by);
    g2.fillStyle = gr;
    circle(g2, bx, by, 0.16 * R);
    g2.fill();
    g2.restore();
    if (A.blush) for (let i = -1; i <= 1; i++) line(g2, [[bx + i * 0.06 * R - 0.025 * R, by + 0.035 * R], [bx + i * 0.06 * R + 0.025 * R, by - 0.035 * R]], 5, "rgba(220,60,90,0.85)");
  }
  if (s.freckles) for (const sd of [-1, 1]) for (const [dx, dy] of [[0.4, 0.24], [0.48, 0.29], [0.56, 0.23], [0.47, 0.2]]) {
    circle(g2, fx + sd * dx * R, ey + dy * R, 0.013 * R);
    g2.fillStyle = "rgba(150,80,50,0.7)";
    g2.fill();
  }
  const inner = [];
  for (const sd of [-1, 1]) {
    const far = yaw !== 0 && Math.sign(yaw) !== sd, sq = (far ? 0.82 : 1) * k2, x = fx + sd * sp * (far ? 0.86 : 1);
    const w = 0.2 * R * sq, I = [x - sd * w, ey + 0.03 * R], O = [x + sd * w * 1.05, ey - 0.06 * R];
    const Cu = [x + sd * 0.02 * R, ey - 0.4 * R * k2], Cl = [x + sd * 0.02 * R, ey + 0.3 * R * k2];
    const mode = blink >= 0.9 ? "line" : A.wink === sd ? "arc" : A.eye;
    const thick = 0.05 * R * Math.min(1, k2 + 0.1);
    if (mode === "normal") {
      const es = (A.es ?? 1) * k2, W = 0.17 * R * sq * es, Yt = ey - 0.2 * R * es, Yb = ey + 0.15 * R * es;
      const op = Math.max(A.open, blink * 0.9), d = op * 0.24 * R * es, ti = A.tilt * 0.06 * R;
      const P = (u, v) => [x + sd * u, v];
      const T0i = P(-W * 0.98, Yt + 0.085 * R), T0o = P(W, Yt + 0.05 * R), C0 = P(0.02 * R, Yt - 0.01 * R);
      const BO = P(W * 0.55, Yb), BI = P(-W * 0.6, Yb - 0.01 * R);
      const open = () => {
        begin(g2);
        g2.moveTo(T0i[0], T0i[1]);
        g2.quadraticCurveTo(C0[0], C0[1], T0o[0], T0o[1]);
        const q = P(W * 1.12, ey + 0.02 * R);
        g2.quadraticCurveTo(q[0], q[1], BO[0], BO[1]);
        g2.quadraticCurveTo(x, Yb + 0.035 * R, BI[0], BI[1]);
        const r = P(-W * 1.04, ey + 0.02 * R);
        g2.quadraticCurveTo(r[0], r[1], T0i[0], T0i[1]);
        g2.closePath();
      };
      const TIb = P(-W * 0.98, Yt + 0.085 * R + d + ti), TOb = P(W, Yt + 0.05 * R + d - ti), Cb = P(0.02 * R, Yt - 0.01 * R + d * 1.3);
      const TIt = P(-W * 1.03, Yt + 0.05 * R + d + ti), TOt = P(W * 1.1, Yt - 8e-3 * R + d - ti), Ct = P(0.02 * R, Yt - 0.08 * R + d * 1.3), tail = P(W * 1.1 + 0.055 * R, Yt + 0.08 * R + d - ti);
      const ix = x + sd * 5e-3 * R + lx * 0.065 * R * sq, iy = ey - 5e-3 * R + ly * 0.045 * R, irx = 0.125 * R * sq * A.ps * es, iry = 0.18 * R * A.ps * es;
      const yb2 = Yb + 0.01 * R - (Yb - Yt) * 0.55 * A.low;
      const below = () => {
        begin(g2);
        g2.moveTo(TIb[0] - sd * 0.2 * R, TIb[1]);
        g2.lineTo(TIb[0], TIb[1]);
        g2.quadraticCurveTo(Cb[0], Cb[1], TOb[0], TOb[1]);
        g2.lineTo(TOb[0] + sd * 0.2 * R, TOb[1]);
        g2.lineTo(TOb[0] + sd * 0.2 * R, Yb + 0.3 * R);
        g2.lineTo(TIb[0] - sd * 0.2 * R, Yb + 0.3 * R);
        g2.closePath();
      };
      const above = () => {
        begin(g2);
        g2.moveTo(x - 0.4 * R, Yt - 0.4 * R);
        g2.lineTo(x - 0.4 * R, yb2 + 0.03 * R);
        g2.quadraticCurveTo(x, yb2 - 0.06 * R, x + 0.4 * R, yb2 + 0.03 * R);
        g2.lineTo(x + 0.4 * R, Yt - 0.4 * R);
        g2.closePath();
      };
      g2.save();
      open();
      g2.clip();
      below();
      g2.clip();
      if (A.low > 0.02) {
        above();
        g2.clip();
      }
      {
        g2.fillStyle = "#ffffff";
        g2.fillRect(x - 0.5 * R, Yt - 0.5 * R, R, R);
        if (A.pin) {
          circle(g2, ix, iy + 0.01 * R, 0.032 * R * es);
          g2.fillStyle = INK;
          g2.fill();
        } else {
          const gr = g2.createLinearGradient(0, iy - iry, 0, iy + iry);
          gr.addColorStop(0, shade(iris, 0.22));
          gr.addColorStop(0.45, iris);
          gr.addColorStop(1, shade(iris, 1.5));
          begin(g2);
          g2.ellipse(ix, iy, irx, iry, 0, 0, Math.PI * 2);
          g2.fillStyle = gr;
          g2.fill();
          g2.lineWidth = 0.014 * R;
          g2.strokeStyle = shade(iris, 0.2);
          g2.stroke();
          begin(g2);
          g2.ellipse(ix, iy + 0.01 * R, irx * 0.46, iry * 0.52, 0, 0, Math.PI * 2);
          g2.fillStyle = shade(iris, 0.1);
          g2.fill();
          begin(g2);
          g2.ellipse(ix, iy + iry * 0.55, irx * 0.68, iry * 0.3, 0, 0, Math.PI * 2);
          g2.fillStyle = "rgba(255,255,255,0.3)";
          g2.fill();
          g2.fillStyle = "#ffffff";
          if (A.stars) {
            for (const [ox, oy, rr] of [[-0.3, -0.32, 0.62], [0.42, 0.38, 0.3]]) {
              const cx0 = ix + ox * irx, cy0 = iy + oy * iry, r0 = rr * irx;
              begin(g2);
              g2.moveTo(cx0, cy0 - r0);
              g2.quadraticCurveTo(cx0, cy0, cx0 + r0, cy0);
              g2.quadraticCurveTo(cx0, cy0, cx0, cy0 + r0);
              g2.quadraticCurveTo(cx0, cy0, cx0 - r0, cy0);
              g2.quadraticCurveTo(cx0, cy0, cx0, cy0 - r0);
              g2.fill();
            }
          } else {
            begin(g2);
            g2.ellipse(ix - irx * 0.36, iy - iry * 0.4, irx * 0.36, iry * 0.28, -0.35, 0, Math.PI * 2);
            g2.fill();
            circle(g2, ix + irx * 0.4, iy + iry * 0.38, irx * 0.15);
            g2.fill();
            if (e === "worried" || A.pool) {
              circle(g2, ix + irx * 0.15, iy - iry * 0.62, irx * 0.14);
              g2.fill();
              circle(g2, ix - irx * 0.5, iy + iry * 0.3, irx * 0.11);
              g2.fill();
            }
          }
        }
        const sh = g2.createLinearGradient(0, Yt + 0.04 * R + d, 0, Yt + 0.17 * R + d);
        sh.addColorStop(0, "rgba(30,20,60,0.35)");
        sh.addColorStop(1, "rgba(30,20,60,0)");
        g2.fillStyle = sh;
        g2.fillRect(x - 0.4 * R, Yt - 0.1 * R, 0.8 * R, 0.4 * R + d);
        if (A.pool) {
          begin(g2);
          g2.moveTo(x - 0.3 * R, Yb + 0.1 * R);
          g2.lineTo(x - 0.3 * R, ey + 0.05 * R);
          for (let i = 0; i < 4; i++) g2.quadraticCurveTo(x - 0.3 * R + 0.15 * (i + 0.5) * R, ey + (i % 2 ? 0.08 : 0.02) * R, x - 0.3 * R + 0.15 * (i + 1) * R, ey + 0.05 * R);
          g2.lineTo(x + 0.3 * R, Yb + 0.1 * R);
          g2.closePath();
          g2.fillStyle = "rgba(140,205,255,0.55)";
          g2.fill();
          begin(g2);
          g2.moveTo(x - 0.3 * R, ey + 0.05 * R);
          for (let i = 0; i < 4; i++) g2.quadraticCurveTo(x - 0.3 * R + 0.15 * (i + 0.5) * R, ey + (i % 2 ? 0.08 : 0.02) * R, x - 0.3 * R + 0.15 * (i + 1) * R, ey + 0.05 * R);
          g2.lineWidth = 5;
          g2.strokeStyle = "rgba(255,255,255,0.9)";
          g2.stroke();
        }
        open();
        g2.lineWidth = 0.022 * R;
        g2.strokeStyle = "rgba(36,26,28,0.4)";
        g2.stroke();
      }
      g2.restore();
      if (A.low > 0.02) {
        begin(g2);
        g2.moveTo(x + sd * W * 0.95, yb2 + 0 * R);
        g2.quadraticCurveTo(x, yb2 - 0.07 * R, x - sd * W * 0.4, yb2 - 0.02 * R);
        g2.lineWidth = 0.02 * R;
        g2.strokeStyle = INK;
        g2.lineCap = "round";
        g2.stroke();
      } else {
        begin(g2);
        for (let i = 0; i <= 8; i++) {
          const t = i / 8 * 0.6, qx = (1 - t) * (1 - t) * BO[0] + 2 * t * (1 - t) * x + t * t * BI[0], qy = (1 - t) * (1 - t) * BO[1] + 2 * t * (1 - t) * (Yb + 0.035 * R) + t * t * BI[1];
          i ? g2.lineTo(qx, qy) : g2.moveTo(qx, qy);
        }
        g2.lineWidth = 0.018 * R;
        g2.strokeStyle = INK;
        g2.lineCap = "round";
        g2.stroke();
      }
      begin(g2);
      g2.moveTo(TIt[0], TIt[1]);
      g2.quadraticCurveTo(Ct[0], Ct[1], TOt[0], TOt[1]);
      g2.lineTo(tail[0], tail[1]);
      g2.lineTo(TOb[0], TOb[1]);
      g2.quadraticCurveTo(Cb[0], Cb[1], TIb[0], TIb[1]);
      g2.closePath();
      g2.fillStyle = INK;
      g2.fill();
      g2.lineWidth = 3;
      g2.strokeStyle = INK;
      g2.lineJoin = "round";
      g2.stroke();
      if (s.lashes) for (const [u, v] of [[0.75, -0.02], [0.95, 0.01]]) {
        const b0 = P(W * u, Yt + d + v * R - ti * (u > 0.8 ? 1 : 0.5));
        line(g2, [b0, [b0[0] + sd * 0.06 * R, b0[1] - 0.06 * R]], 7);
      }
      if (A.shake) for (const k22 of [0, 1, 2]) line(g2, [P(W + 0.07 * R + k22 * 0.035 * R, ey - 0.06 * R + k22 * 0.01 * R), P(W + 0.07 * R + k22 * 0.035 * R, ey + 0.06 * R - k22 * 0.01 * R)], 5);
    } else if (mode === "arc") {
      begin(g2);
      g2.arc(x, ey + 0.07 * R, w * 0.85, Math.PI * 1.12, Math.PI * 1.88);
      g2.lineWidth = thick;
      g2.strokeStyle = INK;
      g2.lineCap = "round";
      g2.stroke();
    } else if (mode === "line") {
      line(g2, [[x - w * 0.95, ey], [x + w * 0.95, ey + 0.01 * R]], thick);
      line(g2, [[x + sd * w * 0.95, ey + 0.01 * R], [x + sd * (w + 0.05 * R), ey - 0.03 * R]], thick * 0.7);
    } else if (mode === "dot") {
      circle(g2, x, ey, 0.04 * R);
      g2.fillStyle = INK;
      g2.fill();
    } else if (mode === "gt") {
      begin(g2);
      g2.moveTo(x - sd * w * 0.75, ey - 0.1 * R);
      g2.lineTo(x + sd * w * 0.7, ey);
      g2.lineTo(x - sd * w * 0.75, ey + 0.1 * R);
      g2.lineWidth = thick;
      g2.strokeStyle = INK;
      g2.lineJoin = "round";
      g2.lineCap = "round";
      g2.stroke();
    } else if (mode === "T") {
      line(g2, [[x - w, ey - 0.04 * R], [x + w, ey - 0.04 * R]], thick);
      line(g2, [[x, ey - 0.04 * R], [x, ey + 0.09 * R]], thick * 0.9);
    } else if (mode === "blank") {
      begin(g2);
      g2.ellipse(x, ey - 0.01 * R, w * 0.95, 0.22 * R * k2, 0, 0, Math.PI * 2);
      fillInk(g2, "#ffffff", 0.028 * R);
      circle(g2, x + lx * 0.04 * R, ey, 0.028 * R * Math.max(0.6, A.ps * 3));
      g2.fillStyle = INK;
      g2.fill();
    } else if (mode === "spiral") {
      circle(g2, x, ey, 0.19 * R * k2);
      fillInk(g2, "#ffffff", 0.025 * R);
      begin(g2);
      for (let t = 0; t <= Math.PI * 5; t += 0.2) {
        const r = (0.012 + t * 0.0108) * R * k2, a = t * sd;
        t ? g2.lineTo(x + Math.cos(a) * r, ey + Math.sin(a) * r) : g2.moveTo(x, ey);
      }
      g2.lineWidth = 0.022 * R;
      g2.strokeStyle = INK;
      g2.stroke();
    } else if (mode === "rage") {
      begin(g2);
      g2.moveTo(x - sd * w * 0.9, ey + 0 * R);
      g2.lineTo(x + sd * w * 1.05, ey - 0.13 * R);
      g2.quadraticCurveTo(x + sd * w * 1, ey + 0.08 * R, x + sd * w * 0.6, ey + 0.1 * R);
      g2.quadraticCurveTo(x - sd * w * 0.3, ey + 0.1 * R, x - sd * w * 0.9, ey);
      g2.closePath();
      g2.lineJoin = "round";
      fillInk(g2, "#ffffff", 0.03 * R);
    } else if (mode === "heart") {
      const hr = 0.18 * R * k2, hy2 = ey + 0.02 * R;
      begin(g2);
      g2.moveTo(x, hy2 + hr * 0.95);
      g2.bezierCurveTo(x - hr * 1.5, hy2 - hr * 0.1, x - hr * 0.7, hy2 - hr * 1.2, x, hy2 - hr * 0.45);
      g2.bezierCurveTo(x + hr * 0.7, hy2 - hr * 1.2, x + hr * 1.5, hy2 - hr * 0.1, x, hy2 + hr * 0.95);
      g2.closePath();
      fillInk(g2, "#ec3a5c", 0.022 * R);
      begin(g2);
      g2.ellipse(x - hr * 0.42, hy2 - hr * 0.35, hr * 0.22, hr * 0.13, -0.6, 0, Math.PI * 2);
      g2.fillStyle = "rgba(255,255,255,0.85)";
      g2.fill();
    } else if (mode === "star") {
      const r1 = 0.2 * R * k2, r2 = r1 * 0.45;
      begin(g2);
      for (let i = 0; i < 10; i++) {
        const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? r2 : r1;
        i ? g2.lineTo(x + Math.cos(a) * r, ey + Math.sin(a) * r) : g2.moveTo(x + Math.cos(a) * r, ey + Math.sin(a) * r);
      }
      g2.closePath();
      g2.lineJoin = "round";
      fillInk(g2, "#ffd23a", 0.022 * R);
      circle(g2, x - r1 * 0.2, ey - r1 * 0.2, r1 * 0.14);
      g2.fillStyle = "#ffffff";
      g2.fill();
    }
    if (s.glasses) {
      circle(g2, x, ey, 0.28 * R * sq);
      inkStroke(g2, 7);
      begin(g2);
      g2.arc(x, ey, 0.23 * R * sq, Math.PI * 1.15, Math.PI * 1.4);
      g2.lineWidth = 6;
      g2.strokeStyle = "rgba(255,255,255,0.9)";
      g2.stroke();
    }
    if (A.tears) {
      const tx = x + sd * 0.02 * R, path = () => {
        begin(g2);
        g2.moveTo(tx - 0.05 * R, ey + 0.1 * R);
        g2.bezierCurveTo(tx - 0.09 * R, ey + 0.4 * R, tx - 0.03 * R, ey + 0.6 * R, tx - 0.1 * R, HY + 1.05 * R);
        g2.lineTo(tx + 0.1 * R, HY + 1.05 * R);
        g2.bezierCurveTo(tx + 0.05 * R, ey + 0.6 * R, tx + 0.1 * R, ey + 0.4 * R, tx + 0.05 * R, ey + 0.1 * R);
        g2.closePath();
      };
      path();
      g2.fillStyle = "rgba(110,185,255,0.85)";
      g2.fill();
      path();
      g2.lineWidth = 4;
      g2.strokeStyle = "rgba(40,90,170,0.9)";
      g2.stroke();
      line(g2, [[tx - 0.02 * R, ey + 0.15 * R], [tx - 0.03 * R, ey + 0.55 * R]], 5, "rgba(255,255,255,0.8)");
    }
    const bw = s.brows === "thick" ? 0.07 * R : s.brows === "bushy" ? 0.1 * R : s.brows === "thin" ? 0.035 * R : 0.05 * R;
    const by = ey - 0.31 * R * k2 + A.bY * R - (sd > 0 ? A.asym : -A.asym * 0.4) * R - (s.glasses ? 0.04 * R : 0);
    const xi = x - sd * 0.12 * R * sq, xo = x + sd * 0.23 * R * sq, yi = by - A.bIn * R, yo = by + 0.03 * R + A.bIn * 0.2 * R;
    const halo = s.hat && s.hat !== "none" || s.hair && !["none", "bald", "combover", "bun", "ponytail", "slick"].includes(s.hair) && Math.min(yi, yo) < HY - 0.22 * R ? 10 : 0;
    BROW_PASS.push(() => browShape(g2, xi, yi, xo, yo, bw, (A.arch + 0.025) * R, bc, s.brows === "bushy", halo));
    inner.push([xi, yi]);
  }
  if (s.brows === "uni") BROW_PASS.push(() => line(g2, [inner[0], [(inner[0][0] + inner[1][0]) / 2, Math.min(inner[0][1], inner[1][1]) + 0.02 * R], inner[1]], 0.05 * R, bc));
  if (s.glasses) line(g2, [[fx - sp + 0.28 * R, ey - 0.02 * R], [fx, ey - 0.05 * R], [fx + sp - 0.28 * R, ey - 0.02 * R]], 7);
  const nx = fx + yaw * 0.12 * R, ny = ey + 0.29 * R;
  if (s.nose === "button" || s.nose === "bulb") {
    const big = s.nose === "bulb", rx = (big ? 0.12 : 0.06) * R, ry = (big ? 0.095 : 0.045) * R;
    begin(g2);
    g2.ellipse(nx, ny, rx, ry, 0, 0, Math.PI * 2);
    fillInk(g2, big ? "#f2b4a6" : shade(skin, 0.93), 5);
    begin(g2);
    g2.ellipse(nx - rx * 0.35, ny - ry * 0.35, rx * 0.3, ry * 0.22, -0.4, 0, Math.PI * 2);
    g2.fillStyle = "rgba(255,255,255,0.75)";
    g2.fill();
  } else line(g2, [[nx + 0.01 * R, ny - 0.03 * R], [nx - 0.015 * R, ny + 0.02 * R]], 5, "rgba(60,40,50,0.6)");
  const my = HY + 0.56 * R, mx = fx + yaw * 0.06 * R;
  mouthAnime(g2, A.mouth, mx, my, e === "talk" ? p.mouth ?? A.mo : A.mo);
  if (s.teeth === "buck" && ["small", "flat", "cat", "smirkFang"].includes(A.mouth)) for (const sd of [-1, 1]) {
    begin(g2);
    g2.roundRect(mx + (sd < 0 ? -0.06 : 5e-3) * R, my + 0.01 * R, 0.055 * R, 0.08 * R, 0.015 * R);
    fillInk(g2, "#ffffff", 5);
  }
  if (s.mustache) {
    const ty = my - 0.07 * R - (["shark", "jaw", "openBig"].includes(A.mouth) ? 0.04 * R : 0);
    begin(g2);
    g2.moveTo(mx - 0.26 * R, ty + 0.02 * R);
    g2.quadraticCurveTo(mx - 0.12 * R, ty - 0.17 * R, mx, ty - 0.08 * R);
    g2.quadraticCurveTo(mx + 0.12 * R, ty - 0.17 * R, mx + 0.26 * R, ty + 0.02 * R);
    g2.quadraticCurveTo(mx + 0.1 * R, ty - 0.02 * R, mx, ty - 0.04 * R);
    g2.quadraticCurveTo(mx - 0.1 * R, ty - 0.02 * R, mx - 0.26 * R, ty + 0.02 * R);
    g2.closePath();
    fillInk(g2, s.mustache, 6);
  }
  const sw = p.sweat ? Math.max(1, A.sweat ?? 1) : A.sweat ?? 0;
  if (sw === 1) drop(g2, CX + 0.74 * R, HY - 0.42 * R, 1.5);
  else if (sw > 1) [[1.12, -0.62, 0.9], [-1.14, -0.45, 0.8], [1.2, -0.12, 0.7]].forEach(([u, v, kk]) => drop(g2, CX + u * R, HY + v * R, kk));
  if (A.bubble) {
    circle(g2, nx + 0.13 * R, ny + 0.05 * R, 0.13 * R);
    g2.fillStyle = "rgba(170,220,255,0.55)";
    g2.fill();
    g2.lineWidth = 4;
    g2.strokeStyle = "rgba(70,130,200,0.9)";
    g2.stroke();
    begin(g2);
    g2.arc(nx + 0.13 * R, ny + 0.05 * R, 0.09 * R, Math.PI * 1.1, Math.PI * 1.45);
    g2.lineWidth = 5;
    g2.strokeStyle = "rgba(255,255,255,0.95)";
    g2.stroke();
  }
  if (A.sparkle) {
    sparkleMark(g2, CX + 1.12 * R, HY - 0.7 * R, 0.1 * R);
    sparkleMark(g2, CX - 1.15 * R, HY - 0.3 * R, 0.07 * R);
    sparkleMark(g2, CX + 1.25 * R, HY - 0.25 * R, 0.06 * R);
  }
  if (A.vein) BROW_PASS.push(() => veinMark(g2, CX + 0.52 * R, HY - 0.62 * R));
};
var face = (g2, s, p) => {
  const st = s.eyes ?? "anime";
  if (st === "anime") return faceAnime(g2, s, p);
  if (st === "fun") return faceFun(g2, s, p);
  if (st === "almond" && !["shock", "grimace"].includes(p.expr ?? "neutral") && !s.glasses) return faceAlmond(g2, s, p);
  return faceRing(g2, s, p);
};
var faceAlmond = (g2, s, p) => {
  const e = p.expr ?? "neutral", yaw = p.yaw ?? 0, blink = p.blink ?? 0, col = s.head ?? "#fbfaf7", [lx, ly] = p.look ?? [0, 0];
  const fx = CX + yaw * 0.34 * R, ey = HY + 0.14 * R, sp = 0.23 * R * (1 - 0.15 * Math.abs(yaw));
  for (const sd of [-1, 1]) {
    const far = yaw !== 0 && Math.sign(yaw) !== sd, x = fx + sd * sp * (far ? 0.85 : 1), sq = far ? 0.8 : 1;
    if (e === "smile" || blink >= 0.9) {
      begin(g2);
      g2.arc(x, ey + 0.04 * R, 0.08 * R * sq, Math.PI * (e === "smile" ? 1.1 : 0.1), Math.PI * (e === "smile" ? 1.9 : 0.9), e !== "smile");
      g2.lineWidth = 10;
      g2.strokeStyle = INK;
      g2.lineCap = "round";
      g2.stroke();
    } else {
      begin(g2);
      g2.ellipse(x + lx * 0.02 * R, ey + ly * 0.02 * R + 0.02 * R, 0.105 * R * sq, 0.135 * R, 0, 0, Math.PI * 2);
      g2.fillStyle = INK;
      g2.fill();
      const lid = e === "deadpan" || e === "smirk" ? 0.55 : e === "angry" ? 0.42 : e === "worried" ? 0.1 : 0.2;
      const yl = ey - 0.1 * R + lid * 0.24 * R, tl = e === "angry" ? sd * 0.05 * R : e === "worried" ? -sd * 0.05 * R : 0;
      g2.save();
      begin(g2);
      g2.ellipse(x + lx * 0.02 * R, ey + ly * 0.02 * R + 0.02 * R, 0.105 * R * sq + 2, 0.135 * R + 2, 0, 0, Math.PI * 2);
      g2.clip();
      begin(g2);
      g2.rect(x - 0.2 * R, ey - 0.25 * R, 0.4 * R, yl - (ey - 0.25 * R));
      g2.fillStyle = col;
      g2.fill();
      g2.restore();
      taper(g2, x - 0.2 * R * sq, yl - tl, x + 0.2 * R * sq, yl + tl, 0.085 * R, 0.012 * R);
    }
    const by = ey - 0.3 * R, bt = e === "angry" ? sd * 0.07 * R : e === "worried" ? -sd * 0.07 * R : e === "smirk" && sd > 0 ? -0.05 * R : 0;
    taper(g2, x - sd * 0.16 * R * sq, by + bt, x + sd * 0.18 * R * sq, by - bt * 0.4 - 0.03 * R, 0.1 * R, 0.045 * R);
  }
  const my = HY + 0.5 * R, mx = fx + yaw * 0.06 * R;
  if (s.mustache) {
    begin(g2);
    g2.moveTo(mx - 0.24 * R, my - 0.05 * R);
    g2.quadraticCurveTo(mx, my - 0.22 * R, mx + 0.24 * R, my - 0.05 * R);
    g2.quadraticCurveTo(mx + 0.1 * R, my - 0.02 * R, mx, my - 0.1 * R);
    g2.quadraticCurveTo(mx - 0.1 * R, my - 0.02 * R, mx - 0.24 * R, my - 0.05 * R);
    g2.closePath();
    fillInk(g2, s.mustache, 6);
  }
  if (e === "talk" || e === "shock") {
    begin(g2);
    g2.ellipse(mx, my + 0.06 * R, 0.085 * R, 0.1 * R, 0, 0, Math.PI * 2);
    fillInk(g2, "#3a1418", 6);
  } else if (e === "smile") {
    begin(g2);
    g2.moveTo(mx - 0.13 * R, my);
    g2.quadraticCurveTo(mx, my + 0.14 * R, mx + 0.13 * R, my);
    g2.quadraticCurveTo(mx, my + 0.07 * R, mx - 0.13 * R, my);
    g2.closePath();
    fillInk(g2, "#3a1418", 6);
  } else if (e === "angry") taper(g2, mx - 0.1 * R, my + 0.08 * R, mx + 0.1 * R, my + 0.08 * R, 0.045 * R, 0.04 * R);
  else if (e === "worried") {
    begin(g2);
    g2.moveTo(mx - 0.12 * R, my + 0.07 * R);
    g2.bezierCurveTo(mx - 0.04 * R, my + 0.02 * R, mx + 0.04 * R, my + 0.11 * R, mx + 0.12 * R, my + 0.05 * R);
    inkStroke(g2, 7);
  } else if (e === "smirk") taper(g2, mx - 0.1 * R, my + 0.07 * R, mx + 0.12 * R, my + 0.02 * R, 0.04 * R, -0.02 * R);
  else taper(g2, mx - 0.07 * R, my + 0.06 * R, mx + 0.08 * R, my + 0.06 * R, 0.04 * R, -0.01 * R);
  if (p.sweat) {
    begin(g2);
    g2.moveTo(CX - 0.86 * R, HY - 0.52 * R);
    g2.quadraticCurveTo(CX - 0.74 * R, HY - 0.3 * R, CX - 0.86 * R, HY - 0.22 * R);
    g2.quadraticCurveTo(CX - 0.98 * R, HY - 0.3 * R, CX - 0.86 * R, HY - 0.52 * R);
    fillInk(g2, "#9fd4ff", 6);
  }
};
var faceRing = (g2, s, p) => {
  const e = p.expr ?? "neutral", [lx, ly] = p.look ?? [0, 0], blink = p.blink ?? 0, col = s.head ?? "#fbfaf7";
  const ey = HY - 0.04 * R, er = 0.235 * R, ex = 0.4 * R;
  const shock = e === "shock" || e === "grimace";
  for (const sd of [-1, 1]) {
    const x = CX + sd * ex;
    circle(g2, x, ey, er);
    fillInk(g2, "#ffffff", 8);
    const pr = shock ? 0.055 * R : 0.075 * R;
    if (blink < 0.9) {
      circle(g2, x + lx * 0.07 * R, ey + ly * 0.07 * R, pr);
      g2.fillStyle = INK;
      g2.fill();
    }
    const lid = blink >= 0.9 ? 1 : e === "deadpan" ? 0.45 : e === "angry" ? 0.35 : e === "worried" ? 0.2 : blink;
    if (lid > 0.02) {
      const yl = ey - er + 2 * er * lid, tiltK = e === "angry" ? -sd * 0.12 * R : e === "worried" ? sd * 0.1 * R : 0;
      g2.save();
      circle(g2, x, ey, er - 4);
      g2.clip();
      begin(g2);
      g2.moveTo(x - er - 10, ey - er - 10);
      g2.lineTo(x + er + 10, ey - er - 10);
      g2.lineTo(x + er + 10, yl - tiltK * sd);
      g2.lineTo(x - er - 10, yl + tiltK * sd);
      g2.closePath();
      g2.fillStyle = col;
      g2.fill();
      g2.restore();
      line(g2, [[x - er, yl + tiltK * sd], [x + er, yl - tiltK * sd]], 8);
    }
    if (s.glasses) {
      circle(g2, x, ey, er * 1.25);
      inkStroke(g2, 7);
    }
    if (e === "angry" || e === "worried") {
      const k2 = e === "angry" ? 1 : -1;
      line(g2, [[x - sd * 0.18 * R, ey - er - 0.08 * R + k2 * 0.06 * R], [x + sd * 0.16 * R, ey - er - 0.08 * R - k2 * 0.06 * R]], 11);
    }
  }
  if (s.glasses) line(g2, [[CX - ex + er * 1.25, ey], [CX + ex - er * 1.25, ey]], 7);
  const my = HY + 0.48 * R;
  if (s.mustache) {
    begin(g2);
    g2.moveTo(CX - 0.26 * R, my - 0.08 * R);
    g2.quadraticCurveTo(CX, my - 0.26 * R, CX + 0.26 * R, my - 0.08 * R);
    g2.quadraticCurveTo(CX, my - 0.14 * R, CX - 0.26 * R, my - 0.08 * R);
    g2.closePath();
    fillInk(g2, s.mustache, 6);
  }
  if (e === "shock") {
    begin(g2);
    g2.ellipse(CX, my + 0.06 * R, 0.1 * R, 0.13 * R, 0, 0, Math.PI * 2);
    fillInk(g2, "#3a1418", 7);
  } else if (e === "grimace") {
    begin(g2);
    g2.roundRect(CX - 0.2 * R, my - 0.02 * R, 0.4 * R, 0.2 * R, 0.06 * R);
    fillInk(g2, "#ffffff", 7);
    for (const k2 of [-1, 0, 1]) line(g2, [[CX + k2 * 0.1 * R, my - 0.02 * R], [CX + k2 * 0.1 * R, my + 0.18 * R]], 5);
    line(g2, [[CX - 0.2 * R, my + 0.08 * R], [CX + 0.2 * R, my + 0.08 * R]], 5);
  } else if (e === "smile") {
    begin(g2);
    g2.arc(CX, my - 0.08 * R, 0.16 * R, 0.15 * Math.PI, 0.85 * Math.PI);
    inkStroke(g2, 8);
  } else if (e === "smirk") {
    begin(g2);
    g2.moveTo(CX - 0.14 * R, my + 0.02 * R);
    g2.quadraticCurveTo(CX + 0.05 * R, my + 0.07 * R, CX + 0.17 * R, my - 0.06 * R);
    inkStroke(g2, 8);
  } else if (e === "worried") {
    begin(g2);
    g2.moveTo(CX - 0.16 * R, my + 0.04 * R);
    g2.bezierCurveTo(CX - 0.06 * R, my - 0.04 * R, CX + 0.04 * R, my + 0.1 * R, CX + 0.16 * R, my + 0.02 * R);
    inkStroke(g2, 8);
  } else if (e === "talk") {
    begin(g2);
    g2.ellipse(CX + 0.02 * R, my + 0.03 * R, 0.08 * R, 0.06 * R, 0, 0, Math.PI * 2);
    fillInk(g2, "#3a1418", 6);
  } else {
    begin(g2);
    g2.moveTo(CX - 0.1 * R, my + 0.02 * R);
    g2.quadraticCurveTo(CX + 0.02 * R, my - 0.01 * R, CX + 0.14 * R, my + 0.04 * R);
    inkStroke(g2, 8);
  }
  if (p.sweat) {
    begin(g2);
    g2.moveTo(CX + 0.86 * R, HY - 0.62 * R);
    g2.quadraticCurveTo(CX + 0.98 * R, HY - 0.4 * R, CX + 0.86 * R, HY - 0.32 * R);
    g2.quadraticCurveTo(CX + 0.74 * R, HY - 0.4 * R, CX + 0.86 * R, HY - 0.62 * R);
    fillInk(g2, "#9fd4ff", 6);
  }
};
var LIMB_W = 0.22 * R;
var noodle = (g2, pts, w, col) => {
  const path = () => {
    begin(g2);
    g2.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
      g2.quadraticCurveTo(pts[i][0], pts[i][1], i === pts.length - 2 ? pts[i + 1][0] : mx, i === pts.length - 2 ? pts[i + 1][1] : my);
    }
    if (pts.length === 2) g2.lineTo(pts[1][0], pts[1][1]);
  };
  g2.lineCap = "round";
  g2.lineJoin = "round";
  path();
  g2.lineWidth = w + 10;
  g2.strokeStyle = INK;
  g2.stroke();
  path();
  g2.lineWidth = w;
  g2.strokeStyle = col;
  g2.stroke();
};
var mitten = (g2, x, y, sd) => {
  begin(g2);
  g2.ellipse(x, y, 0.13 * R, 0.12 * R, 0, 0, Math.PI * 2);
  fillInk(g2, "#f7f6f2", 8);
  begin(g2);
  g2.ellipse(x - sd * 0.1 * R, y - 0.05 * R, 0.05 * R, 0.07 * R, sd * 0.6, 0, Math.PI * 2);
  fillInk(g2, "#f7f6f2", 7);
};
var armPts = (sd, a) => {
  const sx = CX + sd * (BLD.sh - 0.13) * R, sy = BODY_T + 0.32 * R, r1 = (a * 0.75 + 12) * Math.PI / 180, r2 = (a - 2) * Math.PI / 180, L1 = 1.15 * R, L2 = 1.12 * R;
  const ex = sx + sd * Math.sin(r1) * L1, ey = sy + Math.cos(r1) * L1, hx2 = ex + sd * Math.sin(r2) * L2, hy2 = ey + Math.cos(r2) * L2;
  return [[sx, sy], [ex, ey], [hx2, hy2]];
};
var drawArm = (g2, s, sd, a) => {
  const pts = armPts(sd, a), c = s.limb ?? "#2a1a14";
  noodle(g2, pts, LIMB_W, c);
  const [hx2, hy2] = pts[2];
  if (s.sleeves !== false && s.outfit !== "dress") {
    const long = ["jacket", "coat", "suit", "hoodie"].includes(s.outfit), col = long ? s.base : s.shirt ?? "#f4f1ea";
    const lerp = (u) => {
      const [a0, a1, a2] = pts;
      return u < 0.5 ? [a0[0] + (a1[0] - a0[0]) * u * 2, a0[1] + (a1[1] - a0[1]) * u * 2] : [a1[0] + (a2[0] - a1[0]) * (u - 0.5) * 2, a1[1] + (a2[1] - a1[1]) * (u - 0.5) * 2];
    };
    const end = long ? 0.82 : 0.3, sl = long ? [pts[0], pts[1], lerp(end)] : [pts[0], lerp(end)];
    noodle(g2, sl, LIMB_W * 1.28, col);
    g2.save();
    g2.lineCap = "round";
    begin(g2);
    const [x0, y0] = sl[0], [x1, y1] = sl[sl.length - 1];
    g2.moveTo(x0 - sd * 0.08 * R, y0);
    g2.lineTo(x1 - sd * 0.08 * R, y1);
    g2.lineWidth = LIMB_W * 0.35;
    g2.strokeStyle = "rgba(255,255,255,0.18)";
    g2.stroke();
    g2.restore();
    const [cx2, cy2] = lerp(end), [px, py] = lerp(end - 0.05), ang = Math.atan2(cy2 - py, cx2 - px);
    g2.save();
    g2.translate(cx2, cy2);
    g2.rotate(ang);
    begin(g2);
    g2.roundRect(-0.07 * R, -LIMB_W * 0.7, 0.14 * R, LIMB_W * 1.4, 10);
    fillInk(g2, shade(col, 0.72), 7);
    g2.restore();
  }
  if (s.mittens !== false) mitten(g2, hx2, hy2, sd);
  else {
    circle(g2, hx2, hy2, LIMB_W * 0.62);
    g2.fillStyle = c;
    g2.fill();
  }
};
var armAngles = (p) => [p.armL ?? 6, p.wave !== void 0 ? 150 + 20 * p.wave : p.armR ?? 6];
var legPath = (g2, pts, w0, w1, col) => {
  const [a, k2, c] = pts, N = 16, L = [], Rr = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N, x = (1 - t) * (1 - t) * a[0] + 2 * t * (1 - t) * k2[0] + t * t * c[0], y = (1 - t) * (1 - t) * a[1] + 2 * t * (1 - t) * k2[1] + t * t * c[1];
    const dx = 2 * (1 - t) * (k2[0] - a[0]) + 2 * t * (c[0] - k2[0]), dy = 2 * (1 - t) * (k2[1] - a[1]) + 2 * t * (c[1] - k2[1]), l = Math.hypot(dx, dy) || 1, w = (w0 + (w1 - w0) * t) / 2;
    L.push([x - dy / l * w, y + dx / l * w]);
    Rr.push([x + dy / l * w, y - dx / l * w]);
  }
  begin(g2);
  [...L, ...Rr.reverse()].forEach(([x, y], i) => i ? g2.lineTo(x, y) : g2.moveTo(x, y));
  g2.closePath();
  g2.fillStyle = col;
  g2.fill();
  inkStroke(g2, 9);
};
var shoe = (g2, x, sd, kind, col) => {
  const hi = kind === "boots" ? 0.38 * R : kind === "trainers" ? 0.24 * R : 0.18 * R, sole = kind === "boots" ? 0.08 * R : kind === "trainers" ? 0.075 * R : 0.05 * R, w = 0.31 * R;
  g2.save();
  g2.translate(x + sd * 0.04 * R, FEET);
  g2.rotate(sd * 0.1);
  const upper = () => {
    begin(g2);
    g2.moveTo(-w * 0.62, -sole);
    g2.lineTo(-w * 0.55, -hi);
    g2.quadraticCurveTo(0, -hi - 0.03 * R, w * 0.55, -hi);
    g2.lineTo(w * 0.62, -sole);
    g2.closePath();
  };
  const toe = () => {
    begin(g2);
    g2.ellipse(0, -sole - 0.07 * R, w, 0.14 * R, 0, 0, Math.PI * 2);
  };
  begin(g2);
  g2.roundRect(-w * 1.06, -sole - 0.02 * R, w * 2.12, sole + 0.02 * R, 0.04 * R);
  fillInk(g2, kind === "trainers" ? "#f4f2ec" : kind === "boots" ? "#2a1c14" : shade(col, 0.6), 8);
  if (kind === "boots") for (let k2 = -2; k2 <= 2; k2++) line(g2, [[k2 * 0.09 * R - 0.025 * R, -3], [k2 * 0.09 * R + 0.025 * R, -3]], 6, "#5a4030");
  upper();
  g2.fillStyle = col;
  g2.fill();
  inkStroke(g2, 8);
  toe();
  g2.fillStyle = col;
  g2.fill();
  const lit = (path) => withClip(g2, path, () => {
    const gr = g2.createLinearGradient(-w * 1.1, 0, w * 1.1, 0);
    gr.addColorStop(0, "rgba(255,255,255,0.25)");
    gr.addColorStop(0.45, "rgba(255,255,255,0)");
    gr.addColorStop(1, "rgba(10,10,20,0.32)");
    g2.fillStyle = gr;
    g2.fillRect(-w * 1.2, -hi - 20, w * 2.4, hi + 30);
  });
  lit(upper);
  lit(toe);
  withClip(g2, toe, () => {
    if (kind === "oxford") {
      begin(g2);
      g2.ellipse(0, -sole - 0.02 * R, w * 0.62, 0.07 * R, 0, Math.PI, 0);
      g2.lineWidth = 5;
      g2.strokeStyle = "rgba(0,0,0,0.4)";
      g2.stroke();
      begin(g2);
      g2.ellipse(-w * 0.35, -sole - 0.11 * R, w * 0.28, 0.025 * R, -0.1, 0, Math.PI * 2);
      g2.fillStyle = "rgba(255,255,255,0.6)";
      g2.fill();
    }
    if (kind === "trainers") {
      begin(g2);
      g2.moveTo(-w, -sole - 0.02 * R);
      g2.quadraticCurveTo(-w * 0.2, -sole - 0.14 * R, w * 0.5, -sole - 0.03 * R);
      g2.lineWidth = 0.035 * R;
      g2.strokeStyle = "#d8262e";
      g2.stroke();
    }
    if (kind === "boots") {
      begin(g2);
      g2.ellipse(0, -sole - 0.07 * R, w * 0.7, 0.06 * R, 0, Math.PI, 0);
      g2.lineWidth = 4;
      g2.strokeStyle = "rgba(0,0,0,0.3)";
      g2.stroke();
    }
  });
  toe();
  inkStroke(g2, 8);
  if (kind === "boots" || kind === "trainers") {
    const lc = kind === "boots" ? "#f0e2c0" : "#3a3d52", n = kind === "boots" ? 3 : 2, top = -hi + 0.06 * R, bot = -sole - 0.17 * R;
    begin(g2);
    g2.roundRect(-0.075 * R, top - 0.03 * R, 0.15 * R, bot - top + 0.05 * R, 0.03 * R);
    g2.fillStyle = shade(col, 0.82);
    g2.fill();
    for (let k2 = 0; k2 < n; k2++) {
      const yy = top + (k2 + 0.5) * (bot - top) / n;
      line(g2, [[-0.065 * R, yy], [0.065 * R, yy]], 6, lc);
    }
  }
  g2.restore();
};
var footwearOf = (s) => s.footwear ?? (s.outfit === "suit" ? "oxford" : s.outfit === "coat" ? "oxford" : s.outfit === "dress" ? "flats" : s.outfit === "hoodie" ? "trainers" : "boots");
var shoeColOf = (s, kind) => s.shoeCol ?? (kind === "oxford" ? "#1d1b22" : kind === "trainers" ? "#f4f2ec" : kind === "flats" ? "#7a2a32" : "#6a4428");
var legs = (g2, s, p) => {
  const c = s.limb ?? "#2a1a14", kn = p.knee ?? 0, kind = footwearOf(s), sc = shoeColOf(s, kind);
  {
    const sh = g2.createRadialGradient(CX, FEET, 0, CX, FEET, 0.85 * R);
    sh.addColorStop(0, "rgba(20,20,40,0.32)");
    sh.addColorStop(1, "rgba(20,20,40,0)");
    g2.save();
    g2.translate(CX, FEET);
    g2.scale(1, 0.16);
    g2.translate(-CX, -FEET);
    g2.fillStyle = sh;
    g2.beginPath();
    g2.arc(CX, FEET, 0.85 * R, 0, Math.PI * 2);
    g2.fill();
    g2.restore();
  }
  for (const sd of [-1, 1]) {
    const hx2 = CX + sd * 0.27 * R, hy2 = BODY_B + 0.3 * R, ax = CX + sd * 0.29 * R, ay = FEET - (kind === "boots" ? 0.3 * R : 0.14 * R);
    const kx = CX + sd * 0.31 * R + kn * 0.3 * R, ky = (hy2 + ay) / 2;
    if (s.legStyle !== "long") legPath(g2, [[hx2, hy2], [kx, ky], [ax, ay]], LIMB_W * 0.95, LIMB_W * 0.78, c);
    if (kind !== "boots" && s.legStyle !== "long") {
      const sk = s.socks ?? (kind === "trainers" ? "#f4f2ec" : "#3a3d52");
      begin(g2);
      g2.roundRect(ax - LIMB_W * 0.5, ay - 0.08 * R, LIMB_W, 0.12 * R, 6);
      fillInk(g2, sk, 7);
    }
    shoe(g2, ax, sd, kind, sc);
  }
};
var drawClean = (g2, s, p = {}) => {
  g2.save();
  if (p.tilt) {
    g2.translate(CX, FEET);
    g2.rotate(p.tilt * Math.PI / 180);
    g2.translate(-CX, -FEET);
  }
  BLD = BUILDS[s.build ?? (s.outfit === "suit" ? "broad" : "average")];
  HEM = s.outfit === "coat" ? BODY_B - 0.12 * R : s.outfit === "dress" ? BODY_B : JACKET_HEM();
  legs(g2, s, p);
  trousers(g2, s);
  if (p.lean) {
    g2.translate(CX, BODY_B - 40);
    g2.rotate(p.lean * Math.PI / 180);
    g2.translate(-CX, -(BODY_B - 40));
  }
  const [aL, aR] = armAngles(p);
  if (aL < 40) drawArm(g2, s, -1, aL);
  if (aR < 40) drawArm(g2, s, 1, aR);
  outfit(g2, s);
  if (aL >= 40) drawArm(g2, s, -1, aL);
  if (aR >= 40) drawArm(g2, s, 1, aR);
  hairBack(g2, s);
  head(g2, s);
  hair(g2, s);
  const yaw = p.yaw ?? 0;
  if (yaw && s.hair && !["none", "bald", "combover"].includes(s.hair)) withClip(g2, () => headPath(g2), () => {
    const bx = CX - Math.sign(yaw) * 0.95 * R;
    begin(g2);
    g2.ellipse(bx, HY - 0.05 * R, 0.32 * R * Math.min(1, Math.abs(yaw) * 2), 0.5 * R, 0, 0, Math.PI * 2);
    fillInk(g2, s.hairCol ?? "#5a3418", 8);
  });
  BROW_PASS = [];
  face(g2, s, p);
  hat(g2, s);
  hatPaint(g2, s);
  for (const b of BROW_PASS) b();
  BROW_PASS = [];
  g2.restore();
};

// scripts/clean_faces.ts
var out = process.argv[2] ?? "out/clean_faces.png";
var exprs = ["neutral", "smile", "laugh", "cheeky", "smug", "smirk", "talk", "suspicious", "deadpan", "sleepy", "worried", "sad", "grimace", "panic", "shock", "angry", "yell", "excited", "love", "dizzy", "cry"];
var hero = { hair: "messy", hairCol: "#7a4a22", outfit: "jacket", base: "#3f8a4a", iris: "#8a5a2a" };
var cast = [
  ["Dave", { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#3f8a4a", mustache: "#4a3020", hair: "messy", hairCol: "#7a4a22", brows: "bushy", iris: "#4a7a3a" }, "suspicious"],
  ["Repairman", { hat: "cap", hatCol: "#1f4fa0", outfit: "overalls", base: "#2f56a8", hair: "messy", hairCol: "#2a1c18", teeth: "buck", iris: "#3a6ab0" }, "cheeky"],
  ["Boss", { hair: "combover", hairCol: "#9a9a9a", outfit: "suit", base: "#5a3a6a", tie: "#d8262e", nose: "bulb", brows: "bushy", cheeks: true, iris: "#6a4a8a" }, "laugh"],
  ["Worker", { hat: "hardhat", hatCol: "#f2c230", outfit: "vest", base: "#9be03a", hair: "spiky", hairCol: "#e0b040", brows: "uni", browCol: "#8a6420", iris: "#2a8ab0" }, "panic"],
  ["Shop assistant", { hair: "bun", hairCol: "#c8502a", outfit: "coat", base: "#f4f6f8", glasses: true, lashes: true, freckles: true, brows: "thin", iris: "#2f9a6a" }, "smug"],
  ["Bailiff", { hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#24222c", mustache: "#6a6a6a", hair: "slick", hairCol: "#6a6a6a", brows: "thick", iris: "#8a2a2a" }, "yell"]
];
var cols = 7;
var tw = 420;
var th = 440;
var k = 0.62;
var cv = createCanvas(cols * tw, 4 * th + 20);
var g = cv.getContext("2d");
g.fillStyle = "#cfe3f5";
g.fillRect(0, 0, cv.width, cv.height);
var tile = (i, row, s, e, label) => {
  const x = i * tw, y = row * th;
  g.save();
  g.beginPath();
  g.rect(x, y, tw, th);
  g.clip();
  g.translate(x + tw / 2 - 500 * k, y + 60);
  g.scale(k, k);
  drawClean(g, s, { expr: e, sweat: false });
  g.restore();
  g.fillStyle = "#241a1c";
  g.font = "bold 24px Arial";
  g.textAlign = "center";
  g.fillText(label, x + tw / 2, y + 30);
};
exprs.forEach((e, i) => tile(i % cols, Math.floor(i / cols), hero, e, e));
cast.forEach(([n, s, e], i) => tile(i, 3, s, e, `${n}: ${e}`));
fs.writeFileSync(out, cv.toBuffer("image/png"));
console.log("->", out);
