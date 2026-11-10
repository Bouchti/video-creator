# River Garden: shot sheet

Generate keyframes in order. K0 is text-to-image; every later keyframe is a FLUX 3 **edit** of the one named as its input, so the house, fence, lawn and river stay identical (this is what creates the 'same garden, getting worse' effect).

## Keyframes (FLUX 3 local, 9:16, 1080x1920)

### K0  ·  FLUX 3 text-to-image (local)

High aerial three-quarter view from about 25 metres up, looking down the length of the back garden: a modern two-storey countryside house with grey roof, cream render and timber cladding sits at the top of the frame, its patio and back door facing the camera; a long rectangular lawn fills the middle of the frame, bordered by a timber fence on both sides; beyond the bottom fence a wide green river flows left to right across the bottom of the frame between grassy banks. A yellow tracked excavator stands on the lawn near the bottom fence. A winding line of orange marker paint runs from the riverbank, through a gap in the fence, curving across the lawn to a marked oval near the patio. Bright late-morning sun, clear blue sky, soft shadows. Photorealistic architectural 3D visualization, Unreal Engine 5 quality, highly detailed grass, water and stone textures, crisp focus, natural colour, vertical 9:16 composition.

### K1  ·  FLUX 3 edit (local), input = K0

Keep the exact same camera, house, fence, lawn and river. Replace the orange paint line with a freshly dug winding channel about two metres wide and one metre deep with raw brown earth walls, ending in a large oval pit beside the patio. Spoil heaps of soil beside the channel. Leave a narrow wall of earth at the river end so the channel is still dry. The excavator now sits beside the pit. Same lighting.

### K2  ·  FLUX 3 edit (local), input = K1

Keep the exact same camera, house, fence and river. The earth wall is gone: clear green river water fills the whole winding channel and the oval pit, which is now a landscaped pond with stepping stones, a small timber footbridge over the stream, and a dark timber water wheel turning beside the patio. Spoil heaps removed, lawn neat, excavator gone. Warm golden-hour sunlight, long soft shadows.

### K3  ·  FLUX 3 edit (local), input = K2

Keep the house, fence and river. Same water garden, but weeks later: the stream water is now murky brown, the banks on the outside of every bend are eaten away and undercut, turf edges collapsing into the water, the stream noticeably wider, bare mud showing along the edges, a fence post leaning. Overcast flat daylight.

### K4  ·  FLUX 3 edit (local), input = K3

Keep the exact same camera, house, fence and river. Both banks of the stream and the pond edge are now armoured with large grey granite boulders, a continuous wall of rock along every bend. The yellow excavator is back, holding a boulder in its bucket near the river end. The water is clear green again. Bright midday sun.

### K5  ·  FLUX 3 edit (local), input = K4

Keep the exact same camera, house, fence, rock-lined stream and pond. Excavator gone. Night has fallen in spring storm conditions: low dark grey clouds, heavy rain streaks, the river at the bottom of the frame swollen, fast, muddy brown, risen right to the top of its banks with white water, flooding the meadow beyond. Garden lights glowing on the patio.

### K6  ·  FLUX 3 edit (local), input = K5

Keep the exact same camera, house and fence. The swollen brown river is now pouring through the gap in the fence and down the channel as a raging torrent, overtopping the boulders, spreading across the lawn in sheets of brown water; the pond has burst its edge and floodwater is reaching the patio and the back door. Storm, rain, dark clouds.

### K7  ·  FLUX 3 edit (local), input = K6

Same house in the same storm, but now an interior view at ankle height looking down the ground-floor hallway toward the open back door: fast muddy brown floodwater surging through the doorway and along the oak floor, a rug lifting, light from a lamp reflecting on the water. Cinematic, dim, wet.

### K8  ·  FLUX 3 edit (local), input = K6

Pull far back and higher: the same house seen from 80 metres up at dusk in the storm, now in the middle of a suburban street. The river has broken through the back garden and runs down the street between the houses as a wide brown flood, cars half submerged, a red hatchback floating, garden fences flattened, neighbouring gardens under water. Grey rain, emergency lights glowing.

