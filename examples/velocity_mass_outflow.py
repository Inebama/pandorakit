#!/usr/bin/env python3
"""
Velocity fields and mass outflow: the Meszaros-Avrett-Dupree workflow.

Demo 6's `leid` model is an extended RED GIANT chromosphere
(R ~ 84 R_sun per the comments in leid.mod, populations already
converged from an H run) -- the same kind of semi-empirical model used
by Meszaros, Avrett & Dupree 2009 (AJ 138, 615) to infer mass-loss
rates of globular-cluster giants from H-alpha and Ca II profile
asymmetries.

Three Ca II K (5/1, 3933.7 A) calculations:

  static   -- no expansion: symmetric double-peaked emission with a
              deep central self-reversal;
  wind100  -- the shipped 100 km/s wind, which lives ABOVE the K-line
              formation region (transition region): the core barely
              feels it (teaching point: lines only sense flows in the
              layers where they form);
  deep15   -- a Meszaros-style 15 km/s outflow through the chromosphere
              (the K-line forming layers): the core blueshifts by
              ~-6 km/s and the blue emission peak weakens (B/R < 1).

Note the model-vs-measurement factor: a 15 km/s flow produces only a
~6 km/s measured core shift -- Meszaros et al. found exactly this
("nearly a factor of 2 higher velocities were necessary in the models
in every case" compared to the observed bisector velocities).

Runtime: ~3 min (expanding runs use general ray tracing, ~70 s each).
"""

from pathlib import Path

from pandorakit import AaaFile, Atmosphere, Deck, PandoraInstall, PandoraRun
from pandorakit.recipes import (
    core_shift_and_asymmetry,
    mass_loss_rate,
    set_expansion,
    wind_ramp,
)

ROOT = Path.home() / "pandora"
DEMO = ROOT / "v2.1.1/demos/6"
WORK = ROOT / "runs" / "outflow"
R_STAR_RSUN = 84.0  # from the R1N comment in leid.mod
LINE_A = 3933.7  # Ca II K

install = PandoraInstall(ROOT)
base = Deck.read(DEMO / "leidca2.dat", heading=True)
model = Atmosphere.read(DEMO / "leid.mod")
n = model.n
print(f"model: {model}  (red giant, R ~ {R_STAR_RSUN} R_sun)")

# A Meszaros-style chromospheric outflow: 15 km/s, reaching zero at
# depth index 55 (i.e. flowing through the Ca II K formation layers).
deep15 = wind_ramp(n, v_top=15.0, i_zero=55, i_top=15)

cases = {
    "static": set_expansion(Deck.parse(base.dumps(), heading=True), None),
    "wind100": base,  # exactly as distributed (upper-atmosphere wind)
    "deep15": set_expansion(Deck.parse(base.dumps(), heading=True), deep15),
}

results = {}
for name, deck in cases.items():
    res = PandoraRun(
        install,
        case=f"ca2_{name}",
        run_id="001",
        dat=deck,
        mod=DEMO / "leid.mod",
        atom=("ca2", 5),
        res=DEMO / "leidca2.res",
        jnu=DEMO / "leidca2.jnu",
        workdir=WORK,
    ).execute(overwrite=True)
    print(f"[{'ok' if res.ok else 'FAILED'}] {name}: {res.elapsed:.1f} s")
    if not res.ok:
        print(res.log[-1500:])
        raise SystemExit(1)
    results[name] = res

# ------------------------------------------------------------- analysis
# These spherical runs print FLUX profiles (one block per transition).
print("\nCa II K (5/1) line-core diagnostics:")
print(f"{'case':9s} {'core shift':>11s} {'B/R':>7s}   annotations")
profiles = {}
for name, res in results.items():
    b = [
        x
        for x in AaaFile(res.output("aaa")).profile(5, 1)
        if x.kind == "line_profile"
    ][0]
    d = core_shift_and_asymmetry(b.wl, b.ilam, b.line_center or LINE_A,
                                 core_window=1.0)
    profiles[name] = b
    print(
        f"{name:9s} {d['core_shift_kms']:8.2f} km/s {d['br_ratio']:7.3f}"
        f"   [{b.case}; {b.redistribution}]"
    )

# ------------------------------------------------------- mass-loss rate
# Meszaros et al. evaluate Mdot = 4 pi r^2 rho v at the line-forming
# layers. The ramp is not a constant-Mdot wind, so we show the estimate
# across the layers the deep15 flow actually moves (illustrative!).
print("\ndeep15 mass-loss estimates across the flow region:")
print(f"{'i':>4s} {'v [km/s]':>9s} {'NH [cm^-3]':>12s} {'Mdot [Msun/yr]':>15s}")
for i in (20, 30, 40, 50):
    if deep15[i] <= 0:
        continue
    mdot = mass_loss_rate(R_STAR_RSUN, model.nh[i], deep15[i],
                          r_over_rstar=1.5)
    print(f"{i:4d} {deep15[i]:9.1f} {model.nh[i]:12.2e} {mdot:15.2e}")
print("(a real fit pins the rate at the core-formation layer against an")
print(" observed profile; Meszaros et al. 2009 obtain 0.6-5e-9 Msun/yr)")

# ------------------------------------------------------------- figure
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for name, b in profiles.items():
        for ax in axes:
            ax.plot(b.wl, b.ilam, label=name)
    axes[0].set_xlim(-4, 4)
    axes[1].set_xlim(-0.6, 0.6)
    for ax in axes:
        ax.set_yscale("log")
        ax.set_xlabel(r"$\Delta\lambda$ [$\AA$]")
    axes[0].set_ylabel(r"F$_\lambda$ [erg cm$^{-2}$ s$^{-1}$ $\AA^{-1}$]")
    axes[0].legend(title="velocity field")
    axes[1].set_title("core (blueshift + B/R asymmetry)")
    fig.suptitle("Ca II K vs. chromospheric outflow -- leid red-giant model")
    out = WORK / "ca2K_velocity_comparison.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"\nfigure: {out}")
except ImportError:
    print("\n(matplotlib not installed -- skipped the figure)")
