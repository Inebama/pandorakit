"""
Parse PANDORA output files.

The main printout (``.aaa``) is a line-printer document divided into
"print sections".  The companion index file (``.aix``) lists each section
with its PSN (print section number); in the ``.aaa`` file each section
starts with a line beginning ``1PSNnnnnnn`` (the leading ``1`` is Fortran
carriage control for a page eject).

``AaaFile`` reproduces (natively) what the historical ``extract`` csh
script did with sed: pull one section and convert it to machine-readable
rows.  On top of that it parses the most-used sections into columnar data:
emergent line profiles (``PROF (u/l)``), continuum spectra, and any
generic numeric table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

__all__ = ["AaaFile", "Section", "ProfileBlock", "read_profile_blocks"]


@dataclass
class Section:
    psn: int
    title: str
    text: str

    def machine_readable(self) -> list[str]:
        """The section as the `extract` script would emit it.

        Comment lines are prefixed with ';', data rows are cleaned of
        decorations: parentheses become spaces, 'X'/'_' placeholders
        become 0, ' -- ' becomes ' 0 ', the ' nano ' unit tag is blanked.
        """
        out = []
        for line in self.text.splitlines():
            if not line.strip():
                continue
            if line.startswith("1PSN") or line.startswith("\f"):
                out.append(";" + line)
                continue
            if re.match(r"^  *\d+ ", line):
                row = line
                row = row.split("!")[0]  # trailing annotations
                row = re.sub(r"[><)(]", " ", row)
                row = re.sub(r"[X_]", "0", row)
                row = row.replace(" -- ", "  0 ")
                row = row.replace(" nano ", "      ")
                out.append(row.rstrip())
            else:
                out.append("; " + line.rstrip())
        return out

    def rows(self) -> list[list[float]]:
        """All numeric data rows (index column included)."""
        rows = []
        for line in self.machine_readable():
            if line.startswith(";"):
                continue
            vals = []
            ok = True
            for tok in line.split():
                try:
                    vals.append(float(tok))
                except ValueError:
                    ok = False
                    break
            if ok and vals:
                rows.append(vals)
        return rows


@dataclass
class ProfileBlock:
    """One emergent-intensity block of a 'PROF (u/l)' print section.

    kind is one of:

    * ``line_profile``        -- the emergent line profile; ``wl`` is DL,
      the distance from line center in Angstroms;
    * ``background_intensity`` / ``background_flux`` -- the line-specific
      background continuum (absolute wavelength in Angstroms);
    * ``linefree_intensity``  / ``linefree_flux``    -- line-free
      reference spectrum (absolute wavelength).

    mu is the viewing angle cosine, or None for flux blocks.
    For line_profile blocks, ``residual`` holds I/Hz divided by the
    line-free intensity (the residual profile), when printed.
    """

    kind: str
    mu: Optional[float]
    wl: list[float] = field(default_factory=list)  # A (absolute or DL)
    inu: list[float] = field(default_factory=list)  # erg/cm2/s/sr/Hz
    ilam: list[float] = field(default_factory=list)  # erg/cm2/s/sr/A
    tb: list[float] = field(default_factory=list)  # K
    residual: list[float] = field(default_factory=list)
    line_center: Optional[float] = None  # A (line_profile blocks)
    case: Optional[str] = None  # 'Stationary' / 'Moving, ...' annotation
    redistribution: Optional[str] = None  # 'CRD' / 'PRD' when printed
    is_flux: bool = False  # True when columns are F/A, F/Hz (flux profile)


_KIND_PATTERNS = [
    (re.compile(r"Background Intensity", re.I), "background_intensity"),
    (re.compile(r"Background Flux", re.I), "background_flux"),
    (re.compile(r"Line-free Intensity", re.I), "linefree_intensity"),
    (re.compile(r"Line-free Flux", re.I), "linefree_flux"),
    (re.compile(r"Profile of the\s+\d+/\s*\d+\s+Line", re.I), "line_profile"),
]
_CENTER_RE = re.compile(
    r"Profile of the\s+\d+/\s*\d+\s+Line at\s+([0-9.E+-]+)\s+Angstroms", re.I
)


def _floats(tokens):
    vals = []
    for t in tokens:
        try:
            vals.append(float(t))
        except ValueError:
            return None
    return vals


def read_profile_blocks(section: Section) -> list[ProfileBlock]:
    """Parse all intensity/flux blocks of a 'PROF (u/l)' section.

    Handles both the per-mu intensity layout (plane-parallel runs:
    ``DL (flags) I/A I/Hz Residual II IIS TB``) and the flux layout
    (spherical runs: ``DL SHLR F/A F/Hz Residual IF IFS TB``), mapping
    columns by the header names PANDORA prints above each table.
    """
    blocks: list[ProfileBlock] = []
    kind = None
    center = None
    case = None
    redis = None
    colnames: list[str] = []
    cur: Optional[ProfileBlock] = None

    def new_block(mu, is_flux=False):
        nonlocal cur
        cur = ProfileBlock(
            kind=kind or "unknown",
            mu=mu,
            line_center=center,
            case=case,
            redistribution=redis,
            is_flux=is_flux,
        )
        blocks.append(cur)

    for raw in section.text.splitlines():
        for pat, k in _KIND_PATTERNS:
            if pat.search(raw):
                kind = k
                cur = None
                colnames = []
                m = _CENTER_RE.search(raw)
                if m:
                    center = float(m.group(1))
                if k.endswith("_flux"):
                    new_block(None, is_flux=True)
                break
        m = re.search(r"Case:\s*(\S.*?)\s{2,}", raw + "  ")
        if m and "Case:" in raw:
            case = m.group(1).strip()
            continue
        if re.search(r"Complete redistribution", raw, re.I):
            redis = "CRD"
            continue
        if re.search(r"Partial [Rr]edistribution", raw):
            redis = "PRD"
            continue
        m = re.search(r"Mu\s*=\s*([0-9.]+)", raw)
        if m and kind:
            new_block(float(m.group(1)))
            continue
        # column-header line, e.g. "DL  SHLR  F/A  F/Hz  Residual  IF..."
        # (legend lines like "DL       = Distance from ..." contain '=')
        stripped = raw.split()
        if (
            stripped
            and stripped[0] in ("DL", "WL")
            and len(stripped) > 2
            and "=" not in raw
        ):
            colnames = [
                t for t in re.sub(r"\([^)]*\)", " ", raw).split()
            ]
            if kind == "line_profile" and cur is None:
                # flux-style line profile: no Mu headers at all
                new_block(None, is_flux=("F/A" in colnames))
            continue
        if cur is None or not re.match(r"^  *\d+ ", raw):
            continue
        row = raw.split("!")[0]
        row = re.sub(r"\([^)]*\)", " ", row)  # (F KS KI) flags
        row = row.replace(" nano ", " ")
        vals = _floats(row.split())
        if not vals or len(vals) < 4:
            continue
        data = vals[1:]  # drop the index column

        if cur.kind == "line_profile":
            # Layouts (trailing IF/IFS may be blank in moving cases):
            #   flux:      DL SHLR F/A F/Hz Residual [IF IFS] TB
            #   intensity: DL      I/A I/Hz Residual [II IIS] TB
            off = 1 if "SHLR" in colnames else 0
            if len(data) < 3 + off:
                continue
            cur.wl.append(data[0])
            cur.ilam.append(data[1 + off])
            cur.inu.append(data[2 + off])
            cur.tb.append(data[-1])
            if len(data) >= 5 + off:
                cur.residual.append(data[3 + off])
        else:
            # idx, WL, WVL, [OM,] I(F)/Hz, I(F)/A, TB
            cur.wl.append(data[0])
            cur.inu.append(data[-3])
            cur.ilam.append(data[-2])
            cur.tb.append(data[-1])
    return [b for b in blocks if b.wl]


class AaaFile:
    """A PANDORA main printout (.aaa) with its index (.aix)."""

    def __init__(
        self,
        aaa: Union[str, Path],
        aix: Union[str, Path, None] = None,
    ):
        self.path = Path(aaa)
        if aix is None:
            aix = Path(str(aaa).replace(".aaa.", ".aix."))
            if not Path(aix).exists():
                aix = None
        self.aix_path = Path(aix) if aix else None
        self._text = self.path.read_text(errors="replace")
        self._index = self._read_index()

    def _read_index(self) -> list[tuple[int, str]]:
        entries: list[tuple[int, str]] = []
        if self.aix_path and self.aix_path.exists():
            for line in self.aix_path.read_text(errors="replace").splitlines():
                m = re.match(r"^.?PSN(\d+)\s+(.*?)\s+OVER=", line)
                if m:
                    entries.append((int(m.group(1)), m.group(2).strip()))
        else:
            for m in re.finditer(r"^1PSN(\d+)\s+(.+?)\s{2,}", self._text, re.M):
                entries.append((int(m.group(1)), m.group(2).strip()))
        return entries

    @property
    def sections(self) -> list[tuple[int, str]]:
        return list(self._index)

    def find(self, title: str) -> list[tuple[int, str]]:
        """Case-insensitive substring match over section titles."""
        t = title.lower()
        return [(p, s) for p, s in self._index if t in s.lower()]

    def section(self, title: Union[str, int]) -> Section:
        """Extract one section by (sub)title or PSN number."""
        if isinstance(title, int):
            matches = [(p, s) for p, s in self._index if p == title]
        else:
            # exact title first, else unique substring
            matches = [
                (p, s)
                for p, s in self._index
                if s.strip().lower() == str(title).strip().lower()
            ]
            if not matches:
                matches = self.find(str(title))
        if not matches:
            raise KeyError(f"section {title!r} not found; see .sections")
        if len(matches) > 1:
            raise KeyError(
                f"section {title!r} is ambiguous: {[s for _, s in matches]}"
            )
        psn, name = matches[0]
        start = re.search(rf"^1PSN0*{psn}\b.*$", self._text, re.M)
        if not start:
            raise KeyError(f"PSN{psn} marker not found in {self.path}")
        nxt = re.compile(r"^1PSN\d+", re.M)
        m2 = nxt.search(self._text, start.end())
        text = self._text[start.start() : m2.start() if m2 else len(self._text)]
        return Section(psn=psn, title=name, text=text)

    # ------------------------------------------------------- conveniences
    def profile(self, upper: int, lower: int) -> list[ProfileBlock]:
        """Emergent line profile blocks for transition (upper/lower)."""
        sec = self.section(f"PROF ({upper}/{lower})")
        return read_profile_blocks(sec)

    def extract(self, title: Union[str, int], out: Union[str, Path]) -> Path:
        """Write a section in machine-readable form (like `extract`)."""
        sec = self.section(title)
        out = Path(out)
        out.write_text("\n".join(sec.machine_readable()) + "\n")
        return out

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AaaFile {self.path.name}: {len(self._index)} sections>"
