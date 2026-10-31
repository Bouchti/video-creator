"""
BlenderKit asset resolver: a free-text need ("wooden picnic table", "grass") -> a downloaded, checked, FREE
BlenderKit model or material on this machine. Runs outside Blender (plain HTTP), before the render.

    from agents import blenderkit
    a = blenderkit.resolve("wooden picnic table", kind="model", size_m=1.8, story="Max fixes the table")
    a -> {"query", "kind", "assetBaseId", "name", "path", "dimensions", "license", "author"} or None

How a pick is made:
  1. search the free assets (BLENDERKIT_API_KEY in .env, the same key the Blender add-on uses);
  2. keep only results whose name / tags / description contain the query's LAST word (the thing itself:
     "picnic TABLE"), with a sane polygon count (huge photo scans stall Eevee and flicker when small);
  3. the vision check (agents/vision.rank_images) looks at the top thumbnails and keeps the one that really
     shows the thing; without it, BlenderKit's own quality score decides;
  4. the 1K-texture .blend is downloaded to assets/blenderkit/<assetBaseId>/ (git-ignored: the royalty-free
     licence allows use in monetised videos but not redistributing the files) and the choice is recorded in
     assets/blenderkit_index.json (committed), so every machine downloads the same asset for the same need.
Never fatal: any failure returns None and the world builds that prop from its procedural fallback.
"""
import json
import logging
import os
import re
import uuid

import requests

from config.paths import PROJECT_ROOT, slug

log = logging.getLogger("pipeline")
API = "https://www.blenderkit.com/api/v1"
OUT = os.path.join(PROJECT_ROOT, "assets", "blenderkit")
INDEX = os.path.join(PROJECT_ROOT, "assets", "blenderkit_index.json")
MAX_FACES = 400_000
RESOLUTIONS = ("resolution_1K", "resolution_2K", "blend")     # preferred download, best first
ALLOWED_LICENSES = {"royalty_free", "cc_zero"}


def _key():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    except ImportError:
        pass
    return (os.getenv("BLENDERKIT_API_KEY") or "").strip().strip('"')


def available():
    return bool(_key()) and os.getenv("BLENDERKIT", "1") != "0"


def _headers():
    return {"Authorization": f"Bearer {_key()}", "User-Agent": "video-creator/1.0"}


def _norm(query, kind):
    return f"{kind}:{' '.join(re.findall(r'[a-z0-9]+', query.lower()))}"


def _load_index():
    try:
        with open(INDEX, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_index(index):
    with open(INDEX, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, sort_keys=True)


def _words(text):
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z]+", (text or "").lower())}


