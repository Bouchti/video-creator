import React from 'react';
import {Arrow, C, Canvas, Circle, Curve, DiagramProps, Group, Label, Line, Path, Pulse, ease, lerp} from '../../diagram/kit';

export default function Diagram({t, w, h}: DiagramProps) {
  // phase 3: the bike tips, the front weight drops faster, the wheel steers (narrows as it turns)
  const tip = lerp(t, 109, 30, 0, -5);
  const bikeDrop = lerp(t, 109, 30, 0, 20);
  const ballDrop = lerp(t, 112, 18, 0, 70);
  const steer = ease(t, 136, 22);
  const rx = 220 - 100 * steer;
  const ell = (r: number, k: number): [number, number][] => {
    const pts: [number, number][] = [];
    for (let i = 0; i < 40; i++) {
      const a = (i / 40) * Math.PI * 2;
      pts.push([Math.cos(a) * r * k, Math.sin(a) * r]);
    }
    return pts;
  };
  const k = rx / 220;
  return (
    <Canvas t={t} w={w} h={h}>
      {/* ground */}
      <Line x1={120} y1={962} x2={1000} y2={962} stroke={C.ground} width={10} at={0} len={10} />
      <Group x={700} y={960} rotate={tip}>
        <Group x={-700} y={-960 + bikeDrop}>
          {/* frame tubes going back off to the left */}
          <Line x1={530} y1={330} x2={90} y2={385} stroke={C.ink} width={26} at={0} len={12} />
          <Line x1={530} y1={330} x2={90} y2={385} stroke={C.metal} width={14} at={4} len={12} />
          <Line x1={575} y1={455} x2={120} y2={820} stroke={C.ink} width={30} at={2} len={12} />
          <Line x1={575} y1={455} x2={120} y2={820} stroke={C.metal} width={18} at={6} len={12} />
          {/* front wheel (steers: squashes as it turns toward us) */}
          <Group x={700} y={740}>
            <Curve points={ell(220, k)} closed stroke={C.ink} width={30} at={0} len={16} />
            <Curve points={ell(196, k)} closed stroke={C.metal} width={8} at={6} len={12} />
            {[0, 30, 60, 90, 120, 150].map((d, i) => {
              const a = (d * Math.PI) / 180;
              return (
                <Line key={i} x1={-Math.cos(a) * 196 * k} y1={-Math.sin(a) * 196} x2={Math.cos(a) * 196 * k}
                  y2={Math.sin(a) * 196} stroke={C.metal} width={4} at={10 + i} len={8} />
              );
            })}
            <Circle cx={0} cy={0} r={22} fill={C.metal} at={12} len={8} />
          </Group>
          {/* fork from head tube down to the hub */}
          <Path d="M 578 465 Q 650 610 700 740" stroke={C.ink} width={26} at={8} len={12} />
          <Path d="M 578 465 Q 650 610 700 740" stroke={C.metal} width={12} at={12} len={10} />
          {/* head tube (the handlebar post) */}
          <Line x1={515} y1={290} x2={582} y2={478} stroke={C.ink} width={48} at={6} len={10} />
          <Line x1={515} y1={290} x2={582} y2={478} stroke={C.metal} width={30} at={10} len={10} />
          {/* stem and handlebars */}
          <Path d="M 512 285 L 498 235 L 430 225" stroke={C.ink} width={22} at={12} len={10} />
          <Line x1={430} y1={225} x2={400} y2={232} stroke={C.ink} width={34} at={18} len={6} />
          {/* 1) the tilted hinge: steering axis */}
          <Line x1={468} y1={160} x2={735} y2={915} stroke={C.accent} width={12} dashed at={72} len={14} />
          {/* 2) the front's weight: low, ahead of the hinge */}
          <Group x={770} y={640 + ballDrop}>
            <Circle cx={0} cy={0} r={58} fill={C.heat} stroke={C.ink} width={8} at={35} len={10} />
            <Path d="M -30 -25 Q -20 -40 0 -42" stroke={C.paper} width={10} at={42} len={6} />
          </Group>
        </Group>
      </Group>
      <Pulse cx={540} cy={380} r={90} at={77} color={C.accent} />
      <Label x={660} y={170} text="hinge" tone="accent" at={77} size={48} />
      <Label x={910} y={540} text="weight" tone="white" at={38} size={46} />
      {/* 3) front falls first ... and steers into the fall */}
      <Arrow x1={770} y1={760} x2={770} y2={880} color={C.bad} at={116} len={10} />
      <Label x={640} y={880} text="falls" tone="bad" at={118} size={44} />
      <Arrow x1={880} y1={630} x2={890} y2={900} color={C.good} at={136} len={16} bend={90} />
      <Label x={940} y={985} text="steers" tone="good" at={145} size={44} />
    </Canvas>
  );
}
