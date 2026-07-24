#!/usr/bin/env python3
"""
Automated single-star chromospheric wind fit.

Give it a normalized observed line profile and a JSON configuration;
it converges by itself and reports best-fit parameters with
Delta-chi^2 errors and parameter-degeneracy maps.

    python3 fit_single_star.py --obs mock_ca2k_obs.csv \
                               --config fit_config.json \
                               --outdir fit_out

The observation file: columns wl,flux[,sigma], '#' comments; wl is
Delta-lambda [A] from the line center (RV-correct upstream!).

The configuration (all paths, the model space, and the instrument),
e.g.:

{
  "root": "~/pandora",
  "base_dat": "~/pandora/v2.1.1/demos/6/leidca2.dat",
  "mod":      "~/pandora/v2.1.1/demos/6/leid.mod",
  "atm":      "~/pandora/v2.1.1/atoms/ca2l5.atm",
  "res":      "~/pandora/v2.1.1/demos/6/leidca2.res",
  "jnu":      "~/pandora/v2.1.1/demos/6/leidca2.jnu",
  "transition": [5, 1],
  "line_center": 3933.7,
  "resolution": 34000,
  "fit_window_A": 3.0,
  "workdir": "~/pandora/runs/fit_star1",
  "parameters": [
    {"name": "v_top",  "grid": [6, 10, 14, 18], "kind": "float"},
    {"name": "i_zero", "grid": [45, 50, 55, 60], "kind": "int"}
  ],
  "fixed": {"i_top": 15},
  "workers": 3
}

Outputs in --outdir: fit_result.json (parameters, errors, chi2),
best_fit_profile.csv, and (with matplotlib) profile + degeneracy-map
figures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from pandorakit import PandoraInstall
from pandorakit.fit import (
    Observation,
    Parameter,
    WindForwardModel,
    degeneracy_map,
    fit_wind,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--obs", required=True, help="observed profile CSV")
    ap.add_argument("--config", required=True, help="JSON configuration")
    ap.add_argument("--outdir", default="fit_out")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    x = lambda p: Path(p).expanduser() if p else None

    obs = Observation.from_csv(
        args.obs,
        resolution=cfg.get("resolution"),
        line_center=cfg.get("line_center", 3933.7),
    ).window(cfg.get("fit_window_A", 3.0))
    print(f"observation: {len(obs.wl)} pixels in the fit window, "
          f"{'with' if obs.sigma is not None else 'WITHOUT'} error column")

    model = WindForwardModel(
        PandoraInstall(x(cfg.get("root", "~/pandora"))),
        base_dat=x(cfg["base_dat"]),
        mod=x(cfg["mod"]),
        atm=x(cfg["atm"]),
        res=x(cfg.get("res")),
        jnu=x(cfg.get("jnu")),
        transition=tuple(cfg.get("transition", [5, 1])),
        line_center=cfg.get("line_center", 3933.7),
        workdir=x(cfg.get("workdir", "runs/fit")),
    )
    params = [
        Parameter(p["name"], p["grid"], p.get("kind", "float"),
                  tuple(p["bounds"]) if p.get("bounds") else None)
        for p in cfg["parameters"]
    ]

    result = fit_wind(
        obs, model, params,
        fixed=cfg.get("fixed"),
        workers=cfg.get("workers", 3),
    )
    print()
    print(result.summary())

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- persist result
    (outdir / "fit_result.json").write_text(json.dumps({
        "best": result.best,
        "errors": {k: list(v) for k, v in result.errors.items()},
        "chi2_min": result.chi2_min,
        "ndof": result.ndof,
        "chi2_red": result.chi2_red,
        "sigma_scaled": result.sigma_scaled,
        "n_pandora_runs": result.n_evaluations,
        "grid_points": [[p, c] for p, c in result.grid_points],
    }, indent=1))

    best_model = model.on_obs_grid(obs, **result.best)
    np.savetxt(outdir / "best_fit_profile.csv",
               np.column_stack([obs.wl, obs.flux, best_model]),
               delimiter=",", header="wl_delta_A, flux_obs, flux_model")

    # ---- figures
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        if obs.sigma is not None:
            ax.errorbar(obs.wl, obs.flux, obs.sigma, fmt=".", ms=3,
                        alpha=0.6, label="observation")
        else:
            ax.plot(obs.wl, obs.flux, ".", ms=3, alpha=0.6,
                    label="observation")
        ax.plot(obs.wl, best_model, lw=1.8, label="best fit")
        lbl = ", ".join(
            f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
            for k, v in result.best.items()
        )
        ax.set_title(f"best fit: {lbl}")
        ax.set_xlabel(r"$\Delta\lambda$ [$\AA$]")
        ax.set_ylabel("normalized flux")
        ax.legend()
        fig.savefig(outdir / "best_fit.png", dpi=140, bbox_inches="tight")

        names = [p.name for p in params]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                xs, ys, cs = degeneracy_map(result, names[i], names[j])
                if len(xs) < 4:
                    continue
                fig, ax = plt.subplots(figsize=(6, 5))
                sc = ax.tricontourf(xs, ys, np.minimum(cs, 25), levels=14)
                ax.tricontour(xs, ys, cs, levels=[2.30, 6.17],
                              colors="w", linewidths=1)
                ax.plot([result.best[names[i]]], [result.best[names[j]]],
                        "w*", ms=12)
                ax.set_xlabel(names[i])
                ax.set_ylabel(names[j])
                ax.set_title(r"$\Delta\chi^2$ (white: 68% / 95% joint)")
                fig.colorbar(sc)
                fig.savefig(outdir / f"degeneracy_{names[i]}_{names[j]}.png",
                            dpi=140, bbox_inches="tight")
        print(f"\nfigures + results in {outdir}/")
    except ImportError:
        print(f"\nresults in {outdir}/ (no matplotlib: figures skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
