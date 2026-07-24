# Lesson 2 — Radiative transfer: the grammar of starlight

*Goal: own three tools — optical depth, the source function, and
Eddington-Barbier — well enough to predict line shapes qualitatively
before any computer runs.*

## 2.1 Specific intensity and its bookkeeping

The specific intensity I_ν(direction) [erg cm⁻² s⁻¹ Hz⁻¹ sr⁻¹] is the
fundamental quantity (HM15 §3.1); PANDORA's printouts label it `I/Hz`,
with `I/A` the per-wavelength version and TB the equivalent
"brightness temperature" (the T of a blackbody as bright at that ν).
Along a ray, photons are removed (absorption, scattering out) and
added (emission, scattering in):

    dI_ν/ds = −χ_ν I_ν + η_ν .

χ_ν [cm⁻¹] is the extinction coefficient; η_ν the emissivity.

## 2.2 Optical depth and the source function

Two definitions turn the transfer equation into intuition:

    dτ_ν = −χ_ν ds        (optical depth: distance in units of
                           photon mean free paths, counted downward)
    S_ν  = η_ν / χ_ν      (source function: what the gas emits per
                           unit of its own absorption)

    μ dI_ν/dτ_ν = I_ν − S_ν .

* τ_ν ≪ 1: transparent — you see through the layer.
* τ_ν ≈ 1: the "photospheric" surface at that frequency.
* τ_ν ≫ 1: opaque — information from below is erased.

In **LTE** (valid where collisions dominate, i.e. deep, dense layers),
S_ν = B_ν(T), the Planck function at the *local* temperature
(HM15 §4.5). The whole art of lesson 3 is what happens when that
fails.

## 2.3 Eddington-Barbier: the theorem behind lesson 1

The formal solution of the transfer equation, evaluated at the top of
a semi-infinite atmosphere, gives approximately (exact for S linear
in τ; HM15 §11.5, G22 ch. 7):

    I_ν(μ) ≈ S_ν(τ_ν = μ) .

The emergent intensity at each frequency ≈ the source function one
optical depth down *at that frequency*. Since line-center opacity ≫
wing opacity ≫ continuum opacity, scanning across a line profile scans
S (and in LTE, T) across geometric heights. Every profile you compute
this week is this theorem wearing different clothes.

**Limb darkening** falls out for free: smaller μ (slanted view) →
τ = μ is higher up → cooler S → darker limb.

## 2.4 Where lines come from

Within a line, χ_ν = κ_L φ(Δν) + χ_c: line opacity with normalized
profile φ riding on the continuum opacity χ_c. The line core (φ max)
forms highest; the wings slide down toward the continuum-forming
layer. An absorption line is S(high) < S(deep) viewed through this
τ-ladder; an emission feature is the reverse. You already believe
this from lesson 1 — now it is quantitative.

## Exercises

1. ★ In a layer where S decreases outward everywhere (pure
   photosphere), can any part of a line be in emission at disk
   center? What about at the limb, μ → 0?
2. Verify Eddington-Barbier against a real calculation. Run demo 1
   (lesson 5 shows the mechanics; today just execute):

       cd ~/pandora/pandorakit
       python3 examples/run_demo1.py

   Then, in the produced `.aaa` printout, find section `WAVE SUMM 1`
   and locate, for a continuum wavelength near 5000 Å, the depth where
   τ = 1; compare the printed TB with the model's TE at that depth
   (`ATMOSPHERE` section).
3. PANDORA prints, for every computed wavelength, the depth index
   where τ_ν = 1 (columns in the continuum summaries). Use the
   `pandorakit sections` / `extract` commands to pull `WAVE SUMM 1`
   into a text file and plot "formation depth vs wavelength" around
   the Lyman jump. Explain the jump in the plot.

**Answers (1):** no — with S monotonic decreasing outward, I(μ) =
S(τ=μ) is always below the neighboring continuum's S(τ=μ) taken at
its (deeper) surface; lines are absorption at every μ. Emission
requires S to increase outward somewhere (chromosphere) or geometric
effects (off-limb).
