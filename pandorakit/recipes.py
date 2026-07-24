"""
Science recipes: chromospheres, velocity fields, redistribution, mass loss.

These helpers encode the semi-empirical modeling patterns of the
PANDORA literature -- in particular the red-giant chromosphere + wind
methodology of Meszaros, Avrett & Dupree 2009 (AJ 138, 615): a
photosphere anchored model whose chromospheric temperature rises
linearly with decreasing log(column mass) up to T_max, topped by a thin
transition region; a stationary run tunes T_max against the emission
wings, then an outflow velocity field (VXS + option EXPAND) is tuned
until the computed line core shift and blue/red wing asymmetry match
the observed profile; the mass-loss rate follows from the density and
velocity at the formation radius.

Everything here builds or edits `Deck`/`Atmosphere` objects -- nothing
touches PANDORA itself.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from .deck import Deck, Statement
from .model import Atmosphere

__all__ = [
    "wind_ramp",
    "set_expansion",
    "set_redistribution",
    "chromosphere_te_logm",
    "core_shift_and_asymmetry",
    "mass_loss_rate",
]

# CGS / astronomical constants
M_H = 1.6735575e-24  # g
R_SUN = 6.957e10  # cm
M_SUN = 1.989e33  # g
YEAR = 3.1557e7  # s
C_KMS = 2.99792458e5  # km/s


# ---------------------------------------------------------------- velocity
def wind_ramp(
    n: int,
    v_top: float,
    i_zero: int,
    i_top: int = 0,
    shape: str = "smooth",
) -> list[float]:
    """Build an expansion-velocity table VXS (km/s, positive outward).

    Index convention follows PANDORA depth tables: **index 0 is the TOP
    of the atmosphere** and index n-1 the bottom (as in the demos and
    Meszaros et al. 2009 Fig. 2).

    v_top  -- wind speed at the top of the atmosphere;
    i_zero -- first depth index (from the top) where v reaches 0; the
              velocity is 0 from there to the bottom;
    i_top  -- index where the ramp reaches v_top (0 = the very top);
    shape  -- 'smooth' (cosine ramp, like demo 6's field) or 'linear'.

    Example (demo-6-like): wind_ramp(72, 100.0, i_zero=34, i_top=11).
    """
    if not (0 <= i_top < i_zero <= n):
        raise ValueError("need 0 <= i_top < i_zero <= n")
    v = []
    for i in range(n):
        if i <= i_top:
            v.append(v_top)
        elif i >= i_zero:
            v.append(0.0)
        else:
            x = (i - i_top) / (i_zero - i_top)  # 0 at top of ramp, 1 at zero
            if shape == "linear":
                f = 1.0 - x
            else:
                f = 0.5 * (1.0 + math.cos(math.pi * x))
            v.append(v_top * f)
    return v


def set_expansion(
    deck: Deck,
    vxs: Optional[Sequence[float]],
    spherical: Optional[bool] = None,
) -> Deck:
    """Turn a run deck into an expanding-atmosphere run (or back).

    vxs -- the expansion velocity table (km/s, + outward, top first),
           or None to make the run static (removes VXS, sets OMIT EXPAND).
    spherical -- optionally also switch option SPHERE on/off.

    The VXS table and the DO ( EXPAND ) option go to Part D (see demo 6's
    leidca2.dat for the pattern this reproduces).
    """
    # remove existing expand/omit-expand DO/OMIT statements for EXPAND
    for s in list(deck.statements()):
        if s.name.upper() in ("DO", "OMIT") and s.values:
            if str(s.values[0]).upper() == "EXPAND":
                deck.items.remove(s)
    if vxs is None:
        deck.remove("VXS")
        deck.items.insert(0, Statement("OMIT", [], ["EXPAND"]))
    else:
        deck.items.insert(0, Statement("DO", [], ["EXPAND"]))
        deck.set("VXS", list(vxs), part=2)
    if spherical is not None:
        for s in list(deck.statements()):
            if s.name.upper() in ("DO", "OMIT") and s.values:
                if str(s.values[0]).upper() == "SPHERE":
                    deck.items.remove(s)
        deck.items.insert(
            0, Statement("DO" if spherical else "OMIT", [], ["SPHERE"])
        )
    return deck


# ---------------------------------------------------------- redistribution
def set_redistribution(
    deck: Deck,
    upper: int,
    lower: int,
    mode: str,
    gmma: float = -1.0,
) -> Deck:
    """Select CRD or PRD for one transition of a run deck.

    PANDORA computes line source functions in **complete redistribution
    (CRD) by default**; partial redistribution (PRD) is enabled per
    transition with SCH u l ( 1 ) (wup Section 15).  Which method PRD
    uses is set by option PRDMETH (on = Hubeny & Lites 1995; off =
    Kneer & Heasley as in VAL81 Appendix A).

    mode -- 'crd' removes the SCH/GMMA statements for (upper, lower);
            'prd' adds SCH u l ( 1 ) and GMMA u l ( gmma ).
    """
    mode = mode.lower()
    if mode not in ("crd", "prd"):
        raise ValueError("mode must be 'crd' or 'prd'")
    for key in (f"SCH {upper} {lower}", f"GMMA {upper} {lower}"):
        deck.remove(key)
    if mode == "prd":
        anchor = deck.get(f"A {upper} {lower}") or deck.get("IOMX")
        deck.set(f"SCH {upper} {lower}", 1, part=2)
        deck.set(f"GMMA {upper} {lower}", gmma, part=2)
    return deck


# ------------------------------------------------------------ chromosphere
def chromosphere_te_logm(
    zmass_phot: Sequence[float],
    te_phot: Sequence[float],
    zmass_top: float = 1e-5,
    t_start: Optional[float] = None,
    t_max: float = 9000.0,
    n_chromo: int = 50,
    n_tr: int = 10,
    t_tr_top: float = 2.0e5,
) -> tuple[list[float], list[float]]:
    """Meszaros-style chromosphere: T linear in log10(column mass).

    Given photospheric anchors (zmass_phot, te_phot; ordered from the
    TOP of the photosphere downward, CGS g/cm^2 and K), builds the full
    (zmass, te) run of a model with:

    * the chromosphere: n_chromo points from the top of the photosphere
      (t_start defaults to te_phot[0]) rising linearly in T vs
      log10(ZMASS) to t_max at zmass_top;
    * the transition region: n_tr points continuing from t_max to
      t_tr_top with the same log-mass spacing per point as the last
      chromospheric step (thin cap, following Meszaros et al. 2009);
    * the photosphere itself appended below.

    Returns (zmass, te) ordered from the TOP of the atmosphere downward
    (PANDORA's depth-table convention).
    """
    if t_start is None:
        t_start = float(te_phot[0])
    m0 = float(zmass_phot[0])
    if not zmass_top < m0:
        raise ValueError("zmass_top must be smaller than zmass_phot[0]")
    lm0, lm1 = math.log10(m0), math.log10(zmass_top)

    zm_ch, te_ch = [], []
    for k in range(n_chromo):
        x = (k + 1) / n_chromo  # exclude the duplicate anchor point
        lm = lm0 + (lm1 - lm0) * x
        zm_ch.append(10.0 ** lm)
        te_ch.append(t_start + (t_max - t_start) * x)

    dlm = (lm1 - lm0) / n_chromo  # per-point log-mass step (negative)
    zm_tr, te_tr = [], []
    lt0, lt1 = math.log10(t_max), math.log10(t_tr_top)
    for k in range(n_tr):
        x = (k + 1) / n_tr
        zm_tr.append(10.0 ** (lm1 + dlm * (k + 1)))
        te_tr.append(10.0 ** (lt0 + (lt1 - lt0) * x))

    # assemble: TR top -> chromosphere -> photosphere (top-down order)
    zmass = list(reversed(zm_tr)) + list(reversed(zm_ch)) + list(zmass_phot)
    te = list(reversed(te_tr)) + list(reversed(te_ch)) + list(te_phot)
    return zmass, te


# ------------------------------------------------------------- diagnostics
def core_shift_and_asymmetry(
    wl: Sequence[float],
    ilam: Sequence[float],
    line_center: float,
    core_window: float = 1.5,
) -> dict:
    """Measure line-core velocity shift and emission-wing asymmetry.

    wl    -- Delta-lambda from line center (A), as in PROF line-profile
             blocks (b.wl);
    ilam  -- intensity;
    line_center -- absolute wavelength of the line (A), for km/s scaling;
    core_window -- only consider |dl| < core_window (A) for the core.

    Returns dict with:
      core_shift_kms -- velocity of the intensity minimum (negative =
                        blueshift = outflow on the near side);
      br_ratio       -- Blue/Red emission peak ratio (B/R of Meszaros
                        et al.); 1.0 when no distinct peaks;
      wl_min, i_min  -- position/intensity of the core minimum.
    """
    pts = sorted((w, i) for w, i in zip(wl, ilam) if abs(w) <= core_window)
    if len(pts) < 5:
        raise ValueError("too few points inside the core window")
    ws = [p[0] for p in pts]
    xs = [p[1] for p in pts]
    # core = interior minimum (parabolic refinement around the grid min)
    k = min(range(1, len(xs) - 1), key=lambda j: xs[j])
    a, b, c = xs[k - 1], xs[k], xs[k + 1]
    denom = (a - 2 * b + c)
    frac = 0.5 * (a - c) / denom if denom != 0 else 0.0
    frac = max(-1.0, min(1.0, frac))
    w_min = ws[k] + frac * (
        (ws[k + 1] - ws[k]) if frac >= 0 else (ws[k] - ws[k - 1])
    )
    i_min = b
    # emission peaks: maxima on each side of the core minimum
    blue = [x for w, x in zip(ws, xs) if w < w_min]
    red = [x for w, x in zip(ws, xs) if w > w_min]
    br = (max(blue) / max(red)) if blue and red and max(red) > 0 else 1.0
    return {
        "core_shift_kms": w_min / line_center * C_KMS,
        "br_ratio": br,
        "wl_min": w_min,
        "i_min": i_min,
    }


def mass_loss_rate(
    r_star_rsun: float,
    nh_cm3: float,
    v_kms: float,
    r_over_rstar: float = 1.0,
    mu: float = 1.4,
) -> float:
    """Spherical mass-loss estimate  Mdot = 4 pi r^2 rho v  in Msun/yr.

    r_star_rsun -- stellar radius in solar radii;
    nh_cm3      -- total hydrogen number density at the reference layer;
    v_kms       -- outflow velocity there (km/s);
    r_over_rstar-- radius of that layer in stellar radii (Meszaros et
                   al. use the H-alpha core formation layer, ~1.4-2 R*);
    mu          -- mean mass per hydrogen atom in units of m_H
                   (1.4 accounts for helium).

    This is the standard steady-wind estimate used to convert a
    semi-empirical chromosphere + velocity model into a mass-loss rate.
    """
    r = r_star_rsun * R_SUN * r_over_rstar
    rho = mu * M_H * nh_cm3
    mdot = 4.0 * math.pi * r * r * rho * (v_kms * 1e5)  # g/s
    return mdot * YEAR / M_SUN
