#!/usr/bin/env python3
"""
Temporal evolution of centerline temperature for each benchmark solver.

Produces one subplot per solver. Each subplot overlays the T(x) centerline
profile at every available plotfile, coloured by simulation time so you can
see the flame evolve (or quench) over the run.

Requirements:
    pip install yt matplotlib numpy

Usage:
    python plot_temporal.py                        # all solvers, all plotfiles
    python plot_temporal.py --solvers cvode_denseAJ cvode_gmres
    python plot_temporal.py --every 3              # plot every Nth plotfile (thin out)
    python plot_temporal.py --output evolution.png
    python plot_temporal.py --results-dir /path/to/results
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# ============================================================
# Configuration
# ============================================================
CASE_DIR    = Path("/home/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_ND")
RESULTS_DIR = CASE_DIR / "results"

# Directories to never treat as solver results
_SKIP_DIRS = {"coldflow"}

# Colormap for time evolution: early = cool, late = warm
CMAP = cm.plasma

# ============================================================
# Helpers
# ============================================================

def find_plotfiles(solver_dir):
    """
    Return sorted list of clean plt##### directories.
    Excludes plt#####.old.XXXXXXX leftovers from AMReX restarts.
    """
    pattern = re.compile(r"^plt\d{5}$")
    candidates = sorted(
        p for p in Path(solver_dir).iterdir()
        if p.is_dir() and pattern.match(p.name)
    )
    return candidates


def discover_solvers(results_dir):
    """
    Auto-discover solver subdirectories in results_dir that contain plotfiles.
    Skips 'coldflow' and any directory without at least one plt##### folder.
    """
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        return []
    found = []
    for d in sorted(results_dir.iterdir()):
        if d.is_dir() and d.name not in _SKIP_DIRS:
            if find_plotfiles(d):
                found.append(d.name)
    return found


def read_plotfile_time(pltfile):
    with open(Path(pltfile) / "Header") as fh:
        lines = fh.read().splitlines()
    n_fields  = int(lines[1])
    time_line = 2 + n_fields + 1
    return float(lines[time_line])


def extract_centerline(pltfile, field="temp"):
    import yt
    yt.set_log_level("error")
    ds   = yt.load(str(pltfile))
    x_lo = float(ds.domain_left_edge[0].d)
    x_hi = float(ds.domain_right_edge[0].d)
    cz   = float(ds.domain_center[2].d) if ds.dimensionality == 2 else 0.0
    ray  = ds.ray([x_lo, 0.0, cz], [x_hi, 0.0, cz])
    order = np.argsort(ray["x"].d)
    return ray["x"].d[order] * 1e3, ray[("boxlib", field)].d[order]


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Temporal evolution of centerline temperature per solver"
    )
    parser.add_argument("--solvers", nargs="+", default=None,
                        help="Subset of solvers to plot (default: all discovered in results/)")
    parser.add_argument("--field", default="temp",
                        help="Plotfile field name (default: temp)")
    parser.add_argument("--every", type=int, default=1,
                        help="Plot every Nth plotfile to thin out crowded lines (default: 1)")
    parser.add_argument("--output", default=None,
                        help="Output PNG path (default: temporal_evolution.png)")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR),
                        help=f"Path to results/ directory (default: {RESULTS_DIR})")
    args = parser.parse_args()

    try:
        import yt  # noqa: F401
    except ImportError:
        print("ERROR: yt is required.  Install with:  pip install yt")
        sys.exit(1)

    results_dir = Path(args.results_dir)
    solvers     = args.solvers or discover_solvers(results_dir)

    if not solvers:
        print(f"No solver results found in {results_dir}")
        print("  Run at least one solver first, or pass --solvers explicitly.")
        sys.exit(1)

    print(f"Solvers found: {solvers}")

    # ── collect all profiles per solver ──────────────────────────────────────
    all_data = {}   # solver → list of (t_s, x_mm, T)

    for solver in solvers:
        solver_dir = results_dir / solver
        if not solver_dir.is_dir():
            print(f"  [skip] {solver}: {solver_dir} not found")
            continue

        plotfiles = find_plotfiles(solver_dir)
        if not plotfiles:
            print(f"  [skip] {solver}: no plotfiles found")
            continue

        # Apply --every thinning but always include first and last
        if args.every > 1:
            indices  = list(range(0, len(plotfiles), args.every))
            if (len(plotfiles) - 1) not in indices:
                indices.append(len(plotfiles) - 1)
            plotfiles = [plotfiles[i] for i in indices]

        print(f"\n  {solver}  ({len(plotfiles)} plotfiles)")
        profiles = []
        for pltfile in plotfiles:
            try:
                t_s = read_plotfile_time(pltfile)
                x_mm, T = extract_centerline(pltfile, field=args.field)
                profiles.append((t_s, x_mm, T))
                print(f"    {pltfile.name}  t = {t_s*1e3:7.2f} ms  T_max = {T.max():.0f} K")
            except Exception as exc:
                print(f"    {pltfile.name}  FAILED — {exc}")

        if profiles:
            all_data[solver] = profiles

    if not all_data:
        print("\nNo data loaded.")
        sys.exit(1)

    # ── figure ────────────────────────────────────────────────────────────────
    n_solvers = len(all_data)
    fig, axes = plt.subplots(
        n_solvers, 1,
        figsize=(9, 4 * n_solvers),
        sharex=True,
        gridspec_kw={"hspace": 0.35}
    )
    if n_solvers == 1:
        axes = [axes]

    for ax, (solver, profiles) in zip(axes, all_data.items()):
        times = np.array([p[0] for p in profiles])
        t_min, t_max = times.min(), times.max()

        # avoid divide-by-zero if only one plotfile
        norm = mcolors.Normalize(vmin=t_min * 1e3, vmax=max(t_max * 1e3, t_min * 1e3 + 1))

        for t_s, x_mm, T in profiles:
            color = CMAP(norm(t_s * 1e3))
            ax.plot(x_mm, T, color=color, lw=1.2, alpha=0.85)

        # colorbar on the right of each subplot
        sm = cm.ScalarMappable(cmap=CMAP, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, pad=0.02, fraction=0.03)
        cbar.set_label("Simulation time  (ms)", fontsize=10)
        cbar.ax.tick_params(labelsize=9)

        # Mark T_max trajectory as a faint dashed line connecting peaks
        peak_times = [p[0] * 1e3 for p in profiles]
        peak_temps = [p[2].max() for p in profiles]
        ax2 = ax.twinx()
        ax2.plot(peak_times, peak_temps, color="grey", ls="--", lw=1.0, alpha=0.5)
        ax2.set_ylabel("Peak T  (K)", fontsize=9, color="grey")
        ax2.tick_params(axis="y", labelcolor="grey", labelsize=9)

        # Reuse x-axis label trick: peak_times on ax2 is time, not position
        # Actually the twinx shares x incorrectly here — use a separate inset instead
        ax2.remove()

        # simpler: just annotate the T_max trend in the title
        t_start_ms = profiles[0][0]  * 1e3
        t_end_ms   = profiles[-1][0] * 1e3
        T_start    = profiles[0][2].max()
        T_end      = profiles[-1][2].max()
        trend      = "↑" if T_end > T_start + 5 else ("↓ quenching?" if T_end < T_start - 5 else "→ steady")

        ax.set_title(
            f"{solver}   |   "
            f"t = {t_start_ms:.1f} – {t_end_ms:.1f} ms   |   "
            f"T_max: {T_start:.0f} K → {T_end:.0f} K  {trend}",
            fontsize=11
        )
        ax.set_ylabel("Temperature  (K)", fontsize=11)
        ax.grid(True, alpha=0.25)
        ax.tick_params(labelsize=10)

    axes[-1].set_xlabel("x  (mm)", fontsize=11)

    # ── save ──────────────────────────────────────────────────────────────────
    outpath = Path(args.output) if args.output else CASE_DIR / "temporal_evolution.png"
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    print(f"\nSaved → {outpath}")


if __name__ == "__main__":
    main()
