"""
STAGE: the director's generic world. Any topic, filmed from a plan written as DATA (agents/stage_writer.py);
no per-topic code. Runs inside Blender (engine/director/blender_job.py).

The set     a sky (Poly Haven HDRI) + sun, an endless ground (a BlenderKit material, or clean toy grass), backdrop
            assets in rings behind the action (trees, houses ...), and up to ~10 props, each a free BlenderKit
            model scaled to its real size and stood on the ground at a named SPOT.
The cast    Max and his two kids (engine/character.py, the clean toy look), performing motion-capture clips
            (engine/mocap.py): walk / run to a spot at the clip's own ground speed (no foot sliding), then act.
Events      what props do, from a small vocabulary of moves that read clearly and cannot flicker (no
            booleans, no fast strobing): appear, vanish, grow, shrink, rise, drop, spin, wobble, bounce, slide,
            tip_over, glow.
Camera      per beat: wide / medium / close on a prop, a character or the family, with a gentle move; the
            director's Camera enforces the speed limits, so nothing jumps or whips.
Exports     anchors (labels pin to props / characters), actions (the visibility gate) and sounds (footsteps,
            pops, whooshes ... at the frames they happen) for the director's sound stage.

Plan (the parts used here):
  place  {"ground": query, "sky": "day|golden|overcast|night", "backdrop": [query, ...]}
  props  [{"id", "query", "size_m", "spot", "facing"}]        + plan["assets"][id] = {"path", ...} (resolved)
  beats  [{"id", "shot": {"frame", "on", "move"}, "cast": [{"who", "do", "at", "to", "look"}],
           "events": [{"prop", "does", "at", "to"}]}]
"""
import math
import os
import random

import bpy
from mathutils import Vector

from engine import toy
from engine.character import Character
from engine.director import lib
from engine.mocap import Mocap

SPOTS = {   # metres on the stage floor; the camera looks +Y from the front (y < 0)
    "center": (0.0, 0.0), "left": (-2.4, 0.2), "right": (2.4, 0.2), "front_left": (-1.3, -1.6),
    "front_right": (1.3, -1.6), "back_left": (-3.2, 3.4), "back": (0.0, 4.2), "back_right": (3.2, 3.4),
    "far_left": (-5.5, 1.2), "far_right": (5.5, 1.2),
}
LOOKS = {
    "Max": {"hat": "#FF7A00", "shirt": "#E8492F", "shoes": "#F2C230", "iris": "#7A4A1C"},
    # the kids: their own faces (rounder head, big eyes, button nose, rosy cheeks, real hair), not small Maxes
    "Kid1": {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5", "scale": 0.66,
             "hair": "#6B3B1C", "hair_style": "pigtails", "tie": "#FFD23F", "head_scale": 1.12, "eye_scale": 1.08,
             "nose": 0.62, "blush": True},
    "Kid2": {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B", "scale": 0.6,
             "hair": "#3D2616", "hair_style": "tuft", "head_scale": 1.15, "eye_scale": 1.08, "nose": 0.68,
             "blush": True},
}
HOME = {"Max": (-0.9, -0.9), "Kid1": (0.2, -1.2), "Kid2": (1.1, -1.0)}   # where the family starts
MAX_SHOT_WIDTH = 4.5   # metres across a vertical frame: wider, a 1.4 m character is a speck in a 8 m tall picture
LOW = {"crouch", "sneak", "fix", "pick_up", "plant", "harvest", "fall", "roll", "knocked", "get_up"}
SMALL = 0.6                    # props below this size (m) are hand-size: they go on the worktable
MIN_PROP = 0.28                # shown at least this big (toy scale): an 8 cm spinning top was 1 % of the frame
MIN_SHOT = 30                  # frames: a shot shorter than 1 s reads as a flash
HOLD = 24                      # frames an action is held at least (6-9 frame jumps were never seen)
FACE_OUT = {"jump", "knocked", "fall", "no", "yes", "dance", "call_out", "fold_arms", "laugh", "cheer"}  # reactions
TABLE_SIZE, TABLE_AT = 1.8, (0.0, 0.2)
TABLE_HOME = {"Max": (0.0, 0.95), "Kid1": (-1.3, 0.15), "Kid2": (1.3, 0.15)}   # behind it / at its two ends
SKIES = {"day": ["kloofendal_48d_partly_cloudy_puresky", "kloofendal_43d_clear_puresky", "partly_cloudy"],
         "golden": ["kloofendal_48d_partly_cloudy_puresky"],    # clear sky; the low warm sun makes it golden
                                                               # (the misty "golden" HDRIs read as a white sky)
         "overcast": ["kloofendal_overcast_puresky", "overcast"], "night": ["moonless_golf", "night", "moon"]}
SUN = {"day": (52, 0, 35, 3.6, (1.0, 0.96, 0.9)), "golden": (14, 0, 60, 2.6, (1.0, 0.78, 0.55)),
       "overcast": (60, 0, 20, 1.2, (0.9, 0.95, 1.0)), "night": (35, 0, 200, 0.25, (0.6, 0.7, 1.0))}
MOVES = {"walk": "walk", "jog": "jog", "run": "run", "sneak": "sneak"}
SPECTACLE = ("steam_burst", "smoke_burst", "launch", "confetti", "sparks", "rumble",   # hook-grade surprises
             "lean_recover")
EVENTS = ("appear", "vanish", "grow", "shrink", "rise", "drop", "spin", "wobble", "bounce", "slide", "tip_over",
          "glow") + SPECTACLE
EVENT_SOUND = {"appear": "pop", "vanish": "whoosh", "grow": "power_up", "shrink": "whoosh", "rise": "whoosh",
               "drop": "impact thud", "spin": "whoosh", "wobble": "wood creak", "bounce": "boing",
               "slide": "slide", "tip_over": "impact thud", "glow": "power_up", "steam_burst": "steam hiss",
               "smoke_burst": "explosion", "launch": "whoosh", "confetti": "party popper", "sparks": "electric spark",
               "rumble": "rumble", "lean_recover": "metal clang"}
CLIP_SOUND = {"jump": "whoosh", "land": "impact thud", "fall": "impact thud", "dance": None, "push": "wood creak",
              "fix": "hammer", "chop": "hammer", "hit": "impact thud", "throw": "whoosh", "eat": "eat crunch"}


# The ground is the biggest surface in every frame, so it is the CLEAN toy look of the Max films, never a photo
# texture (a photo-scanned grass of blades read as ugly, noisy carpet and shimmered under camera moves):
# two broad colour patches (metres wide), a soft mottling, a gentle relief, nothing finer than ~10 cm.
GROUNDS = {   # kind -> (patch dark, patch light, mottle, roughness, relief)
    "grass": ("#3E7F33", "#4F9440", "#5E9F49", 0.88, 0.05),     # a lawn, not lime: the brighter set read neon
    "sand": ("#D9BE86", "#E9D3A0", "#F2E2B8", 0.9, 0.06),
    "gravel": ("#8E877D", "#A9A399", "#BDB7AD", 0.85, 0.12),
    "asphalt": ("#3B3C40", "#4A4B50", "#55565B", 0.75, 0.04),
    "snow": ("#E2EAF2", "#F2F6FA", "#FFFFFF", 0.6, 0.05),
    "dirt": ("#73563B", "#8B6A4A", "#9C7B58", 0.92, 0.08),
    "paving stones": ("#9C968C", "#B3ADA3", "#C4BEB4", 0.8, 0.0),
}


GREY_GROUNDS = {"asphalt", "gravel", "paving stones"}


