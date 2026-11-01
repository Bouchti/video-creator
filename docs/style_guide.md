# Build-It Studio: style guide

Built from `refs/style_reference.md` and the reference frames in `refs/frames/` (576x1024, upscaled
by 1.875 to our 1080x1920). The reference is the target **family**, not something to copy: we keep its
storytelling, pacing, look, camera grammar and overlay system, but use our own analogies, objects and wording.

## 1. Story: build the machine, don't show it

- **Never open on the finished machine.** Open on a cheap everyday object that is about to do something
  surprising (the reference uses a firecracker under a tin can). The payoff comes within 2 to 4 s (the can
  is blasted at the lens).
- The episode is a chain of loops: **analogy → problem → added part → payoff**. Each added part fixes the
  problem the previous loop just created.
  - The energy flies away, so put it in a tube.
  - The tube only pushes, so add a rod and a crank.
  - There's no more fuel, so add a head, fuel and air.
  - The explosion is weak, so compress first.
  - One bang per two turns, so add four cylinders.
  - Then gas, noise, heat, starting, and finally the car.
- The reference runs about 9 loops in 85 s, so about 9 s per loop. Each loop has a short problem line
  ("Sauf que…", "But…") and a short fix line ("Alors tu…", "So you…").
- **One visual through-line.** The everyday object becomes the real part (the can becomes the piston), so
  the viewer never loses track of it.
- **Milestone pull-backs:** at about 12 s (a tiny tube next to a big wheel: "we need rotation"), 48 s (four
  cylinders) and 82 s (the engine in a car chassis). The ending is the full machine running, with a green
  "done" pill.
- **Voice:** second person ("you light it", "you add"), present tense, short sentences, informal and
  playful, with no jargon until the part is on screen; then name it once, as a label.

## 2. Set and light

- **Seamless studio.**
  - Backdrop: a vertical gradient from warm grey-beige (`#beb4ab`) down to taupe (`#938980`), slightly
    darker in the top corners (a natural vignette) and brightest behind the subject.
  - Floor: sandy brown (`#8c7b66` → `#74614e`).
  - There is **no visible horizon line**: the floor dissolves into the backdrop through haze.
- **Ground haze** is the signature. A low, lumpy layer of soft fog or dust clouds lies on the floor, like
  cloud tops seen from above. It catches the key light, partly hides the floor plane, and parts sit
  slightly "in" it. It gives depth and the dreamy, premium feel.
- **Lighting:**
  - a big soft key from the upper front-left;
  - a warm bounce from the floor;
  - soft, broad contact shadows (the can's shadow at 4–7 s is a dark soft ellipse);
  - low contrast, bright overall, never dark or dramatic.
- **Mood washes:** heat or energy is shown by a **warm yellow wash on the backdrop** (58 s, 70 s) and an
  orange spill on the floor under explosions.
- **Grade:** warm, slightly desaturated, soft highlights with a gentle bloom on glows and specular hits.

## 3. Materials and shapes

| Role | Look |
|---|---|
| Pistons, head plate, rings | Brushed aluminium with **strong visible brushing** (linear on flats, circular on caps), bright anisotropic streaks |
| Rims, rings, pins | Polished chrome |
| Head cover, accents | Glossy candy red (`#b8141c`-ish) with sharp highlights |
| Crank, rods, exhaust, tyres | Dark graphite or satin black, with metal bearing pins showing at the ends |
| Housings | **Clear glass** with a faint tint, thick bevelled edges and chrome rings at each end: we see inside without cutting anything |
| Base | Matte black plinth |
| Glow | Warm emissive (`#ffb060`), with bloom |

- **Shapes:** chunky, simplified and toy-like, but solid and believable. Every edge has a generous bevel and
  nothing is a bare primitive. There is less detail than real engineering, but each part reads at a glance.
- **Particles:**
  - fuel and air mist: hundreds of small warm-yellow glowing dots;
  - injected fuel: larger white droplets in an arc;
  - air: white or blue specks;
  - sound: translucent blue concentric rings;
  - exhaust: light smoke.
- **Explosion:** a bright white-yellow sphere of light in the chamber with a warm bloom and floor spill. It
  is quick, then fades. Hot parts tint peach or orange.

## 4. Camera and animation

- **Framing:**
  - mostly front-on, slightly above the subject (about 10–20°);
  - long-lens feel, low perspective distortion;
  - subject centred, filling 35–60% of the frame height;
  - extreme close-ups fill the frame (the piston crown and particle cloud at 30–32 s);
  - reveal pull-backs make the subject tiny.
- **Moves:**
  - slow eased push-ins, pull-backs and lateral reframes, with no fast orbits;
  - a new framing or a new object at least every 2 s;
  - the camera arrives on the word that introduces the part.
- **Depth of field:** shallow on close-ups (background and haze go creamy), deep on wide shots. Motion blur
  on fast parts (the rising piston smears).
- **Assembly:** parts **drop in from above, slide in from the side or pop in**, overshoot slightly and
  settle, then start working at once. The mechanism keeps running under the narration.

## 5. Captions

- **One to two words at a time**, sentence case (not uppercase), white, very heavy rounded sans (Poppins
  Black or Montserrat ExtraBold class) with a dark outline and a soft drop shadow.
  - About 34 px in the 576-px reference, so **about 64 px at 1080 wide**.
- Horizontally centred at about 67% of the height: **y ≈ 1250–1300** at 1920. The position is fixed; the
  captions never move with the action.
- Each word pops in (scale about 0.9 → 1.0 in about 80 ms), timed to word timestamps.

## 6. Label pills

- Small rounded rectangles in bold uppercase, about 20 px in the reference, so **about 36 px at 1080**.
  They often carry a tiny icon.
- Variants:
  - **neutral:** white fill, dark text, dark outline (VILEBREQUIN, LE MÊME MOUVEMENT, 1er TOUR);
  - **warning / energy:** cream fill, orange outline, flame icon (ÇA TAPE FORT !, 100 EXPLOSIONS / SECONDE);
  - **air / cold:** light-blue fill and outline, wind icon (AIR);
  - **done:** mint fill, green outline, check icon (MOTEUR ✓);
  - **dark chip:** for a number beside a bracket (÷10, VOLUME).
- Placed **beside** the part (upper area or to the right), never on top of it. A thin leader line or a
  square bracket marks a span (the gas height before and after compression).
- A pill pops or fades in on its word, stays for the beat, then leaves. There is at most one or two on
  screen at a time.
- Numeric gauges are allowed as props (a tachometer dial floating above the engine).

## 7. Pacing and sound

- A visual change every 1.5–2 s. Captions change roughly every 0.4–0.6 s. Short silences only at loop
  turns.
- Sound (inferred): conversational narration on top; light, upbeat music well underneath; small SFX on
  events (pops and clicks for parts landing, a soft "fwoomp" for explosions, mechanical whirr, exhaust
  puffs).

## 8. Safe zones and differences from the reference

- Keep captions, pills and the subject inside y 150–1550, and out of the right-hand 140 px (TikTok UI).
  The reference puts some content in the bottom area; we don't.
- Our own design details:
  - our analogies and objects (no fruit-label can);
  - our own font pairing;
  - a loop or call-to-action ending instead of the platform end card.
