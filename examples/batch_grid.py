#!/usr/bin/env python3
"""
Several "stars" at once: a mini-grid of temperature-scaled chromospheres.

Scales the demo-6 model's T(z) by a few factors and runs 5-level
hydrogen in each, in parallel -- the pattern for surveys, parameter
studies, and 1.5D column synthesis (see MANUAL.md sections 14 and 17).
"""

from pathlib import Path

from pandorakit import Atmosphere, PandoraInstall, batch

ROOT = Path.home() / "pandora"
DEMO = ROOT / "v2.1.1/demos/6"

install = PandoraInstall(ROOT)
base = Atmosphere.read(DEMO / "leid.mod")
print("base model:", base)

jobs = []
for i, f in enumerate([0.96, 1.00, 1.04]):
    jobs.append(
        batch.Job(
            case=f"grid_t{i}",
            run_id="001",
            dat=DEMO / "leidh.dat",
            mod=base.with_te_scaled(f).to_deck(),
            atom=("h", 5),
            res=DEMO / "leidh.res",
            jnu=DEMO / "leidh.jnu",
            meta={"te_scale": f},
        )
    )

results = batch.run_batch(
    install, jobs, workdir=ROOT / "runs" / "grid", max_workers=3,
    overwrite=True,
)

print()
for key, res in sorted(results.items()):
    print(f"{key}: ok={res.ok}  {res.elapsed:.1f}s  outputs={sorted(res.outputs)}")
