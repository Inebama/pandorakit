# pandorakit — PANDORA, usable

**PANDORA** (E. H. Avrett & R. Loeser, Harvard-Smithsonian CfA) is the
classic non-LTE stellar-atmosphere and spectrum-synthesis code behind
the VAL/FAL solar models: multilevel statistical equilibrium, line and
continuum transfer with **partial redistribution**, particle diffusion,
flows, spherical geometry — in 1D. It is distributed as ~4,500 Fortran
77 routines that do not build with modern compilers, are driven by
fixed logical units and csh scripts, and are documented by a 368-page
writeup.

**pandorakit** makes it usable in 2026:

* **`patches/` + `install.sh`** — a verified gfortran port (macOS
  arm64 & Linux) with every change documented, and one command from the
  CfA tarballs to a *numerically verified* installation
  ([docs/INSTALL.md](docs/INSTALL.md));
* **`docs/MANUAL.md`** — a zero-to-hero manual distilled from the
  writeup, the demos, and the source: input language, run anatomy,
  workflows, recipes for new stars, troubleshooting, and a realistic
  3D roadmap;
* **`pandorakit/`** — a zero-dependency Python package: parse and edit
  any PANDORA file (`Deck`, `Atmosphere`), run without csh
  (`PandoraRun`), parse printouts and emergent profiles (`AaaFile`),
  chain ions (`merge_pop`), run **many stars in parallel** (`batch`);
* **a browser GUI** (`pandorakit gui`) — draggable T(z) model editor
  (successor to the IDL `xtwiddle`), run launcher with live log,
  profile plots, and instant search of the ~740 input parameters;
* **`tests/` + `examples/verify_install.py`** — parser tests and
  demo-reference comparisons (demo 4's Mg II k profile reproduces the
  2014 ifort reference to every printed digit).

## Quick start

```bash
# 1. download the five release archives from
#    https://lweb.cfa.harvard.edu/~avrett/pandora/releases/  into ~/Downloads/Pandora
# 2. build + verify PANDORA into ~/pandora:
./install.sh ~/Downloads/Pandora ~/pandora
# 3. the Python package + GUI:
python3 -m pip install -e .
python3 examples/verify_install.py
pandorakit gui
```

```python
from pandorakit import PandoraInstall, PandoraRun, AaaFile

install = PandoraInstall("~/pandora")
res = PandoraRun(install, case="sunh", run_id="001",
                 dat="sun_h.dat", mod="sun.mod", atom=("h", 15),
                 workdir="runs").execute()
assert res.ok
prof = [b for b in AaaFile(res.output("aaa")).profile(2, 1)
        if b.kind == "line_profile"]
```

## Repository layout

```
docs/INSTALL.md      installation guide (patches explained, flags, why sys/ needs -O0)
docs/MANUAL.md       the zero-to-hero manual
install.sh           automated: extract, patch, build, install, verify
patches/             gfortran port patch for pristine pandora-v2.2.0-src
pandorakit/          the Python package (stdlib only)
examples/            runnable examples incl. multi-ion chain and batch grid
tests/               pytest suite
```

## Science extensions

* **Velocity fields & winds** — `recipes.wind_ramp` / `set_expansion`
  build expanding-atmosphere runs (VXS + `DO ( EXPAND )`);
  `examples/velocity_mass_outflow.py` reproduces the
  Mészáros-Avrett-Dupree red-giant workflow on the shipped `leid`
  giant model (core blueshift, B/R asymmetry, mass-loss estimate) and
  the GUI's Model editor includes a draggable velocity-table editor.
* **CRD / PRD per transition** — CRD is PANDORA's default; PRD is a
  per-line switch (`SCH u l`). `recipes.set_redistribution` toggles
  it; `examples/prd_vs_crd.py` demonstrates the factor ~2 inner-wing
  difference on Mg II k.
* **Chromosphere builder** — `recipes.chromosphere_te_logm` implements
  the T-linear-in-log(column-mass) parameterization of Mészáros et
  al. 2009.
* **Bridges to other codes** — `to_multi_atmos` exports models in the
  MULTI/RH `.atmos` text format for cross-checking with the RH family
  (cf. Rutten & Uitenbroek 2012).
* **Atomic data** — age/quality audit and safe update procedure in
  [docs/ATOMIC_DATA.md](docs/ATOMIC_DATA.md).
* **Teaching** — a week-long course pack (intro → NLTE → PRD →
  hands-on → mass loss → frontiers) in
  [docs/course/](docs/course/README.md), physics crosschecked against
  Hubeny & Mihalas (2015) and Gray (2022).

## Automated fitting (single star)

`pandorakit.fit` + `examples/fit_single_star.py` implement the full
observed-spectrum-to-parameters loop: cached PANDORA forward model,
parallel grid + Nelder-Mead, **Δχ² profile-likelihood error bars**,
and 2D degeneracy maps. Validated by blind recovery of known
parameters from a mock observation. Learn it interactively in
[notebooks/fitting_tutorial.ipynb](notebooks/fitting_tutorial.ipynb);
the exhaustive input reference is [docs/INPUTS.md](docs/INPUTS.md) and
the complete API reference [docs/API.md](docs/API.md).

## Status & caveats

* Build verified with gfortran 14 on macOS/arm64; demos 1–7 run.
  **`sys/` must be compiled `-O0`** (see INSTALL.md — undefined
  behavior in the legacy in-memory I/O layer breaks under optimizers).
* References ship from program version 78.018; this source is 79.009 —
  electron-density-related tables differ by the documented "revised NE
  calculations" (~2% in the demos). Demo 4 (no NE feedback) matches
  exactly.
* PANDORA itself is © its authors and distributed by CfA; this
  repository contains only patches, tooling, and documentation.

## Citing

Avrett & Loeser 2003 (ASP Conf. 288, 303) for the code; VAL/FAL papers
per application; this repository for the port and tooling. State
compiler and flags — each run records them in `EXECUTION DATA`.
