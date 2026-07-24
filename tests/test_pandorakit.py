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


# ---------------------------------------------------------------- recipes
def test_wind_ramp_shape():
    from pandorakit.recipes import wind_ramp

    v = wind_ramp(72, v_top=15.0, i_zero=55, i_top=15)
    assert len(v) == 72
    assert v[0] == 15.0 and v[15] == 15.0
    assert v[55] == 0.0 and v[71] == 0.0
    assert all(v[i] >= v[i + 1] for i in range(71))  # monotonic decline


def test_set_expansion_and_redistribution():
    from pandorakit.recipes import set_expansion, set_redistribution

    d = Deck.parse("DO ( EXPAND ) >\nVXS ( 1. 2. 3. ) >\nGO >\nIOMX ( 2 ) >\nGO >\nGO >\nGO\n")
    set_expansion(d, None)
    assert d.get("VXS") is None
    dos = [s for s in d.statements() if s.name.upper() == "OMIT"]
    assert any(str(s.values[0]).upper() == "EXPAND" for s in dos)

    d2 = Deck.parse("IOMX ( 2 ) >\nGO >\nA 2 1 ( 1.E8 ) >\nGO >\nGO >\nGO\n")
    set_redistribution(d2, 2, 1, "prd", gmma=-0.9)
    assert d2.get("SCH 2 1").scalar == 1
    assert d2.get("GMMA 2 1").scalar == -0.9
    set_redistribution(d2, 2, 1, "crd")
    assert d2.get("SCH 2 1") is None


def test_chromosphere_builder():
    from pandorakit.recipes import chromosphere_te_logm

    zm, te = chromosphere_te_logm(
        zmass_phot=[1.0, 2.0, 5.0], te_phot=[4200.0, 4600.0, 5200.0],
        t_max=9000.0, n_chromo=50, n_tr=10,
    )
    assert len(zm) == len(te) == 63
    # top-down: TR first (hot), then chromosphere, then photosphere
    assert te[0] == pytest.approx(2.0e5, rel=1e-6)
    assert te[-1] == 5200.0
    # column mass increases monotonically downward
    assert all(zm[i] < zm[i + 1] for i in range(len(zm) - 1))


def test_core_shift_and_asymmetry():
    import math

    from pandorakit.recipes import core_shift_and_asymmetry

    # symmetric double-peaked emission with central self-reversal
    wl = [(-40 + i) / 20.0 for i in range(81)]
    prof = [
        1.0
        + 2.0 * math.exp(-0.5 * ((abs(w) - 0.5) / 0.15) ** 2)
        - 2.5 * math.exp(-0.5 * (w / 0.1) ** 2)
        for w in wl
    ]
    d = core_shift_and_asymmetry(wl, prof, 4000.0)
    assert abs(d["core_shift_kms"]) < 2
    assert d["br_ratio"] == pytest.approx(1.0, abs=0.02)

    # blueshift the core: minimum moved to -0.1 A
    prof2 = [
        1.0
        + 2.0 * math.exp(-0.5 * ((abs(w) - 0.5) / 0.15) ** 2)
        - 2.5 * math.exp(-0.5 * ((w + 0.1) / 0.1) ** 2)
        for w in wl
    ]
    d2 = core_shift_and_asymmetry(wl, prof2, 4000.0)
    assert d2["core_shift_kms"] < -4  # ~-7.5 km/s expected


def test_mass_loss_rate_magnitude():
    from pandorakit.recipes import mass_loss_rate

    # MAD09-like layer: R=70 Rsun, NH=1e8, v=10 km/s at 1.5 R*
    mdot = mass_loss_rate(70.0, 1e8, 10.0, r_over_rstar=1.5)
    assert 1e-9 < mdot < 1e-8  # their published range neighborhood


def test_atmosphere_vxs_roundtrip():
    src = DEMOS / "6" / "leid.mod"
    if not src.exists():
        pytest.skip("demos not present")
    atm = Atmosphere.read(src)
    assert atm.vxs is None
    atm.vxs = [1.0] * atm.n
    d = atm.to_deck()
    assert d.get("VXS").array(atm.n)[0] == 1.0
    # structure preserved: populations survive
    hn = [s for s in d.statements() if s.name.upper() == "HN"]
    assert len(hn) == 15


