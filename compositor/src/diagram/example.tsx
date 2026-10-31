// THE STYLE REFERENCE the diagram agent is shown (agents/diagram_writer.py): a different subject on purpose,
// so it copies the quality, not the content. "Why does ice float?" in one short animation.
import React from 'react';
import {Arrow, Box, C, Canvas, DiagramProps, Group, Label, Path, Pulse, lerp} from './kit';

export default function Diagram({t, w, h}: DiagramProps) {
  // the cube drops in (frames 10-30), then bobs and settles with its top above the waterline
  const settle = t < 30 ? 0 : 14 * Math.sin((t - 30) / 5) * Math.exp(-(t - 30) / 18);
  const y = lerp(t, 10, 20, 140, 585) + settle;   // most of the cube under the waterline (y 520)
  const tilt = lerp(t, 10, 20, -12, 0) + settle * 0.4;
  return (
    <Canvas t={t} w={w} h={h}>
      {/* the glass, cut open: a recognisable object, big, simplified to what matters */}
      <Path d="M 300 260 L 340 920 Q 345 960 390 960 L 690 960 Q 735 960 740 920 L 780 260" fill={C.air} at={0} len={14} />
      {/* the water, below the waterline at y = 520 */}
      <Path d="M 318 520 L 762 520 L 742 915 Q 738 945 700 945 L 380 945 Q 342 945 338 915 Z" fill={C.water} stroke={C.ink} width={8} at={4} len={12} />
      <Group x={540} y={y} rotate={tilt}>
        <Box x={-95} y={-95} w={190} h={190} r={30} fill={C.cold} at={10} len={10} />
        <Path d="M -55 -55 L -15 -55" stroke={C.paper} width={14} at={16} len={6} />
      </Group>
      {/* cause -> effect, each on its word: the water pushes UP (good), the ice's weight pulls DOWN (bad) */}
      <Arrow x1={540} y1={860} x2={540} y2={640} color={C.good} at={50} />
      <Arrow x1={700} y1={300} x2={700} y2={410} color={C.bad} at={62} width={14} />
      <Label x={540} y={900} text="water pushes up" tone="good" at={54} />
      <Label x={790} y={250} text="weight" tone="bad" at={64} />
      {/* the take-away, last, where nothing else is */}
      <Pulse cx={540} cy={585} r={140} at={80} />
      <Label x={540} y={160} text="ice is lighter" tone="accent" at={84} size={56} />
    </Canvas>
  );
}
