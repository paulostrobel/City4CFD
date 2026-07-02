#!/usr/bin/env bash
# =============================================================================
# Cranfield University runway microclimate — HPC pipeline (>50M-cell mesh)
#
# High-detail companion to examples/CranfieldRunway: same geometry, domain and
# boundary conditions, but a 10 m background mesh with level-4 refinement on
# the buildings and dedicated refinement bands above the runway/taxiway/apron.
# The mesh is built and solved fully decomposed (scotch) — it is never
# reconstructed.
#
# Usage:
#   ./pipeline_hpc.sh [STAGE]
#
# STAGE (default: all)
#   setup      – symlink data/results from ../CranfieldRunway, copy 0/, constant/
#   stl        – generate buildings.stl AND runway.stl (same rotation)
#   mesh       – blockMesh → decomposePar → parallel snappyHexMesh → checkMesh
#   solve      – print sbatch instructions (or run locally under LOCAL_TEST=1)
#   all        – run every stage in order
#
# HPC knobs (edit before running):
#   BASE_CELL_SIZE=10   background cell [m]            (~3.94M base cells)
#   SNH_NEAR=4          level ≤20 m of buildings       (0.625 m cells)
#   SNH_FAR=3           level ≤50 m of buildings       (1.25 m cells)
#   RWY_NEAR=3          level ≤8 m above the runway    (1.25 m cells)
#   RWY_FAR=2           level ≤24 m above the runway   (2.5 m cells)
#   N_PROCS=128         MPI ranks for meshing and solving
#   END_TIME=500        simpleFoam iterations
#
# Workstation validation of the full parallel workflow at coarse settings:
#   LOCAL_TEST=1 ./pipeline_hpc.sh all
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT_DIR="$SCRIPT_DIR/../CranfieldRunway"
OF_CASE="$SCRIPT_DIR/openfoam"
VENV="$REPO_ROOT/.venv"
OF_BASHRC="${OF_BASHRC:-/usr/share/openfoam/etc/bashrc}"

# ── HPC mesh knobs ───────────────────────────────────────────────────────────
BASE_CELL_SIZE=10
SNH_NEAR=4
SNH_FAR=3
RWY_NEAR=3
RWY_FAR=2
N_PROCS=128
END_TIME=500

# ── LOCAL_TEST=1: coarse settings to validate the workflow on a workstation ──
if [[ "${LOCAL_TEST:-0}" == "1" ]]; then
    BASE_CELL_SIZE=40
    SNH_NEAR=2
    SNH_FAR=1
    RWY_NEAR=1
    RWY_FAR=1
    N_PROCS=4
    END_TIME=10
    # allow mpirun inside root containers
    export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
    echo "*** LOCAL_TEST mode: coarse mesh, $N_PROCS ranks, $END_TIME iterations ***"
fi

log()  { echo ""; echo "=== $* ==="; }
die()  { echo "ERROR: $*" >&2; exit 1; }
# OpenFOAM's bashrc references unset variables — relax nounset while sourcing
of()   { set +u; source "$OF_BASHRC" 2>/dev/null; set -u; "$@"; }

# Domain: X -1800..2300 (4100 m), Y -1600..1600 (3200 m), Z 0..300 (300 m)
compute_block_cells() {
    python3 - <<EOF
import math
s = $BASE_CELL_SIZE
nx = math.ceil(4100 / s)
ny = math.ceil(3200 / s)
nz = max(10, math.ceil(300 / s))
print(f"{nx} {ny} {nz}")
EOF
}

# =============================================================================
stage_setup() {
    log "Setting up HPC case from ../CranfieldRunway"
    cd "$SCRIPT_DIR"
    [[ -d "$PARENT_DIR/results" ]] || die "parent results/ missing — run ../CranfieldRunway/pipeline.sh geometry first"

    [[ -e data ]]    || ln -s ../CranfieldRunway/data data
    [[ -e results ]] || ln -s ../CranfieldRunway/results results

    mkdir -p openfoam/{0,0.orig,constant/triSurface,system}
    # Initial fields live in 0.orig and are distributed into processor*/0
    # AFTER parallel meshing (snappy creates the 'buildings' patch only then).
    # Copy the solution fields only — the parent 0/ may also hold stale
    # cellLevel/pointLevel files from its own snappyHexMesh runs.
    for f in "$PARENT_DIR/openfoam/0"/{U,p,k,epsilon,nut}; do
        dest="openfoam/0.orig/$(basename "$f")"
        [[ -f "$dest" ]] && continue
        cp "$f" "$dest"
        # cover the decomposition's processor patches with constraint defaults
        sed -i '/^boundaryField$/{n;s/^{/{\n    #includeEtc "caseDicts\/setConstraintTypes"/}' "$dest"
    done
    for f in "$PARENT_DIR/openfoam/constant/transportProperties" \
             "$PARENT_DIR/openfoam/constant/turbulenceProperties"; do
        dest="openfoam/constant/$(basename "$f")"
        [[ -f "$dest" ]] || cp "$f" "$dest"
    done
    # dicts shared with the workstation case (the HPC-specific ones —
    # blockMeshDict, snappyHexMeshDict, decomposeParDict, controlDict — are
    # committed in this folder and must not be overwritten)
    for f in fvSchemes fvSolution meshQualityDict; do
        [[ -f "openfoam/system/$f" ]] || cp "$PARENT_DIR/openfoam/system/$f" openfoam/system/
    done
    echo "Setup complete"
}

