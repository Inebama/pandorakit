"""
pandorakit command-line interface.

    pandorakit run CASE --dat X.dat [--mod M.mod] [--atom h --levels 15] ...
    pandorakit sections FILE.aaa.001
    pandorakit extract 'PROF (2/1)' FILE.aaa.001 out.txt
    pandorakit profile FILE.aaa.001 2 1 [-o prof.csv]
    pandorakit pmerge '@NE+' case.pop.001 model.mod -o model.mod
    pandorakit params [NAME ...]        # look up input parameters
    pandorakit gui [--root ~/pandora]   # launch the browser GUI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _install(args):
    from .runner import PandoraInstall

    return PandoraInstall(args.root)


def cmd_run(args) -> int:
    from .runner import PandoraRun

    install = _install(args)
    atom = None
    if args.atom:
        atom = (args.atom, args.levels) if args.levels else args.atom
    run = PandoraRun(
        install,
        case=args.case,
        run_id=args.run_id,
        dat=args.dat,
        mod=args.mod,
        atm=args.atm,
        atom=atom,
        res=args.res,
        jnu=args.jnu,
        workdir=args.workdir,
    )
    res = run.execute(overwrite=args.overwrite, timeout=args.timeout)
    print(res)
    if not res.ok:
        tail = "\n".join(res.log.splitlines()[-20:])
        print("--- log tail ---\n" + tail, file=sys.stderr)
        return 1
    for ext, path in sorted(res.outputs.items()):
        print(f"  .{ext}: {path}")
    return 0


def cmd_sections(args) -> int:
    from .outputs import AaaFile

    aaa = AaaFile(args.aaa)
    for psn, title in aaa.sections:
        print(f"PSN{psn:06d}  {title}")
    return 0


def cmd_extract(args) -> int:
    from .outputs import AaaFile

    AaaFile(args.aaa).extract(args.section, args.out)
    print(f"wrote {args.out}")
    return 0


def cmd_profile(args) -> int:
    from .outputs import AaaFile

    blocks = AaaFile(args.aaa).profile(args.upper, args.lower)
    out = sys.stdout if args.out is None else open(args.out, "w")
    print("# block  mu  wl_A  I_nu  I_A  T_b", file=out)
    for i, b in enumerate(blocks):
        for wl, inu, ilam, tb in zip(b.wl, b.inu, b.ilam, b.tb):
            mu = "flux" if b.mu is None else f"{b.mu:.4f}"
            print(f"{i} {mu} {wl:.6e} {inu:.6e} {ilam:.6e} {tb:.1f}",
                  file=out)
    if args.out:
        out.close()
        print(f"wrote {args.out}")
    return 0


def cmd_pmerge(args) -> int:
    from .pmerge import merge_pop

    out = args.out or args.mod
    merge_pop(args.spec, args.pop, args.mod, out)
    print(f"merged {args.spec} from {args.pop} into {out}")
    return 0


def cmd_params(args) -> int:
    db_path = Path(__file__).parent / "data" / "parameters.json"
    db = json.loads(db_path.read_text())
    names = {n.upper() for n in args.names}
    shown = 0
    for p in db:
        if not p.get("name"):
            continue
        if names and p["name"].upper() not in names:
            if not any(
                n in (p.get("description") or "").upper() for n in names
            ):
                continue
        print(f"{p['name']:12s} {p.get('description', '')}")
        if p.get("length"):
            print(f"{'':12s}   length: {p['length']}")
        if p.get("codes"):
            print(f"{'':12s}   part/form: {p['codes']}  mode: {p.get('mode')}")
        if p.get("default"):
            print(f"{'':12s}   default: {p['default']}")
        shown += 1
    if not shown:
        print("no matching parameters (searched name and description)")
    return 0


def cmd_gui(args) -> int:
    from .gui import serve

    serve(root=args.root, port=args.port, open_browser=not args.no_browser)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="pandorakit", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--root", default=str(Path.home() / "pandora"),
        help="PANDORA install root (default ~/pandora)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="stage and execute a PANDORA run")
    p.add_argument("case")
    p.add_argument("--dat", required=True)
    p.add_argument("--mod")
    p.add_argument("--atm", help="explicit atomic model file")
    p.add_argument("--atom", help="atom name for the atoms/ library (e.g. h)")
    p.add_argument("--levels", help="levels code (e.g. 15 or l15)")
    p.add_argument("--res")
    p.add_argument("--jnu")
    p.add_argument("--run-id", default="001")
    p.add_argument("--workdir", default="runs")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--timeout", type=float)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("sections", help="list print sections of a .aaa file")
    p.add_argument("aaa")
    p.set_defaults(func=cmd_sections)

    p = sub.add_parser("extract", help="extract a section (machine readable)")
    p.add_argument("section")
    p.add_argument("aaa")
    p.add_argument("out")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("profile", help="emergent line profile as columns")
    p.add_argument("aaa")
    p.add_argument("upper", type=int)
    p.add_argument("lower", type=int)
    p.add_argument("-o", "--out")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("pmerge", help="merge .pop tables into a model")
    p.add_argument("spec", help="e.g. '@NE+,@NP+' or 'NE,HN_1-15'")
    p.add_argument("pop")
    p.add_argument("mod")
    p.add_argument("-o", "--out")
    p.set_defaults(func=cmd_pmerge)

    p = sub.add_parser("params", help="input parameter reference lookup")
    p.add_argument("names", nargs="*")
    p.set_defaults(func=cmd_params)

    p = sub.add_parser("gui", help="launch the browser GUI")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_gui)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
