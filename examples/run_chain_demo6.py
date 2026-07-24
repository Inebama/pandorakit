#!/usr/bin/env python3
"""
The demo-6 multi-ion chain, fully in Python (no csh, no manual edits):

    H run  -> merge NE/NP/HN/BDH into the model
    He I   -> merge HE tables into the model
    Ca II  -> extract emergent profiles

Reproduces v2.1.1/demos/6/run.sou. Runtime: a few minutes.
"""

import shutil
from pathlib import Path

from pandorakit import AaaFile, Deck, PandoraInstall, PandoraRun, merge_pop

ROOT = Path.home() / "pandora"
DEMO = ROOT / "v2.1.1/demos/6"
WORK = ROOT / "runs" / "chain6"

WORK.mkdir(parents=True, exist_ok=True)
model = WORK / "leid.mod"
shutil.copy(DEMO / "leid.mod", model)

install = PandoraInstall(ROOT)
N = "py1"


def run(ion, levels, dat, res, jnu=None):
    r = PandoraRun(
        install,
        case=f"leid{ion}",
        run_id=N,
        dat=DEMO / dat,
        mod=model,
        atom=(ion, levels),
        res=DEMO / res,
        jnu=(DEMO / jnu) if jnu else None,
        workdir=WORK,
    ).execute(overwrite=True)
    print(r)
    assert r.ok, r.log[-2000:]
    return r


# 1. hydrogen establishes NE and the H populations
rh = run("h", 5, "leidh.dat", "leidh.res", "leidh.jnu")
merge_pop("@NE+", rh.output("pop"), model, model)
print("merged @NE+ into", model)

# 2. He I in the updated atmosphere
rhe = run("he1", 5, "leidhe1.dat", "leidhe1.res")
merge_pop("@HE+", rhe.output("pop"), model, model)
print("merged @HE+ into", model)

# 3. Ca II (not a population ion: nothing to merge back)
rca = run("ca2", 5, "leidca2.dat", "leidca2.res", "leidca2.jnu")

# 4. profiles
for res_, (u, l) in ((rh, (3, 2)), (rhe, (4, 2)), (rca, (5, 1))):
    aaa = AaaFile(res_.output("aaa"))
    blocks = [b for b in aaa.profile(u, l) if b.kind == "line_profile"]
    for b in blocks[:1]:
        print(
            f"{res_.case} PROF({u}/{l}) mu={b.mu}: {len(b.wl)} pts, "
            f"line at {b.line_center} A, peak I/A = {max(b.ilam):.3e}"
        )