def search(query, kind="model", n=24):
    q = f"{query}+asset_type:{kind}+is_free:true"
    r = requests.get(f"{API}/search/?query={q}&dict_parameters=1&page_size={n}&addon_version=3.12.0",
                     headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json().get("results", [])


GENERIC = {"set", "kit", "pair", "piece", "unit", "model", "object", "big", "small", "large", "old", "new"}


def need_words(query):
    return _words(query) - GENERIC or _words(query)


def head_word(query):
    """The thing itself: the last word that is not a generic one ("swing SET" -> swing, "garden SHED" -> shed)."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in GENERIC] or query.lower().split()
    return words[-1] if words else ""


def relevant(a, query):
    """The asset IS the query's thing: at least one real word of the need is in its own NAME (a stone statue
    tagged "stone" is not a curling stone; footballs from a "garden shed" pack are not a shed), and every word
    appears somewhere about it (name, tags, description)."""
    need, head = need_words(query), head_word(query)
    name = _words(a.get("name") or "")
    about = _words(" ".join([a.get("name") or "", " ".join(a.get("tags") or []), a.get("description") or ""]))
    head = _words(head) or {head}
    return bool(need) and bool(head & name) and need <= about    # the THING in the name ("Garden Gnome" != shed)


def _faces(a):
    return (a.get("dictParameters") or {}).get("faceCount") or 0


KITS = re.compile(r"\b(modular|kit|pack|set|collection|bundle|assets|library|scene|environment)\b", re.I)


THEMED = re.compile(r"\b(witch\w*|halloween|christmas|xmas|fantasy|medieval|sci-?fi|steampunk|zombie|horror|"
                    r"cyberpunk|alien|magic\w*|cartoon|toy|miniature|low-?poly)\b", re.I)


def candidates(results, query, kind):
    keep = []
    for a in results:
        # an everyday need gets the everyday thing: "broom" picked a Witches Broom
        if THEMED.search(a.get("name") or "") and not THEMED.search(query):
            continue
        # one object per prop: a "Modular Electricity Poles" kit dropped a dozen poles all over the stage
        if kind == "model" and KITS.search(a.get("name") or "") and not KITS.search(query):
            continue
        if not a.get("isFree") or (a.get("license") or "royalty_free") not in ALLOWED_LICENSES:
            continue
        if kind == "model" and _faces(a) > MAX_FACES:
            continue
        if not relevant(a, query):
            continue
        keep.append(a)
    # named after the thing beats merely mentioning it (a "garden shed set" description lists footballs too)
    need = need_words(query)        # every word in the name ("Drinking Glass") beats one ("Pepsi Glass Bottle")
    keep.sort(key=lambda a: (len(need - _words(a.get("name") or "")), -(a.get("score") or 0)))
    return keep


def _thumb(a, folder):
    url = a.get("thumbnailMiddleUrl") or a.get("thumbnailSmallUrl")
    if not url:
        return None
    path = os.path.join(folder, f"{a['assetBaseId']}.jpg")
    if not os.path.isfile(path):
        r = requests.get(url, timeout=60)
        if not r.ok:
            return None
        with open(path, "wb") as fh:
            fh.write(r.content)
    return path


def choose(cands, query, story="", top=6, strict=False):
    """Vision pick among the top thumbnails; falls back to the best BlenderKit score. strict (a relaxed search
    for just the last word): a candidate the vision check did not confirm must carry EVERY word of the need
    in its name, or a "tesla coil" turns into a heating coil."""
    if strict:     # a relaxed search ("stone") must still NAME the thing: a statue tagged stone is not one
        head = _words(head_word(query))
        cands = [a for a in cands if head & _words(a.get("name") or "")]
    cands = cands[:top]
    if len(cands) <= 1:
        return cands[0] if cands else None
    try:
        from agents import vision
        if not vision.vision_enabled():
            return cands[0]
        folder = os.path.join(OUT, "_thumbs")
        os.makedirs(folder, exist_ok=True)
        pairs = [(a, _thumb(a, folder)) for a in cands]
        pairs = [(a, p) for a, p in pairs if p]
        order = vision.rank_images(f"a 3D model whose main object is clearly a {query} (a simple backdrop or "
                                   "small extra props are fine)", story or query, [p for _a, p in pairs])
        if order:
            return pairs[order[0]][0]
        if order == []:              # the vision check rejected every candidate: only a NAMED match is safe
            need = query.lower().split() if strict else query.lower().split()[-1:]
            named = [a for a in cands if all(w in (a.get("name") or "").lower() for w in need)]
            return named[0] if named else None
    except Exception as e:  # noqa: BLE001
        log.warning(f"  blenderkit: vision pick failed ({str(e)[:80]}); using the search score")
    return cands[0]


def download(a):
    base = a["assetBaseId"]
    folder = os.path.join(OUT, base)
    files = {f.get("fileType"): f for f in a.get("files", [])}
    for res in RESOLUTIONS:
        f = files.get(res)
        if not f:
            continue
        path = os.path.join(folder, f"{slug(a.get('name') or base, 50)}_{res}.blend")
        if os.path.isfile(path):
            return path
        d = requests.get(f["downloadUrl"], params={"scene_uuid": str(uuid.uuid4())}, headers=_headers(), timeout=60)
        d.raise_for_status()
        signed = d.json().get("filePath")
        if not signed:
            continue
        os.makedirs(folder, exist_ok=True)
        with requests.get(signed, stream=True, timeout=900) as s:
            s.raise_for_status()
            with open(path + ".part", "wb") as fh:
                for chunk in s.iter_content(1 << 20):
                    fh.write(chunk)
        os.replace(path + ".part", path)
        return path
    return None


def _record(a, query, kind, path):
    p = a.get("dictParameters") or {}
    dims = [p.get("dimensionX"), p.get("dimensionY"), p.get("dimensionZ")]
    return {"query": query, "kind": kind, "assetBaseId": a["assetBaseId"], "name": a.get("name"),
            "license": a.get("license"), "author": (a.get("author") or {}).get("fullName")
            if isinstance(a.get("author"), dict) else None,
            "dimensions": dims if all(isinstance(d, (int, float)) and d > 0 for d in dims) else None,
            "file": os.path.relpath(path, PROJECT_ROOT).replace("\\", "/") if path else None}


def _by_id(base):
    r = requests.get(f"{API}/search/?query=asset_base_id:{base}&dict_parameters=1", headers=_headers(), timeout=60)
    r.raise_for_status()
    res = r.json().get("results", [])
    return res[0] if res else None


def resolve_id(base, kind="material", label=None):
    """A CURATED asset by its assetBaseId (the stage's ground looks were picked by eye, not by search)."""
    if not base or not available():
        return None
    key = f"{kind}:id:{base}"
    index = _load_index()
    rec = index.get(key)
    if rec and rec.get("file") and os.path.isfile(os.path.join(PROJECT_ROOT, rec["file"])):
        return dict(rec, path=os.path.join(PROJECT_ROOT, rec["file"]))
    try:
        a = _by_id(base)
        path = download(a) if a and a.get("isFree") else None
        if not path:
            return None
        rec = _record(a, label or a.get("name") or base, kind, path)
        index[key] = rec
        _save_index(index)
        return dict(rec, path=path)
    except Exception as e:  # noqa: BLE001
        log.warning(f"  blenderkit: asset {base} failed: {str(e)[:160]}")
        return None


def resolve(query, kind="model", size_m=None, story=""):
    """A local .blend for the need, or None. Cached by (kind, query) in the committed index."""
    if not query or not available():
        return None
    key = _norm(query, kind)
    index = _load_index()
    try:
        if key in index:
            rec = index[key]
            if rec is None:
                return None                         # searched before, nothing fit: don't pay for it again
            if rec.get("file") and os.path.isfile(os.path.join(PROJECT_ROOT, rec["file"])):
                return dict(rec, path=os.path.join(PROJECT_ROOT, rec["file"]))
            a = _by_id(rec["assetBaseId"])           # another machine chose it: fetch the same asset
            path = download(a) if a else None
            if path:
                rec = _record(a, query, kind, path)
                index[key] = rec
                _save_index(index)
                return dict(rec, path=path)
        a = None
        tries = [query] + ([head_word(query)] if len(query.split()) > 1 else [])
        for q in tries:                               # the full need, then just the thing ("shed")
            # the vision check always judges against the FULL need: "coil" results must still be a tesla coil
            a = choose(candidates(search(q, kind), q, kind), query, story, strict=q != query)
            if a is not None:
                break
        if a is None:
            index[key] = None
            _save_index(index)
            log.info(f"  blenderkit: nothing fits '{query}' ({kind}); procedural fallback")
            return None
        path = download(a)
        if not path:
            return None
        rec = _record(a, query, kind, path)
        index[key] = rec
        _save_index(index)
        log.info(f"  blenderkit: '{query}' -> {rec['name']} ({rec['license']})")
        return dict(rec, path=path)
    except Exception as e:  # noqa: BLE001  (offline, key expired, API change: never fatal)
        log.warning(f"  blenderkit: '{query}' failed: {str(e)[:160]}")
        return None


# ------------------------------------------------------------------ props of a story set (cutaway-bk route)
PROPS_MANIFEST = os.path.join(OUT, "props_manifest.json")   # read by engine/props.py inside Blender
USES_PROPS = re.compile(r"from\s+engine\s+import\s+[^\n]*\bprops\b|import\s+engine\.props|from\s+engine\.props\s+import")
PROP_CALL = re.compile(r"""\bprop\(\s*["']([^"'\n]{2,60})["']\s*,\s*([0-9]+(?:\.[0-9]+)?)""")


def prop_key(query):
    return " ".join(str(query).lower().split())      # = engine/props.key


def code_props(code):
    """[(query, size_m)] a set's code asks BlenderKit for: its literal prop("query", size) calls, only when the
    set imports engine.props (every older set builds everything itself and is left alone)."""
    if not USES_PROPS.search(code or ""):
        return []
    seen, out = set(), []
    for q, size in PROP_CALL.findall(code):
        if prop_key(q) not in seen:
            seen.add(prop_key(q))
            out.append((q.strip(), float(size)))
    return out


def resolve_set_props(set_path, story=""):
    """Resolve every BlenderKit prop of a set BEFORE Blender runs and record it in PROPS_MANIFEST
    ({query: {"path", "name", "size_m"} or None}). Never fatal: a miss is None and the set's fallback builds
    the object. Returns the number of props found on BlenderKit."""
    try:
        with open(set_path, encoding="utf-8") as fh:
            wanted = code_props(fh.read())
    except OSError:
        return 0
    if not wanted:
        return 0
    try:
        with open(PROPS_MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        manifest = {}
    found = 0
    for query, size in wanted:
        k = prop_key(query)
        rec = manifest.get(k)
        if rec and os.path.isfile(os.path.join(PROJECT_ROOT, rec["path"])):
            found += 1
            continue
        a = resolve(query, "model", size, story)
        manifest[k] = ({"path": os.path.relpath(a["path"], PROJECT_ROOT), "name": a.get("name", ""), "size_m": size}
                       if a and a.get("path") else None)
        found += bool(manifest[k])
    os.makedirs(OUT, exist_ok=True)
    with open(PROPS_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    log.info(f"  blenderkit: {found} of {len(wanted)} set props from BlenderKit (the rest are built from primitives)")
    return found
