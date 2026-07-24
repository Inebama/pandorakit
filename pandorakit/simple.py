"""
The easy interface: compute a spectrum without knowing PANDORA.

One call takes you from an atmosphere table (a plain CSV) to emergent
line profiles:

    from pandorakit.simple import compute_spectrum

    result = compute_spectrum("mystar.csv", lines=[(3, 2)],
                              iterations=5, workdir="runs/mystar")
    halpha = result.profile(3, 2)          # ProfileBlock (mu=1 or flux)
    result.atmosphere_updated.to_table("mystar_updated.csv")

Everything PANDORA-specific (run decks, statement language, restart
files, unit numbers) is handled internally using the validated
templates in the repository's ``templates/`` directory.

Scope of this v1 interface: **hydrogen runs** (the bootstrap of every
PANDORA project, and the H-alpha mass-loss diagnostic). For other ions
(Ca II, Mg II, He I...) you chain them on top of a converged hydrogen
run -- see examples/run_chain_demo6.py and docs/GETTING_STARTED.md
section "Beyond hydrogen".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence, Union

from .deck import Deck
from .model import Atmosphere
from .outputs import AaaFile, ProfileBlock
from .pmerge import merge_pop
from .recipes import set_expansion, set_redistribution
from .runner import PandoraInstall, PandoraRun, RunResult

__all__ = ["compute_spectrum", "SpectrumResult"]

_TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class SpectrumResult:
    """What a compute_spectrum call returns."""

    run: RunResult
    profiles: dict = field(default_factory=dict)  # (u, l) -> [ProfileBlock]
    atmosphere_updated: Optional[Atmosphere] = None

    @property
    def ok(self) -> bool:
        return self.run.ok

    def profile(self, u: int, l: int, mu: Optional[float] = 1.0
                ) -> ProfileBlock:
        """The emergent line profile of transition (u, l).

        mu -- viewing angle cosine (1.0 = disk center); None or no
        match returns the first block (the flux profile in spherical
        runs).
        """
        blocks = self.profiles.get((u, l), [])
        if not blocks:
            raise KeyError(
                f"no profile for transition ({u},{l}); "
                f"available: {sorted(self.profiles)}"
            )
        for b in blocks:
            if mu is not None and b.mu == mu:
                return b
        return blocks[0]

    def summary(self) -> str:
        lines = [f"run {self.run.case}: "
                 f"{'OK' if self.ok else 'FAILED'} "
                 f"({self.run.elapsed:.1f}s)"]
        for (u, l), blocks in sorted(self.profiles.items()):
            b = blocks[0]
            lines.append(
                f"  line ({u}/{l}) at {b.line_center} A: "
                f"{len(blocks)} block(s), {len(b.wl)} wavelengths "
                f"[{b.case}; {b.redistribution}]"
            )
        return "\n".join(lines)


def compute_spectrum(
    atmosphere: Union[str, Path, Atmosphere],
    lines: Sequence[tuple[int, int]] = ((3, 2),),
    levels: int = 3,
    iterations: int = 5,
    wind: Optional[Sequence[float]] = None,
    prd_lines: Sequence[tuple[int, int]] = (),
    r1n: Optional[float] = None,
    gravity_ratio: Optional[float] = None,
    case: Optional[str] = None,
    run_id: str = "001",
    workdir: Union[str, Path] = "runs/simple",
    install_root: Union[str, Path, None] = None,
    update_populations: bool = True,
    timeout: float = 3600.0,
) -> SpectrumResult:
    """Run hydrogen NLTE + emergent line profiles for an atmosphere.

    Parameters
    ----------
    atmosphere : CSV/table path, ``.mod`` path, or Atmosphere object.
        Tables need columns (z_km|z_cm|zmass), te, nh, ne -- see
        Atmosphere.from_table for the format (header, '#' comments,
        optional vturb/wind columns).
    lines : which hydrogen transitions to synthesize, as (upper, lower)
        level pairs. With levels=3: (2,1)=Ly-alpha, (3,1)=Ly-beta,
        (3,2)=H-alpha. Default: H-alpha.
    levels : size of the model atom: 3 (fast, robust bootstrap),
        5, or 15 (production; slower). Uses the shipped library atoms.
    iterations : overall NLTE iterations this run (start 5; check
        convergence and rerun -- see GETTING_STARTED).
    wind : optional outflow velocity per depth [km/s, + outward, first
        value = top of atmosphere]; same length as the model. Build one
        with recipes.wind_ramp. None = static atmosphere.
    prd_lines : transitions to treat in partial redistribution
        (default: all in CRD, PANDORA's default).
    r1n, gravity_ratio : atmosphere scalars (thickness parameter [cm]
        and gravity relative to the Sun) if not already in the model.
    update_populations : also return `atmosphere_updated`, the input
        atmosphere with the run's new NE/populations merged in -- feed
        it to the next call for convergence chains.
    install_root : PANDORA installation (default ~/pandora).

    Returns SpectrumResult (raises RuntimeError on a failed run, with
    the log tail in the message).
    """
    # ---- the atmosphere
    if isinstance(atmosphere, Atmosphere):
        atm = atmosphere.copy()
    else:
        p = Path(atmosphere)
        if p.suffix.lower() in (".mod", ".pmod"):
            atm = Atmosphere.read(p)
        else:
            atm = Atmosphere.from_table(p)
    if r1n is not None:
        atm.r1n = r1n
    if gravity_ratio is not None:
        atm.cgr = gravity_ratio  # CGR: gravity ratio w.r.t. the Sun
    if atm.nvh is None:
        atm.nvh = 0
    issues = atm.validate()
    if issues:
        raise ValueError("atmosphere not runnable: " + "; ".join(issues))

    # ---- the run deck from the validated template
    deck = Deck.read(_TEMPLATES / "h_spectrum.dat", heading=True)
    deck.set("IOMX", int(iterations))
    for (u, l) in lines:
        deck.set(f"PROF {u} {l}", 1, part=2)
    for (u, l) in prd_lines:
        set_redistribution(deck, u, l, "prd")
    if wind is not None:
        if len(wind) != atm.n:
            raise ValueError(
                f"wind has {len(wind)} points, model has {atm.n}"
            )
        set_expansion(deck, list(wind))

    # ---- run
    install = PandoraInstall(install_root or (Path.home() / "pandora"))
    if case is None:
        case = f"{atm.name}_h"
    run = PandoraRun(
        install,
        case=case,
        run_id=run_id,
        dat=deck,
        mod=atm.to_deck(),
        atom=("h", levels),
        workdir=workdir,
    )
    res = run.execute(overwrite=True, timeout=timeout)
    if not res.ok:
        raise RuntimeError(
            f"PANDORA run failed (see {res.directory}):\n"
            + res.log[-1500:]
        )

    # ---- collect
    out = SpectrumResult(run=res)
    aaa = AaaFile(res.output("aaa"))
    for (u, l) in lines:
        blocks = [
            b for b in aaa.profile(u, l) if b.kind == "line_profile"
        ]
        out.profiles[(u, l)] = blocks

    if update_populations and "pop" in res.outputs:
        merged = merge_pop("@NE+", Deck.read(res.output("pop")),
                           atm.to_deck())
        out.atmosphere_updated = Atmosphere.from_deck(merged,
                                                      name=atm.name)
    return out
