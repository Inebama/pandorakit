# pandorakit API reference

*Every public class and function, with parameters and usage. Import
root: `from pandorakit import ...` (everything below is re-exported
there unless noted).*

---

## Module `deck` — PANDORA's input language

### `Deck`
An ordered list of input items (statements, comments, `GO`s, `USE`s)
= one PANDORA file.

| method | parameters | does |
|---|---|---|
| `Deck.read(path, heading=False)` | `path`; `heading`: treat line 1 as the Part-A HEADING (use for `.dat` files; not for `.mod/.atm`) | parse a file |
| `Deck.parse(text, heading=False)` | | parse a string (use `Deck.parse(other.dumps())` to deep-copy a deck) |
| `.get(key, part=None)` | `key`: canonical name + indices, e.g. `"TE"`, `"A 3 2"`, `"CE 2 1"`; `part`: restrict to input Part 1..4 (B, D, F, H) | → `Statement` or None |
| `.get_all(name)` | bare name | all statements with that name (e.g. every `HN j`) |
| `.set(key, values, part=None, after=None)` | `values`: scalar or list; `part`: which Part to append to if new; `after`: insert after this statement | replace-or-add; → the `Statement` |
| `.remove(key)` | | delete a statement; → bool |
| `.statements()` | | iterator over `Statement`s |
| `.dumps()` / `.write(path)` | | render back to PANDORA text (80-col safe) |
| `.heading` | attribute | the Part-A line (str) |
| `.items` | attribute | raw item list (`Statement/Comment/Go/Use`) for surgical edits |

### `Statement`
`name` (str), `indices` (list of int, e.g. `[3, 2]`), `values` (list).

| member | does |
|---|---|
| `.key` | canonical lookup key: `"CE 3 2"` |
| `.scalar` | the single value (raises if not exactly one) |
| `.array(length=None)` | values as a plain list; resolves a trailing `Fill` when `length` given; `SKIP` entries → None |