def ground_material(kind):
    from engine import textures as tx
    from engine.studio import _mix_color
    dark, light, mottle, rough, relief = GROUNDS.get(kind, GROUNDS["grass"])
    if kind == "paving stones":
        return tx.tiles("ground_paving", light, grout="#8A847A", size=0.6, rough=rough, coat=0.0)
    t = tx._Tree(f"ground_{kind.replace(' ', '_')}")
    patches = t.ramp(t.noise(scale=0.09, detail=2, rough=0.4), [(0.38, dark), (0.66, light)])
    soft = t.noise(scale=0.8, detail=2, rough=0.45)
    color = t.shade(patches, t.math("ADD", 0.93, t.math("MULTIPLY", soft, 0.14)))
    speck = t.math("DIVIDE", t.math("SUBTRACT", t.noise(scale=2.2, detail=1, rough=0.3), 0.62), 0.08, clamp=True)
    color = _mix_color(t, t.math("MULTIPLY", speck, 0.35), color, (*toy.srgb(mottle), 1.0))
    height = t.noise(scale=1.6, detail=2, rough=0.4)
    return t.finish(color, rough, height, strength=relief, distance=0.02)


class StageWorld:
    def __init__(self, timing, preview=False, plan=None):
        self.t = timing
        self.plan = plan or {}
        self.beats = {b["id"]: b for b in timing["beats"]}
        self.scene = lib.reset(timing.get("fps", 30), preview, look=timing.get("look", "vivid"))
        self.scene.frame_start, self.scene.frame_end = 1, timing["total"]
        self.rnd = random.Random(11)
        self.anchors = lib.Anchors()
        self.actions, self.sounds = [], []
        self.cam = lib.Camera(lens=32, fstop=4.0)
        self.mocap = Mocap()
        self.props, self.sizes = {}, {}
        place = self.plan.get("place", {})
        self._sky(place.get("sky", "day"))
        self._ground()
        self._backdrop()
        self._props()
        self._cast()

    # ------------------------------------------------------------------ helpers
    def act(self, name, ob, f0, f1, min_share=0.05):
        self.actions.append({"name": name, "obj": ob.name, "f0": int(f0), "f1": int(f1), "min_share": min_share})

    def sound(self, kind, frame, gain=1.0, duration=0):
        if kind:
            self.sounds.append({"kind": kind, "frame": int(frame), "gain": gain, "duration": int(duration)})

    def cue(self, beat, word, share=0.15):
        b = self.beats[beat]
        if beat == self.t["beats"][0]["id"] and (not word or word in ("start", "begin")):
            return b["f0"] + 3          # the hook acts AT ONCE: at 15 % of the beat it missed the first second
        if word and word not in ("start", "begin"):
            key = word.lower().strip(".,:;?!\"'()")
            for w, fr in b.get("cues", {}).items():
                if w == key:
                    return max(b["f0"], min(b["f1"] - 6, fr))
        return b["f0"] + int((b["f1"] - b["f0"]) * share)

    def asset(self, pid):
        return (self.plan.get("assets") or {}).get(pid) or {}

    @staticmethod
    def spot(name, default=(0.0, 0.0)):
        if isinstance(name, (list, tuple)) and len(name) >= 2:
            return Vector((float(name[0]), float(name[1]), 0.0))
        return Vector((*SPOTS.get(name or "", default), 0.0))

    # ------------------------------------------------------------------ the set
    def _sky(self, sky):
        path = None
        for hint in SKIES.get(sky, SKIES["day"]) + SKIES["day"]:
            try:
                path = lib.hdri(hint)
                break
            except Exception:  # noqa: BLE001
                continue
        if path:
            lib.hdri_world(path, strength=0.9 if sky != "night" else 0.35, rotation_deg=40)
        el, _r, az, strength, colour = SUN.get(sky, SUN["day"])
        lib.sun(rotation=(90 - el, 0, az), strength=strength, color=colour)

    def _import(self, path, name):
        """Every object of a BlenderKit .blend under one empty, normalised so its bottom sits at z=0 and its
        footprint is centred (BlenderKit models come with arbitrary origins)."""
        before = set(bpy.data.objects)
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        root = lib.empty(f"P_{name}")
        for ob in dst.objects:
            if ob is None or ob.type in ("CAMERA", "LIGHT", "LIGHT_PROBE", "SPEAKER"):
                continue
            bpy.context.scene.collection.objects.link(ob)
        new = [o for o in bpy.data.objects if o not in before and o is not root
               and o.name in bpy.context.scene.objects]
        for ob in new:
            if ob.parent is None:
                ob.parent = root
        bpy.context.view_layer.update()
        meshes = [o for o in root.children_recursive if o.type == "MESH" and not o.hide_render]
        if not meshes:
            bpy.data.objects.remove(root)
            return None, 0.0
        pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        offset = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for ob in root.children:
            ob.location -= offset
        for o in meshes:
            o.visible_shadow = True
        return root, max(hi - lo)

    FALLBACK_SHAPES = (   # words in the prop's id / search -> the basic form a viewer recognises
        (("top", "cone", "funnel", "spike"), "cone"),
        (("ball", "orb", "globe", "planet", "egg", "balloon", "bubble"), "sphere"),
        (("wheel", "can", "barrel", "drum", "pipe", "pot", "cup", "jar", "bottle", "log", "coin", "disc", "tire",
          "pencil", "stick", "rod", "pole", "bat", "candle", "tube"), "cylinder"),
    )
    FALLBACK_COLOURS = ("#E8492F", "#3A7BD5", "#F2C230", "#3DBE6E", "#FF7A00", "#8E6CD8")

    def _fallback(self, name, size, query=""):
        """A clean toy shape when no asset fits (never a missing prop): a cone for a spinning top, a sphere for
        a ball, a cylinder for a wheel or a pot, else a rounded block; a bright toy colour, not beige."""
        words = set((name + " " + query).lower().replace("_", " ").split())
        form = next((f for keys, f in self.FALLBACK_SHAPES if words & set(keys)), "box")
        colour = self.FALLBACK_COLOURS[sum(map(ord, name)) % len(self.FALLBACK_COLOURS)]
        mat = toy.material(f"fb_{name}", toy.srgb(colour), roughness=0.35, coat=0.6)
        root = lib.empty(f"P_{name}")
        if form == "cone":                      # point down, like a spinning top
            bpy.ops.mesh.primitive_cone_add(radius1=size * 0.45, radius2=0.0, depth=size * 0.8,
                                            location=(0, 0, size * 0.45), rotation=(math.pi, 0, 0), vertices=40)
            ob = bpy.context.active_object
            ob.data.materials.append(mat)
            bpy.ops.object.shade_smooth()
            stem = toy.cylinder(f"{name}_stem", size * 0.06, size * 0.25, (0, 0, size * 0.9), mat=mat)
            stem.parent = root
        elif form == "sphere":
            ob = toy.sphere(f"{name}_ball", size * 0.5, (0, 0, size * 0.5), mat=mat)
        elif form == "cylinder":
            ob = toy.cylinder(f"{name}_cyl", size * 0.4, size * 0.8, (0, 0, size * 0.4), mat=mat, bevel=0.02)
        else:
            ob = toy.box(f"{name}_block", (size * 0.8, size * 0.8, size), (0, 0, size / 2), mat=mat, bevel=0.06)
        ob.parent = root
        return root, size

    def _ground(self):
        size = 160.0
        bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "Ground"
        kind = self.plan.get("place", {}).get("ground", "grass")
        if kind in GREY_GROUNDS:        # grey ground filled the frame: every beat failed the colour gate
            kind = "grass"
        mat = self._stylized_ground(g, size, kind)
        g.data.materials.append(mat or ground_material(kind))
        g.visible_shadow = False      # receives, never casts (half the render time, no acne)
        if kind == "grass":
            self._lawn()

    def _lawn(self):
        """Grass as the Max films did it: real 3D blade clumps over the soft lawn, not a texture (both a photo
        scan and a painted grass texture read as ugly carpet). Dense where the camera is close, sparser out to
        the backdrop, none in the far distance (thin blades far away alias and shimmer)."""
        import bmesh
        mesh = bpy.data.meshes.new("stage_tuft")
        bm = bmesh.new()
        rnd = random.Random(5)
        for _ in range(11):
            ang = rnd.uniform(0, 2 * math.pi)
            lean = rnd.uniform(0.15, 0.45)
            h = rnd.uniform(0.08, 0.16)
            w = 0.009
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy * w, dx * w
            base = Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0))
            mid = base + Vector((dx * lean * h * 0.4, dy * lean * h * 0.4, h * 0.55))
            tip = base + Vector((dx * lean * h, dy * lean * h, h))
            v = [bm.verts.new(base + Vector((px, py, 0))), bm.verts.new(base - Vector((px, py, 0))),
                 bm.verts.new(mid - Vector((px, py, 0)) * 0.7), bm.verts.new(mid + Vector((px, py, 0)) * 0.7),
                 bm.verts.new(tip)]
            bm.faces.new((v[0], v[1], v[2], v[3]))
            bm.faces.new((v[3], v[2], v[4]))
        bm.to_mesh(mesh)
        bm.free()
        tuft = bpy.data.objects.new("stage_tuft", mesh)
        bpy.context.scene.collection.objects.link(tuft)
        dark, light, _m, _r, _b = GROUNDS["grass"]
        tuft.data.materials.append(toy.noise_material("stage_blades", toy.srgb(dark), toy.srgb(light), scale=0.6,
                                                      roughness=0.6, bump=0.0))
        tuft.location = (0, 0, -100)
        tuft.hide_render = True
        # the camera stands in front (y < 0), up to ~12 m back for a wide shot: the blades run under it,
        # or a wide shot ended in a flat green band at the bottom of the frame
        for name, (x0, x1, y0, y1), density in (("lawn_near", (-7, 7, -4, 6), 420),
                                                ("lawn_front", (-10, 10, -14, -4), 300),
                                                ("lawn_mid", (-14, 14, 6, 16), 160),
                                                ("lawn_left", (-14, -7, -4, 6), 160),
                                                ("lawn_right", (7, 14, -4, 6), 160)):
            em = toy.scatter(name, x0, x1, y0, y1, tuft, density, size=1.2, size_random=0.5, z=0.002,
                             seed=len(name))
            em.visible_shadow = False

    def _stylized_ground(self, g, size, kind, tile=3.5):
        """The curated stylized BlenderKit material, tiled every `tile` m, with a broad procedural colour
        variation multiplied over it so the repeat never shows across the lawn."""
        path = self.asset("_ground").get("path")
        if not (path and os.path.isfile(path)):
            return None
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.materials = list(src.materials)
        mats = [m for m in dst.materials if m is not None and m.use_nodes]
        if not mats:
            return None
        mat = max(mats, key=lambda m: len(m.node_tree.nodes))
        for loop in g.data.uv_layers.active.data:
            loop.uv = loop.uv * (size / tile)
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        link = next((lk for lk in nt.links if bsdf and lk.to_socket == bsdf.inputs["Base Color"]), None)
        if link is None:
            return mat
        tc = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.06          # ~15 m patches, in object space = metres
        noise.inputs["Detail"].default_value = 2.0
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.82, 0.86, 0.8, 1)
        ramp.color_ramp.elements[1].color = (1.08, 1.06, 1.0, 1)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        a = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")
        b = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
        nt.links.new(link.from_socket, a)
        nt.links.new(ramp.outputs["Color"], b)
        nt.links.new(next(s for s in mix.outputs if s.type == "RGBA"), bsdf.inputs["Base Color"])
        return mat

    def _backdrop(self):
        """Backdrop assets in two rings behind the action, a few copies each, at real sizes."""
        queries = self.plan.get("place", {}).get("backdrop", [])[:3]
        k = 0
        for q in queries:
            a = self.asset(f"_backdrop_{q}")
            if not a.get("path"):
                continue
            src, size = self._import(a["path"], f"bd_{k}")
            if src is None:
                continue
            want = float(a.get("size_m") or 6.0)
            s = want / max(size, 1e-3)
            copies = [src] + [self._duplicate(src, f"bd_{k}_{i}") for i in range(4)]
            for i, ob in enumerate(copies):
                x = (-14 + 7 * i + self.rnd.uniform(-1.5, 1.5)) * (1 + 0.3 * k)
                y = 11 + 5 * k + self.rnd.uniform(-1.5, 2.0)
                ob.location = (x, y, 0)
                ob.rotation_euler = (0, 0, self.rnd.uniform(-0.6, 0.6))
                ob.scale = (s * self.rnd.uniform(0.85, 1.15),) * 3
            k += 1

    @staticmethod
    def _duplicate(root, name):
        new_root = root.copy()
        new_root.name = name
        bpy.context.scene.collection.objects.link(new_root)

        def copy_children(src, dst):
            for c in src.children:
                cc = c.copy()                      # shares mesh data: cheap
                bpy.context.scene.collection.objects.link(cc)
                cc.parent = dst
                copy_children(c, cc)
        copy_children(root, new_root)
        return new_root

    def _prop(self, pid, want, asset, name=None):
        root, size = (self._import(asset["path"], name or pid) if asset.get("path") and os.path.isfile(asset["path"])
                      else (None, 0.0))
        if root is None:
            root, size = self._fallback(name or pid, want)
        s = want / max(size, 1e-3)
        holder = lib.empty(f"prop_{name or pid}")
        root.parent = holder
        root.scale = (s, s, s)
        return holder

    def _props(self):
        """Floor props at their spots. HAND-SIZE props (< SMALL m: a pot, a gauge, a phone) on the floor were
        specks metres apart and the cooking happened on the ground: they go on a worktable at the front,
        spread along its top, with Max behind it and the kids at its ends."""
        props = self.plan.get("props", [])
        small = [p for p in props if float(p.get("size_m") or 1.0) < SMALL]
        self.table, self.on_table = None, set()
        # the worktable takes the centre only if no BIG prop wants it: a toolbox once pushed the star of the
        # film (the bike) 2.4 m to the back. Otherwise it goes to the first free side.
        big = [self.spot(p.get("spot"), (0, 2.0)) for p in props if float(p.get("size_m") or 1.0) >= SMALL]
        for at in (TABLE_AT, (2.9, 0.5), (-2.9, 0.5), (0.0, 2.6)):
            if all((Vector((*at, 0)) - b).length > 1.9 for b in big):
                break
        self.table_at = at
        self.table_home = {w: (at[0] + x - TABLE_AT[0], at[1] + y - TABLE_AT[1]) for w, (x, y) in TABLE_HOME.items()}
        if small:
            self.table = self._prop("_worktable", TABLE_SIZE, self.asset("_worktable"), "worktable")
            self.table.location = Vector((*self.table_at, 0.0))
            bpy.context.view_layer.update()
            meshes = [o for o in self.table.children_recursive if o.type == "MESH"]
            top = max((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box) if meshes else 0.8
            self.table_top = top if 0.4 < top < 1.3 else 0.8
        for k, p in enumerate(small):
            pid = p["id"]
            want = max(MIN_PROP, float(p.get("size_m") or 0.3))
            holder = self._prop(pid, want, self.asset(pid))
            x = self.table_at[0] + (k - (len(small) - 1) / 2) * min(0.5, (TABLE_SIZE * 0.8) / max(1, len(small)))
            holder.location = Vector((x, self.table_at[1] - 0.05, self.table_top + 0.005))
            holder.rotation_euler = (0, 0, math.radians(float(p.get("facing") or 0)))
            self.props[pid], self.sizes[pid] = holder, want
            self.on_table.add(pid)
            self.anchors.add(pid, holder.location + Vector((0, 0, want * 0.9)), holder)
            self.anchors.add(f"{pid}.mid", holder.location + Vector((0, 0, want * 0.45)), holder)   # arrows
        for p in props:
            if p in small:
                continue
            pid = p["id"]
            want = float(p.get("size_m") or 1.0)
            holder = self._prop(pid, want, self.asset(pid))
            holder.location = self.spot(p.get("spot"), (0, 2.0))
            if self.table is not None and (holder.location - Vector((*self.table_at, 0))).length < 1.6:
                holder.location += Vector((0, 2.4, 0))      # the worktable owns the front of the stage
            holder.rotation_euler = (0, 0, math.radians(float(p.get("facing") or 0)))
            self.props[pid], self.sizes[pid] = holder, want
            self.anchors.add(pid, holder.location + Vector((0, 0, want * 0.9)), holder)
            self.anchors.add(f"{pid}.mid", holder.location + Vector((0, 0, want * 0.45)), holder)

    # ------------------------------------------------------------------ the cast
    def _cast(self):
        self.cast, self.home = {}, {}
        for who, look in LOOKS.items():
            x, y = self.table_home[who] if self.table is not None else self._clear_of_props(*HOME[who])
            ch = Character(who, look, location=(x, y, 0), facing_deg=0)
            self.cast[who] = ch
            self.anchors.add(who, (x, y, 1.55 * look.get("scale", 1.0)), ch.root)
            ch.auto_blink(1, self.t["total"], seed=len(who))
            self.home[who] = (x, y)
        self.where = {w: Vector((*self.home[w], 0.0)) for w in self.cast}
        self.facing = {w: 0.0 for w in self.cast}
        self.turn_end = {}

    def _clear_of_props(self, x, y):
        """A start mark no prop stands on (a pole went through Max's head): step toward the camera until clear."""
        if not hasattr(self, "home"):
            self.home = {}
        p = Vector((x, y, 0))
        for _ in range(12):
            hit = [pid for pid, ob in self.props.items() if pid not in self.on_table
                   and (Vector((ob.location.x, ob.location.y, 0)) - p).length < self.sizes[pid] * 0.5 + 0.45]
            if not hit:
                break
            p.y -= 0.35
            p.x += 0.2 if p.x >= 0 else -0.2
        return p.x, p.y

    def _at_table(self, p):
        return (self.table is not None and abs(p.x - self.table_at[0]) < TABLE_SIZE / 2 + 0.5
                and abs(p.y - self.table_at[1]) < 1.2)

    def _route(self, a, b):
        """[a, ..., b]: around the worktable's nearer end when the straight line crosses it (Max walked
        through the table)."""
        if self.table is None:
            return [a, b]
        tx, ty = self.table_at
        half, depth = TABLE_SIZE / 2 + 0.45, 0.55
        crosses = (a.y - ty) * (b.y - ty) < 0 or abs(a.y - ty) < depth or abs(b.y - ty) < depth
        if not crosses:
            return [a, b]
        # where the segment passes the table line
        k = (ty - a.y) / (b.y - a.y) if abs(b.y - a.y) > 1e-6 else 0.5
        x_at = a.x + (b.x - a.x) * max(0.0, min(1.0, k))
        if abs(x_at - tx) > half:
            return [a, b]
        side = 1 if (a.x + b.x) / 2 >= tx else -1
        end = Vector((tx + side * half, ty, 0))
        return [a, end + Vector((0, -depth if a.y < ty else depth, 0)), end + Vector((0, depth if b.y > ty else -depth, 0)),
                b]

    def _height(self, who):
        return 1.45 * LOOKS[who].get("scale", 1.0)

    def _face(self, who, f, deg, frames=8, max_frames=None):
        ch = self.cast[who]
        deg = self.facing[who] + ((deg - self.facing[who] + 180) % 360 - 180)    # shortest turn
        # ~8 degrees a frame at most: a 180-degree spin in 8 frames strobed in a close-up
        frames = max(frames, int(abs(deg - self.facing[who]) / 8))
        if max_frames:
            frames = max(2, min(frames, max_frames))     # a walking leg turns before its end
        f = max(f, self.turn_end.get(who, 0))            # never inside the previous turn (keys out of order)
        lib.key(ch.root, "rotation_euler", f, (0, 0, math.radians(self.facing[who])))
        lib.key(ch.root, "rotation_euler", f + frames, (0, 0, math.radians(deg)))
        self.facing[who] = deg
        self.turn_end[who] = f + frames

    def _target(self, name, who=None, f=None):
        """A world point for a spot, prop or character name (characters stop beside props, not inside). With a
        frame, a prop is where its EVENTS have moved it by then (a bike that slid ran into Max otherwise)."""
        if name in self.on_table:                 # their own place at the worktable, never in front of it
            if who == "Max":
                tx = self.table_at[0]
                return Vector((max(tx - 0.6, min(tx + 0.6, self.props[name].location.x)),
                               self.table_home["Max"][1], 0))
            return Vector((*self.table_home.get(who, self.table_home["Kid1"]), 0))
        if name in self.props:
            # beside and a little BEHIND the prop: standing in front of it blocked the close-ups
            if f is not None:
                bpy.context.scene.frame_set(f)
                p = self.props[name].matrix_world.translation.copy()
            else:
                p = self.props[name].location
            # each character has its OWN slot around a prop (all three on one point stood inside each other):
            # Max on the right, Kid1 on the left, Kid2 in front a little to the right
            reach = 0.45 + self.sizes[name] * 0.45
            slot = {"Max": (reach, 0.25), "Kid1": (-reach, 0.25), "Kid2": (reach * 0.55, -0.55)}.get(
                who, (reach, 0.25))
            return Vector((p.x + slot[0], p.y + slot[1], 0))
        if name in self.cast:
            return self.where[name] + Vector((0.8, 0, 0))
        return self.spot(name, (0, 0))

    def perform(self):
        """Every character's timeline for the whole film -> mocap segments + root moves + turns."""
        total = self.t["total"]
        self.walks = {}                     # who -> [(f0, f1)] of every walk (the edit avoids them)
        lines = {w: [] for w in self.cast}
        for b in self.t["beats"]:
            pb = self._plan_beat(b["id"])
            acting = set()
            for c in pb.get("cast", []):
                if c.get("who") in lines:
                    lines[c["who"]].append((self.cue(b["id"], c.get("at")), b["id"], c))
                    acting.add(c["who"])
            # whoever does not act in a beat stops and WATCHES what it is about (a throw clip held for 20 s and
            # random gestures made the film look like characters moving at random)
            on = (pb.get("shot") or {}).get("on")
            if on in self.props:
                for w in lines:
                    if w not in acting:
                        lines[w].append((b["f0"] + 4, b["id"], {"who": w, "do": "idle", "look": on, "watch": True}))
        for who, items in lines.items():
            items.sort(key=lambda r: r[0])
            ch = self.cast[who]
            h = 0.56 * LOOKS[who].get("scale", 1.0)
            segs, f_last = [], 1
            idle = "idle"
            for k, (f, bid, c) in enumerate(items):
                f_next = items[k + 1][0] - 1 if k + 1 < len(items) else total
                if f > f_last:
                    segs.append((idle, f_last, f - 1))
                f = max(f, f_last)
                # never toward the lens: a walk to a front spot filled the frame with a belly
                to = {"front_left": "left", "front_right": "right"}.get(c.get("to"), c.get("to"))
                if not to and not c.get("watch"):
                    # BLOCKING: whoever acts in a beat comes to its subject first (a kid jumping 6 m away from
                    # the shot was simply off screen); characters already close stay where they are
                    on = (self._plan_beat(bid).get("shot") or {}).get("on")
                    there = (self.props[on].location if on in self.props
                             else self.where[on] if on in self.cast and on != who else None)
                    if there is not None and (Vector((there.x, there.y, 0)) - self.where[who]).length > 2.5:
                        to = on
                if to:
                    dest = self._target(to, who, f_next if to in self.props else None)
                    path = self._route(self.where[who], dest)
                    dist = sum((b - a).length for a, b in zip(path, path[1:]))
                    move = MOVES.get(c.get("move") or ("run" if c.get("do") == "run" else "walk"), "walk")
                    speed = max(0.3, self.mocap.ground_speed(move, h) or 0.7)
                    frames = max(18, int(dist / speed * 30))
                    frames = min(frames, max(18, f_next - f - 10))
                    if dist > 0.25:
                        t, done = f, 0.0
                        lib.key(ch.root, "location", f, tuple(path[0]), "LINEAR")
                        for a, b in zip(path, path[1:]):          # leg by leg, facing each leg
                            leg = (b - a).length
                            n = max(4, int(frames * leg / dist))
                            d = b - a
                            self._face(who, t, math.degrees(math.atan2(d.x, -d.y)), 6, max_frames=n)
                            lib.key(ch.root, "location", t + n, tuple(b), "LINEAR")
                            t += n
                            done += leg
                        frames = t - f
                        segs.append((move, f, f + frames))
                        self.walks.setdefault(who, []).append((f, f + frames))
                        for s in range(f + 8, f + frames, 14 if move == "walk" else 9):
                            self.sound("footstep grass", s, 0.5)
                        self.where[who] = dest
                        f += frames + 1
                look = c.get("look") or "camera"
                if look == "camera":
                    self._face(who, f, 0.0)
                else:
                    tgt = self._target(look) if look in self.props or look in self.cast else None
                    if tgt is not None:
                        d = tgt - self.where[who]
                        deg = (math.degrees(math.atan2(d.x, -d.y)) + 180) % 360 - 180
                        if c.get("do") in FACE_OUT:
                            deg = max(-45.0, min(45.0, deg * 0.5))   # a reaction is played to us, 3/4 toward it
                        else:
                            deg = max(-100.0, min(100.0, deg))       # in profile at most, never the back
                        self._face(who, f, deg)
                clip = c.get("do") or "idle"
                if clip in MOVES:
                    clip = "idle"
                if clip in LOW and self._at_table(self.where[who]):
                    clip = "interact"          # kneeling behind the worktable hid Max completely
                # held at least HOLD frames, even when the next cue comes sooner (that one starts a bit later)
                end = min(total, max(f_next, f + HOLD))
                if f < end:
                    segs.append((clip, f, end))
                    self.sound(CLIP_SOUND.get(clip), f + 10, 0.8)
                    if clip in ("dance", "jump", "yes"):
                        ch.smile(f, big=True)
                    if not c.get("watch"):          # watching is not an action the QA must find on screen
                        self.act(f"{who} {clip}", ch.root, f, min(end, f + 60), min_share=0.08)
                f_last = end + 1
            if f_last <= total:
                segs.append((idle, f_last, total))
            self.mocap.perform(ch, segs, hips_height=0.56)     # local units: the kids' root scale applies

    def _plan_beat(self, bid):
        return next((b for b in self.plan.get("beats", []) if b["id"] == bid), {})

    # ------------------------------------------------------------------ prop events
    def event(self, bid, e):
        pid = e.get("prop")
        ob = self.props.get(pid)
        does = e.get("does")
        if ob is None or does not in EVENTS:
            return
        f = self.cue(bid, e.get("at"))
        first = self.t["beats"][0]
        if bid == first["id"] and does in SPECTACLE:
            f = min(f, first["f0"] + 12)     # the hook's surprise is ON SCREEN within the first 0.4 s
        size = self.sizes[pid]
        loc = Vector(ob.location)
        s = tuple(ob.scale)
        dur = 24
        if does == "appear":
            lib.visible(ob, 1, False)
            lib.visible(ob, f, True)
            lib.key(ob, "scale", f, (0.01, 0.01, 0.01))
            lib.tween(ob, "scale", f, f + 14, (0.01,) * 3, s, "pop")
        elif does == "vanish":
            lib.tween(ob, "scale", f, f + 12, s, (0.01,) * 3, "in")
            lib.visible(ob, f + 13, False)
        elif does in ("grow", "shrink"):
            k = 1.6 if does == "grow" else 0.6
            lib.tween(ob, "scale", f, f + dur, s, tuple(v * k for v in s), "pop")
        elif does == "rise":
            lib.tween(ob, "location", f, f + dur + 6, tuple(loc), tuple(loc + Vector((0, 0, size * 0.8))), "smooth")
        elif does == "drop":
            top = loc + Vector((0, 0, 3.0 + size))
            lib.visible(ob, 1, False)                     # not hanging in the air before it falls
            lib.visible(ob, f - 1, True)
            lib.key(ob, "location", f - 1, tuple(top), "CONSTANT")
            lib.tween(ob, "location", f, f + 22, tuple(top), tuple(loc), "bounce")
        elif does == "spin":
            r = tuple(ob.rotation_euler)
            lib.tween(ob, "rotation_euler", f, f + 36, r, (r[0], r[1], r[2] + 2 * math.pi), "smooth")
        elif does == "wobble":                                   # 2.5 Hz, decaying: reads, never strobes
            r = Vector(ob.rotation_euler)
            for i in range(0, 31, 2):
                lib.key(ob, "rotation_euler", f + i,
                        tuple(r + Vector((0, math.radians(7) * math.exp(-i / 14) * math.sin(i / 30 * 2 * math.pi * 2.5),
                                          0))))
        elif does == "bounce":
            for i in range(3):
                h = size * 0.35 * (0.6 ** i)
                lib.tween(ob, "location", f + i * 12, f + i * 12 + 6, tuple(loc), tuple(loc + Vector((0, 0, h))), "out")
                lib.tween(ob, "location", f + i * 12 + 6, f + i * 12 + 12, tuple(loc + Vector((0, 0, h))), tuple(loc),
                          "in")
        elif does == "slide":
            dest = self.spot(e.get("to"), (loc.x + 2, loc.y))
            lib.tween(ob, "location", f, f + 36, tuple(loc), tuple(dest), "smooth")
        elif does == "tip_over":
            r = tuple(ob.rotation_euler)
            lib.tween(ob, "rotation_euler", f, f + 18, r, (r[0], math.radians(85), r[2]), "bounce")
        elif does == "glow":
            light = bpy.data.lights.new(f"glow_{pid}", "POINT")
            light.color = (1.0, 0.85, 0.5)
            lob = lib.link(bpy.data.objects.new(f"glow_{pid}", light), ob)
            lob.location = (0, 0, size * 0.6)
            light.energy = 0
            light.keyframe_insert("energy", frame=f)
            light.energy = 400 * size
            light.keyframe_insert("energy", frame=f + 15)
        elif does in SPECTACLE:
            dur = self._spectacle(does, ob, pid, f, size, loc)
        self.sound(EVENT_SOUND.get(does), f, 1.0 if does in SPECTACLE else 0.9)
        self.act(f"{pid} {does}", ob, f, f + max(dur, 18), min_share=0.06)

    # ------------------------------------------------------------------ spectacle (hooks)
    def _bits(self, name, n, radius, mat, parent=None):
        """n small solid pieces, hidden until used (shared by puffs, confetti, sparks)."""
        out = []
        for i in range(n):
            b = toy.sphere(f"{name}_{i}", radius, (0, 0, -50), mat=mat, subdiv=1)
            b.visible_shadow = False
            out.append(b)
        return out

    def _spectacle(self, does, ob, pid, f, size, loc):
        """The surprises a hook opens with. All SOLID and smooth (opaque cartoon puffs, not transparent smoke;
        pieces on real ballistic arcs), so they read at once and never flicker. Returns the duration."""
        rnd = random.Random(sum(map(ord, f"{pid}{does}")) * 1000 + f)    # stable across runs (not hash())
        top = loc + Vector((0, 0, size * 0.95))
        if does in ("steam_burst", "smoke_burst"):
            col = "#F4F6F8" if does == "steam_burst" else "#9A9A9E"
            mat = toy.material(f"puff_{does}", toy.srgb(col), roughness=0.9)
            # puffs ~10 cm that rise about a metre: sized by the whole object (a 1.8 m bike) they were 20 cm
            # balls drifting 5 m up into the sky
            puffs = self._bits(f"{pid}_{does}{f}", 9, min(0.12, 0.06 + 0.03 * size), mat)
            for i, p in enumerate(puffs):
                d = Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.4, 0.2), 1.0)).normalized()
                start, f_i = top + Vector((0, 0, 0.02)), f + i
                end = start + d * rnd.uniform(0.5, 0.9) + Vector((0, 0, 0.35))
                lib.key(p, "location", 1, tuple(start), "CONSTANT")
                lib.key(p, "scale", 1, (0.01,) * 3, "CONSTANT")
                lib.key(p, "scale", f_i, (0.01,) * 3)
                lib.tween(p, "scale", f_i, f_i + 10, (0.01,) * 3, (1.0,) * 3, "out")
                lib.tween(p, "location", f_i, f_i + 34, tuple(start), tuple(end), "out")
                lib.tween(p, "scale", f_i + 18, f_i + 34, (1.0,) * 3, (0.01,) * 3, "in")
            return 40
        if does == "launch":                        # shoots up spinning, falls back, lands with a bounce
            h = 1.6 + size * 1.5
            r = Vector(ob.rotation_euler)
            lib.key(ob, "location", f, tuple(loc))
            lib.tween(ob, "location", f, f + 14, tuple(loc), tuple(loc + Vector((0, 0, h))), "out")
            lib.tween(ob, "location", f + 14, f + 28, tuple(loc + Vector((0, 0, h))), tuple(loc), "in")
            lib.tween(ob, "location", f + 28, f + 36, tuple(loc), tuple(loc + Vector((0, 0, h * 0.12))), "out")
            lib.tween(ob, "location", f + 36, f + 42, tuple(loc + Vector((0, 0, h * 0.12))), tuple(loc), "in")
            lib.tween(ob, "rotation_euler", f, f + 28, tuple(r), tuple(r + Vector((0, 0, 2 * math.pi))), "smooth")
            return 42
        if does in ("confetti", "sparks"):
            # sized to the object and slow enough to read: 2 cm sparks flying off-frame in half a second were
            # invisible in the hook
            # SLOW (a burst at full speed jumped several pixels a frame: the QA measured it as strobing), and
            # confetti is PAPER: flat squares tumbling down, not balls (the review saw "a burst of coloured balls")
            paper = does == "confetti"
            if paper:
                n, rad, life, slow, g = 30, max(0.035, size * 0.035), 60, 0.55, 3.0
            else:
                n, rad, life, slow, g = 18, max(0.035, size * 0.03), 34, 0.7, 4.9
            colours = ("#FF5D8F", "#FFD23F", "#3DBE6E", "#3A7BD5", "#FF7A00") if paper else ("#FFE58A",)
            bits = []
            for k, c in enumerate(colours):
                m = (toy.material(f"{does}_{k}", toy.srgb(c), roughness=0.4) if paper
                     else lib.flat(f"{does}_{k}", toy.srgb(c), rough=0.3, emission=6.0))     # sparks glow
                if paper:
                    for j in range(n // len(colours) + 1):
                        sq = toy.box(f"{pid}_{does}{f}_{k}_{j}", (rad * 2.2, rad * 1.6, rad * 0.12), (0, 0, -50),
                                     mat=m, bevel=0.0)
                        sq.visible_shadow = False
                        bits.append(sq)
                else:
                    bits += self._bits(f"{pid}_{does}{f}_{k}", n // len(colours) + 1, rad, m)
            for i, b in enumerate(bits):
                v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 0.4), rnd.uniform(1.0, 1.8))) * (0.9 + size * 0.6)
                lib.key(b, "location", 1, tuple(top), "CONSTANT")
                lib.key(b, "scale", 1, (0.01,) * 3, "CONSTANT")
                lib.key(b, "scale", f, (1.0,) * 3, "CONSTANT")
                spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 1.2   # rad/s: slow tumbles (fast flips flash)
                for s in range(0, life + 1, 2):          # an arc keyed every 2 frames, in slow motion
                    t = s / 30.0 * slow
                    p = top + v * t + Vector((0, 0, -0.5 * g * t * t))
                    p.z = max(0.02, p.z)
                    lib.key(b, "location", f + s, tuple(p), "LINEAR")
                    if paper:
                        lib.key(b, "rotation_euler", f + s, tuple(spin * t), "LINEAR")
                lib.tween(b, "scale", f + life - 8, f + life, (1.0,) * 3, (0.01,) * 3, "in")
            return life
        if does == "lean_recover":                  # tips toward a fall, then swings back upright by itself
            # lean SIDEWAYS: roll around the object's own long horizontal axis (a fixed Y axis made a bike that
            # stands lengthwise just nod)
            inv = ob.matrix_world.inverted()
            pts = [inv @ (o.matrix_world @ Vector(c)) for o in ob.children_recursive if o.type == "MESH"
                   for c in o.bound_box]
            ext_x = (max(p.x for p in pts) - min(p.x for p in pts)) if pts else 1.0
            ext_y = (max(p.y for p in pts) - min(p.y for p in pts)) if pts else 1.0
            axis = Vector((1, 0, 0)) if ext_x >= ext_y else Vector((0, 1, 0))
            r = Vector(ob.rotation_euler)
            tilt = math.radians(30)
            lean, back = tuple(r + axis * tilt), tuple(r - axis * tilt * 0.25)
            lib.key(ob, "rotation_euler", f, tuple(r))
            lib.tween(ob, "rotation_euler", f, f + 12, tuple(r), lean, "out")
            lib.tween(ob, "rotation_euler", f + 14, f + 28, lean, back, "smooth")
            lib.tween(ob, "rotation_euler", f + 28, f + 40, back, tuple(r), "smooth")
            return 40
        if does == "rumble":                        # a shake that GROWS (anticipation before a payoff)
            r = Vector(ob.rotation_euler)
            for i in range(0, 31, 2):
                a = math.radians(2 + 8 * i / 30) * math.sin(i / 30 * 2 * math.pi * 3.0)
                lib.key(ob, "rotation_euler", f + i, tuple(r + Vector((a, a * 0.6, 0))))
            lib.key(ob, "rotation_euler", f + 32, tuple(r))
            return 32
        return 24

    # ------------------------------------------------------------------ camera
    def _subject(self, on, f):
        """(centre, height) of what a shot is about at frame f."""
        bpy.context.scene.frame_set(f)
        if on in self.cast:
            ch = self.cast[on]
            h = self._height(on)
            return ch.root.matrix_world.translation + Vector((0, 0, h * 0.55)), h
        if on in self.props:
            ob = self.props[on]
            size = self.sizes[on]
            return ob.matrix_world.translation + Vector((0, 0, size * 0.5)), size
        pts = [ch.root.matrix_world.translation for ch in self.cast.values()]
        c = sum(pts, Vector()) / len(pts)
        span = max((p - c).length for p in pts) * 2 + 1.0
        return c + Vector((0, 0, 0.7)), max(1.6, span * 0.8)

    def _subject_meshes(self, on):
        if on in self.cast:
            return {o for o in self.cast[on].root.children_recursive if o.type == "MESH"}
        if on in self.props:
            return {o for o in self.props[on].children_recursive if o.type == "MESH"}
        return {o for ch in self.cast.values() for o in ch.root.children_recursive if o.type == "MESH"}

    def _clear_yaw(self, centre, width, yaw0, pitch, on, f):
        """The yaw nearest yaw0 from which nothing stands between the camera and the subject (a picnic table
        hid a kid in the foreground). Rays to the subject's centre and a little above and below it."""
        scene = bpy.context.scene
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        mine = {o.name for o in self._subject_meshes(on)}
        if on in self.on_table and self.table is not None:      # the table a prop stands on is part of the shot
            mine |= {o.name for o in self.table.children_recursive if o.type == "MESH"}
        for yaw in sorted({yaw0, -yaw0, 0, 18, -18, 30, -30, 42, -42}, key=lambda y: abs(y - yaw0)):
            cam, _aim = self.cam.pose(centre, width, yaw, pitch)
            blocked = False
            for dz in (0.0, width * 0.25, -width * 0.25):
                tgt = Vector(centre) + Vector((0, 0, dz))
                d = tgt - cam
                hit, _loc, _n, _i, ob, _m = scene.ray_cast(dg, cam, d.normalized(), distance=d.length - 0.05)
                if hit and ob is not None and ob.name not in mine and ob.name != "Ground":
                    blocked = True
                    break
            if not blocked:
                return yaw
        return yaw0

    def _include_actors(self, b, pb, centre, width, frame, on):
        """Everyone who ACTS in the beat is in the shot: a kid jumping or a prop wobbling out of frame (the QA
        found most actions of a beat off screen) is the most confusing thing a film can do. The shot widens
        and re-centres over the subject + the characters and props of this beat's cast and events (up to 8 m);
        a close-up keeps only what is within 2 m of its subject."""
        names = {c.get("who") for c in pb.get("cast", [])} | {e.get("prop") for e in pb.get("events", [])}
        names = {n for n in names if n and (n in self.cast or n in self.props) and n != on}
        if not names:
            return centre, width
        near = 2.0 if frame == "close" else 3.0     # actors further away walk in (perform's blocking) instead:
        xs = [centre.x - width * 0.3, centre.x + width * 0.3]  # stretching the shot to 8 m made everyone specks
        zs = [centre.z]
        for f in (b["f0"], (b["f0"] + b["f1"]) // 2, b["f1"]):
            for n in names:
                c, h = self._subject(n, f)
                if (Vector((c.x, c.y)) - Vector((centre.x, centre.y))).length > near:
                    continue
                xs += [c.x - 0.35, c.x + 0.35]
                zs.append(c.z)
        span = (max(xs) - min(xs)) * 1.2
        if span <= width:
            return centre, width
        new_c = Vector(((max(xs) + min(xs)) / 2, centre.y, (max(zs) + min(zs)) / 2 if frame != "close" else centre.z))
        return new_c, min(MAX_SHOT_WIDTH, span)

    def _reactor(self, pb, on):
        """Who the edit cuts to for the reaction: a kid if one acts in the beat, else Max (never the subject)."""
        acting = [c.get("who") for c in pb.get("cast", []) if c.get("who") in self.cast and c.get("who") != on]
        for who in ("Kid1", "Kid2", "Max"):
            if who in acting:
                return who
        return None

    def _near(self, a, b, f):
        """Two subjects one shot holds anyway: both on the worktable, or props within 0.6 m of each other."""
        if a == b:
            return True
        if a in self.on_table and b in self.on_table:
            return True
        if a in self.props and b in self.props:
            return (self._subject(a, f)[0] - self._subject(b, f)[0]).length < 0.6
        return False

    def moments(self, b, pb, on):
        """[(first frame, subject)]: the beat's edit. The camera goes where the sentence's action is: each prop
        event is filmed AS it happens (the QA found most events off screen while the camera held the beat's
        first subject, and the narration then described things nobody saw). Shots last >= MIN_SHOT frames."""
        f0, f1 = b["f0"], b["f1"]
        evs = sorted((self.cue(b["id"], e.get("at")), e["prop"]) for e in pb.get("events", [])
                     if e.get("prop") in self.props and e.get("does") in EVENTS)
        if evs and evs[0][0] - f0 < MIN_SHOT and not any(self._near(pid, on, f) and f - f0 < MIN_SHOT
                                                         for f, pid in evs):
            on = evs[0][1]          # the action starts at once and the writer's subject does nothing yet: open on it
        out = [[f0, on, set()]]
        for f, pid in evs:
            last_f, last_on, extras = out[-1]
            if self._near(pid, last_on, f) or pid in extras:
                continue
            start = max(f0, f - 6)                    # just before it moves
            if start - last_f < MIN_SHOT:
                start = last_f + MIN_SHOT
                if start > f + 12:
                    # too soon for its own cut: the shot holding frames it too (a wheel popping up on the other
                    # side 7 frames after the first one was never seen)
                    extras.add(pid)
                    continue
            if f1 - start < MIN_SHOT:
                extras.add(pid)
                continue
            out.append([start, pid, set()])
        return [tuple(m) for m in out]

    def shoot(self, b):
        """The beat's camera, EDITED: a shot per acting prop as its event happens (see moments), then a close-up
        of the main reactor in a long beat. A tall frame cannot hold a group up close: one shot stretched over
        everyone left tiny distant figures over a lawn, and the hook never stopped a scroll."""
        pb = self._plan_beat(b["id"])
        shot = pb.get("shot") or {}
        on, frame = shot.get("on") or "family", shot.get("frame", "medium")
        move = shot.get("move", "push_in")
        hook = b["id"] == self.t["beats"][0]["id"]
        f0, f1 = b["f0"], b["f1"]
        cuts = self.moments(b, pb, on)
        reactor = self._reactor(pb, on)
        last = cuts[-1][0]
        if reactor and f1 - last >= 75 and reactor not in {s for _f, s, _x in cuts}:
            fm = last + int((f1 - last) * 0.55)
            # never a close-up of someone walking: a kid crossing 5 m in a close-up made the frame 11 m wide
            # (or, chased by the camera, strobed the lawn). Wait until they arrive; no time left -> no cut,
            # they walk into the subject's shot instead.
            for w0, w1 in getattr(self, "walks", {}).get(reactor, []):
                if w0 <= f1 and w1 >= fm:
                    fm = max(fm, w1 + 1)
            if f1 - fm >= MIN_SHOT + 6 and fm - last >= MIN_SHOT:
                cuts.append((fm, reactor, set()))
        single = len(cuts) == 1
        for k, (s0, subj, extras) in enumerate(cuts):
            s1 = cuts[k + 1][0] - 1 if k + 1 < len(cuts) else f1
            if single and not extras:
                must = {subj} | {c.get("who") for c in pb.get("cast", [])}
                self._shot(b, pb, s0, s1, subj, frame if subj == on else "medium", move, must, hook)
                continue
            if subj in self.cast:
                fr, mv = "close", "push_in"
            elif subj == on:
                fr, mv = ("close" if hook else frame), move
            else:
                fr, mv = "medium", "static"
            self._shot(b, pb, s0, s1, subj, fr, mv, {subj}, True, extras)

    def _shot(self, b, pb, f0, f1, on, frame, move, must, tight, extras=()):
        """One camera move over f0..f1 on `on`. tight: frame the subject alone (no widening for other actors, no
        lower-third lift). extras: props acting during the shot that it must take in too."""
        mid = (f0 + f1) // 2
        centre, h = self._subject(on, mid)
        # framing follows the subject's size: a 0.25 m gauge needs a 0.75 m wide close-up, a person 1.6 m;
        # a tall prop (a 10 m pole) is framed by its lower part, where the story happens
        h = min(h, 3.0)
        if on in self.props:
            width = {"wide": min(MAX_SHOT_WIDTH, max(3.6, h * 2.6)), "medium": max(1.4, h * 4.0) if on in self.on_table
                     else max(2.0, h * 1.6), "close": max(0.6, h * 3.0) if on in self.on_table
                     else max(1.2, h * 1.2)}.get(frame, max(1.4, h * 2.0))
        else:
            width = {"wide": min(MAX_SHOT_WIDTH, max(3.6, h * 2.6)), "medium": max(2.0, h * 1.35),
                     "close": max(1.3, h * 1.1)}.get(frame, h * 1.35)
        if tight:
            # tight on its subject, never widened for bystanders nor lifted: "tiny distant figures" is exactly
            # what makes people scroll past
            width = min(width, max(1.6, h * 1.25)) if on in self.props else width
        else:
            centre, width = self._include_actors(b, pb, centre, width, frame, on)
        if extras:
            pts = [centre] + [self._subject(x, mid)[0] for x in extras]
            lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            centre = (lo + hi) / 2
            width = max(width, min(MAX_SHOT_WIDTH, (hi.x - lo.x) * 1.3 + h * 0.8))
        if frame == "close" and (on in self.cast):
            centre = centre + Vector((0, 0, h * 0.25))      # faces, not belts
        lift = Vector()
        if frame in ("medium", "wide") and on not in self.on_table and not tight:
            # the subject on the LOWER THIRD of the tall frame (house and sky above it): centred, half of every
            # vertical frame was lawn
            lift = Vector((0, 0, width * 16 / 9 * 0.16))
        if on in self.on_table and frame in ("close", "medium"):
            # a gauge alone in a vertical frame was mostly empty tabletop: rise to take in Max's face behind it
            lift = Vector((0, 0, 0.45))       # 0.3 still cut Max's hat off when he leaned over the table
            width = max(width, 1.2 if frame == "close" else 1.7)
        centre = centre + lift
        yaw0 = self.rnd.choice((-14, -8, 8, 14))
        if frame == "close" and on in self.cast:
            # in FRONT of the face (a reaction close-up filmed Kid1's back as she looked at the bike); never more
            # than 40 degrees round, where the set ends
            bpy.context.scene.frame_set(mid)
            facing = math.degrees(self.cast[on].root.matrix_world.to_euler().z)
            yaw0 = max(-40.0, min(40.0, (facing + 180) % 360 - 180))
        end_c, _h = self._subject(on, f1)
        end_c = end_c + lift
        travel = end_c - centre
        if frame == "close" and (on in self.cast):
            end_c = end_c + Vector((0, 0, h * 0.25))
        if travel.length > 1.0:          # the subject walks: film it from the side it walks across, not its back
            yaw0 = 40 if travel.x < 0 else -40
        walking = travel.length > 0.6
        if walking:
            # one calm frame over the whole path: chasing a walking kid in close-up broke every speed limit, the
            # move was cut to a third and the kid walked out of the frame
            centre = centre + travel * 0.5
            width = max(width, min(MAX_SHOT_WIDTH, travel.length + h * 0.9))
        pitch = {"close": 8, "medium": 4, "wide": 6}.get(frame, 5)    # near kids' eye level: from above, a tall frame was half lawn
        yaw0 = self._clear_yaw(centre, width, yaw0, pitch, on, (f0 + f1) // 2)
        a = dict(center=tuple(centre), width=width, yaw=yaw0, pitch=pitch)
        b2 = dict(a)
        if move == "push_in":
            b2["width"] = width * 0.82
        elif move == "pull_out":
            a["width"], b2["width"] = width * 0.82, width
        elif move == "orbit_left":
            b2["yaw"] = yaw0 - 16
        elif move == "orbit_right":
            b2["yaw"] = yaw0 + 16
        else:
            b2["width"] = width * 0.96
        b2["center"] = (tuple(Vector(a["center"]) + travel * 0.08) if walking
                        else tuple(Vector(a["center"]).lerp(end_c, 0.7)))
        self.cam.shot(f0, f1, a, b2)
        # checked on the camera as KEYED: the camera may glide on from the previous shot instead of cutting,
        # so the framing it really films can differ from the one asked for
        shifts = 0
        # who must be WHOLE (`must`): the subject, and in a single-shot beat whoever acts in it. Anyone else may be
        # cut by the edge (normal film language): widening for bystanders made a tight hook "tiny distant figures"
        for _ in range(8):
            cut_top, cuts = self._cropped(f0, f1, on, must)
            if not (cut_top or cuts):
                break
            if all(who not in must for who, _ in cuts) and not cut_top:
                if shifts >= 1:
                    break                       # one slide tried: a bystander at the edge is acceptable
            bystanders = {d for who, d in cuts if who != on}
            if not cut_top and bystanders and len(bystanders) == 1 and all(who != on for who, _ in cuts) \
                    and shifts < 1:     # one small slide at most: three slid the SUBJECT out of frame
                # a bystander half out at one side: slide the frame AWAY so they leave it (zooming out to fit
                # them made the subject tiny)
                d = bystanders.pop()
                for pose in (a, b2):
                    y = math.radians(pose.get("yaw", 0))
                    right = Vector((math.cos(y), math.sin(y), 0))
                    pose["center"] = tuple(Vector(pose["center"]) - right * d * 0.12 * pose["width"])
                shifts += 1
            else:
                if max(a["width"], b2["width"]) >= MAX_SHOT_WIDTH:
                    break                       # never wider: tiny distant figures are worse than a cut edge
                for pose in (a, b2):
                    pose["width"] = min(MAX_SHOT_WIDTH, pose["width"] * 1.12)
                    if cut_top:
                        pose["center"] = tuple(Vector(pose["center"]) + Vector((0, 0, 0.06 * pose["width"])))
            self.cam.shot(f0, f1, a, b2)

    def _cropped(self, f0, f1, on=None, must=None):
        """(cut at the top, [(who, side)] cut at a side, side -1 left / +1 right): is any character PARTLY in
        frame at five points of the shot? A head with its hat sliced off, or a kid half outside the edge, reads
        as a mistake; fully in or fully out is fine."""
        from bpy_extras.object_utils import world_to_camera_view
        scene = bpy.context.scene
        top, side = False, set()
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            scene.frame_set(int(round(f0 + (f1 - f0) * t)))
            for who, ch in self.cast.items():
                s = LOOKS[who].get("scale", 1.0)
                base = ch.root.matrix_world.translation
                h = self._height(who) + 0.15 * s
                pts = [world_to_camera_view(scene, scene.camera, base + Vector((dx * 0.3 * s, dy * 0.25 * s, z)))
                       for dx in (-1, 1) for dy in (-1, 1) for z in (0.0, h)]
                pts = [p for p in pts if p.z > 0.05]
                inside = [0.015 < p.x < 0.985 and 0.015 < p.y < 0.985 for p in pts]
                if pts and any(inside) and not all(inside):
                    top = top or ((must is None or who in must) and any(p.y >= 0.985 for p in pts))
                    if any(p.x <= 0.015 for p in pts):
                        side.add((who, -1))
                    if any(p.x >= 0.985 for p in pts):
                        side.add((who, 1))
            if on in self.props:          # the SUBJECT prop must be whole: a bike cut by the edge killed the hook
                ob = self.props[on]
                meshes = [o for o in ob.children_recursive if o.type == "MESH"]
                pts = [world_to_camera_view(scene, scene.camera, o.matrix_world @ Vector(c))
                       for o in meshes for c in o.bound_box]
                pts = [p for p in pts if p.z > 0.05]
                if pts and not all(0.0 < p.x < 1.0 and 0.0 < p.y < 1.0 for p in pts):
                    top = top or any(p.y >= 1.0 for p in pts)
                    side.add((on, 1 if any(p.x >= 1.0 for p in pts) else -1))
        return top, sorted(side)

    # ------------------------------------------------------------------ film
    def film(self):
        # props move FIRST, so the characters walk to where things really are when they get there
        for b in self.t["beats"]:
            for e in self._plan_beat(b["id"]).get("events", []):
                self.event(b["id"], e)
        self.perform()
        for b in self.t["beats"]:
            self.shoot(b)
        return self
