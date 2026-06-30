#!/usr/bin/env bash
# =============================================================================
# Brasília Congress microclimate CFD pipeline
# City4CFD → snappyHexMesh → simpleFoam (kEpsilon, steady-state)
#
# Usage:
#   ./pipeline.sh [STAGE]
#
# STAGE (default: all)
#   deps         – install system + Python packages
#   build        – compile City4CFD
#   osm          – download OpenStreetMap data
#   geometry     – run City4CFD to generate OBJ surfaces
#   stl          – convert OBJ → buildings.stl for snappyHexMesh
#   fix-geometry – replace Congress complex with accurate primitives
#   mesh         – blockMesh + snappyHexMesh + checkMesh
#   solve        – run simpleFoam
#   all          – run every stage in order
#
# Mesh refinement knobs (edit before running):
#   BASE_CELL_SIZE  – blockMesh target cell size in metres (default 20)
#   SNH_NEAR        – snappyHexMesh refinement level within 20 m (default 3)
#   SNH_FAR         – snappyHexMesh refinement level within 50 m (default 2)
#   END_TIME        – simpleFoam iterations (default 500)
# =============================================================================
set -euo pipefail

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OF_CASE="$SCRIPT_DIR/openfoam"
RESULTS="$SCRIPT_DIR/results"
VENV="$REPO_ROOT/.venv"
OF_BASHRC="/usr/share/openfoam/etc/bashrc"

# ── refinement knobs ─────────────────────────────────────────────────────────
BASE_CELL_SIZE=20   # metres — halving doubles cell count in each direction (~8×)
SNH_NEAR=3          # refinement level within 20 m of buildings
SNH_FAR=2           # refinement level within 50 m of buildings
END_TIME=500        # simpleFoam iterations

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo ""; echo "=== $* ==="; }
die()  { echo "ERROR: $*" >&2; exit 1; }
of()   { source "$OF_BASHRC" 2>/dev/null; "$@"; }

require_venv() {
    [[ -x "$VENV/bin/python3" ]] || die "venv not found — run:  ./pipeline.sh deps"
}

require_binary() {
    command -v "$1" &>/dev/null || die "$1 not found — run:  ./pipeline.sh build"
}

# ── blockMeshDict cell counts derived from BASE_CELL_SIZE ────────────────────
# Domain: X -1700..2700 (4400 m), Y -1730..1700 (3430 m), Z 0..600 (600 m)
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
stage_deps() {
    log "Installing dependencies"
    sudo apt-get install -y \
        cmake libcgal-dev libgdal-dev libeigen3-dev \
        libboost-filesystem-dev libboost-locale-dev libboost-dev

    [[ -x "$VENV/bin/python3" ]] || python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet osmnx geopandas pyproj shapely geopy trimesh
    echo "Dependencies OK"
}

# =============================================================================
stage_build() {
    log "Building City4CFD"
    require_binary cmake
    cd "$REPO_ROOT"
    mkdir -p build
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -Wno-dev
    make -j"$(nproc)" -C build
    [[ -x "$REPO_ROOT/build/city4cfd" ]] || die "Build failed"
    echo "city4cfd built at $REPO_ROOT/build/city4cfd"
}

# =============================================================================
stage_osm() {
    log "Downloading OSM data"
    require_venv
    cd "$SCRIPT_DIR"
    mkdir -p data
    "$VENV/bin/python3" "$REPO_ROOT/tools/fetch_polygons/fetch_osm.py"
}

# =============================================================================
stage_geometry() {
    log "Running City4CFD"
    require_binary "$REPO_ROOT/build/city4cfd"
    cd "$SCRIPT_DIR"
    mkdir -p results
    "$REPO_ROOT/build/city4cfd" config_bpg.json --output_dir results
}

# =============================================================================
stage_stl() {
    log "Converting OBJ → STL"
    require_venv
    mkdir -p "$OF_CASE/constant/triSurface"
    "$VENV/bin/python3" - <<'PYEOF'
import trimesh, sys, os
results = os.environ.get("RESULTS", "results")
out     = os.environ.get("STL_OUT", "openfoam/constant/triSurface/buildings.stl")
meshes  = []
for f in ["Brasilia_Congress_Buildings_0.obj", "Brasilia_Congress_Buildings_1.obj"]:
    p = f"{results}/{f}"
    if os.path.exists(p):
        meshes.append(trimesh.load(p, force="mesh"))
if not meshes:
    sys.exit("No building OBJ files found — run geometry stage first")
combined = trimesh.util.concatenate(meshes)
combined.export(out)
print(f"Exported {len(combined.faces):,} faces → {out}")
PYEOF
}
export RESULTS="$RESULTS"
export STL_OUT="$OF_CASE/constant/triSurface/buildings.stl"

# =============================================================================
stage_fix_geometry() {
    log "Fixing Congress complex geometry"
    require_venv
    cd "$SCRIPT_DIR"
    [[ -f fix_congress_geometry.py ]] || die "fix_congress_geometry.py not found"
    "$VENV/bin/python3" fix_congress_geometry.py
}

# =============================================================================
stage_mesh() {
    log "Meshing (blockMesh + snappyHexMesh)"
    cd "$OF_CASE"

    # Re-generate blockMeshDict with current BASE_CELL_SIZE
    read NX NY NZ <<< "$(compute_block_cells)"
    echo "  Base cells: ${NX} x ${NY} x ${NZ}  (${BASE_CELL_SIZE} m target)"

    sed -i "s/^    hex (0 1 2 3 4 5 6 7) ([0-9]* [0-9]* [0-9]*)/    hex (0 1 2 3 4 5 6 7) ($NX $NY $NZ)/" \
        system/blockMeshDict

    # Patch snappyHexMesh refinement levels
    sed -i "s/levels ([0-9]* [0-9]*) ([0-9]* [0-9]*)/levels (20 $SNH_NEAR) (50 $SNH_FAR)/" \
        system/snappyHexMeshDict

    log "  blockMesh"
    of blockMesh 2>&1 | tee log.blockMesh | grep -E "nCells|Error|End"

    log "  snappyHexMesh"
    of snappyHexMesh -overwrite 2>&1 | tee log.snappyHexMesh | \
        grep -E "cells:|FATAL|Finished meshing"

    log "  checkMesh"
    of checkMesh 2>&1 | tee log.checkMesh | \
        grep -E "cells:|Max |Min |mesh ok|FAILED|\*\*\*"
}

# =============================================================================
stage_solve() {
    log "Running simpleFoam (endTime=$END_TIME)"
    cd "$OF_CASE"

    # Update endTime in controlDict
    sed -i "s/^endTime .*/endTime         $END_TIME;/" system/controlDict

    of simpleFoam 2>&1 | tee log.simpleFoam
}

# =============================================================================
STAGE="${1:-all}"
cd "$SCRIPT_DIR"

case "$STAGE" in
    deps)           stage_deps ;;
    build)          stage_build ;;
    osm)            stage_osm ;;
    geometry)       stage_geometry ;;
    stl)            stage_stl ;;
    fix-geometry)   stage_fix_geometry ;;
    mesh)           stage_mesh ;;
    solve)          stage_solve ;;
    all)
        stage_deps
        stage_build
        stage_osm
        stage_geometry
        stage_stl
        stage_fix_geometry
        stage_mesh
        stage_solve
        ;;
    *) die "Unknown stage '$STAGE'. Valid: deps build osm geometry stl fix-geometry mesh solve all" ;;
esac

log "Done — stage: $STAGE"