### Value markers
`SKIP` — the `S` control (keep PANDORA's default for that element);
`Fill(value)` — the `F` control (fill the rest of the array).
`Comment(text)`, `Go()`, `Use(target)` — the other item types
(`target` ∈ MODEL/ATOM/RESTART/JNU/INPUT).

```python
d = Deck.read("SPh.dat", heading=True)
d.set("IOMX", 11)
te = d.get("TE").array(91)
d.write("SPh.dat")
```

---

## Module `model` — atmospheres as arrays

### `Atmosphere`
Wraps a model deck; exposes the physical tables as Python lists.
**Convention: index 0 = TOP of the atmosphere** (most negative z); CGS
units, velocities km/s.

Constructor / IO:

| call | parameters |
|---|---|
| `Atmosphere(name, z, te, nh, ne, zmass, v, vt, vxs, bdhm, r1n, cgr, nvh)` | any subset; arrays same length. Either (`z, te, nh, ne`) or (`zmass, te, ne`) makes it runnable |
| `Atmosphere.read(path)` / `.from_deck(deck, name)` | parse a `.mod` (keeps the source deck internally) |
| `.to_deck()` | → runnable deck. From a file: a copy of the original with arrays replaced **in place** (preserves `USE ( INPUT )` segments, populations, comments). From scratch: a fresh 4-segment deck |
| `.write(path)` | `to_deck()` + write |

Attributes: `z, te, nh, ne, zmass, v (broadening!), vt, vxs (wind),
bdhm` (lists or None); `r1n, cgr, nvh` (scalars); `n` (depth count).

| method | does |
|---|---|
| `.validate()` | list of problems; empty = runnable |
| `.copy()` | deep copy |
| `.with_te(te)` / `.with_te_scaled(f)` | copies with a new / scaled T(z). ⚠ scaling beyond ~±5% ⇒ re-converge the H populations (run the H chain and `merge_pop`) |

### `to_multi_atmos(atm, name=None, scale="height", vturb_kms=2.0)`
Export in the MULTI/RH `.atmos` text format (`scale="mass"` needs
`zmass`). For cross-checks with the RH code family; verify against
your RH reader before production.

---

## Module `runner` — executing PANDORA

### `PandoraInstall(root="~/pandora", executable=None, atoms_dir=None, opacities_dir=None)`
Locates `pandora.x`, `atoms/`, `opacities/` under `root` (the
INSTALL.md layout); each path can be overridden.
`.atom_file("h", 15)` or `.atom_file("h", "l15")` → path of
`atoms/hl15.atm` (with a helpful error listing what exists).

### `PandoraRun(install, case, run_id="001", dat=..., mod=None, atm=None, atom=None, res=None, jnu=None, workdir="runs", keep_scratch=False)`

| parameter | meaning |
|---|---|
| `case` | base name of the run's files (`CASE.aaa.RUNID`...) |
| `dat` | the control deck: a path **or a `Deck` object** (written for you) |
| `mod`, `atm`, `res`, `jnu` | path or `Deck` or None. Missing `res`/`jnu` become **empty files** (= start from scratch) |
| `atom` | shortcut for `atm`: `("ca2", 5)` / `("h", "l15")` / `"hl3"` via the library |
| `workdir` | runs happen in `workdir/CASE.RUNID/` (isolated; `fort.NN` symlinks managed for you) |

`.execute(timeout=None, overwrite=False)` → `RunResult`:

| member | meaning |
|---|---|
| `.ok` | True ⇔ exit 0 **and** "PANDORA done" in the log (the only reliable success signal) |
| `.outputs` | dict ext → path (`"aaa", "aix", "rst", "msc", "pop", "jnr", "spc", ...`) |
| `.output("aaa")` | one path, with a helpful KeyError |
| `.log`, `.elapsed`, `.directory`, `.returncode` | as named |

### `PandoraError`
Raised for missing files/tables before any run starts.

---

## Module `outputs` — reading the printout

### `AaaFile(aaa, aix=None)`
The main printout + its section index (`.aix` auto-located).

| member | does |
|---|---|
| `.sections` | list of `(psn, title)` |
| `.find(text)` | case-insensitive substring match over titles |
| `.section(title_or_psn)` | → `Section` (unique match enforced) |
| `.profile(u, l)` | parse `PROF (u/l)` → list of `ProfileBlock` |
| `.extract(title, out)` | machine-readable section dump (the historical `extract` tool) |

### `Section`
`.text` (raw), `.machine_readable()` (list of cleaned lines,
`;`-comments), `.rows()` (numeric rows as float lists).

### `ProfileBlock`
One block of a PROF section.

| field | meaning |
|---|---|
| `.kind` | `"line_profile"` (the emergent line; `wl` = Δλ from center), `"background_intensity/_flux"`, `"linefree_intensity/_flux"` (absolute λ) |
| `.mu` | viewing angle cosine; None for flux blocks |
| `.is_flux` | True for spherical-run flux profiles (F/A columns) |
| `.wl, .ilam, .inu, .tb, .residual` | Δλ [Å] / I or F per Å / per Hz / brightness T / residual profile |
| `.line_center` | absolute line wavelength [Å] |
| `.case` | `"Stationary"` / `"Moving, Source Function velocity"` — PANDORA's own annotation |
| `.redistribution` | `"CRD"` / `"PRD"` — ditto (use to *verify* what physics ran) |

---

## Module `pmerge` — population handoff

`merge_pop(spec, pop, mod, out=None)` — copy tables from a `.pop`
(path or Deck) into a model (path or Deck); write to `out` if given;
→ merged Deck. `spec`: comma-separated keys with shorthands
`@NE+` (NE, NP, HN j, BDH j — after a hydrogen run), `@NP+`, `@HE+`
(helium tables), ranges `HN_1-15`.
`expand_spec(spec, pop_deck)` → the resolved key list.

---

## Module `batch` — many runs in parallel

`Job(case, dat, run_id="001", mod, atm, atom, res, jnu, timeout, meta)`
— one run description (same semantics as `PandoraRun`; `meta` is your
free-form tag dict).

`run_batch(install, jobs, workdir="runs", max_workers=4,
overwrite=False, progress=True)` → `{case.run_id: RunResult}`.
Failures don't stop the batch — check each `.ok`.

---

## Module `recipes` — science building blocks

| function | parameters | does |
|---|---|---|
| `wind_ramp(n, v_top, i_zero, i_top=0, shape="smooth")` | `n` depths; speed `v_top` [km/s] from the top (index 0) down to index `i_top`, then declining (cosine or `"linear"`) to 0 at `i_zero` | → VXS list |
| `set_expansion(deck, vxs, spherical=None)` | `vxs`: list → installs `DO ( EXPAND )` + `VXS` in Part D; None → static (`OMIT EXPAND`, VXS removed); `spherical`: also toggle SPHERE | edits the deck in place; → deck |
| `set_redistribution(deck, u, l, mode, gmma=-1.0)` | `mode`: `"prd"` (adds `SCH u l ( 1 )` + `GMMA`) or `"crd"` (removes them — CRD is PANDORA's default) | per-transition redistribution |
| `chromosphere_te_logm(zmass_phot, te_phot, zmass_top=1e-5, t_start=None, t_max=9000, n_chromo=50, n_tr=10, t_tr_top=2e5)` | photospheric anchors (top-down) + the Mészáros 2009 parameters | → `(zmass, te)` full model run, top-down |
| `core_shift_and_asymmetry(wl, ilam, line_center, core_window=1.5)` | a line-profile block's arrays | → dict: `core_shift_kms` (− = blueshift = outflow), `br_ratio` (B/R < 1 ⇒ outflow in the wing region), `wl_min`, `i_min` |
| `mass_loss_rate(r_star_rsun, nh_cm3, v_kms, r_over_rstar=1.0, mu=1.4)` | conditions at the reference layer | → Ṁ [M☉/yr] = 4πr²ρv |

---

## Module `fit` — automated single-star fitting (needs numpy)

### `Observation(wl, flux, sigma=None, resolution=None, line_center=3933.7)`
A normalized observed profile; `wl` = Δλ [Å] from line center
(RV-correct upstream). `Observation.from_csv(path, resolution,
line_center)` reads `wl,flux[,sigma]` columns; `.window(half_width)`
restricts to the fitting window.

### `Parameter(name, grid, kind="float", bounds=None)`
One fit dimension. `name` ∈ {`v_top`, `i_zero`, `i_top`, `te_scale`}
for the wind model; `grid`: coarse-stage values; `kind="int"` = grid
only (no continuous refinement); `bounds`: hard limits for refinement.

### `WindForwardModel(install, base_dat, mod, atm, res=None, jnu=None, transition=(5,1), line_center=3933.7, workdir="runs/fit", cache_dir=None, wing_window=(3.5,4.5), n_depths=None, run_timeout=1800)`
parameters → PANDORA run → normalized profile. **Caches every run** on
rounded parameter values (`cache_dir`), so grids/refits are free.

| method | does |
|---|---|
| `.profile(**params)` | → `(wl, flux_norm)` model profile (cached) |
| `.on_obs_grid(obs, **params)` | + LSF convolution to `obs.resolution` + interpolation onto `obs.wl` |
| `.chi2(obs, sigma, **params)` | χ² against the observation |
| `.evaluations` | number of real PANDORA runs so far |

### `fit_wind(obs, model, parameters, fixed=None, refine=True, workers=3, profile_points=7, verbose=True)` → `FitResult`
Stage 1: parallel factorial grid. Stage 2: Nelder-Mead refinement of
the float parameters. Stage 3: per-parameter profile likelihood →
**Δχ² = 1 intervals**. If `obs.sigma is None`, σ is scaled so
χ²_red = 1 at the best fit (intervals then measure precision *given
the model's own misfit* — see the statistical-honesty note in the
module docstring).

### `FitResult`
`.best` (dict), `.chi2_min`, `.ndof`, `.chi2_red`, `.errors`
(name → (−, +)), `.grid_points` (every evaluation: fodder for maps),
`.sigma_scaled`, `.n_evaluations`, `.summary()` (printable).

### `degeneracy_map(result, xname, yname)`
→ `(x, y, Δχ²)` scatter arrays (2D profile likelihood over all other
parameters). Δχ² = 2.30 / 6.17 contours = joint 68% / 95% for two
parameters.

### Helpers
`convolve_R(wl, flux, R, line_center)` — Gaussian LSF convolution;
`normalize_to_wings(wl, flux, wing=(3.5, 4.5))` — pseudo-continuum
normalization (use the same convention as your data!).

---

## Module `gui`
`serve(root=None, port=8765, open_browser=True)` — the browser GUI
(model editor with T(z) & velocity drag-editing, run launcher,
results browser, parameter search). Also `python -m pandorakit.gui`
(env: `PANDORAKIT_ROOT`, `PANDORAKIT_NO_BROWSER=1`).

## Command line (`pandorakit ...`)
`run` (stage + execute), `sections`, `extract`, `profile`, `pmerge`,
`params` (search the 738-parameter reference), `gui` — each with
`--help`. Plus `examples/fit_single_star.py --obs ... --config ...`
for the automated fit (see its docstring for the config format).
