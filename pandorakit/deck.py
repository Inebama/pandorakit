"""
Read, write, and edit PANDORA input decks.

PANDORA input files (.dat, .mod, .atm, .res, .pop, .rst, ...) all use the
same free-field, self-identified statement language (wup.pdf, Section 1):

    NAME j ( Q ) >

* Fields are separated by blanks; only the first 80 columns of a line are
  read.
* ``[ comment ]`` is a comment (the blanks after ``[`` and before ``]`` are
  mandatory).
* ``>`` skips the rest of the input line.
* ``GO`` terminates one of the input Parts (B, D, F, H).
* ``USE ( MODEL | ATOM | RESTART | JNU | INPUT )`` switches reading to
  another file.

Inside ``( Q )`` the value list supports control fields:

* ``M m``  -- multiplier applied to every following numeric value,
* ``I i``  -- set the array pointer (1-based) for the next value,
* ``R r``  -- repeat the next value r times,
* ``S``    -- skip an array member (leave its current/default value),
* ``F v``  -- fill the remainder of the array with v.

This module parses that language losslessly enough for round-tripping
scientific content: statements are expanded to plain value arrays
(multipliers applied, repeats/index jumps resolved), and written back out
as simple explicit lists that PANDORA reads identically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

__all__ = [
    "Comment",
    "Go",
    "Use",
    "Statement",
    "Deck",
    "SKIP",
    "Fill",
]


class _Skip:
    """Sentinel for an S (skip) entry: keep PANDORA's current value."""

    def __repr__(self) -> str:  # pragma: no cover
        return "SKIP"


SKIP = _Skip()


@dataclass
class Fill:
    """Marker for an F (fill) entry: fill the rest of the array with value."""

    value: Union[float, int, str]


@dataclass
class Comment:
    text: str


@dataclass
class Go:
    pass


@dataclass
class Use:
    target: str  # MODEL | ATOM | RESTART | JNU | INPUT


@dataclass
class Statement:
    """One PANDORA input statement.

    name     -- parameter name as written (case preserved; PANDORA is
                case-insensitive).
    indices  -- 0-2 integer indices between the name and '(' (e.g. the
                (upper, lower) level pair of 'A 3 2 ( ... )').
    values   -- expanded value list. Elements are float/int/str, SKIP, or a
                trailing Fill.
    """

    name: str
    indices: list[int] = field(default_factory=list)
    values: list = field(default_factory=list)

    @property
    def key(self) -> str:
        """Canonical lookup key, e.g. 'A 3 2' or 'TE'."""
        return " ".join([self.name.upper()] + [str(i) for i in self.indices])

    @property
    def scalar(self):
        """The single value of a scalar statement."""
        vals = [v for v in self.values if not isinstance(v, (_Skip, Fill))]
        if len(vals) != 1:
            raise ValueError(f"{self.key} has {len(vals)} values, not 1")
        return vals[0]

    def array(self, length: Optional[int] = None) -> list:
        """Values as a plain list, resolving a trailing Fill if length given."""
        out = []
        for v in self.values:
            if isinstance(v, Fill):
                if length is None:
                    raise ValueError(
                        f"{self.key} ends with F (fill); pass the array length"
                    )
                while len(out) < length:
                    out.append(v.value)
                return out
            out.append(None if isinstance(v, _Skip) else v)
        if length is not None:
            if len(out) > length:
                out = out[:length]
            while len(out) < length:
                out.append(None)
        return out


Item = Union[Comment, Go, Use, Statement]

_INT_RE = re.compile(r"[+-]?\d{1,9}$")
_FLT_RE = re.compile(
    r"[+-]?(\d+\.?\d*|\.\d+)([EeDd][+-]?\d{1,3})?$"
)


def _classify(tok: str):
    """Return int, float, or str value of a raw field, like NUDEAL."""
    if _INT_RE.match(tok):
        return int(tok)
    if _FLT_RE.match(tok) and any(c.isdigit() for c in tok):
        return float(tok.replace("D", "E").replace("d", "e"))
    return tok


def _tokenize(text: str) -> Iterator[tuple[str, bool]]:
    """Yield (field, is_line_end) pairs; honors the 80-column limit."""
    lines = text.splitlines()
    for line in lines:
        line = line[:80]
        toks = line.split()
        for i, t in enumerate(toks):
            yield t, i == len(toks) - 1
        if not toks:
            yield "", True


