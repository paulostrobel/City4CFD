#!/bin/bash
#SBATCH --job-name=brasilia_hpc
#SBATCH --ntasks=128
#SBATCH --cpus-per-task=1
#SBATCH --time=48:00:00
#SBATCH --mem-per-cpu=2G
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=32
#SBATCH --output=slurm_%j.log
#SBATCH --error=slurm_%j.err

# ============================================================================
# Brasília Congress HPC solver job (50M mesh, 128 cores, ~48h)
# ============================================================================
# Usage:
#   sbatch submit.slurm              # Default: 48h, 128 cores
#   sbatch --time=24:00:00 submit.slurm  # Override to 24h
#
# Check job status:
#   squeue -u $USER
#   scancel <JOBID>
# ============================================================================

set -euo pipefail

echo "================================================================================"
echo "Brasília CFD HPC Solver"
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_NNODES  |  Tasks: $SLURM_NTASKS  |  CPUs/task: $SLURM_CPUS_PER_TASK"
echo "Walltime: $SLURM_TIME_LIMIT  |  Memory: $(($SLURM_MEM_PER_CPU * $SLURM_NTASKS / 1024)) GB total"
echo "================================================================================"
echo ""

CASE_DIR="$SLURM_SUBMIT_DIR/openfoam"
cd "$CASE_DIR" || exit 1

# ── Source OpenFOAM ──────────────────────────────────────────────────────────
# Edit this path for your HPC system:
OF_BASHRC="/opt/openfoam/etc/bashrc"  # Example: module-based path
# Or:
# OF_BASHRC="/software/OpenFOAM-v2412/etc/bashrc"

[[ -f "$OF_BASHRC" ]] || {
    echo "ERROR: OpenFOAM bashrc not found at $OF_BASHRC"
    echo "Edit submit.slurm to set the correct path for your cluster"
    exit 1
}

source "$OF_BASHRC" || exit 1
echo "OpenFOAM sourced from: $OF_BASHRC"
echo ""

# ── Parallel solver ──────────────────────────────────────────────────────────
echo "Starting simpleFoam on $SLURM_NTASKS cores..."
echo "Mesh: ~50M cells"
echo "Initial residuals: U ~10⁻³, p ~10⁻⁴"
echo ""

mpirun -np $SLURM_NTASKS simpleFoam -parallel 2>&1 | tee log.simpleFoam

EXITCODE=${PIPESTATUS[0]}
echo ""
echo "================================================================================"
echo "Solver finished with exit code: $EXITCODE"
echo "================================================================================"

exit $EXITCODE
