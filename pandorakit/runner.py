"""
Run PANDORA without the historical csh wrappers.

PANDORA (a fixed-form Fortran 77 program) does not open files by name: it
reads and writes fixed logical units, which appear on disk as ``fort.NN``
in the working directory (gfortran convention).  This module stages an
isolated run directory with ``fort.NN`` symlinks for the inputs, executes
``pandora.x`` there, and harvests the outputs under their traditional
names (``<case>.aaa.<runid>`` etc.).

This works with any Fortran compiler's build of pandora.x whose unnamed
units default to ``fort.NN`` (gfortran, and also ifort/PGI builds when the
FORT*/FOR0* environment variables are not set).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from .deck import Deck

__all__ = ["PandoraInstall", "PandoraRun", "RunResult", "PandoraError"]

# logical unit -> (role, traditional extension)
INPUT_UNITS = {
    3: "dat",  # main run-specific input deck (required)
    4: "mod",  # atmosphere model (optional; via USE ( MODEL ))
    7: "atm",  # atomic model (optional; via USE ( ATOM ))
    8: "res",  # restart data (optional; via USE ( RESTART ))
    9: "jnu",  # PRD JNU restart values (optional)
}
TABLE_UNITS = {
    10: "statistical.dat",
    11: "composite.dat",
    12: "average.dat",
}
OUTPUT_UNITS = {
    1: "tmp",  # direct-access scratch (deleted afterwards)
    15: "aaa",  # main printout
    16: "aer",  # error messages / debug
    19: "rst",  # restart data (line source functions etc.)
    20: "msc",  # miscellaneous restart data
    21: "pop",  # populations restart data
    22: "jnr",  # PRD JNU values
    23: "spc",  # emergent spectrum results
    24: "coo",  # cooling rates
    25: "csp",  # continuum data (machine readable)
    26: "mat",  # sample matrices
    27: "tsf",  # source-function related data
    29: "jrl",  # journal (input statements as read)
    30: "itr",  # iterative studies data
    31: "aix",  # printout index
    32: "cks",  # checksums
    97: "smd",  # world/iworld dump
}
ARCHIVE_UNIT = 28  # run_archive.txt (append)
SYSDATA_UNIT = 98  # 'uname -a' output


class PandoraError(RuntimeError):
    pass


@dataclass
class PandoraInstall:
    """Locations of the PANDORA executable and its data tables.

    root -- a directory that contains ``bin/pandora.x`` plus the table
    directories ``atoms/`` and ``opacities/`` (the layout produced by the
    installation guide; e.g. ``~/pandora`` holding v2.2.0/bin and
    v2.1.1/{atoms,opacities}).  Individual paths can be overridden.
    """

    root: Union[str, Path] = Path.home() / "pandora"
    executable: Optional[Path] = None
    atoms_dir: Optional[Path] = None
    opacities_dir: Optional[Path] = None

    def __post_init__(self):
        self.root = Path(self.root).expanduser()
        if self.executable is None:
            for cand in (
                self.root / "bin" / "pandora.x",
                self.root / "v2.2.0" / "bin" / "pandora.x",
            ):
                if cand.exists():
                    self.executable = cand
                    break
        if self.executable is None:
            raise PandoraError(
                f"pandora.x not found under {self.root}; "
                "pass executable= explicitly"
            )
        self.executable = Path(self.executable).expanduser()
        if self.atoms_dir is None:
            for cand in (self.root / "atoms", self.root / "v2.1.1" / "atoms"):
                if cand.exists():
                    self.atoms_dir = cand
                    break
        if self.opacities_dir is None:
            for cand in (
                self.root / "opacities",
                self.root / "v2.1.1" / "opacities",
            ):
                if cand.exists():
                    self.opacities_dir = cand
                    break
        if self.atoms_dir is None or self.opacities_dir is None:
            raise PandoraError(
                f"atoms/ or opacities/ tables not found under {self.root}"
            )
        self.atoms_dir = Path(self.atoms_dir).expanduser()
        self.opacities_dir = Path(self.opacities_dir).expanduser()

    def atom_file(self, atom: str, levels: Union[int, str, None] = None) -> Path:
        """Resolve an atomic model, e.g. atom_file('h', 15) -> atoms/hl15.atm."""
        if levels is None:
            name = atom if atom.endswith(".atm") else f"{atom}.atm"
        else:
            lev = str(levels)
            if not lev.startswith("l"):
                lev = f"l{lev}"
            name = f"{atom}{lev}.atm"
        p = self.atoms_dir / name
        if not p.exists():
            avail = sorted(f.name for f in self.atoms_dir.glob(f"{atom}*.atm"))
            raise PandoraError(
                f"atomic model {name} not found in {self.atoms_dir}; "
                f"available for '{atom}': {avail}"
            )
        return p


@dataclass
class RunResult:
    case: str
    run_id: str
    directory: Path
    returncode: int
    elapsed: float
    log: str
    outputs: dict[str, Path] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when PANDORA printed its normal-completion message."""
        return self.returncode == 0 and "PANDORA done" in self.log

    @property
    def aborted(self) -> bool:
        return "ABORT" in self.log or any(
            "ABORT  stopped this run" in self._tail(p)
            for k, p in self.outputs.items()
            if k == "aaa"
        )

    @staticmethod
    def _tail(path: Path, n: int = 4096) -> str:
        try:
            with open(path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - n))
                return f.read().decode(errors="replace")
        except OSError:
            return ""

    def output(self, ext: str) -> Path:
        if ext not in self.outputs:
            raise KeyError(
                f"no .{ext} output; available: {sorted(self.outputs)}"
            )
        return self.outputs[ext]

    def __repr__(self) -> str:  # pragma: no cover
        state = "ok" if self.ok else "FAILED"
        return (
            f"<RunResult {self.case}.{self.run_id}: {state}, "
            f"{self.elapsed:.1f}s, outputs={sorted(self.outputs)}>"
        )


