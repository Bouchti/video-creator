"""Cut the painted anime cast (out/anime/<name>_body.png + _sheet.png) into a sprite kit for the toon pipeline.
python scripts/anime_kit.py <name>|all [--exprs neutral,angry] [--model ...]
out/anime/kit/<name>/body_<expr>.png : full body, transparent, SAME body pixels for every expression (only the head changes)
out/anime/kit/<name>/face_<expr>.png : head-and-shoulders close-up cut from the 5x2 sheet, transparent
out/anime/kit/<name>/meta.json       : body bbox + head box (for framing close-ups)"""
import os, sys, json, argparse, urllib.request, io
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
import fal_client
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(os.path.dirname(ROOT), ".env"), encoding="utf-8"):
    if line.startswith("FAL_API_KEY="): os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
SRC = os.path.join(ROOT, "out", "anime")
EXPRS = ["neutral", "smirk", "suspicious", "angry", "sad", "panic", "shock", "laugh", "excited", "yell"]
LOOK = {
 "neutral": "calm neutral face, mouth closed", "smirk": "one-sided cocky grin, half-lidded eyes",
 "suspicious": "narrowed side-eye glance, one brow lowered, mouth flat", "angry": "brows slammed into a V, glaring, clenched teeth bared, red anime anger mark beside the head",
 "sad": "brows raised in the middle, mouth open, big blue anime tear streams down the cheeks", "panic": "wide eyes with tiny pupils, open wavy mouth, sweat drops",
 "shock": "anime shock: face faded blue from the top, blank white eyes, mouth open in an O", "laugh": "eyes closed in happy arcs, wide open laughing mouth",
 "talk": "calm, speaking mid-word with the mouth half open", "smirk_talk": "cocky one-sided grin while speaking mid-word, mouth half open",
 "blink": "calm neutral face with both eyes fully closed, mouth closed",
 "excited": "sparkling eyes, big open smile, small gold sparkles near the head", "yell": "furious, mouth wide open shouting, red anime anger mark beside the head",
}

