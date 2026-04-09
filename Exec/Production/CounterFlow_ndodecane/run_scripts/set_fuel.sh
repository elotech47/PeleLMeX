#!/bin/bash
# Update the fuel species and chemistry mechanism across all input files and GNUmakefile.
#
# Usage:
#   bash set_fuel.sh --fuel CH4 --mechanism drm19
#   bash set_fuel.sh --fuel NC12H26 --mechanism dodecane_lu30
#   bash set_fuel.sh --fuel CH4                  # only update fuel, keep current mechanism
#   bash set_fuel.sh --mechanism grimech30        # only update mechanism, keep current fuel

set -euo pipefail

CASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

INPUTS_DIR="${CASE_DIR}/inputs"
GNUMAKEFILE="${CASE_DIR}/GNUmakefile"

# Root-level originals are also kept in sync
ROOT_INPUTS=(
    "${CASE_DIR}/input.2d-regt"
    "${CASE_DIR}/input_coolflow.2d-regt"
)

# ============================================================
# Parse arguments
# ============================================================
NEW_FUEL=""
NEW_MECH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fuel)      NEW_FUEL="$2";  shift 2 ;;
        --mechanism) NEW_MECH="$2";  shift 2 ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--fuel FUEL_NAME] [--mechanism MECHANISM]"
            exit 1
            ;;
    esac
done

if [[ -z "$NEW_FUEL" && -z "$NEW_MECH" ]]; then
    echo "Usage: $0 [--fuel FUEL_NAME] [--mechanism MECHANISM]"
    echo ""
    echo "Examples:"
    echo "  $0 --fuel CH4 --mechanism drm19"
    echo "  $0 --fuel NC12H26 --mechanism dodecane_lu30"
    echo "  $0 --fuel C2H4 --mechanism USC_Mech_II"
    exit 1
fi

# ============================================================
# Detect current values for reporting
# ============================================================
CURRENT_FUEL=$(grep -m1 'peleLM\.fuel_name' "${CASE_DIR}/input.2d-regt" \
               | awk -F'=' '{print $2}' | xargs)
CURRENT_MECH=$(grep -m1 'Chemistry_Model' "${GNUMAKEFILE}" \
               | awk -F'=' '{print $2}' | xargs)

echo ""
echo "=== set_fuel.sh ==="
echo "  Case dir : ${CASE_DIR}"
echo "  Current  : fuel=${CURRENT_FUEL}  mechanism=${CURRENT_MECH}"

# ============================================================
# Apply fuel change to all input files
# ============================================================
if [[ -n "$NEW_FUEL" ]]; then
    echo ""
    echo "  Updating fuel: ${CURRENT_FUEL} → ${NEW_FUEL}"

    ALL_INPUTS=("${ROOT_INPUTS[@]}" "${INPUTS_DIR}"/input.*)

    for f in "${ALL_INPUTS[@]}"; do
        [[ -f "$f" ]] || continue
        sed -i \
            -e "s|peleLM\.fuel_name = .*|peleLM.fuel_name = ${NEW_FUEL}|" \
            -e "s|peleLM\.mixtureFraction\.fuelTank = .*|peleLM.mixtureFraction.fuelTank = ${NEW_FUEL}:1.0|" \
            "$f"
        echo "    updated: $(basename "$f")"
    done
fi

# ============================================================
# Apply fuel species ID change to pelelmex_prob.H
# ============================================================
PROB_H="${CASE_DIR}/pelelmex_prob.H"

if [[ -n "$NEW_FUEL" && -f "$PROB_H" ]]; then
    OLD_FUEL_ID="${CURRENT_FUEL}_ID"
    NEW_FUEL_ID="${NEW_FUEL}_ID"
    if grep -q "${OLD_FUEL_ID}" "${PROB_H}"; then
        echo "  Updating fuel species ID in pelelmex_prob.H: ${OLD_FUEL_ID} → ${NEW_FUEL_ID}"
        sed -i "s|${OLD_FUEL_ID}|${NEW_FUEL_ID}|g" "${PROB_H}"
        echo "    updated: pelelmex_prob.H"
        echo ""
        echo "  NOTE: pelelmex_prob.H change requires a full rebuild:"
        echo "    make realclean && make -j8"
    else
        echo "  WARNING: ${OLD_FUEL_ID} not found in pelelmex_prob.H — check manually"
    fi
fi

# ============================================================
# Apply mechanism change to GNUmakefile
# ============================================================
if [[ -n "$NEW_MECH" ]]; then
    echo ""
    echo "  Updating mechanism: ${CURRENT_MECH} → ${NEW_MECH}"
    sed -i "s|Chemistry_Model = .*|Chemistry_Model = ${NEW_MECH}|" "${GNUMAKEFILE}"
    echo "    updated: GNUmakefile"
    echo ""
    echo "  NOTE: A mechanism change requires a full rebuild:"
    echo "    make realclean && make -j8"
fi

# ============================================================
# Summary
# ============================================================
echo ""
NEW_FUEL_SHOW="${NEW_FUEL:-${CURRENT_FUEL} (unchanged)}"
NEW_MECH_SHOW="${NEW_MECH:-${CURRENT_MECH} (unchanged)}"
echo "  Done. New state: fuel=${NEW_FUEL_SHOW}  mechanism=${NEW_MECH_SHOW}"
echo ""
