#!/usr/bin/env python3
"""
parse_timings.py — Extract per-step CPU timing from a PeleLMeX run log.

Reads the log produced by a PeleLMeX run and outputs a CSV file with:
    step, sim_time, dt, advance_wall_time, reaction_wall_time, cumulative_wall_time

Fields:
    step                 — AMReX timestep number
    sim_time             — simulation time at start of this step (s)
    dt                   — timestep size (s)
    advance_wall_time    — wall time for full Advance() call (s)
    reaction_wall_time   — wall time for ScalarReaction() within the step (s)
                           (sum across SDC iterations; 0 if not present in log)
    cumulative_wall_time — running total of advance_wall_time (s)

Usage:
    python parse_timings.py run_log.log                         # auto-name output
    python parse_timings.py run_log.log --output timings.csv    # explicit output
    python parse_timings.py --all                               # parse all logs in logs/local_logs/
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR   = SCRIPT_DIR.parent
LOGS_DIR   = CASE_DIR / "logs" / "local_logs"

# ── Regex patterns ────────────────────────────────────────────────────────────
RE_STEP      = re.compile(r"STEP \[(\d+)\] - Time: ([\d.eE+\-]+), dt ([\d.eE+\-]+)")
RE_ADVANCE   = re.compile(r">> PeleLMeX::Advance\(\) --> Time: ([\d.eE+\-]+)")
RE_REACTION  = re.compile(r"oneSDC\(\)::ScalarReaction\(\)\s*--> Time: ([\d.eE+\-]+)")


# ── Parser ────────────────────────────────────────────────────────────────────
def parse_log(log_path: Path) -> list[dict]:
    """
    Parse a PeleLMeX log and return a list of per-step dicts.
    """
    records = []
    cumulative = 0.0

    current_step = None
    current_sim_time = None
    current_dt = None
    reaction_times: list[float] = []

    with open(log_path) as fh:
        for line in fh:
            # New step header
            m = RE_STEP.search(line)
            if m:
                current_step     = int(m.group(1))
                current_sim_time = float(m.group(2))
                current_dt       = float(m.group(3))
                reaction_times   = []
                continue

            # Reaction wall time (accumulate over SDC iterations)
            m = RE_REACTION.search(line)
            if m and current_step is not None:
                reaction_times.append(float(m.group(1)))
                continue

            # Advance complete — close out this step
            m = RE_ADVANCE.search(line)
            if m and current_step is not None:
                adv_time  = float(m.group(1))
                rxn_time  = sum(reaction_times)
                cumulative += adv_time
                records.append({
                    "step":                 current_step,
                    "sim_time":             current_sim_time,
                    "dt":                   current_dt,
                    "advance_wall_time":    adv_time,
                    "reaction_wall_time":   rxn_time,
                    "cumulative_wall_time": cumulative,
                })
                current_step = None  # reset until next STEP header

    return records


def write_csv(records: list[dict], out_path: Path) -> None:
    if not records:
        print(f"  No step data found — skipping {out_path.name}")
        return
    fields = ["step", "sim_time", "dt", "advance_wall_time",
              "reaction_wall_time", "cumulative_wall_time"]
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(f"  Written {len(records)} rows → {out_path}")


def print_summary(records: list[dict], solver: str) -> None:
    if not records:
        return
    total_steps   = len(records)
    total_wall    = records[-1]["cumulative_wall_time"]
    total_rxn     = sum(r["reaction_wall_time"] for r in records)
    mean_adv      = total_wall / total_steps if total_steps else 0
    rxn_fraction  = (total_rxn / total_wall * 100) if total_wall > 0 else 0

    print(f"  Solver          : {solver}")
    print(f"  Steps           : {total_steps}")
    print(f"  Total wall time : {total_wall:.1f} s")
    print(f"  Mean / step     : {mean_adv:.3f} s")
    print(f"  Reaction frac.  : {rxn_fraction:.1f}%  ({total_rxn:.1f} s)")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract per-step CPU timing from PeleLMeX run logs"
    )
    parser.add_argument("log", nargs="?", type=str, default=None,
                        help="Path to a single PeleLMeX run log")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: <results>/<solver>/timings.csv)")
    parser.add_argument("--all", action="store_true",
                        help=f"Parse all run_*.log files in {LOGS_DIR}")
    args = parser.parse_args()

    if not args.log and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.all:
        logs = sorted(LOGS_DIR.glob("run_*.log"))
        if not logs:
            print(f"No run_*.log files found in {LOGS_DIR}")
            sys.exit(1)
    else:
        logs = [Path(args.log)]

    for log_path in logs:
        if not log_path.exists():
            print(f"ERROR: {log_path} not found")
            continue

        solver = log_path.stem.replace("run_", "")

        # Default output: results/<solver>/timings.csv
        if args.output and len(logs) == 1:
            out_path = Path(args.output)
        else:
            out_dir = CASE_DIR / "results" / solver
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "timings.csv"

        print(f"\n[{solver}]  {log_path.name}")
        records = parse_log(log_path)
        print_summary(records, solver)
        write_csv(records, out_path)


if __name__ == "__main__":
    main()
