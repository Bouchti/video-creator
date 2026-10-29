"""
What each director world can film, as data (no Blender): the planner writes plans against this, the
validator checks plans against it, and blender_job.py maps the world name to its class.

hero      the character the story follows (every world has one: people watch characters, not diagrams)
shots     beat id -> what the picture shows (the narration comments on exactly this), the gag in it, and the
          cue words the animation listens for (it falls back to a share of the beat when a cue is missing)
anchors   names a pinned label can point at
order     fixed order of beats (a world's story is physical: it cannot be shuffled)
"""

SEPTIC = {
    "world": "septic",
    "class": "engine.director.septic:SepticWorld",
    "subject": "what happens after you flush, told through Flushy, a googly-eyed poop",
    "hero": "Flushy: a small brown blob with big eyes and a mouth. Cheerful, a bit dim, always surprised.",
    "anchors": ["sludge", "scum", "tee", "soil", "groundwater", "pipe"],
    "order": ["hook", "follow", "sort", "baffle", "field", "die", "float", "land"],
    "shots": {
        "hook": {"shows": "Flooded blue ground; glowing arrows push an EMPTY concrete tank; it trembles, bursts out "
                          "of the lawn leaving a crater, the lid pops off like a bottle cap and Flushy is launched "
                          "into the sky, eyes wide.",
                 "gag": "a poop launched like a rocket", "cues": []},
        "follow": {"shows": "VHS rewind of the hook (edit), then Flushy drops down the house drain with a squash and zooms down "
                            "the cut-open sewer pipe across a wide shot, wobbling with delight, and arrives at the tank.",
                   "gag": "Flushy enjoys the slide like a water park", "cues": []},
        "sort": {"shows": "Inside the half-cut tank: Flushy and a gang of brown blobs with eyes splash in; the heavy "
                          "ones (Flushy too) bounce down onto the sludge; yellow greasy blobs float up into the scum.",
                 "gag": "everyone gets sorted like at a school", "cues": ["heavy", "greasy"]},
        "baffle": {"shows": "Close on the white T-pipe wearing sunglasses: blue drops slip under the scum, up the tee "
                            "and out; a greasy blob tries to sneak out, gets squashed against the tee and bounced back.",
                   "gag": "the T-pipe is a nightclub bouncer", "cues": ["tonight"]},
        "field": {"shows": "Drops seep from holes in a pipe into gravel; angry green germs sink into the soil; purple "
                           "microbes with mouths pop up and chomp them to nothing.",
                  "gag": "microbes eat germs like Pac-Man", "cues": ["seeps", "microbes"]},
        "die": {"shows": "White wipes drop into the tank and never dissolve; the sludge and scum swell, Flushy rises "
                         "with them, gang members escape down the outlet into the gravel, the gravel turns black, a "
                         "brown swamp spreads on the lawn, green stink lines rise and the flowers wilt.",
                "gag": "the flowers faint from the smell", "cues": ["wipes", "grows", "escapes", "swamp"]},
        "float": {"shows": "A pickup truck arrives and a hose pumps the tank empty (only Flushy is left, clinging on); "
                           "the soil floods blue up to the lawn; arrows push the empty tank, it bursts out (the hook).",
                  "gag": "an empty concrete tank floats like a boat", "cues": ["pumps", "flood", "boat", "shoves"]},
        "land": {"shows": "Flushy falls from the sky onto the lawn beside the crater and the tilted tank, squashes, "
                          "blinks, then hops and smiles at the camera.",
                 "gag": "Flushy lands like a gymnast: ta-da", "cues": ["lands", "ta-da"]},
    },
}

WORLDS = {"septic": SEPTIC}
