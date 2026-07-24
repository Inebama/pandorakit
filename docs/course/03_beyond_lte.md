# Lesson 3 — Breaking LTE: scattering, the two-level atom, and why chromospheric lines lie

*Goal: understand — with one equation — why the center of Ca II K is
dark even where the chromosphere is hot, and what "non-LTE" actually
buys us.*

## 3.1 What LTE assumes and where it dies

LTE assumes the gas particles' level populations follow
Boltzmann/Saha statistics at the local kinetic temperature — true when
**collisions** dominate transitions. Radiation, however, has a mean
free path far longer than particle mean free paths (HM15 ch. 14), so
photons couple distant layers: the radiation field at one height
"remembers" conditions where it was born, not where it is absorbed.
High in an atmosphere, densities drop, collisions become rare, and
level populations are set by this *nonlocal* radiation → LTE fails
exactly where chromospheric lines form.

The bookkeeping of non-LTE is **statistical equilibrium**: for each
level i of each atom, the rates in = rates out,

    Σ_j n_j (R_ji + C_ji) = n_i Σ_j (R_ij + C_ij),

with radiative rates R (which depend on the radiation field J̄, which
depends on populations everywhere — the great nonlinear, nonlocal
loop) and collisional rates C. PANDORA's core job is to close this
loop for multilevel atoms (Avrett & Loeser 2003). Departure
coefficients b_i ≡ n_i / n_i^LTE measure how far from LTE each level
sits — PANDORA prints them (`BD` tables), and lesson 5 plots them.

## 3.2 The two-level atom: the whole story in one line

For a single line (levels l, u) with complete redistribution, the line
source function becomes frequency-independent (HM15 §14.2, eq. 14.14),
and the statistical equilibrium collapses to the most quoted equation
of the field:

    S_L = (1 − ε) J̄ + ε B(T_e)

* J̄ = ∫ J_ν φ_ν dν: the profile-averaged mean intensity — the
  *radiation bath* in the line;
* ε: the **photon destruction probability** per interaction —
  essentially C_ul/(C_ul + A_ul + ...): the chance that an absorbed
  photon's energy is thermalized by a collision instead of being
  re-emitted (scattered).

Deep down (ε → 1): S_L → B: LTE recovered. High up (ε ~ 10⁻⁴...10⁻⁸
in chromospheric resonance lines): **S_L ≈ J̄** — the line does not
radiate the local temperature at all; it *scatters* whatever radiation
field is present.

## 3.3 Thermalization: how deep is "deep"?

A scattered photon random-walks until destroyed (probability ε per
scattering) or escaped. The **thermalization depth** — the depth from
which line photons still reach the surface while remembering B —
scales as Λ ≈ 1/ε for Doppler profiles (HM15 §14.3; longer for Voigt
wings). With ε = 10⁻⁶, layers down to τ_line ~ 10⁶ feed the emergent
core: enormous. Consequences:

* line cores are *darker* than LTE predicts (S_L ≈ J̄ < B near the
  surface: photons leak out, J̄ drops below B — "photon losses");
* the dark K₃ center of Ca II K is **not** a cool layer — it is
  scattering; brightness temperature ≠ temperature (the resolution of
  lesson 1's puzzle);
* conversely, radiation from the deep photosphere can *boost* lines
  high up (RU12 call this backradiation — lesson 7).

## 3.4 What "solving" non-LTE means in practice

Given T(z), n(z): iterate {statistical equilibrium ↔ radiative
transfer} until populations, J̄, and S stop changing. PANDORA does
this with an equivalent-two-level-atom formulation per transition
plus net-radiative-bracket (ρ) accounting between them (wup §12, §20;
HM15 §14.4 describes the same family of methods) — its iterations are
literally the loop you now understand. When you watch `RHO AND RBD`
consistency checks approach 1 in lesson 5, that is statistical
equilibrium converging before your eyes.

## Exercises

1. ★ Order these lines from "most LTE-like" to "most
   scattering-dominated" and justify with ε and formation depth:
   Fe I 6173 (photospheric), Hα core (chromospheric, giant),
   Ca II K₃, Mg II k₃.
2. From the demo-2 run of lesson 5 you will have `demo2h.pop.001`
   with `BDH j` tables (H departure coefficients b_j). Plot b₁ and b₂
   vs depth (Deck parsing:
   `Deck.read(...).get("BDH 1").array(25)`). Where is b₁ ≫ 1?
   Explain with §3.3 (hint: photon losses in Lyman continuum drive
   overpopulation of the ground state high up).
3. Estimate ε for Hα in a red-giant chromosphere: n_e ~ 10⁹ cm⁻³,
   C_ul ≈ n_e q with q ~ 10⁻⁸ cm³ s⁻¹, A_ul = 4.4×10⁷ s⁻¹. Then
   estimate the thermalization depth 1/ε and comment on why the Hα
   core "feels" the upper chromosphere and wind, not the local
   photosphere.

**Answers (1):** Fe I 6173 (dense formation, high ε, S≈B) → Hα giant
core (ε small; partially collisional via n_e-sensitive upper levels) →
Ca II K₃ ≈ Mg II k₃ (resonance scattering, tiny ε, S≈J̄; Mg II k
forms even higher). **(3):** ε ≈ C/(C+A) ≈ 10/4.4×10⁷ ≈ 2×10⁻⁷;
thermalization depth ~ 1/ε ~ 5×10⁶ in line optical depths — the core
is radiatively controlled over its entire formation region.
