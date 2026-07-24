# The PANDORA atomic data: age, quality, and how to update it

Short answer: **the shipped atomic models are 1987–2006 vintage; the
quantities that dominate chromospheric line profiles are still good to
a few percent; the weakest ingredients are collision rates for metals.
Everything is updatable by editing plain-text `.atm` files, and this
page shows how to do it safely.**

## What ships

97 model atoms in `v2.1.1/atoms/` (same statement language as all
PANDORA input). Header comments record their history — e.g. `hl15.atm`
(1992–2006), `ca2l5.atm` ("Modified by Pablo Mauas 1988/1989, new
recombination data 2000"), `mg2l8.atm` ("reviewed... 2005"),
`fe1l15.atm` (1987–1997). These are the atoms behind the VAL/FAL-era
literature, including Mészáros, Avrett & Dupree 2009.

## How the shipped values compare with current references

* **Hydrogen is special-cased**: `hl15.atm` contains *no* explicit
  A-values or cross sections — PANDORA computes hydrogenic radiative
  data internally (exact quantum results). H is effectively always up
  to date; the H `.atm` files mainly define the level/transition
  structure, collision-rate tables, and broadening constants.
* **Resonance-line A-values (spot check against NIST ASD 2024):**

  | line | shipped | NIST | diff |
  |---|---|---|---|
  | Mg II k 2796 (`A 2 1`, mg2l8) | 2.616e8 | 2.60e8 | +0.6 % |
  | Ca II K 3934 (`A 5 1`, ca2l5) | 1.41e8 | 1.47e8 | −4 % |
  | Ca II H 3968 (`A 4 1`, ca2l5) | 1.41e8 | 1.46e8 | −3 % |

  A few percent in A translates to smaller-than-that changes in
  computed profiles (opacity scales, but chromospheric emission is
  controlled mostly by T(z), n_e and the velocity field). For mass-loss
  work in the Mészáros style these differences are far below the
  fitting uncertainties.
* **Collision rates (CE/CI tables) are the true vintage part**: they
  come from 1970s–1990s compilations (van Regemorter-style scaling,
  early close-coupling results). Modern R-matrix rates (e.g. for Ca II,
  Mg II, He I) differ by tens of percent in places. They matter most
  where densities are high (photosphere) and for subordinate lines;
  resonance-line cores in low-density chromospheres are
  scattering-dominated (photon-controlled, not collision-controlled),
  which is why the vintage is more benign than it sounds.
* **Abundances**: the run's metal abundances are set by PANDORA's
  internal element data (wup §10) scaled by your `ABD`/metallicity
  inputs — review them for any non-solar star (as Mészáros et al. did
  with [Fe/H] scaling).

## Updating an atom file (safe procedure)

1. Copy the shipped file: `cp atoms/ca2l5.atm atoms/ca2l5u.atm` — never
   edit in place; the demos regression-test against the originals.
2. Replace values with cited modern ones:
   * A-values, level energies: NIST ASD (<https://physics.nist.gov/asd>);
   * collision strengths: CHIANTI database / OPEN-ADAS effective
     collision strengths, converted to PANDORA's `CE u l` tables on the
     `TER` temperature grid (CE is the downward collisional rate
     coefficient table; check wup §5 for the exact convention and
     units via the `params` search: `pandorakit params CE CI TER`);
   * photoionization cross sections: `CP` per level (TOPbase/NORAD).
3. Keep the structure statements (`NL`, `NT`, `INPAIR`, `MR`, `LR`,
   `RUNTOPOP`) untouched unless you are redesigning the level scheme.
4. Validate cheaply: run an input-only pass (`DO ( JSTIN )`) and read
   the `ATOM` and `INPUT NOTES` sections of the printout; then a
   2-iteration comparison run against the unmodified atom
   (`pandorakit run ... --atm atoms/ca2l5u.atm`) to see the effect.
5. Record the source of every number in `>` comment lines in the file —
   that is exactly what Loeser/Avrett/Mauas did, and it is why we can
   audit these files 35 years later.

## Practical recommendation

For the red-giant Hα / Ca II mass-outflow program: the shipped `hl15`
(H internal data) and `ca2l5` atoms are scientifically adequate —
Mészáros et al. 2009 published with effectively these files. If you
want belt-and-braces, update the two Ca II H&K A-values to NIST (−4 %)
and, if He 10830 becomes part of the program, treat `he1*` collision
data as the first thing to modernize. Any update is a per-file, fully
documented text edit — no code changes involved.
