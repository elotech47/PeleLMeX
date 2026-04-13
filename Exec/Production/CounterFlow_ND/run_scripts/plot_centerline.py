#!/usr/bin/env python3
"""
Two-panel figure for the PeleLMeX solver benchmark:
  Top    — centerline temperature profile for all solvers + cold flow reference
  Bottom — total wall-clock time per solver (from run logs)

Requirements:
    pip install yt matplotlib numpy

Usage:
    python plot_centerline.py                             # latest plotfile, all solvers
    python plot_centerline.py --step 500                  # specific step
    python plot_centerline.py --solvers cvode_denseAJ cvode_gmres
    python plot_centerline.py --no-coldflow               # skip initial profile
    python plot_centerline.py --output my_comparison.png
    python plot_centerline.py --results-dir /path/to/results
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================================================
# Configuration
# ============================================================
CASE_DIR    = Path("/home/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_ND")
RESULTS_DIR = CASE_DIR / "results"
LOGS_DIR    = CASE_DIR / "logs/local_logs"

ALL_SOLVERS = ["cvode_dense", "cvode_denseAJ", "cvode_gmres", "qss", "adaptive"]

STYLES = {
    "cvode_dense":   dict(color="#1f77b4", ls="-",  lw=1.8),
    "cvode_denseAJ": dict(color="#ff7f0e", ls="--", lw=1.8),
    "cvode_gmres":   dict(color="#d62728", ls=":",  lw=2.0),
    "qss":           dict(color="#2ca02c", ls="-.", lw=1.8),
    "adaptive":      dict(color="#9467bd", ls="--", lw=1.8),
}

COLDFLOW_STYLE = dict(color="black", ls=(0, (3, 1, 1, 1)), lw=1.4, alpha=0.7)

# ============================================================
# Plotfile helpers
# ============================================================

def find_plotfile(solver_dir, step=None):
    base = Path(solver_dir)
    if step is not None:
        for name in (f"plt{step:05d}", f"plt{step}"):
            p = base / name
            if p.is_dir():
                return p
        return None
    candidates = sorted(p for p in base.glob("plt*") if p.is_dir())
    return candidates[-1] if candidates else None


def read_plotfile_time(pltfile):
    with open(Path(pltfile) / "Header") as fh:
        lines = fh.read().splitlines()
    n_fields  = int(lines[1])
    time_line = 2 + n_fields + 1
    return float(lines[time_line])


# ============================================================
# Profile extraction via yt
# ============================================================

def extract_centerline(pltfile, field="temp"):
    import yt
    yt.set_log_level("error")

    ds   = yt.load(str(pltfile))
    x_lo = float(ds.domain_left_edge[0].d)
    x_hi = float(ds.domain_right_edge[0].d)
    cz   = float(ds.domain_center[2].d) if ds.dimensionality == 2 else 0.0

    ray   = ds.ray([x_lo, 0.0, cz], [x_hi, 0.0, cz])
    order = np.argsort(ray["x"].d)
    return ray["x"].d[order] * 1e3, ray[("boxlib", field)].d[order]


# ============================================================
# Log parsing
# ============================================================

def parse_total_time(log_path):
    """Return total wall-clock time (s) from a run log, or None if not found."""
    try:
        text = Path(log_path).read_text()
        match = re.search(r"Total Time:\s+([\d.eE+\-]+)", text)
        return float(match.group(1)) if match else None
    except FileNotFoundError:
        return None


def parse_n_steps(log_path):
    """Return the last completed step number from a run log."""
    try:
        text = Path(log_path).read_text()
        matches = re.findall(r"STEP \[(\d+)\]", text)
        return int(matches[-1]) if matches else None
    except FileNotFoundError:
        return None


def load_timings_csv(csv_path):
    """
    Load per-step timing data from a timings.csv produced by parse_timings.py.
    Returns (total_wall_s, n_steps, rxn_fraction) or None if not found.
    """
    import csv
    try:
        with open(csv_path) as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            return None
        n_steps   = len(rows)
        total     = float(rows[-1]["cumulative_wall_time"])
        rxn_total = sum(float(r["reaction_wall_time"]) for r in rows)
        rxn_frac  = rxn_total / total if total > 0 else 0.0
        return total, n_steps, rxn_frac
    except (FileNotFoundError, KeyError, ValueError):
        return None


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Centerline temperature + CPU time comparison across solver runs"
    )
    parser.add_argument("--step", type=int, default=None,
                        help="Plotfile step number (default: latest)")
    parser.add_argument("--solvers", nargs="+", default=None,
                        help="Subset of solvers (default: all three)")
    parser.add_argument("--field", default="temp",
                        help="Plotfile field name (default: temp)")
    parser.add_argument("--no-coldflow", action="store_true",
                        help="Skip the initial cold flow reference profile")
    parser.add_argument("--output", default=None,
                        help="Output PNG path")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR),
                        help=f"Path to results/ directory (default: {RESULTS_DIR})")
    parser.add_argument("--logs-dir", default=str(LOGS_DIR),
                        help=f"Path to logs/ directory (default: {LOGS_DIR})")
    args = parser.parse_args()

    try:
        import yt  # noqa: F401
    except ImportError:
        print("ERROR: yt is required.  Install with:  pip install yt")
        sys.exit(1)

    results_dir = Path(args.results_dir)
    logs_dir    = Path(args.logs_dir)
    solvers     = args.solvers or ALL_SOLVERS

    # ── cold flow reference ───────────────────────────────────────────────────
    coldflow_profile = None
    if not args.no_coldflow:
        coldflow_plt = find_plotfile(results_dir / "coldflow")
        if coldflow_plt:
            try:
                t_cf = read_plotfile_time(coldflow_plt)
                print(f"  {'coldflow':<20s}  {coldflow_plt.name}"
                      f"  (t = {t_cf*1e3:.1f} ms) ...", end=" ", flush=True)
                x_mm, T = extract_centerline(coldflow_plt, field=args.field)
                coldflow_profile = (x_mm, T, t_cf)
                print(f"T_max = {T.max():.0f} K")
            except Exception as exc:
                print(f"FAILED — {exc}")
        else:
            print("  [skip] cold flow: no plotfile in results/coldflow/")

    # ── solver profiles + timings ─────────────────────────────────────────────
    profiles = {}   # solver → (x_mm, T, t_sim)
    timings  = {}   # solver → total_wall_time_s

    for solver in solvers:
        solver_dir = results_dir / solver
        log_path   = logs_dir / f"run_{solver}.log"

        # temperature profile
        if solver_dir.is_dir():
            pltfile = find_plotfile(solver_dir, step=args.step)
            if pltfile:
                try:
                    t_sim = read_plotfile_time(pltfile)
                    print(f"  {solver:<20s}  {pltfile.name}"
                          f"  (t = {t_sim*1e3:.2f} ms) ...", end=" ", flush=True)
                    x_mm, T = extract_centerline(pltfile, field=args.field)
                    profiles[solver] = (x_mm, T, t_sim)
                    print(f"T_max = {T.max():.0f} K")
                except Exception as exc:
                    print(f"FAILED — {exc}")
            else:
                print(f"  [skip] {solver}: no plotfile found")
        else:
            print(f"  [skip] {solver}: results dir not found")

        # wall-clock time — prefer timings.csv (more accurate), fall back to log
        csv_path   = results_dir / solver / "timings.csv"
        csv_data   = load_timings_csv(csv_path)
        if csv_data is not None:
            t_wall, n_steps, rxn_frac = csv_data
            timings[solver] = (t_wall, n_steps, rxn_frac)
            print(f"           timing: {t_wall:.1f} s  ({n_steps} steps, "
                  f"rxn={rxn_frac*100:.0f}%)  [from CSV]")
        else:
            t_wall  = parse_total_time(log_path)
            n_steps = parse_n_steps(log_path)
            if t_wall is not None:
                timings[solver] = (t_wall, n_steps, None)
                print(f"           timing: {t_wall:.1f} s  ({n_steps} steps)  [from log]")
            else:
                print(f"           timing: not found ({log_path.name})")

    if not profiles and coldflow_profile is None and not timings:
        print("\nNothing to plot.")
        sys.exit(1)

    # ── figure: two stacked panels ────────────────────────────────────────────
    fig, (ax_temp, ax_time) = plt.subplots(
        2, 1, figsize=(8, 9),
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.38}
    )

    # — top: temperature profiles —
    if coldflow_profile is not None:
        x_mm, T, t_cf = coldflow_profile
        ax_temp.plot(x_mm, T,
                     label=f"initial / cold flow  (t = {t_cf*1e3:.1f} ms)",
                     **COLDFLOW_STYLE)

    for solver, (x_mm, T, t_sim) in profiles.items():
        ax_temp.plot(x_mm, T,
                     label=f"{solver}  (t = {t_sim*1e3:.1f} ms)",
                     **STYLES.get(solver, {}))

    ax_temp.set_xlabel("x  (mm)", fontsize=12)
    ax_temp.set_ylabel("Temperature  (K)", fontsize=12)
    ax_temp.set_title("Centerline temperature — solver comparison", fontsize=13)
    ax_temp.legend(fontsize=10, framealpha=0.9)
    ax_temp.grid(True, alpha=0.3)
    ax_temp.tick_params(labelsize=11)

    # — bottom: wall-clock time bar chart —
    if timings:
        solver_names  = list(timings.keys())
        wall_times    = [timings[s][0] for s in solver_names]
        bar_colors    = [STYLES.get(s, {}).get("color", "#888888") for s in solver_names]

        bars = ax_time.barh(solver_names, wall_times, color=bar_colors,
                            edgecolor="white", height=0.5)

        # label each bar with wall time, step count, and reaction fraction
        for bar, solver in zip(bars, solver_names):
            w        = bar.get_width()
            n_steps  = timings[solver][1]
            rxn_frac = timings[solver][2]
            label    = f"  {w:.1f} s"
            if n_steps is not None:
                label += f"  ({n_steps} steps)"
            if rxn_frac is not None:
                label += f"  rxn={rxn_frac*100:.0f}%"
            ax_time.text(w, bar.get_y() + bar.get_height() / 2,
                         label, va="center", ha="left", fontsize=10)

        ax_time.set_xlabel("Wall-clock time  (s)", fontsize=12)
        ax_time.set_title("Total CPU time per solver  (rxn% = time in chemistry)", fontsize=13)
        ax_time.tick_params(labelsize=11)
        ax_time.set_xlim(right=max(wall_times) * 1.25)
        ax_time.invert_yaxis()   # match the legend order (top = first solver)
        ax_time.grid(True, axis="x", alpha=0.3)
        ax_time.spines["top"].set_visible(False)
        ax_time.spines["right"].set_visible(False)
    else:
        ax_time.text(0.5, 0.5, "No timing data found\n(run logs not yet available)",
                     ha="center", va="center", transform=ax_time.transAxes,
                     fontsize=12, color="grey")
        ax_time.set_axis_off()

    # ── save ──────────────────────────────────────────────────────────────────
    if args.output:
        outpath = Path(args.output)
    else:
        step_tag = f"step{args.step:05d}" if args.step else "latest"
        outpath  = CASE_DIR / f"centerline_temp_{step_tag}.png"

    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    print(f"\nSaved → {outpath}")


if __name__ == "__main__":
    main()
