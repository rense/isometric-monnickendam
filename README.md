# Isometric Monnickendam

An isometric pixel-art map of Monnickendam, the harbour and the full Kloosterdijk, including its houses and farms. Adapted from [Isometric Helenaveen by jankeesvw](https://github.com/jankeesvw/isometric-helenaveen).

## Area and data

`scripts/config.py` sets a 4 × 3.5 km area in RD New (EPSG:28992): x 129000–133000, y 495000–498500. PDOK's Kloosterdijk road geometry lies inside this boundary (x 129349–130848, y 497304–498190).

The Dutch sources are retained: 3DBAG LoD2.2 buildings and roof geometry; BGT ground surfaces; PDOK aerial imagery; AHN surface and bare-earth heights; BAG addresses; OpenStreetMap roads, paths, pitches and walking routes. All buildings in the area are processed, rather than selecting only landmarks. BAG addresses inside the area are searchable.

## Build and view

Requirements: Python 3.11+, uv, Node.js, npm and libvips (`vips`).

```sh
npm install
npx playwright install chromium
./build.sh
python3 -m http.server 8000 -d site
```

Open http://localhost:8000. The build downloads raw data to `data/raw/`, makes meshes and textures in `data/build/`, renders four views and object masks to `out/`, and assembles the tiled viewer in `site/`. Downloads are cached. Rendering uses Metal on macOS and Vulkan elsewhere.

For this machine's Python certificate setup, the build was launched with `SSL_CERT_FILE=/etc/ssl/cert.pem`, `UV_SYSTEM_CERTS=true` and `UV_PYTHON=3.11`. These are environment settings, not a reason to disable certificate verification.

`SCALE=3 ./build.sh` changes the rendered pixels per metre. `SCALE=3 ./site.sh` reassembles that render. Keep the same scale for both commands.

## Places and stories

`scripts/landmarks.py` contains the Speeltoren, Grote Kerk, Lutherse Kerk, Weeshuis, harbour and Kloosterdijk. Stories are paraphrased from the [Waterlandsmuseum](https://www.despeeltoren.nl/) and [Protestantse Gemeente Monnickendam](https://www.pgmonnickendam.nl/gebouwen), with links in the viewer. `scripts/build_history.py` makes a short Monnickendam tour without importing the Helenaveen stories or photographs.

The viewer starts at the Speeltoren; street lighting and passing birds use the historic centre. The Helenaveen canal swimmers are removed. The Kloosterdijk has a direct navigation button.

## Licences and attribution

- [3DBAG](https://docs.3dbag.nl/en/copyright/): TU Delft 3D geoinformation research group and 3DGI, CC BY 4.0. Geometry adapted for rendering.
- [BGT](https://api.pdok.nl/kadaster/bgt/ogc/v1?f=html): Kadaster, CC0 1.0.
- [AHN](https://www.ahn.nl/open-data): CC0 1.0, as declared in the PDOK WMS capabilities for the service used here.
- [Aerial imagery](https://www.beeldmateriaal.nl/dataroom): Beeldmateriaal Nederland, CC BY 4.0. Colours simplified and used on ground and roofs.
- BAG addresses: Kadaster / PDOK Locatieserver.
- [OpenStreetMap contributors](https://www.openstreetmap.org/copyright): ODbL 1.0. The derived OSM JSON files are distributed under ODbL 1.0.
- [My Street](https://opengameart.org/content/my-street), congusbongus: CC0.

`viewer/credits.html` is published with the map. No landmark photos are copied. The upstream repository has no code licence file; this adaptation retains its attribution and does not assign a new licence to its code.

## Publish

Point `origin` to your own GitHub repository and run `./deploy.sh`. The script enables Pages from `gh-pages` at `/` if needed and replaces that branch with the current generated site. Do not point it at the original author's repository.
