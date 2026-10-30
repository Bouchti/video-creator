import React from 'react';
import {Arrow, Box, C, Canvas, Circle, DiagramProps, Group, Label, Line, Mark, Pulse, ease, lerp} from '../../diagram/kit';

export default function Diagram({t, w, h}: DiagramProps) {
  // rider's weight tips left on 'tips', the bike's wheels roll back under it on 'wheels roll back under'
  const rx = lerp(t, 23, 18, 0, -110);
  const bx = lerp(t, 103, 26, 0, -110);
  const steer = lerp(t, 56, 18, 0, -25) + lerp(t, 116, 16, 0, 25);
  const fx = 540 + bx;
  const fy = 340;
  const rad = (steer * Math.PI) / 180;
  const grip = (s: number) => [fx + s * 110 * Math.cos(rad), fy + s * 110 * Math.sin(rad)];
  const gl = grip(-1);
  const gr = grip(1);
  const arrowFade = 1 - ease(t, 116, 12);

  // dotted turn path, starting at the front wheel and curving left
  const dots = Array.from({length: 8}, (_, i) => {
    const u = (i + 1) / 9;
    const x = (1 - u) * (1 - u) * 540 + 2 * u * (1 - u) * 535 + u * u * 420;
    const y = (1 - u) * (1 - u) * 230 + 2 * u * (1 - u) * 130 + u * u * 95;
    return {x, y, at: 77 + i * 2};
  });

  return (
    <Canvas t={t} w={w} h={h}>
      {/* the road scrolling past: the bike is rolling forward (up) */}
      {[130, 950].map((lx) =>
        Array.from({length: 6}, (_, i) => (
          <Box key={`${lx}-${i}`} x={lx - 10} y={70 + ((i * 160 + t * 8) % 880)} w={20} h={70} r={10}
               fill={C.paper} stroke={C.paper} width={2} at={0} len={6} opacity={0.5} />
        ))
      )}

      {/* the turn path */}
      {dots.map((d, i) => (
        <Circle key={i} cx={d.x} cy={d.y} r={11} fill={C.accent} stroke={C.accent} at={d.at} len={4} />
      ))}

      {/* the bike, seen from above (x-ray) */}
      <Group x={bx}>
        <Box x={515} y={660} w={50} h={240} r={25} fill={C.ink} stroke={C.ink} at={0} len={10} />
        <Box x={528} y={680} w={24} h={200} r={12} fill={C.metal} at={4} len={8} />
        <Box x={528} y={360} w={24} h={320} r={10} fill={C.metal} at={4} len={10} />
        <Box x={505} y={640} w={70} h={60} r={26} fill={C.ink} at={8} len={8} />
      </Group>

      {/* front wheel + handlebars: they steer */}
      <Group x={fx} y={fy} rotate={steer}>
        <Box x={-25} y={-120} w={50} h={240} r={25} fill={C.ink} stroke={C.ink} at={2} len={10} />
        <Box x={-12} y={-100} w={24} h={200} r={12} fill={C.metal} at={6} len={8} />
        <Box x={-120} y={-14} w={240} h={28} r={14} fill={C.accent} at={10} len={10} />
        <Circle cx={-118} cy={0} r={20} fill={C.ink} at={14} len={6} />
        <Circle cx={118} cy={0} r={20} fill={C.ink} at={14} len={6} />
      </Group>

      {/* rider (the weight), arms to the grips */}
      <Line x1={540 + rx - 85} y1={585} x2={gl[0]} y2={gl[1]} stroke={C.skin} width={22} at={12} len={8} />
      <Line x1={540 + rx + 85} y1={585} x2={gr[0]} y2={gr[1]} stroke={C.skin} width={22} at={12} len={8} />
      <Group x={540 + rx} y={600}>
        <Box x={-115} y={-45} w={230} h={90} r={45} fill={C.purple} at={10} len={10} />
        <Circle cx={0} cy={-10} r={50} fill={C.skin} at={14} len={8} />
      </Group>

      {/* 1) it tips left */}
      <Group opacity={arrowFade}>
        <Arrow x1={330} y1={600} x2={170} y2={600} color={C.bad} at={23} len={10} />
        <Label x={230} y={690} text="tips" tone="bad" at={26} />
      </Group>

      {/* 2) handlebars turn toward the fall */}
      <Pulse cx={fx} cy={fy} r={150} at={46} />
      <Label x={810} y={300} text="steer" tone="accent" at={58} />

      {/* 3-4) wheels roll back under it: upright again */}
      <Label x={790} y={880} text="back under" tone="good" at={121} />
      <Mark x={800} y={600} ok at={130} size={110} />
    </Canvas>
  );
}
