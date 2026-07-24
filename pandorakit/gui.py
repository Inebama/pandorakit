"""
pandorakit GUI -- a local browser interface for single-case exploration.

Zero dependencies: python stdlib only.  Start with

    pandorakit gui            # or: python -m pandorakit.gui

and a browser opens on http://127.0.0.1:8765 with:

* an atmosphere-model editor: T(z) shown as a draggable curve (the
  modern replacement for the historical IDL `xtwiddle` tool), with the
  other model tables plotted alongside;
* a run panel: pick the deck / atom / run id, launch PANDORA, watch the
  log live;
* a results browser: print sections, emergent line profiles plotted
  interactively, CSV export;
* an input-parameter reference search (from the wup.pdf glossary).

Everything happens in your filesystem: the GUI reads and writes the same
.mod/.dat files you use from Python or the command line.
"""

from __future__ import annotations

import errno
import json
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .deck import Deck
from .model import Atmosphere
from .outputs import AaaFile
from .runner import PandoraInstall, PandoraRun

# Everyday vocabulary -> the terms PANDORA's own parameter descriptions
# use. Lets a user search "wind" and find VXS/VX ("expansion velocity").
_PARAM_SYNONYMS = {
    "wind": ("expansion",),
    "outflow": ("expansion",),
    "velocity field": ("expansion",),
    "turbulence": ("broadening velocity", "turbulent"),
    "microturbulence": ("broadening velocity",),
    "temperature": ("temperature",),
    "iterations": ("iteration",),
    "gravity": ("gravity",),
    "abundance": ("abundance",),
    "prd": ("redistribution",),
    "crd": ("redistribution",),
    "sphere": ("spherical",),
    "radius": ("spherical", "distance"),
    "spectrum": ("emergent", "profile"),
    "profile": ("profile",),
    "opacity": ("opacit",),
    "column mass": ("column mass",),
}

_STATE = {
    "install": None,
    "root": None,
    "model": None,       # Atmosphere
    "model_path": None,
    "run": None,         # dict with status/log/result
}
_LOCK = threading.Lock()


# --------------------------------------------------------------------------
def _json_bytes(obj) -> bytes:
    return json.dumps(obj).encode()


def depth_axes(m: "Atmosphere") -> dict:
    """Alternative depth axes for plotting a model, from its own tables.

    Returns {key: {"label": str, "values": [...]}} with, as available:

      index   -- depth index 1..N (always);
      z_km    -- height [km] (negative above the surface reference);
      logm    -- log10 column mass [g/cm^2]: from ZMASS when the model
                 has it, else integrated from NH (rho = 1.4 m_H n_H);
      logtau  -- log10 tau(5000 A): an LTE estimate from H- bound-free
                 (Saha) + Thomson scattering -- approximate, for
                 orientation, and labeled as such. Both logm and logtau
                 increase downward, so the atmosphere's top is always
                 on the left of the plots.
    """
    import math

    n = m.n
    axes = {
        "index": {"label": "depth index", "values": list(range(1, n + 1))}
    }
    if m.z:
        axes["z_km"] = {"label": "height [km]",
                        "values": [zi / 1e5 for zi in m.z]}

    M_H = 1.6726e-24
    if m.zmass:
        axes["logm"] = {
            "label": "log m [g/cm2]",
            "values": [math.log10(max(x, 1e-12)) for x in m.zmass],
        }
    elif m.z and m.nh:
        col = []
        acc = 1.4 * M_H * m.nh[0] * abs(m.z[1] - m.z[0]) * 0.1
        for i in range(n):
            if i > 0:
                acc += (1.4 * M_H * 0.5 * (m.nh[i] + m.nh[i - 1])
                        * (m.z[i] - m.z[i - 1]))
            col.append(math.log10(max(acc, 1e-12)))
        axes["logm"] = {"label": "log m [g/cm2] (integrated)",
                        "values": col}

    if m.z and m.nh and m.ne and m.te:
        SIG_HM = 3.0e-17   # H- bf cross-section at 5000 A [cm^2]
        SIG_T = 6.652e-25  # Thomson
        tau = []
        acc = 1e-12
        kap_prev = None
        for i in range(n):
            T = max(m.te[i], 1.0)
            # Saha: n(H-)/(n(HI) n_e), and H ionization for n(HI)
            phi_hm = 1.035e-16 * T ** -1.5 * math.exp(min(8762.0 / T, 60))
            phi_h = 2.415e15 * T ** 1.5 * math.exp(-157800.0 / T)
            nhi = m.nh[i] / (1.0 + phi_h / max(m.ne[i], 1.0))
            kap = nhi * m.ne[i] * phi_hm * SIG_HM + SIG_T * m.ne[i]
            if i > 0:
                acc += 0.5 * (kap + kap_prev) * (m.z[i] - m.z[i - 1])
            kap_prev = kap
            tau.append(math.log10(max(acc, 1e-12)))
        axes["logtau"] = {
            "label": "log tau(5000) [approx: H- + Thomson, LTE]",
            "values": tau,
        }
    return axes


