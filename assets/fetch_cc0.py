"""Download the free CC0 (public-domain) 3D asset packs the Unreal route uses into assets/cc0/.

    python assets/fetch_cc0.py

All of it is CC0: free for commercial use, no attribution required, no account needed.
  Kenney (kenney.nl): low-poly kits, each with FBX + glTF and a License.txt
  Poly Haven (polyhaven.com): a daylight sky HDRI
The downloads are git-ignored (about 120 MB); this script is the record of where they come from.
"""
import io
import json
import os
import urllib.request
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0")

KENNEY = {   # kit → what it covers
    "city-kit-suburban/2c871b7af2-1745479373/kenney_city-kit-suburban_20.zip": "houses, fences, garden trees",
    "city-kit-roads/74288c9459-1791628607/kenney_city-kit-roads.zip": "roads, road bridge + pillars, poles",
    "city-kit-industrial/0ec35b139d-1788171848/kenney_city-kit-industrial_2.0.zip":
        "water tower, tanks, chimneys, windmills, factory buildings",
    "nature-kit/37ac38a37b-1677698939/kenney_nature-kit.zip": "trees, rocks, cliffs, stone/wood bridges",
    "train-kit/cf8521d625-1727040883/kenney_train-kit.zip": "rails and train cars",
    "car-kit/1a312ec241-1775131960/kenney_car-kit.zip": "cars, trucks, tractors",
    "watercraft-kit/a335cfed49-1713519620/kenney_watercraft-pack.zip": "boats, sailing and cargo ships",
    "factory-kit/edaac9d4f6-1777639602/kenney_factory-kit_3.0.zip": "machines, cogs, conveyors, catwalks",
    "city-kit-commercial/a742d900eb-1753115042/kenney_city-kit-commercial_2.1.zip": "city towers and shops (skylines)",
    "retro-urban-kit/8314d4db22-1738147509/kenney_retro-urban-kit.zip": "city streets, brick buildings",
    "modular-buildings/3253b4219a-1707397411/kenney_modular-buildings.zip": "modular apartment blocks",
    "building-kit/0de7aaa492-1743244741/kenney_building-kit.zip": "house walls, roofs, floors (construction)",
    "castle-kit/a395102d20-1711543616/kenney_castle-kit.zip": "castle walls, towers, gates (history)",
    "fantasy-town-kit/efe948d309-1754222374/kenney_fantasy-town-kit_2.0.zip": "old-town houses, market, mill",
    "space-kit/20874c75ac-1677698978/kenney_space-kit.zip": "rockets, launch pads, planets, rovers",
    "space-station-kit/6475288f2e-1712749919/kenney_space-station-kit.zip": "space station modules",
    "survival-kit/4065a8185b-1712149243/kenney_survival-kit.zip": "camp, tents, tools, fire",
    "furniture-kit/440e0608a4-1677580847/kenney_furniture-kit.zip": "home interiors, kitchen, appliances",
    "food-kit/83086fa91c-1719418518/kenney_food-kit.zip": "food and cooking",
}
HDRI = "kloofendal_48d_partly_cloudy_puresky"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "video-creator asset fetch"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def main() -> None:
    for path, covers in KENNEY.items():
        name = os.path.splitext(os.path.basename(path))[0]
        target = os.path.join(ROOT, "kenney", name)
        if os.path.isdir(target):
            print(f"have  {name}")
            continue
        print(f"get   {name} ({covers})")
        zipfile.ZipFile(io.BytesIO(fetch(f"https://kenney.nl/media/pages/assets/{path}"))).extractall(target)
    sky = os.path.join(ROOT, "polyhaven", f"{HDRI}_2k.hdr")
    if not os.path.isfile(sky):
        os.makedirs(os.path.dirname(sky), exist_ok=True)
        info = json.loads(fetch(f"https://api.polyhaven.com/files/{HDRI}"))
        with open(sky, "wb") as f:
            f.write(fetch(info["hdri"]["2k"]["hdr"]["url"]))
        print(f"get   {os.path.basename(sky)}")


if __name__ == "__main__":
    main()
