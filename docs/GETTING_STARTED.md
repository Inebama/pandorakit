# Getting started — no PANDORA knowledge required

*This is the document to read first. It assumes you know basic stellar
astrophysics and Python — and **nothing** about PANDORA. You will
never write, read, or debug a PANDORA input file: the Python tool does
that. Learn this interface and you can do science.*

---

## 1. What this tool actually does

You give it **the structure of a star's atmosphere** — temperature and
density as a function of depth, as a plain table. It computes, without
assuming LTE:

* how the atoms distribute over their energy levels at every depth
  (the "populations", including the electron density), and
* the **emergent spectral line profiles** an observer would see —
  intensity versus wavelength for lines like Hα, Ca II K, Mg II k.

On top of that base capability you can:

* add a **wind** (an outflow velocity vs depth) and see the line cores
  shift and become asymmetric — the basis of mass-loss measurements;
* **edit the star** (temperature structure, densities, turbulence) in
  Python or by dragging curves in a browser GUI;
* **fit an observed profile** automatically, with error bars
  (`docs/API.md` §fit, `notebooks/fitting_tutorial.ipynb`);
* run **many stars in parallel** (`pandorakit.batch`).

What it does **not** do: determine T_eff/log g/abundances from
photospheric lines (use a classical synthesis code for that — see
MANUAL.md §12), magnetic field/polarization synthesis, or 3D
atmospheres (MANUAL.md §17 explains the landscape).

## 2. The mental model, in 30 seconds

A star's spectrum forms in a thin shell of atmosphere. If you tell me
the temperature `te` and the densities (`nh` = hydrogen nuclei, `ne` =
electrons) at, say, 50 depths through that shell, physics fixes
everything else: how hydrogen distributes over its energy levels, how
photons scatter, and what line profile escapes. Computing that
self-consistently requires iteration (the radiation depends on the
populations, which depend on the radiation) — that's what a "run"
does. **Your job is only: provide the structure, ask for lines, look
at profiles.**

## 3. The one input you must bring: an atmosphere table

### Do I need a model atmosphere a priori?

Yes — this is a *semi-empirical* tool: it does not invent the star's
structure, it computes the spectrum OF a structure (and refines the
electron density for you). You have three ways to get one:

1. **Start from a shipped model** (easiest). The installation includes
   real, converged structures. Export any of them as an editable
   table:

   ```python
   from pandorakit import Atmosphere
   atm = Atmosphere.read("~/pandora/v2.1.1/demos/6/leid.mod")  # red giant
   atm.to_table("my_star.csv")   # now edit it in any editor / pandas
   ```

   Useful starting points: `demos/6/leid.mod` (red giant, R≈84 R☉,
   72 depths, chromosphere), `demos/5/SP.mod` (sunspot umbra, 91
   depths), `demos/2/demo2.mod` (small 25-depth teaching model).

2. **Type one from the literature.** Papers like VAL/FAL (solar) or
   Mészáros et al. 2009 (globular-cluster giants) publish exactly
   these tables (height or column mass, T, densities).

3. **Build one**: photospheric part from a MARCS/Kurucz model for
   your T_eff/log g, plus a parametrized chromosphere on top —
   `recipes.chromosphere_te_logm` implements the standard
   parameterization (see MANUAL.md §12 for the full recipe).

### The file format (exactly)

A plain text file. Rules:

* `#` starts a comment — anywhere, including after data;
* the **first non-comment line is the header** naming the columns;
* columns separated by spaces and/or commas; any order;
* one row per depth point; **top of the atmosphere first**
  (the code auto-detects and flips bottom-first tables).

```
# my red giant, structure from XYZ et al. (2026), Table 3
# top of atmosphere first
 z_km        te      nh         ne          vturb
 -134.5e3   132000   8.70e3     1.16e4      2.0
 -120.0e3    95000   2.1e4      2.5e4       2.0
 ...
    0.0       5800   1.3e16     8.1e11      1.5
    0.29e3    6200   2.9e16     3.6e12     1.5
```

**Columns** (case-insensitive; aliases in parentheses):

| column | unit | meaning | required? |
|---|---|---|---|
| `z_km` (`z_cm`, `height_km`) | km or cm | height; **0 near the visible surface, negative above it** (toward the observer) | yes¹ |
| `zmass` (`colmass`, `m`) | g/cm² | column mass — an alternative depth scale | ¹either z or zmass |
| `te` (`t`, `temp`) | K | temperature | **yes** |
| `nh` (`n_h`) | cm⁻³ | total hydrogen (HI + HII) number density | yes with z¹ |
| `ne` (`n_e`) | cm⁻³ | electron density — **a rough guess is fine**: hydrogen runs recompute it | **yes** |
| `vturb` (`v_turb`) | km/s | micro-turbulent line broadening | no (typical 1–5) |
| `vt` | km/s | turbulence for pressure support | no |
| `wind` (`vxs`, `v_wind`) | km/s | outflow velocity, positive outward | no |

