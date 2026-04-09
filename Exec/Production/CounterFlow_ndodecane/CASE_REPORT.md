# Counterflow Diffusion Flame — Case Report

**Solver:** PeleLMeX (low-Mach AMR combustion solver)  
**Case:** 2-D axisymmetric counterflow diffusion flame  
**Mechanism:** DRM19 (19 species, 84 reactions — reduced methane/air mechanism)  
**Purpose:** Benchmark comparison of chemistry ODE integrators (CVODE variants vs. RK64)

---

## 1. Physical Problem

A counterflow diffusion flame is established by directing opposing jets of fuel and oxidizer toward
each other. Mixing occurs near the stagnation plane at the domain center, and the flame anchors
at the stoichiometric mixture fraction surface on the oxidizer side. This configuration is a
canonical test for turbulent combustion modeling because it isolates the effects of strain rate
and scalar dissipation rate on flame structure and extinction.

```
      Fuel jet (CH4, 450 K)
           ↓  ↓  ↓
  ─────────────────────────  y = +7.5 mm
  |                       |
  |     flame sheet       |
  |   ─ ─ ─ ─ ─ ─ ─ ─    |  y ≈ 0 (stagnation plane)
  |                       |
  ─────────────────────────  y = −7.5 mm
           ↑  ↑  ↑
      Oxidizer jet (air, 450 K)
```

---

## 2. Domain and Grid

| Parameter              | Value                                       |
|------------------------|---------------------------------------------|
| Geometry               | 2-D Cartesian                               |
| Domain (x)             | −7.5 mm to +7.5 mm                          |
| Domain (y)             | −7.5 mm to +7.5 mm                          |
| Boundary conditions    | Inflow (lo-x, hi-x) / Outflow (lo-y, hi-y) |
| Base grid              | 64 × 64 cells                               |
| Base cell size Δx₀     | ≈ 234 μm                                    |
| AMR levels (reacting)  | 2 refinement levels (ref_ratio = 2)         |
| Finest cell size Δx    | ≈ 58 μm                                     |
| AMR levels (cold flow) | 0 (uniform grid)                            |
| Refinement criterion   | `gradT > 100 K` up to level 2              |

---

## 3. Operating Conditions

| Parameter             | Value                          | Notes                            |
|-----------------------|--------------------------------|----------------------------------|
| Mean pressure         | 792,897.5 Pa (≈ 7.83 atm)      | High-pressure operating point    |
| Fuel                  | Pure CH4 (Y_CH4 = 1.0)         | No dilution                      |
| Oxidizer              | Air (O2: 23.3%, N2: 76.7% wt.) |                                  |
| Fuel inlet temp       | 450 K                          | Both streams preheated           |
| Oxidizer inlet temp   | 450 K                          |                                  |
| Inert (co-flow) temp  | 450 K                          |                                  |
| Fuel mass flux        | 2.228 kg/m²·s                  | Applied over jet_radius = 2.5 mm |
| Oxidizer mass flux    | 0.9171 kg/m²·s                 |                                  |
| Fuel co-flow velocity | 0.0617 m/s                     | Outside jet_radius               |
| Oxidizer co-flow vel. | 0.1500 m/s                     |                                  |
| Jet radius            | 2.5 mm                         |                                  |
| Stoich. mixture frac. | Z_st (CH4/air, Bilger)         | ≈ 0.055                          |

---

## 4. Chemistry

| Parameter   | Value                                                  |
|-------------|--------------------------------------------------------|
| Mechanism   | DRM19                                                  |
| Species     | 19 (CH4, O2, N2, H2O, CO2, CO, H2, OH, H, O, HO2, H2O2, CH3, CH2O, CH3OH, C2H2, C2H4, C2H6, AR) |
| Reactions   | 84                                                     |
| EOS         | Fuego (ideal gas)                                      |
| Transport   | Simple (mixture-averaged)                              |
| Wbar term   | Enabled (`peleLM.use_wbar = 1`)                        |
| SDC iters   | 2 (`peleLM.sdc_iterMax = 2`)                           |

---

## 5. Run Sequence

### Stage 1 — Cold flow (no chemistry)

The flow field is developed without reactions to produce a steady-state velocity and species
distribution. This plotfile is used to hot-start every benchmark run.

