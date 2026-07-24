"""
Run PANDORA for several stars (or several ions/cases) in parallel.

Each job is an independent `PandoraRun`; jobs run in separate run
directories so they never collide.  Parallelism uses processes since a
PANDORA run is an external executable anyway.

Example -- a small grid of chromosphere models::

    from pandorakit import PandoraInstall, batch

    install = PandoraInstall("~/pandora")
    jobs = []
    for i, factor in enumerate([0.95, 1.0, 1.05]):
        atm = base_model.with_te_scaled(factor)
        jobs.append(batch.Job(
            case=f"star{i}", dat="template.dat",
            mod=atm.to_deck(), atom=("h", 3), run_id="001",
        ))
    results = batch.run_batch(install, jobs, workdir="grid", max_workers=3)
"""

from __future__ import annotations

import concurrent.futures as cf
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from .deck import Deck
from .runner import PandoraInstall, PandoraRun, RunResult

__all__ = ["Job", "run_batch"]


@dataclass
class Job:
    case: str
    dat: Union[str, Path, Deck]
    run_id: str = "001"
    mod: Union[str, Path, Deck, None] = None
    atm: Union[str, Path, Deck, None] = None
    atom: Union[tuple, str, None] = None
    res: Union[str, Path, Deck, None] = None
    jnu: Union[str, Path, None] = None
    timeout: Optional[float] = None
    meta: dict = field(default_factory=dict)


def _run_one(install: PandoraInstall, job: Job, workdir: Path,
             overwrite: bool) -> RunResult:
    run = PandoraRun(
        install,
        case=job.case,
        run_id=job.run_id,
        dat=job.dat,
        mod=job.mod,
        atm=job.atm,
        atom=job.atom,
        res=job.res,
        jnu=job.jnu,
        workdir=workdir,
    )
    return run.execute(timeout=job.timeout, overwrite=overwrite)


def run_batch(
    install: PandoraInstall,
    jobs: list[Job],
    workdir: Union[str, Path] = "runs",
    max_workers: int = 4,
    overwrite: bool = False,
    progress: bool = True,
) -> dict[str, RunResult]:
    """Execute all jobs; returns {case.run_id: RunResult}.

    Failures do not stop the batch: inspect each result's .ok flag.
    """
    workdir = Path(workdir).expanduser()
    results: dict[str, RunResult] = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(_run_one, install, job, workdir, overwrite): job
            for job in jobs
        }
        for fut in cf.as_completed(futs):
            job = futs[fut]
            key = f"{job.case}.{job.run_id}"
            try:
                res = fut.result()
                results[key] = res
                if progress:
                    state = "ok" if res.ok else "FAILED"
                    print(f"[{state}] {key}  ({res.elapsed:.1f}s)")
            except Exception as exc:  # noqa: BLE001
                if progress:
                    print(f"[ERROR] {key}: {exc}")
                raise
    return results
