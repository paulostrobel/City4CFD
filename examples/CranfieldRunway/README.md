# Cranfield University Runway — Microclimate CFD

Microclimate (wind) study of the **runway 03/21 at Cranfield Airport (EGTC)**
and the surrounding Cranfield University campus, Bedfordshire, UK.
Geometry is generated automatically from OpenStreetMap — no LiDAR required.

The case is set up in a **runway-aligned frame**: the x axis runs along
runway 03/21 (true bearing ≈ 034°) and the wind blows from 214° — the
prevailing south-westerly that the runway was aligned with. The inlet flow is
therefore exactly `(1 0 0)`, straight down the runway, which makes headwind
(`Ux`) and crosswind (`Uy`) components trivial to extract along the
centreline.

## Quick start

```bash
cd examples/CranfieldRunway
./pipeline.sh all        # full run: deps → build → OSM → geometry → mesh → solve
```

Run a single stage:

```bash
./pipeline.sh deps       # install system + Python packages (needs sudo for apt)
./pipeline.sh build      # compile City4CFD
./pipeline.sh osm        # download OSM data into data/
./pipeline.sh geometry   # generate OBJ surfaces in results/
./pipeline.sh stl        # rotate runway → +x, merge OBJ → buildings.stl
./pipeline.sh mesh       # blockMesh + snappyHexMesh + checkMesh
./pipeline.sh solve      # simpleFoam (500 iterations)
```

> The `osm` stage needs access to `overpass-api.de` (and
> `nominatim.openstreetmap.org`). Run it from a machine with unrestricted
> internet if your environment blocks those hosts.

## Site parameters

| Parameter | Value |
|---|---|
| Location | Cranfield Airport (EGTC), 52.0722° N, 0.6166° W |
| CRS | EPSG:27700 (British National Grid) |
| `point_of_interest` | E 494916, N 242440 (runway midpoint) |
| Runway | 03/21, 1799 m × 45 m, true bearing ≈ 034°/214° |
| Terrain | flat plateau ~110 m AMSL → `flat_terrain: true` |
| Tallest obstacles | hangars / campus buildings, ~20 m |
| Wind | Uref = 5 m/s at 10 m, from 214° (prevailing SW) |
| Roughness | z₀ = 0.03 m (open airfield: mown grass, paved runway) |

## Case structure

```
examples/CranfieldRunway/
├── pipeline.sh               ← entry point
├── config_bpg.json           ← City4CFD config (BPG domain, flat terrain)
├── cities.txt                ← POI reference (generic fetch_osm.py format)
├── fetch_osm_cranfield.py    ← OSM download incl. aeroway polygons
├── rotate_and_merge_stl.py   ← OBJ → STL, rotates runway axis onto +x
├── plot_runway.py            ← post-processing (pedestrian slice, centreline)
├── data/                     ← GeoJSON from OpenStreetMap (generated)
│   ├── cranfield_buildings.geojson
│   ├── cranfield_runway.geojson      (runway/taxiways/aprons)
│   ├── cranfield_vegetation.geojson
│   └── cranfield_water.geojson
├── results/                  ← City4CFD OBJ surfaces (generated)
│   ├── Cranfield_Runway_Buildings_0/1.obj
│   ├── Cranfield_Runway_Terrain.obj
│   ├── Cranfield_Runway_Runway/Vegetation/Water.obj
│   └── failedReconstructions.geojson
└── openfoam/
    ├── 0/                    ← initial conditions
    │   ├── U                   ABL log-law inlet (Uref=5 m/s, z0=0.03 m)
    │   ├── p
    │   ├── k                   k = u*²/√Cμ = 0.41 m²/s²
    │   ├── epsilon             ε = Cμ^¾·k^¾/(κ·z) profile
    │   └── nut
    ├── constant/
    │   ├── transportProperties   (air at ~12°C, ν=1.47×10⁻⁵ m²/s)
    │   ├── turbulenceProperties  (kEpsilon)
    │   └── triSurface/buildings.stl
    └── system/
        ├── blockMeshDict         outer domain 4100×3200×300 m
        ├── snappyHexMeshDict     distance-based refinement
        ├── meshQualityDict
        ├── fvSchemes             linearUpwind U, upwind k/ε
        ├── fvSolution            SIMPLE, GAMG pressure solver
        └── controlDict           500 iter, write every 100
```

## Geometry pipeline

