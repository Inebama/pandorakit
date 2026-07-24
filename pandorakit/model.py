"""
Atmosphere models for PANDORA.

An atmosphere model (traditionally a ``.mod`` file) is a deck of Group-1
statements: the depth grid and the physical state of the star.

Required minimum (wup Section 99): N, Z, TE, NH, NE
(or ZMASS + TE + NE, from which PANDORA derives Z and NH).
Common additions: V (flow velocity), VT (microturbulence), R1N, CGR,
BDHM, NVH, and for restarts the population tables (NP, HN j, BDH j...).

Design: an `Atmosphere` *wraps* its source deck rather than replacing
it.  A `.mod` file is structured into segments separated by
``USE ( INPUT )`` markers, and statements must stay in their segment
(they are read into different input Parts -- see MANUAL.md section 5).
`to_deck()` therefore returns a copy of the source deck with the
physical arrays replaced in place; only models built from scratch get a
freshly generated four-segment deck.  Everything stays in PANDORA's CGS
conventions: Z in cm, TE in K, densities in cm^-3, velocities km/s.
"""

from __future__ import annotations

import copy as _copy
from pathlib import Path
from typing import Optional, Sequence, Union

from .deck import Comment, Deck, Statement, Use

__all__ = ["Atmosphere"]

# statement key -> Atmosphere attribute
_FIELD_KEYS = {
    "Z": "z",
    "TE": "te",
    "NH": "nh",
    "NE": "ne",
    "ZMASS": "zmass",
    "V": "v",
    "VT": "vt",
    "BDHM": "bdhm",
}
_SCALAR_KEYS = {"R1N": "r1n", "CGR": "cgr", "NVH": "nvh"}


