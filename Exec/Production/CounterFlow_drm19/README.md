# CounterFlow_drm19 — Running on LONI QB2

2-D counterflow diffusion flame benchmark using the DRM19 methane mechanism.
See [`CASE_REPORT.md`](CASE_REPORT.md) for full physics documentation.

---

## Current status

- [x] Cold flow complete — steady-state flow field available in `results/coldflow/`
- [ ] Benchmark runs — submit with `submit_benchmark.py --benchmark`

---

## Prerequisites

A compiled executable must exist in this directory before submitting any jobs.

### Sync and build

```bash
# From local machine
bash ~/combustion_research/sync_to_cluster.sh

# On QB2
ssh qb2.loni.org
cd /work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19
source /work/elo/combustion_research/PeleLMeX/setup_env_loni.sh
make -j8
ls -lh PeleLMeX2d.gnu.MPI.ex   # confirm it exists
```

> **Changing the mechanism?**  
> `bash run_scripts/set_fuel.sh --fuel CH4 --mechanism drm19`  
> then `make realclean && make -j8`.

---

## Submitting benchmark runs

The cold flow is already done. Submit the 5 solver benchmark runs directly:

```bash
cd /work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19

# All 5 solvers, 2 nodes each (40 MPI tasks), default stop time from input file
python run_scripts/submit_benchmark.py --benchmark --nodes 2

# Run longer if the flame hasn't fully developed (recommended: 0.3–0.5 s)
python run_scripts/submit_benchmark.py --benchmark --nodes 2 --stop-time 0.5

# 4 nodes (80 tasks) for a faster run
python run_scripts/submit_benchmark.py --benchmark --nodes 4 --stop-time 0.5

# Single solver only
python run_scripts/submit_benchmark.py --benchmark --solver cvode_denseAJ --nodes 2 --stop-time 0.5
```

The script auto-detects the latest plotfile in `results/coldflow/` as the restart point.
To specify one explicitly:

```bash
python run_scripts/submit_benchmark.py --benchmark \
    --coldflow-plt results/coldflow/plt01234 \
    --nodes 2 --stop-time 0.5
```

> **Partition rules (QB2):**
> `--nodes 1` → `single` partition, `--nodes 2+` → `workq` partition.  
> This is handled automatically — no need to set it manually.

### Starting fresh (cold flow + benchmark in one command)

If you ever need to redo the cold flow:

```bash
python run_scripts/submit_benchmark.py --coldflow --then-benchmark --nodes 2 --stop-time 0.5
```

---

## Monitoring

```bash
squeue -u elo                          # current jobs
watch -n 30 squeue -u elo             # live view
tail -f logs/run_cvode_denseAJ.log    # follow a running solver
grep "STEP\|T_max\|Total" logs/run_cvode_denseAJ.log   # progress snapshot
```

---

## Plotting results

Requires `yt` and `matplotlib` (install once with `pip install --user yt matplotlib`):

```bash
# Centerline temperature — all solvers vs. initial cold flow profile
python run_scripts/plot_centerline.py

# Specific step
python run_scripts/plot_centerline.py --step 500

# Custom output path
python run_scripts/plot_centerline.py --output ~/my_plot.png

# Skip the cold flow reference line
python run_scripts/plot_centerline.py --no-coldflow
```

The plot is saved to `centerline_temp_latest.png` in the case directory. Copy it back:

```bash
scp qb2.loni.org:/work/elo/combustion_research/PeleLMeX/Exec/Production/CounterFlow_drm19/centerline_temp_latest.png .
```

---

## Collecting timing results

```bash
bash run_scripts/collect_timings.sh
```

Example output:

```
Solver               | Total Time (s)  | Steps
---------------------+-----------------+----------
cvode_dense          | 1842.3          | 500
cvode_denseAJ        | 1204.7          | 500
cvode_gmres          | 1531.8          | 500
```

Plotfiles and checkpoints are in `results/<solver>/`.

---

## Output structure

```
CounterFlow_drm19/
├── results/
│   ├── coldflow/          ← already done
│   ├── cvode_dense/
│   ├── cvode_denseAJ/
│   └── cvode_gmres/
└── logs/
    ├── run_cvode_dense.log
    ├── run_cvode_denseAJ.log
    ├── run_cvode_gmres.log
    └── slurm_logs/
```

---

## Troubleshooting

**Flame not fully developed** — resubmit with a longer stop time:
```bash
python run_scripts/submit_benchmark.py --benchmark --nodes 2 --stop-time 0.5
```

**Job fails immediately / executable not found**
```bash
ls PeleLMeX2d.gnu.MPI.ex
source /work/elo/combustion_research/PeleLMeX/setup_env_loni.sh
```

**Benchmark crashes at ignition** — ignition kernel may be too large for the grid.
Reduce `prob.ignition_SphRad` in the input files (currently 1.5 mm).

**CVODE diverges** — tighten tolerances in the relevant input file:
`ode.rtol = 1e-7`, `ode.atol = 1e-6`, or `cvode.max_order = 3`.

**Rerun a single solver**
```bash
python run_scripts/submit_benchmark.py --benchmark --solver rk64 --nodes 2 --stop-time 0.5
```
