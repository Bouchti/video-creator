"""
Download the music beds into assets/cc0/music/incompetech/ (git-ignored; fetched at the start of the first run
by agents/libraries.py, part "music").

    python assets/fetch_music.py

Kevin MacLeod (incompetech.com), CC BY 4.0: free for commercial use, the credit line below goes into every
video's description (agents/director.py writes it). Playful, comedic cartoon tracks that sit under a voice.
"""
import json
import os
import urllib.parse

import requests

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0", "music", "incompetech")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
CREDIT = '"{title}" Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 ' \
         'License, http://creativecommons.org/licenses/by/4.0/'
TRACKS = {   # title -> mood
    "Fluffing a Duck": "silly", "Sneaky Snitch": "sneaky", "Monkeys Spinning Monkeys": "silly",
    "Investigations": "curious", "Carefree": "happy", "Quirky Dog": "silly", "Run Amok": "chaotic",
    "Life of Riley": "happy", "Merry Go": "happy", "Hidden Agenda": "sneaky", "Wallpaper": "calm",
    "Pixel Peeker Polka - faster": "chaotic",
}


def main(argv=None):
    os.makedirs(ROOT, exist_ok=True)
    failed, rows = [], []
    for title, mood in TRACKS.items():
        path = os.path.join(ROOT, f"{title}.mp3")
        if not os.path.isfile(path):
            try:
                r = requests.get(BASE + urllib.parse.quote(title) + ".mp3", headers=UA, timeout=120)
                r.raise_for_status()
                with open(path, "wb") as fh:
                    fh.write(r.content)
                print(f"get   {title}")
            except Exception as exc:  # noqa: BLE001  (retried next run)
                print(f"FAIL  {title}: {exc}")
                failed.append(title)
                continue
        rows.append({"title": title, "mood": mood, "file": os.path.basename(path),
                     "credit": CREDIT.format(title=title)})
    with open(os.path.join(ROOT, "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    return {"assets": len(TRACKS), "failed": failed}


if __name__ == "__main__":
    main()
