#!/bin/bash
set -e
cd /home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/openfoam
source /usr/share/openfoam/etc/bashrc 2>/dev/null

echo "[$(date)] Starting blockMesh" | tee -a ../fine_pipeline.log
blockMesh > log.blockMesh 2>&1
echo "[$(date)] blockMesh done" | tee -a ../fine_pipeline.log

echo "[$(date)] Starting snappyHexMesh" | tee -a ../fine_pipeline.log
snappyHexMesh -overwrite > log.snappyHexMesh 2>&1
echo "[$(date)] snappyHexMesh done" | tee -a ../fine_pipeline.log

echo "[$(date)] Starting simpleFoam" | tee -a ../fine_pipeline.log
simpleFoam > log.simpleFoam 2>&1
echo "[$(date)] simpleFoam done" | tee -a ../fine_pipeline.log
# (resume from simpleFoam only)
