#!/bin/bash
# ---------------------------------------------------------------------------
# PANDORA v2.2.0 automated installer (gfortran port)
#
#   ./install.sh <download-dir> [<install-root>]
#
# <download-dir> must contain the CfA release archives:
#   pandora-v2.2.0-src.tgz  pandora-v2.1.1-tables.tgz
#   pandora-v2.1.1-demos.tgz  pandora-v2.1.1-doc.tgz
#   (optional) pandora-v2.1.1-demo-refs.tgz
# <install-root> defaults to ~/pandora
#
# Performs: extract -> patch -> build (sys at -O0, rest at -O2; see
# docs/INSTALL.md for why) -> install -> run demo 1 -> verify.
# Idempotent: refuses to clobber an existing v2.2.0/ source tree.
# ---------------------------------------------------------------------------
set -euo pipefail

DL=${1:?usage: install.sh <download-dir> [<install-root>]}
ROOT=${2:-$HOME/pandora}
HERE=$(cd "$(dirname "$0")" && pwd)
PATCH="$HERE/patches/pandora-v2.2.0-gfortran.patch"
FC=${FC:-gfortran}
FF="-std=legacy -fallow-argument-mismatch"
JOBS=${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

command -v "$FC" >/dev/null || die "$FC not found (install gcc/gfortran first)"
[ -f "$PATCH" ] || die "patch not found at $PATCH"
for a in pandora-v2.2.0-src.tgz pandora-v2.1.1-tables.tgz \
         pandora-v2.1.1-demos.tgz pandora-v2.1.1-doc.tgz; do
  [ -f "$DL/$a" ] || die "missing archive: $DL/$a"
done

say "Extracting into $ROOT"
mkdir -p "$ROOT"; cd "$ROOT"
[ -d v2.2.0 ] && die "$ROOT/v2.2.0 already exists; remove it (or pick another root) first"
tar xzf "$DL/pandora-v2.2.0-src.tgz"
tar xzf "$DL/pandora-v2.1.1-tables.tgz"
tar xzf "$DL/pandora-v2.1.1-demos.tgz"
tar xzf "$DL/pandora-v2.1.1-doc.tgz"
[ -f "$DL/pandora-v2.1.1-demo-refs.tgz" ] && tar xzf "$DL/pandora-v2.1.1-demo-refs.tgz"

say "Applying gfortran port patch"
cd v2.2.0
patch -p1 --forward < "$PATCH"

say "Building (sys at -O0 -- required; zoo/pan/util at -O2)"
( cd sys  && make FC="$FC" FFLAGS="-O0 $FF" )
( cd zoo  && make -j"$JOBS" FC="$FC" FFLAGS="-O2 $FF" )
( cd pan  && make -j"$JOBS" FC="$FC" FFLAGS="-O2 $FF" )
make FC="$FC" FFLAGS="-O2 $FF" pandora.x
( cd util && make FC="$FC" FFLAGS="-O2 $FF" )
make FC="$FC" BIN=bin install

say "Linking executables into the demo tree"
cd "$ROOT/v2.1.1" && ln -sfn ../v2.2.0/bin bin

say "Verification: running demo 1"
cd "$ROOT/v2.1.1/demos"
rm -f 1/demo1none.???.001 1/demo1.log
csh -c "bin/pandora -io 1/ -atoms 1/ demo1 none '' 001" > 1/demo1.log 2>&1 || true
grep -q "PANDORA done" 1/demo1.log \
  || die "demo 1 did not complete -- see $ROOT/v2.1.1/demos/1/demo1.log"

if [ -d 1r ]; then
  say "Comparing demo 1 populations against the 2014 reference"
  python3 - "$ROOT" "$HERE" <<'PYEOF' || die "reference comparison failed"
import sys
root, kit = sys.argv[1], sys.argv[2]
sys.path.insert(0, kit)  # use pandorakit's full input-language parser
from pandorakit.deck import Deck

def tables(path):
    return {
        s.key: [v for v in s.values if isinstance(v, (int, float))]
        for s in Deck.read(path).statements()
        if any(isinstance(v, (int, float)) for v in s.values)
    }

new = tables(f"{root}/v2.1.1/demos/1/demo1none.pop.001")
ref = tables(f"{root}/v2.1.1/demos/1r/demo1none.pop.001")
common = [k for k in new if k in ref and k != "ZME"]
assert len(common) > 10, f"too few comparable tables: {common}"
bad = []
for k in common:
    a, b = new[k], ref[k]
    n = min(len(a), len(b))
    rd = max(abs(x - y) / max(abs(x), abs(y), 1e-300)
             for x, y in zip(a[:n], b[:n]))
    # NE-family tables differ ~2% by documented version change 78->79
    tol = 0.05 if k.split()[0] in ("NE", "NP", "NC") else 0.01
    if rd > tol:
        bad.append((k, rd))
print(f"  compared {len(common)} tables; "
      + ("all within tolerance" if not bad else f"FAIL: {bad}"))
sys.exit(1 if bad else 0)
PYEOF
else
  echo "  (demo-refs archive not present -- skipped numeric comparison)"
fi

say "INSTALL VERIFIED"
cat <<EOF

PANDORA is installed at: $ROOT
  executable   $ROOT/v2.2.0/bin/pandora.x
  atomic data  $ROOT/v2.1.1/atoms/
  opacities    $ROOT/v2.1.1/opacities/
  demos        $ROOT/v2.1.1/demos/
  writeup      $ROOT/v2.1.1/doc/wup.pdf

Next:
  python3 -m pip install -e $HERE     # the pandorakit Python package
  pandorakit gui                       # browser GUI
  ...and read $HERE/docs/MANUAL.md
EOF