class Atmosphere:
    """A PANDORA atmosphere model (wrapping its source deck)."""

    def __init__(
        self,
        name: str = "model",
        z: Optional[Sequence[float]] = None,
        te: Optional[Sequence[float]] = None,
        nh: Optional[Sequence[float]] = None,
        ne: Optional[Sequence[float]] = None,
        zmass: Optional[Sequence[float]] = None,
        v: Optional[Sequence[float]] = None,
        vt: Optional[Sequence[float]] = None,
        bdhm: Optional[Sequence[float]] = None,
        r1n: Optional[float] = None,
        cgr: Optional[float] = None,
        nvh: Optional[int] = None,
        source_deck: Optional[Deck] = None,
    ):
        self.name = name
        self.z = list(z) if z is not None else None
        self.te = list(te) if te is not None else None
        self.nh = list(nh) if nh is not None else None
        self.ne = list(ne) if ne is not None else None
        self.zmass = list(zmass) if zmass is not None else None
        self.v = list(v) if v is not None else None
        self.vt = list(vt) if vt is not None else None
        self.bdhm = list(bdhm) if bdhm is not None else None
        self.r1n = r1n
        self.cgr = cgr
        self.nvh = nvh
        self._source = source_deck

    # ------------------------------------------------------------- checks
    @property
    def n(self) -> int:
        for arr in (self.z, self.te, self.zmass):
            if arr is not None:
                return len(arr)
        return 0

    def validate(self) -> list[str]:
        """Return a list of problems (empty when the model looks runnable)."""
        issues = []
        n = self.n
        if n == 0:
            issues.append("no depth grid: provide z or zmass")
        using_zmass = self.z is None
        if using_zmass and (self.zmass is None or self.ne is None):
            issues.append("need either (z, te, nh, ne) or (zmass, te, ne)")
        for nm in ("z", "te", "nh", "ne", "zmass", "v", "vt", "bdhm"):
            arr = getattr(self, nm)
            if arr is not None and len(arr) != n:
                issues.append(f"{nm} has {len(arr)} points, expected {n}")
        if self.te is None:
            issues.append("te (temperature) is required")
        if not using_zmass:
            if self.nh is None:
                issues.append("nh is required when using a z grid")
            if self.ne is None:
                issues.append("ne is required when using a z grid")
            if self.z is not None and any(
                self.z[i] >= self.z[i + 1] for i in range(len(self.z) - 1)
            ):
                issues.append("z must be strictly increasing (bottom to top)")
        if self.te is not None and any(t <= 0 for t in self.te):
            issues.append("te must be positive")
        return issues

    # ------------------------------------------------------------- deck IO
    @classmethod
    def from_deck(cls, deck: Deck, name: str = "model") -> "Atmosphere":
        def arr(key):
            s = deck.get(key)
            if s is None:
                return None
            return [v for v in s.array() if v is not None]

        def scal(key):
            s = deck.get(key)
            if s is None:
                return None
            try:
                return s.scalar
            except ValueError:
                return None

        return cls(
            name=name,
            **{attr: arr(key) for key, attr in _FIELD_KEYS.items()},
            **{attr: scal(key) for key, attr in _SCALAR_KEYS.items()},
            source_deck=deck,
        )

    @classmethod
    def read(cls, path: Union[str, Path]) -> "Atmosphere":
        path = Path(path)
        return cls.from_deck(Deck.read(path), name=path.stem)

    def to_deck(self) -> Deck:
        """Return a runnable ``.mod`` deck.

        When the Atmosphere came from a file, this is a copy of that deck
        with the physical arrays / scalars replaced in place (statements
        keep their original USE ( INPUT ) segment, which PANDORA's Part
        structure requires).  A from-scratch Atmosphere gets a fresh
        four-segment deck.
        """
        issues = self.validate()
        if issues:
            raise ValueError("model not runnable: " + "; ".join(issues))

        if self._source is not None:
            deck = _copy.deepcopy(self._source)
            for key, attr in _FIELD_KEYS.items():
                arr = getattr(self, attr)
                s = deck.get(key)
                if s is not None and arr is not None:
                    s.values = list(arr)
                elif s is None and arr is not None:
                    # new table: place it beside TE (same segment/Part)
                    deck.set(key, list(arr), after="TE")
            for key, attr in _SCALAR_KEYS.items():
                val = getattr(self, attr)
                s = deck.get(key)
                if s is not None and val is not None:
                    s.values = [val]
                elif s is None and val is not None:
                    deck.set(key, val, after="TE")
            s = deck.get("N")
            if s is not None:
                s.values = [self.n]
            return deck

        # ---- from scratch: canonical 4-segment layout
        d = Deck()
        d.items.append(Comment(f"ATMOSPHERE MODEL {self.name}"))
        d.items.append(Statement("N", [], [self.n]))
        d.items.append(Use("INPUT"))
        d.items.append(Comment(f"{self.name} - physical state"))
        for key, attr in _SCALAR_KEYS.items():
            val = getattr(self, attr)
            if val is not None:
                d.items.append(Statement(key, [], [val]))
        for key, attr in _FIELD_KEYS.items():
            arr = getattr(self, attr)
            if arr is not None:
                d.items.append(Statement(key, [], list(arr)))
        d.items.append(Use("INPUT"))
        d.items.append(Use("INPUT"))  # Part F: nothing
        d.items.append(Use("INPUT"))  # Part H: nothing (populations go here)
        return d

    def write(self, path: Union[str, Path]) -> Path:
        return self.to_deck().write(path)

    # ------------------------------------------------------------- editing
    def copy(self) -> "Atmosphere":
        return _copy.deepcopy(self)

    def with_te(self, te: Sequence[float]) -> "Atmosphere":
        atm = self.copy()
        atm.te = list(te)
        return atm

    def with_te_scaled(self, factor: float) -> "Atmosphere":
        return self.with_te([t * factor for t in self.te])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Atmosphere {self.name}: N={self.n}"
            + (
                f", TE {min(self.te):.0f}-{max(self.te):.0f} K"
                if self.te
                else ""
            )
            + ">"
        )
