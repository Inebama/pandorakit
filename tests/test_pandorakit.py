"""Core pandorakit tests (no PANDORA executable required)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pandorakit.deck import SKIP, Deck, Fill, Go, Statement, Use  # noqa: E402
from pandorakit.model import Atmosphere  # noqa: E402
from pandorakit.pmerge import expand_spec, merge_pop  # noqa: E402

DEMOS = Path("/Users/ibaeza/pandora/v2.1.1/demos")


# ---------------------------------------------------------------- language
def test_parse_basic_statement():
    d = Deck.parse("N ( 25 ) >\nKK ( 9 ) >\n")
    assert d.get("N").scalar == 25
    assert d.get("KK").scalar == 9


def test_parse_multiplier_and_fill():
    # from wup.pdf section 1 example: expands to 0,10,20,30,40,50,60x5,70...
    d = Deck.parse("NE ( 0. M 1.E1 1. 2. 3. 4. 5.\nR 5 6. F 7. )\n")
    vals = d.get("NE").array(12)
    assert vals[:6] == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    assert vals[6:11] == [60.0] * 5
    assert vals[11] == 70.0


def test_parse_index_control():
    d = Deck.parse("XK ( I 13 5.5 )  DLU  ( 0.1 ) >\n")
    xk = d.get("XK").array(13)
    assert xk[12] == 5.5
    assert all(v is None for v in xk[:12])
    assert d.get("DLU").scalar == 0.1


def test_parse_indices_and_comment():
    d = Deck.parse("A 3 2 ( 4.41E+7 )\n[ BALMER DATA ] >\nCSK 3 2 ( 1.174E-3 ) >\n")
    assert d.get("A 3 2").scalar == pytest.approx(4.41e7)
    assert d.get("CSK 3 2").scalar == pytest.approx(1.174e-3)


def test_parse_go_and_use():
    d = Deck.parse("USE ( MODEL ) >\nGO >\nIOMX ( 2 ) >\nGO\n")
    kinds = [type(i).__name__ for i in d.items]
    assert kinds == ["Use", "Go", "Statement", "Go"]
    assert d.items[0].target == "MODEL"


def test_line_skip_gt():
    # '>' skips the rest of the line, values continue next line
    d = Deck.parse("Z ( >  THIS IS JUNK\n1. 2. 3. ) >\n")
    assert d.get("Z").array() == [1.0, 2.0, 3.0]


def test_roundtrip_demo_deck():
    src = DEMOS / "1" / "demo1none.dat"
    if not src.exists():
        pytest.skip("demos not present")
    d1 = Deck.read(src, heading=True)
    text = d1.dumps()
    d2 = Deck.parse(text, heading=True)
    def norm(vals):
        return [
            ("F", v.value) if isinstance(v, Fill)
            else ("S" if v is SKIP else v)
            for v in vals
        ]

    k1 = {s.key: norm(s.values) for s in d1.statements()}
    k2 = {s.key: norm(s.values) for s in d2.statements()}
    assert k1.keys() == k2.keys()
    for k in k1:
        assert len(k1[k]) == len(k2[k]), k
        for a, b in zip(k1[k], k2[k]):
            if isinstance(a, float) and isinstance(b, float):
                assert b == pytest.approx(a, rel=1e-8), k
            else:
                assert a == b, k


def test_deck_set_and_scalar():
    d = Deck.parse("IOMX ( 2 ) >\nGO >\nGO >\nGO >\nGO\n")
    d.set("IOMX", 11)
    assert d.get("IOMX").scalar == 11
    d.set("TE", [5000.0, 6000.0], part=1)
    assert d.get("TE").array() == [5000.0, 6000.0]


# ---------------------------------------------------------------- model
def test_atmosphere_from_demo_mod():
    src = DEMOS / "2" / "demo2.mod"
    if not src.exists():
        pytest.skip("demos not present")
    atm = Atmosphere.read(src)
    assert atm.n == 25
    assert atm.validate() == []
    assert atm.te[0] == pytest.approx(11480.0)  # M 1.E3 11.48
    assert min(atm.te) > 4000 and max(atm.te) < 70000

    # roundtrip through a deck
    d = atm.to_deck()
    atm2 = Atmosphere.from_deck(d)
    assert atm2.te == pytest.approx(atm.te)
    assert atm2.ne == pytest.approx(atm.ne)


def test_atmosphere_validation():
    atm = Atmosphere(name="x", z=[0.0, 1.0], te=[5000.0])
    issues = atm.validate()
    assert any("te has 1" in i for i in issues)


# ---------------------------------------------------------------- pmerge
def test_pmerge_demo6_style():
    pop = DEMOS / "2" / "demo2h.dat"  # any deck works structurally
    if not pop.exists():
        pytest.skip("demos not present")
    pop_deck = Deck.parse(
        "NE ( 1. 2. 3. ) >\nNP ( 4. 5. 6. ) >\n"
        "HN 1 ( 7. 8. 9. ) >\nBDH 1 ( 1. 1. 1. ) >\n"
    )
    mod_deck = Deck.parse("N ( 3 ) >\nNE ( 9. 9. 9. ) >\nTE ( 1. 1. 1. ) >\n")
    merged = merge_pop("@NE+", pop_deck, mod_deck)
    assert merged.get("NE").array() == [1.0, 2.0, 3.0]
    assert merged.get("NP").array() == [4.0, 5.0, 6.0]
    assert merged.get("HN 1").array() == [7.0, 8.0, 9.0]


def test_expand_spec_ranges():
    pop = Deck.parse("HN 1 ( 1. ) >\nHN 2 ( 2. ) >\nHN 3 ( 3. ) >\n")
    keys = expand_spec("HN_1-3", pop)
    assert keys == ["HN 1", "HN 2", "HN 3"]


# ---------------------------------------------------------------- outputs
def test_outputs_reference_profile():
    ref = DEMOS / "4r" / "demo4mg2.aaa.001"
    if not ref.exists():
        pytest.skip("demo refs not present")
    from pandorakit.outputs import AaaFile

    aaa = AaaFile(ref)
    assert len(aaa.sections) > 10
    blocks = aaa.profile(2, 1)
    assert blocks and all(len(b.wl) == len(b.ilam) for b in blocks)
    mus = {b.mu for b in blocks}
    assert 1.0 in mus
