# Brasília Congress — Microclimate CFD

Pedestrian-level wind comfort study of the **Congresso Nacional** and the
Esplanada dos Ministérios in Brasília, DF.  
Geometry is generated automatically from OpenStreetMap — no LiDAR required.

## Quick start

```bash
cd examples/Brasilia
./pipeline.sh all        # full run: deps → build → OSM → geometry → mesh → solve
```

Run a single stage:

```bash
./pipeline.sh deps          # install system + Python packages (needs sudo for apt)
./pipeline.sh build         # compile City4CFD
./pipeline.sh osm           # download OSM data into data/
./pipeline.sh geometry      # generate OBJ surfaces in results/
./pipeline.sh stl           # merge OBJ buildings → openfoam/constant/triSurface/buildings.stl
./pipeline.sh fix-geometry  # replace Congress complex with accurate primitives (optional)
./pipeline.sh mesh          # blockMesh + snappyHexMesh + checkMesh
./pipeline.sh solve         # simpleFoam (500 iterations)
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| City4CFD | built from repo | `./pipeline.sh build` |
| OpenFOAM | v1912 (ESI) | `sudo apt install openfoam` |
| Python | 3.10+ | system |
| cmake, CGAL 6+, GDAL 3+, Eigen3, Boost | — | `./pipeline.sh deps` |

## Mesh refinement

All refinement knobs are at the top of `pipeline.sh`:

```bash
BASE_CELL_SIZE=20   # blockMesh base cell size (metres)
SNH_NEAR=3          # snappyHexMesh level within 20 m of buildings
SNH_FAR=2           # snappyHexMesh level within 50 m of buildings
END_TIME=500        # solver iterations
```

### Refinement guide

| `BASE_CELL_SIZE` | `SNH_NEAR` | Finest cell | ~Total cells | Pi 5 solve time |
|-----------------|------------|-------------|-------------|----------------|
| 20 m (default)  | 3          | 2.5 m       | 7 M         | ~11 h          |
| 15 m            | 3          | 1.9 m       | 15 M        | ~25 h          |
| 10 m            | 4          | 1.25 m      | 60 M        | memory limit ⚠ |

To re-mesh at a finer level without re-downloading data:

```bash
# Edit BASE_CELL_SIZE / SNH_NEAR in pipeline.sh, then:
./pipeline.sh mesh
./pipeline.sh solve
```

### What the levels mean

```
blockMesh base (20 m)
  └── SNH_FAR  level 2  → 5.0 m cells  within 50 m of any building face
        └── SNH_NEAR level 3 → 2.5 m cells within 20 m of any building face
```

Each additional refinement level halves the cell size and multiplies cell
count by ~8 in the refined region.

## Case structure

```
examples/Brasilia/
├── pipeline.sh              ← entry point
├── config_bpg.json          ← City4CFD config (BPG domain, flat terrain)
├── cities.txt               ← POI for OSM download
├── data/                    ← GeoJSON from OpenStreetMap (generated)
├── results/                 ← City4CFD OBJ surfaces (generated)
│   ├── Brasilia_Congress_Buildings_0/1.obj
│   ├── Brasilia_Congress_Terrain.obj
│   ├── Brasilia_Congress_Front/Back/Side/Top.obj
│   ├── Brasilia_Congress_Water/Vegetation.obj
│   └── failedReconstructions.geojson
└── openfoam/
    ├── 0/                   ← initial conditions
    │   ├── U                  ABL log-law inlet (Uref=5 m/s, z0=0.5 m)
    │   ├── p
    │   ├── k                  k = u*²/√Cμ = 1.51 m²/s²
    │   ├── epsilon            ε = Cμ^¾·k^¾/(κ·z) profile
    │   └── nut
    ├── constant/
    │   ├── transportProperties  (air, ν=1.56×10⁻⁵ m²/s)
    │   ├── turbulenceProperties (kEpsilon)
    │   └── triSurface/buildings.stl
    └── system/
        ├── blockMeshDict        outer domain 4400×3430×600 m
        ├── snappyHexMeshDict    distance-based refinement
        ├── meshQualityDict
        ├── fvSchemes            linearUpwind U, upwind k/ε
        ├── fvSolution           SIMPLE, GAMG pressure solver
        └── controlDict          500 iter, write every 100
