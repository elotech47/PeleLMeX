#!/usr/bin/env python3
"""
Plot centerline temperature profile for all benchmark solver runs,
including the initial cold flow profile as a reference.

Reads the latest plotfile from each solver's results/ directory, extracts
temperature along the x-axis at y=0 (through the stagnation plane), and
overlays all solvers on one figure.

Requirements:
    pip install yt matplotlib numpy

Usage:
    python plot_centerline.py                             # latest plotfile, all solvers
    python plot_centerline.py --step 500                  # specific step
    python plot_centerline.py --solvers cvode_denseAJ rk64
    python plot_centerline.py --no-coldflow               # skip initial profile
    python plot_centerline.py --output my_comparison.png
    python plot_centerline.py --results-dir /path/to/results
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")   # non-interactive — safe on the cluster
import matplotlib.pyplot as plt

# ============================================================
# Configuration
# ============================================================
CASE_DIR    = Path("/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19")
RESULTS_DIR = CASE_DIR / "results"

ALL_SOLVERS = ["cvode_dense", "cvode_denseAJ", "cvode_gmres"]

# Distinct colors + line styles so curves are readable in greyscale too
STYLES = {
    "cvode_dense":   dict(color="#1f77b4", ls="-",  lw=1.8),
    "cvode_denseAJ": dict(color="#ff7f0e", ls="--", lw=1.8),
    "cvode_gmres":   dict(color="#d62728", ls=":",  lw=2.0),
}

COLDFLOW_STYLE = dict(color="black", ls=(0, (3, 1, 1, 1)), lw=1.4, alpha=0.7)

# ============================================================
# Plotfile helpers
# ============================================================

def find_plotfile(solver_dir, step=None):
    """Return a plotfile Path. Uses `step` if given, otherwise the latest plt*."""
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
    """Read simulation time from the plotfile Header."""
    with open(Path(pltfile) / "Header") as fh:
        lines = fh.read().splitlines()
    n_fields = int(lines[1])
    time_line = 2 + n_fields + 1   # version / count / fields / dim / time
    return float(lines[time_line])


# ============================================================
# Profile extraction via yt
# ============================================================

def extract_centerline(pltfile, field="temp"):
    """
    Extract a 1-D profile of `field` along the x-axis at y=0.
    Returns (x_mm, values) as numpy arrays sorted by x.
    """
    import yt
    yt.set_log_level("error")

    ds = yt.load(str(pltfile))

    x_lo = float(ds.domain_left_edge[0].d)
    x_hi = float(ds.domain_right_edge[0].d)

    # yt represents 2-D AMReX files with a thin z dimension; use its midpoint
    cz = float(ds.domain_center[2].d) if ds.dimensionality == 2 else 0.0
    ray = ds.ray([x_lo, 0.0, cz], [x_hi, 0.0, cz])

    order  = np.argsort(ray["x"].d)
    x_mm   = ray["x"].d[order] * 1e3
    values = ray[("boxlib", field)].d[order]
    return x_mm, values


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Centerline temperature comparison across PeleLMeX solver runs"
    )
    parser.add_argument("--step", type=int, default=None,
                        help="Plotfile step number (default: latest for each solver)")
    parser.add_argument("--solvers", nargs="+", default=None,
                        help="Subset of solvers (default: all five)")
    parser.add_argument("--field", default="temp",
                        help="Plotfile field name to plot (default: temp)")
    parser.add_argument("--no-coldflow", action="store_true",
                        help="Skip the initial cold flow reference profile")
    parser.add_argument("--output", default=None,
                        help="Output PNG path (default: centerline_temp_<tag>.png)")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR),
                        help=f"Path to results/ directory (default: {RESULTS_DIR})")
    args = parser.parse_args()

    try:
        import yt  # noqa: F401
    except ImportError:
        print("ERROR: yt is required.  Install with:  pip install yt")
        sys.exit(1)

    results_dir = Path(args.results_dir)
    solvers     = args.solvers or ALL_SOLVERS

    # ── cold flow initial profile ─────────────────────────────────────────────
    coldflow_profile = None
    if not args.no_coldflow:
        coldflow_dir = results_dir / "coldflow"
        coldflow_plt = find_plotfile(coldflow_dir)
        if coldflow_plt is not None:
            try:
                t_cf = read_plotfile_time(coldflow_plt)
                print(f"  {'coldflow (initial)':<20s}  {coldflow_plt.name}"
                      f"  (t = {t_cf*1e3:.1f} ms) ...", end=" ", flush=True)
                x_mm, T = extract_centerline(coldflow_plt, field=args.field)
                coldflow_profile = (x_mm, T, t_cf)
                print(f"T_max = {T.max():.0f} K")
            except Exception as exc:
                print(f"FAILED — {exc}")
        else:
            print("  [skip] cold flow: no plotfile found in results/coldflow/")

    # ── solver profiles ───────────────────────────────────────────────────────
    profiles = {}
    for solver in solvers:
        solver_dir = results_dir / solver
        if not solver_dir.is_dir():
            print(f"  [skip] {solver}: {solver_dir} not found")
            continue

        pltfile = find_plotfile(solver_dir, step=args.step)
        if pltfile is None:
            msg = f"step {args.step:05d}" if args.step else "any plt*"
            print(f"  [skip] {solver}: no plotfile ({msg})")
            continue

        try:
            t_sim = read_plotfile_time(pltfile)
            print(f"  {solver:<20s}  {pltfile.name}  (t = {t_sim*1e3:.2f} ms) ...",
                  end=" ", flush=True)
            x_mm, T = extract_centerline(pltfile, field=args.field)
            profiles[solver] = (x_mm, T, t_sim)
            print(f"T_max = {T.max():.0f} K")
        except Exception as exc:
            print(f"FAILED — {exc}")

    if not profiles and coldflow_profile is None:
        print("\nNo profiles loaded. Check that results/ dirs contain plt* files.")
        sys.exit(1)

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))

    # Draw cold flow first so it sits behind the solver curves
    if coldflow_profile is not None:
        x_mm, T, t_cf = coldflow_profile
        ax.plot(x_mm, T,
                label=f"initial / cold flow  (t = {t_cf*1e3:.1f} ms)",
                **COLDFLOW_STYLE)

    for solver, (x_mm, T, t_sim) in profiles.items():
        style = STYLES.get(solver, {})
        ax.plot(x_mm, T, label=f"{solver}  (t = {t_sim*1e3:.1f} ms)", **style)

    ax.set_xlabel("x  (mm)", fontsize=13)
    ax.set_ylabel("Temperature  (K)", fontsize=13)
    ax.set_title("Centerline temperature — solver comparison", fontsize=13)
    ax.legend(fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=11)
    plt.tight_layout()

    # ── save ──────────────────────────────────────────────────────────────────
    if args.output:
        outpath = Path(args.output)
    else:
        step_tag = f"step{args.step:05d}" if args.step else "latest"
        outpath  = CASE_DIR / f"centerline_temp_{step_tag}.png"

    fig.savefig(outpath, dpi=150)
    print(f"\nSaved → {outpath}")


if __name__ == "__main__":
    main()
