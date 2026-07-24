# PANDORA inputs: the complete practical reference

*Everything PANDORA reads, what is mandatory, and the exact structure —
with a line-by-line annotated real case. Companion to MANUAL.md §§4-8;
authoritative source: wup.pdf §§1-5, 19, 99.*

---

## 1. The files a run consumes

A PANDORA run reads up to **9 files**. Four are yours; the rest ship
with the installation and you never edit them:

| you write | unit | role | required? |
|---|---|---|---|
| `CASE.dat` | 3 | run controls; **reading always starts here** | **always** |
| `MODEL.mod` | 4 | the atmosphere | if the .dat says `USE ( MODEL )` |
| `ATOM.atm` | 7 | the model atom | if the .dat says `USE ( ATOM )` |
| `CASE.res` | 8 | restart data (previous run's `.rst`) | if `USE ( RESTART )`; an *empty file* is legal and means "start from scratch" |
| `CASE.jnu` | 9 | PRD J̄ restart (previous `.jnr`) | only for PRD runs |

| shipped | unit | role |
|---|---|---|
| `opacities/statistical.dat` | 10 | statistical background line opacity |
| `opacities/composite.dat` | 11 | composite background line opacity |
| `opacities/average.dat` | 12 | averaged background line opacity |
| `run_archive.txt` | 28 | performance log (append; may start empty) |

The split of your input across .dat/.mod/.atm/.res is **pure
convention** — demo 1 puts everything in one .dat. The point of the
split (wup §99): the same `.mod` serves many ions, the same `.atm`
serves many stars. pandorakit's `PandoraRun` wires all files to their
units for you; you only ever choose *content*.

## 2. One language for everything

Every file above (including PANDORA's own outputs `.rst/.pop/...`)
uses the same statement language:

```
NAME idx... ( values ) >        [ a comment needs inner blanks ]
```

with value-list controls `M m` (multiplier), `I i` (jump to element
i), `R r` (repeat next value r times), `S` (skip = keep default),
`F v` (fill the rest with v); `>` = ignore rest of line; `GO` = end of
an input Part; 80-column limit. Full grammar: MANUAL.md §4.

**Statement forms** — every parameter in the reference (and in
`pandorakit params NAME`) carries a *form code* telling you the exact
index pattern (wup §2):

| form | pattern | example |
|---|---|---|
| 1 | `NAME ( q )` — one scalar | `IOMX ( 11 )` |
| 1* | `NAME z ( q )` — scalar at depth z | `TRAD 5 ( 4500. )` |
| 2 | `NAME ( q q q ... )` — plain array | `TE ( ... )` |
| 2* | `NAME Z z ( q ... )` — array starting at depth z | `VXS Z 30 ( ... )` |
| 3 | `NAME k ( q ... )` — array per level k (or per depth) | `HN 2 ( ... )`, `CI 1 ( ... )` |
| 3* | `NAME k Z z ( q ... )` — per level, from depth z | |
| 4 | `NAME u l ( q )` — scalar per transition (u>l) | `A 3 2 ( 4.41E7 )`, `SCH 2 1 ( 1 )` |
| 5 | `NAME u l ( q ... )` — array per transition | `CE 3 2 ( ... )` |
| 5* | `NAME u l Z z ( q ... )` — per transition, from depth z | |
| 6 | `WEIGHT u l ( m n w )` — sublevel term weights | |
| 7/8 | `NAME u l k ( ... )` — per transition and per μ-index | `LSFPRINT 3 2 1 ( 1 )` |

In the parameter database the `codes` field reads like `D, 2*,2, flpt`
= "Part D; forms 2* or 2; floating point". `[N]`-type lengths mean
"one value per depth point".

## 3. The required minimum, file by file

### 3.1 `CASE.dat` — always required

Structure (Parts; wup §3):

```
line 1     HEADING          one free-text line (banner; always line 1)
Part B     lengths, options, switches            ... GO
Part D     the physics                           ... GO
Part F     spectrum-calculation parameters       ... GO
Part H     populations data                      ... GO
```

All four `GO`s must be present even when Parts are empty. `USE (...)`
statements route reading through .mod/.atm/.res at the points you
choose (see the annotated case below for the canonical routing).

Strictly required in the .dat itself: the HEADING, the `GO`s, and the
first `USE` (if any files beyond .dat are used). Everything else can
live in whichever file you prefer.

**Part-B ordering constraints** (violating them = input error):
`NT` before `INPAIR`; `NSL` (< 51) before `MR`/`LR`; `NL` < `NSL`;
`NAB` (< 100) before `BANDL/BANDU/BANDE`; `NMT` < 51; `NCL` < 100;
`NVX` < 100. **Part D**: per-transition `LDL` before that transition's
`DDL/CDL`/broadening; `KST/KBT/KRT` before `XISYMT/XIBLUT/XIREDT`.

### 3.2 Atmosphere (Group 1 — usually in `.mod`)

| statement | form | meaning | required |
|---|---|---|---|
| `N` | 1, int | number of depth points (Part B!) | **yes** |
| `Z` | 2 | heights [cm], index 1 = TOP (most negative), strictly increasing | **yes**¹ |
| `TE` | 2 | electron temperature [K] | **yes** |
| `NH` | 2 | total hydrogen density [cm⁻³] | **yes**¹ |
| `NE` | 2 | electron density [cm⁻³] | **yes** |
| `ZMASS` | 2 | column mass [g cm⁻²] | ¹alternative: `ZMASS`+`TE`+`NE` replaces `Z`+`NH` (PANDORA derives them) |
| `BDHM` | 2 | H⁻ departure coefficients | no (default 1) |
| `V` / `VR` | 2 | micro-turbulent broadening velocity [km/s] (⚠ not a flow!) | no |
| `VT` | 2 | turbulent velocity for pressure/HSE [km/s] | no |
| `VXS` | 2*/2 | expansion (wind) velocity [km/s, + outward]; needs option EXPAND | no |
| `NVH` | 1 | velocity-handling switch (`0` with V=0, cf. demo 1) | no |
| `R1N` | 1 | atmosphere thickness R(1)−R(N) [cm-scale; see wup §5] for spherical work | for SPHERE |
| `CGR` | 1 | gravity parameter | recommended |
| `NLH` + `NP`, `HN j`, `BDH j` | 1; 2; 3; 3 | hydrogen populations from a previous H run (Part H) | for restarts/chains |

### 3.3 Atom (Group 2 — usually in `.atm`)

Minimum that must be present or the run fails (wup §99, §19):

| statement | form | meaning |
|---|---|---|
| `NL` | 1 | number of bound levels (Part B; < NSL ≤ 50) |
| `NT` | 1 | number of radiative transitions (Part B) |
| `INPAIR` | 2 | the NT (u,l) pairs, e.g. `INPAIR ( 2 1  3 1  3 2 )` (Part B, after NT) |
| `ELSYM` | 1, alpha | element symbol, e.g. `( H )`, `( CA )` |
| `IONSTAGE` | 1 | ionization stage (1 = neutral) |
| `MASS` | 1 | atomic mass [amu] |
| `ABD` | 1 | abundance of the run's element (H = 1 scale) |
| `P` | 2 | level statistical weights g_i |

Plus, in practice (defaults exist but you nearly always supply):
`NAME` (`( HYDROGEN )` etc. — triggers special treatments!), `XNU`
(level energies [cm⁻¹] — hydrogenic ones computed internally), `CP`
(photoionization cross sections per level), `NTE` + `TER` (temperature
grid for collision tables), `CI k` (collisional ionization per level),
`CE u l` (collisional excitation per transition), `A u l` (Einstein A
— hydrogen: internal), broadening constants `CRD/CVW/CSK/CRS u l`
(+ `PW` if Stark `CSK` given), `RUNTOPOP` (level mapping for
population-update runs), `MR`/`LR` (sublevel structure). Detailed-
balance variants: `ktrans u l ( thick )` puts (u,l) in detailed
balance (the `db` atom files, bootstrap runs).

**Do not write atom files from scratch** — copy the nearest of the 97
shipped ones and edit (see ATOMIC_DATA.md).

### 3.4 Run controls (Group 4 — the `.dat` proper)

All have defaults; the ones you will actually set:

| statement | meaning |
|---|---|
| `IOMX ( n )` | overall iterations this run (default 1!) |
| `DO ( X )` / `OMIT ( X )` | switch option X on/off (~340 options; `OPTIONS` printout lists all states) |
| `POPUP ( NAME )` | make this a population-update run (H, HE1, ... the 12 background ions) |
| `RUNTOPOP ( ... )` | level mapping used by POPUP |
| `SCH u l ( 1 )` + `GMMA u l` | PRD for transition (u,l) (CRD is the default) |
| `DO ( EXPAND )` + `VXS` | expanding atmosphere (wind) |
| `DO ( SPHERE )` | spherical geometry |
| `DO ( HSE )` | hydrostatic equilibrium (recompute densities from T) |
| `DO ( JSTIN )` | input-only run — **always do this first with new input** |
| `KK ( k )` | number of ray directions / μ points (with `XK` table) |
| `WAVES ( ... )` | extra continuum wavelengths [Å] |
| `TRN k ( ... )` | radiation temperature table [K] for level k (used with option USETRIN; `TRN 2 ( I 23 5000. 5000. )` sets depths 23-24) |
| `DO ( SPECSAV )` | write emergent-spectrum data to the `.spc` file |
| `MU` / `MUF ( ... )` | μ values for intensity / flux profile printouts |

### 3.5 Restart (Group 3 — `.res`, `.jnu`)

Never written by hand: `.res` is the previous run's `.rst` renamed
(and `.jnu` ← `.jnr`). First run of a series: **supply an empty
`.res`** (pandorakit does this automatically when `res=None`).

## 4. A real case, annotated line by line

Demo 2 (the canonical 4-file layout). Files in
`~/pandora/v2.1.1/demos/2/`.

### `demo2h.dat` (unit 3 — reading starts here)

```
[ DEMO-2   3 L H, D.B.  ITER 01-02  28 OCT 87 ]   <- Part A: HEADING (line 1, free text)
KK ( 9 ) >              <- Part B: 9 ray angles (XK table comes later)
NVH ( 0 ) >             <- static treatment of the broadening velocity
USE ( MODEL ) >         <- switch reading to demo2.mod (Part-B piece: N)
USE ( ATOM ) >          <- then to hl3.atm (Part-B piece: NL, NT, INPAIR...)
DO ( LYMAN ) >          <- option: compute level-N-to-continuum transfer
OMIT ( PHASE2 ) >       <- option: skip phase-2 printout
DO ( USETRIN ) >        <- option: use input radiation temperatures (TRN)
GO >                    <- Part C: end of Part B
USE ( MODEL ) >         <- Part D: read the model's physics tables
USE ( ATOM ) >          <-         then the atom's physics data
USE ( RESTART ) >       <-         then demo2h.res (EMPTY = from scratch)
IOMX ( 2 ) >            <- 2 overall iterations
POPUP ( HYDROGEN ) >    <- population-update run for H
XK ( 1. 1.1 1.2 1.4 1.7 2.3 3. 5. 8. ) >   <- the 9 ray parameters
TRN 2 ( I 23 5000. 5000. ) >   <- radiation temperatures, transition 2
TRN 3 ( I 24 5300. 5300. ) >   <-   (used because USETRIN is on)
GO >                    <- Part E: end of Part D
GO >                    <- Part G: Part F is empty (no spectrum params)
USE ( MODEL ) >         <- Part H: give the model a chance to supply
GO                      <-   populations (none here) ... end of Part H
```

### `demo2.mod` (unit 4 — read in pieces, as the `USE`s above dictate)

```
[ ATMOSPHERE FOR DEMO-2 ] >    <- comment
N ( 25 ) >                     <- Part-B piece: 25 depths
USE ( INPUT ) >                <- hand control back to the .dat
[ ATMOSPHERE FOR DEMO-2 ] >    <- (reading resumes HERE on the 2nd USE ( MODEL ))
R1N ( 7.66E7 ) >               <- Part-D piece: thickness parameter
CGR ( 8.17E-4 ) >              <- gravity parameter
Z  ( >                         <- heights, cm; index 1 = top (z most negative)
-6.91000000E+08 -4.99000000E+08 ... 0.00000000E+00
) >
TE    ( M 1.E3 11.48 20.99 43.55 67.21 >    <- temperatures: M 1.E3 means x1000
51.96 40.93 ... 5.00 5.20 ) >               <-   (11480 K at top ... 5200 K at bottom)
NH ( M 2.E6 1.18 ... M 20. ... ) >          <- H densities; note multiplier changes mid-table
NE ( M 20. ... ) >                          <- electron densities
BDHM ( ... ) >                              <- H- departure coefficients
USE ( INPUT ) >                <- end of the Part-D piece
USE ( INPUT ) >                <- Part-H piece: nothing, hand back at once
```

### `hl3.atm` (unit 7) — 3-level hydrogen

```
NL ( 3 ) >                     <- Part-B piece: 3 bound levels
RUNTOPOP ( 1 2 3 0 ) >         <- level mapping for POPUP
NTE ( 5 ) >                    <- collision tables on 5 temperatures
NT ( 3 )  INPAIR ( 2 1  3 1  3 2 ) >   <- 3 radiative transitions (NT first!)
USE ( INPUT ) >
NAME ( HYDROGEN ) >            <- Part-D piece; NAME=HYDROGEN activates H special code
ELSYM ( H )  IONSTAGE ( 1 ) >
MASS ( 1. )  PART ( 0. ) >
ABD ( 1. ) >
PW ( 0.6666666666667 ) >       <- Stark exponent (needed because CSK given)
P ( 2. 8. 18. ) >              <- statistical weights 2n^2
CP ( M 1.E-17 .792 1.3 2.156 ) >   <- photoionization cross sections
TER ( M 1000. 5. 9. 15. 25. 35. ) >    <- the 5 temperatures (K)
CI 1 ( M 1.E-9 2.82 3.92 5.3 7.27 9.01 ) >   <- coll. ionization, level 1 (form 3)
CI 2 ( ... ) >  CI 3 ( ... ) >
ktrans 2 1 ( thick ) >         <- Ly-alpha in detailed balance ("D.B." in the heading!)
CE 2 1 ( M 1.E-8 2. 2. 1.9 1.8 1.8 ) >       <- coll. excitation (form 5)
ktrans 3 1 ( thick ) >  CE 3 1 ( ... ) >
A 3 2 ( 4.41E+7 )              <- H-alpha Einstein A (form 4)
CE 3 2 ( F 1.4E-6 ) >          <- fill: same value at all 5 temperatures
CRD 3 2 ( 6.5E-4 ) >  CVW 3 2 ( 4.4E-4 ) >   <- radiative + van der Waals damping
CSK 3 2 ( 1.174E-3 ) >  CRS 3 2 ( 8.98E-4 ) >   <- Stark + resonance
USE ( INPUT ) >
USE ( INPUT ) >
```

Read this section twice and you can read *any* PANDORA input,
including the code's own restart files.

## 5. How to know PANDORA understood you

1. **`DO ( JSTIN )`** — input-only run, costs seconds. Then read:
2. **`INPUT NOTES`** printout section — flags everything suspicious;
3. the **`.jrl` journal** — every statement echoed as read (diff two
   journals to find what changed between runs);
4. the **`OPTIONS`** section — final state of all ~340 options;
5. the **`ATMOSPHERE` / `ATOM`** sections — the tables as understood.
6. Input errors print the offending line with an `*` under the
   failing field; with DELABORT (default on) PANDORA collects several
   errors before stopping.

## 6. Doing all of the above from Python

You rarely hand-write these files: `Atmosphere` emits valid `.mod`s,
`Deck` edits any statement in place, `recipes.*` installs
winds/PRD/chromospheres, and `PandoraRun` wires files to units. See
docs/API.md for every function, and the tutorial notebook for the
full workflow in action.