```

## Domain and boundary conditions

```
         top (symmetryPlane)
        ┌─────────────────────┐
side1   │     ↑z              │  side2
(sym)   │  →x   buildings    │  (sym)
        │     ground (wall)   │
        └─────────────────────┘
  inlet (ABL)             outlet (zeroGradient p)
  x = −1700 m             x = +2700 m
```

| Patch     | U                          | p              | k / ε              | nut                      |
|-----------|----------------------------|----------------|--------------------|--------------------------|
| inlet     | `atmBoundaryLayerInlet`    | zeroGradient   | `atmBoundaryLayer` | calculated               |
| outlet    | inletOutlet                | fixedValue 0   | zeroGradient       | calculated               |
| sides/top | symmetryPlane              | —              | —                  | —                        |
| ground    | noSlip                     | zeroGradient   | kqRWallFunction    | nutkAtmRoughWallFunction |
| buildings | noSlip                     | zeroGradient   | kqRWallFunction    | nutUSpaldingWallFunction |

ABL parameters: Uref = 5 m/s at z = 10 m, z₀ = 0.5 m (suburban), κ = 0.41.

## Post-processing

### Manual ParaView
Open the case in ParaView:
```bash
touch openfoam/Brasilia.foam
paraview openfoam/Brasilia.foam
```

Useful filters for pedestrian wind comfort:
- **Slice** at z = 1.75 m → horizontal U magnitude map
- **Streamlines** seeded at inlet → flow paths around the Congress
- **Plot Over Line** along Esplanada axis → wind speed profile

### Automated plotting scripts

Matplotlib (2-D contours and streamlines):
```bash
python3 plot_results.py      # 3-panel: pedestrian slice, ABL profile, 3D streamlines
python3 plot_contours.py     # 12-panel: velocity/pressure/k/nut at multiple heights + slices
python3 compare_refinements.py  # refinement study comparison (coarse/medium/fine)
```

ParaView (high-quality 3-D renderings):
```bash
# Set up X display (Pi 5 v3d GPU requires Mesa software rasterization)
DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch paraview_postprocess.py

# Congress complex detail visualisations:
DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_flow.py      # XZ/YZ vertical slices + streamlines
DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_detail.py    # pedestrian-level isosurfaces + streamlines
DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_frontview.py # front-facing architectural view
```

**Output files** (all .png):

| Script | Output | Description |
|--------|--------|-------------|
| `plot_results.py` | `results_cfd.png` | Pedestrian-level |U\| slice (z=1.75m), ABL inlet profile, 3D streamlines |
| `plot_contours.py` | `contours_cfd.png` | 12-panel: U/p/k/νt at z=1.75/10/50m; XZ/YZ vertical slices; pedestrian zoom |
| `paraview_postprocess.py` | `pv_U_*` (11 files) | 11 ParaView renders: velocity/pressure/k/νt slices, XZ/YZ planes, 3D streamlines, pedestrian zoom |
| `pv_congress_flow.py` | 4 files | XZ centreline, YZ N-S section through dome/bowl, streamlines, pedestrian detail |
| `pv_congress_detail.py` | `pv_congress_pedestrian_detail.png` | Pedestrian-level view with velocity isosurfaces and streamlines |
| `pv_congress_frontview.py` | `pv_congress_frontview.png` | Front-facing architectural-style view of Congress complex |

## Known issues / notes

- `failedReconstructions.geojson` lists ~23 buildings where City4CFD could
  not reconstruct a LoD 1.2 solid (missing height data in OSM). These are
  excluded from the STL and therefore absent from the mesh.
- The ocean tag in fetch_osm.py returns an empty result (expected — Brasília
  is landlocked).
- snappyHexMesh `resolveFeatureAngle 30` with `implicitFeatureSnap false`
  means building edges are not explicitly snapped; increase `SNH_NEAR` to 4
  for sharper edge resolution.
- The `solverInfo` function object triggers a sha1 IOstream bug in the
  packaged OF1912/aarch64 build — it is disabled in controlDict. Monitor
  residuals via `tail -f openfoam/log.simpleFoam` instead.