def test_multi_export():
    from pandorakit.model import to_multi_atmos

    src = DEMOS / "6" / "leid.mod"
    if not src.exists():
        pytest.skip("demos not present")
    atm = Atmosphere.read(src)
    txt = to_multi_atmos(atm)
    rows = [l for l in txt.splitlines()
            if l.startswith("  ") and len(l.split()) == 5]
    assert len(rows) == atm.n
    h0 = float(rows[0].split()[0])
    h1 = float(rows[-1].split()[0])
    assert h0 > h1  # heights decrease downward


# ------------------------------------------------------- flux profile parse
def test_flux_profile_parsing():
    aaa = Path("/Users/ibaeza/pandora/runs/outflow/ca2_static.001/ca2_static.aaa.001")
    if not aaa.exists():
        pytest.skip("outflow demo outputs not present")
    from pandorakit.outputs import AaaFile

    blocks = [b for b in AaaFile(aaa).profile(5, 1) if b.kind == "line_profile"]
    assert blocks and blocks[0].is_flux
    b = blocks[0]
    assert b.case == "Stationary" and b.redistribution == "CRD"
    # symmetric: intensity at +-0.5 A agree to ~1%
    import bisect
    pts = sorted(zip(b.wl, b.ilam))
    def at(x):
        return min(pts, key=lambda t: abs(t[0] - x))[1]
    assert at(0.5) == pytest.approx(at(-0.5), rel=0.02)


# ---------------------------------------------------------------- fit math
def test_fit_convolve_and_normalize():
    np = pytest.importorskip("numpy")
    from pandorakit.fit import convolve_R, normalize_to_wings

    wl = np.linspace(-5, 5, 801)
    f = 1.0 - 0.8 * np.exp(-0.5 * (wl / 0.05) ** 2)  # narrow line
    fc = convolve_R(wl, f, R=30000.0, line_center=4000.0)
    # LSF FWHM = 0.133 A >> line width: core fills in, area preserved
    assert fc.min() > f.min() + 0.2
    assert abs((1 - fc).sum() - (1 - f).sum()) / (1 - f).sum() < 0.05

    g = normalize_to_wings(wl, 2.5 * f, wing=(4.0, 5.0))
    assert g[np.abs(wl) > 4].mean() == pytest.approx(1.0, abs=0.01)


def test_fit_nelder_mead_and_intervals():
    np = pytest.importorskip("numpy")
    from pandorakit.fit import _interval_from_profile, _nelder_mead

    # quadratic bowl with minimum at (3, -2)
    f = lambda x: (x[0] - 3.0) ** 2 + 2.0 * (x[1] + 2.0) ** 2
    xb, fb = _nelder_mead(f, np.array([0.0, 0.0]), np.array([1.0, 1.0]),
                          maxiter=200, ftol=1e-8)
    assert xb[0] == pytest.approx(3.0, abs=0.01)
    assert xb[1] == pytest.approx(-2.0, abs=0.01)

    # chi2 = (x-1)^2 -> Delta chi2 = 1 at +-1
    xs = np.linspace(-3, 5, 81)
    chis = (xs - 1.0) ** 2
    lo, hi = _interval_from_profile(xs, chis, 1.0, 0.0)
    assert lo == pytest.approx(1.0, abs=0.05)
    assert hi == pytest.approx(1.0, abs=0.05)


