#!/usr/bin/env python3
"""
PeleLMeX solver benchmark submission script.
Usage:
    # Submit cold flow first (1 node):
    python submit_benchmark.py --coldflow

    # Submit cold flow on 2 nodes:
    python submit_benchmark.py --coldflow --nodes 2

    # Submit all benchmark solvers (2 nodes each):
    python submit_benchmark.py --benchmark --nodes 2

    # Submit a specific solver only:
    python submit_benchmark.py --benchmark --solver cvode_denseAJ --nodes 4

    # Submit everything, chain benchmark after coldflow:
    python submit_benchmark.py --coldflow --then-benchmark --nodes 2

    # Override stop time (e.g. run longer to get a fully developed flame):
    python submit_benchmark.py --benchmark --stop-time 0.5

    # Chain with a longer stop time:
    python submit_benchmark.py --coldflow --then-benchmark --nodes 2 --stop-time 0.5
"""

import argparse
import subprocess
import glob
from pathlib import Path

# ============================================================
# Configuration — edit these paths
# ============================================================
CASE_DIR = Path("/ddnB/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_ndodecane")
RUN_SCRIPTS_DIR = CASE_DIR / "run_scripts"
RESULTS_DIR     = CASE_DIR / "results"
LOGS_DIR        = CASE_DIR / "logs" / "slurm_logs"
TEMPLATE_PATH   = RUN_SCRIPTS_DIR / "run_benchmark.slurm.template"
COLDFLOW_SLURM  = RUN_SCRIPTS_DIR / "run_coldflow.slurm"

# QB2 has 20 cores per node
CORES_PER_NODE = 20

SOLVERS = [
    "cvode_dense",
    "cvode_denseAJ",
    "cvode_gmres",
    "qss",
]

# ============================================================
# Helpers
# ============================================================
def partition_for(nodes):
    """
    QB2 partition rules:
      single  — 1 node only
      workq   — 2+ nodes (standard multi-node queue)
    """
    return "single" if nodes == 1 else "workq"


def render_template(template_path, replacements):
    """Fill {{KEY}} placeholders in a template string."""
    text = Path(template_path).read_text()
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def submit_job(script_content, job_name, dependency_job_id=None):
    """Write rendered script to logs dir and submit via sbatch."""
    script_path = LOGS_DIR / f"{job_name}.slurm"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_content)

    cmd = ["sbatch"]
    if dependency_job_id:
        cmd += [f"--dependency=afterok:{dependency_job_id}"]
    cmd.append(str(script_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR submitting {job_name}:\n{result.stderr}")
        return None

    job_id = result.stdout.strip().split()[-1]   # "Submitted batch job 12345"
    print(f"  Submitted {job_name} → job {job_id}")
    return job_id


def find_latest_coldflow_plt():
    """Find the most recent coldflow plotfile."""
    candidates = sorted(glob.glob(str(RESULTS_DIR / "coldflow" / "plt*")))
    return candidates[-1] if candidates else None


# ============================================================
# Actions
# ============================================================
def submit_coldflow(nodes):
    ntasks    = nodes * CORES_PER_NODE
    partition = partition_for(nodes)
    print(f"\n=== Submitting cold flow job ===")
    print(f"  {nodes} node(s) × {CORES_PER_NODE} cores = {ntasks} MPI tasks  [{partition}]")
    script = render_template(COLDFLOW_SLURM, {
        "CASE_DIR":   CASE_DIR,
        "NODES":      nodes,
        "NTASKS":     ntasks,
        "PARTITION":  partition,
    })
    return submit_job(script, "coldflow")


def submit_benchmark(nodes, solvers=None, coldflow_plt=None,
                     dependency_job_id=None, stop_time=None):
    if solvers is None:
        solvers = SOLVERS

    if coldflow_plt is None:
        coldflow_plt = find_latest_coldflow_plt()
        if coldflow_plt is None:
            print("ERROR: No coldflow plotfile found in results/coldflow/")
            print("  Run cold flow first: python submit_benchmark.py --coldflow")
            return

    # Build any command-line overrides to pass through to the AMReX executable.
    # These take precedence over values in the input file.
    extra_args_list = []
    if stop_time is not None:
        extra_args_list.append(f"amr.stop_time={stop_time}")
        # amr.max_step = 500 in the input files is a benchmark cap — clear it
        # when the user specifies a stop time so time is the only termination criterion.
        extra_args_list.append("amr.max_step=99999999")
    extra_args = " ".join(extra_args_list)

    ntasks    = nodes * CORES_PER_NODE
    partition = partition_for(nodes)
    print(f"\n=== Submitting benchmark jobs ===")
    print(f"  {nodes} node(s) × {CORES_PER_NODE} cores = {ntasks} MPI tasks  [{partition}]")
    print(f"  Cold flow restart: {coldflow_plt}")
    if stop_time is not None:
        print(f"  Stop time override: {stop_time} s  (amr.max_step cap removed)")
    print(f"  Solvers: {solvers}")

    job_ids = {}
    for solver in solvers:
        script = render_template(TEMPLATE_PATH, {
            "SOLVER_NAME":  solver,
            "CASE_DIR":     CASE_DIR,
            "COLDFLOW_PLT": coldflow_plt,
            "NODES":        nodes,
            "NTASKS":       ntasks,
            "PARTITION":    partition,
            "EXTRA_ARGS":   extra_args,
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
    parser.add_argument("--stop-time", type=float, default=None,
                        help="Override amr.stop_time (seconds) for benchmark runs. "
                             "Use this to run longer if the flame has not fully developed. "
                             "If not set, the value in the input file is used (0.150 s).")
    parser.add_argument("--nodes", type=int, default=2,
                        help="Number of nodes per job (default: 2). "
                             "Partition is chosen automatically: "
                             "single (1 node) or workq (2+ nodes).")
    args = parser.parse_args()

    if not args.coldflow and not args.benchmark:
        parser.print_help()
        return

    coldflow_job_id = None

    if args.coldflow:
        coldflow_job_id = submit_coldflow(nodes=args.nodes)

    if args.benchmark:
        solvers    = [args.solver] if args.solver else None
        dependency = coldflow_job_id if args.then_benchmark else None
        submit_benchmark(
            nodes=args.nodes,
            solvers=solvers,
            coldflow_plt=args.coldflow_plt,
            dependency_job_id=dependency,
            stop_time=args.stop_time,
        )
    elif args.then_benchmark and coldflow_job_id:
        # --coldflow --then-benchmark without --benchmark: chain automatically
        submit_benchmark(nodes=args.nodes, dependency_job_id=coldflow_job_id,
                         stop_time=args.stop_time)


if __name__ == "__main__":
    main()
