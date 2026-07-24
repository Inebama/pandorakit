"""
pandorakit -- a modern Python interface to the PANDORA NLTE code.

PANDORA (E. H. Avrett & R. Loeser, CfA) computes non-LTE model stellar
atmospheres and emergent spectra: multilevel statistical equilibrium,
line and continuum radiative transfer with PRD, in 1D plane-parallel or
spherical geometry.

pandorakit wraps a locally built ``pandora.x``:

* :class:`~pandorakit.deck.Deck` -- read/write PANDORA's statement
  language (.dat/.mod/.atm/.pop/... files);
* :class:`~pandorakit.model.Atmosphere` -- atmosphere models as arrays;
* :class:`~pandorakit.runner.PandoraRun` -- stage + execute runs without
  the historical csh wrappers;
* :class:`~pandorakit.outputs.AaaFile` -- parse printout sections,
  emergent line profiles and spectra;
* :mod:`~pandorakit.pmerge` -- population handoff between chained runs;
* :mod:`~pandorakit.batch` -- many stars / many ions in parallel.
"""

from .deck import Deck, Statement, Comment, Go, Use, Fill, SKIP  # noqa: F401
from .model import Atmosphere  # noqa: F401
from .runner import (  # noqa: F401
    PandoraError,
    PandoraInstall,
    PandoraRun,
    RunResult,
)
from .outputs import AaaFile, Section, ProfileBlock  # noqa: F401
from .pmerge import merge_pop  # noqa: F401
from . import batch  # noqa: F401

__version__ = "0.1.0"
