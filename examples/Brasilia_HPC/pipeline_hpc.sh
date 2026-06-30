#!/usr/bin/env bash
# =============================================================================
# Brasília Congress HPC pipeline — 50M element mesh
# Ultra-refined for high-performance computing (128+ cores)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT_DIR="$SCRIPT_DIR/../Brasilia"
OF_CASE="$SCRIPT_DIR/openfoam"
VENV="$REPO_ROOT/.venv"
OF_BASHRC="/usr/share/openfoam/etc/bashrc"

# ── HPC mesh knobs ───────────────────────────────────────────────────────────
BASE_CELL_SIZE=7.5   # metres — ~50M cells target
SNH_NEAR=4           # refinement level within 20 m (high detail)
SNH_FAR=3            # refinement level within 50 m
END_TIME=500         # solver iterations
N_PROCS=128          # parallel cores for decomposition

log()  { echo ""; echo "=== $* ==="; }
die()  { echo "ERROR: $*" >&2; exit 1; }
of()   { source "$OF_BASHRC" 2>/dev/null; "$@"; }

compute_block_cells() {
    python3 - <<EOF
import math
s = $BASE_CELL_SIZE
nx = math.ceil(4400 / s)
ny = math.ceil(3430 / s)
nz = max(10, math.ceil(600 / s))
print(f"{nx} {ny} {nz}")
EOF
}

# =============================================================================
stage_setup() {
    log "Setting up HPC case from parent"
    cd "$SCRIPT_DIR"

    # Symlink shared resources
    [[ -L data ]] || ln -s "$PARENT_DIR/data" data
    [[ -L results ]] || ln -s "$PARENT_DIR/results" results
    [[ -L fix_congress_geometry.py ]] || ln -s "$PARENT_DIR/fix_congress_geometry.py" fix_congress_geometry.py

    # Copy OpenFOAM structure
    mkdir -p openfoam/{0,constant/triSurface,system}

    # Copy from parent (avoid symlink for mutable dirs)
    [[ -f openfoam/0/U ]] || cp -r "$PARENT_DIR/openfoam/0"/* openfoam/0/ 2>/dev/null || true
    [[ -f openfoam/system/controlDict ]] || cp -r "$PARENT_DIR/openfoam/system"/* openfoam/system/ 2>/dev/null || true

    echo "Setup complete"
}

# =============================================================================
stage_stl() {
    log "Generating STL from results/"
    [[ -d results ]] || die "results/ symlink not found — run stage_setup first"

    source "$OF_BASHRC" 2>/dev/null || die "OpenFOAM not sourced"
    cd "$SCRIPT_DIR"
    mkdir -p "$VENV" || true
    [[ -x "$VENV/bin/python3" ]] || python3 -m venv "$VENV"

    "$VENV/bin/pip" install -q trimesh 2>/dev/null || true

    "$VENV/bin/python3" - <<'PYEOF'
import trimesh, os
results = "results"
out     = "openfoam/constant/triSurface/buildings.stl"
meshes  = []
for f in ["Brasilia_Congress_Buildings_0.obj", "Brasilia_Congress_Buildings_1.obj"]:
    p = f"{results}/{f}"
    if os.path.exists(p):
        meshes.append(trimesh.load(p, force="mesh"))
if not meshes:
    exit("No OBJ files found")
combined = trimesh.util.concatenate(meshes)
combined.export(out)
print(f"Exported {len(combined.faces):,} faces → {out}")
PYEOF
}

# =============================================================================
stage_fix_geometry() {
    log "Fixing Congress complex geometry"
    [[ -f fix_congress_geometry.py ]] || die "fix_congress_geometry.py not found"

    source "$VENV/bin/activate" 2>/dev/null || true
    cd "$SCRIPT_DIR"
    python3 fix_congress_geometry.py
}

# =============================================================================
stage_mesh() {
    log "Meshing for HPC (BASE_CELL_SIZE=$BASE_CELL_SIZE m, SNH_NEAR=$SNH_NEAR, target ~50M cells)"
    log "⚠️  WARNING: snappyHexMesh requires 20–30 GB RAM. Ensure sufficient memory available."
    cd "$OF_CASE"

    # Update blockMeshDict
    read NX NY NZ <<< "$(compute_block_cells)"
    echo "  Base cells: ${NX} x ${NY} x ${NZ}  (${BASE_CELL_SIZE} m target)"
    sed -i "s/^    hex (0 1 2 3 4 5 6 7) ([0-9]* [0-9]* [0-9]*)/    hex (0 1 2 3 4 5 6 7) ($NX $NY $NZ)/" \
        system/blockMeshDict

    # Update snappyHexMeshDict
    sed -i "s/levels ([0-9]* [0-9]*) ([0-9]* [0-9]*)/levels (20 $SNH_NEAR) (50 $SNH_FAR)/" \
        system/snappyHexMeshDict

    log "  blockMesh"
    of blockMesh 2>&1 | tee log.blockMesh | grep -E "nCells|Error|End"

    log "  snappyHexMesh (this will take 1–4 hours and use 20–30 GB RAM)"
    of snappyHexMesh -overwrite 2>&1 | tee log.snappyHexMesh | \
        grep -E "cells:|FATAL|Finished meshing"

    log "  checkMesh"
    of checkMesh 2>&1 | tee log.checkMesh | \
        grep -E "cells:|Max |Min |mesh ok|FAILED"
}

# =============================================================================
stage_decompose() {
    log "Decomposing mesh for $N_PROCS cores"
    cd "$OF_CASE"

    # Update decomposeParDict
    sed -i "s/numberOfSubdomains .*/numberOfSubdomains $N_PROCS;/" \
        system/decomposeParDict 2>/dev/null || {
        # If decomposeParDict doesn't exist, create it
        cat > system/decomposeParDict <<EOF
FoamFile { version 2.0; format ascii; class dictionary; location "system"; object decomposeParDict; }

numberOfSubdomains $N_PROCS;
method simple;
simpleCoeffs
{
    n ($N_PROCS 1 1);
}

distributed false;
EOF
    }

    log "  preparePar"
    of preparePar 2>&1 | tee log.preparePar | grep -E "decomposing|Created|processors"
}

# =============================================================================
stage_solve() {
    log "Solver ready for parallel execution on $N_PROCS cores"
    cd "$OF_CASE"

    # Update controlDict for HPC
    sed -i "s/^endTime .*/endTime         $END_TIME;/" system/controlDict
    sed -i "s/^writeInterval .*/writeInterval   100;/" system/controlDict

    log "  simpleFoam (HPC ready)"
    log "  Run on cluster:"
    log "    cd $OF_CASE"
    log "    source $OF_BASHRC"
    log "    mpirun -np $N_PROCS simpleFoam -parallel 2>&1 | tee log.simpleFoam"
}

# =============================================================================
STAGE="${1:-all}"
cd "$SCRIPT_DIR"

case "$STAGE" in
    setup)       stage_setup ;;
    stl)         stage_stl; stage_fix_geometry ;;
    mesh)        stage_mesh ;;
    decompose)   stage_decompose ;;
    solve)       stage_solve ;;
    all)
        stage_setup
        stage_stl
        stage_fix_geometry
        stage_mesh
        stage_decompose
        stage_solve
        ;;
    *) die "Unknown stage '$STAGE'. Valid: setup stl mesh decompose solve all" ;;
esac

log "Done — stage: $STAGE"
