# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Monnickendam landmarks. Stories link to their primary sources; geometry comes from 3DBAG."""

import json

import numpy as np
from config import BUILD, RAW
from geo import wgs_to_rd

BUILDINGS = [
    {
        "name": "Speeltoren",
        "at": (131113.868, 496901.805),
        "kind": "Museum",
        "address": "Noordeinde 2",
        "text": "Het Waterlandsmuseum is gebouwd rond de middeleeuwse Speeltoren. Het vertelt over Waterland, van scheepsbouw en visserij tot de rokerijen van Monnickendam.",
        "web": "https://www.despeeltoren.nl/",
        "more": "https://www.despeeltoren.nl/",
    },
    {
        "name": "Grote Kerk",
        "at": (130873.92, 496611.822),
        "kind": "Kerk",
        "address": "De Zarken 2",
        "text": "De Grote of Sint Nicolaaskerk is een laatgotische, driebeukige hallenkerk aan de oude stadsrand. De toren is al van ver te zien.",
        "web": "https://grotekerkmonnickendam.nl/",
        "more": "https://www.pgmonnickendam.nl/gebouwen",
        "style": "church",
    },
    {
        "name": "Lutherse Kerk",
        "at": (131290.484, 496836.077),
        "kind": "Kerk",
        "address": "Zuideinde 39",
        "text": "Deze zaalkerk dateert uit het midden van de achttiende eeuw. Het aangrenzende clubhuis staat op nummer 41.",
        "more": "https://www.pgmonnickendam.nl/gebouwen",
        "style": "church",
    },
    {
        "name": "Weeshuis",
        "at": (131106.874, 496725.427),
        "kind": "Historisch gebouw",
        "address": "Weezenland 16",
        "text": "Dit renaissancecomplex stamt uit de eerste helft van de zeventiende eeuw. Het staat aan het Weezenland, dicht bij de Grote Kerk.",
        "more": "https://www.pgmonnickendam.nl/gebouwen",
    },
]

POINTS = [
    {
        "name": "Kloosterdijk",
        "at": (130070.725, 497793.003),
        "kind": "Dijk",
        "text": "De Kloosterdijk met zijn huizen en boerderijen. Alle gebouwen binnen deze kaart komen uit 3DBAG; de adressen zijn te vinden via het zoekveld.",
        "more": "https://www.pdok.nl/",
    },
    {
        "name": "De Haven",
        "at": (131170.91, 496947.769),
        "kind": "Haven",
        "text": "Scheepsbouw, zeevaart, visserij en visverwerking horen bij de geschiedenis van Monnickendam. Het Waterlandsmuseum vertelt die verhalen.",
        "more": "https://www.despeeltoren.nl/te-zien/historie/",
    },
]

CATEGORIES = [
    (
        "monnickendam",
        "Monnickendam",
        [
            "Speeltoren",
            "Grote Kerk",
            "Lutherse Kerk",
            "Weeshuis",
            "Kloosterdijk",
            "De Haven",
        ],
    )
]

INFO = ("note", "kind", "text", "address", "web", "more", "photo", "stop")
MASTS = []


def point_in_ring(x, y, ring):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, np.roll(ring, -1, axis=0)):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


ADDRESSES = None


def address_xy(name):
    """RD position of a BAG address such as "Geldersestraat 3" (data/raw/addresses.json, from scripts/fetch.py)."""
    global ADDRESSES
    if ADDRESSES is None:
        ADDRESSES = {
            label.replace(", Monnickendam", "").split(", ")[0]: (x, y)
            for x, y, label in json.loads((RAW / "addresses.json").read_text())
        }
    return ADDRESSES[name]


def building_at(rings, x, y):
    for rid, ring, a in rings:
        if point_in_ring(x, y, ring):
            return rid, a
    return None, None


def main():
    with open(RAW / "3dbag.jsonl") as source:
        feats = [json.loads(line) for line in source]
    rings = []
    for f in feats:
        t = f["transform"]
        V = np.array(f["vertices"], dtype=np.float64) * t["scale"] + t["translate"]
        co = f["CityObjects"][f["id"]]
        rings.append(
            (f["id"], V[co["geometry"][0]["boundaries"][0][0]][:, :2], co["attributes"])
        )

    out = {"buildings": {}, "places": [], "masts": [], "hotspots": [], "categories": []}
    for b in BUILDINGS:
        if "addrs" in b:
            pts = [address_xy(a) for a in b["addrs"]]
            pids = [building_at(rings, *pt)[0] for pt in pts]
            assert all(pids), f"{b['name']}: no building at {b['addrs']}"
            x, y = np.mean(pts, axis=0)
            out["places"].append(
                {"name": b["name"], "note": b.get("note"), "x": x, "y": y, "h": 4.0}
            )
            out["hotspots"].append(
                {
                    "name": b["name"],
                    "pids": pids,
                    "x": x,
                    "y": y,
                    **{k: b[k] for k in INFO if k in b},
                }
            )
            print(f"{b['name']}: {', '.join(pids)}")
            continue
        x, y = b["at"] if "at" in b else wgs_to_rd(*b["latlon"])
        pid, attrs = None, None
        for rid, ring, a in rings:
            if point_in_ring(x, y, ring):
                pid, attrs = rid, a
                break
        if pid is None:
            d = [(np.hypot(*(ring.mean(0) - (x, y))), rid, a) for rid, ring, a in rings]
            dist, pid, attrs = min(d, key=lambda t: t[0])
            if dist > 20:
                pid = None
        height = ((attrs or {}).get("b3_h_dak_max") or 0) - (
            (attrs or {}).get("b3_h_maaiveld") or 0
        )
        if "tower" in b:
            height = b["tower"]["top"]
        elif "turret" in b:
            height = b["turret"]["top"]
        out["places"].append(
            {
                "name": b["name"],
                "note": b.get("note"),
                "x": x,
                "y": y,
                "h": round(height, 1),
            }
        )
        if pid and "style" in b:
            out["buildings"][pid] = {
                k: v for k, v in b.items() if k not in ("at", "latlon", *INFO)
            }
        if pid:
            out["hotspots"].append(
                {
                    "name": b["name"],
                    "pid": pid,
                    "x": x,
                    "y": y,
                    **{k: b[k] for k in INFO if k in b},
                }
            )
        print(f"{b['name']}: {pid or 'no building'}")
    for p in POINTS:
        x, y = (
            p["at"]
            if "at" in p
            else address_xy(p["addr"]) if "addr" in p else wgs_to_rd(*p["latlon"])
        )
        out["places"].append(
            {"name": p["name"], "note": p.get("note"), "x": x, "y": y, "h": 2.0}
        )
        out["hotspots"].append(
            {"name": p["name"], "x": x, "y": y, **{k: p[k] for k in INFO if k in p}}
        )
    for m in MASTS:
        x, y = wgs_to_rd(*m["latlon"])
        out["masts"].append(
            {**{k: v for k, v in m.items() if k != "latlon"}, "x": x, "y": y}
        )
    names = {h["name"] for h in out["hotspots"]}
    for key, label, members in CATEGORIES:
        missing = [n for n in members if n not in names]
        assert not missing, f"{label}: no hotspot for {missing}"
        out["categories"].append({"key": key, "label": label, "names": members})
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "landmarks.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
