#!/bin/bash
set -e
cd /home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/openfoam
source /usr/share/openfoam/etc/bashrc 2>/dev/null
echo "[$(date)] Starting simpleFoam" | tee -a ../fine_pipeline.log
simpleFoam > log.simpleFoam 2>&1
echo "[$(date)] simpleFoam done" | tee -a ../fine_pipeline.log
