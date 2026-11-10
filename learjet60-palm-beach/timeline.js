// The one timeline: picture, score, foley, voice and subtitles all read these numbers.
// 80 BPM, 4/4: one beat = 0.75 s, one bar = 3 s. Key actions sit on beats (tools/cuecheck.py checks).
export const BPM = 80;
export const BEAT = 60 / BPM;
export const b = n => +(n * BEAT).toFixed(4);          // beat number -> seconds

export const T = {
  paint: 0,            // a scan paints the neighbourhood in
  lock: b(2),          // 1.5   reticle locks on the impact point
  stamp: b(3),         // 2.25  reading: 12:51 (on the spoken time)
  climb: b(12),        // 9.0   climb to orbit; colour returns; bass enters
  route0: b(17),       // 12.75 orbit over the Gulf
  austin: b(19),       // 14.25 Austin marked (on "Austin"), the route starts to grow
  bahamas: b(21),      // 15.75 destination marked (on "Bahamas")
  cruise: b(23),       // 17.25 reading lands: 35,000 ft (on the spoken number)
  routeEnd: b(24),     // 18.0  the route reaches Palm Beach
  storm0: b(26),       // 19.5  descent towards Palm Beach County
  low: b(28.75),       // 21.56 the descent reaches the storm (150 km)
  radar: [b(28.5), b(29.5), b(30.5), b(31.5)],   // 21.375 .. 23.625  radar scans 17:30, 17:35, 17:40, 17:45 UTC (12:30-12:45 EST)
  r1247: b(32),        // 24.0  12:47 stamp: crew reports turbulence and icing
  req370: b(38),       // 28.5  climb to 37,000 ft requested
  hush: b(41),         // 30.75 suck-out: music and foley stop (silence 1)
  dive0: b(45),        // 33.75 the dive: first sound after the silence
  logOver: b(48),      // 36.0  log: overspeed reported
  log20k: b(50),       // 37.5  log: descending 20,000 ft/min
  logMay: b(53),       // 39.75 log: mayday
  land8750: b(60),     // 45.0  the reading lands on 8,750 ft
  impact: b(61),       // 45.75 impact stamp; low hit, then silence 2
  ring: b(62),         // 46.5  impact ring prints
  trail0: b(64),       // 48.0  Military Trail traced
  trail1: b(66),       // 49.5
  res600: b(67),       // 50.25  reading: about 600 residents displaced
  breakup: b(73),      // 54.75 NTSB note: possible break-up before impact
  out0: b(76),         // 57.0  climb back to orbit
  end: b(79),          // 59.25 the reticle opens into the end card
  dur: 65.0,
};

// narration: start times fitted to the real Kokoro durations (voice/out/dur.json); tools/cues.mjs checks overlaps.
// `parts`: the subtitle cues each line is split into, timed from the word timestamps (voice/out/words.json).
export const VO = [
  { id: 'l1', t: 0.6, parts: ['Sunday, November 1, 12:51 p.m.', 'A business jet struck this neighborhood', 'in Palm Beach County, almost straight down.'] },
  { id: 'l2', t: 9.75, parts: ['All nine people on board were killed.'] },
  { id: 'l3', t: 12.75, parts: ['The Learjet 60 had left Austin, Texas, for the Bahamas,', 'cruising at 35,000 feet.'] },
  { id: 'l4', t: 19.55, parts: ['Over South Florida, it flew into a line of thunderstorms.'] },
  { id: 'l5', t: 23.62, parts: ['At 12:47, the crew reported turbulence and icing,', 'and asked to climb to 37,000 feet.'] },
  { id: 'l6', t: 31.6, parts: ['Moments later, the jet began to dive.'] },
  { id: 'l7', t: 34.85, parts: ['The pilots reported an overspeed,', 'a descent of 20,000 feet a minute, and called mayday.'] },
  { id: 'l8', t: 40.9, parts: ['In about one minute, it fell from 35,000 feet', 'to under 9,000.'] },
  { id: 'l9', t: 47.6, parts: ['It came down beside Military Trail.', 'About 600 residents were displaced.'] },
  { id: 'l10', t: 52.95, parts: ['Investigators see signs the jet may have begun', 'breaking apart before impact.'] },
  { id: 'l11', t: 58.4, parts: ['The cause is not yet known.', 'The NTSB hopes to recover the cockpit voice recorder.'] },
];

// places (lon, lat)
export const P = {
  site: [-80.113111, 26.632889],     // impact point, near Military Trail and 10th Avenue North (reports)
  austin: [-97.6699, 30.1945],       // Austin-Bergstrom International (KAUS)
  eleuthera: [-76.6835, 25.4749],    // North Eleuthera Airport (MYEH)
  pbi: [-80.0956, 26.6832],          // Palm Beach International (for orientation only)
};
