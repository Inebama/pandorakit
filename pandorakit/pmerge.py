"""
Merge tables from a PANDORA .pop restart file into a model deck.

Python port of the historical `pmerge` Perl script.  After a run of a
"population ion" (H, He I, ...), the ``.pop`` output contains updated
tables (NE, NP, HN j, BDH j, HE tables, ...) that should replace the
values in the atmosphere model (``.mod``) before the next run of the
chain (see demos/6: H -> He I -> Ca II).

Shorthands (same as the Perl tool):

* ``@NE+``  ==  NE, NP, HN 1..NLH, BDH 1..NLH   (after a Hydrogen run)
* ``@NP+``  ==  NP, HN 1..NLH, BDH 1..NLH
* ``@HE+``  ==  HE, HE1 1..N, BDHE1 1..N  (after a He I run: HE table etc.)

plus explicit comma-separated names; ``HN_1-15`` expands to HN 1 .. HN 15.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

from .deck import Deck, Statement

__all__ = ["merge_pop", "expand_spec"]


def _pop_keys(pop: Deck) -> list[str]:
    return [s.key for s in pop.statements()]


def expand_spec(spec: str, pop: Deck) -> list[str]:
    """Expand a pmerge VALUES spec into a list of canonical statement keys."""
    keys: list[str] = []
    avail = _pop_keys(pop)
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if item == "@NE+":
            keys += [k for k in avail if k == "NE"]
            keys += expand_spec("@NP+", pop)
            continue
        if item == "@NP+":
            keys += [k for k in avail if k == "NP"]
            keys += [k for k in avail if re.match(r"^(HN|BDH) \d+$", k)]
            continue
        if item == "@HE+":
            keys += [
                k
                for k in avail
                if k == "HE"
                or k == "RHEAB"
                or re.match(r"^(HE1|BDHE1|HEN|BDHE) \d+$", k)
            ]
            continue
        item = item.replace("_", " ")
        m = re.match(r"^(.*?)(\d+)-(\d+)$", item)
        if m:
            stem, lo, hi = m.group(1).strip(), int(m.group(2)), int(m.group(3))
            keys += [f"{stem} {i}" for i in range(lo, hi + 1)]
        else:
            keys.append(" ".join(item.upper().split()))
    # keep order, drop duplicates
    seen = set()
    out = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def merge_pop(
    spec: str,
    pop: Union[str, Path, Deck],
    mod: Union[str, Path, Deck],
    out: Union[str, Path, None] = None,
) -> Deck:
    """Copy the named tables from `pop` into `mod`.

    Tables already present in the model are replaced in place; new ones
    are appended to the Part where their kin live (populations go to
    Part H region for restart-style models, otherwise appended at the
    end, which PANDORA reads equivalently within the right Part).

    Returns the merged deck; writes it to `out` if given.
    """
    pop_deck = pop if isinstance(pop, Deck) else Deck.read(pop)
    mod_deck = mod if isinstance(mod, Deck) else Deck.read(mod)
    keys = expand_spec(spec, pop_deck)
    missing = []
    for key in keys:
        src = pop_deck.get(key)
        if src is None:
            missing.append(key)
            continue
        dst = mod_deck.get(key)
        if dst is not None:
            dst.values = list(src.values)
        else:
            fields = key.split()
            mod_deck.items.append(
                Statement(fields[0], [int(x) for x in fields[1:]],
                          list(src.values))
            )
    if missing:
        raise KeyError(
            f"tables not found in .pop file: {missing}; "
            f"available: {_pop_keys(pop_deck)}"
        )
    if out is not None:
        mod_deck.write(out)
    return mod_deck
