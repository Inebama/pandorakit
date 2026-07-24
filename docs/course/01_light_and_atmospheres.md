# Lesson 1 — Starlight and stellar atmospheres

*Goal: stop seeing a spectrum as a curve, and start seeing it as a
map of depth into a star.*

## 1.1 The only thing we get

Almost everything we know about any star arrives as a spectrum:
intensity versus wavelength. A star has no surface you could stand on —
what we call "the surface" is the thin shell where the gas becomes
transparent, and *that shell sits at a different depth for every
wavelength*. This is the single most important idea of the course:

> **A spectrum is a scan through the atmosphere.** Wavelengths where
> the gas absorbs strongly show you high, usually cooler layers;
> wavelengths where the gas is transparent let you see deep, hot
> layers. Reading a spectrum = reading temperature (and velocity, and
> density) as a function of depth.

A blackbody curve has no such structure; a real star deviates from it
exactly because different wavelengths escape from different depths
(G22 ch. 1; HM15 ch. 2).

## 1.2 Anatomy of a late-type stellar atmosphere

Working upward (density falling roughly exponentially):

* **Photosphere** — where the visible continuum escapes. Temperature
  *falls* outward (energy flows out), e.g. ~6500→4400 K in the Sun,
  ~4500→3200 K in a K giant. Most absorption lines form here.
* **Temperature minimum** — the coolest layer (~4400 K solar).
* **Chromosphere** — temperature *rises* outward again (mechanical/
  magnetic heating that we still cannot compute from first principles;
  in semi-empirical work it is *measured*, not predicted). Strong-line
  cores (Ca II H&K, Mg II h&k, Hα in giants) and many emission
  features form here.
* **Transition region** — a thin wall where T jumps from ~10⁴ to 10⁶ K.
* **Corona / wind** — hot, tenuous, expanding.

The photosphere of a red giant is a few thousand km thick; its
chromosphere can extend for a stellar radius or more. That geometric
extension is why giants show chromospheric *emission* so prominently —
and why we will need spherical geometry in lesson 6.

## 1.3 Why chromospheres put lines "in emission"

In the photosphere, T falls outward, so line cores (formed high) are
*darker* than the neighboring continuum (formed deep): absorption
lines. Wherever the line core samples the chromospheric temperature
rise, the core source region is *hotter* than the layers just below
it → emission features: the double peaks flanking the Ca II K core,
the emission wings of Hα in metal-poor giants (MAD09), the reversal at
the center of Mg II k. In lesson 2 this intuition becomes a theorem
(Eddington-Barbier); for now it is our working picture.

## 1.4 The cast of characters for this course

* **The Sun**: the calibration lab. VAL/FAL "standard models" (built
  with PANDORA) describe its average atmosphere.
* **Red giants in globular clusters** (M13, M15, M92): our science
  targets. Their Hα profiles show emission wings and *blueshifted*
  cores — gas flowing out at km/s speeds — and by the end of the week
  you will turn those asymmetries into mass-loss rates, following
  MAD09.

## Exercises

1. ★ The solar photosphere emits roughly as a 5800 K blackbody, the
   chromospheric Ca II K₂ emission peaks correspond to brightness
   temperatures near 4400-5000 K, and the K₁ minima to ~4200 K. Sketch
   I(λ) around 3933 Å and annotate which *depth* each feature samples.
2. Look at the temperature structure of a real model: with the GUI
   (`pandorakit gui` → Model editor → load
   `~/pandora/v2.1.1/demos/6/leid.mod`). Identify photosphere,
   temperature minimum, chromosphere, transition region. Note N=72
   depth points — count how many the modelers spent on each region,
   and explain their choice.
3. Discussion: why can we *not* infer a unique T(depth) from a single
   line profile? (Keep your answer; lesson 7 returns to it.)

**Answers (1):** the K-line wings (photospheric) trace the ~5800 K
continuum falling toward the core; K₁ minima ~4200 K sample the
temperature minimum; K₂ peaks sample the lower chromosphere's rise;
the central K₃ dip samples the higher, scattering-dominated
chromosphere (that one needs lesson 3 — its darkness is *not* a
temperature).
