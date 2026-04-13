#!/bin/bash
# collect_timings.sh — Print a timing summary from all available run logs.
#
# Searches logs/local_logs/ (local runs) first, then logs/ (HPC runs).
# Also regenerates results/<solver>/timings.csv via parse_timings.py.
#
# Usage:
#   bash run_scripts/collect_timings.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASE_DIR="$(dirname "$SCRIPT_DIR")"
LOCAL_LOG_DIR="${CASE_DIR}/logs/local_logs"
HPC_LOG_DIR="${CASE_DIR}/logs"

# ── Refresh timings.csv ───────────────────────────────────────────────────────
if command -v python3 &>/dev/null && [[ -d "$LOCAL_LOG_DIR" ]]; then
    echo "Refreshing timings.csv from local logs..."
    python3 "${SCRIPT_DIR}/parse_timings.py" --all 2>/dev/null || true
    echo ""
fi

# ── Helper: extract stats from CSV ───────────────────────────────────────────
csv_stats() {
    local csv_path="$1"
    [[ -f "$csv_path" ]] || { echo "N/A N/A N/A"; return; }
    python3 - "$csv_path" <<'EOF'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
if not rows:
    print("N/A N/A N/A"); sys.exit(0)
tot_wall = float(rows[-1]['cumulative_wall_time'])
rxn      = sum(float(r['reaction_wall_time']) for r in rows)
rxn_frac = f"{rxn/tot_wall*100:.1f}%" if tot_wall > 0 else "N/A"
sim_ms   = float(rows[-1]['sim_time']) * 1e3
print(f"{tot_wall:.1f} {sim_ms:.2f} {rxn_frac}")
EOF
}

# ── Print summary table ───────────────────────────────────────────────────────
printf "\n%-22s | %-14s | %-10s | %-8s | %-12s | %-6s\n" \
    "Solver" "Wall time (s)" "Sim t (ms)" "Steps" "Reaction %" "Source"
printf "%.0s-" {1..82}; echo ""

printed=()

for logdir in "${LOCAL_LOG_DIR}" "${HPC_LOG_DIR}"; do
    [[ -d "$logdir" ]] || continue
    [[ "$logdir" == "$LOCAL_LOG_DIR" ]] && src="local" || src="hpc"

    for log in "${logdir}"/run_*.log; do
        [[ -f "$log" ]] || continue
        SOLVER=$(basename "$log" .log | sed 's/run_//')

        # Skip duplicates (local already printed for same solver)
        already=0
        for s in "${printed[@]:-}"; do [[ "$s" == "$SOLVER" ]] && already=1; done
        [[ $already -eq 1 ]] && continue
        printed+=("$SOLVER")

        STEPS=$(grep "STEP \[" "$log" 2>/dev/null | tail -1 \
                | grep -oP '\[\K[0-9]+' 2>/dev/null || echo "N/A")

        CSV="${CASE_DIR}/results/${SOLVER}/timings.csv"
        read -r WALLTIME SIM_MS RXNFRAC <<< "$(csv_stats "$CSV")"

        printf "%-22s | %-14s | %-10s | %-8s | %-12s | %-6s\n" \
            "${SOLVER}" "${WALLTIME}" "${SIM_MS}" "${STEPS:-N/A}" "${RXNFRAC}" "${src}"
    done
done

echo ""
echo "Wall time: cumulative from timings.csv (works for partial/failed runs too)"
echo "Sim t:     last recorded simulation time"
echo "Reaction%: fraction of advance time spent in chemistry"
echo "Details:   results/<solver>/timings.csv"