# ------------------------------------------------------------ simple tables
def test_from_table_parsing(tmp_path):
    f = tmp_path / "star.csv"
    f.write_text(
        "# a comment line\n"
        "z_km, te, nh, ne, vturb   # header with aliases\n"
        "0.0,    5800, 1.3e16, 8.1e11, 1.5\n"
        "-50e3,  9000, 2.0e10, 3.0e9,  2.0  # bottom-first on purpose\n"
        "-134e3, 1.3e5, 8.7e3, 1.2e4,  2.0\n"
    )
    atm = Atmosphere.from_table(f)
    assert atm.n == 3
    # auto-flip: top (most negative z) must be first
    assert atm.z[0] == pytest.approx(-134e3 * 1e5)  # km -> cm
    assert atm.te[0] == pytest.approx(1.3e5)
    assert atm.v[0] == pytest.approx(2.0)  # vturb -> PANDORA's V
    assert atm.validate() == []

    # unknown column -> clear error
    g = tmp_path / "bad.csv"
    g.write_text("z_km te banana\n1 2 3\n")
    with pytest.raises(ValueError, match="banana"):
        Atmosphere.from_table(g)


def test_to_table_roundtrip(tmp_path):
    src = DEMOS / "2" / "demo2.mod"
    if not src.exists():
        pytest.skip("demos not present")
    atm = Atmosphere.read(src)
    p = tmp_path / "out.csv"
    atm.to_table(p)
    back = Atmosphere.from_table(p)
    assert back.n == atm.n
    assert back.te == pytest.approx(atm.te)
    assert back.ne == pytest.approx(atm.ne)


def test_simple_templates_ship():
    from pandorakit import simple

    assert (simple._TEMPLATES / "h_bootstrap.dat").exists()
    assert (simple._TEMPLATES / "h_spectrum.dat").exists()
    # templates must be depth-count agnostic: no depth-indexed statements
    for name in ("h_bootstrap.dat", "h_spectrum.dat"):
        txt = (simple._TEMPLATES / name).read_text()
        assert "TRN" not in txt and "VXS" not in txt


def test_empty_restart_placeholder(tmp_path):
    # a 0-byte restart crashes PANDORA's reader; the runner must write
    # USE ( INPUT ) instead (cf. demos/2/demo2h.res)
    import inspect

    from pandorakit import runner

    src = inspect.getsource(runner.PandoraRun.execute)
    assert "USE ( INPUT )" in src


# ---------------------------------------------------------------- gui axes
def test_depth_axes():
    from pandorakit.gui import depth_axes

    src = DEMOS / "6" / "leid.mod"
    if not src.exists():
        pytest.skip("demos not present")
    m = Atmosphere.read(src)
    axes = depth_axes(m)
    assert set(axes) == {"index", "z_km", "logm", "logtau"}
    n = m.n
    for k, a in axes.items():
        assert len(a["values"]) == n, k
    # all axes: top of atmosphere first => values increase with index
    for k in ("z_km", "logm", "logtau"):
        v = axes[k]["values"]
        assert v[0] == min(v) and v[-1] == max(v), k
    # tau grows monotonically over many decades top -> bottom
    # (leid is a chromosphere-only slab: tau5000 << 1 everywhere is
    # physically correct there)
    lt = axes["logtau"]["values"]
    assert lt[-1] - lt[0] > 4
    assert all(lt[i] <= lt[i + 1] + 1e-9 for i in range(len(lt) - 1))
    # z in km matches model z in cm
    assert axes["z_km"]["values"][0] == pytest.approx(m.z[0] / 1e5)


def test_gui_port_fallback():
    """A busy port must not crash the GUI: it moves to the next one."""
    import socket
    import threading
    import time

    from pandorakit import gui

    # occupy 8765-like port
    squatter = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    squatter.bind(("127.0.0.1", 0))
    busy = squatter.getsockname()[1]
    squatter.listen(1)

    started = {}

    def fake_serve_forever(self):
        started["port"] = self.server_address[1]
        raise KeyboardInterrupt  # stop immediately

    from http.server import ThreadingHTTPServer

    orig = ThreadingHTTPServer.serve_forever
    ThreadingHTTPServer.serve_forever = fake_serve_forever
    try:
        gui.serve(root=Path.home() / "pandora", port=busy,
                  open_browser=False)
    except SystemExit:
        pytest.fail("serve() gave up instead of trying the next port")
    finally:
        ThreadingHTTPServer.serve_forever = orig
        squatter.close()

    assert started.get("port") == busy + 1
