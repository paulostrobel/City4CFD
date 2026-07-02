#!/bin/bash
#SBATCH --job-name=cranfield_mesh
#SBATCH --ntasks=64
#SBATCH --cpus-per-task=1
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=32
#SBATCH --mem-per-cpu=4G
#SBATCH --time=08:00:00
#SBATCH --output=slurm_mesh_%j.log
#SBATCH --error=slurm_mesh_%j.err

# ============================================================================
# Cranfield runway HPC — parallel meshing job (>50M cells)
#
# Runs: blockMesh → decomposePar → snappyHexMesh -parallel → checkMesh
#       → renumberMesh, via pipeline_hpc.sh mesh with N_PROCS = SLURM ranks.
#
# Memory: snappyHexMesh needs roughly 2 KB per final cell in aggregate
#         (~120 GB for 58M cells) — hence 64 ranks × 4 GB here.
#
# Usage:
#   sbatch submit_mesh.slurm
# Prerequisites (run on the login node first):
#   ./pipeline_hpc.sh setup && ./pipeline_hpc.sh stl
# ============================================================================
set -euo pipefail

cd "$SLURM_SUBMIT_DIR"

# Edit for your cluster (module load openfoam/v2412, or a direct path):
export OF_BASHRC="${OF_BASHRC:-/usr/share/openfoam/etc/bashrc}"
[[ -f "$OF_BASHRC" ]] || { echo "ERROR: set OF_BASHRC for your cluster"; exit 1; }

# match the pipeline's rank count to this job
sed -i "s/^N_PROCS=[0-9]*/N_PROCS=$SLURM_NTASKS/" pipeline_hpc.sh

./pipeline_hpc.sh mesh