## Motion clips (MiniMax H3 local, image-to-video)

| Clip | Narration | First frame | Last frame | Length | Camera |
|---|---|---|---|---|---|
| c1 | s1-s2 | K0 | K1 | 10s | establishing, static |
| c2 | s3-s4 | K1 | K2 | 8s | establishing, dolly_in |
| c3 | s4 | K2 | (free) | 5s | wide, crane_down |
| c4 | s5 | K2 | K3 | 9s | wide, static |
| c5 | s6 | K3 | K4 | 6s | wide, static |
| c6 | s7 | K4 | K5 | 8s | establishing, static |
| c7 | s8 | K5 | K6 | 7s | establishing, dolly_in |
| c8 | s9 | K7 | (free) | 5s | close_up, dolly_in |
| c9 | s10-s11 | K8 | (free) | 10s | extreme_wide, crane_up |

**c1.** The yellow excavator digs along the painted line, bucket scooping earth, the winding channel growing from the river toward the patio in fast time-lapse; spoil heaps build up. Camera locked high aerial, very slow push in. Sound of diesel engine and digging.

**c2.** The excavator bucket breaks the last wall of earth; river water bursts into the channel, rushes along every bend and floods the pit, which transforms into a calm landscaped pond as the light turns golden; the water wheel starts turning. Slow push in. Rushing water sound.

**c3.** Gentle golden-hour drift: koi glide in the clear pond, the timber water wheel turns steadily dripping water, ripples sparkle. Camera cranes down slowly toward the pond. Birdsong, trickling water.

**c4.** Time-lapse over weeks: the stream water clouds to brown, the outside of each bend erodes, chunks of turf break off and slide into the water, the channel widens, sky turns overcast. Locked camera. Low rumbling water.

**c5.** Fast time-lapse: the excavator returns and lines both banks with large grey boulders, rock by rock, the water clearing to green. Locked aerial camera. Clunks of stone.

**c6.** Time-lapse from bright day to stormy night: clouds roll in, rain begins, the river at the bottom of the frame swells, turns brown and rises to the top of its banks. Locked camera. Thunder, rising roar of water.

**c7.** The flooded river surges through the fence gap into the channel, white water overtops the boulders and spreads across the lawn toward the house in sheets. Slow push in toward the patio. Roaring torrent, rain.

**c8.** Muddy floodwater surges through the open back door and races down the hallway toward camera, a rug lifts and floats, water splashing up the walls. Low ankle-height camera pushing forward. Rushing water, indoor echo.

**c9.** Slow rising aerial over the flooded street at dusk: the brown river flows between houses, the red hatchback drifts, emergency lights flash, rain falls. Camera cranes up and pulls back to reveal the whole neighbourhood under water. Rain, distant sirens.

## Narration

**s1 (0-4.5s, Hook).** You live forty metres from a river. So you do the obvious thing.
**s2 (4.5-10s, Dig).** You dig a channel right through your back garden, all the way to your patio.
**s3 (10-15s, Let it in).** Then you knock out the last wall of dirt, and let the river in.
**s4 (15-23s, Paradise).** And it's perfect. A stream, a pond, a water wheel turning by your back door. Fresh water, all year round, for free.
**s5 (23-32s, Erosion).** But moving water never stops working. Every second it carries a little of your soil away. The bends get wider, the banks cave in.
**s6 (32-37s, Armour).** So you fight back. Tonnes of granite along every bank.
**s7 (37-45s, Rise).** And it holds. Until spring. Snow melts upstream, and overnight the river rises two metres.
**s8 (45-52s, Torrent).** And you just built it the easiest path in the valley. Now the whole river wants your garden.
**s9 (52-58s, Inside).** It pours over the rocks, across the lawn, and straight through your back door.
**s10 (58-64s, Street).** And since your garden opens onto the street, it doesn't stop at your house.
**s11 (64-68s, Payoff).** Turns out you didn't borrow a river. You moved it.