def cutout(im: Image.Image) -> Image.Image:
    """Remove the flat/gradient light-blue backdrop: flood from the border through bluish-light pixels.
    The white sticker outline is not bluish, so the fill stops there and the outline stays."""
    a = np.asarray(im.convert("RGB")).astype(np.int16); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    bg = (b - r > 18) & (b > 170) & (g > 150)
    lab, _ = ndimage.label(bg)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])); edge = edge[edge > 0]
    m = np.isin(lab, edge)
    m = ndimage.binary_opening(m, iterations=1)
    alpha = Image.fromarray(np.where(m, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    out = im.convert("RGBA"); out.putalpha(alpha); return out

def fal_edit(img_path, prompt, model):
    url = fal_client.upload_file(img_path)
    r = fal_client.subscribe(model, arguments={"prompt": prompt, "image_urls": [url], "num_images": 1, "output_format": "png", "aspect_ratio": "9:16"})
    return Image.open(io.BytesIO(urllib.request.urlopen(r["images"][0]["url"]).read())).convert("RGB")

def head_box(alpha: np.ndarray):
    ys, xs = np.nonzero(alpha > 128); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    hh = int((y1 - y0) * 0.24)                     # head + hat + neck band of a ~7-head adult
    rows = alpha[y0:y0 + hh] > 128; cols = np.nonzero(rows.any(0))[0]
    return [int(x0), int(y0), int(x1), int(y1)], [int(cols.min()), int(y0), int(cols.max()), int(y0 + hh)]

def swap_head(base: Image.Image, var: Image.Image, hb):
    """Paste only the changed head pixels of `var` onto `base` (feathered), so bodies never jitter between expressions."""
    if var.size != base.size: var = var.resize(base.size, Image.LANCZOS)
    A = np.asarray(base.convert("RGB")).astype(np.float32); B = np.asarray(var).astype(np.float32)
    x0, y0, x1, y1 = hb; pad = int((x1 - x0) * 0.35)
    region = np.zeros(A.shape[:2], bool); region[max(0, y0 - pad):y1 + pad // 3, max(0, x0 - pad):x1 + pad] = True
    diff = np.abs(A - B).sum(-1) > 40
    m = ndimage.binary_dilation(ndimage.binary_closing(diff & region, iterations=4), iterations=10) & region
    soft = ndimage.gaussian_filter(m.astype(np.float32), 6)[..., None]
    out = A * (1 - soft) + B * soft
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

def sheet_faces(name, kit):
    """The sheet is a 5 x 2 grid: cut each cell, then drop the backdrop inside the cell."""
    s = Image.open(os.path.join(SRC, f"{name}_sheet.png")).convert("RGB"); W, H = s.size
    for i, e in enumerate(EXPRS):
        r, c = divmod(i, 5)
        cell = cutout(s.crop((c * W // 5, r * H // 2, (c + 1) * W // 5, (r + 1) * H // 2)))
        al = np.asarray(cell)[..., 3] > 128; lab, n = ndimage.label(al)
        if n:   # keep the biggest blob (the portrait) plus anything touching it (sparkles stay if big enough)
            sizes = ndimage.sum(al, lab, range(1, n + 1)); keep = np.isin(lab, [i + 1 for i, v in enumerate(sizes) if v > 0.004 * al.size])
            arr = np.asarray(cell).copy(); arr[..., 3] = np.where(keep, arr[..., 3], 0); cell = Image.fromarray(arr)
            ys, xs = np.nonzero(arr[..., 3] > 128); cell = cell.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        cell.save(os.path.join(kit, f"face_{e}.png"))

def build(name, exprs, model):
    kit = os.path.join(SRC, "kit", name); os.makedirs(kit, exist_ok=True)
    base_rgb = os.path.join(kit, "_base_neutral_rgb.png")
    if not os.path.exists(base_rgb):   # normalise the body to a calm neutral face first
        fal_edit(os.path.join(SRC, f"{name}_body.png"), f"Edit only the face: {LOOK['neutral']}. Keep the pose, outfit, hat, hair, art style, framing, white sticker outline and light blue background exactly identical.", model).save(base_rgb)
    base = Image.open(base_rgb).convert("RGB"); bcut = cutout(base)
    body_box, hb = head_box(np.asarray(bcut)[..., 3])
    bcut.save(os.path.join(kit, "body_neutral.png"))
    def one(e):
        raw = os.path.join(kit, f"_raw_{e}.png")
        if not os.path.exists(raw):
            fal_edit(base_rgb, f"Edit only the facial expression to: {LOOK[e]}. Keep the same character, same head size and position, same pose, outfit, hat, hair, art style, framing, white sticker outline and light blue background exactly identical.", model).save(raw)
        v = swap_head(base, Image.open(raw).convert("RGB"), hb)
        c = cutout(v); a = np.asarray(c).copy(); a[..., 3] = np.maximum(a[..., 3], np.asarray(bcut)[..., 3]) if False else a[..., 3]
        c.save(os.path.join(kit, f"body_{e}.png")); return e
    with ThreadPoolExecutor(5) as ex:
        for e in ex.map(one, [e for e in exprs if e != "neutral"]): print(f"  {name}: body_{e}")
    sheet_faces(name, kit)
    json.dump({"size": base.size, "body": body_box, "head": hb, "exprs": EXPRS}, open(os.path.join(kit, "meta.json"), "w"))
    print("kit ->", kit)

ap = argparse.ArgumentParser(); ap.add_argument("who"); ap.add_argument("--faces-only", action="store_true"); ap.add_argument("--exprs", default=",".join(EXPRS)); ap.add_argument("--model", default="fal-ai/nano-banana-pro/edit")
a = ap.parse_args()
names = ["dave", "repairman", "boss", "worker", "assistant", "bailiff"] if a.who == "all" else a.who.split(",")
if a.faces_only:
    for n in names: sheet_faces(n, os.path.join(SRC, "kit", n)); print("faces", n)
else:
    with ThreadPoolExecutor(len(names)) as ex: list(ex.map(lambda n: build(n, a.exprs.split(","), a.model), names))