¹ Two valid minimal sets: (`z`, `te`, `nh`, `ne`) **or** (`zmass`,
`te`, `ne`) — with column mass, the code derives heights and `nh`.

How many rows? 40–100, concentrated where your lines form (the upper
photosphere and chromosphere) — the shipped models show sensible
spacing.

Load and sanity-check it:

```python
atm = Atmosphere.from_table("my_star.csv")
print(atm)             # <Atmosphere my_star: N=45, TE 5493-132412 K>
print(atm.validate())  # [] means runnable; otherwise plain-English problems
```

### Two scalar properties of the star

Passed in the compute call (or set on the Atmosphere):

* `gravity_ratio` — surface gravity relative to the Sun
  (e.g. `10**(logg - 4.44)`);
* `r1n` — the thickness of your modeled atmosphere slab in cm
  (top row to bottom row). It matters for extended giants (sphericity);
  for a first run, `abs(z_top)` is a fine value.

## 4. Your first spectrum

```python
from pandorakit.simple import compute_spectrum

result = compute_spectrum(
    "my_star.csv",             # your table (or an Atmosphere object)
    lines=[(3, 2), (2, 1)],    # which H lines: (3,2)=H-alpha, (2,1)=Ly-alpha
    levels=3,                  # model-atom size: 3 now, 15 for production
    iterations=5,              # NLTE iterations this run
    gravity_ratio=2.1e-3,      # giant star
    r1n=5.9e7,
    workdir="runs/my_star",
)
print(result.summary())
```

That's the whole thing. ~15 s later (3-level atom, 45 depths) you
have profiles. Every argument explained:

| argument | what it means | how to choose |
|---|---|---|
| `lines` | which transitions to synthesize, as (upper, lower) energy-level pairs of hydrogen | H-alpha = (3,2); Ly-alpha = (2,1); with `levels=15` also H-beta (4,2), Paschen... |
| `levels` | how many H energy levels the model atom has | 3 = fast bootstrap; 15 = production accuracy (slower) |
| `iterations` | how many times the populations↔radiation loop runs | 5 to start; convergence = rerunning changes nothing (see §6) |
| `wind` | outflow speed per depth, km/s (list, top first) | `None` = static; build with `recipes.wind_ramp` (§8) |
| `prd_lines` | lines to treat with partial redistribution | leave default until you work on strong resonance lines |
| `update_populations` | return the atmosphere with refined NE/populations | keep True; feed `result.atmosphere_updated` to the next call |

## 5. What you get back

```python
b = result.profile(3, 2)      # H-alpha, disk center (mu=1)
```

`b` is a ProfileBlock — arrays ready for numpy/matplotlib:

| field | meaning |
|---|---|
| `b.wl` | wavelength offsets from line center [Å] (0 = line center) |
| `b.ilam` | intensity [erg cm⁻² s⁻¹ sr⁻¹ Å⁻¹] (or flux in spherical runs) |
| `b.line_center` | absolute wavelength of the line [Å] |
| `b.mu` | viewing angle: 1.0 = star's disk center, 0.3 = near the limb; `None` = whole-disk flux |
| `b.tb` | brightness temperature [K] per wavelength |
| `b.case` | the code's own annotation: "Stationary" or "Moving..." — use it to *verify* what ran |
| `b.redistribution` | "CRD"/"PRD" — ditto |

```python
import matplotlib.pyplot as plt
plt.plot(b.wl, b.ilam)
plt.xlabel("Δλ [Å] from H-alpha"); plt.ylabel("intensity")
```

And the refined star:

```python
result.atmosphere_updated.to_table("my_star_v2.csv")  # NE now self-consistent
```

## 6. Iterating to convergence

One call = `iterations` loops from your starting guess. For a new
atmosphere, repeat the call feeding the output back until the answer
stops changing:

```python
atm = Atmosphere.from_table("my_star.csv")
for i in range(3):
    result = compute_spectrum(atm, lines=[(3, 2)], iterations=5,
                              gravity_ratio=2.1e-3, r1n=5.9e7,
                              run_id=f"{i:03d}", workdir="runs/my_star")
    atm = result.atmosphere_updated
```

Converged when the profile and the NE table are stable between rounds
(plot them!). Then switch `levels=15` for the production run.

## 7. Changing the star

`Atmosphere` attributes are plain Python lists — edit freely, then
recompute:

```python
atm.te = [t * 1.03 for t in atm.te]        # hotter chromosphere
atm2 = atm.with_te_scaled(1.03)            # same, as a copy
```

(Temperature changes beyond a few percent: re-run the convergence loop
of §6 afterward — populations must catch up.)

Prefer clicking? `pandorakit gui` opens a browser app: load a model,
**drag the T(z) curve** and the velocity curve with the mouse, save,
run — nothing to install, and everything it writes is a normal file.

## 8. Winds and mass loss

