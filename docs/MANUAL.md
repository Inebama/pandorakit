# PANDORA from zero to hero

*A practical manual for the PANDORA non-LTE atmosphere & spectrum
synthesis code (Avrett & Loeser, CfA), for people who have never run it.*

This manual is self-contained for practical work, and cross-references
the authoritative 368-page writeup by Rudy Loeser (`v2.1.1/doc/wup.pdf`,
"wup" below) for deep detail. Section numbers like *(wup §5)* point
there. Read this manual first; keep wup.pdf as your reference book.

---

## Table of contents

1. [What PANDORA is (and is not)](#1-what-pandora-is-and-is-not)
2. [The mental model: how a run works](#2-the-mental-model)
3. [Files and logical units](#3-files-and-logical-units)
4. [The input language](#4-the-input-language)
5. [Input structure: Parts A-I and run types](#5-input-structure)
6. [Your first run, step by step (demo 1)](#6-your-first-run)
7. [Atmosphere models (.mod)](#7-atmosphere-models)
8. [Atom models (.atm) and the atomic library](#8-atom-models)
9. [Outputs and how to read them](#9-outputs)
10. [Iteration, convergence, and restarts](#10-iteration-convergence-restarts)
11. [Multi-ion chains: the real workflow (demo 6)](#11-multi-ion-chains)
12. [Synthesizing the spectrum of a new star: full recipe](#12-a-new-star)
13. [pandorakit: Python and GUI](#13-pandorakit)
14. [Many stars at once (batch)](#14-batch)
15. [Troubleshooting](#15-troubleshooting)
16. [Physics reference: what is being solved](#16-physics)
17. [Toward 3D and modern codes: an honest roadmap](#17-toward-3d)
18. [Citing and further reading](#18-citing)

---

## 1. What PANDORA is (and is not)

PANDORA computes, for a **one-dimensional** stellar atmosphere
(plane-parallel or spherical), the **time-independent non-LTE** state of
multilevel model atoms and the resulting **emergent spectrum**. Begun in
1966 by Rudolf Loeser under Eugene Avrett's direction, it built many of
the canonical solar atmosphere models (VAL, FAL — e.g. Vernazza, Avrett
& Loeser 1981; Fontenla, Avrett & Loeser 1993; Avrett & Loeser 2008) and
has been applied to other stars and nebulae.

Its specific strengths:

* **line source functions** with full **partial frequency
  redistribution (PRD)** — essential for strong resonance lines
  (Lyman α/β, Mg II h&k, Ca II H&K, He lines);
* multilevel statistical equilibrium with radiative + collisional
  processes, fluorescence, dielectronic terms;
* many "background" opacity sources (H, H⁻, He I/II, C I, Si I, Mg I,
  Fe I, Na I, Ca I, O I, S I, Al I, dust, molecules, X-ray/coronal
  illumination);
* **particle diffusion and flow velocities in the ionization
  equilibrium** — important wherever temperature gradients are steep
  (chromosphere-corona transition region);
* hydrostatic equilibrium, radiative energy balance with mechanical
  heating, momentum balance;
* spherical geometry and expanding atmospheres (winds).

What it is **not**:

* not 3D, not (magneto)hydrodynamic, not time-dependent — you supply a
  1D T(z) structure (or iterate one under energy balance), PANDORA
  supplies the NLTE radiation field, populations, and spectra
  (see [§17](#17-toward-3d));
* not a black box: a converged model is reached through a *sequence of
  restarted runs* under your judgement, not one command;
* not a modern codebase: Fortran 77, fixed logical units, line-printer
  output. pandorakit ([§13](#13-pandorakit)) hides most of that.

## 2. The mental model

One PANDORA **run** = one execution of `pandora.x`:

```
inputs                          PANDORA                     outputs
──────────────                  ────────────                ───────────────
.dat  run controls       ┐      read input                  .aaa printout
.mod  atmosphere model   │      ↓                           .aix index
.atm  atom model         ├───►  iterate: continuum,   ───►  .rst .msc .pop
.res  restart data       │      rates, statistical          restart data
.jnu  PRD Jbar restart   ┘      equilibrium, line           .spc spectra
atoms/ opacities/ tables        source functions            .jrl journal ...
```

A typical *project* (one star, one instrument's lines) is a **chain** of
runs: a hydrogen run establishes n_e and the H populations; its output
populations are merged into the atmosphere model; further ions (He I,
Ca II, Mg II, ...) are run in that atmosphere; strong-line runs are
restarted several times, adjusting numerical switches as convergence
proceeds; finally spectrum-oriented runs produce profiles for
comparison with observations. The historical tooling for this loop is
csh scripts + an editor; pandorakit gives you Python objects and a GUI.

Key habit from the original authors *(wup §99)*: **each run's inputs are
small edits of the previous run's inputs, and most inputs come from the
previous run's outputs** (the restart files are written *in the input
language* for exactly this reason).

## 3. Files and logical units

PANDORA addresses files by Fortran unit number; wrapper tooling maps
names onto units (see INSTALL.md "How PANDORA finds its files").
Traditional extensions *(wup §7, §8)*:

**Inputs**

| unit | ext | contents |
|---|---|---|
| 3 | `.dat` | run-specific controls; *reading always starts here* |
| 4 | `.mod` | atmosphere model (via `USE ( MODEL )`) |
| 7 | `.atm` | atom model (via `USE ( ATOM )`) |
| 8 | `.res` | restart data from previous run (via `USE ( RESTART )`) |
| 9 | `.jnu` | PRD mean-intensity restart values |
| 10/11/12 | — | opacity tables `statistical.dat`, `composite.dat`, `average.dat` |
| 28 | — | `run_archive.txt` performance log (append) |

**Outputs**

| unit | ext | contents |
|---|---|---|
| 15 | `.aaa` | the main printout — everything human-readable |
| 31 | `.aix` | index of `.aaa` print sections (PSN numbers) |
| 16 | `.aer` | error messages / debug |
| 19 | `.rst` | restart data: ρ, J̄, source-function state → next run's `.res` |
| 20 | `.msc` | miscellaneous restart data (model tables, fluxes, ...) |
| 21 | `.pop` | population tables (NE, NP, HN j, BDH j, ...) |
| 22 | `.jnr` | PRD J̄ values → next run's `.jnu` |
| 23 | `.spc` | emergent spectrum data (when TRN directives request it) |
| 24 | `.coo` | cooling rates |
| 25/26/30/32 | `.csp/.mat/.itr/.cks` | machine-readable data for separate programs |
| 27 | `.tsf` | source-function related transition data |
| 29 | `.jrl` | journal: every input statement as read |
| 1 | `.tmp` | direct-access scratch (can reach GBs; deleted after run) |

## 4. The input language

*(wup §1 — this summary is complete for practical purposes)*

Everything PANDORA reads (`.dat`, `.mod`, `.atm`, `.res`, ...) is the
same free-field, blank-separated statement language:

```
NAME j ( Q ) >
```

* `NAME` — the parameter (case-insensitive). ~740 exist *(wup §5;*
  `pandorakit params <name>` *searches them)*.
* `j` — zero, one or two integer indices: `TE ( ... )`,
  `CI 1 ( ... )`, `A 3 2 ( ... )` (transition upper=3, lower=2).
* `( Q )` — the values. A statement may span lines; the closing `)`
  ends it. Several statements may share a line.
* `>` — "ignore the rest of this input line". Used to protect trailing
  junk and to end lines inside long value lists.
* `[ comment ]` — comment; **the blanks after `[` and before `]` are
  mandatory**, and a `>` inside a comment is treated as comment text —
  a classic gotcha *(wup §1 example line 11!)*.
* `GO` — ends one input Part ([§5](#5-input-structure)).
* Only the first **80 columns** of each line are read.

Inside `( Q )`, plain numbers fill the array left to right, and five
control fields modify that:

| control | meaning |
|---|---|
| `M m` | multiplier: every following number ×m (until the next `M`) |
| `I i` | set the array pointer: next value goes to element i (1-based) |
| `R r` | repeat the next value r times |
| `S` | skip an element (keep its current/default value) |
| `F v` | fill the rest of the array with v; ends the statement's data |

Example *(wup §1)*:

```
NE ( 0. M 1.E1 1. 2. 3. 4. 5.
R 5 6. F 7. )
```

yields NE = 0, 10, 20, 30, 40, 50, 60,60,60,60,60, 70, 70, ... — note
the multiplier applying to everything after `M`, the repeat, the fill.
PANDORA's own restart files use these forms, so any parser you write
must expand them (pandorakit's `Deck` does).

## 5. Input structure

*(wup §3)* Input is organized in nine Parts, **in this order**:

```
Part A  HEADING            one line, printed on banners (first line of .dat)
Part B  table lengths, switches, options        ┐ ended by GO
Part C  GO                                      ┘
Part D  the physics: model, atom, controls      ┐ ended by GO
Part E  GO                                      ┘
Part F  spectrum-calculation parameters         ┐ ended by GO
Part G  GO                                      ┘
Part H  populations data                        ┐ ended by GO
Part I  GO                                      ┘
```

Any of B, D, F, H may be empty, but all four `GO`s must appear.
Reading always starts in `.dat`; `USE ( MODEL )`, `USE ( ATOM )`,
`USE ( RESTART )`, `USE ( JNU )` switch reading to the other files, and
`USE ( INPUT )` (inside those files) hands control back. A partially
read file resumes where it left off — that is how one `.mod` file
contributes to Part B (its `N`), Part D (its tables) and Part H (its
populations) as reading progresses. Look at `demos/2` for the canonical
4-file layout.

Ordering constraints worth knowing *(wup §3)*: `NT` before `INPAIR`;
`NSL` before `MR`/`LR`; `NL` < `NSL` ≤ 50; per-transition `LDL` before
that transition's broadening data; `KST/KBT/KRT` before the
corresponding wavelength tables.

**Run types** *(wup §99)*: (1) population-update runs with H;
(2) population-update runs with other ions (`POPUP` switch set);
(3) regular runs; (4) no-ion runs (option DOION off); (5) continuum-only
runs (`JSTCN`); (6) input-only runs (`DO ( JSTIN )`) — read the input,
print Phase-0 diagnostics, stop. **Always debug new input with an
input-only run first**; it costs seconds.

## 6. Your first run

(Assumes the install from INSTALL.md, with demos under
`~/pandora/v2.1.1/demos`.)

Demo 1 is a 3-level hydrogen atom in a 25-depth solar-like atmosphere,
2 iterations, everything in a single `.dat` file.

**Classic way:**

```bash
cd ~/pandora/v2.1.1/demos
csh -c "bin/pandora -io 1/ -atoms 1/ demo1 none '' 001" > 1/demo1.log
```

**pandorakit way:**

```python
from pandorakit import PandoraInstall, PandoraRun, AaaFile
install = PandoraInstall("~/pandora")
res = PandoraRun(install, case="demo1none", run_id="001",
                 dat="~/pandora/v2.1.1/demos/1/demo1none.dat",
                 workdir="runs").execute()
assert res.ok            # checks for "PANDORA done"
```

What to look at afterwards *(wup §99 walks the same outputs)*:

* `demo1none.aaa.001` — the printout. Find your way with the index
  `demo1none.aix.001`, or `pandorakit sections 1/demo1none.aaa.001`.
* Section `LINE (3/2)` — the line source function calculation for the
  3→2 transition (Hα analog in this toy atom); `S(n)` vs `S` columns
  nearly equal ⇒ converged.
* Section `RHO AND RBD` — ends with *Consistency CHECKs*: essentially
  all values should be ≈ 1 in a converged model (demo 1 is deliberately
  *not* converged after 2 iterations — the "Iterative Ratio" plots and
  RK-1 "Old/New" far from unity show it; that's the lesson).
* `demo1none.pop.001` / `.rst` / `.msc` — restart data for continuing.

Now open the input `1/demo1none.dat` next to wup §99's DEMO1 narrative
and identify: the HEADING; Part B (N, KK, NL, NT, INPAIR, DO/OMIT
options, RUNTOPOP); the first GO; Part D (atmosphere Z/TE/NH/NE/BDHM,
atom data P, CP, TER, CI, CE, A 3 2, line-broadening CRD/CVW/CSK/CRS,
XK ray table, IOMX iteration count, POPUP, TRN spectrum directives);
then GO GO GO. You have now read a complete PANDORA input.

## 7. Atmosphere models

Minimum content *(wup §99)*: `N` (number of depths, Part B) and, in
Part D, `Z`, `TE`, `NH`, `NE` — or `ZMASS`, `TE`, `NE` (PANDORA then
derives Z and NH). Units: CGS (Z in cm, increasing upward with 0
conventionally near τ₅₀₀₀=1... follow the demos; TE in K; densities
cm⁻³).

Common additions:

| statement | meaning |
|---|---|
| `V` | flow velocity (km/s; sign convention: + outward) |
| `VT` | microturbulent velocity (km/s), broadening + turbulent pressure |
| `NVH ( 0 )` | with V=0: forces the static treatment (see demo 1) |
| `R1N` | R(1)-R(N): atmosphere thickness parameter (cm) for spherical/eclipse work |
| `CGR` | gravity parameter (see wup §5 note; demos use solar 8.17E-4 scaled) |
| `BDHM` | H⁻ departure coefficients |
| `NLH ( n )` + `HN 1..n`, `BDH 1..n`, `NP` | hydrogen populations from a previous H run (Part H) |

Real models to start from:

* `demos/5/SP.mod` — a sunspot umbra test model (91 depths);
* `demos/6/leid.mod` — a 72-depth chromospheric model;
* the literature: VAL-C (Vernazza et al. 1981), FAL models (Fontenla et
  al. 1993), Avrett & Loeser (2008) — their tables give Z/TE/NE/NH
  directly; type them into a `.mod` or build one with
  `pandorakit.Atmosphere` from arrays.

For a *different star*, see [§12](#12-a-new-star).

## 8. Atom models

97 ready-made `.atm` files ship in `v2.1.1/atoms/`: H (3,4,5,15 levels,
plus `db` detailed-balance variants), He I/II, C I-V, N, O, Na, Mg I/II,
Al, Si I/II, S, Ca I/II, Fe I... Naming: `<ion>l<levels>.atm`
(`hl15.atm`, `mg2l2.atm` = Mg II 2-level, `ca2l5.atm`).

An atom model contains *(wup §19)*: `NL` (bound levels), `NT`+`INPAIR`
(which transitions are radiative), level data (`P` statistical weights,
`CP` photoionization cross-sections, `XNU` level energies where needed),
collisional rates (`CI` ionization, `CE ij` excitation, on the `TER`
temperature grid), radiative data (`A u l` Einstein coefficients,
broadening: `CRD` radiative, `CVW` van der Waals, `CSK` Stark, `CRS`
resonance), `MR`/`LR` sublevel structure, `RUNTOPOP` mapping for
population updates, and for H the special treatments of wup §19.

Advice: **do not write atom files from scratch**; start from the
library. When you need a new ion, copy the closest structure and replace
the atomic data (NIST for levels/A-values; standard collision-strength
sources). The `db` variants put resonance lines in detailed balance —
useful in first bootstrap runs.

## 9. Outputs

The `.aaa` printout is divided into *print sections*, indexed by the
`.aix` file (`PSNnnnnnn` markers). List them:

```bash
pandorakit sections SPh.aaa.001
```

Landmarks (demo-5-like hydrogen run): `OPTIONS` (every option's state),
`INPUT NOTES` (**read this** — it flags suspicious input), `ATMOSPHERE`,
`ATOM`, per-iteration `ITERATION n` / `RATES` / `LINE (u/l)` blocks,
`NE` (electron density recomputation), `POPULATIONS`, `RHO AND RBD`
(with the consistency CHECKs), `WAVE SUMM 0/1` (continuum summary —
keep these on), `PROF (u/l)` (emergent line profiles), `FLUX`,
`ECLIPSE`, `COOLING`, `ITERATES` (iterative-ratio convergence plots),
`EXECUTION DATA`, `SIGN-OFF` (version stamp).

Extraction:

```bash
# machine-readable text (the historical `extract` behavior):
pandorakit extract 'PROF (5/1)' SPh.aaa.001 prof.txt
# emergent line profile as columns (block kind aware):
pandorakit profile SPh.aaa.001 5 1 -o prof.csv
```

or in Python:

```python
aaa = AaaFile("SPh.aaa.001")
blocks = [b for b in aaa.profile(5, 1) if b.kind == "line_profile"]
# b.wl = Δλ from line center [Å], b.ilam = I [erg/cm²/s/sr/Å],
# b.mu, b.residual, b.line_center
```

A `PROF (u/l)` section contains, in order: *Background Intensity* and
*Background Flux* (the line-specific continuum around the line,
absolute λ), *Line-free* variants, then the *Profile of the u/l Line*
blocks per μ (DL = Δλ from line center; I/A, I/Hz, Residual = I/I_c,
integrated intensities, brightness temperature). `pandorakit` labels
these `kind`s for you.

The `.spc` file collects spectrum data written by `TRN` directives
(e.g. `TRN 2 ( I 23 5000. 5000. )` writes transition 2's profile data
to unit 23); the `PROF` printout is usually the more convenient source.

## 10. Iteration, convergence, restarts

`IOMX ( n )` sets the number of overall iterations in the run.
PANDORA's iteration is not a fixed-point button you press once: real
projects converge over **several restarted runs** (5-15 iterations
each), inspecting between runs.

The restart loop (single ion) — *(wup §99, DEMO3)*:

1. Run with `IOMX ( n )`.
2. Move outputs to inputs: `.rst` → `.res`; if PRD: `.jnr` → `.jnu`.
3. Update the model's populations: merge `.pop` tables (NE, NP, HN j,
   BDH j) into the `.mod` (pandorakit: `merge_pop("@NE+", pop, mod)`;
   classic: `pmerge @NE+,@NP+ case.pop.001 model.mod`).
4. Optionally adjust numerical switches (the *Iterative Ratio* plots
   and `INPUT NOTES` guide you; wup §4-§6 document the options).
5. Rerun. Converged when: consistency CHECKs ≈ 1, iterative ratios ≈ 1,
   `S(n)` ≈ `S`, populations stable between runs.

The `ready.x` utility (classic: `bin/ready SPh`) interactively stamps a
new `IOMX` into a `.dat`; with pandorakit simply:

```python
deck = Deck.read("SPh.dat", heading=True)
deck.set("IOMX", 11)
deck.write("SPh.dat")
```

## 11. Multi-ion chains

The canonical workflow (demo 6: H → He I → Ca II in a chromospheric
model):

```
run H          (pop-update run: recomputes NE, H populations)
merge @NE+     leidh.pop → leid.mod         (NE, NP, HN 1.., BDH 1..)
run He I       (pop-update run in the updated atmosphere)
merge @HE+     leidhe1.pop → leid.mod
run Ca II      (regular run: Ca II is not a background 'population ion')
extract PROF   → Ca II H&K profiles, Hα, He 10830 ...
```

Hydrogen runs are special *(wup §99)*: only they recompute Z, NH, NE
authoritatively — always begin a chain with hydrogen, and prefer its NE
over other ions'. The 12 "population ions" whose densities feed the
background opacity are H, He I(+II), C I, Si I, Al I, Mg I, Fe I, Na I,
Ca I, O I, S I *(POPUP / RUNTOPOP machinery)*.

In pandorakit this chain is a short script — see
`examples/run_chain_demo6.py`, which reproduces demo 6's `run.sou`
exactly (runs, merges, extracts — no csh, no manual editing).

## 12. A new star

The honest recipe for "spectra for star X from scratch":

1. **Start from a structure.** Take a published semi-empirical model of
   a star of similar T_eff/g/activity (solar VAL/FAL for G stars; M
   dwarf chromospheric models; etc.), or a photospheric structure from
   MARCS/ATLAS/PHOENIX extended by a parametrized chromosphere if you
   are modeling emission lines. Get it into a `.mod`
   (`Atmosphere(z=…, te=…, nh=…, ne=…)`; `zmass`+`te`+`ne` also works
   and lets PANDORA derive Z, NH).
2. **Scale the fundamentals**: `CGR` (gravity), `ABD`/element
   abundances *(wup §10, `FRANK` element data)*, `R1N` if spherical
   effects matter (giants!), `VT` microturbulence.
3. **Bootstrap hydrogen.** 3-5 level H (`hl5.atm`), detailed-balance
   Lyman (`DO ( LYMAN )` handling as in demo 1), a handful of
   iterations, `DO ( JSTIN )` first to validate input. Then 15-level H
   restarts until NE stabilizes.
4. **Hydrostatic equilibrium** (option HSE) if you want the density
   structure self-consistent with your T(z), or keep densities fixed if
   they came from a trusted model.
5. **Chain the ions you care about** ([§11](#11-multi-ion-chains)).
   PRD for resonance lines (Mg II, Ca II, Lyα): supply `.jnu` restarts
   between runs.
6. **Fine-tune T(z) against observations**: perturb the temperature
   structure (GUI drag-editing; `Atmosphere.with_te(...)` in scripts),
   rerun the affected ions, compare profiles. This inverse problem is
   the day-to-day craft of semi-empirical modeling.
7. **Assemble the spectrum**: profiles from `PROF` sections
   (line-profile blocks), continua from the flux/intensity sections or
   `.csp`.

Rules of thumb: 50-100 depth points, refined where lines form (the
demos' grids are good templates); every strong line's core forms higher
than you think; check the `INPUT NOTES` and `.aer` after every first
run of a new configuration.

## 13. pandorakit

```python
from pandorakit import (PandoraInstall, PandoraRun, Deck, Atmosphere,
                        AaaFile, merge_pop, batch)
```

* `Deck` — parse/edit/write any PANDORA input file (full language:
  M/I/R/S/F, comments, GO, USE). `deck.get("TE").array(n)`,
  `deck.set("IOMX", 11)`, `deck.write(path)`.
* `Atmosphere` — model as arrays; `.validate()` explains what's
  missing; `.to_deck()/.write()`; `.with_te_scaled(1.02)` for quick
  experiments.
* `PandoraRun(...).execute()` — isolated run directory, `fort.NN`
  symlinks, output harvesting, `RunResult.ok` ⇔ "PANDORA done".
* `AaaFile` — sections, machine-readable extraction, profile parsing
  with block kinds.
* `merge_pop("@NE+", pop, mod, out)` — population handoff.
* `batch.run_batch(install, jobs, max_workers=8)` — grids/surveys.
* CLI: `pandorakit run|sections|extract|profile|pmerge|params|gui`.

**GUI** (`pandorakit gui`): browser app, no dependencies —

* *Model editor*: T(z) as a draggable curve (successor of the IDL
  `xtwiddle`), shift-drag moves neighbours with Gaussian weights,
  double-click to type a value; density plots; validity check; save.
* *Run*: pick deck/model/atom, launch, watch the live log.
* *Results*: browse print sections, plot emergent profiles per μ,
  export CSV.
* *Parameters*: instant search of the ~740-entry input glossary.

## 14. Batch

```python
from pandorakit import PandoraInstall, Atmosphere, Deck, batch

install = PandoraInstall("~/pandora")
base = Atmosphere.read("leid.mod")
template = Deck.read("leidh.dat", heading=True)

jobs = []
for i, f in enumerate([0.96, 0.98, 1.0, 1.02, 1.04]):
    jobs.append(batch.Job(
        case=f"leid_t{i}", run_id="001",
        dat=template, mod=base.with_te_scaled(f).to_deck(),
        atom=("h", 5),
    ))
results = batch.run_batch(install, jobs, workdir="grid", max_workers=5)
for key, res in sorted(results.items()):
    print(key, res.ok, res.elapsed)
```

Each job runs in its own directory; failures don't stop the batch.
This is also the building block for the "1.5D" mode of [§17](#17-toward-3d).

## 15. Troubleshooting

* **`PANDORA done` missing** → the run did not finish, whatever else
  got written. Check the log tail and `.aer`.
* **Input errors**: PANDORA echoes the offending line with an `*` under
  the failing field *(wup §3)*. With option DELABORT (default on) it
  keeps scanning to report more errors before stopping. Common causes:
  missing blank inside `[ ]`, a `>` inside a comment (swallows the
  line), statement in the wrong Part, table longer than its declared
  length (`N`, `NSL`, ...), `NT`/`INPAIR` order.
* **`Trouble reading Continuum Block at address = ...`** on a fresh
  build → your `sys/` was compiled with optimization. Rebuild `sys/` at
  `-O0` (see INSTALL.md — this is a build problem, not an input
  problem).
* **Immediate stop with workspace messages** (`WORLD`/`IWORLD`,
  `TOAST`, allocation) → enlarge `LNGTHX` / `LNGTHI` / `LENMEM` in
  `pan/pandora.f` and rebuild (defaults: 50M real*8 ≈ 400 MB, 2M int,
  25M real*8 ≈ 200 MB — big grids/many transitions can exceed them).
* **Negative/NaN populations, oscillating iterations** → too ambitious
  a first run. Reduce: fewer levels, detailed-balance resonance lines
  (`db` atom files or `ktrans u l ( thick )`), more conservative
  damping options; converge H before anything else; increase depth
  resolution where the line core forms.
* **PRD runs wander** → make sure `.jnu` from the previous run is
  supplied (`USE`d) and current; PRD restarts effectively continue the
  Jbar iteration.
* **It worked yesterday, differs today at 1e-3** → PANDORA runs are
  deterministic; you changed an input. `diff` the `.jrl` journals of
  the two runs — that's what they are for.

## 16. Physics

For a rigorous statement of the equations (statistical equilibrium with
the net-radiative-bracket ρ formulation, equivalent-two-level-atom
source functions, PRD redistribution integrals, diffusion terms in the
ionization balance, spherical transfer, energy balance) read, in order:

1. Avrett & Loeser 2003, ASP Conf. 288, "Solar and Stellar Atmospheric
   Modeling Using the Pandora Computer Program" (`doc/paper.pdf` — 14
   pages, the best overview);
2. wup §12 (source functions), §15 (PRD), §16 (velocities), §17 (ion
   abundances), §20 (statistical equilibrium equations), §21 (Lyman
   lines in the continuum);
3. Vernazza, Avrett & Loeser 1981, ApJS 45, 635 (the VAL III paper —
   the methodology in action);
4. Avrett & Loeser 2008, ApJS 175, 229 (modern solar application).

## 17. Toward 3D

You asked where this goes for "3D realism". The honest picture:

**PANDORA is structurally 1D.** Geometry (plane-parallel/spherical
rays), the workspace layout, and the entire input model assume one
depth coordinate. There is no practical path to making the code itself
3D — do not attempt it.

**What is both realistic and scientifically standard:**

1. **1.5D / column-by-column synthesis** (works today with
   pandorakit): take a 3D atmosphere — an RMHD simulation snapshot
   (Bifrost, MURaM, CO5BOLD) or any parametrized 3D structure — treat
   each vertical column as an independent 1D atmosphere, run the batch
   ([§14](#14-batch)), and assemble emergent intensity maps/spectra.
   This captures horizontal *structure* (what varies across the
   surface) but not horizontal *radiative transfer* (photons crossing
   columns). For lines forming in deep/dense layers 1.5D is often
   adequate; for chromospheric resonance-line cores it is known to
   overestimate contrast. PANDORA's PRD treatment per column is
   top-class, which makes PANDORA-1.5D a legitimate niche.
2. **Dedicated 3D NLTE codes** for true 3D transfer: **Multi3D**
   (Leenaarts & Carlsson), **RH / RH1.5D** (Uitenbroek; Pereira &
   Uitenbroek — RH1.5D is exactly the columnwise mode above with
   modern PRD), **PORTA** (Štěpán & Trujillo Bueno, polarized).
   The mature workflow in the field: RMHD model (Bifrost/MURaM) →
   Multi3D/RH for the 3D NLTE spectrum. If your science demands true
   3D chromospheric line formation, plan to *migrate* to these rather
   than extend PANDORA.
3. **A sane division of labor**: use PANDORA for what it is uniquely
   good at — semi-empirical 1D modeling with PRD, diffusion,
   energy-balance chromospheres, spherical/expanding cases; use its
   converged models as physical insight and starting structures; do 3D
   with the 3D codes. pandorakit's parsers make the handoff (models
   and profiles as arrays) trivial.

## 18. Citing and further reading

* Code: Avrett, E. H., & Loeser, R. 2003, in ASP Conf. Ser. 288,
  *Stellar Atmosphere Modeling*, 303 (the PANDORA description paper).
* Applications: Vernazza, Avrett & Loeser 1981, ApJS 45, 635;
  Fontenla, Avrett & Loeser 1993, ApJ 406, 319; Avrett & Loeser 2008,
  ApJS 175, 229.
* This port + tooling: cite the pandorakit repository (patches, build
  recipe, wrapper) alongside the code papers, and state compiler +
  flags for reproducibility (they are recorded in each run's
  `EXECUTION DATA` section and the `run_archive.txt`).

---

*Manual written July 2026 for PANDORA release 2.2.0 (program version
79.009), gfortran port. Corrections welcome — measure against wup.pdf,
which remains the authority.*
