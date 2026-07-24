# Lesson 6 — Chromospheres, winds, and weighing mass loss

*Goal: execute the full Mészáros-Avrett-Dupree (2009) program on a
real red-giant model: build/tune a chromosphere, add a wind, match
profile asymmetries, extract a mass-loss rate.*

## 6.1 The science question

Population II giants must lose mass on the RGB (horizontal-branch
morphology demands it), but *measuring* those rates is hard: the winds
are slow (≲ 20 km/s), cool, and barely below the escape speed. The
only accessible diagnostics for cluster giants are chromospheric line
profiles: Hα emission wings, blueshifted absorption cores, Ca II K
asymmetries (MAD09; Dupree et al. 1984 onward). Extracting Ṁ from
them requires exactly the machinery of lessons 2-5 — this lesson is
the payoff.

## 6.2 The MAD09 recipe, step by step

1. **Photosphere**: take a Kurucz model for (T_eff, log g, [Fe/H]) —
   the innermost ~12 depth points.
2. **Chromosphere**: attach a parametrized rise — temperature linear
   in log(column mass) from the T-minimum up to T_max at m ~ 10⁻⁵
   g cm⁻², sampled by ~50 points; cap with a thin transition region
   (last ~10 points, up to 2×10⁵ K). One free parameter: **T_max**
   (it controls the Hα emission-wing strength).
   `pandorakit.recipes.chromosphere_te_logm()` builds exactly this
   parameterization.
3. **Static NLTE runs** (15-level H; spherical, R ~ 70 R☉): tune
   T_max until emission wings match the observed strength.
4. **Add the velocity field** `VXS` with `DO ( EXPAND )`: outflow
   where the core forms (top), possibly inflow where the wings form;
   iterate against the observed core shift and B/R.
5. **Mass-loss rate**: Ṁ = 4π r² ρ(r) v(r) at the formation layer.

## 6.3 Hands on: a red giant with a wind

Demo 6's `leid` model *is* a red giant (R ≈ 84 R☉, 72 depths,
populated by an H run). The shipped Ca II deck even carries a
100 km/s wind. Run the three-case experiment:

```bash
python3 examples/velocity_mass_outflow.py     # ~3 min
```

Real output (gfortran build):

    case       core shift     B/R    annotations
    static        0.00 km/s   0.999  [Stationary; CRD]
    wind100      -0.47 km/s   0.999  [Moving...; CRD]
    deep15       -5.60 km/s   0.958  [Moving...; CRD]

Three lessons in one table:

* **static** — symmetric self-reversed emission: your lesson-1/3
  physics, quantified;
* **wind100** — 100 km/s of wind *above* the formation region:
  nearly invisible in the line. Where a line forms decides what it
  can see (lesson 2's τ-ladder, now for velocities);
* **deep15** — 15 km/s *through* the chromosphere: core blueshift
  −5.6 km/s, B/R < 1. Note the factor ~2.7 between true wind speed
  and measured shift — MAD09 found exactly this ("higher velocities
  were necessary in the models in every case").

The script ends with Ṁ estimates layer by layer; at the
upper-chromospheric wind layers it lands at ~6×10⁻⁹ M☉/yr — the
MAD09 ballpark (their grid: 0.6-5×10⁻⁹).

## 6.4 Your turn: fit a "star"

Instructor preparation: pick a wind (v_top ∈ [5, 25] km/s, i_zero ∈
[45, 60]), run it, and hand students only the resulting profile CSV
("the observation").

Student task (the actual MAD09 workflow):

1. measure core shift and B/R of the "observation";
2. hypothesize (v_top, i_zero); run; compare; iterate (2-4 rounds
   converge nicely);
3. report Ṁ with an honest error bar from your bracketing runs;
4. (harder) also perturb T_max via the GUI's T(z) editor and report
   how much it pollutes your Ṁ — this degeneracy is the real error
   bar of the literature.

## 6.5 What makes this legitimate science (and what doesn't)

Legitimate: the *differential* diagnostics (shift, B/R vs wind depth
and speed) are robust; the NLTE machinery is the same that built the
standard solar models; PRD/spherical/velocity physics is
state-of-the-art 1D.

Fragile: uniqueness (several (T_max, v) pairs fit similar profiles —
MAD09 mitigate with multiple lines), homogeneity (a single 1D column
for a convective, spotted giant), stationarity (their own data show
factor-6 variability in 18 months!). Carry these doubts into
lesson 7.

## Exercises

1. ★ Why does an outflow above the line-forming region leave the
   profile almost unchanged, while the same speed *inside* it shifts
   the core by less than the full v/c?
2. Run the 6.4 fitting game.
3. Switch the Ca II K run from CRD to PRD (`SCH 5 1 ( 1 )` via
   `recipes.set_redistribution`; note demo 6's deck ships with the
   PRD lines commented out — the authors left the knob for you). How
   much do core shift and B/R move? Would MAD09's Ṁ change outside
   its error bar?
4. Estimate the wind's kinetic-energy flux 0.5 Ṁ v² for your best
   fit and compare with the star's luminosity — why "weighing the
   wind" is easier than "driving the wind" (which nobody has computed
   from first principles for these stars).

**Answers (1):** above the formation region τ_line ≪ 1: photons are
already decoupled — a moving transparent medium neither absorbs nor
emits significantly. Inside, the emergent core is an integral over
layers moving at 0...v_top; the centroid reflects an
opacity-weighted *average*, always below the peak speed.