def _model_payload():
    m: Atmosphere = _STATE["model"]
    if m is None:
        return {"loaded": False}
    return {
        "loaded": True,
        "name": m.name,
        "path": str(_STATE["model_path"] or ""),
        "n": m.n,
        "z": m.z,
        "te": m.te,
        "ne": m.ne,
        "nh": m.nh,
        "v": m.v,
        "vt": m.vt,
        "vxs": m.vxs,
        "issues": m.validate(),
        "axes": depth_axes(m),
    }


def _run_payload():
    r = _STATE["run"]
    if r is None:
        return {"state": "idle"}
    out = {k: v for k, v in r.items() if k != "thread"}
    return out


def _launch_run(params):
    install: PandoraInstall = _STATE["install"]
    case = params["case"]
    rid = params.get("run_id", "001")
    atom = params.get("atom") or None
    levels = params.get("levels") or None
    workdir = params.get("workdir") or str(Path(_STATE["root"]) / "runs")

    run = PandoraRun(
        install,
        case=case,
        run_id=rid,
        dat=params["dat"],
        mod=params.get("mod") or None,
        atm=params.get("atm") or None,
        atom=(atom, levels) if atom and levels else atom,
        res=params.get("res") or None,
        jnu=params.get("jnu") or None,
        workdir=workdir,
    )

    info = {"state": "running", "case": case, "run_id": rid, "log": "",
            "outputs": {}}
    _STATE["run"] = info

    def work():
        try:
            res = run.execute(overwrite=True)
            info["log"] = res.log[-20000:]
            info["outputs"] = {k: str(v) for k, v in res.outputs.items()}
            info["elapsed"] = res.elapsed
            info["state"] = "done" if res.ok else "failed"
        except Exception:  # noqa: BLE001
            info["log"] += "\n" + traceback.format_exc()
            info["state"] = "failed"

    t = threading.Thread(target=work, daemon=True)
    info["thread"] = t
    t.start()


# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code=200, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # ------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif u.path == "/api/state":
                self._send(200, _json_bytes({
                    "root": str(_STATE["root"]),
                    "model": _model_payload(),
                    "run": _run_payload(),
                    "atoms": sorted(
                        p.name for p in
                        _STATE["install"].atoms_dir.glob("*.atm")
                    ),
                }))
            elif u.path == "/api/sections":
                aaa = AaaFile(q["aaa"])
                self._send(200, _json_bytes(
                    [{"psn": p, "title": t} for p, t in aaa.sections]
                ))
            elif u.path == "/api/section_text":
                aaa = AaaFile(q["aaa"])
                sec = aaa.section(int(q["psn"]))
                self._send(200, _json_bytes({"text": sec.text[:400000]}))
            elif u.path == "/api/profile":
                aaa = AaaFile(q["aaa"])
                blocks = aaa.profile(int(q["upper"]), int(q["lower"]))
                self._send(200, _json_bytes([
                    {"kind": b.kind, "mu": b.mu, "wl": b.wl, "inu": b.inu,
                     "ilam": b.ilam, "tb": b.tb,
                     "line_center": b.line_center}
                    for b in blocks
                ]))
            elif u.path == "/api/params":
                db = json.loads(
                    (Path(__file__).parent / "data" / "parameters.json")
                    .read_text()
                )
                needle = q.get("q", "").upper()
                # everyday words -> PANDORA's own vocabulary, so users
                # need not know the code's terminology to search
                needles = {needle} | {
                    s.upper() for s in _PARAM_SYNONYMS.get(needle.lower(), ())
                }
                hits = [
                    p for p in db
                    if p.get("name") and any(
                        nd in p["name"].upper()
                        or nd in (p.get("description") or "").upper()
                        for nd in needles
                    )
                ][:80]
                self._send(200, _json_bytes(hits))
            elif u.path == "/api/browse":
                d = Path(q.get("dir") or _STATE["root"]).expanduser()
                items = []
                if d.is_dir():
                    for p in sorted(d.iterdir()):
                        if p.name.startswith("."):
                            continue
                        items.append({
                            "name": p.name, "dir": p.is_dir(),
                            "path": str(p),
                        })
                self._send(200, _json_bytes(
                    {"dir": str(d), "parent": str(d.parent), "items": items}
                ))
            else:
                self._send(404, _json_bytes({"error": "not found"}))
        except Exception as exc:  # noqa: BLE001
            self._send(500, _json_bytes(
                {"error": str(exc), "trace": traceback.format_exc()}
            ))

    # ------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        try:
            body = self._body()
            if u.path == "/api/load_model":
                path = Path(body["path"]).expanduser()
                with _LOCK:
                    _STATE["model"] = Atmosphere.read(path)
                    _STATE["model_path"] = path
                self._send(200, _json_bytes(_model_payload()))
            elif u.path == "/api/update_model":
                with _LOCK:
                    m: Atmosphere = _STATE["model"]
                    for key in ("z", "te", "ne", "nh", "v", "vt", "vxs"):
                        if key in body and body[key] is not None:
                            setattr(m, key, [float(x) for x in body[key]])
                self._send(200, _json_bytes(_model_payload()))
            elif u.path == "/api/save_model":
                path = Path(body["path"]).expanduser()
                with _LOCK:
                    m: Atmosphere = _STATE["model"]
                    # Atmosphere wraps its source deck: to_deck() keeps the
                    # original statement structure and replaces the arrays
                    m.write(path)
                    _STATE["model_path"] = path
                self._send(200, _json_bytes({"saved": str(path)}))
            elif u.path == "/api/run":
                _launch_run(body)
                self._send(200, _json_bytes(_run_payload()))
            else:
                self._send(404, _json_bytes({"error": "not found"}))
        except Exception as exc:  # noqa: BLE001
            self._send(500, _json_bytes(
                {"error": str(exc), "trace": traceback.format_exc()}
            ))


