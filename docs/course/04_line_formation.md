# Lesson 4 — Line profiles: broadening, redistribution, and motion

*Goal: read profile shapes mechanically — core, wings, asymmetries —
and know when the CRD simplification of lesson 3 breaks (PRD), and
what a velocity field does.*

## 4.1 The absorption profile: Doppler core, damping wings

The line extinction profile φ(Δν) is a **Voigt function** (HM15 ch. 8,
§14.2; G22 ch. 11): a Gaussian core from thermal + microturbulent
motions,

    ΔνD ∝ (2kT/m + v_turb²)^(1/2) ,

convolved with a Lorentzian of damping parameter a from natural,
van der Waals, Stark, and resonance broadening. PANDORA takes these as
per-transition constants `CRD, CVW, CSK, CRS` (see them in any `.atm`
file; wup §16 gives the exact damping formula) and the
micro-turbulence as the depth-dependent `V`/`VT` tables — *note the
historical naming trap: PANDORA's `V` is a broadening velocity, not a
flow!* Flows are `VXS`/`VX` (lesson 6).

Rules of thumb: Doppler core dominates within ~3 Doppler widths;
damping wings beyond. Wings form deep (small opacity → see far down),
core forms high.

## 4.2 CRD vs PRD: does a scattered photon forget its frequency?

Lesson 3 assumed **complete redistribution** (CRD): the re-emitted
photon's frequency is drawn afresh from φ — total amnesia per
scattering. Good when collisions reshuffle the excited state
(photospheric lines, subordinate lines). But in strong **resonance
lines** high in a chromosphere, an atom re-emits before any collision:
wing photons scatter nearly *coherently* (in the atom frame). That is
**partial redistribution** (PRD; HM15 ch. 10 & 15): the wings decouple
from the core and behave like an almost-coherent scattering continuum,
with a source function well below the CRD one.

Observable consequence: CRD overpredicts the inner-wing emission of
Mg II h&k, Ca II H&K, Lyα. **In PANDORA**: CRD is the default; PRD is
switched per transition with `SCH u l ( 1 )` (wup §15; the demo decks
show `GMMA`, `XC`, `XR` fine-tuning). Run the comparison yourself:

    python3 examples/prd_vs_crd.py

On demo 4's Mg II k line this prints (real output, gfortran build):

    DL [A]      I_PRD        I_CRD     CRD/PRD
     0.151   1.966e+05    2.253e+05      1.15
     0.324   1.987e+05    3.936e+05      1.98
     0.432   1.250e+05    2.874e+05      2.30
     0.811   4.879e+04    1.309e+05      2.68

— a factor ~2-2.7 in the inner wings: this is why PRD machinery
exists, and why PANDORA (whose PRD treatment is one of its crown
jewels) stayed relevant for decades.

## 4.3 Velocity fields: profiles as velocimeters

A macroscopic flow v(z) Doppler-shifts the *local* absorption/emission
by Δλ = λ v_proj/c (wup §16 gives PANDORA's exact implementation).
Three regimes matter to us:

1. **Flow confined above the formation region** → almost no effect on
   the line (photons are already free). You will *prove* this in
   lesson 6: a 100 km/s wind above the Ca II K formation layers moves
   the core by only −0.5 km/s.
2. **Flow through the formation region** → the core (formed highest)
   shifts toward the observer for outflow (blueshift), and the
   *asymmetry* between blue and red emission peaks (B/R) encodes where
   the flow sits relative to each feature's formation depth. MAD09's
   fitting logic: B/R < 1 ⇒ outflow in the wing-forming region;
   blueshifted core ⇒ outflow at the top.
3. **Strong, extended winds** → P Cygni morphology (blueshifted
   absorption trough + redshifted emission).

A subtlety with teeth (MAD09 found it empirically; you will reproduce
it): the measured core shift *underestimates* the flow speed —
in our red-giant demo a 15 km/s wind produces a −5.6 km/s core shift.
Profiles integrate over the formation region; only part of it moves at
peak speed.

## Exercises

1. ★ Why do damping wings form deeper than the Doppler core even
   though both belong to the same transition?
2. Run `examples/prd_vs_crd.py`; overplot the two profiles from the
   PNG or by parsing with `AaaFile(...).profile(2,1)`. Where do the
   PRD and CRD profiles agree, and why exactly there? (Two places —
   different reasons.)
3. Take the demo-4 CRD run and double the microturbulence: with
   `Deck`, read `demo4.mod`, inspect which statement carries the
   broadening velocity, double it, rerun, and measure the K-line core
   width. Which parts of the profile respond?

**Answers (1):** wing opacity is ~10²-10⁴ times smaller than core
opacity, so τ_wing = 1 lies geometrically deeper — same τ-ladder logic
as lesson 2. **(2):** at line center (both are core-photon dominated,
S≈J̄ locally) and in the far wings (both approach the continuum /
line-free background); the disagreement is the inner wing, where CRD
couples wing photons to the core reservoir but coherent scattering
does not.