A wind is just an array: the outflow speed at each depth (km/s,
positive outward, first value = top of the atmosphere). The helper
builds the standard shape (fast on top, decaying to zero below):

```python
from pandorakit.recipes import wind_ramp
w = wind_ramp(atm.n, v_top=12.0,  # 12 km/s at the top
              i_zero=34,          # reaches zero at depth index 34
              i_top=8)            # full speed above index 8
result = compute_spectrum(atm, lines=[(3, 2)], wind=w, ...)
```

Physics you will see: the line only reacts if the wind flows through
the layers where it forms; the core shifts blueward and the profile
becomes asymmetric — exactly the observables used to infer mass-loss
rates (`recipes.mass_loss_rate` turns density + speed + radius into
M☉/yr; the course pack lesson 6 walks the full science case).
Expanding runs cost ~3–5× a static run.

## 9. Beyond hydrogen

Hydrogen comes first for a reason: it dominates the gas and sets the
electron density — every other ion's calculation *rides on* a
converged hydrogen atmosphere. The pattern for Ca II, He I, Mg II...
is a **chain**: hydrogen run → its updated atmosphere → the next ion.
The runnable example [examples/run_chain_demo6.py](../examples/run_chain_demo6.py)
does H → He I → Ca II on the red-giant model, and
[examples/velocity_mass_outflow.py](../examples/velocity_mass_outflow.py)
does the Ca II K wind study. Use them as templates — they are ~40
lines each and follow exactly the calls you already know. (A
`compute_spectrum`-style one-liner for other ions is a planned
addition; the chain scripts are today's supported route.)

## 10. Fitting an observation

When you have a real spectrum and want parameters + error bars:

* your data: a CSV with columns `wl, flux[, sigma]` — wl in Å
  *relative to the line center* (apply the star's radial-velocity
  correction first), flux normalized;
* the tutorial: [notebooks/fitting_tutorial.ipynb](../notebooks/fitting_tutorial.ipynb)
  (start here — it explains every step and runs in minutes);
* unattended: `python3 examples/fit_single_star.py --obs star.csv
  --config fit_config.json --outdir out/` → best-fit parameters,
  Δχ² error bars, degeneracy maps.

## 11. When something goes wrong

* `atm.validate()` before running — it answers in plain English
  ("ne is required when using a z grid", "te must be positive"...).
* A failed run raises `RuntimeError` with the tail of the engine's
  log and the directory where the full record lives. The three most
  common causes: a column in the wrong units (heights in cm when km
  intended — check the magnitudes printed by `print(atm)`), a
  non-monotonic depth column, densities with a typo'd exponent.
* Runs are isolated per directory — a crashed run never corrupts
  anything; fix the input and rerun.
* Ask the reference docs only when you want depth: MANUAL.md (how the
  engine thinks), INPUTS.md (the native input format, for reading the
  shipped templates), API.md (every function).

## 12. Glossary — jargon you may meet in the other docs

| term | plain meaning |
|---|---|
| *deck* / `.dat` | the engine's run-settings file. You never write one: `compute_spectrum` fills a shipped, validated **template** |
| *model* / `.mod` | the engine's own atmosphere format. Your CSV is converted automatically (`Atmosphere` ⇄ both formats) |
| *atom file* / `.atm` | energy levels + transition data for an element; 97 ship with the install; `levels=` picks among them |
| *restart files* (`.rst/.pop/...`) | the run's memory between iterations — handled internally (`atmosphere_updated` is the friendly face of it) |
| *populations* | how many atoms sit in each energy level, per depth |
| *NLTE* | populations computed from the actual radiation, not from the local temperature — the whole point of this engine |
| *iterations* (`IOMX`) | rounds of the populations↔radiation loop in one run |
| *PROF (u/l)* | the printout section holding the emergent profile of transition u→l — what `result.profile(u, l)` reads for you |
| *PRD / CRD* | how photon frequencies reshuffle in scattering; CRD is the default, PRD matters for strong resonance lines |
| *μ (mu)* | viewing angle cosine: 1 = disk center, small = near the limb |

## 13. Cheat sheet

| I want to... | do this |
|---|---|
| get a starting atmosphere | `Atmosphere.read(<shipped .mod>).to_table("star.csv")` |
| load/check my table | `atm = Atmosphere.from_table("star.csv")`; `atm.validate()` |
| compute Hα | `compute_spectrum(atm, lines=[(3,2)], ...)` |
| plot it | `b = result.profile(3,2); plt.plot(b.wl, b.ilam)` |
| refine to convergence | loop `atm = result.atmosphere_updated` |
| change T(z) | edit `atm.te` / `atm.with_te_scaled(f)` / `pandorakit gui` |
| add a wind | `wind=wind_ramp(atm.n, v_top, i_zero)` |
| other ions | copy `examples/run_chain_demo6.py` |
| fit my observed profile | the tutorial notebook → `fit_single_star.py` |
| look up any engine parameter | `pandorakit params <name>` (738 entries, plain descriptions) |
