#!/usr/bin/env python3
"""
Plot centerline temperature profile for all benchmark solver runs.

Reads the latest plotfile from each solver's results/ directory, extracts
temperature along the x-axis at y=0 (through the stagnation plane), and
overlays all solvers on one figure.

Requirements:
    pip install yt matplotlib numpy

Usage:
    python plot_centerline.py                             # latest plotfile, all solvers
    python plot_centerline.py --step 500                  # specific step
    python plot_centerline.py --solvers cvode_denseAJ rk64
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

ALL_SOLVERS = ["cvode_dense", "cvode_denseAJ", "cvode_sparse", "cvode_gmres", "rk64"]

# Distinct colors + line styles so curves are readable in greyscale too
STYLES = {
    "cvode_dense":   dict(color="#1f77b4", ls="-",        lw=1.8),
    "cvode_denseAJ": dict(color="#ff7f0e", ls="--",       lw=1.8),
    "cvode_sparse":  dict(color="#2ca02c", ls="-.",       lw=1.8),
    "cvode_gmres":   dict(color="#d62728", ls=":",        lw=2.0),
    "rk64":          dict(color="#9467bd", ls=(0, (5,1)), lw=1.8),
}

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
    header = Path(pltfile) / "Header"
    with open(header) as fh:
        lines = fh.read().splitlines()
    # Format: version / n_fields / <fields> / dim / time / ...
    n_fields = int(lines[1])
    time_line = 2 + n_fields + 1   # after version, count, field names, dim
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
    if ds.dimensionality == 2:
        cz = float(ds.domain_center[2].d)
        start = [x_lo, 0.0, cz]
        end   = [x_hi, 0.0, cz]
    else:
        cz    = 0.0
        start = [x_lo, 0.0, cz]
        end   = [x_hi, 0.0, cz]

    ray    = ds.ray(start, end)
    x_pos  = ray["x"].d
    values = ray[("boxlib", field)].d

    order = np.argsort(x_pos)
    return x_pos[order] * 1e3, values[order]   # x in mm


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
    parser.add_argument("--output", default=None,
                        help="Output PNG path (default: centerline_temp_<tag>.png in CASE_DIR)")
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

    # ── load profiles ────────────────────────────────────────────────────────
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

    if not profiles:
        print("\nNo profiles loaded. Check that results/ dirs contain plt* files.")
        sys.exit(1)

    # ── plot ─────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))

    for solver, (x_mm, T, t_sim) in profiles.items():
        style = STYLES.get(solver, {})
        label = f"{solver}  (t = {t_sim*1e3:.1f} ms)"
        ax.plot(x_mm, T, label=label, **style)

    ax.set_xlabel("x  (mm)", fontsize=13)
    ax.set_ylabel("Temperature  (K)", fontsize=13)
    ax.set_title("Centerline temperature — solver comparison", fontsize=13)
    ax.legend(fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=11)
    plt.tight_layout()

    # ── save ─────────────────────────────────────────────────────────────────
    if args.output:
        outpath = Path(args.output)
    else:
        step_tag = f"step{args.step:05d}" if args.step else "latest"
        outpath  = CASE_DIR / f"centerline_temp_{step_tag}.png"

    fig.savefig(outpath, dpi=150)
    print(f"\nSaved → {outpath}")


if __name__ == "__main__":
    main()
