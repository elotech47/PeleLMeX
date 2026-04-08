#!/bin/bash
# Extracts timing summary from all benchmark run logs
# Usage: bash collect_timings.sh

CASE_DIR=~/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19
LOG_DIR=${CASE_DIR}/logs

printf "\n%-20s | %-15s | %-10s\n" "Solver" "Total Time (s)" "Steps"
printf "%-20s-+-%-15s-+-%-10s\n" "--------------------" "---------------" "----------"

for log in ${LOG_DIR}/run_*.log; do
    [ -f "$log" ] || continue
    SOLVER=$(basename $log .log | sed 's/run_//')
    TOTAL=$(grep "Total Time:" "$log" | awk '{print $3}')
    STEPS=$(grep "STEP \[" "$log" | tail -1 | grep -oP '\[\K[0-9]+')
    printf "%-20s | %-15s | %-10s\n" "$SOLVER" "${TOTAL:-N/A}" "${STEPS:-N/A}"
done

echo ""
echo "Full logs in: ${LOG_DIR}"
