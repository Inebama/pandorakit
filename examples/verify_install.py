#!/usr/bin/env python3
"""
Verify a PANDORA installation against the CfA demo references.

Runs demos 1, 2 and 4 through pandorakit and compares populations and
the demo-4 Mg II k emergent profile with the reference outputs
(v2.1.1/demos/{1r,2r,4r}, from pandora-v2.1.1-demo-refs.tgz).

Expected outcome (references were made with ifort + pandora 78.018;
this build is 79.009 -- see HISTORY):
  * demo 4 profile: identical to printed precision;
  * H populations: <= ~1e-3, except NE/NP/NC ~2% (documented NE
    revision) and ZME (redefined between versions; skipped).
"""

import sys
from pathlib import Path

from pandorakit import AaaFile, Deck, PandoraInstall, PandoraRun

ROOT = Path.home() / "pandora"
DEMOS = ROOT / "v2.1.1/demos"
install = PandoraInstall(ROOT)
failures = []


def arrays(deck):
    return {
        s.key: [v for v in s.values if isinstance(v, (int, float))]
        for s in deck.statements()
    }


def compare_pop(new_pop, ref_pop, label):
    a, b = arrays(Deck.read(new_pop)), arrays(Deck.read(ref_pop))
    for k in sorted((set(a) & set(b)) - {"ZME"}):
        va, vb = a[k], b[k]
        n = min(len(va), len(vb))
        if not n:
            continue
        rd = max(
            abs(x - y) / max(abs(x), abs(y), 1e-300)
            for x, y in zip(va[:n], vb[:n])
        )
        tol = 0.05 if k.split()[0] in ("NE", "NP", "NC") else 0.01
        status = "ok" if rd <= tol else "FAIL"
        if rd > tol:
            failures.append(f"{label} {k}: {rd:.2e} > {tol}")
        print(f"  {label:8s} {k:8s} max rel diff {rd:.2e}  [{status}]")


print("== demo 1 ==")
r1 = PandoraRun(
    install, case="demo1none", run_id="vfy",
    dat=DEMOS / "1/demo1none.dat", workdir=ROOT / "runs" / "verify",
).execute(overwrite=True)
assert r1.ok, "demo1 failed"
compare_pop(r1.output("pop"), DEMOS / "1r/demo1none.pop.001", "demo1")

print("== demo 2 ==")
r2 = PandoraRun(
    install, case="demo2h", run_id="vfy",
    dat=DEMOS / "2/demo2h.dat", mod=DEMOS / "2/demo2.mod",
    atm=DEMOS / "2/hl3.atm", res=DEMOS / "2/demo2h.res",
    workdir=ROOT / "runs" / "verify",
).execute(overwrite=True)
assert r2.ok, "demo2 failed"
compare_pop(r2.output("pop"), DEMOS / "2r/demo2h.pop.001", "demo2")

print("== demo 4 (Mg II k profile) ==")
r4 = PandoraRun(
    install, case="demo4mg2", run_id="vfy",
    dat=DEMOS / "4/demo4mg2.dat", mod=DEMOS / "4/demo4.mod",
    atm=DEMOS / "4/mg2l2.atm", res=DEMOS / "4/demo4mg2.res",
    workdir=ROOT / "runs" / "verify",
).execute(overwrite=True)
assert r4.ok, "demo4 failed"
new = AaaFile(r4.output("aaa")).profile(2, 1)
ref = AaaFile(DEMOS / "4r/demo4mg2.aaa.001").profile(2, 1)
worst = 0.0
for bn, br in zip(new, ref):
    n = min(len(bn.ilam), len(br.ilam))
    rd = max(
        abs(x - y) / max(abs(x), abs(y), 1e-300)
        for x, y in zip(bn.ilam[:n], br.ilam[:n])
    )
    worst = max(worst, rd)
print(f"  worst profile rel diff: {worst:.2e} "
      f"[{'ok' if worst < 1e-12 else 'FAIL'}]")
if worst >= 1e-12:
    failures.append(f"demo4 profile diff {worst:.2e}")

print()
if failures:
    print("VERIFICATION FAILED:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("INSTALLATION VERIFIED against reference outputs.")
