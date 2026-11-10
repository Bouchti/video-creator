// Character sheet for the Emu War short (art checks only): every emu mode + the 1932 cast on one 2D canvas.
import React, { useLayoutEffect, useRef } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Pen, bodyFront, bodySide, MAJOR, gunner, farmer, MINISTER, CAMERAMAN, mp } from "./toon";
import { emuSide, emuFront, EmuOpts } from "./emudraw";

const cell = (g: CanvasRenderingContext2D, x: number, y: number, s: number, draw: (p: Pen) => void) => {
  g.save(); g.translate(x, y); g.scale(s, s); draw(new Pen(g)); g.restore();
};

export const EmuSheet: React.FC = () => {
  const ref = useRef<HTMLCanvasElement>(null);
  const f = useCurrentFrame();
  useLayoutEffect(() => {
    const g = ref.current!.getContext("2d")!;
    g.fillStyle = "#cfe3f2"; g.fillRect(0, 0, 1080, 1920);
    const ph = (f % 30) / 30;
    const emus: EmuOpts[] = [
      { mode: "stand" }, { mode: "walk", phase: ph }, { mode: "run", phase: ph }, { mode: "peck", phase: ph },
      { mode: "look", dark: true }, { mode: "alarm", dark: true, eye: "shock" }, { mode: "salute", hat: "slouch", eye: "proud" }, { mode: "stand", hat: "slouch", eye: "smug" },
    ];
    emus.forEach((o, i) => cell(g, (i % 4) * 270, Math.floor(i / 4) * 280, 0.27, (p) => emuSide(p, { ...o, seed: i + 1 })));
    const fr: EmuOpts[] = [{ mode: "stand" }, { mode: "look", dark: true, eye: "shock" }, { mode: "salute", hat: "slouch", eye: "proud" }, { mode: "stand", hat: "slouch", eye: "smug" }];
    fr.forEach((o, i) => cell(g, i * 270, 570, 0.27, (p) => emuFront(p, { ...o, seed: i + 3 })));
    const people = [
      (p: Pen) => bodyFront(p, MAJOR, { mode: "stand", expr: "grin", prop: "point", facing: 1 }),
      (p: Pen) => bodyFront(p, gunner(0), { mode: "stand", expr: "smile", prop: "salute" }),
      (p: Pen) => bodyFront(p, gunner(1), { mode: "stand", expr: "dazed" }),
      (p: Pen) => bodyFront(p, farmer(0), { mode: "stand", expr: "stern", prop: "hatInHand" }),
      (p: Pen) => bodyFront(p, farmer(1), { mode: "stand", expr: "nervous" }),
      (p: Pen) => bodyFront(p, MINISTER, { mode: "stand", expr: "smile" }),
      (p: Pen) => bodyFront(p, CAMERAMAN, { mode: "stand", expr: "grin", prop: ["crank", ph] }),
      (p: Pen) => bodyFront(p, mp(1), { mode: "stand", expr: "laugh", prop: ["scratch", 0.5] }),
      (p: Pen) => bodySide(p, gunner(0), { mode: "push", pose: 1, expr: "grin" }),
      (p: Pen) => bodySide(p, MAJOR, { mode: "march", phase: ph, expr: "stern" }),
      (p: Pen) => bodySide(p, farmer(2), { mode: "stand", expr: "shock" }),
      (p: Pen) => bodyFront(p, MAJOR, { mode: "stand", expr: "relief", prop: "pen" }),
    ];
    people.forEach((d, i) => cell(g, (i % 6) * 180, 860 + Math.floor(i / 6) * 330, 0.3, d));
  }, [f]);
  return <AbsoluteFill><canvas ref={ref} width={1080} height={1920} /></AbsoluteFill>;
};
