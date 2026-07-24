# Lesson 5 — Driving PANDORA

*Goal: run, modify, and read real non-LTE calculations. After today
the code is a lab instrument, not a black box.*

## 5.0 What you are driving

PANDORA (Avrett & Loeser, CfA, developed 1966-2014, ~4500 Fortran-77
routines) computes: multilevel statistical equilibrium + line/continuum
transfer with PRD, in 1D plane-parallel or spherical geometry, with
flows, diffusion, hydrostatic equilibrium... It built the standard
solar models (VAL/FAL) and the red-giant analyses we target. You drive
it through `pandorakit` (Python) or the GUI; the full manual is
[../MANUAL.md](../MANUAL.md).

Vocabulary (memorize these five):

* **deck (.dat)** — the run's control input, in PANDORA's statement
  language: `NAME ( values ) >`, parts separated by `GO`.
* **model (.mod)** — the atmosphere: depth grid + T, densities...
* **atom (.atm)** — the model atom: levels, transitions, rates.
* **printout (.aaa)** — the (large) human-readable output, split into
  indexed *print sections*.
* **restart files (.rst/.pop/.jnu...)** — outputs written *in the
  input language* so the next run can continue the iteration.

## 5.1 First contact (15 min)

```bash
cd ~/pandora/pandorakit
python3 examples/run_demo1.py      # 3-level H, 2 iterations, ~1 s
```

Open the run directory it prints, and look at three things:

1. `demo1none.aaa.*` — scroll it once end-to-end (it's a line-printer
   document; that's the historical genre). Find the `OPTIONS`,
   `ATMOSPHERE`, `LINE (3/2)`, `NE`, `SIGN-OFF` sections.
2. `pandorakit sections <the .aaa file>` — the section index.
3. The input `~/pandora/v2.1.1/demos/1/demo1none.dat` next to the
   `ATOM` printout section — match statements (`NL`, `INPAIR`,
   `A 3 2`, `CE 2 1`...) to what the code understood.

## 5.2 The language in five minutes

```
TE    ( M 1.E3 11.48 20.99 43.55 ... ) >   [ multiplier M ]
NE    ( 0. M 1.E1 1. 2. R 5 6. F 7. ) >    [ repeat R, fill F ]
A 3 2 ( 4.41E+7 ) >                        [ transition indices ]
DO ( LYMAN ) >   OMIT ( PHASE2 ) >         [ options on/off ]
GO >                                       [ end of input Part ]
```

In Python you never format this by hand:

```python
from pandorakit import Deck
d = Deck.read("SPh.dat", heading=True)
d.set("IOMX", 11)          # iterations
d.get("TE").array(72)      # any table as a list
d.write("SPh.dat")
```

## 5.3 A real chromospheric calculation (30 min)

Demo 5 is a sunspot umbra: 91 depths, 15-level hydrogen, PRD Lyman
lines, 11 iterations, ~7 min on a laptop. Launch it, then *while it
runs* watch the log's phase messages (Continuum Calculations → Rates →
Line Source Functions → NE Updating → ... per iteration) and map them
to the lesson-3 loop.

```python
from pandorakit import PandoraInstall, PandoraRun
install = PandoraInstall("~/pandora")
run = PandoraRun(install, case="SPh", run_id="c01",
                 dat=".../demos/5/SPh.dat", mod=".../demos/5/SP.mod",
                 atom=("h", 15), res=".../demos/5/SPh.res",
                 jnu=".../demos/5/SPh.jnu", workdir="runs")
res = run.execute(); print(res.ok)
```

Afterwards:

* `RHO AND RBD` section → consistency CHECKs ≈ 1? (convergence);
* `ITERATES` → iterative-ratio plots stabilizing?;
* plot Lyδ: `pandorakit profile <aaa> 5 1` or the GUI Results tab;
* `.pop` file → `BDH j` departure coefficients for exercise 3.2.

## 5.4 The GUI

`pandorakit gui` — load a model, drag T(z) (this is how semi-empirical
modeling *feels*: bend the chromosphere, rerun, compare), edit
velocity tables, launch runs, browse sections, plot profiles, search
all ~740 input parameters. Everything it writes is an ordinary file
you can also produce from Python — no lock-in.

## Exercises

1. ★ In demo 1's deck, `IOMX ( 2 )`. Change it to 6 (via `Deck`),
   rerun, and compare the `RK-1 Old/New` ratios and the CHECKs
   against the 2-iteration run. Converging toward what?
2. Break it on purpose: remove the `NE` statement from a copy of
   demo 2's model and run. Read the error report style (the `*` under
   the offending field / the missing-table complaint). Knowing failure
   modes is half of driving.
3. Population handoff: run demo-6's chain
   (`python3 examples/run_chain_demo6.py`) and diff `leid.mod` before
   and after the `@NE+` merge (`git diff --no-index` works). Exactly
   which tables did hydrogen update?
4. Departure coefficients: from 5.3's `.pop`, plot b₁, b₂, b₃ vs
   depth; annotate where each Lyman/Balmer line forms (use the
   formation-depth columns from the line sections) — you are now
   reading a non-LTE calculation like a professional.

**Answers (1):** ratios → 1 monotonically; the run converges toward
the self-consistent statistical-equilibrium solution — more overall
iterations ≈ more Λ-iteration-like sweeps of the lesson-3 loop.
