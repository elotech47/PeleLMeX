# Adaptive Chemistry Integrator — Design & Implementation Tracker

## Status

| Component | Status | Notes |
|-----------|--------|-------|
| `ReactorAdaptive.H` | ✅ Done | `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.H` |
| `ReactorAdaptive.cpp` | ✅ Done | `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.cpp` |
| `ReactorBase.H` — make `set_typ_vals_ode` virtual | ✅ Done | Line 82 — backward-compatible |
| `Make.package` — register new sources | ✅ Done | `ReactorAdaptive.H` + `.cpp` added to both lines |
| `input.adaptive` | ✅ Done | `Exec/Production/CounterFlow_drm19/inputs/input.adaptive` |
| `input.adaptive_local` | ✅ Done | `Exec/Production/CounterFlow_drm19/inputs/input.adaptive_local` |

---

## 1. Motivation

PeleLMeX currently assigns a single chemistry integrator to every cell in the
domain for the entire run. QSS and ARKODE (explicit) are fast but fail in
high-stiffness regions. CVODE (implicit BDF) is robust everywhere but
expensive. The observations that motivate adaptive selection:

- Non-reacting / cold cells → mild stiffness → QSS succeeds, CVODE is overkill
- Ignition kernel / flame cells → high stiffness → only CVODE converges

The adaptive integrator evaluates a thermophysical condition per cell at each
timestep and routes the cell to the appropriate integrator.

**Phase 1 scope (this implementation):** QSS (primary) + CVODE (fallback),
combined temperature + species condition, CPU-only.

---

## 2. Architecture

```
PeleLMeX_Reactions.cpp
  └─ m_reactor->react(box, rY, rYsrc, T, rEner, rEner_src, FC, mask, dt, time)
        │
        ▼
  ReactorAdaptive::react(box, ...)           ← lives in PelePhysics
        │
        ├─ [1] amrex::LoopOnCpu over all cells in box
        │         evaluate condition(T_cell, Y_species_cell) per cell
        │
        ├─ [2] For each cell: pack into a 1-cell buffer via box_flatten<YCOrder>
        │         (recomputes T from energy for consistency)
        │
        ├─ [3] Call  m_primary->react(buf, ncells=1)   — QSS
        │       OR   m_fallback->react(buf, ncells=1)  — CVODE
        │         (ncells=1 guarantees YCOrder == CYOrder, works for any reactor)
        │
        └─ [4] Unpack: direct copy back to Array4
                (1D react already applied energy source and recomputed T)
```

**Why per-cell (ncells=1) calls rather than batching?**

ReactorCvode uses `CYOrder` (species-major) internally; ReactorQSS uses
`YCOrder` (cell-major). For `ncells=1` both orderings produce the same flat
layout, so a single pack format works for any sub-reactor. Batching (Phase 2)
would need ordering-aware repacking or a transposition step.

**Why no mask-based routing?**

ReactorQSS and ReactorArkode ignore the `mask` parameter entirely.
ReactorCvode uses it only for EB-covered cells (mask == -1). There is no way
to use existing mask semantics to route cells between two sub-reactors. The
per-cell classify-and-dispatch loop is the correct approach.

---

## 3. Condition System

```
Condition TRUE  → primary (QSS)   — fast, handles easy chemistry
Condition FALSE → fallback (CVODE) — robust, handles stiff chemistry

Condition types (adaptive.condition_type):
  "temperature" : T_cell < T_threshold
  "species"     : Y_species_cell < Y_threshold
  "combined"    : (T_cell < T_threshold) AND/OR (Y_species_cell < Y_threshold)
                  controlled by adaptive.condition_logic = "AND" | "OR"
```

**Physical rationale for CH4/air counterflow at 7.8 atm:**
- `T < 1200 K` and `Y_OH < 1e-6` → inert mixing / preheat → QSS
- `T ≥ 1200 K` or `Y_OH ≥ 1e-6` → reacting / flame → CVODE

Both thresholds are user-tunable in the input file.

---

## 4. Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.H` | **Create** | Class declaration |
| `Submodules/PelePhysics/Source/Reactions/ReactorAdaptive.cpp` | **Create** | Implementation |
| `Submodules/PelePhysics/Source/Reactions/ReactorBase.H` | **Modify** | Add `virtual` to `set_typ_vals_ode` |
| `Submodules/PelePhysics/Source/Reactions/Make.package` | **Modify** | Add new sources to GNUmake build |
| `Exec/Production/CounterFlow_drm19/inputs/input.adaptive` | **Create** | Cluster input file |
| `Exec/Production/CounterFlow_drm19/inputs/input.adaptive_local` | **Create** | Local input file |

---

## 5. Input File Parameters

