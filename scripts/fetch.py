# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Download the raw open data for the area: 3D BAG, BGT, aerial photos and AHN."""

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from config import CHUNK, NX, NY, RAW, XMAX, XMIN, YMAX, YMIN

UA = {"User-Agent": "isometric-monnickendam/0.1"}
RD = "http://www.opengis.net/def/crs/EPSG/0/28992"

BGT_COLLECTIONS = [
    "begroeidterreindeel",
    "onbegroeidterreindeel",
    "wegdeel",
    "ondersteunendwegdeel",
    "waterdeel",
    "ondersteunendwaterdeel",
    "overbruggingsdeel",
    "overigbouwwerk",
    "kunstwerkdeel_vlak",
    "scheiding_vlak",
    "scheiding_lijn",
    "vegetatieobject_punt",
    "vegetatieobject_vlak",
    "vegetatieobject_lijn",
    "pand",
    "spoor",
    "weginrichtingselement_lijn",
    "weginrichtingselement_vlak",
    "straatmeubilair",
    "paal",
    "mast",
]


def get(url, binary=False, tries=5):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=120
            ) as r:
                data = r.read()
                return data if binary else json.loads(data)
        except Exception as e:
            if attempt == tries - 1:
                raise
            print(f"retry {attempt + 1} {url[:100]}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


def fetch_3dbag():
    out = RAW / "3dbag.jsonl"
    if out.exists():
        return
    url = f"https://api.3dbag.nl/collections/pand/items?bbox={XMIN},{YMIN},{XMAX},{YMAX}&limit=100"
    n = 0
    with open(out.with_suffix(".tmp"), "w") as f:
        while url:
            page = get(url)
            transform = page["metadata"]["transform"]
            for feat in page["features"]:
                feat["transform"] = transform
                f.write(json.dumps(feat) + "\n")
                n += 1
            url = next((l["href"] for l in page["links"] if l["rel"] == "next"), None)
            print(f"3dbag {n}/{page['numberMatched']}", file=sys.stderr)
    out.with_suffix(".tmp").rename(out)


def fetch_bgt(coll):
    out = RAW / f"bgt_{coll}.geojson"
    if out.exists():
        return
    q = urllib.parse.urlencode(
        {
            "bbox": f"{XMIN},{YMIN},{XMAX},{YMAX}",
            "bbox-crs": RD,
            "crs": RD,
            "limit": 1000,
            "f": "json",
        }
    )
    url = f"https://api.pdok.nl/lv/bgt/ogc/v1/collections/{coll}/items?{q}"
    feats = []
    while url:
        page = get(url)
        feats += page["features"]
        url = next((l["href"] for l in page["links"] if l["rel"] == "next"), None)
    # The API also serves retired versions of objects; keep only the current ones.
    current = [f for f in feats if not f["properties"].get("eind_registratie")]
    out.write_text(json.dumps({"type": "FeatureCollection", "features": current}))
    print(f"bgt {coll}: {len(current)} current of {len(feats)}", file=sys.stderr)


def fetch_aerial(ix, iy, chunk=CHUNK, res=0.25):
    d = RAW / "aerial"
    d.mkdir(exist_ok=True)
    out = d / f"{ix}_{iy}.jpg"
    if out.exists():
        return
    x0, y0 = XMIN + ix * chunk, YMIN + iy * chunk
    px = int(chunk / res)
    q = urllib.parse.urlencode(
        {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": "Actueel_orthoHR",
            "STYLES": "",
            "CRS": "EPSG:28992",
            "BBOX": f"{x0},{y0},{x0 + chunk},{y0 + chunk}",
            "WIDTH": px,
            "HEIGHT": px,
            "FORMAT": "image/jpeg",
        }
    )
    out.write_bytes(
        get(f"https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0?{q}", binary=True)
    )


def fetch_ahn(cov, ix, iy, chunk=CHUNK):
    # The WCS refuses anything over 4000 px a side, so fetch it in chunks (1000 px at 0.5 m).
    d = RAW / "ahn"
    d.mkdir(exist_ok=True)
    out = d / f"{cov}_{ix}_{iy}.tif"
    if out.exists():
        return
    x0, y0 = XMIN + ix * chunk, YMIN + iy * chunk
    url = (
        "https://service.pdok.nl/rws/ahn/wcs/v1_0?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
        f"&COVERAGEID={cov}&SUBSET=x({x0},{x0 + chunk})&SUBSET=y({y0},{y0 + chunk})&FORMAT=image/tiff"
    )
    out.write_bytes(get(url, binary=True))


def fetch_addresses():
    """Every BAG address in Monnickendam, for the viewer's search box."""
    out = RAW / "addresses.json"
    if out.exists():
        return
    pts, start = [], 0
    while True:
        q = urllib.parse.urlencode(
            {
                "q": "*",
                "fq": ["woonplaatsnaam:Monnickendam", "type:adres"],
                "fl": "weergavenaam,centroide_rd",
                "rows": 100,
                "start": start,
            },
            doseq=True,
        )
        d = get(f"https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?{q}")[
            "response"
        ]
        for doc in d["docs"]:
            x, y = (float(v) for v in doc["centroide_rd"][6:-1].split())
            pts.append((x, y, doc["weergavenaam"]))
        start += 100
        if start >= d["numFound"]:
            break
    out.write_text(json.dumps(pts))


def osm_bbox():
    from geo import rd_to_wgs

    lats, lons = zip(*(rd_to_wgs(x, y) for x in (XMIN, XMAX) for y in (YMIN, YMAX)))
    return f"{min(lats)},{min(lons)},{max(lats)},{max(lons)}"


def fetch_osm_map():
    """Read small OSM map extracts when public Overpass servers are unavailable."""
    outputs = [
        RAW / name
        for name in ("osm_landmarks.json", "osm_routes.json", "osm_roads.json")
    ]
    if all(path.exists() for path in outputs):
        return
    south, west, north, east = map(float, osm_bbox().split(","))
    elements = {}

    def tile(w, s, e, n, depth=0):
        url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={w},{s},{e},{n}"
        try:
            page = get(url, tries=2)
        except urllib.error.HTTPError as error:
            if error.code != 400 or depth >= 4:
                raise
            mx, my = (w + e) / 2, (s + n) / 2
            for box in ((w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)):
                tile(*box, depth + 1)
            return
        for el in page["elements"]:
            elements[(el["type"], el["id"])] = el
        print(f"OSM map extract: {len(elements)} elements", file=sys.stderr)

    mx, my = (west + east) / 2, (south + north) / 2
    for box in (
        (west, south, mx, my),
        (mx, south, east, my),
        (west, my, mx, north),
        (mx, my, east, north),
    ):
        tile(*box)
    for (kind, _), el in elements.items():
        if kind == "way":
            el["geometry"] = [
                {"lat": node["lat"], "lon": node["lon"]}
                for nid in el["nodes"]
                if (node := elements.get(("node", nid)))
            ]
    for (kind, _), el in elements.items():
        if kind == "relation":
            for member in el.get("members", []):
                way = (
                    elements.get(("way", member["ref"]))
                    if member["type"] == "way"
                    else None
                )
                if way:
                    member["geometry"] = way["geometry"]
    all_elements = list(elements.values())
    landmarks = [
        el
        for el in all_elements
        if (t := el.get("tags", {}))
        and (
            "military" in t
            or t.get("leisure") == "pitch"
            or t.get("landuse") == "cemetery"
            or t.get("amenity") == "place_of_worship"
            or "tourism" in t
            or "historic" in t
        )
    ]
    routes = [
        el
        for el in all_elements
        if el.get("tags", {}).get("route") in ("hiking", "foot", "walking")
        or el.get("tags", {}).get("rwn_ref")
    ]
    roads = [
        el
        for el in all_elements
        if el["type"] == "way" and el.get("tags", {}).get("highway")
    ]
    for path, selected in zip(outputs, (landmarks, routes, roads)):
        path.write_text(json.dumps({"elements": selected}))


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    jobs = [
        fetch_3dbag,
        fetch_addresses,
        fetch_osm_map,
        *(lambda c=c: fetch_bgt(c) for c in BGT_COLLECTIONS),
    ]
    jobs += [
        lambda c=c, i=i, j=j: fetch_ahn(c, i, j)
        for c in ("dsm_05m", "dtm_05m")
        for i in range(NX)
        for j in range(NY)
    ]
    jobs += [lambda i=i, j=j: fetch_aerial(i, j) for i in range(NX) for j in range(NY)]
    with ThreadPoolExecutor(8) as pool:
        for fut in [pool.submit(j) for j in jobs]:
            fut.result()
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
