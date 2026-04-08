#!/bin/bash
#SBATCH --job-name=pelelm_coldflow
#SBATCH --output={{CASE_DIR}}/logs/slurm_logs/%x_%j.out
#SBATCH --error={{CASE_DIR}}/logs/slurm_logs/%x_%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --partition=single
#SBATCH -A loni_chemnet3
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=eikpon1@lsu.edu

# ============================================================
# Environment setup
# ============================================================
source ~/combustion_research/PeleLMeX/setup_env_loni.sh

# ============================================================
# Working directory
# ============================================================
cd $SLURM_SUBMIT_DIR
mkdir -p {{CASE_DIR}}/logs/slurm_logs
mkdir -p {{CASE_DIR}}/results/coldflow

# ============================================================
# Run cold flow to develop the flow field
# Output plotfiles go to results/coldflow/
# ============================================================
CASE_DIR="{{CASE_DIR}}"
EXE="${CASE_DIR}/PeleLMeX2d.gnu.MPI.ex"

echo "Starting cold flow run..."
echo "Case dir: ${CASE_DIR}"
echo "Executable: ${EXE}"

cd ${CASE_DIR}/results/coldflow

mpirun -np 8 ${EXE} ${CASE_DIR}/inputs/input.coldflow \
    amr.plot_file=${CASE_DIR}/results/coldflow/plt \
    amr.check_file=${CASE_DIR}/results/coldflow/chk \
    2>&1 | tee ${CASE_DIR}/logs/coldflow.log

echo "Cold flow run complete."
echo "Final plotfile: $(ls -dt ${CASE_DIR}/results/coldflow/plt* | head -1)"
