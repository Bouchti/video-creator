"""
Ready-to-post text for a finished film: TikTok caption + hashtags + cover idea, YouTube Shorts title,
description and tags, Instagram Reels caption + hashtags + alt text. Written next to the video as `<video>_post.txt` every time a film is produced.

Claude writes it from the film's script and fact sheet (same backend as the showrunner: the
subscription by default). Without Claude it falls back to a template built from the script.

    python -m agents.post_text output/films/<film>.json output/<film>.mp4
"""
import json
import logging
import os
import sys

log = logging.getLogger("pipeline")

RULES = """Write the posting text for this short vertical video.
- TikTok caption: line 1 is the funniest hook (at most ~70 characters, it shows before "more"),
  then 1-2 short lines on what happens and what the viewer learns, then the video's closing
  question on its own line. 1-3 fitting emojis. Then 5-6 hashtags: 2 searchable topic tags,
  1-2 broad tags for the video's field (#science, #history, ...), #learnontiktok, #fyp.
- Cover: which moment of the first 2 seconds to use as the cover, and a cover text of at most
  6 words.
- YouTube Shorts: a searchable title (a real question people type, then the hook, under 100
  characters, ending with #shorts); a description that tells the story in 2 lines, then
  "What you'll learn:" with 4-6 emoji bullets (each a real fact from the script, with its number),
  then the closing question, then 6-8 hashtags starting with #shorts; 8-12 search tags
  (comma-separated phrases people search).
- Instagram Reels: a caption whose first line is the hook (the first ~125 characters show before
  "more"), then 2-4 short lines that tell the story and the most surprising fact (with its number),
  line breaks between ideas, 2-4 emojis, then the closing question on its own line. Then 8-12
  hashtags mixing broad tags for the video's field (#science, #history, ...), topic and niche tags (no #fyp, no #learnontiktok).
  Plus an alt text: one plain sentence describing what is seen in the video, for accessibility.
- Never ask people to like, comment, follow or subscribe: end on the question only.
- Only facts that are in the script or the fact sheet. Plain text, no markdown headers."""

SCHEMA = {
    "type": "object",
    "properties": {
        "tiktok_caption": {"type": "string"},
        "tiktok_hashtags": {"type": "array", "items": {"type": "string"}},
        "cover_moment": {"type": "string"},
        "cover_text": {"type": "string"},
        "youtube_title": {"type": "string"},
        "youtube_description": {"type": "string"},
        "youtube_tags": {"type": "array", "items": {"type": "string"}},
        "instagram_caption": {"type": "string"},
        "instagram_hashtags": {"type": "array", "items": {"type": "string"}},
        "instagram_alt_text": {"type": "string"},
    },
    "required": ["tiktok_caption", "tiktok_hashtags", "cover_moment", "cover_text", "youtube_title",
                 "youtube_description", "youtube_tags", "instagram_caption", "instagram_hashtags",
                 "instagram_alt_text"],
    "additionalProperties": False,
}


def _ask_claude(film):
    from agents import showrunner as sr
    script = "\n".join(f"- [{b.get('action')}] {b['text']}" for b in film["beats"])
    meta = film.get("meta", {})
    prompt = (f"{RULES}\n\nTITLE: {film.get('title', '')}\nCLOSING QUESTION: {film.get('cta') or ''}\n\n"
              f"SCRIPT (in order):\n{script}\n\nFACT SHEET:\n{meta.get('facts', '')[:4000]}")
    return sr._call("You write social media posts for a premium educational TikTok/YouTube channel.", prompt,
                    SCHEMA, effort="low")


def _normalise(film):
    """Accept both Blender films and the main pipeline's evaluated-script schema."""
    value = dict(film)
    value.setdefault("title", value.get("video_title", ""))
    meta = dict(value.get("meta") or {})
    meta.setdefault("caption", value.get("description", ""))
    meta.setdefault("hashtags", value.get("hashtags", []))
    facts = value.get("fact_sheet") or value.get("research_summary") or ""
    if not facts and value.get("research_sources"):         # main pipeline: the evidence it was checked against
        facts = "\n\n".join(f"{s.get('title', '')}: {s.get('evidence', '')[:1200]}"
                            for s in value["research_sources"] if isinstance(s, dict))
    meta.setdefault("facts", facts)
    value["meta"] = meta
    if not value.get("cta") and value.get("beats"):
        last = value["beats"][-1].get("text", "")
        value["cta"] = last if last.rstrip().endswith("?") else ""
    return value


def _template(film):
    meta = film.get("meta", {})
    hook = film["beats"][0]["text"] if film.get("beats") else film.get("title", "")
    q = film.get("cta") or ""
    tags = [t if t.startswith("#") else f"#{t}" for t in meta.get("hashtags", [])][:4] or ["#howitworks", "#science"]
    return {
        "tiktok_caption": f"{hook}\n\n{meta.get('caption', '')}\n\n{q}".strip(),
        "tiktok_hashtags": tags + ["#learnontiktok", "#fyp"],
        "cover_moment": "the hook (first 2 seconds)",
        "cover_text": film.get("title", "")[:40],
        "youtube_title": f"{film.get('title', '')} #shorts"[:100],
        "youtube_description": f"{meta.get('caption', hook)}\n\n{q}\n\n#shorts " + " ".join(tags),
        "youtube_tags": [t.lstrip("#") for t in tags],
        "instagram_caption": f"{hook}\n\n{meta.get('caption', '')}\n\n{q}".strip(),
        "instagram_hashtags": tags + ["#science", "#engineering", "#animation", "#reels"],
        "instagram_alt_text": f"Animated 3D cartoon: {film.get('title', '')}.",
    }


def _no_tag_lines(text):
    """Drop hashtag-only lines from a caption (the hashtags are printed once, below it)."""
    keep = [ln for ln in text.strip().splitlines()
            if not (ln.strip() and all(w.startswith("#") for w in ln.split()))]
    return "\n".join(keep).strip()


def _fmt(p):
    p = dict(p, tiktok_caption=_no_tag_lines(p["tiktok_caption"]),
             instagram_caption=_no_tag_lines(p["instagram_caption"]))
    tags = " ".join(t if t.startswith("#") else f"#{t}" for t in p["tiktok_hashtags"])
    return (f"===== TIKTOK =====\n{p['tiktok_caption'].strip()}\n\n{tags}\n\n"
            f"Cover: {p['cover_moment'].strip()}\nCover text: {p['cover_text'].strip()}\n\n"
            f"===== YOUTUBE SHORTS =====\nTitle:\n{p['youtube_title'].strip()}\n\n"
            f"Description:\n{p['youtube_description'].strip()}\n\n"
            f"Tags:\n{', '.join(t.strip().lstrip('#') for t in p['youtube_tags'])}\n\n"
            f"===== INSTAGRAM REELS =====\n{p['instagram_caption'].strip()}\n\n"
            f"{' '.join(t if t.startswith('#') else f'#{t}' for t in p['instagram_hashtags'])}\n\n"
            f"Alt text: {p['instagram_alt_text'].strip()}\n")


def write(film, video_path):
    """Write `<video>_post.txt` next to the video. Never fails the render: falls back to a template."""
    film = _normalise(film)
    try:
        post = _ask_claude(film)
    except Exception as e:                                  # no Claude / usage limit: still give a post
        log.warning(f"  post text: Claude unavailable ({str(e)[:120]}); using the template")
        post = _template(film)
    out = os.path.splitext(video_path)[0] + "_post.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(_fmt(post))
    log.info(f"POST TEXT: {out}")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    write(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
