#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

source /usr/share/openfoam/etc/bashrc

echo "=== blockMesh ==="
blockMesh 2>&1 | tee log.blockMesh

echo "=== snappyHexMesh ==="
snappyHexMesh -overwrite 2>&1 | tee log.snappyHexMesh

echo "=== checkMesh ==="
checkMesh 2>&1 | tee log.checkMesh

echo "=== simpleFoam ==="
simpleFoam 2>&1 | tee log.simpleFoam

echo "=== Done ==="