| Parameter        | Value          |
|------------------|----------------|
| Input file       | `inputs/input.coldflow` |
| `do_ignition`    | 0 (off)        |
| AMR levels       | 0 (uniform)    |
| `stop_time`      | 0.500 s        |
| `init_dt`        | 1.0 × 10⁻⁶ s  |
| `dt_shrink`      | 0.01           |
| `cfl`            | 0.1            |
| Chemistry        | ReactorCvode / denseAJ_direct |
| Output           | `results/coldflow/plt*` |

### Stage 2 — Reacting benchmark runs

Each benchmark run restarts from the cold flow plotfile, applies an ignition kernel, and advances
for 500 steps. Timing data is captured in `logs/run_<solver>.log`.

| Parameter           | Value                              |
|---------------------|------------------------------------|
| Input files         | `inputs/input.<solver>`            |
| `do_ignition`       | 1                                  |
| Ignition kernel T   | 1000 K                             |
| Ignition kernel R   | 1.5 mm                             |
| Restart from        | Latest `results/coldflow/plt*`     |
| AMR levels          | 2                                  |
| `max_step`          | 500                                |
| `stop_time`         | 0.150 s                            |
| `plot_per`          | 0.005 s (every 5 ms)               |
| `init_dt`           | 1.0 × 10⁻⁶ s                      |
| `cfl`               | 0.1                                |
| Projector rtol      | 1.0 × 10⁻¹⁰                       |

---

## 6. Solver Variants Being Benchmarked

| Input file            | Integrator     | Linear solver    | Notes                          |
|-----------------------|----------------|------------------|--------------------------------|
| `input.cvode_dense`   | ReactorCvode   | dense_direct     | Full dense Jacobian            |
| `input.cvode_denseAJ` | ReactorCvode   | denseAJ_direct   | Analytical Jacobian (default)  |
| `input.cvode_gmres`   | ReactorCvode   | GMRES            | Iterative Krylov solver        |

> `cvode_sparse` (KLU) and `rk64` were removed — both failed to run for this case.

Common ODE tolerances across all variants: `rtol = 1e-6`, `atol = 1e-5`.

---

## 7. Output and Diagnostics

| Output                    | Location                         | Frequency        |
|---------------------------|----------------------------------|------------------|
| Plotfiles                 | `results/<solver>/plt*`          | Every 5 ms       |
| Checkpoints               | `results/<solver>/chk*`          | Every 2000 steps |
| Temporal integrals        | `results/<solver>/temporals/`    | Every step       |
| Mass balance              | `results/<solver>/temporals/`    | Every step       |
| Run log (timing)          | `logs/run_<solver>.log`          | Continuous       |
| Cold flow log             | `logs/coldflow.log`              | Continuous       |
| SLURM stdout/err          | `logs/slurm_logs/`               | Per job          |

Derived quantities written to plotfiles: `avg_pressure`, `mag_vort`, `mass_fractions`, `mixture_fraction`.

---

## 8. Key Files

```
CounterFlow_drm19/
├── GNUmakefile                       build configuration (Chemistry_Model = drm19)
├── pelelmex_prob.H / .cpp            problem-specific initialization
├── drm_CH4Air_stoich.dat             stoichiometric data file
├── inputs/
│   ├── input.coldflow                cold flow (no chemistry, no AMR)
│   ├── input.cvode_dense             benchmark: CVODE + dense Jacobian
│   ├── input.cvode_denseAJ           benchmark: CVODE + analytical Jacobian
│   ├── input.cvode_sparse            benchmark: CVODE + KLU sparse
│   ├── input.cvode_gmres             benchmark: CVODE + GMRES
│   └── input.rk64                   benchmark: explicit RK64
└── run_scripts/
    ├── set_fuel.sh                   update fuel/mechanism everywhere
    ├── submit_benchmark.py           SLURM job submission
    ├── run_coldflow.slurm            cold flow job script
    ├── run_benchmark.slurm.template  benchmark job template
    └── collect_timings.sh            parse timing from logs
```

---

## 9. Changing Fuel or Mechanism

To switch the fuel species and/or chemistry mechanism across all input files and `GNUmakefile`:

```bash
bash run_scripts/set_fuel.sh --fuel CH4 --mechanism drm19
```

A mechanism change requires a full rebuild: `make realclean && make -j8`.
