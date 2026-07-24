# Installing PANDORA + pandorakit

This guide takes a clean machine to a verified, working PANDORA
installation with the `pandorakit` Python interface. It was developed and
tested on macOS (Apple Silicon, macOS 26, gfortran 14 from MacPorts); the
same recipe works on Linux with gfortran ≥ 10 (see the Linux notes at the
end).

PANDORA itself is distributed by the Harvard-Smithsonian CfA at
<https://lweb.cfa.harvard.edu/~avrett/pandora/> (releases under
`releases/`). It is Fortran 77, ~4,500 routines, last released in 2014
(release 2.2.0 = program version 79.009). It does **not** build cleanly
with a modern compiler out of the box — a small set of patches is
required, all included here and explained below.

---

## 0. Prerequisites

* A Fortran compiler. Tested: **gfortran 14** (MacPorts `gcc14`;
  Homebrew `brew install gcc` also provides it as `gfortran`).
* `make`, `csh` (macOS ships csh; Linux: `apt install csh` — only needed
  for the optional classic wrapper scripts), `perl` (for `pmerge`,
  optional), Python ≥ 3.9 for pandorakit.
* ~1 GB of disk for sources + tables + demo outputs.

## 1. Get the archives

Download into e.g. `~/Downloads/Pandora/`:

```
pandora-v2.2.0-src.tgz        source code
pandora-v2.1.1-tables.tgz     atomic data + opacity tables
pandora-v2.1.1-demos.tgz      demo cases 1-7
pandora-v2.1.1-doc.tgz        documentation (wup.pdf: the 368-page writeup)
pandora-v2.1.1-demo-refs.tgz  reference outputs for the demos (optional
                              but recommended: lets you verify your build)
```

from `https://lweb.cfa.harvard.edu/~avrett/pandora/releases/`.

## 2. Automated install

The repository ships `install.sh` which performs every step below
(extract, patch, build with the correct per-directory flags, install,
run demo 1, and compare against your extracted demo references):

```bash
cd pandorakit
./install.sh ~/Downloads/Pandora ~/pandora
```

If it prints `INSTALL VERIFIED` at the end you are done; continue with
step 6 (Python package). The rest of this document explains what it does
and how to do it by hand.

## 3. Manual: extract and patch

```bash
mkdir -p ~/pandora && cd ~/pandora
tar xzf /path/to/pandora-v2.2.0-src.tgz
tar xzf /path/to/pandora-v2.1.1-tables.tgz
tar xzf /path/to/pandora-v2.1.1-demos.tgz
tar xzf /path/to/pandora-v2.1.1-doc.tgz
tar xzf /path/to/pandora-v2.1.1-demo-refs.tgz   # optional
cd v2.2.0
patch -p1 < /path/to/pandorakit/patches/pandora-v2.2.0-gfortran.patch
```

### What the patch does (and why)

All changes are compiler-portability fixes; none alter the physics.
One latent logic bug is fixed (noted below). Summary:

| Files | Change | Reason |
|---|---|---|
| `sys/luck.f`, `sys/muck.f`, `sys/puck.f`, `util/cents.f`, `util/lookat.f` | `READONLY` → `action='READ'` | `READONLY` is a DEC VMS extension; `action='READ'` is the standard equivalent. |
| `sys/percord.f` | `close(..., disp='KEEP')` → `status='KEEP'` | Same: DEC spelling of a standard keyword. |
| `sys/get_date.F` | compile the Intel `idate()` branch for gfortran too | gfortran's `idate` returns (day, month, year) like ifort's; the PGI branch would swap day and month in every date stamp. |
| `sys/second.f`, `sys/calypso.f`, `sys/get_time.f`, `sys/get_date.F` | remove `external etime/flush/itime/idate` | These are *intrinsics* in gfortran; declaring them `external` makes the linker look for symbols libgfortran does not export. |
| `sys/is_xxx-gfortran.f` | new file (copy of `is_xxx-ieee.f`) | The build system selects `is_xxx-$(FC).f`; the IEEE_ARITHMETIC variant is exactly right for gfortran. |
| `zoo/abject.f`, `util/lookat.f` | `'0C'X` → `12` | DEC hex-constant syntax; the value is ASCII form-feed (12). |
| `util/ready.f`, `util/cents.f`, `util/lookat.f` | `ACCEPT n, x` → `READ n, x` | `ACCEPT` is a DEC I/O statement. |
| `pan/abakan.f` | `(NSW)` → `(NSW.gt.0)` in a logical `.or.` | **Latent bug**: `NSW` is an INTEGER; DEC/PGI compilers accepted it as a logical operand testing the *low bit* (i.e. true iff NSW is odd) — clearly not the intent. |
| `pan/anatini.f` | `.or.JATAW` → `.or.(JATAW.gt.0)` | Same pattern (compare `FWRAT = (JATAW.gt.0)` two lines above). |
| `pan/caramba.f`, `pan/hydru.f` | `if(N1NUP)` / `if(JSSV)` → `.ne.0` | Integer 0/1 switches used as logicals. |
| `pan/drink.f` | `if(DUMP.gt.0)` → `if(DUMP)` | `DUMP` is a LOGICAL compared as an integer. |
| `pan/elima.f` | remove dead `data GO /.false./` | `GO` is neither declared nor used; implicit typing makes it REAL and the DATA statement a type error. |
| `util/Makefile.inc` | link `panlib.a`+`zoolib.a` into `cents.x`, `ready.x`, `modup.x` | `syslib`'s `run_data.f` calls `ABORT`, which lives in `panlib`; the PGI/Intel runtimes masked this by providing their own `abort_`. |
| `sbin/setFORx-gfortran.sou` (new), `sbin/FORxxx`, `sbin/pandora` | gfortran unit-mapping mode | See "How PANDORA finds its files" below. |

