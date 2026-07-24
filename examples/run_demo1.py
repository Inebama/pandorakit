#!/usr/bin/env python3
"""Smallest possible pandorakit run: demo 1 (3-level H, 2 iterations)."""

from pathlib import Path

from pandorakit import AaaFile, PandoraInstall, PandoraRun

ROOT = Path.home() / "pandora"

install = PandoraInstall(ROOT)
run = PandoraRun(
    install,
    case="demo1none",
    run_id="ex1",
    dat=ROOT / "v2.1.1/demos/1/demo1none.dat",
    workdir=ROOT / "runs",
)
res = run.execute(overwrite=True)
print(res)
assert res.ok, "run failed -- check res.log"

aaa = AaaFile(res.output("aaa"))
print(f"\n{len(aaa.sections)} print sections; a few of them:")
for psn, title in aaa.sections[:12]:
    print(f"  PSN{psn:06d}  {title}")
