#!/bin/bash
#SBATCH --job-name=cranfield_solve
#SBATCH --ntasks=128
#SBATCH --cpus-per-task=1
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=32
#SBATCH --mem-per-cpu=2G
#SBATCH --time=48:00:00
#SBATCH --output=slurm_solve_%j.log
#SBATCH --error=slurm_solve_%j.err

# ============================================================================
# Cranfield runway HPC — parallel solver job (>50M cells, 128 ranks)
#
# The mesh must already exist decomposed for exactly this many ranks
# (submit_mesh.slurm with --ntasks=128, or redecompose:
#   decomposePar -force  after editing system/decomposeParDict).
#
# Usage:
#   sbatch submit_solve.slurm
#   squeue -u $USER              # status
#   tail -f openfoam/log.simpleFoam
# ============================================================================
set -euo pipefail

CASE_DIR="$SLURM_SUBMIT_DIR/openfoam"
cd "$CASE_DIR"

# Edit for your cluster (module load openfoam/v2412, or a direct path):
OF_BASHRC="${OF_BASHRC:-/usr/share/openfoam/etc/bashrc}"
[[ -f "$OF_BASHRC" ]] || { echo "ERROR: set OF_BASHRC for your cluster"; exit 1; }
set +u; source "$OF_BASHRC"; set -u

NPROC_DIRS=$(ls -d processor* 2>/dev/null | wc -l)
[[ "$NPROC_DIRS" -eq "$SLURM_NTASKS" ]] || {
    echo "ERROR: mesh is decomposed for $NPROC_DIRS ranks but job has $SLURM_NTASKS"
    exit 1
}

echo "simpleFoam on $SLURM_NTASKS ranks, $(date)"
mpirun -np "$SLURM_NTASKS" simpleFoam -parallel 2>&1 | tee log.simpleFoam

exit "${PIPESTATUS[0]}"