## 4. Manual: build

**The single most important thing on this page:**

> **`sys/` must be compiled at `-O0`.**
>
> The MEMOIR scratch-I/O routines (`sys/me*.f`) address a large buffer
> through a COMMON array declared `SIOBUF(1)` — a classic F77 trick that
> is undefined behavior under modern optimizers. With gfortran at `-O1`
> or above, PANDORA runs but its in-memory continuum-block cache returns
> garbage and every run dies with
> `Trouble reading Continuum Block at address = ...` followed by an
> ABORT from `LETTER`. At `-O0` the code is correct.
> `zoo/`, `pan/`, `util/` are fine at `-O2` (verified against reference
> outputs — see step 5).

```bash
cd ~/pandora/v2.2.0
FF="-std=legacy -fallow-argument-mismatch"

( cd sys  && make FC=gfortran FFLAGS="-O0 $FF" )
( cd zoo  && make -j8 FC=gfortran FFLAGS="-O2 $FF" )
( cd pan  && make -j8 FC=gfortran FFLAGS="-O2 $FF" )   # ~5 min parallel
make FC=gfortran FFLAGS="-O2 $FF" pandora.x
( cd util && make FC=gfortran FFLAGS="-O2 $FF" )
make FC=gfortran BIN=bin install
```

Flag notes:

* `-std=legacy` — accept pre-F90 constructs without warnings;
* `-fallow-argument-mismatch` — this code routinely passes scalars /
  differently-typed arrays to subroutines (standard practice in 1970s
  Fortran); gfortran ≥ 10 makes that an error without this flag.

The result is `bin/pandora.x` (the solver) plus the utility programs
(`ready.x`, `cents.x`, `census.x`, `dimes.x`, `modup.x`, `wrap.x`,
`he1diff.x`, `lookat.x`) and the classic csh wrapper scripts.

Make the demo tree see the executables:

```bash
cd ~/pandora/v2.1.1 && ln -sfn ../v2.2.0/bin bin
```

## 5. Verify

Quick check (demo 1 runs in ~1 s):

```bash
cd ~/pandora/v2.1.1/demos
csh -c "bin/pandora -io 1/ -atoms 1/ demo1 none '' 001" > 1/demo1.log
grep "PANDORA done" 1/demo1.log      # must print: STOP PANDORA done
```

`PANDORA done` is, per the original documentation, *the only reliable
sign of a healthy run*.

If you extracted the demo references, compare (they were produced in
2014 with ifort and program version 78.018 — our build is 79.009):

* demo 4's emergent Mg II k profile should match the reference **to
  every printed digit**;
* demo 1-3 hydrogen populations agree to ~10⁻³-10⁻⁴, except
  electron-density-related tables (NE, NP, NC ~2%) — version 79.007
  "revised NE calculations" (see `HISTORY`), and ZME which was
  redefined between the versions;
* demo 5 (sunspot, 15-level H, PRD; ~7 min) reproduces the reference's
  line-profile morphology with core intensities within tens of percent —
  the same NE revision amplified through 11 iterations in the
  transition region.

`pandorakit` automates all of this: `python -m pytest tests/` in the
repository runs the parser suite, and `examples/verify_install.py`
reruns the demo comparisons.

## 6. The Python package

```bash
cd pandorakit
python3 -m pip install -e .          # zero runtime dependencies
pandorakit --help
pandorakit gui                        # browser GUI
```

pandorakit expects the layout created above (`~/pandora` containing
`v2.2.0/bin` and `v2.1.1/{atoms,opacities}`) — pass `--root` or
`PandoraInstall(root=...)` for other locations.

## How PANDORA finds its files (important background)

PANDORA never opens a file by name: it reads/writes fixed Fortran
logical units. Unit 3 is the input deck, 7 the atom file, 15 the main
printout, etc. (full table in the manual). How a *name* gets attached
to a unit is compiler-specific:

* **ifort**: environment variables `FORT3`, `FORT7`, ...
* **PGI**: environment variables `FOR003`, ...
* **gfortran**: no environment mechanism — a unit opens the file
  `fort.NN` in the working directory.

The classic `bin/pandora` csh script uses `bin/setFORx.sou` to abstract
this; our patch adds a gfortran mode that creates `fort.NN` *symlinks*
(and cleans them up afterwards). The pandorakit runner does the same
thing natively in Python, in an isolated per-run directory — this is the
recommended way to run.

## Linux notes

Identical recipe. `csh` may need installing if you want the classic
scripts (`sudo apt install csh`); pandorakit does not need it. With
gfortran ≥ 10 keep both flags; with 8/9 `-fallow-argument-mismatch`
does not exist (mismatches are only warnings there) — drop it.

## Rebuilding after source changes

Only ever rebuild `sys/` at `-O0`. If you touch `pan/pandora.f` to
enlarge the workspace arrays (`LNGTHX`, `LENMEM` — see manual §"Memory"),
rebuild with the same flags; nothing else changes.