1. **`osm`** — downloads OSM buildings (r = 1500 m), aeroways (runway,
   taxiways, aprons), vegetation and water (r = 3300 m, COST-732 rule
   15·Hmax + 2·r_buildings). Runway/taxiway centrelines mapped as
   LineStrings are buffered to their tagged or default width so City4CFD
   receives polygons only.
2. **`geometry`** — City4CFD reconstructs LoD 1.2 buildings from `height`
   or `building:levels` tags (3 m per floor). Buildings without any height
   information are extruded to `min_height` (3 m) via
   `reconstruct_failed: true` instead of being dropped. The runway,
   vegetation and water polygons are imprinted into the flat terrain as
   separate surface layers.
3. **`stl`** — merges the building OBJs and rotates the scene about the
   origin (runway midpoint) so the runway axis measured from the OSM
   runway polygon lands on +x. Warns if the rotated geometry exceeds the
   blockMesh box.

## Domain and boundary conditions

```
          top (symmetryPlane)                       z = 300 m
        ┌───────────────────────────────────┐
side1   │   03 ────── runway ────── 21      │  side2
(sym)   │ →x   hangars ▪▪  campus ▪▪▪       │  (sym)
        │        ground (wall, z0=0.03)     │
        └───────────────────────────────────┘
  inlet (ABL)                          outlet (zeroGradient p)
  x = −1800 m                          x = +2300 m
  wind from 214° = straight down the runway
```

| Patch     | U                       | p            | k / ε              | nut                      |
|-----------|-------------------------|--------------|--------------------|--------------------------|
| inlet     | `atmBoundaryLayerInlet` | zeroGradient | `atmBoundaryLayer` | calculated               |
| outlet    | inletOutlet             | fixedValue 0 | zeroGradient       | calculated               |
| sides/top | symmetryPlane           | —            | —                  | —                        |
| ground    | noSlip                  | zeroGradient | kqRWallFunction    | nutkAtmRoughWallFunction |
| buildings | noSlip                  | zeroGradient | kqRWallFunction    | nutUSpaldingWallFunction |

ABL parameters: Uref = 5 m/s at z = 10 m, z₀ = 0.03 m (open airfield),
κ = 0.41 → u\* = 0.353 m/s, k = 0.41 m²/s², ε(10 m) = 0.011 m²/s³.

To study a different wind direction (e.g. a crosswind case for runway
usability), change `flowDir` in `0/U`, `0/k`, `0/epsilon` and rotate the
STL accordingly (adjust the rotation in `rotate_and_merge_stl.py`), or
keep the geometry fixed and re-orient the domain box.

## Mesh refinement

All refinement knobs are at the top of `pipeline.sh`:

```bash
BASE_CELL_SIZE=20   # blockMesh base cell size (metres)
SNH_NEAR=3          # snappyHexMesh level within 20 m of buildings
SNH_FAR=2           # snappyHexMesh level within 50 m of buildings
END_TIME=500        # solver iterations
```

| `BASE_CELL_SIZE` | `SNH_NEAR` | Finest cell | ~Total cells |
|-----------------|------------|-------------|--------------|
| 20 m (default)  | 3          | 2.5 m       | ~4 M         |
| 15 m            | 3          | 1.9 m       | ~9 M         |
| 10 m            | 4          | 1.25 m      | ~35 M        |

## Post-processing

```bash
python3 plot_runway.py       # → results_cfd.png
```

Panels: pedestrian-level |U| map with the runway outline, headwind/crosswind
components along the runway centreline at z = 10 m (standard anemometer
height), and vertical ABL profiles above both thresholds and midfield —
useful for checking hangar/campus wake effects on the touchdown zones.

Manual ParaView:

```bash
touch openfoam/Cranfield.foam
paraview openfoam/Cranfield.foam
```

## Known issues / notes

- OSM height coverage at Cranfield is sparse: many campus buildings carry
  neither `height` nor `building:levels`. These fall back to a 3 m
  extrusion (`reconstruct_failed` + `min_height`), so wakes of untagged
  tall buildings are underestimated. Check `results/logFile.log` and
  `failedReconstructions.geojson` after the geometry stage.
- The runway itself is resolved as a *surface layer* on flat ground; it
  matters for visualisation and for assigning a distinct roughness patch,
  not as an obstacle.
- The ABL profiles assume neutral stratification; thermal microclimate
  effects (runway surface heating) are outside the scope of this
  steady-state RANS setup.