class PandoraRun:
    """Stage and execute one PANDORA run.

    Typical use::

        install = PandoraInstall("~/pandora")
        run = PandoraRun(install, case="suna", run_id="001",
                         dat="sun_a.dat", mod="sun.mod",
                         atom=("h", 15), workdir="runs")
        result = run.execute()
        assert result.ok
    """

    def __init__(
        self,
        install: PandoraInstall,
        case: str,
        run_id: str = "001",
        dat: Union[str, Path, Deck, None] = None,
        mod: Union[str, Path, Deck, None] = None,
        atm: Union[str, Path, Deck, None] = None,
        atom: Union[tuple, str, None] = None,
        res: Union[str, Path, Deck, None] = None,
        jnu: Union[str, Path, None] = None,
        workdir: Union[str, Path] = "runs",
        keep_scratch: bool = False,
    ):
        self.install = install
        self.case = case
        self.run_id = str(run_id)
        self.workdir = Path(workdir).expanduser()
        self.keep_scratch = keep_scratch
        if dat is None:
            raise PandoraError("a .dat input deck is required (dat=...)")
        if atm is None and atom is not None:
            if isinstance(atom, (tuple, list)):
                atm = install.atom_file(*atom)
            else:
                atm = install.atom_file(atom)
        self.sources: dict[int, Union[Path, Deck, None]] = {
            3: self._as_source(dat),
            4: self._as_source(mod),
            7: self._as_source(atm),
            8: self._as_source(res),
            9: self._as_source(jnu),
        }

    @staticmethod
    def _as_source(x):
        if x is None or isinstance(x, Deck):
            return x
        return Path(x).expanduser().resolve()

    # ------------------------------------------------------------------
    def execute(
        self,
        timeout: Optional[float] = None,
        overwrite: bool = False,
    ) -> RunResult:
        rundir = self.workdir / f"{self.case}.{self.run_id}"
        if rundir.exists():
            if not overwrite:
                raise PandoraError(
                    f"run directory {rundir} already exists "
                    "(pass overwrite=True to replace it)"
                )
            shutil.rmtree(rundir)
        rundir.mkdir(parents=True)

        # ---- stage inputs as fort.NN
        for unit, src in self.sources.items():
            tgt = rundir / f"fort.{unit}"
            if src is None:
                # Units 8/9 (restart / JNU) may be "empty" -- but PANDORA's
                # reader crashes on a 0-byte file: an empty restart must
                # contain USE ( INPUT ) so reading hands control straight
                # back (cf. demos/2/demo2h.res).
                if unit in (8, 9):
                    tgt.write_text("USE ( INPUT ) >\n")
                continue
            if isinstance(src, Deck):
                src.write(rundir / f"{self.case}.{INPUT_UNITS[unit]}")
                tgt.symlink_to(f"{self.case}.{INPUT_UNITS[unit]}")
            else:
                if not src.exists():
                    raise PandoraError(f"input for unit {unit} missing: {src}")
                tgt.symlink_to(src)
        for unit, name in TABLE_UNITS.items():
            src = self.install.opacities_dir / name
            if not src.exists():
                raise PandoraError(f"opacity table missing: {src}")
            (rundir / f"fort.{unit}").symlink_to(src)

        # ---- run archive + system data
        (rundir / f"fort.{ARCHIVE_UNIT}").touch()
        uname = subprocess.run(
            ["uname", "-a"], capture_output=True, text=True
        ).stdout
        (rundir / f"fort.{SYSDATA_UNIT}").write_text(uname)

        # ---- execute
        t0 = time.time()
        proc = subprocess.run(
            [str(self.install.executable)],
            cwd=rundir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - t0
        log = proc.stdout + proc.stderr
        (rundir / f"{self.case}.log.{self.run_id}").write_text(log)

        # ---- harvest outputs
        outputs: dict[str, Path] = {}
        for unit, ext in OUTPUT_UNITS.items():
            f = rundir / f"fort.{unit}"
            if f.exists() and f.stat().st_size > 0:
                if ext == "tmp" and not self.keep_scratch:
                    f.unlink()
                    continue
                new = rundir / f"{self.case}.{ext}.{self.run_id}"
                f.rename(new)
                outputs[ext] = new
            elif f.exists():
                f.unlink()
        # clean up unit symlinks and empty placeholders
        for f in rundir.glob("fort.*"):
            if f.is_symlink() or f.stat().st_size == 0:
                f.unlink()

        result = RunResult(
            case=self.case,
            run_id=self.run_id,
            directory=rundir,
            returncode=proc.returncode,
            elapsed=elapsed,
            log=log,
            outputs=outputs,
        )
        return result
