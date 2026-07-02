# Cranfield Runway — HPC case (>50M-cell mesh)

High-detail companion to [`../CranfieldRunway`](../CranfieldRunway): identical
geometry, runway-aligned domain and ABL boundary conditions, but a **>50M-cell
mesh** with high refinement on **both the buildings and the runway**, built and
solved fully decomposed for an HPC cluster.

## Quick start

On the cluster login node (after the parent case's `deps`/`build`/`osm`/`geometry`
stages have produced `../CranfieldRunway/results/`):

```bash
cd examples/CranfieldRunway_HPC
./pipeline_hpc.sh setup     # symlinks data/, results/; copies 0/, constant/, shared dicts
./pipeline_hpc.sh stl       # buildings.stl + runway.stl (same rotation)
sbatch submit_mesh.slurm    # blockMesh → decomposePar → parallel snappy (64 ranks, ~4 h)
sbatch submit_solve.slurm   # simpleFoam, 128 ranks, up to 48 h
```

Validate the complete workflow first on any 4-core workstation:

```bash
LOCAL_TEST=1 ./pipeline_hpc.sh all    # coarse mesh, 4 MPI ranks, 10 iterations
```

## Mesh strategy

Background mesh 10 m (410×320×30 = 3.94M cells over the 4100×3200×300 m
domain), refined by parallel snappyHexMesh:

| Region | Level | Cell size | ~Cells |
|---|---|---|---|
| background | 0 | 10 m | 3.9M |
| ≤50 m of buildings | 3 | 1.25 m | (transition) |
| ≤20 m of buildings + walls | 4 (surface 3–4) | 0.625 m | ~53M |
| ≤24 m above runway/taxiway/apron | 2 | 2.5 m | ~0.5M |
| ≤8 m above runway/taxiway/apron | 3 | 1.25 m | ~1.5M |
| **total** | | | **~58M** |

The building-zone estimate scales the verified workstation runs of the parent
case (1.32M cells at 20 m base / level 3 within 20 m): halving the refined cell
size from 2.5 m to 0.625 m multiplies the ~0.83M refined-zone cells by
(2.5/0.625)³ = 64. Exact counts depend on the OSM geometry — the mesh job
prints the final number; if it lands under 50M, lower `BASE_CELL_SIZE` to 8
(+95% background cells) or raise `RWY_NEAR` to 4 before re-meshing.

**Runway refinement**: `runway.stl` is generated from City4CFD's imprinted
aeroway layer (`Cranfield_Runway_Runway.obj` — runway, taxiways, aprons) with
the same rotation as the buildings. Because it is coplanar with the domain
floor it is used only as a **distance-mode refinement region**, never as a
snapping surface: the patch set stays identical to the workstation case, the
parent's `0/` fields apply unchanged, and the near-ground cells over the whole
movement area resolve the runway's wind environment at 1.25 m.

All knobs are at the top of `pipeline_hpc.sh`:

```bash
BASE_CELL_SIZE=10   # background cell [m]
SNH_NEAR=4          # ≤20 m of buildings          SNH_FAR=3   # ≤50 m
RWY_NEAR=3          # ≤8 m above the runway       RWY_FAR=2   # ≤24 m
N_PROCS=128         # MPI ranks
END_TIME=500        # simpleFoam iterations
```

## HPC workflow

Everything runs decomposed; the 50M mesh is never reconstructed:

```
blockMesh (serial, 3.9M cells)
  → decomposePar  (scotch — load-balances the non-uniform refinement)
  → mpirun snappyHexMesh -parallel -overwrite
  → mpirun checkMesh -parallel
  → mpirun renumberMesh -parallel -overwrite
  → mpirun simpleFoam -parallel        (sbatch submit_solve.slurm)
```

Differences from the workstation case, all in committed dicts:

| File | Change |
|---|---|
| `system/blockMeshDict` | 10 m base cells |
| `system/snappyHexMeshDict` | `runway` triSurface + distance regions; buildings level (3 4)/(20 4)(50 3); `maxGlobalCells 120M`, `maxLocalCells 20M` |
| `system/decomposeParDict` | `method scotch`, 128 subdomains |
| `system/controlDict` | `writeFormat binary` (ascii I/O is infeasible at 50M), `startFrom latestTime` for restarts |

## Resource estimates

| Step | Ranks | Memory | Wall time |
|---|---|---|---|
| snappyHexMesh | 64 | ~2 KB/cell aggregate → 4 GB/rank | 2–4 h |
| simpleFoam (500 iter) | 128 | ~2 GB/rank | 24–48 h |
| storage per write | — | ~6 GB (binary, U p k ε νt) | `purgeWrite 2` keeps 2 |

Edit the `OF_BASHRC` path (or export it) in the SLURM scripts for your
cluster's OpenFOAM installation; any recent ESI version (v1912–v2412) works.

## Post-processing

At 50M cells use the decomposed case directly in ParaView (`Decomposed Case`
option in the OpenFOAM reader), or extract slices in parallel:

```bash
mpirun -np $N postProcess -parallel -func "surfaces" -latestTime
```

The parent case's `plot_runway.py` works on a reconstructed case only — for
the HPC mesh prefer ParaView or function-object surfaces.
