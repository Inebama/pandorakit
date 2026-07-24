# A Week of Stellar Atmospheres with PANDORA

*A hands-on course: from "what is a spectrum" to inferring the mass
loss of a red giant from its Hα and Ca II profiles.*

## Who this is for

Students who know basic astronomy (magnitudes, HR diagram, blackbody
radiation) and have met a spectrum before, but have **not** seen
radiative transfer, non-LTE physics, or atmosphere modeling. Each
lesson is one session (~2-3 h including the computer exercises); the
whole pack is a one-week intensive or a seven-week seminar at one
lesson per week.

## What you need

* A laptop with the PANDORA + pandorakit installation
  ([../INSTALL.md](../INSTALL.md); one classroom machine shared over
  SSH also works — runs take seconds to minutes).
* Python 3 with matplotlib for the exercise plots
  (`pip install matplotlib`).
* No prior Fortran — students never touch the Fortran; instructors may
  enjoy [../MANUAL.md](../MANUAL.md).

## The arc

| # | lesson | you will be able to... |
|---|---|---|
| 1 | [Starlight and stellar atmospheres](01_light_and_atmospheres.md) | read a spectrum as a depth-map of a star |
| 2 | [Radiative transfer](02_radiative_transfer.md) | use optical depth, source function, Eddington-Barbier |
| 3 | [Breaking LTE](03_beyond_lte.md) | explain why chromospheric lines need non-LTE, use the two-level atom |
| 4 | [Line profiles: broadening, redistribution, motion](04_line_formation.md) | connect profile shapes to Voigt physics, PRD vs CRD, velocity fields |
| 5 | [Driving PANDORA](05_pandora_hands_on.md) | run and modify real non-LTE models, read their outputs |
| 6 | [Chromospheres and mass loss](06_chromospheres_and_mass_loss.md) | build a red-giant chromosphere + wind and estimate a mass-loss rate |
| 7 | [What we swept under the rug](07_frontiers.md) | criticize everything you just did; know the 3D/dynamic frontier |

Lessons 1-4 are blackboard-first with short computer moments; 5-6 are
computer-first; 7 is a discussion seminar around two papers.

## Sources and further reading

The physics follows Hubeny & Mihalas, *Theory of Stellar Atmospheres*
(2015) — cited as **HM15** — and Gray, *The Observation and Analysis of
Stellar Photospheres* (2022) — cited as **G22**. The science case is
Mészáros, Avrett & Dupree 2009, AJ 138, 615 (**MAD09**); the critical
perspective is Rutten & Uitenbroek 2012, A&A 540, A86 (**RU12**). The
code background is Avrett & Loeser 2003 (ASP Conf. 288, 303) and the
PANDORA writeup (`v2.1.1/doc/wup.pdf`).

## A note to instructors

Every numerical exercise in this pack was executed during its writing
against PANDORA 79.009 (gfortran build) and the outputs quoted are
real. Exercises marked ★ have model answers in the text (white-on-white
style is not used; they are simply printed at the end of each lesson —
tear off as needed).