def serve(root=None, port=8765, open_browser=True, max_port_tries=20):
    """Start the GUI, moving to the next free port if `port` is taken.

    A previous GUI (or any other program) may already hold the port;
    rather than failing, try the next few ports and say which one was
    used. Pass max_port_tries=1 to insist on exactly `port`.
    """
    root = Path(root or (Path.home() / "pandora")).expanduser()
    _STATE["root"] = root
    _STATE["install"] = PandoraInstall(root)

    httpd = None
    first = port
    for candidate in range(first, first + max(1, max_port_tries)):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError as exc:
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES):
                raise
    if httpd is None:
        raise SystemExit(
            f"pandorakit GUI: ports {first}-{first + max_port_tries - 1} "
            "are all in use.\n"
            "  Another GUI is probably still running: open "
            f"http://127.0.0.1:{first}/ to use it,\n"
            "  stop it with  pkill -f pandorakit.gui  , "
            "or choose another port with  --port NNNN"
        )
    if port != first:
        print(f"note: port {first} was busy (another GUI running?), "
              f"using {port} instead")

    url = f"http://127.0.0.1:{port}/"
    print(f"pandorakit GUI at {url}  (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------
PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>pandorakit</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --bg:#10141a; --panel:#1a212b; --ink:#e8edf4; --dim:#8b98a9;
  --acc:#5cc8ff; --acc2:#ffb454; --ok:#7dd491; --bad:#ff7a7a;
  --grid:#2a3442;
}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 -apple-system,'Segoe UI',Roboto,sans-serif;
     background:var(--bg);color:var(--ink)}
header{display:flex;align-items:baseline;gap:14px;padding:10px 18px;
       background:var(--panel);border-bottom:1px solid var(--grid)}
header h1{font-size:17px;margin:0;color:var(--acc)}
header .sub{color:var(--dim);font-size:12px}
nav{display:flex;gap:4px;margin-left:auto}
nav button{background:none;border:1px solid var(--grid);color:var(--dim);
  padding:5px 12px;border-radius:6px;cursor:pointer;font-size:13px}
