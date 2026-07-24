#!/usr/bin/env python3
"""
Partial vs. complete redistribution on the Mg II k line (demo 4).

PANDORA computes line source functions in COMPLETE redistribution
(CRD) by default; PARTIAL redistribution (PRD) is enabled per
transition with ``SCH u l ( 1 )`` (wup Section 15). Demo 4 ships with
PRD on for the Mg II k resonance line (2795.5 A). This example runs it
both ways and compares the emergent profiles.

Expected physics (Hubeny & Mihalas 2015, ch. 15; VAL81 Appendix A):
in strong resonance lines the wing photons scatter nearly coherently
in the atom's frame; CRD instead redistributes them across the whole
profile, which couples the wings to the core source function and
typically OVERESTIMATES the inner-wing emission of chromospheric
resonance lines. PRD is why Mg II h&k and Ca II H&K modeling needs the
machinery at all.

Runtime: seconds.
"""

from pathlib import Path

from pandorakit import AaaFile, Deck, PandoraInstall, PandoraRun
from pandorakit.recipes import set_redistribution

ROOT = Path.home() / "pandora"
DEMO = ROOT / "v2.1.1/demos/4"
WORK = ROOT / "runs" / "prd_crd"

install = PandoraInstall(ROOT)
base = Deck.read(DEMO / "demo4mg2.dat", heading=True)

decks = {
    "prd": base,
    "crd": set_redistribution(
        Deck.parse(base.dumps(), heading=True), 2, 1, "crd"
    ),
}

profiles = {}
for name, deck in decks.items():
    res = PandoraRun(
        install,
        case=f"mg2_{name}",
        run_id="001",
        dat=deck,
        mod=DEMO / "demo4.mod",
        atm=DEMO / "mg2l2.atm",
        res=DEMO / "demo4mg2.res",
        workdir=WORK,
    ).execute(overwrite=True)
    print(f"[{'ok' if res.ok else 'FAILED'}] {name}: {res.elapsed:.1f} s")
    if not res.ok:
        print(res.log[-1500:])
        raise SystemExit(1)
    blocks = [
        b
        for b in AaaFile(res.output("aaa")).profile(2, 1)
        if b.kind == "line_profile" and b.mu == 1.0
    ]
    b = blocks[0]
    profiles[name] = b
    print(f"    annotation: [{b.redistribution}]  "
          f"{len(b.wl)} wavelengths, line at {b.line_center} A")

# sanity: the printout itself must confirm which physics ran
assert profiles["prd"].redistribution == "PRD"
assert profiles["crd"].redistribution == "CRD"

print("\nInner-wing / peak comparison (mu = 1):")
print(f"{'DL [A]':>8s} {'I_PRD':>12s} {'I_CRD':>12s} {'CRD/PRD':>8s}")
bp, bc = profiles["prd"], profiles["crd"]
for wl_target in (0.15, 0.3, 0.5, 1.0, 2.0):
    ip = min(zip(bp.wl, bp.ilam), key=lambda t: abs(t[0] - wl_target))
    ic = min(zip(bc.wl, bc.ilam), key=lambda t: abs(t[0] - wl_target))
    print(f"{ip[0]:8.3f} {ip[1]:12.4e} {ic[1]:12.4e} {ic[1]/ip[1]:8.2f}")

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, b in profiles.items():
        ax.plot(b.wl, b.ilam, label=name.upper())
    ax.set_xlabel(r"$\Delta\lambda$ from Mg II k line center [$\AA$]")
    ax.set_ylabel(r"I$_\lambda$ [erg cm$^{-2}$ s$^{-1}$ sr$^{-1}$ $\AA^{-1}$]")
    ax.set_yscale("log")
    ax.legend(title="redistribution")
    ax.set_title("Mg II k: partial vs. complete redistribution (demo 4)")
    out = WORK / "mg2k_prd_vs_crd.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"\nfigure: {out}")
except ImportError:
    print("\n(matplotlib not installed -- skipped the figure)")
