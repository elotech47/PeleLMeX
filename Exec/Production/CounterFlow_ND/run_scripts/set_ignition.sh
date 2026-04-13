#!/bin/bash
# Update ignition kernel parameters across all reacting input files.
# Does NOT touch input.coldflow (cold flow has do_ignition = 0).
#
# Usage:
#   bash set_ignition.sh --temp 1800 --radius 0.003
#   bash set_ignition.sh --temp 1500              # only update temperature
#   bash set_ignition.sh --radius 0.002           # only update radius

set -euo pipefail

CASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INPUTS_DIR="${CASE_DIR}/inputs"

ROOT_INPUTS=()

# ============================================================
# Parse arguments
# ============================================================
NEW_TEMP=""
NEW_RAD=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --temp)   NEW_TEMP="$2"; shift 2 ;;
        --radius) NEW_RAD="$2";  shift 2 ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--temp TEMPERATURE_K] [--radius RADIUS_M]"
            exit 1
            ;;
    esac
done

if [[ -z "$NEW_TEMP" && -z "$NEW_RAD" ]]; then
    echo "Usage: $0 [--temp TEMPERATURE_K] [--radius RADIUS_M]"
    echo ""
    echo "Examples:"
    echo "  $0 --temp 1800 --radius 0.003   # hotter, larger kernel"
    echo "  $0 --temp 1500                  # only raise temperature"
    echo "  $0 --radius 0.002               # only change radius"
    echo ""
    echo "Current values are read from inputs/input.cvode_denseAJ"
    echo "Recommended range: --temp 1500–2000  --radius 0.002–0.004"
    exit 1
fi

# ============================================================
# Detect current values for reporting
# ============================================================
REF_FILE="${INPUTS_DIR}/input.cvode_denseAJ"
CURRENT_TEMP=$(grep -m1 'prob\.ignition_SphT' "${REF_FILE}" \
               | awk -F'=' '{print $2}' | xargs)
CURRENT_RAD=$(grep -m1 'prob\.ignition_SphRad' "${REF_FILE}" \
              | awk -F'=' '{print $2}' | xargs)

echo ""
echo "=== set_ignition.sh ==="
echo "  Case dir : ${CASE_DIR}"
echo "  Current  : ignition_SphT=${CURRENT_TEMP} K   ignition_SphRad=${CURRENT_RAD} m"

# ============================================================
# Build list of files to update — all benchmark inputs, NOT coldflow
# ============================================================
BENCHMARK_INPUTS=()
for f in "${ROOT_INPUTS[@]}" "${INPUTS_DIR}"/input.*; do
    [[ -f "$f" ]] || continue
    # Skip coldflow input — it has do_ignition = 0 and no SphT/SphRad lines
    [[ "$(basename "$f")" == "input.coldflow" ]] && continue
    BENCHMARK_INPUTS+=("$f")
done

# ============================================================
# Apply changes
# ============================================================
echo ""

if [[ -n "$NEW_TEMP" ]]; then
    echo "  Updating ignition_SphT: ${CURRENT_TEMP} K → ${NEW_TEMP} K"
    for f in "${BENCHMARK_INPUTS[@]}"; do
        sed -i "s|prob\.ignition_SphT = .*|prob.ignition_SphT = ${NEW_TEMP}.0|" "$f"
        echo "    updated: $(basename "$f")"
    done
fi

if [[ -n "$NEW_RAD" ]]; then
    echo ""
    echo "  Updating ignition_SphRad: ${CURRENT_RAD} m → ${NEW_RAD} m"
    for f in "${BENCHMARK_INPUTS[@]}"; do
        sed -i "s|prob\.ignition_SphRad = .*|prob.ignition_SphRad = ${NEW_RAD}|" "$f"
        echo "    updated: $(basename "$f")"
    done
fi

# ============================================================
# Summary
# ============================================================
echo ""
NEW_TEMP_SHOW="${NEW_TEMP:-${CURRENT_TEMP} (unchanged)}"
NEW_RAD_SHOW="${NEW_RAD:-${CURRENT_RAD} (unchanged)}"
echo "  Done. New state: ignition_SphT=${NEW_TEMP_SHOW} K   ignition_SphRad=${NEW_RAD_SHOW} m"
echo ""
echo "  Resubmit with:"
echo "    python run_scripts/submit_benchmark.py --benchmark --nodes 2 --stop-time 0.5"
echo ""
