"""
"Where your tap water comes from": every station (diorama) and every shot of the film (runs inside Blender).

Same conventions as engine/flush (and it reuses its parts kit): stations sit 1 km apart along world X, each under
its own root empty (root y = 0, never rotated, so the section plane y = 0 is shared; the camera sits at y < 0 and
looks +Y at the cut face). A beat's shot is a method named after the beat id; it gets the beat's frame span (s, e)
from the voiceover timings and stages the camera plus whatever moves in that shot. Only the station on screen is
rendered (the others are hidden per beat).

Each station lives in its own module (home, source, plant, tower, street) exposing build_<station> plus one
function per shot, collected in SHOTS; they are attached to Film below. Anchors (self.anchor) are named points
the HyperFrames compositor pins labels and rulers to; the film's beats name them in "callouts".
"""
import bpy
from mathutils import Vector

from engine import events
from engine.director import lib

V = Vector

# 1 km apart: farther than the camera's clip distance, so no station's ground ever shows in another's shot
STATION_X = {"home": 0.0, "source": 1000.0, "plant": 2000.0, "tower": 3000.0, "street": 4000.0}


class Film:
    def __init__(self, scene, cam, total):
        self.scene, self.cam, self.total = scene, cam, total
        self.roots = {}
        self.on = {}             # station -> [(s, e)] spans it is on screen
        self.anchors = lib.Anchors()
        self.anchor_station = {}  # anchor name -> station key
        self.restore_fstop = []   # frames where a shallow-focus shot hands the default f-stop back
        self.finishers = []       # callables run once after every shot is staged

    # ------------------------------------------------------------------ helpers

    def root(self, key):
        r = lib.empty(f"ST_{key}", (STATION_X[key], 0, 0))
        self.roots[key] = r
        return r

    def W(self, key, x, y, z):
        """World position of a station-local point."""
        return (STATION_X[key] + x, y, z)

    def shot(self, key, s, e, a, b=None, cut=True, ease="smooth"):
        """Camera move inside station `key`: a/b are pose() dicts with station-local centres."""
        def world(p):
            p = dict(p)
            p["center"] = self.W(key, *p["center"])
            return p
        self.cam.shot(s, e, world(a), world(b) if b else None, cut=cut, ease=ease)

    def on_station(self, key, s, e):
        self.on.setdefault(key, []).append((s, e))

    def anchor(self, key, name, local, parent=None):
        """A named point for pinned labels: `local` is station-local; with a parent it follows that part."""
        ob = self.anchors.add(name, self.W(key, *local), parent)
        ob["no_occlude"] = True
        self.anchor_station[name] = key
        return ob

    def finish(self):
        for fn in self.finishers:
            fn()
        data = self.cam.data
        for f in self.restore_fstop:
            data.dof.aperture_fstop = 4.0
            data.keyframe_insert("dof.aperture_fstop", frame=f)
        for fc in lib.fcurves(data):
            if fc.data_path == "dof.aperture_fstop":
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"
        soften(events._events)


# The film's sound: water where water moves, rain on the hills, the pump hum, a calm night. Loud loops read as
# noise under the narration, so they are traded for a quieter sound here, in one place.
SOUND = {"water_rush": ("pour", 0.4), "pour": ("pour", 0.6), "pump": ("pump", 0.6), "bubbles": ("bubbles", 0.6),
         "lake": ("lake", 0.8), "rain": ("rain", 0.7), "traffic": None, "hum": ("hum", 0.5), "creak": None,
         "whoosh": None, "splash": ("splash", 0.5),
         "wind": ("wind", 0.5), "click": ("click", 0.6)}


def soften(log):
    out = []
    for ev in log:
        rule = SOUND.get(ev["kind"], (ev["kind"], 1.0))
        if rule is None:
            continue
        out.append(dict(ev, kind=rule[0], gain=round(ev.get("gain", 1.0) * rule[1], 3)))
    log[:] = out


def attach(modules):
    for mod in modules:
        for fn in mod.SHOTS:
            setattr(Film, fn.__name__, fn)


def load_modules(stations):
    """Import only the station modules a run needs (a half-built station never breaks the others' previews)."""
    import importlib
    mods = []
    for key in stations:
        try:
            mods.append(importlib.import_module(f"engine.tap.{key}"))
        except ModuleNotFoundError as exc:
            if exc.name != f"engine.tap.{key}":
                raise
            print(f"WARNING: no module for station {key}")
    attach(mods)
    return mods


_ = bpy  # (Blender must be importable: this module only runs inside it)