```ini
peleLM.chem_integrator = "ReactorAdaptive"
peleLM.use_typ_vals_chem = 1

# Sub-reactors
adaptive.primary_integrator  = "ReactorQSS"    # fast explicit — handles cold cells
adaptive.fallback_integrator = "ReactorCvode"  # implicit BDF — handles flame cells

# Condition (TRUE → primary, FALSE → fallback)
adaptive.condition_type  = "combined"           # temperature | species | combined
adaptive.condition_logic = "AND"                # AND | OR  (combined only)
adaptive.T_threshold     = 1200.0               # K:  T < threshold → primary
adaptive.species_name    = "OH"                 # radical indicator of active flame
adaptive.Y_threshold     = 1.0e-6              # mass fraction: Y < threshold → primary

# Verbosity (0=quiet, 1=per-box stats, 2=per-cell)
adaptive.verbose = 0

# Tolerances passed to both sub-reactors
ode.rtol = 1.0e-6
ode.atol = 1.0e-5

# QSS-specific (read by ReactorQSS::init)
qss.epsmax = 20.0
qss.epsmin = 1.0e-2
qss.dtmin  = 1.0e-20
qss.dtmax  = 1.0e-6
qss.itermax = 2
qss.tfd    = 1.000008
qss.abstol = 1.0e-11
qss.Tmax   = 3000.0
qss.stability_check = 1

# CVODE-specific (read by ReactorCvode::init)
cvode.solve_type = denseAJ_direct
cvode.max_order  = 4
```

---

## 6. How to Run

```bash
# First ensure coldflow results exist:
bash run_scripts/run_local.sh --np 4 --coldflow

# Then run the adaptive integrator:
bash run_scripts/run_local.sh --np 4 --solver adaptive
```

The script auto-selects `input.adaptive_local` over `input.adaptive`.

---

## 7. Key Implementation Details

### Factory registration
`ReactorAdaptive` extends `ReactorBase::Register<ReactorAdaptive>` and
provides `static std::string identifier() { return "ReactorAdaptive"; }`.
No changes to ReactorBase.cpp are needed — CRTP handles auto-registration.

### `set_typ_vals_ode` virtual
PeleLMeX calls `m_reactor->set_typ_vals_ode(typical_values)` through a
`ReactorBase*`. Since this method is not virtual in the base class, a plain
override in `ReactorAdaptive` would never be called. Making it `virtual` in
`ReactorBase.H` is a backward-compatible one-line fix; all existing reactors
inherit the default implementation from `ReactorBase.cpp` unchanged.

### Species index resolution
The species name (e.g., "OH") is resolved to an index in `set_eos_parm()`,
which is called after `init()` once the EOS parameters are available.

### Data layout for 1-cell calls
With `ncells=1`:
- `YCOrder`: `vec_index(s, 0, 1) = 0*(NS+1) + s = s`
- `CYOrder`: `vec_index(s, 0, 1) = s*1 + 0   = s`

Identical layout — the per-cell approach avoids ordering mismatches between
QSS (YCOrder) and CVODE (CYOrder) at zero cost.

### Energy consistency after 1D react
Both QSS and CVODE 1D `react()` leave the buffer in the state:
- `rY_buf[s]` = updated rhoY_s
- `rY_buf[NUM_SPECIES]` = updated T (recomputed from energy + species)
- `rX_buf[0]` = updated energy (original + dt * energy_src)

The unpack is therefore a direct copy with no further EOS call needed.

### `clean_init_massfrac` not supported
The correction applied in `box_unflatten` when `clean_init_massfrac=1`
requires knowledge of the pre-clipped rhoY. Since the 1D react interface
does not expose this, the correction is skipped. Use the default
`ode.clean_init_massfrac = 0`.

---

## 8. Known Limitations (Phase 1)

| Limitation | Notes |
|------------|-------|
| CPU-only | `amrex::LoopOnCpu` — per-cell loop defeats GPU batching |
| No failure-mode fallback | Condition-based only; no retry if QSS fails in a cell |
| No batching | ncells=1 calls; each cell has individual reactor init overhead |
| `clean_init_massfrac` ignored | Document and keep default=0 in inputs |
| Diagnostic counters | Per-box stats only; no global accumulated count |

---

## 9. Future Work (Phase 2 / 3)

- **Failure-mode fallback**: NaN/out-of-range check on QSS output; revert
  and retry with CVODE for failed cells.
- **Batching**: Group same-reactor cells, pack in reactor-specific ordering,
  call `react(buf, ncells)` for each group. Reduces per-cell overhead.
- **Additional conditions**: Mixture fraction, progress variable, Da number.
- **GPU**: Device-side condition evaluation + sorting + kernel dispatch.
- **Diagnostics**: Write primary/fallback cell fractions to temporals output.
