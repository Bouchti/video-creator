"""Paint the cast as anime emotion sheets with fal, using a style reference sheet.
python scripts/anime_cast.py <name>|all [--model fal-ai/nano-banana-pro/edit]
Writes out/anime/<name>_sheet.png (10 expressions, head + shoulders) and <name>_body.png."""
import os, sys, json, argparse, urllib.request
import fal_client
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(os.path.dirname(ROOT), ".env"), encoding="utf-8"):
    if line.startswith("FAL_API_KEY="): os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
REF = os.path.join(os.path.expanduser("~"), "Downloads", "Three-Generation Emotion Sheet.png")
OUT = os.path.join(ROOT, "out", "anime"); os.makedirs(OUT, exist_ok=True)
EXPRS = ("TOP ROW left to right: 1 neutral (calm, mouth closed), 2 smirk (one-sided grin, half-lidded eyes), 3 suspicious (narrowed side-eye, one brow down), "
 "4 angry (brows slammed down into a V, glaring, clenched teeth bared, red anger mark), 5 sad (brows up in the middle, mouth open, big blue tear streams). "
 "BOTTOM ROW left to right: 6 panic (wide eyes, small pupils, open wavy mouth, sweat drops), 7 shock (blue-faded face, blank white eyes, mouth open in an O), "
 "8 laugh (eyes closed in happy arcs, wide open laughing mouth), 9 excited (sparkling eyes, big open smile, gold sparkles), 10 yell (furious, mouth wide open shouting, red anger mark)")
CAST = {
 "dave": "Dave, a 35-year-old working-class British man: square strong jaw, light stubble shadow, thick brown mustache, bushy brows, green eyes, messy chestnut-brown hair sticking out under a brown tweed flat cap, green work jacket with a red neckerchief",
 "repairman": "a repairman around 40: long lean face with defined cheekbones, short black goatee, slightly buck front teeth, blue eyes, messy black hair under a glossy blue baseball cap, white t-shirt under blue denim overalls",
 "boss": "the boss, a stout man around 65: round jowly face, bulbous nose, bushy grey brows, grey combover with puffy grey sides, rosy cheeks, purple polka-dot suit with a gold watch chain and red tie",
 "worker": "a construction worker around 30: broad square face, thick blond full beard kept to the jaw and chin, single heavy blond unibrow, blue eyes, spiky blond hair under a yellow hard hat, neon-green hi-vis vest over a blue shirt",
 "assistant": "a shop assistant, a woman around 28: soft V-shaped face, freckles, green eyes, round glasses, copper-red hair in a top bun, white lab-style shop coat with pens in the pocket and a blue tie",
 "bailiff": "a bailiff around 60: hard square face, grey mutton-chop sideburns and grey mustache, thick grey brows, dark red eyes, slicked grey hair under a black bowler hat, black suit, white shirt, maroon suspenders",
}
def up(p): return fal_client.upload_file(p)
def run(model, prompt, imgs):
    r = fal_client.subscribe(model, arguments={"prompt": prompt, "image_urls": imgs, "num_images": 1, "output_format": "png", "aspect_ratio": "16:9" if "grid" in prompt else "9:16"}, with_logs=False)
    return r["images"][0]["url"]
def get(url, path): urllib.request.urlretrieve(url, path); print("->", path)
ap = argparse.ArgumentParser(); ap.add_argument("who"); ap.add_argument("--model", default="fal-ai/nano-banana-pro/edit"); ap.add_argument("--body", action="store_true"); ap.add_argument("--redo", action="store_true")
a = ap.parse_args()
ref = up(REF)
for name in (CAST if a.who == "all" else [a.who]):
    desc = CAST[name]
    sheet = os.path.join(OUT, f"{name}_sheet.png")
    if a.redo and os.path.exists(sheet): os.replace(sheet, sheet.replace(".png", "_old.png"))
    if not os.path.exists(sheet):
        p = (f"Make a NEW character emotion sheet in exactly the same art style as the reference image (polished modern anime, clean dark line art, soft cel shading, glossy detailed eyes, hair drawn in strand clumps with highlights, warm skin, light blue background, white sticker outline). "
             f"The character: {desc}. A grid of exactly 10 head-and-shoulders portraits in 2 rows of 5, evenly spaced, each portrait the same size, of this SAME character, identical design in every panel, front view. {EXPRS}. "
             "Use the same comic extras as the reference: red anger mark for angry and yell, big blue tear streams for sad, sweat drops for panic, blue-faded face with white blank eyes for shock, closed happy eyes for laugh, gold sparkles for excited. "
             "Adult proportions, not a kid: a real adult face with a defined jaw. No text, no labels.")
        get(run(a.model, p, [ref]), sheet)
    if a.body:
        body = os.path.join(OUT, f"{name}_body.png")
        if not os.path.exists(body):
            p = (f"Full-body character design of this same character, standing, three-quarter front view, whole figure from hat to shoes visible, same anime art style and same face as the sheet, adult proportions about 7 heads tall, plain light blue background, white sticker outline, no text. Character: {desc}.")
            get(run(a.model, p, [up(sheet), ref]), body)
