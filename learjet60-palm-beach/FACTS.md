# FACTS — Learjet 60 N722BD, Palm Beach County, Florida, 1 November 2026

Every claim spoken or shown in the film, with its source. Gathered 3 Nov 2026. The NTSB investigation is open; no cause has been determined, and the film says so.

| # | Claim in the film | Source | Wording in the source |
|---|---|---|---|
| 1 | Sunday 1 Nov 2026; a Learjet 60, registration N722BD | Wikipedia, "2026 Palm Beach County Learjet 60 crash"; AIN 2026-11-01 | "a privately owned Learjet 60 business jet crashed in Palm Beach County, Florida … on November 1, 2026"; "Bombardier Learjet 60 (N722BD)" |
| 2 | Flight from Austin, Texas, to North Eleuthera, Bahamas | AIN; Wikipedia | "departed Austin-Bergstrom International Airport (KAUS) … bound for North Eleuthera Airport (MYEH), Bahamas" |
| 3 | Cruising at 35,000 ft | Wikipedia | "Cruise altitude: 35,000 ft, heading eastbound" |
| 4 | Thunderstorms over the area | Wikipedia; FlightGlobal headline + NEXRAD caption | "Thunderstorms were affecting the area"; "high-altitude upset in convective weather" |
| 5 | 12:47 EST: crew reported turbulence and icing, asked to climb to 37,000 ft | Wikipedia; AIN | "Crew reported turbulence, altitude deviations of about 700 ft, icing … requested a climb to 37,000 ft"; AIN: "requested a climb to 37,000 feet" |
| 6 | Pilots reported an overspeed and a descent of 20,000 ft/min | AIN | "the aircraft 'was in an overspeed condition' and was descending at 20,000 fpm" |
| 7 | Mayday call | Wikipedia; AIN | "A pilot radioed a mayday call"; "the crew issued a mayday call" |
| 8 | FAA: fell from 35,250 ft to 8,750 ft in about one minute | Wikipedia (citing FAA) | "the plane descended from 35,250 ft to 8,750 ft in one minute before impact" |
| 9 | Impact 12:51 EST, near-vertical, near Military Trail and 10th Avenue North | Wikipedia | "12:51:50 … hit the ground in an almost vertical nosedive"; "near the intersection of Military Trail (SR 809) and 10th Avenue North"; 26.632889 N, 80.113111 W |
| 10 | All nine on board killed (7 passengers, 2 crew) | Wikipedia; AIN; CNN headline | "All 9 killed (7 passengers, 2 crew)" |
| 11 | About 600 residents displaced | Wikipedia | "About 600 residents of a nearby mobile home community were evacuated or displaced" |
| 12 | Deadliest Learjet 60 crash | Wikipedia; search summary citing Flight Safety Foundation | "the deadliest crash involving a Learjet 60" |
| 13 | NTSB: indications the jet may have begun breaking apart before impact | Wikipedia, paraphrasing NTSB board member Tom Chapman, briefing 2 Nov | "investigators found indications the aircraft may have begun breaking apart before impact" |
| 14 | NTSB hopes to recover the cockpit voice recorder; cause not determined | Wikipedia; AIN; FlightGlobal | "investigators hoped to recover it"; "no cause has been determined" |

Not used, on purpose: the names of the victims; the pilot's last words; any theory of cause.

## Sources

- https://en.wikipedia.org/wiki/2026_Palm_Beach_County_Learjet_60_crash
- https://www.ainonline.com/aviation-news/business-aviation/2026-11-01/florida-learjet-crash-claims-nine
- https://www.flightglobal.com/ops-safety/2026/11/learjet-crash-probe-seeks-to-understand-high-altitude-upset-in-convective-weather/
- https://edition.cnn.com/2026/11/02/us/florida-learjet-plane-crash-monday
- https://www.flightradar24.com/blog/flight-tracking-news/major-incident/learjet-60-crashes-near-west-palm-beach-florida/

## Measurements made for the film

- **Radar** (on screen 12:30-12:45 EST): NOAA NEXRAD n0q composite (IEM archive), frames 17:30, 17:35, 17:40, 17:45 UTC.
  dBZ = value / 2 - 32.5, smoothed (Gaussian sigma 1.2 px at 0.005 deg), outlines at 40 and 50 dBZ (tools/radar.py, contourpy).
  Strongest reflectivity within ~20 km of the impact point: 46.6 dBZ (17:30), 50.5 (17:35), 52.1 (17:40), 50.1 (17:45), 33.4 (17:50).
  This supports "a line of thunderstorms" and is not used to claim the jet's exact path.
- **Impact point** 26.632889 N, 80.113111 W (Wikipedia coordinates, from reports) placed on NAIP 2023; it falls ~90 m west of
  Military Trail, consistent with reports of a crash near Military Trail and 10th Avenue North. Military Trail traced on NAIP 2023 at 80.11232 W.
- **Altitude in the dive**: the camera height is set to the FAA's reported values, 35,250 ft at the start and 8,750 ft at the end,
  with an accelerating curve in between (the curve is illustrative; only the two end values are reported). The real minute is
  shown in about 11 s of film; the on-screen clock runs 12:48 -> 12:51:50 EST over the same span.
- **Route**: Austin (KAUS) -> crash site drawn as a great circle and labelled "route approximate"; the leg to North Eleuthera (MYEH)
  is the planned destination, dashed. No ADS-B track was used.
