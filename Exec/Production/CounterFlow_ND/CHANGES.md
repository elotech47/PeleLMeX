# CounterFlow_ND — Changes and Implementation Notes

## Overview

Three features were added to the CounterFlow_ND case, plus a review and
correction of the run scripts. All changes were made to support the n-dodecane
(NC12H26) counterflow diffusion flame benchmark study.

---

## 1. Config-Driven Input File Management

### Problem
Six sets of input files (3 solvers × local + HPC) share many identical
physical and numerical parameters. Changing a single setting (e.g. massflow or
AMR level) required editing all files manually.

### Solution: `inputs/case_config.cfg` + `run_scripts/configure_inputs.py`

**`inputs/case_config.cfg`** holds all shared parameters in three sections:

| Section    | Applied to                            |
|------------|---------------------------------------|
| `[shared]` | ALL input files                       |
| `[local]`  | Only `input.*_local` files            |
| `[hpc]`    | All other input files (cluster runs)  |

**`run_scripts/configure_inputs.py`** propagates the config to every
`inputs/input.*` file in place:

```bash
# Preview what would change (dry run):
python run_scripts/configure_inputs.py

# Apply changes to all files:
python run_scripts/configure_inputs.py --apply

# Apply only to one file:
python run_scripts/configure_inputs.py --apply --file input.adaptive_local

# Apply only the shared section:
python run_scripts/configure_inputs.py --apply --section shared
```

The script uses regex to find and update parameter values while preserving
all existing comments and solver-specific sections.

### What is managed by the config

**`[shared]`** — physical conditions, flow rates, ignition kernel, AMR grid
size, CFL, timestep ramp, SDC iterations, ODE tolerances, projection tolerances.

**`[local]`** — `amr.max_level = 0`, `amr.gradT.max_level = 0`, `peleLM.v = 2`
(no AMR for quick local tests)

**`[hpc]`** — `amr.max_level = 2`, `amr.gradT.max_level = 2`, `peleLM.v = 3`

**Not managed** (edit per-file): `amr.stop_time`, `amr.plot_per`, `amr.check_int`,
`amr.max_step`, all solver-specific params (`cvode.*`, `qss.*`, `adaptive.*`).

> **Note**: The coldflow input files (`input.coldflow`, `input.coldflow_cvode`)
> are also updated by the script. The `amr.max_level = 2` from `[hpc]` will be
> applied to them as well. If you prefer to keep AMR off for cold flow, run:
> `python run_scripts/configure_inputs.py --apply --section shared` which skips
> the hpc/local level overrides.

---

## 2. CPU Time Tracking Per Step

### Problem
Only total wall-clock time was available from the run logs. No per-step
breakdown existed, making it impossible to plot cost-per-step or identify
where time was spent (chemistry vs flow).

### Solution: `run_scripts/parse_timings.py`

Parses a PeleLMeX run log and writes `results/<solver>/timings.csv` with:

| Column | Description |
|---|---|
| `step` | AMReX timestep number |
| `sim_time` | Simulation time at start of step (s) |
| `dt` | Timestep size (s) |
| `advance_wall_time` | Wall time for the full Advance() call (s) |
| `reaction_wall_time` | Wall time in ScalarReaction() (sum over SDC iters, s) |
| `cumulative_wall_time` | Running total of advance_wall_time (s) |

```bash
# Parse one log:
python run_scripts/parse_timings.py logs/local_logs/run_adaptive.log

# Parse all logs in logs/local_logs/:
python run_scripts/parse_timings.py --all
```

**Integration with `run_local.sh`**: The parser is called automatically at the
end of each run (and also on partial logs if the run fails), so
`results/<solver>/timings.csv` is always up to date after a run.

**Integration with `plot_centerline.py`**: If `timings.csv` exists, the timing
bar chart now shows the reaction fraction (`rxn%`) on each bar:
```
adaptive   286.8 s  (533 steps)  rxn=64%
```

**Integration with `collect_timings.sh`**: Updated to use `timings.csv` for the
reaction fraction column and to use self-resolving relative paths.

---

## 3. Per-Cell Solver Choice in Plotfiles (Adaptive Integrator)

### Problem
When using `ReactorAdaptive`, there was no way to tell from the plotfiles which
cells used QSS vs CVODE. This prevented spatial analysis of solver routing.

### Solution: Encoded in `FunctCallFab`

**Files modified:**
- `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.cpp`
- `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.H`

The `FunctCallFab` field written to every plotfile now encodes solver choice:

| Value | Meaning |
|---|---|
| `-1.0` | QSS used (primary reactor, successful) |
| `0.0` | Cell was masked (EB-covered), no chemistry run |
| `> 0.0` | CVODE used; value = number of RHS function evaluations |

**Loading in post-processing:**
```python
import yt
ds = yt.load("results/adaptive/plt00500")
# Load the solver-choice field:
solver_flag = ds.all_data()[("boxlib", "FunctCallFab")]
qss_mask   = solver_flag < 0    # QSS cells
cvode_mask = solver_flag > 0    # CVODE cells
```

To overlay on temperature:
```python
import yt; import numpy as np
ds  = yt.load("plt00500")
slc = yt.SlicePlot(ds, "z", "temp")
slc.annotate_contour(("boxlib", "FunctCallFab"), ncont=1, clim=(0, 0))
slc.save()
```

**Requires recompilation** of `PelePhysics` after this change:
```bash
make -j$(nproc)
```

---

## 4. Run Scripts — Bugs Fixed

| File | Issue | Fix |
|---|---|---|
| `submit_benchmark.py` | `CASE_DIR` pointed to `CounterFlow_drm19` | Changed to `CounterFlow_ND` |
| `collect_timings.sh` | Hardcoded path to DRM19 case; missing reaction fraction | Rewritten with relative paths, per-step reaction fraction from CSV |
| `set_fuel.sh` | Referenced `input.2d-regt` (not present in ND case) | Removed `ROOT_INPUTS` array |
| `set_ignition.sh` | Same non-existent file reference | Removed `ROOT_INPUTS` array |
| `run_local.sh` | No per-step timing capture | Added `parse_timings.py` call after each run |

---

## Files Changed Summary

```
inputs/
  case_config.cfg                [NEW]  Central config for all shared params

run_scripts/
  configure_inputs.py            [NEW]  Propagate config → all input files
  parse_timings.py               [NEW]  Extract per-step CPU time → CSV
  run_local.sh                   [MOD]  Auto-parse timings after each run
  submit_benchmark.py            [MOD]  Fixed CASE_DIR (was CounterFlow_drm19)
  collect_timings.sh             [MOD]  Relative paths + reaction fraction
  set_fuel.sh                    [MOD]  Removed ROOT_INPUTS (non-existent files)
  set_ignition.sh                [MOD]  Same

Submodules/PelePhysics/Source/Reactions/
  ReactorAdaptive.cpp            [MOD]  FunctCallFab encodes QSS (-1) vs CVODE (nfe)
  ReactorAdaptive.H              [MOD]  Documented FC_in encoding
```

---

## Quick Reference

```bash
# 1. Edit parameters in one place:
vim inputs/case_config.cfg

# 2. Propagate to all input files:
python run_scripts/configure_inputs.py --apply

# 3. Run a local benchmark:
bash run_scripts/run_local.sh --np 4 --coldflow --then-solver cvode_denseAJ

# 4. View timing summary:
bash run_scripts/collect_timings.sh

# 5. Submit HPC benchmark:
python run_scripts/submit_benchmark.py --benchmark --nodes 2
```