class Deck:
    """An ordered collection of PANDORA input items (one file)."""

    def __init__(self, items: Optional[list[Item]] = None, heading: str = ""):
        self.items: list[Item] = items or []
        self.heading = heading  # Part A comment line (main .dat only)

    # ------------------------------------------------------------- parsing
    @classmethod
    def read(cls, path: Union[str, Path], heading: bool = False) -> "Deck":
        return cls.parse(Path(path).read_text(errors="replace"), heading=heading)

    @classmethod
    def parse(cls, text: str, heading: bool = False) -> "Deck":
        deck = cls()
        toks = list(_tokenize(text))
        pos = 0

        if heading and toks:
            # Part A: the entire first line is the HEADING comment.
            first_line_end = next(
                (i for i, (_, eol) in enumerate(toks) if eol), 0
            )
            line_toks = [t for t, _ in toks[: first_line_end + 1] if t]
            deck.heading = " ".join(line_toks)
            pos = first_line_end + 1

        def skip_line(i: int) -> int:
            while i < len(toks) and not toks[i][1]:
                i += 1
            return i + 1

        while pos < len(toks):
            tok, eol = toks[pos]
            if tok == "":
                pos += 1
                continue
            if tok == ">":
                pos = skip_line(pos)
                continue
            if tok == "[":
                # comment runs to the matching ']' field (across lines)
                j = pos + 1
                words = []
                while j < len(toks) and toks[j][0] != "]":
                    if toks[j][0]:
                        words.append(toks[j][0])
                    j += 1
                deck.items.append(Comment(" ".join(words)))
                pos = j + 1
                continue
            if tok.upper() == "GO":
                deck.items.append(Go())
                pos += 1
                continue
            # a statement: NAME [idx [idx]] ( values )
            name = tok
            indices: list[int] = []
            j = pos + 1
            while j < len(toks) and toks[j][0] != "(":
                t = toks[j][0]
                if t == "":
                    j += 1
                    continue
                if _INT_RE.match(t):
                    indices.append(int(t))
                    j += 1
                elif t == ">":
                    j = skip_line(j)
                else:
                    # Not a statement after all (stray field) - drop `name`
                    break
            if j >= len(toks) or toks[j][0] != "(":
                pos += 1  # stray token; skip it
                continue
            # collect value fields until the matching ')'
            j += 1
            values: list = []
            mult: Optional[Union[int, float]] = None
            pending_repeat = 1
            pending_index: Optional[int] = None

            def push(v):
                nonlocal pending_repeat, pending_index
                if isinstance(v, (int, float)) and mult is not None:
                    v = v * mult
                for _ in range(pending_repeat):
                    if pending_index is not None:
                        while len(values) < pending_index - 1:
                            values.append(SKIP)
                        if len(values) >= pending_index:
                            values[pending_index - 1] = v
                        else:
                            values.append(v)
                    else:
                        values.append(v)
                    if pending_index is not None:
                        pending_index += 1
                pending_repeat = 1
                pending_index = None

            while j < len(toks):
                t, teol = toks[j]
                if t == "":
                    j += 1
                    continue
                if t == ")":
                    break
                if t == ">":
                    j = skip_line(j)
                    continue
                if t == "[":
                    while j < len(toks) and toks[j][0] != "]":
                        j += 1
                    j += 1
                    continue
                u = t.upper()
                if u == "M":
                    j += 1
                    while toks[j][0] in ("", ">"):
                        j = skip_line(j) if toks[j][0] == ">" else j + 1
                    mult = _classify(toks[j][0])
                    j += 1
                    continue
                if u == "I":
                    j += 1
                    while toks[j][0] in ("", ">"):
                        j = skip_line(j) if toks[j][0] == ">" else j + 1
                    pending_index = int(toks[j][0])
                    j += 1
                    continue
                if u == "R":
                    j += 1
                    while toks[j][0] in ("", ">"):
                        j = skip_line(j) if toks[j][0] == ">" else j + 1
                    pending_repeat = int(toks[j][0])
                    j += 1
                    continue
                if u == "S":
                    for _ in range(pending_repeat):
                        values.append(SKIP)
                    pending_repeat = 1
                    j += 1
                    continue
                if u == "F":
                    j += 1
                    while toks[j][0] in ("", ">"):
                        j = skip_line(j) if toks[j][0] == ">" else j + 1
                    v = _classify(toks[j][0])
                    if isinstance(v, (int, float)) and mult is not None:
                        v = v * mult
                    values.append(Fill(v))
                    j += 1
                    continue
                push(_classify(t))
                j += 1

            stmt = Statement(name=name, indices=indices, values=values)
            if name.upper() == "USE":
                deck.items.append(Use(str(stmt.values[0]).upper()))
            else:
                deck.items.append(stmt)
            pos = j + 1

        return deck

    # ------------------------------------------------------------- access
    def statements(self) -> Iterator[Statement]:
        for it in self.items:
            if isinstance(it, Statement):
                yield it

    def get(self, key: str, part: Optional[int] = None) -> Optional[Statement]:
        """Find a statement by canonical key ('TE', 'A 3 2', ...).

        part -- restrict the search to input Part 1..4 (B, D, F, H),
                counting GO separators.
        """
        key = " ".join(key.upper().split())
        n_go = 0
        for it in self.items:
            if isinstance(it, Go):
                n_go += 1
            if isinstance(it, Statement) and it.key == key:
                if part is None or n_go == part - 1:
                    return it
        return None

    def get_all(self, name: str) -> list[Statement]:
        name = name.upper()
        return [s for s in self.statements() if s.name.upper() == name]

    def set(
        self,
        key: str,
        values,
        part: Optional[int] = None,
        after: Optional[str] = None,
    ) -> Statement:
        """Set (replace or append) a statement's values.

        key    -- e.g. 'TE', 'A 3 2', 'CE 2 1'.
        values -- scalar or iterable.
        part   -- when appending, which Part (1=B, 2=D, 3=F, 4=H) to
                  append to (default: last part present, else Part B).
        after  -- when appending, insert after this statement key.
        """
        if not isinstance(values, (list, tuple)):
            values = [values]
        values = list(values)
        fields = key.upper().split()
        name = fields[0]
        indices = [int(f) for f in fields[1:]]
        existing = self.get(key, part=part)
        if existing is not None:
            existing.values = values
            return existing
        stmt = Statement(name=name, indices=indices, values=values)
        insert_at = None
        if after is not None:
            tgt = self.get(after, part=part)
            if tgt is not None:
                insert_at = self.items.index(tgt) + 1
        if insert_at is None:
            if part is not None:
                # position of the (part-1)-th GO .. part-th GO
                gos = [i for i, it in enumerate(self.items) if isinstance(it, Go)]
                while len(gos) < part:
                    self.items.append(Go())
                    gos = [
                        i for i, it in enumerate(self.items) if isinstance(it, Go)
                    ]
                insert_at = gos[part - 1]
            else:
                insert_at = len(self.items)
        self.items.insert(insert_at, stmt)
        return stmt

    def remove(self, key: str) -> bool:
        s = self.get(key)
        if s is None:
            return False
        self.items.remove(s)
        return True

    # ------------------------------------------------------------- writing
    @staticmethod
    def _fmt(v) -> str:
        if isinstance(v, _Skip):
            return "S"
        if isinstance(v, Fill):
            return f"F {Deck._fmt(v.value)}"
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            if v == 0:
                return "0."
            if 1e-3 <= abs(v) < 1e5 and float(f"{v:.10g}") == v:
                s = f"{v:.10g}"
                return s if ("." in s or "e" in s or "E" in s) else s + "."
            return f"{v:.8E}"
        return str(v)

    def dumps(self) -> str:
        lines: list[str] = []
        if self.heading:
            h = self.heading
            if not (h.startswith("[") or h.startswith(">")):
                h = f"[ {h} ]"
            lines.append(h)
        for it in self.items:
            if isinstance(it, Comment):
                lines.append(f"[ {it.text} ] >")
            elif isinstance(it, Go):
                lines.append("GO >")
            elif isinstance(it, Use):
                lines.append(f"USE ( {it.target} ) >")
            else:
                head = " ".join([it.name] + [str(i) for i in it.indices])
                fields = [self._fmt(v) for v in it.values]
                line = f"{head} ( "
                out = []
                for fdx, fld in enumerate(fields):
                    sep = "" if fdx == 0 else " "
                    if len(line) + len(sep) + len(fld) > 76:
                        out.append(line + " >")
                        line = " " + fld
                    else:
                        line += sep + fld
                out.append(line + " ) >")
                lines.extend(out)
        return "\n".join(lines) + "\n"

    def write(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        path.write_text(self.dumps())
        return path

    # ------------------------------------------------------------- misc
    def __repr__(self) -> str:  # pragma: no cover
        n = sum(1 for _ in self.statements())
        return f"<Deck: {n} statements, {len(self.items)} items>"
