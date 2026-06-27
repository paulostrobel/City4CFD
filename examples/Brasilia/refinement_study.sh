#!/usr/bin/env bash
# =============================================================================
# Mesh refinement study — Brasília Congress microclimate CFD
#
# Runs three mesh levels sequentially, archiving polyMesh + solution after
# each solve. Results are stored under:
#   examples/Brasilia/study/<level>/
#
# Usage:
#   ./refinement_study.sh [LEVEL]
#
# LEVEL (default: all)
#   coarse   – archive current run (BASE=20, NEAR=3) — no re-mesh
#   medium   – BASE=15, NEAR=3  (~15 M cells)
#   fine     – BASE=10, NEAR=4  (~50 M cells, needs ~6 GB RAM)
#   all      – coarse → medium → fine in sequence
#
# After all levels are done, run the comparison plotter:
#   .venv/bin/python3 compare_refinements.py
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OF_CASE="$SCRIPT_DIR/openfoam"
STUDY_DIR="$SCRIPT_DIR/study"
VENV="$REPO_ROOT/.venv"
OF_BASHRC="/usr/share/openfoam/etc/bashrc"
END_TIME=500

log()  { echo ""; echo "=== $* ==="; }
die()  { echo "ERROR: $*" >&2; exit 1; }
of()   { source "$OF_BASHRC" 2>/dev/null; "$@"; }

# ── compute blockMesh cell counts from cell size ────────────────────────────
cell_counts() {
    python3 - "$1" <<'EOF'
import math, sys
s = float(sys.argv[1])
nx = math.ceil(4400 / s)
ny = math.ceil(3430 / s)
nz = max(10, math.ceil(600 / s))
print(f"{nx} {ny} {nz}")
EOF
}

# ── patch mesh knobs and run mesh + solve ───────────────────────────────────
run_level() {
    local NAME=$1 BASE=$2 NEAR=$3 FAR=$4
    local OUT="$STUDY_DIR/$NAME"
    mkdir -p "$OUT"

    log "Level: $NAME  (BASE=${BASE}m  NEAR=${NEAR}  FAR=${FAR})"

    # ── mesh ──────────────────────────────────────────────────────────────
    cd "$OF_CASE"

    if [[ "$NAME" != "coarse" ]]; then
        # clean previous mesh and time dirs
        rm -rf constant/polyMesh
        rm -f  0/cellLevel 0/pointLevel
        for d in [1-9]*/ [1-9][0-9]*/; do [[ -d "$d" ]] && rm -rf "$d"; done || true

        read NX NY NZ <<< "$(cell_counts "$BASE")"
        echo "  Base cells: ${NX}×${NY}×${NZ}"

        sed -i "s/^    hex (0 1 2 3 4 5 6 7) ([0-9]* [0-9]* [0-9]*)/    hex (0 1 2 3 4 5 6 7) ($NX $NY $NZ)/" \
            system/blockMeshDict
        sed -i "s/levels ([0-9]* [0-9]*) ([0-9]* [0-9]*)/levels (20 $NEAR) (50 $FAR)/" \
            system/snappyHexMeshDict

        log "  blockMesh"
        of blockMesh 2>&1 | tee log.blockMesh | grep -E "nCells|Error|End" || true

        log "  snappyHexMesh"
        of snappyHexMesh -overwrite 2>&1 | tee log.snappyHexMesh | \
            grep -E "cells:|FATAL|Finished meshing" || true

        log "  checkMesh"
        of checkMesh 2>&1 | tee log.checkMesh | \
            grep -E "cells:|Max |Min |mesh ok|FAILED|\*\*\*" || true
    else
        log "  Coarse: using existing mesh"
        of checkMesh 2>&1 | grep -E "cells:|mesh ok" || true
    fi

    # archive mesh
    cp -r constant/polyMesh "$OUT/polyMesh"
    cp    log.checkMesh     "$OUT/log.checkMesh"
    echo "$BASE $NEAR $FAR" > "$OUT/knobs.txt"

    # ── solve ─────────────────────────────────────────────────────────────
    if [[ "$NAME" == "coarse" ]] && [[ -d "$OF_CASE/500" ]]; then
        log "  Coarse: solution already exists — archiving"
    else
        log "  simpleFoam ($END_TIME iterations)"
        sed -i "s/^endTime .*/endTime         $END_TIME;/" system/controlDict
        of simpleFoam 2>&1 | tee log.simpleFoam
    fi

    # archive solution
    local TDIR
    TDIR=$(ls -d "$OF_CASE"/[0-9]*/ 2>/dev/null | sort -V | tail -1)
    if [[ -n "$TDIR" ]]; then
        cp -r "$TDIR" "$OUT/solution"
        echo "  Solution archived from: $TDIR → $OUT/solution"
    fi
    cp log.simpleFoam "$OUT/log.simpleFoam" 2>/dev/null || true

    log "Level $NAME done → $OUT"
}

# ── main ────────────────────────────────────────────────────────────────────
LEVEL="${1:-all}"
mkdir -p "$STUDY_DIR"

case "$LEVEL" in
    coarse) run_level coarse 20 3 2 ;;
    medium) run_level medium 15 3 2 ;;
    fine)   run_level fine   10 4 2 ;;
    all)
        run_level coarse 20 3 2
        run_level medium 15 3 2
        run_level fine   10 4 2
        ;;
    *) die "Unknown level '$LEVEL'. Valid: coarse medium fine all" ;;
esac

log "Refinement study complete — results in $STUDY_DIR"
echo "Run comparison: .venv/bin/python3 compare_refinements.py"
