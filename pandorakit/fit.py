"""
Automated single-star fitting of chromospheric wind parameters.

Implements the Meszaros-Avrett-Dupree stage-2 workflow as an automated
loop: given a NORMALIZED observed line profile, find the velocity-field
(and optionally temperature-scale) parameters whose PANDORA profile
matches it best, and report parameter values with Delta-chi^2
confidence intervals and 2D degeneracy maps.

Requires numpy (``pip install numpy``; matplotlib optional for the
figures). PANDORA runs are cached on parameter values, so grids,
refinements, and repeated fits never recompute an identical model.

Pipeline per evaluation:

  parameters -> deck edit (VXS wind, optional TE scale)
             -> PANDORA run (spherical, expanding)
             -> parse flux profile (AaaFile)
             -> normalize to the line wings
             -> convolve to the instrument resolution R
             -> interpolate onto the observed wavelength grid
             -> chi^2 against the observation

Statistical honesty
-------------------
* If the observation has per-pixel errors, chi^2 uses them and the
  quoted intervals are absolute (Delta chi^2 = 1 for 1 parameter).
* If it does not, sigma is set from the fit residuals so that reduced
  chi^2 = 1 at the best fit; intervals then measure how well the model
  family constrains parameters GIVEN its own misfit level -- they do
  not include systematic model error (choice of T(z), atomic data,
  1D geometry...). Bracket those separately (see docs/course lesson 6).
* The T-structure / velocity degeneracy is real: fit multiple lines
  when possible, and always look at the 2D maps, not only the 1D bars.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence, Union

try:
    import numpy as np
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "pandorakit.fit requires numpy: pip install numpy"
    ) from _e

from .deck import Deck
from .outputs import AaaFile
from .recipes import set_expansion, wind_ramp
from .runner import PandoraInstall, PandoraRun

__all__ = [
    "Observation",
    "Parameter",
    "WindForwardModel",
    "FitResult",
    "fit_wind",
    "convolve_R",
    "normalize_to_wings",
]

C_KMS = 2.99792458e5


# ---------------------------------------------------------------- helpers
def convolve_R(wl: np.ndarray, flux: np.ndarray, R: float,
               line_center: float) -> np.ndarray:
    """Convolve a profile with a Gaussian instrumental LSF of resolution R.

    wl is Delta-lambda [A] relative to `line_center` [A]; the LSF FWHM
    is line_center/R. The profile is resampled to a uniform grid for
    the convolution and interpolated back, so wl need not be uniform.
    """
    if R is None or R <= 0:
        return flux
    fwhm = line_center / R
    sigma = fwhm / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    step = max(min(np.diff(wl).min(), sigma / 3.0), 1e-4)
    grid = np.arange(wl[0], wl[-1] + step, step)
    f = np.interp(grid, wl, flux)
    half = int(4 * sigma / step) + 1
    x = np.arange(-half, half + 1) * step
    kern = np.exp(-0.5 * (x / sigma) ** 2)
    kern /= kern.sum()
    fc = np.convolve(f, kern, mode="same")
    # guard the edges (convolution bleeds toward zero there)
    fc[:half] = f[:half]
    fc[-half:] = f[-half:]
    return np.interp(wl, grid, fc)


def normalize_to_wings(
    wl: np.ndarray, flux: np.ndarray, wing: tuple[float, float] = (3.5, 4.5)
) -> np.ndarray:
    """Divide a profile by its mean level in |wl| in [wing0, wing1] A.

    This defines the pseudo-continuum reference in the line wings --
    apply the SAME convention to observation and model. For real data,
    match this window to however your spectra were normalized.
    """
    m = (np.abs(wl) >= wing[0]) & (np.abs(wl) <= wing[1])
    if not m.any():
        raise ValueError(f"no points in the wing window {wing}")
    return flux / flux[m].mean()


# ---------------------------------------------------------------- inputs
@dataclass
class Observation:
    """A normalized observed line profile.

    wl    -- Delta-lambda from line center [A] (apply your RV correction
             and line-center subtraction upstream);
    flux  -- normalized flux;
    sigma -- per-pixel 1-sigma errors (None -> scaled from residuals);
    resolution -- instrument R = lambda/dlambda (None -> no convolution);
    line_center -- absolute line wavelength [A] (velocity conversions).
    """

    wl: np.ndarray
    flux: np.ndarray
    sigma: Optional[np.ndarray] = None
    resolution: Optional[float] = None
    line_center: float = 3933.7

    @classmethod
    def from_csv(
        cls,
        path: Union[str, Path],
        resolution: Optional[float] = None,
        line_center: float = 3933.7,
    ) -> "Observation":
        """Read columns wl,flux[,sigma] from a CSV (# comments allowed)."""
        rows = []
        for line in Path(path).read_text().splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = [p for p in line.replace(",", " ").split()]
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                continue  # header line
        arr = np.array(rows)
        return cls(
            wl=arr[:, 0],
            flux=arr[:, 1],
            sigma=arr[:, 2] if arr.shape[1] > 2 else None,
            resolution=resolution,
            line_center=line_center,
        )

    def window(self, half_width: float) -> "Observation":
        """Restrict to |wl| <= half_width [A] (the fitting window)."""
        m = np.abs(self.wl) <= half_width
        return Observation(
            wl=self.wl[m],
            flux=self.flux[m],
            sigma=None if self.sigma is None else self.sigma[m],
            resolution=self.resolution,
            line_center=self.line_center,
        )


@dataclass
class Parameter:
    """One fit parameter.

    name   -- one of the names the forward model understands
              (WindForwardModel: 'v_top', 'i_zero', 'i_top', 'te_scale');
    grid   -- values for the coarse-grid stage;
    kind   -- 'float' (refined continuously) or 'int' (grid-only);
    bounds -- hard limits for the refinement stage (default: grid span).
    """

    name: str
    grid: Sequence[float]
    kind: str = "float"
    bounds: Optional[tuple[float, float]] = None

    def clip(self, x: float) -> float:
        lo, hi = self.bounds or (min(self.grid), max(self.grid))
        return min(max(x, lo), hi)


# ---------------------------------------------------------- forward model
class WindForwardModel:
    """PANDORA forward model: wind parameters -> normalized profile.

    Parameters understood (all optional per call):
      v_top    -- wind speed at the top [km/s] (0 -> static run);
      i_zero   -- depth index (from the top) where the wind reaches 0;
      i_top    -- index where the ramp reaches v_top (default 15);
      te_scale -- multiply the model TE by this factor (default 1;
                  NOTE: large excursions require re-converging the H
                  populations -- keep within ~±5% or re-run the H chain
                  and update `mod` yourself; see docs).

    Runs are cached in `cache_dir` keyed on rounded parameter values:
    repeated evaluations are free.
    """

    def __init__(
        self,
        install: PandoraInstall,
        base_dat: Union[str, Path],
        mod: Union[str, Path],
        atm: Union[str, Path],
        res: Union[str, Path, None] = None,
        jnu: Union[str, Path, None] = None,
        transition: tuple[int, int] = (5, 1),
        line_center: float = 3933.7,
        workdir: Union[str, Path] = "runs/fit",
        cache_dir: Union[str, Path, None] = None,
        wing_window: tuple[float, float] = (3.5, 4.5),
        n_depths: Optional[int] = None,
        run_timeout: float = 1800.0,
    ):
        self.install = install
        self.base_dat = Path(base_dat)
        self.mod = Path(mod)
        self.atm = Path(atm)
        self.res = Path(res) if res else None
        self.jnu = Path(jnu) if jnu else None
        self.transition = transition
        self.line_center = line_center
        self.workdir = Path(workdir)
        self.cache_dir = Path(cache_dir or (self.workdir / "cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.wing_window = wing_window
        self.run_timeout = run_timeout
        self._base = Deck.read(self.base_dat, heading=True)
        if n_depths is None:
            from .model import Atmosphere

            n_depths = Atmosphere.read(self.mod).n
        self.n = n_depths
        self.evaluations = 0  # actual PANDORA runs (cache misses)

    # -- parameter canonicalization (also the cache key)
    @staticmethod
    def canon(params: dict) -> dict:
        out = {}
        for k, v in params.items():
            if k in ("i_zero", "i_top"):
                out[k] = int(round(v))
            else:
                out[k] = round(float(v), 3)
        return out

    def _key(self, params: dict) -> str:
        s = json.dumps(self.canon(params), sort_keys=True)
        return hashlib.sha1(s.encode()).hexdigest()[:16]

    # -- one evaluation
    def profile(self, **params) -> tuple[np.ndarray, np.ndarray]:
        """Return (wl [A from line center], normalized flux) for params."""
        p = self.canon(params)
        key = self._key(p)
        cached = self.cache_dir / f"{key}.csv"
        if cached.exists():
            arr = np.loadtxt(cached, delimiter=",")
            return arr[:, 0], arr[:, 1]

        v_top = p.get("v_top", 0.0)
        i_zero = p.get("i_zero", 55)
        i_top = p.get("i_top", 15)
        te_scale = p.get("te_scale", 1.0)

        deck = Deck.parse(self._base.dumps(), heading=True)
        if v_top > 0:
            deck = set_expansion(
                deck, wind_ramp(self.n, v_top, i_zero=i_zero, i_top=i_top)
            )
        else:
            deck = set_expansion(deck, None)

        mod_path = self.mod
        if te_scale != 1.0:
            from .model import Atmosphere

            atmm = Atmosphere.read(self.mod).with_te_scaled(te_scale)
            mod_path = self.cache_dir / f"mod_{key}.mod"
            atmm.write(mod_path)

        run = PandoraRun(
            self.install,
            case=f"fit_{key}",
            run_id="001",
            dat=deck,
            mod=mod_path,
            atm=self.atm,
            res=self.res,
            jnu=self.jnu,
            workdir=self.workdir,
        )
        result = run.execute(overwrite=True, timeout=self.run_timeout)
        self.evaluations += 1
        if not result.ok:
            raise RuntimeError(
                f"PANDORA run failed for {p}:\n{result.log[-1200:]}"
            )
        blocks = [
            b
            for b in AaaFile(result.output("aaa")).profile(*self.transition)
            if b.kind == "line_profile"
        ]
        b = blocks[0]
        order = np.argsort(np.asarray(b.wl))
        wl = np.asarray(b.wl)[order]
        fl = np.asarray(b.ilam)[order]
        fl = normalize_to_wings(wl, fl, self.wing_window)
        np.savetxt(cached, np.column_stack([wl, fl]), delimiter=",")
        # tidy the (large) run directory; profile is what we keep
        shutil.rmtree(result.directory, ignore_errors=True)
        return wl, fl

    def on_obs_grid(self, obs: Observation, **params) -> np.ndarray:
        """Model profile convolved to obs.resolution on obs.wl."""
        wl, fl = self.profile(**params)
        fl = convolve_R(wl, fl, obs.resolution, self.line_center)
        return np.interp(obs.wl, wl, fl)

    def chi2(self, obs: Observation, sigma: np.ndarray, **params) -> float:
        m = self.on_obs_grid(obs, **params)
        return float(np.sum(((obs.flux - m) / sigma) ** 2))


# ---------------------------------------------------------------- fitting
@dataclass
class FitResult:
    best: dict
    chi2_min: float
    ndof: int
    errors: dict = field(default_factory=dict)  # name -> (minus, plus)
    grid_points: list = field(default_factory=list)  # [(params, chi2), ...]
    sigma_scaled: bool = False
    n_evaluations: int = 0
    message: str = ""

    @property
    def chi2_red(self) -> float:
        return self.chi2_min / max(self.ndof, 1)

    def summary(self) -> str:
        lines = [
            f"best fit (chi2 = {self.chi2_min:.1f}, "
            f"ndof = {self.ndof}, chi2_red = {self.chi2_red:.2f})"
        ]
        if self.sigma_scaled:
            lines.append(
                "  [no observational errors given: sigma scaled so "
                "chi2_red = 1; intervals are relative to model misfit]"
            )
        for k, v in self.best.items():
            if k in self.errors:
                lo, hi = self.errors[k]
                lines.append(f"  {k:9s} = {v:.3f}  (-{lo:.3f} / +{hi:.3f})")
            else:
                lines.append(f"  {k:9s} = {v}")
        lines.append(f"  ({self.n_evaluations} PANDORA runs, rest cached)")
        return "\n".join(lines)


def _nelder_mead(
    f: Callable[[np.ndarray], float],
    x0: np.ndarray,
    step: np.ndarray,
    maxiter: int = 60,
    ftol: float = 0.05,
):
    """Compact Nelder-Mead (chi^2 scale: absolute ftol convergence)."""
    n = len(x0)
    simplex = [x0]
    for i in range(n):
        x = x0.copy()
        x[i] += step[i]
        simplex.append(x)
    vals = [f(x) for x in simplex]
    for _ in range(maxiter):
        order = np.argsort(vals)
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < ftol:
            break
        centroid = np.mean(simplex[:-1], axis=0)
        xr = centroid + (centroid - simplex[-1])  # reflection
        fr = f(xr)
        if fr < vals[0]:
            xe = centroid + 2.0 * (centroid - simplex[-1])  # expansion
            fe = f(xe)
            if fe < fr:
                simplex[-1], vals[-1] = xe, fe
            else:
                simplex[-1], vals[-1] = xr, fr
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = centroid + 0.5 * (simplex[-1] - centroid)  # contraction
            fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:  # shrink
                for i in range(1, n + 1):
                    simplex[i] = simplex[0] + 0.5 * (simplex[i] - simplex[0])
                    vals[i] = f(simplex[i])
    k = int(np.argmin(vals))
    return simplex[k], vals[k]


def _interval_from_profile(
    xs: np.ndarray, chis: np.ndarray, x_best: float, chi_min: float,
    delta: float = 1.0,
) -> tuple[float, float]:
    """1-sigma interval from a profile-likelihood curve (Delta chi2)."""
    lo = hi = float("nan")
    left = xs[xs <= x_best]
    cl = chis[xs <= x_best]
    right = xs[xs >= x_best]
    cr = chis[xs >= x_best]
    target = chi_min + delta
    if len(left) > 1 and cl.max() >= target:
        lo = x_best - float(np.interp(target, cl[::-1], left[::-1]))
    elif len(left) > 1:
        lo = float(x_best - left.min())  # interval unbounded: quote span
    if len(right) > 1 and cr.max() >= target:
        hi = float(np.interp(target, cr, right)) - x_best
    elif len(right) > 1:
        hi = float(right.max() - x_best)
    return abs(lo), abs(hi)


def fit_wind(
    obs: Observation,
    model: WindForwardModel,
    parameters: list[Parameter],
    fixed: Optional[dict] = None,
    refine: bool = True,
    workers: int = 3,
    profile_points: int = 7,
    verbose: bool = True,
) -> FitResult:
    """Grid + Nelder-Mead fit with Delta-chi^2 errors.

    Stages:
      1. full factorial grid over each Parameter.grid (parallel,
         cached) -- also the data for the degeneracy maps;
      2. Nelder-Mead refinement of the float parameters from the best
         node (int parameters stay at their best grid value);
      3. per-parameter profile likelihood: scan `profile_points` values
         across the parameter's span, minimizing over the other float
         parameters via the grid+NM surrogate (cheap: cached runs are
         reused; new points cost real runs);
      4. intervals at Delta chi^2 = 1 (one parameter at a time).

    Returns a FitResult; `grid_points` holds every (params, chi2)
    evaluated, ready for corner-style 2D maps.
    """
    fixed = dict(fixed or {})
    names = [p.name for p in parameters]

    # ---- sigma
    if obs.sigma is not None:
        sigma = obs.sigma.copy()
        sigma_scaled = False
    else:
        sigma = np.full_like(obs.flux, 1.0)
        sigma_scaled = True

    evaluated: list[tuple[dict, float]] = []

    def chi2_of(pdict: dict) -> float:
        full = {**fixed, **pdict}
        c = model.chi2(obs, sigma, **full)
        evaluated.append((model.canon(full), c))
        return c

    # ---- stage 1: factorial grid
    import itertools

    combos = [
        dict(zip(names, vals))
        for vals in itertools.product(*(p.grid for p in parameters))
    ]
    if verbose:
        print(f"grid stage: {len(combos)} nodes "
              f"({workers} workers, cached runs free)")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        chis = list(ex.map(chi2_of, combos))
    best_i = int(np.argmin(chis))
    best = dict(combos[best_i])
    chi_min = chis[best_i]
    if verbose:
        print(f"  grid best: {best}  chi2 = {chi_min:.1f}")

    # ---- stage 2: NM refinement of float parameters
    floats = [p for p in parameters if p.kind == "float"]
    if refine and floats:
        fnames = [p.name for p in floats]
        spans = {
            p.name: (max(p.grid) - min(p.grid)) / max(len(p.grid) - 1, 1)
            for p in floats
        }

        def fvec(x: np.ndarray) -> float:
            pd = dict(best)
            for nm, xi, pp in zip(fnames, x, floats):
                pd[nm] = pp.clip(float(xi))
            return chi2_of(pd)

        x0 = np.array([best[nm] for nm in fnames], dtype=float)
        step = np.array([0.6 * spans[nm] for nm in fnames])
        xb, chi_b = _nelder_mead(fvec, x0, step)
        if chi_b < chi_min:
            chi_min = chi_b
            for nm, xi, pp in zip(fnames, xb, floats):
                best[nm] = pp.clip(float(xi))
        if verbose:
            print(f"  refined:   {model.canon(best)}  chi2 = {chi_min:.1f}")

    # ---- sigma scaling (no obs errors): chi2_red = 1 at best
    ndof = len(obs.wl) - len(parameters)
    if sigma_scaled:
        scale = math.sqrt(chi_min / max(ndof, 1))
        sigma = sigma * scale
        # rescale everything already evaluated
        evaluated = [(p, c / scale**2) for p, c in evaluated]
        chi_min = chi_min / scale**2
        if verbose:
            print(f"  sigma scaled by {scale:.4f} (chi2_red -> 1)")

    # ---- stage 3: profile-likelihood intervals
    errors: dict = {}
    for p in parameters:
        if p.kind != "float":
            continue
        lo_b, hi_b = p.bounds or (min(p.grid), max(p.grid))
        xs = np.linspace(lo_b, hi_b, profile_points)
        prof = []
        for xv in xs:
            others = [q for q in parameters if q.name != p.name
                      and q.kind == "float"]
            if others and refine:
                onames = [q.name for q in others]

                def g(y: np.ndarray, _xv=xv, _onames=onames,
                      _others=others) -> float:
                    pd = dict(best)
                    pd[p.name] = float(_xv)
                    for nm, yi, qq in zip(_onames, y, _others):
                        pd[nm] = qq.clip(float(yi))
                    return chi2_of(pd)

                y0 = np.array([best[nm] for nm in onames], dtype=float)
                st = np.array([
                    0.3 * (max(q.grid) - min(q.grid))
                    / max(len(q.grid) - 1, 1)
                    for q in others
                ])
                _, cbest = _nelder_mead(g, y0, st, maxiter=25, ftol=0.2)
                prof.append(cbest)
            else:
                pd = dict(best)
                pd[p.name] = float(xv)
                prof.append(chi2_of(pd))
        prof = np.array(prof)
        errors[p.name] = _interval_from_profile(
            xs, prof, best[p.name], chi_min
        )
        if verbose:
            lo, hi = errors[p.name]
            print(f"  {p.name}: {best[p.name]:.3f} -{lo:.3f} +{hi:.3f}")

    return FitResult(
        best=model.canon(best),
        chi2_min=chi_min,
        ndof=ndof,
        errors=errors,
        grid_points=evaluated,
        sigma_scaled=sigma_scaled,
        n_evaluations=model.evaluations,
    )


# ------------------------------------------------------------- degeneracy
def degeneracy_map(
    result: FitResult, xname: str, yname: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Delta-chi^2 samples for a parameter pair, from every evaluation.

    Returns (x, y, dchi2) arrays -- scatter data; for each (x, y) pair
    the MINIMUM chi2 over all other parameters is used (profile
    likelihood in 2D). Feed to tricontourf / scatter; the Delta chi^2 =
    2.30 contour is the joint 68% region for 2 parameters.
    """
    agg: dict = {}
    for p, c in result.grid_points:
        if xname not in p or yname not in p:
            continue
        k = (p[xname], p[yname])
        if k not in agg or c < agg[k]:
            agg[k] = c
    xs = np.array([k[0] for k in agg])
    ys = np.array([k[1] for k in agg])
    cs = np.array([agg[k] for k in agg]) - result.chi2_min
    return xs, ys, cs
