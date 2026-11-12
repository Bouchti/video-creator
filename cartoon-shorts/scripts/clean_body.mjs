// scripts/clean_body.ts
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
var shade = (hex, k) => {
  const n = parseInt(hex.slice(1), 16), c = [n >> 16 & 255, n >> 8 & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(k >= 1 ? v + (255 - v) * (k - 1) : v * k))));
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
var bodyPath = (g2, inset = 0) => {
  const t = BODY_T + inset, b = BODY_B - inset, w0 = 0.64 * R - inset, w1 = 0.98 * R - inset, h = b - t;
  begin(g2);
  g2.moveTo(CX - w0, t + 0.08 * h);
  g2.bezierCurveTo(CX - w0, t - 0.02 * h, CX + w0, t - 0.02 * h, CX + w0, t + 0.08 * h);
  g2.bezierCurveTo(CX + w0 + 0.06 * R, t + 0.4 * h, CX + w1, t + 0.62 * h, CX + w1, t + 0.8 * h);
  g2.bezierCurveTo(CX + w1, b + 0.04 * h, CX - w1, b + 0.04 * h, CX - w1, t + 0.8 * h);
  g2.bezierCurveTo(CX - w1, t + 0.62 * h, CX - w0 - 0.06 * R, t + 0.4 * h, CX - w0, t + 0.08 * h);
  g2.closePath();
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
      line(g2, [[CX, BODY_T + 1 * R], [CX, BODY_B]], 6, INK);
      for (let k = 0; k < 3; k++) circle(g2, CX + 0.1 * R, BODY_T + (1.25 + 0.42 * k) * R, 9), fillInk(g2, shade(base, 0.85), 4);
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
      for (let k = 0; k < 2; k++) circle(g2, CX + 0.08 * R, BODY_T + (1.15 + 0.4 * k) * R, 9), fillInk(g2, shade(base, 0.6), 4);
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
      for (let k = 0; k < 3; k++) {
        const by = BODY_T + (0.75 + 0.62 * k) * R;
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
      for (let k = 0; k < 3; k++) circle(g2, CX, BODY_T + (0.5 + 0.35 * k) * R, 8), fillInk(g2, "#ffffff", 4);
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
      for (let k = 0; k <= 14; k++) {
        const u = k / 14, x = (1 - u) * (1 - u) * (CX - 0.55 * R) + 2 * u * (1 - u) * (CX - 0.1 * R) + u * u * (CX + 0.45 * R), y = (1 - u) * (1 - u) * (BODY_T + 1.05 * R) + 2 * u * (1 - u) * (BODY_T + 1.45 * R) + u * u * (BODY_T + 1 * R);
        begin(g2);
        g2.ellipse(x, y, 13, 9, k % 2 ? 0.6 : -0.6, 0, Math.PI * 2);
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
    if (s.outfit !== "dress" && s.outfit !== "overalls") {
      const hem = BODY_B - 0.55 * R;
      g2.fillStyle = s.pants ?? "#4a3426";
      g2.fillRect(CX - 2 * R, hem, 4 * R, R);
      line(g2, [[CX - 1.2 * R, hem], [CX + 1.2 * R, hem]], 9, INK);
      line(g2, [[CX - 1.2 * R, hem + 0.22 * R], [CX + 1.2 * R, hem + 0.22 * R]], 4, "rgba(0,0,0,0.25)");
      if (s.suspenders) for (const sd of [-1, 1]) {
        const x02 = CX + sd * 0.42 * R + sd * 6;
        begin(g2);
        g2.rect(x02 - 24, hem - 46, 48, 40);
        fillInk(g2, "#d9a640", 5);
        begin(g2);
        g2.rect(x02 - 12, hem - 36, 24, 20);
        g2.fillStyle = shade("#d9a640", 0.6);
        g2.fill();
      }
    }
    const x0 = CX - 1 * R, x1 = CX + 1 * R;
    const cyl = g2.createLinearGradient(x0, 0, x1, 0);
    cyl.addColorStop(0, "rgba(255,255,255,0.0)");
    cyl.addColorStop(0.18, "rgba(255,255,255,0.10)");
    cyl.addColorStop(0.42, "rgba(255,255,255,0)");
    cyl.addColorStop(0.7, "rgba(10,20,30,0.14)");
    cyl.addColorStop(1, "rgba(10,20,30,0.36)");
    g2.fillStyle = cyl;
    g2.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, BODY_B - BODY_T + 120);
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
    const vert = g2.createLinearGradient(0, BODY_T, 0, BODY_B);
    vert.addColorStop(0, "rgba(255,255,255,0.06)");
    vert.addColorStop(0.55, "rgba(255,255,255,0)");
    vert.addColorStop(1, "rgba(20,14,30,0.22)");
    g2.fillStyle = vert;
    g2.fillRect(CX - 2 * R, BODY_T - 60, 4 * R, BODY_B - BODY_T + 120);
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
var keyLight = (g2, cx, cy, r, k = 1) => {
  const gr = g2.createRadialGradient(cx - 0.16 * r, cy - 0.3 * r, 0.05 * r, cx - 0.08 * r, cy - 0.12 * r, 1.12 * r);
  gr.addColorStop(0, "rgba(255,255,255,0)");
  gr.addColorStop(0.45, `rgba(92,84,100,${0.03 * k})`);
  gr.addColorStop(0.8, `rgba(84,76,96,${0.13 * k})`);
  gr.addColorStop(1, `rgba(72,64,88,${0.26 * k})`);
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
    if (s.hair === "side" || s.hair === "bob") brimShadow(g2, HY - 0.5 * R);
  });
  headPath(g2);
  inkStroke(g2, W_INK);
};
var hair = (g2, s) => {
  if (s.hat && s.hat !== "none") return;
  const c = s.hairCol ?? "#2a1c18", hi = shade(c, 1.5);
  if (!s.hair || s.hair === "none" || s.hair === "bald") {
    if (s.hair === "bald") for (const sd of [-1, 1]) {
      begin(g2);
      g2.ellipse(CX + sd * 0.98 * R, HY + 0.05 * R, 0.1 * R, 0.24 * R, 0, 0, Math.PI * 2);
      fillInk(g2, "#c9c3b5", 6);
    }
    return;
  }
  if (s.hair === "side" || s.hair === "bob") {
    begin(g2);
    g2.moveTo(CX - 1.02 * R, HY + (s.hair === "bob" ? 0.45 : 0.05) * R);
    g2.bezierCurveTo(CX - 1.15 * R, HY - 1.2 * R, CX + 1.15 * R, HY - 1.25 * R, CX + 1.03 * R, HY + (s.hair === "bob" ? 0.45 : -0.05) * R);
    g2.bezierCurveTo(CX + 0.7 * R, HY - 0.55 * R, CX - 0.1 * R, HY - 0.75 * R, CX - 0.35 * R, HY - 0.48 * R);
    g2.bezierCurveTo(CX - 0.6 * R, HY - 0.6 * R, CX - 0.9 * R, HY - 0.35 * R, CX - 1.02 * R, HY + (s.hair === "bob" ? 0.45 : 0.05) * R);
    g2.closePath();
    fillInk(g2, c, W_INK);
    line(g2, [[CX - 0.35 * R, HY - 0.5 * R], [CX - 0.3 * R, HY - 0.92 * R]], 7, hi);
    line(g2, [[CX + 0.2 * R, HY - 0.6 * R], [CX + 0.45 * R, HY - 0.88 * R]], 6, hi);
  } else if (s.hair === "tuft") {
    for (let k = 0; k < 3; k++) line(g2, [[CX - 0.1 * R + k * 0.1 * R, HY - 0.98 * R], [CX - 0.18 * R + k * 0.14 * R, HY - 1.22 * R]], 10, c);
  } else if (s.hair === "curly") {
    for (let k = 0; k < 9; k++) {
      const a = Math.PI * (1.05 + 0.9 * k / 8);
      circle(g2, CX + 0.92 * R * Math.cos(a), HY + 0.85 * R * Math.sin(a), 0.22 * R);
      fillInk(g2, c, 8);
    }
  }
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
    for (let k = -4; k <= 4; k++) line(g2, [[CX + k * 0.22 * R, HY - 0.46 * R], [CX + k * 0.22 * R, HY - 0.27 * R]], 4, SEAM);
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
    if (s.hatPattern === "stripes") for (let k = -6; k <= 6; k++) {
      begin(g2);
      g2.moveTo(CX + k * 0.17 * R, HY - 0.2 * R);
      g2.quadraticCurveTo(CX + k * 0.13 * R, HY - 0.8 * R, CX + k * 0.05 * R, HY - 1.3 * R);
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
var face = (g2, s, p) => {
  if ((s.eyes ?? "almond") === "almond" && !["shock", "grimace"].includes(p.expr ?? "neutral") && !s.glasses) return faceAlmond(g2, s, p);
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
      const k = e === "angry" ? 1 : -1;
      line(g2, [[x - sd * 0.18 * R, ey - er - 0.08 * R + k * 0.06 * R], [x + sd * 0.16 * R, ey - er - 0.08 * R - k * 0.06 * R]], 11);
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
    for (const k of [-1, 0, 1]) line(g2, [[CX + k * 0.1 * R, my - 0.02 * R], [CX + k * 0.1 * R, my + 0.18 * R]], 5);
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
  const sx = CX + sd * 0.6 * R, sy = BODY_T + 0.28 * R, r1 = (a * 0.7 + 24) * Math.PI / 180, r2 = (a - 2) * Math.PI / 180, L1 = 1.15 * R, L2 = 1.12 * R;
  const ex = sx + sd * Math.sin(r1) * L1, ey = sy + Math.cos(r1) * L1, hx = ex + sd * Math.sin(r2) * L2, hy = ey + Math.cos(r2) * L2;
  return [[sx, sy], [ex, ey], [hx, hy]];
};
var drawArm = (g2, s, sd, a) => {
  const pts = armPts(sd, a), c = s.limb ?? "#2a1a14";
  noodle(g2, pts, LIMB_W, c);
  const [hx, hy] = pts[2];
  if (s.mittens !== false) mitten(g2, hx, hy, sd);
  else {
    circle(g2, hx, hy, LIMB_W * 0.62);
    g2.fillStyle = c;
    g2.fill();
  }
};
var armAngles = (p) => [p.armL ?? 6, p.wave !== void 0 ? 150 + 20 * p.wave : p.armR ?? 6];
var legs = (g2, s, p) => {
  const c = s.limb ?? "#2a1a14", kn = p.knee ?? 0;
  for (const sd of [-1, 1]) {
    const hx = CX + sd * 0.24 * R, hy = BODY_B - 0.2 * R, ax = CX + sd * 0.26 * R, ay = FEET - 0.1 * R;
    const kx = CX + sd * (0.3 * R) + kn * 0.32 * R, ky = (hy + ay) / 2 + 0.05 * R;
    noodle(g2, [[hx, hy], [kx, ky], [ax, ay], [ax + sd * 0.2 * R, FEET - 0.05 * R]], LIMB_W * 0.92, c);
  }
};
var drawClean = (g2, s, p = {}) => {
  g2.save();
  if (p.tilt) {
    g2.translate(CX, FEET);
    g2.rotate(p.tilt * Math.PI / 180);
    g2.translate(-CX, -FEET);
  }
  legs(g2, s, p);
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
  head(g2, s);
  hair(g2, s);
  const yaw = p.yaw ?? 0;
  if (yaw && s.hair !== "none" && s.hair !== "bald") withClip(g2, () => headPath(g2), () => {
    const bx = CX - Math.sign(yaw) * 0.95 * R;
    begin(g2);
    g2.ellipse(bx, HY - 0.05 * R, 0.32 * R * Math.min(1, Math.abs(yaw) * 2), 0.5 * R, 0, 0, Math.PI * 2);
    fillInk(g2, s.hairCol ?? "#5a3418", 8);
  });
  face(g2, s, p);
  hat(g2, s);
  hatPaint(g2, s);
  g2.restore();
};

// scripts/clean_body.ts
var out = process.argv[2] ?? "out/clean_body.png";
var cv = createCanvas(700, 800);
var g = cv.getContext("2d");
var bg = g.createLinearGradient(0, 0, 0, 800);
bg.addColorStop(0, "#d9682a");
bg.addColorStop(0.55, "#e8a060");
bg.addColorStop(1, "#b0705a");
g.fillStyle = bg;
g.fillRect(0, 0, 700, 800);
g.save();
g.translate(-30, -377);
g.scale(0.76, 0.76);
drawClean(g, { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#24a89a", trim: "#5a3a22", neckerchief: "#c0353a", hair: "side", hairCol: "#5a3418", suspenders: "#3a2418", pants: "#4a3426" }, { expr: "deadpan", yaw: 0.3, armL: 6, armR: 6, knee: 0.3 });
g.restore();
fs.writeFileSync(out, cv.toBuffer("image/png"));
console.log("->", out);
