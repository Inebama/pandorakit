# Lesson 7 — What we swept under the rug (seminar)

*Goal: criticize everything from lessons 1-6 like a referee, using
RU12 as the guide; know the code landscape and where 1D semi-empirical
modeling stands today.*

## 7.1 Reading for this session

* Rutten & Uitenbroek 2012, A&A 540, A86 (**RU12**) — all of it.
* MAD09 §5 (the discussion you now have the tools to interrogate).

## 7.2 RU12's four punches, in course language

1. **Non-uniqueness is real.** Two published solar models (AL-C7,
   FCHHT-B) fit the same UV atlases with *different* stratifications
   and different physics for chromospheric support (turbulent pressure
   vs non-gravitational acceleration). Fitting a spectrum with a 1D
   T(z) is not an inversion with a unique answer — remember your
   lesson-1 exercise 3 and your lesson-6 error bar.
2. **Check claims with formation physics.** RU12 demolish a published
   claim (TR backradiation controlling minority ionization at the
   temperature minimum) by *computing where the relevant continua
   actually form* — pure lesson-2 contribution-function reasoning.
   Moral: every "the model says X" must survive a τ≈1 cross-check.
3. **Hα is a scattering telescope pointed down.** In the standard
   models Hα's chromospheric core photons are mostly *created in the
   deep photosphere* and scattered up across an "opacity gap"
   (lesson-3 physics at its purest). Lines with similar-looking cores
   can have utterly different photon economies (compare Ca II K:
   locally coupled; Hα: backradiation-fed).
4. **The real chromosphere is not a stratification.** At modern
   resolution it is fibrilar, magnetic, and shocked; non-equilibrium
   simulations show cool post-shock phases with departure
   coefficients up to 10¹² — static 1D models are *averages of an
   intrinsically dynamic thing*, and some observables punish that
   average badly.

Discussion prompts: Which of the four hits MAD09 hardest? (The
factor-6 time variability of K757 suggests #4 bites.) Which does the
*differential* nature of the Ṁ diagnostics partially dodge?

## 7.3 The code landscape (so you can place PANDORA)

| code | geometry | strengths | typical use |
|---|---|---|---|
| **PANDORA** | 1D pp/spherical | PRD pedigree, diffusion, winds, energy balance; the VAL/FAL/MAD09 machine | semi-empirical modeling, extended/expanding atmospheres |
| **MULTI** (Carlsson) | 1D | fast multilevel ALI standard | NLTE line formation on given models |
| **RH / RH1.5D** (Uitenbroek; Pereira) | 1D / columns of 3D cubes | modern PRD, overlapping transitions; RU12's instrument (deliberately configured to match PANDORA-class setups) | today's default for chromospheric diagnostics |
| **Multi3D** | full 3D | true 3D NLTE transfer | line formation in MHD simulation cubes |
| **PORTA** | 3D, polarized | scattering polarization, Hanle/Zeeman | "second solar spectrum" science |
| RMHD engines: **Bifrost, MURaM, CO5BOLD** | 3D, time-dep. | make the dynamic atmospheres | provide the cubes the above analyze |

The modern pipeline for chromospheres is RMHD cube → RH1.5D/Multi3D.
The pandorakit `batch` module gives you the *1.5D pattern* with
PANDORA physics (columns in parallel) — pedagogically ideal; for
production 3D work, migrate to the dedicated codes. What 1D
semi-empirical modeling still does best: extended and expanding
atmospheres of evolved stars (spherical PRD with winds — precisely
lesson 6), irradiance/reference models, and *insight* — every term in
its equations is inspectable, which is why a course like this one is
possible at all.

## 7.4 Capstone options (pick one, present in 15 min)

1. **1.5D experiment**: take 5-10 columns that differ in T_max
   (grid via `batch_grid.py`), average their Ca II K profiles, and
   compare the average-of-profiles with the profile-of-the-average
   model. Which lesson-3/4 nonlinearity makes them differ? (This is
   RU12's punch #4 in miniature.)
2. **Backradiation hunt**: in the demo-5 sunspot output, use the
   line source-function printouts (`LINE (u/l)` sections, S vs B
   columns) to find where S decouples from B for Lyδ vs Hα-like
   transitions; relate to RU12 §6.
3. **Atomic-data sensitivity**: update Ca II A-values per
   [../ATOMIC_DATA.md](../ATOMIC_DATA.md) (−4 %), rerun lesson 6's
   fit, and report the Ṁ shift vs the T_max degeneracy. Which
   uncertainty budget dominates?
4. **Code-comparison proposal** (paper exercise): design — do not
   run — a PANDORA vs RH1.5D benchmark for the MAD09 problem: which
   quantities would you compare, at which depths, and what would
   constitute agreement? (RU12's setup section is your template.)

## 7.5 Where to go next

HM15 chs. 13-15 & 18-20 (the numerics you now have intuition for);
G22 for observational technique; Leenaarts (2020, LRSP) for
non-equilibrium chromospheric modeling; Carlsson, De Pontieu &
Hansteen (2019, ARA&A) for the modern chromosphere. And the PANDORA
writeup (`wup.pdf`) — 368 pages of one perfectionist documenting one
instrument for 40 years: worth an afternoon regardless of which code
you end up using.