nav button.active{color:var(--ink);border-color:var(--acc);background:#20303f}
main{padding:14px 18px;max-width:1300px;margin:0 auto}
.tab{display:none}.tab.active{display:block}
.card{background:var(--panel);border:1px solid var(--grid);border-radius:10px;
      padding:14px;margin-bottom:14px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
label{display:block;font-size:11px;color:var(--dim);margin-bottom:2px}
input,select{background:#0d1117;color:var(--ink);border:1px solid var(--grid);
  border-radius:6px;padding:6px 8px;font-size:13px;min-width:60px}
input[type=text]{min-width:220px}
button.go{background:var(--acc);color:#00131f;border:none;border-radius:6px;
  padding:7px 16px;font-weight:600;cursor:pointer}
button.mini{background:#233041;color:var(--ink);border:1px solid var(--grid);
  border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px}
svg{display:block;width:100%;background:#0d1117;border:1px solid var(--grid);
    border-radius:8px}
.axis{stroke:var(--grid);stroke-width:1}
.lbl{fill:var(--dim);font-size:10px}
pre{background:#0d1117;border:1px solid var(--grid);border-radius:8px;
    padding:10px;max-height:420px;overflow:auto;font-size:11.5px;color:#c7d2e0}
table{border-collapse:collapse;font-size:12px}
td,th{border:1px solid var(--grid);padding:3px 8px;text-align:right}
th{color:var(--dim);font-weight:500}
.status{font-weight:600}
.status.done{color:var(--ok)}.status.failed{color:var(--bad)}
.status.running{color:var(--acc2)}
.hint{color:var(--dim);font-size:12px;margin-top:6px}
.browser{max-height:260px;overflow:auto;background:#0d1117;
  border:1px solid var(--grid);border-radius:8px;padding:6px;font-size:12.5px}
.browser div{padding:2px 6px;cursor:pointer;border-radius:4px}
.browser div:hover{background:#20303f}
.browser .d{color:var(--acc)}
#paramlist div{padding:6px 8px;border-bottom:1px solid var(--grid)}
#paramlist b{color:var(--acc2)}
</style></head><body>
<header>
  <h1>pandorakit</h1><span class="sub">PANDORA non-LTE atmospheres &amp; spectra</span>
  <nav>
    <button data-tab="model" class="active">Model editor</button>
    <button data-tab="run">Run</button>
    <button data-tab="results">Results</button>
    <button data-tab="params">Parameters</button>
  </nav>
</header>
<main>

<!-- ============================ MODEL ============================ -->
<div class="tab active" id="tab-model">
  <div class="card">
    <div class="row">
      <div style="flex:1"><label>Model file (.mod)</label>
        <input type="text" id="modelPath" placeholder="/path/to/model.mod"></div>
      <button class="mini" onclick="browse('modelPath')">browse…</button>
      <button class="go" onclick="loadModel()">Load</button>
      <div style="flex:1"><label>Save as</label>
        <input type="text" id="savePath"></div>
      <button class="go" onclick="saveModel()">Save</button>
    </div>
    <div class="browser" id="fileBrowser" style="display:none;margin-top:8px"></div>
    <div class="row" style="margin-top:8px;align-items:center">
      <label style="margin:0">Depth axis</label>
      <select id="axisSel" onchange="setAxis(this.value)"></select>
      <span class="hint" id="axisNote"></span>
    </div>
    <div class="hint" id="modelInfo">no model loaded</div>
  </div>
  <div class="card">
    <div class="row" style="align-items:center">
      <b>T(z)</b><span class="hint">drag points; shift-drag = move neighbours
      (Gaussian); double-click a point to type a value</span>
      <span style="margin-left:auto"></span>
      <button class="mini" onclick="scaleTE(0.98)">T &times;0.98</button>
      <button class="mini" onclick="scaleTE(1.02)">T &times;1.02</button>
      <button class="mini" onclick="undoTE()">undo</button>
    </div>
    <svg id="teplot" height="340" viewBox="0 0 1000 340"></svg>
  </div>
  <div class="card">
    <div class="row" style="align-items:center">
      <b>Velocities</b>
      <span class="hint" id="velInfo">km/s; drag points like T(z).
        VXS = expansion (outflow +), VT/V = broadening.
        A run only feels VXS with DO ( EXPAND ) in its deck
        (see recipes.set_expansion / examples/velocity_mass_outflow.py)</span>
      <span style="margin-left:auto"></span>
      <button class="mini" id="addVxsBtn" onclick="addVXS()">add VXS (wind) table</button>
    </div>
    <svg id="velplot" height="260" viewBox="0 0 1000 260"></svg>
  </div>
  <div class="card">
    <b>Densities</b>
    <svg id="denplot" height="260" viewBox="0 0 1000 260"></svg>
  </div>
</div>

<!-- ============================ RUN ============================ -->
<div class="tab" id="tab-run">
  <div class="card">
    <div class="row">
      <div><label>Case name</label><input id="rCase" value="star1"></div>
      <div><label>Run id</label><input id="rId" value="001" size="5"></div>
      <div style="flex:1"><label>.dat deck</label><input id="rDat" type="text"></div>
      <button class="mini" onclick="browse('rDat')">browse…</button>
    </div>
    <div class="row" style="margin-top:8px">
      <div style="flex:1"><label>.mod model (blank = none)</label>
        <input id="rMod" type="text"></div>
      <button class="mini" onclick="browse('rMod')">browse…</button>
      <div><label>Atom (library)</label><select id="rAtom"></select></div>
      <div style="flex:1"><label>.res restart (optional)</label>
        <input id="rRes" type="text"></div>
      <div style="flex:1"><label>.jnu (optional, PRD)</label>
        <input id="rJnu" type="text"></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button class="go" onclick="startRun()">Run PANDORA</button>
      <span class="status" id="runState">idle</span>
      <span class="hint" id="runMeta"></span>
    </div>
  </div>
  <div class="card"><b>Log</b><pre id="runLog">–</pre></div>
</div>

<!-- ============================ RESULTS ============================ -->
<div class="tab" id="tab-results">
  <div class="card">
    <div class="row">
      <div style="flex:1"><label>.aaa printout file</label>
        <input id="aaaPath" type="text"></div>
      <button class="mini" onclick="browse('aaaPath')">browse…</button>
      <button class="go" onclick="listSections()">Open</button>
    </div>
    <div class="row" style="margin-top:8px">
      <div><label>Sections</label><select id="secList" size="8"
        style="min-width:280px"></select></div>
      <div style="flex:1">
        <div class="row">
          <div><label>Transition u</label><input id="pU" value="2" size="3"></div>
          <div><label>l</label><input id="pL" value="1" size="3"></div>
          <button class="go" onclick="showProfile()">Plot profile</button>
          <button class="mini" onclick="showSectionText()">Show section text</button>
          <button class="mini" onclick="exportCSV()">Export CSV</button>
        </div>
        <svg id="profplot" height="330" viewBox="0 0 1000 330"
             style="margin-top:8px"></svg>
      </div>
    </div>
  </div>
  <div class="card"><b>Section text</b><pre id="secText">–</pre></div>
</div>

<!-- ============================ PARAMS ============================ -->
<div class="tab" id="tab-params">
  <div class="card">
    <div class="row">
      <div style="flex:1"><label>Search the 700+ input parameters
        (name or description)</label>
        <input id="pq" type="text" placeholder="e.g. IOMX, abundance, turbulence"
               oninput="searchParams()"></div>
    </div>
    <div id="paramlist" style="margin-top:10px"></div>
  </div>
</div>
</main>
<script>
"use strict";
const $ = id => document.getElementById(id);
const api = async (p, opts) => {
  const r = await fetch(p, opts);
  const j = await r.json();
  if (j && j.error) throw new Error(j.error);
  return j;
};
const post = (p, body) => api(p, {method:"POST", body:JSON.stringify(body)});

/* ---------- tabs ---------- */
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");
  $("tab-"+b.dataset.tab).classList.add("active");
});

/* ---------- state ---------- */
let M = null;          // model payload
let teHistory = [];
let atoms = [];

async function refresh(){
  const s = await api("/api/state");
  atoms = s.atoms;
  const sel = $("rAtom");
  sel.innerHTML = "<option value=''>(none)</option>" +
    atoms.map(a=>`<option>${a}</option>`).join("");
  if (s.model.loaded){ M = s.model; buildAxisSelector(); drawAll(); }
}
refresh();

/* ---------- file browser ---------- */
let browseTarget = null;
async function browse(target){
  browseTarget = target;
  const start = $(target).value || "";
  await showDir(start.replace(/[^/]*$/, "") || undefined);
}
async function showDir(dir){
  const j = await api("/api/browse" + (dir?`?dir=${encodeURIComponent(dir)}`:""));
  const el = $("fileBrowser"); el.style.display = "block";
  let html = `<div class="d" onclick="showDir('${j.parent}')">&#8679; ..</div>`;
  for (const it of j.items){
    html += it.dir
      ? `<div class="d" onclick="showDir('${it.path}')">&#128193; ${it.name}</div>`
      : `<div onclick="pick('${it.path}')">${it.name}</div>`;
  }
  el.innerHTML = html;
  el.scrollTop = 0;
}
function pick(path){
  if (browseTarget) $(browseTarget).value = path;
  $("fileBrowser").style.display = "none";
}

/* ---------- model ---------- */
/* ---------- depth axis ---------- */
let AXIS = "z_km";
const AXIS_NAMES = {index:"depth index", z_km:"height [km]",
                    logm:"log column mass", logtau:"log τ(5000)"};
function ax(){ return M.axes[AXIS].values; }
function axLabel(){ return M.axes[AXIS].label; }
function axFmt(v){
  if (AXIS === "z_km") return v.toExponential(1);
  if (AXIS === "index") return v.toFixed(0);
  return v.toFixed(1);
}
function setAxis(k){
  AXIS = k;
  $("axisSel").value = k;          // keep the selector in sync
  $("axisNote").textContent = M.axes[k].label;
  drawAll();
}
function buildAxisSelector(){
  const sel = $("axisSel");
  const keys = Object.keys(M.axes);
  sel.innerHTML = keys.map(k =>
    `<option value="${k}">${AXIS_NAMES[k] || k}</option>`).join("");
  if (!keys.includes(AXIS))
    AXIS = keys.includes("z_km") ? "z_km" : keys[0];
  sel.value = AXIS;
  $("axisNote").textContent = M.axes[AXIS].label;
}

async function loadModel(){
  M = await post("/api/load_model", {path: $("modelPath").value});
  $("savePath").value = $("modelPath").value;
  teHistory = [];
  buildAxisSelector();
  drawAll();
}
async function saveModel(){
  await post("/api/update_model",
             {te: M.te, ne: M.ne, nh: M.nh, v: M.v, vt: M.vt, vxs: M.vxs});
  const j = await post("/api/save_model", {path: $("savePath").value});
  $("modelInfo").textContent = "saved to " + j.saved;
}
function drawAll(){
  if (!M || !M.loaded) return;
  $("modelInfo").textContent =
    `${M.name}: N=${M.n} depths, T ${Math.min(...M.te).toFixed(0)}–` +
    `${Math.max(...M.te).toFixed(0)} K` +
    (M.issues.length ? "  ⚠ " + M.issues.join("; ") : "  ✓ runnable");
  drawTE(); drawDen(); drawVel();
}

/* ---- generic plot helpers ---- */
function frame(svg, W, H, pad){
  svg.innerHTML = "";
  const g = (x1,y1,x2,y2)=>{
    const l=document.createElementNS("http://www.w3.org/2000/svg","line");
    l.setAttribute("x1",x1);l.setAttribute("y1",y1);
    l.setAttribute("x2",x2);l.setAttribute("y2",y2);
    l.setAttribute("class","axis");svg.appendChild(l);
  };
  g(pad,H-pad,W-pad,H-pad); g(pad,pad,pad,H-pad);
  return svg;
}
function text(svg,x,y,s,anchor="middle",cls="lbl"){
  const t=document.createElementNS("http://www.w3.org/2000/svg","text");
  t.setAttribute("x",x);t.setAttribute("y",y);
  t.setAttribute("text-anchor",anchor);t.setAttribute("class",cls);
  t.textContent=s;svg.appendChild(t);
}
function poly(svg, pts, color, w=2){
  const p=document.createElementNS("http://www.w3.org/2000/svg","polyline");
  p.setAttribute("points", pts.map(q=>q.join(",")).join(" "));
  p.setAttribute("fill","none");p.setAttribute("stroke",color);
  p.setAttribute("stroke-width",w);svg.appendChild(p);
  return p;
}

/* ---- T(z) editor ---- */
const TEP = {W:1000,H:340,pad:46};
function teScales(){
  const {W,H,pad}=TEP;
  const av=ax();
  const a0=Math.min(...av), a1=Math.max(...av);
  const tmin=Math.min(...M.te)*0.9, tmax=Math.max(...M.te)*1.05;
  const lt0=Math.log10(tmin), lt1=Math.log10(tmax);
  return {
    x: i => pad + (av[i]-a0)/(a1-a0||1)*(W-2*pad),
    y: t => H-pad - (Math.log10(t)-lt0)/(lt1-lt0)*(H-2*pad),
    yi: py => Math.pow(10, lt0 + (H-pad-py)/(H-2*pad)*(lt1-lt0)),
    tmin,tmax
  };
}
function xTicks(svg, W, H, pad){
  // 6 tick labels evenly spaced ON SCREEN (the depth grid itself is
  // strongly non-uniform, so index-spaced ticks would collide)
  const av=ax();
  const a0=Math.min(...av), a1=Math.max(...av);
  for (let t=0;t<=5;t++){
    const val = a0 + (a1-a0)*t/5;
    const xpx = pad + t/5*(W-2*pad);
    text(svg, xpx, H-pad+14, axFmt(val));
  }
  text(svg, W/2, H-4, axLabel());
}
function drawTE(){
  const svg=$("teplot"); const {W,H,pad}=TEP;
  frame(svg,W,H,pad);
  const s=teScales();
  for (let i=0;i<=4;i++){
    const t = s.tmin*Math.pow(s.tmax/s.tmin, i/4);
    text(svg, pad-6, s.y(t)+3, (t>=1e4? (t/1e3).toFixed(0)+"k" :
      t.toFixed(0)), "end");
  }
  xTicks(svg, W, H, pad);
  text(svg, 14, 16, "T [K] (log)", "start");
  poly(svg, M.te.map((t,i)=>[s.x(i), s.y(t)]), "var(--acc2)", 2);
  M.te.forEach((t,i)=>{
    const c=document.createElementNS("http://www.w3.org/2000/svg","circle");
    c.setAttribute("cx",s.x(i));c.setAttribute("cy",s.y(t));
    c.setAttribute("r",5);c.setAttribute("fill","var(--acc)");
    c.style.cursor="ns-resize";
    c.addEventListener("pointerdown", e=>startDrag(e,i));
    c.addEventListener("dblclick", ()=>{
      const v=prompt(
        `TE at depth ${i+1} (${axLabel()} = ${axFmt(ax()[i])})`,
        M.te[i]);
      if(v){pushHist(); M.te[i]=parseFloat(v); drawTE();}
    });
    svg.appendChild(c);
  });
}
function pushHist(){ teHistory.push([...M.te]); if(teHistory.length>60)
  teHistory.shift(); }
function undoTE(){ if(teHistory.length){ M.te=teHistory.pop(); drawTE(); } }
function scaleTE(f){ pushHist(); M.te=M.te.map(t=>t*f); drawTE(); }
let drag=null;
function startDrag(e,i){
  pushHist();
  drag={i, shift:e.shiftKey};
  const svg=$("teplot");
  const move=ev=>{
    const r=svg.getBoundingClientRect();
    const py=(ev.clientY-r.top)*TEP.H/r.height;
    const s=teScales();
    const newT=Math.max(500, s.yi(py));
    if (drag.shift){
      const sig=Math.max(2, M.n/12);
      const ratio=newT/M.te[drag.i];
      M.te=M.te.map((t,k)=>{
        const w=Math.exp(-0.5*Math.pow((k-drag.i)/sig,2));
        return t*Math.pow(ratio,w);
      });
    } else {
      M.te[drag.i]=newT;
    }
    drawTE();
  };
  const up=()=>{window.removeEventListener("pointermove",move);
               window.removeEventListener("pointerup",up);};
  window.addEventListener("pointermove",move);
  window.addEventListener("pointerup",up);
}

/* ---- velocity editor ---- */
// active editable series: VXS if present, else VT, else V
function velActive(){
  if (M.vxs) return ["vxs", M.vxs, "var(--acc2)"];
  if (M.vt)  return ["vt",  M.vt,  "var(--acc)"];
  if (M.v)   return ["v",   M.v,   "var(--acc)"];
  return null;
}
function addVXS(){
  if (!M || !M.loaded) return;
  if (!M.vxs) M.vxs = new Array(M.n).fill(0.0);
  drawVel();
}
let vdrag=null;
function drawVel(){
  const svg=$("velplot"); const W=1000,H=260,pad=46;
  frame(svg,W,H,pad);
  const act = velActive();
  $("addVxsBtn").style.display = (M && M.loaded && !M.vxs) ? "" : "none";
  if (!act){
    text(svg, W/2, H/2,
         "no velocity tables in this file - click 'add VXS' to create a wind");
    return;
  }
  const av=ax();
  const a0=Math.min(...av), a1=Math.max(...av);
  const series=[["vxs",M.vxs,"var(--acc2)"],["vt",M.vt,"var(--acc)"],
                ["v",M.v,"var(--ok)"]].filter(s=>s[1]);
  const all=series.flatMap(s=>s[1]);
  let v0=Math.min(0,...all), v1=Math.max(1,...all);
  const p=(v1-v0)*0.1; v0-=p; v1+=p;
  const x=i=>pad+(av[i]-a0)/(a1-a0||1)*(W-2*pad);
  const y=v=>H-pad-(v-v0)/(v1-v0)*(H-2*pad);
  const yi=py=>v0+(H-pad-py)/(H-2*pad)*(v1-v0);
  for(let i=0;i<=4;i++){
    const v=v0+(v1-v0)*i/4;
    text(svg,pad-6,y(v)+3,v.toFixed(0),"end");
  }
  xTicks(svg, W, H, pad);
  if (v0<0){ // zero line
    const l=document.createElementNS("http://www.w3.org/2000/svg","line");
    l.setAttribute("x1",pad);l.setAttribute("y1",y(0));
    l.setAttribute("x2",W-pad);l.setAttribute("y2",y(0));
    l.setAttribute("stroke","var(--grid)");l.setAttribute("stroke-dasharray","4 4");
    svg.appendChild(l);
  }
  series.forEach(([nm,arr,col],k)=>{
    poly(svg, arr.map((vv,i)=>[x(i),y(vv)]), col, nm===act[0]?2.5:1.5);
    text(svg, W-pad-8, pad+14+k*14, nm.toUpperCase(), "end");
  });
  // draggable points on the active series
  const [aname, aarr] = act;
  aarr.forEach((vv,i)=>{
    const c=document.createElementNS("http://www.w3.org/2000/svg","circle");
    c.setAttribute("cx",x(i));c.setAttribute("cy",y(vv));
    c.setAttribute("r",4.5);c.setAttribute("fill",act[2]);
    c.style.cursor="ns-resize";
    c.addEventListener("pointerdown", e=>{
      vdrag={i, shift:e.shiftKey};
      const move=ev=>{
        const r=svg.getBoundingClientRect();
        const nv=yi((ev.clientY-r.top)*H/r.height);
        if (vdrag.shift){
          const sig=Math.max(2, M.n/12);
          const dv=nv-aarr[vdrag.i];
          for(let k2=0;k2<M.n;k2++){
            aarr[k2]+=dv*Math.exp(-0.5*Math.pow((k2-vdrag.i)/sig,2));
          }
        } else { aarr[vdrag.i]=nv; }
        drawVel();
      };
      const up=()=>{window.removeEventListener("pointermove",move);
                    window.removeEventListener("pointerup",up);};
      window.addEventListener("pointermove",move);
      window.addEventListener("pointerup",up);
    });
    c.addEventListener("dblclick", ()=>{
      const nv=prompt(`${aname.toUpperCase()} at depth ${i+1} (km/s)`, aarr[i]);
      if(nv!==null){aarr[i]=parseFloat(nv); drawVel();}
    });
    svg.appendChild(c);
  });
  text(svg,14,16,`km/s (editing ${aname.toUpperCase()})`,"start");
}

/* ---- density plot ---- */
function drawDen(){
  const svg=$("denplot"); const W=1000,H=260,pad=46;
  frame(svg,W,H,pad);
  const av=ax();
  const a0=Math.min(...av), a1=Math.max(...av);
  const series=[["NH",M.nh,"var(--acc)"],["NE",M.ne,"var(--ok)"]]
    .filter(s=>s[1]);
  const all=series.flatMap(s=>s[1]).filter(v=>v>0);
  const l0=Math.log10(Math.min(...all)), l1=Math.log10(Math.max(...all));
  const x=i=>pad+(av[i]-a0)/(a1-a0||1)*(W-2*pad);
  const y=v=>H-pad-(Math.log10(v)-l0)/(l1-l0)*(H-2*pad);
  for(let i=0;i<=4;i++){
    const lv=l0+(l1-l0)*i/4;
    text(svg,pad-6,y(Math.pow(10,lv))+3,"1e"+lv.toFixed(0),"end");
  }
  xTicks(svg, W, H, pad);
  series.forEach(([nm,arr,col],k)=>{
    poly(svg, arr.map((vv,i)=>[x(i),y(Math.max(vv,1e-30))]), col, 2);
    text(svg, W-pad-8, pad+14+k*14, nm, "end");
  });
  text(svg,14,16,"n [cm⁻³] (log)","start");
}

/* ---------- run ---------- */
async function startRun(){
  const atomFile=$("rAtom").value;
  let atom=null, levels=null;
  if (atomFile){
    const m=atomFile.match(/^([a-z0-9]+?)(l\d+[a-z]*)\.atm$/);
    if (m){atom=m[1];levels=m[2];}
  }
  await post("/api/run",{
    case:$("rCase").value, run_id:$("rId").value,
    dat:$("rDat").value, mod:$("rMod").value,
    atom:atom, levels:levels,
    res:$("rRes").value, jnu:$("rJnu").value,
  });
  pollRun();
}
async function pollRun(){
  const s=await api("/api/state");
  const r=s.run;
  const el=$("runState");
  el.textContent=r.state; el.className="status "+r.state;
  $("runLog").textContent=r.log||"(starting…)";
  if (r.outputs && r.outputs.aaa){
    $("aaaPath").value=r.outputs.aaa;
    $("runMeta").textContent =
      `outputs: ${Object.keys(r.outputs).join(", ")}` +
      (r.elapsed?`  (${r.elapsed.toFixed(1)} s)`:"");
  }
  if (r.state==="running") setTimeout(pollRun, 1500);
}

/* ---------- results ---------- */
let lastProfile=null;
async function listSections(){
  const secs=await api("/api/sections?aaa="+encodeURIComponent($("aaaPath").value));
  $("secList").innerHTML =
    secs.map(s=>`<option value="${s.psn}">${s.title}</option>`).join("");
}
async function showSectionText(){
  const psn=$("secList").value;
  if(!psn) return;
  const j=await api(`/api/section_text?aaa=${encodeURIComponent($("aaaPath").value)}&psn=${psn}`);
  $("secText").textContent=j.text;
}
async function showProfile(){
  const all=await api(`/api/profile?aaa=${encodeURIComponent($("aaaPath").value)}` +
                    `&upper=${$("pU").value}&lower=${$("pL").value}`);
  // prefer the emergent line profile blocks (DL axis); fall back to the
  // line-specific background spectrum blocks
  let j=all.filter(b=>b.kind==="line_profile");
  let axisNote="ΔΛ from line center [Å]";
  if(!j.length){ j=all; axisNote="wavelength [Å]"; }
  if(j.length && j[0].line_center)
    axisNote += `   (line at ${j[0].line_center.toFixed(2)} Å)`;
  lastProfile=j;
  const svg=$("profplot"); const W=1000,H=330,pad=52;
  frame(svg,W,H,pad);
  if(!j.length){text(svg,W/2,H/2,"no profile blocks found");return;}
  const wls=j.flatMap(b=>b.wl), ils=j.flatMap(b=>b.ilam).filter(v=>v>0);
  const w0=Math.min(...wls), w1=Math.max(...wls);
  const l0=Math.log10(Math.min(...ils)), l1=Math.log10(Math.max(...ils));
  const x=w=>pad+(w-w0)/(w1-w0)*(W-2*pad);
  const y=v=>H-pad-(Math.log10(Math.max(v,1e-30))-l0)/(l1-l0)*(H-2*pad);
  const cols=["var(--acc)","var(--acc2)","var(--ok)","#d48bff","#ff8bb3"];
  j.forEach((b,k)=>{
    poly(svg,b.wl.map((w,i)=>[x(w),y(b.ilam[i])]),cols[k%cols.length],2);
    text(svg,W-pad-8,pad+14+k*14,
         (b.mu===null?"flux":("μ="+b.mu))+" ("+b.kind.replace(/_/g," ")+")",
         "end");
  });
  for(let i=0;i<=5;i++){
    const w=w0+(w1-w0)*i/5;
    text(svg,x(w),H-pad+14,w.toFixed(2));
  }
  text(svg,14,16,"I(λ) [erg cm⁻² s⁻¹ sr⁻¹ Å⁻¹] (log)","start");
  text(svg,W/2,H-8,axisNote);
}
function exportCSV(){
  if(!lastProfile) return;
  let s="block,mu,wl_A,I_nu,I_A,T_b\n";
  lastProfile.forEach((b,k)=>{
    b.wl.forEach((w,i)=>{
      s+=`${k},${b.mu===null?"flux":b.mu},${w},${b.inu[i]},${b.ilam[i]},${b.tb[i]}\n`;
    });
  });
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([s],{type:"text/csv"}));
  a.download="profile.csv"; a.click();
}

/* ---------- params ---------- */
let pqTimer=null;
function searchParams(){
  clearTimeout(pqTimer);
  pqTimer=setTimeout(async ()=>{
    const q=$("pq").value.trim();
    if(!q){$("paramlist").innerHTML="";return;}
    const hits=await api("/api/params?q="+encodeURIComponent(q));
    $("paramlist").innerHTML=hits.map(p=>
      `<div><b>${p.name}</b> ${p.length?("["+p.length+"] "):""}` +
      `<span style="color:var(--dim)">${p.codes||""} ${p.mode||""}</span><br>` +
      `${p.description||""}` +
      (p.default?`<br><span style="color:var(--dim)">default: ${p.default}</span>`:"") +
      `</div>`).join("");
  },250);
}
</script>
</body></html>
"""


if __name__ == "__main__":  # pragma: no cover
    import os

    serve(
        root=os.environ.get("PANDORAKIT_ROOT"),
        open_browser=os.environ.get("PANDORAKIT_NO_BROWSER") != "1",
    )
