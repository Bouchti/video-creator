"""
TikTok-style captions (ASS, burned with libass). Two modes:

- "phrase": 1-3 words on screen at a time, the spoken word highlighted in yellow,
  each new phrase popping in, placed above the platform UI.
- "word": ONE big bold white word at a time, centred mid-screen with a dark
  outline + soft shadow, each word popping in exactly on its timestamp
  (3D-explainer style).
"""
import re

PLAY_W, PLAY_H = 1080, 1920
POS_Y = 1330
MAX_WORDS, MAX_CHARS = 3, 16
WHITE, YELLOW = "&H00FFFFFF", "&H0000E6FF"   # ASS colours are &HAABBGGRR

HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_W}
PlayResY: {PLAY_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Arial Black,112,{WHITE},{WHITE},&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Word,Arial Black,124,{WHITE},{WHITE},&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,6,5,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(s: float) -> str:
    s = max(0.0, s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}"


def _clean(word: str) -> str:
    return re.sub(r"[{}\\]", "", word).strip().upper()


def chunk_words(words: list) -> list:
    """Group words into short on-screen phrases, breaking after punctuation."""
    chunks, cur = [], []
    for w in words:
        text = _clean(w["text"])
        if not text:
            continue
        if cur and (len(cur) >= MAX_WORDS
                    or len(" ".join(_clean(c["text"]) for c in cur) + " " + text) > MAX_CHARS):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if text[-1] in ".!?,;:":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


WORD_Y = 905          # just above the middle: the eye's resting point on a 9:16 frame


def _word_text(word: str) -> str:
    """Title-case a spoken word, dropping trailing punctuation ("ninety-five," → "Ninety-five")."""
    w = re.sub(r"[{}\\]", "", word).strip().strip(".,;:!?\"'…")
    return w[:1].upper() + w[1:] if w else ""


def words_to_ass_single(words: list, path: str) -> str:
    """One word at a time: shown from its start until the next word starts (gaps < 0.6 s are
    bridged so the screen never flickers empty mid-sentence)."""
    lines = [HEADER]
    words = [w for w in words if _word_text(w["text"])]
    for i, w in enumerate(words):
        start = w["start"]
        nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + 0.4
        end = nxt if nxt - w["end"] < 0.6 else w["end"] + 0.25
        end = max(end, start + 0.08)
        pop = "\\fscx82\\fscy82\\t(0,70,\\fscx104\\fscy104)\\t(70,130,\\fscx100\\fscy100)"
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Word,,0,0,0,,"
                     f"{{\\an5\\pos({PLAY_W // 2},{WORD_Y}){pop}}}{_word_text(w['text'])}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def words_to_ass(words: list, path: str, mode: str = "phrase") -> str:
    """words: [{"text", "start", "end"}] → ASS file at path."""
    if mode == "word":
        return words_to_ass_single(words, path)
    lines = [HEADER]
    chunks = chunk_words(words)
    for ci, chunk in enumerate(chunks):
        chunk_end = (chunks[ci + 1][0]["start"] if ci + 1 < len(chunks)
                     else chunk[-1]["end"] + 0.3)
        for wi, w in enumerate(chunk):
            start = w["start"]
            end = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
            if end - start < 0.05:
                end = start + 0.05
            parts = []
            for k, other in enumerate(chunk):
                text = _clean(other["text"])
                if k == wi:
                    # Colour only: an inline scale tag would cancel the phrase pop-in.
                    parts.append(f"{{\\c{YELLOW}}}{text}{{\\c{WHITE}}}")
                else:
                    parts.append(text)
            pop = "\\fscx70\\fscy70\\t(0,90,\\fscx100\\fscy100)" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Pop,,0,0,0,,"
                         f"{{\\an5\\pos({PLAY_W // 2},{POS_Y}){pop}}}{' '.join(parts)}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path
