# CounterFlow_drm19 — Running on LONI QB2

This is a 2-D counterflow diffusion flame benchmark using the DRM19 methane mechanism.
See [`CASE_REPORT.md`](CASE_REPORT.md) for full physics documentation.

---

## Prerequisites

Before submitting any jobs, you need a compiled executable in this directory.

### 1. Sync the repo to the cluster

From your local machine:

```bash
bash ~/combustion_research/sync_to_cluster.sh
```

### 2. Build on the cluster

SSH into QB2 and build:

```bash
ssh qb2.loni.org
cd /ddnB/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19
source ~/combustion_research/PeleLMeX/setup_env_loni.sh
make -j8
```

The executable will be `PeleLMeX2d.gnu.MPI.ex`. Confirm it exists before submitting jobs:

```bash
ls -lh PeleLMeX2d.gnu.MPI.ex
```

> **Changing the mechanism?** Run `bash run_scripts/set_fuel.sh --fuel CH4 --mechanism drm19`
> then `make realclean && make -j8` before submitting.

---

## Running the Benchmark

The benchmark has two stages: (1) develop the cold flow field, (2) restart from it with
each chemistry solver. The `submit_benchmark.py` script handles both.

### Option A — Submit everything in one command (recommended)

This submits the cold flow job and chains all 5 benchmark jobs to start automatically
after it finishes. The `--nodes` flag controls how many nodes each job gets; the
partition (`single` vs `workq`) is chosen automatically.

```bash
cd /ddnB/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19

# 2 nodes each (40 MPI tasks) — workq partition
python run_scripts/submit_benchmark.py --coldflow --then-benchmark --nodes 2

# 4 nodes each (80 MPI tasks)
python run_scripts/submit_benchmark.py --coldflow --then-benchmark --nodes 4

# Single node (20 tasks) — stays on the single partition
python run_scripts/submit_benchmark.py --coldflow --then-benchmark --nodes 1
```

> **Partition rules (QB2):**
> - `--nodes 1` → `single` partition
> - `--nodes 2+` → `workq` partition

### Option B — Submit stages manually

**Step 1:** Submit cold flow only:

```bash
python run_scripts/submit_benchmark.py --coldflow --nodes 2
```

Wait for it to finish (`squeue -u elo`), then find the final plotfile:

```bash
ls -dt results/coldflow/plt* | head -1
```

**Step 2:** Submit all benchmark solvers (auto-detects the latest cold flow plotfile):

```bash
python run_scripts/submit_benchmark.py --benchmark --nodes 4
```

Or submit a specific solver only:

```bash
python run_scripts/submit_benchmark.py --benchmark --solver cvode_denseAJ --nodes 2
```

Or pass the plotfile path explicitly:

```bash
python run_scripts/submit_benchmark.py --benchmark --coldflow-plt results/coldflow/plt01234 --nodes 4
```

---

## Monitoring Jobs

```bash
# Show your running/pending jobs
squeue -u elo

# Watch them live
watch -n 30 squeue -u elo

# Tail a running log
tail -f logs/run_cvode_denseAJ.log

# Check cold flow progress
tail -f logs/coldflow.log
```

---

## Collecting Results

Once benchmark jobs finish, extract wall-clock timing from all logs:

```bash
bash run_scripts/collect_timings.sh
```

Example output:

```
Solver               | Total Time (s)  | Steps
---------------------+-----------------+----------
cvode_dense          | 1842.3          | 500
cvode_denseAJ        | 1204.7          | 500
cvode_sparse         | 987.1           | 500
cvode_gmres          | 1531.8          | 500
rk64                 | 623.4           | 500
```

Plotfiles and checkpoints are in `results/<solver>/`.

---

## Output Structure After a Full Run

```
CounterFlow_drm19/
├── results/
│   ├── coldflow/
│   │   ├── plt00000, plt00010, ...    cold flow plotfiles
│   │   └── chk00000, ...             checkpoints
│   ├── cvode_dense/
│   │   ├── plt00000, ...
│   │   └── chk00000, ...
│   ├── cvode_denseAJ/  ...
│   ├── cvode_sparse/   ...
│   ├── cvode_gmres/    ...
│   └── rk64/           ...
└── logs/
    ├── coldflow.log
    ├── run_cvode_dense.log
    ├── run_cvode_denseAJ.log
    ├── run_cvode_sparse.log
    ├── run_cvode_gmres.log
    ├── run_rk64.log
    └── slurm_logs/
        ├── pelelm_coldflow_<jobid>.out
        └── pelelm_bench_<solver>_<jobid>.out
```

---

## Troubleshooting

**Job fails immediately / executable not found**
```bash
ls PeleLMeX2d.gnu.MPI.ex   # must exist
source setup_env_loni.sh    # reload environment
```

**Cold flow didn't reach steady state**
Increase `stop_time` in `inputs/input.coldflow` (default 0.500 s) and resubmit.
Check convergence in Paraview by looking at the velocity field over time.

**Benchmark crashes at ignition**
The ignition kernel (`ignition_SphT = 1000 K`, `ignition_SphRad = 1.5 mm`) may be too large
relative to the grid. Try reducing `prob.ignition_SphRad` in the input files.

**CVODE solver diverges**
Tighten tolerances: `ode.rtol = 1e-7`, `ode.atol = 1e-6`, or reduce `cvode.max_order = 3`.

**Need to rerun a single solver**
```bash
python run_scripts/submit_benchmark.py --benchmark --solver rk64
```

---

## Updating the Fuel or Mechanism

To switch fuel species and chemistry mechanism everywhere at once:

```bash
bash run_scripts/set_fuel.sh --fuel CH4 --mechanism drm19
# Then rebuild if mechanism changed:
make realclean && make -j8
```
