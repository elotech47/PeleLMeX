#!/usr/bin/env python3
"""
PeleLMeX solver benchmark submission script.
Usage:
    # Submit cold flow first:
    python submit_benchmark.py --coldflow

    # After cold flow finishes, submit all benchmark solvers:
    python submit_benchmark.py --benchmark

    # Submit a specific solver only:
    python submit_benchmark.py --benchmark --solver cvode_denseAJ

    # Submit benchmark after coldflow job completes (SLURM dependency):
    python submit_benchmark.py --coldflow --then-benchmark
"""

import argparse
import os
import subprocess
import glob
from pathlib import Path

# ============================================================
# Configuration — edit these paths
# ============================================================
CASE_DIR = Path("/ddnB/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19")
RUN_SCRIPTS_DIR = CASE_DIR / "run_scripts"
RESULTS_DIR = CASE_DIR / "results"
LOGS_DIR = CASE_DIR / "logs" / "slurm_logs"
TEMPLATE_PATH = RUN_SCRIPTS_DIR / "run_benchmark.slurm.template"
COLDFLOW_SLURM = RUN_SCRIPTS_DIR / "run_coldflow.slurm"

SOLVERS = [
    "cvode_dense",
    "cvode_denseAJ",
    "cvode_sparse",
    "cvode_gmres",
    "rk64",
]

# ============================================================
# Helpers
# ============================================================
def render_template(template_path, replacements):
    """Fill {{KEY}} placeholders in a template string."""
    text = Path(template_path).read_text()
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def submit_job(script_content, job_name, dependency_job_id=None):
    """Write script to a temp file and submit via sbatch."""
    script_path = LOGS_DIR / f"{job_name}.slurm"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_content)

    cmd = ["sbatch"]
    if dependency_job_id:
        cmd += [f"--dependency=afterok:{dependency_job_id}"]
    cmd.append(str(script_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR submitting {job_name}:\n{result.stderr}")
        return None

    # sbatch output: "Submitted batch job 12345"
    job_id = result.stdout.strip().split()[-1]
    print(f"  Submitted {job_name} → job {job_id}")
    return job_id


def find_latest_coldflow_plt():
    """Find the most recent coldflow plotfile."""
    pattern = str(RESULTS_DIR / "coldflow" / "plt*")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        return None
    return candidates[-1]


# ============================================================
# Actions
# ============================================================
def submit_coldflow():
    """Submit the cold flow job."""
    print("\n=== Submitting cold flow job ===")
    script = render_template(COLDFLOW_SLURM, {
        "CASE_DIR": CASE_DIR,
    })
    job_id = submit_job(script, "coldflow")
    return job_id


def submit_benchmark(solvers=None, coldflow_plt=None, dependency_job_id=None):
    """Submit benchmark jobs for each solver."""
    if solvers is None:
        solvers = SOLVERS

    # Auto-detect coldflow plotfile if not specified
    if coldflow_plt is None:
        coldflow_plt = find_latest_coldflow_plt()
        if coldflow_plt is None:
            print("ERROR: No coldflow plotfile found in results/coldflow/")
            print("  Run cold flow first: python submit_benchmark.py --coldflow")
            return

    print(f"\n=== Submitting benchmark jobs ===")
    print(f"  Cold flow restart: {coldflow_plt}")
    print(f"  Solvers: {solvers}")

    job_ids = {}
    for solver in solvers:
        script = render_template(TEMPLATE_PATH, {
            "SOLVER_NAME": solver,
            "CASE_DIR": CASE_DIR,
            "COLDFLOW_PLT": coldflow_plt,
        })
        job_id = submit_job(
            script,
            job_name=f"bench_{solver}",
            dependency_job_id=dependency_job_id,
        )
        if job_id:
            job_ids[solver] = job_id

    print(f"\nSubmitted {len(job_ids)} benchmark jobs.")
    print("Monitor with: squeue -u elo")
    return job_ids


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="PeleLMeX solver benchmark scheduler")
    parser.add_argument("--coldflow", action="store_true",
                        help="Submit the cold flow job")
    parser.add_argument("--benchmark", action="store_true",
                        help="Submit benchmark solver jobs")
    parser.add_argument("--solver", type=str, default=None,
                        help="Submit a specific solver only (e.g. cvode_denseAJ)")
    parser.add_argument("--coldflow-plt", type=str, default=None,
                        help="Path to coldflow plotfile to restart from")
    parser.add_argument("--then-benchmark", action="store_true",
                        help="Auto-submit benchmark after coldflow finishes (SLURM dependency)")
    args = parser.parse_args()

    if not args.coldflow and not args.benchmark:
        parser.print_help()
        return

    coldflow_job_id = None

    if args.coldflow:
        coldflow_job_id = submit_coldflow()

    if args.benchmark:
        solvers = [args.solver] if args.solver else None
        dependency = coldflow_job_id if args.then_benchmark else None
        submit_benchmark(
            solvers=solvers,
            coldflow_plt=args.coldflow_plt,
            dependency_job_id=dependency,
        )
    elif args.then_benchmark and coldflow_job_id:
        # --coldflow --then-benchmark: chain automatically
        submit_benchmark(dependency_job_id=coldflow_job_id)


if __name__ == "__main__":
    main()
