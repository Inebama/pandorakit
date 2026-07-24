#!/usr/bin/env python3
"""
Synthesize a mock 'observed' Ca II K profile with KNOWN wind parameters.

Used to validate the automated fitter (the fit must recover the truth
within its quoted errors) and as the observation for the tutorial
notebook. Truth: v_top = 12.7 km/s, i_zero = 52 -- deliberately off
the fitter's grid nodes.
"""

from pathlib import Path

import numpy as np

from pandorakit import PandoraInstall
from pandorakit.fit import WindForwardModel, convolve_R

ROOT = Path.home() / "pandora"
DEMO = ROOT / "v2.1.1/demos/6"
OUT = Path(__file__).parent / "mock_ca2k_obs.csv"

TRUTH = {"v_top": 12.7, "i_zero": 52}
R = 34000.0  # Hectochelle-like resolution (MAD09)
SNR = 80.0
LINE = 3933.7
SEED = 42

model = WindForwardModel(
    PandoraInstall(ROOT),
    base_dat=DEMO / "leidca2.dat",
    mod=DEMO / "leid.mod",
    atm=ROOT / "v2.1.1/atoms/ca2l5.atm",
    res=DEMO / "leidca2.res",
    jnu=DEMO / "leidca2.jnu",
    transition=(5, 1),
    line_center=LINE,
    workdir=ROOT / "runs" / "fit_mock",
)

wl_mod, fl_mod = model.profile(**TRUTH)
fl_mod = convolve_R(wl_mod, fl_mod, R, LINE)

# observed pixel grid: uniform, R-sampled at ~2.5 px per FWHM
dpix = LINE / R / 2.5
wl_obs = np.arange(-4.5, 4.5 + dpix, dpix)
flux = np.interp(wl_obs, wl_mod, fl_mod)
rng = np.random.default_rng(SEED)
sigma = flux / SNR
flux_noisy = flux + rng.normal(0.0, sigma)

hdr = (
    f"# mock Ca II K observation | truth: v_top={TRUTH['v_top']} km/s, "
    f"i_zero={TRUTH['i_zero']} | R={R:.0f}, SNR={SNR:.0f}, seed={SEED}\n"
    "# wl_delta_A, flux_norm, sigma\n"
)
with open(OUT, "w") as f:
    f.write(hdr)
    for w, fx, s in zip(wl_obs, flux_noisy, sigma):
        f.write(f"{w:.5f}, {fx:.6f}, {s:.6f}\n")
print(f"wrote {OUT} ({len(wl_obs)} pixels)")
