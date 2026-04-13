#!/usr/bin/env bash
# =============================================================================
# run_local.sh  — local equivalent of the SLURM benchmark pipeline
#
# Usage:
#   bash run_local.sh --np 4 --coldflow
#   bash run_local.sh --np 4 --solver qss
#   bash run_local.sh --np 4 --coldflow --then-solver qss
#   bash run_local.sh --np 4 --solver cvode_denseAJ
#
# Results go to:  results/<coldflow|SOLVER>/
# Logs go to:     logs/local_logs/
# =============================================================================
set -euo pipefail

# ── Resolve script location so this works from any CWD ──────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASE_DIR="$(dirname "$SCRIPT_DIR")"

# ── Defaults ─────────────────────────────────────────────────────────────────
NP=4
DO_COLDFLOW=false
DO_SOLVER=false
SOLVER=""
THEN_SOLVER=""

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --np)          NP="$2";          shift 2 ;;
        --coldflow)    DO_COLDFLOW=true; shift   ;;
        --solver)      DO_SOLVER=true; SOLVER="$2"; shift 2 ;;
        --then-solver) THEN_SOLVER="$2"; shift 2 ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: bash run_local.sh --np N [--coldflow] [--solver NAME] [--then-solver NAME]"
            exit 1 ;;
    esac
done

if [[ "$DO_COLDFLOW" == false && "$DO_SOLVER" == false && -z "$THEN_SOLVER" ]]; then
    echo "Nothing to do. Specify --coldflow, --solver NAME, or --coldflow --then-solver NAME."
    echo "Usage: bash run_local.sh --np N [--coldflow] [--solver NAME] [--then-solver NAME]"
    exit 1
fi

# ── Find executable ───────────────────────────────────────────────────────────
EXE=$(ls "${CASE_DIR}"/PeleLMeX*.ex 2>/dev/null | head -1)
if [[ -z "$EXE" ]]; then
    echo "ERROR: No PeleLMeX*.ex found in ${CASE_DIR}"
    echo "  Build first: make -j\$(nproc)"
    exit 1
fi
echo "Executable: ${EXE}"

# ── Directories ───────────────────────────────────────────────────────────────
LOGS_DIR="${CASE_DIR}/logs/local_logs"
mkdir -p "${LOGS_DIR}"

# ── Helper: find latest coldflow plotfile ─────────────────────────────────────
find_latest_coldflow() {
    local candidates
    candidates=$(ls -d "${CASE_DIR}/results/coldflow/plt"* 2>/dev/null | sort)
    if [[ -z "$candidates" ]]; then
        echo ""
    else
        echo "$candidates" | tail -1
    fi
}

# ── Helper: run one case ──────────────────────────────────────────────────────
run_case() {
    local name="$1"          # "coldflow" or solver name
    local input_file="$2"    # full path to input file
    local extra_args="${3:-}" # optional extra key=value overrides

    local results_dir="${CASE_DIR}/results/${name}"
    local log_file="${LOGS_DIR}/run_${name}.log"

    mkdir -p "${results_dir}"

    echo ""
    echo "============================================================"
    echo "  Running: ${name}"
    echo "  Input:   ${input_file}"
    echo "  Results: ${results_dir}"
    echo "  Log:     ${log_file}"
    echo "  MPI:     mpirun -np ${NP}"
    echo "============================================================"

    cd "${results_dir}"

    # shellcheck disable=SC2086
    mpirun -np "${NP}" "${EXE}" "${input_file}" \
        amr.plot_file="${results_dir}/plt" \
        amr.check_file="${results_dir}/chk" \
        ${extra_args} \
        2>&1 | tee "${log_file}"

    local status=${PIPESTATUS[0]}
    cd "${CASE_DIR}"

    if [[ $status -ne 0 ]]; then
        echo ""
        echo "ERROR: ${name} run failed (exit code ${status}). Check ${log_file}"
        # Still try to parse timings from a partial run
        if [[ "$name" != "coldflow" ]] && command -v python3 &>/dev/null; then
            echo "  Parsing partial timings from failed run..."
            python3 "${SCRIPT_DIR}/parse_timings.py" "${log_file}" 2>/dev/null || true
        fi
        exit $status
    fi

    echo ""
    echo "  ${name} complete."

    # ── Parse per-step CPU timings into results/<name>/timings.csv ────────────
    if command -v python3 &>/dev/null; then
        echo "  Parsing step timings → results/${name}/timings.csv"
        python3 "${SCRIPT_DIR}/parse_timings.py" "${log_file}"
    fi
}

# ── Cold flow ─────────────────────────────────────────────────────────────────
if [[ "$DO_COLDFLOW" == true ]]; then
    INPUT="${CASE_DIR}/inputs/input.coldflow_cvode"
    if [[ ! -f "$INPUT" ]]; then
        echo "ERROR: ${INPUT} not found"
        exit 1
    fi
    run_case "coldflow" "${INPUT}"
fi

# ── Hot / solver run ──────────────────────────────────────────────────────────
run_solver() {
    local solver="$1"

    local input_base="${CASE_DIR}/inputs/input.${solver}"
    # prefer _local variant if it exists
    if [[ -f "${input_base}_local" ]]; then
        input_base="${input_base}_local"
    elif [[ ! -f "$input_base" ]]; then
        echo "ERROR: No input file found for solver '${solver}'"
        echo "  Looked for: ${CASE_DIR}/inputs/input.${solver}_local"
        echo "              ${CASE_DIR}/inputs/input.${solver}"
        exit 1
    fi

    local coldflow_plt
    coldflow_plt=$(find_latest_coldflow)
    if [[ -z "$coldflow_plt" ]]; then
        echo "ERROR: No coldflow plotfile found in ${CASE_DIR}/results/coldflow/"
        echo "  Run cold flow first: bash run_local.sh --np ${NP} --coldflow"
        exit 1
    fi

    echo "  Cold flow restart: ${coldflow_plt}"
    run_case "${solver}" "${input_base}" "amr.initDataPlt=${coldflow_plt}"
}

if [[ "$DO_SOLVER" == true ]]; then
    run_solver "${SOLVER}"
fi

# --coldflow --then-solver chains the two
if [[ -n "$THEN_SOLVER" ]]; then
    run_solver "${THEN_SOLVER}"
fi

echo ""
echo "All done."