# =============================================================================
stage_stl() {
    log "Generating buildings.stl and runway.stl (runway-aligned rotation)"
    [[ -x "$VENV/bin/python3" ]] || die "venv not found — run ../CranfieldRunway/pipeline.sh deps"
    cd "$SCRIPT_DIR"
    mkdir -p "$OF_CASE/constant/triSurface"

    "$VENV/bin/python3" "$PARENT_DIR/rotate_and_merge_stl.py" \
        --results results --runway data/cranfield_runway.geojson \
        --out "$OF_CASE/constant/triSurface/buildings.stl"

    "$VENV/bin/python3" "$PARENT_DIR/rotate_and_merge_stl.py" \
        --results results --runway data/cranfield_runway.geojson \
        --glob "Cranfield_Runway_Runway.obj" \
        --out "$OF_CASE/constant/triSurface/runway.stl"
}

# =============================================================================
stage_mesh() {
    log "HPC meshing: base ${BASE_CELL_SIZE} m, buildings (${SNH_FAR} ${SNH_NEAR}), runway (${RWY_FAR} ${RWY_NEAR}), ${N_PROCS} ranks"
    cd "$OF_CASE"

    read NX NY NZ <<< "$(compute_block_cells)"
    echo "  Base cells: ${NX} x ${NY} x ${NZ}"
    sed -i "s/^    hex (0 1 2 3 4 5 6 7) ([0-9]* [0-9]* [0-9]*)/    hex (0 1 2 3 4 5 6 7) ($NX $NY $NZ)/" \
        system/blockMeshDict

    # surface + distance refinement levels (distances make each sed unambiguous)
    sed -i "s/level ([0-9]* [0-9]*);/level ($SNH_FAR $SNH_NEAR);/" system/snappyHexMeshDict
    sed -i "s/levels ((20 [0-9]*) (50 [0-9]*))/levels ((20 $SNH_NEAR) (50 $SNH_FAR))/" system/snappyHexMeshDict
    sed -i "s/levels ((8 [0-9]*) (24 [0-9]*))/levels ((8 $RWY_NEAR) (24 $RWY_FAR))/" system/snappyHexMeshDict
    sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $N_PROCS;/" system/decomposeParDict
    if [[ "${LOCAL_TEST:-0}" == "1" ]]; then
        # Ubuntu's packaged OpenFOAM ships a scotch stub — use hierarchical
        sed -i "s/^method .*/method          hierarchical;/" system/decomposeParDict
    fi

    log "  blockMesh (serial)"
    of blockMesh 2>&1 | tee log.blockMesh | grep -E "nCells|Error|End" \
        || die "blockMesh failed — see openfoam/log.blockMesh"

    log "  decomposePar ($N_PROCS subdomains)"
    of decomposePar -force 2>&1 | tee log.decomposePar | grep -icE "processor" >/dev/null \
        || die "decomposePar failed — see openfoam/log.decomposePar"
    grep -qE "FATAL" log.decomposePar && die "decomposePar failed — see openfoam/log.decomposePar"

    log "  snappyHexMesh -parallel  (50M-cell target: hours; needs ~2 KB/cell aggregate RAM)"
    of mpirun -np "$N_PROCS" snappyHexMesh -parallel -overwrite 2>&1 | \
        tee log.snappyHexMesh | grep -E "Refined mesh|Snapped mesh|FATAL|Finished meshing" \
        || die "snappyHexMesh failed — see openfoam/log.snappyHexMesh"
    grep -q "Finished meshing without any errors" log.snappyHexMesh \
        || die "snappyHexMesh did not finish cleanly — see openfoam/log.snappyHexMesh"

    log "  distributing initial fields (0.orig → processor*/0)"
    for p in processor*; do
        mkdir -p "$p/0"
        cp 0.orig/* "$p/0/"
    done

    log "  checkMesh -parallel"
    of mpirun -np "$N_PROCS" checkMesh -parallel 2>&1 | tee log.checkMesh | \
        grep -E "cells:|Max |Min |mesh OK|Failed|\*\*\*" \
        || die "checkMesh failed — see openfoam/log.checkMesh"

    log "  renumberMesh -parallel (bandwidth reduction for the solver)"
    of mpirun -np "$N_PROCS" renumberMesh -parallel -overwrite 2>&1 | \
        tee log.renumberMesh | grep -cE "Band|End" >/dev/null \
        || die "renumberMesh failed — see openfoam/log.renumberMesh"
}

# =============================================================================
stage_solve() {
    cd "$OF_CASE"
    sed -i "s/^endTime .*/endTime         $END_TIME;/" system/controlDict

    if [[ "${LOCAL_TEST:-0}" == "1" ]]; then
        log "LOCAL_TEST solve: mpirun -np $N_PROCS simpleFoam -parallel ($END_TIME iterations)"
        of mpirun -np "$N_PROCS" simpleFoam -parallel 2>&1 | tee log.simpleFoam | \
            grep -E "^Time = |converged|FATAL" | tail -5
    else
        log "Mesh is decomposed for $N_PROCS ranks — submit the solver as a batch job:"
        echo "    cd $SCRIPT_DIR"
        echo "    sbatch submit_solve.slurm"
        echo "  (or interactively:  mpirun -np $N_PROCS simpleFoam -parallel)"
    fi
}

# =============================================================================
STAGE="${1:-all}"
cd "$SCRIPT_DIR"

case "$STAGE" in
    setup)  stage_setup ;;
    stl)    stage_stl ;;
    mesh)   stage_mesh ;;
    solve)  stage_solve ;;
    all)
        stage_setup
        stage_stl
        stage_mesh
        stage_solve
        ;;
    *) die "Unknown stage '$STAGE'. Valid: setup stl mesh solve all" ;;
esac

log "Done — stage: $STAGE"
