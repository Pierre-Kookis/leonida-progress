#!/usr/bin/env python3
"""Leonida progress page: one self-contained HTML file built from a Leonida checkout.

    python -I progress.py --repo <Leonida checkout> [--isa amdgpu_isa_rdna2.xml] [--local local.json] [--out progress.html]

Every number is read from the checkout's docs/ at the time of the run (a regex per row, listed in ROWS below), so the
page follows the repository instead of being typed by hand. With --isa, the ISA grid runs tools/isa_coverage.py on
AMD's XML and shows one cell per instruction; without it, the grid is drawn from the totals quoted in
docs/isa_coverage.md. --local overrides rows with your own measurements: {"rows": {"<row label>": {"n": 1, "d": 2,
"note": "..."}}}. Counts only: nothing of the game goes into the page. Standard library only.
"""
import argparse, datetime, html, json, os, re, subprocess, sys

GITHUB = "https://github.com/ItsNotRexed/Leonida"
NUM = r"[\d,]+"


def num(s):
    return float(s.replace(",", ""))


class Src:
    """A row's source: a regex over a doc, giving n/d (named groups n, d, f = failures) or p (percent)."""

    def __init__(self, path, pattern, const_d=None):
        self.path, self.rx, self.const_d = path, re.compile(pattern, re.S), const_d


def table_rows(text, header_start):
    """Rows (lists of cells) of the first markdown table whose header line starts with header_start."""
    lines, out, on = text.splitlines(), [], False
    for ln in lines:
        if ln.startswith(header_start):
            on = True
            continue
        if on:
            if not ln.startswith("|"):
                break
            if set(ln.replace("|", "").strip()) <= set("-: "):
                continue
            out.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return out


def dll_imports(text):
    rows = table_rows(text, "| Image | Size of image")
    return sum(1 for r in rows if r[-1] == "0"), len(rows)


def xbox_imports(text):
    rows = table_rows(text, "| Consumer | Import | Binding")
    return sum(1 for r in rows if r[-1] == "shim"), len(rows)


def exe_present(text):
    return (0 if "executable is still missing" in text else 1), 1


# (area, label, source). A source is a Src or (path, function(text) -> (n, d)).
ROWS = [
    ("Shader translator (RDNA2 → SPIR-V)", "Corpus shaders translate + pass spirv-val",
     Src("docs/design.md", r"All (?P<n>" + NUM + r") shaders translate and pass `spirv-val`")),
    ("Shader translator (RDNA2 → SPIR-V)", "FSPX FidelityFX programs translate",
     Src("docs/README.md", r"fspx\.md.*?(?P<n>\d+) of (?P<d>\d+) translate")),
    ("Shader translator (RDNA2 → SPIR-V)", "BVH builder FSSM programs pass spirv-val",
     Src("docs/d3d12_vulkan.md", r"builder's (?P<d>\d+) console `FSSM` programs \((?P<n>\d+) pass `spirv-val`")),
    ("Runtime loader", "Package DLLs map and bind every import", ("docs/runtime_imports.md", dll_imports)),
    ("Runtime loader", "Xbox-only import uses served by shims", ("docs/runtime_imports.md", xbox_imports)),
    ("Runtime loader", "Game executable present", ("docs/runtime_imports.md", exe_present)),
    ("Assets (decoded without the executable)", "Models decoded",
     Src("docs/design.md", r"(?P<f>" + NUM + r") decode failures across all (?P<d>" + NUM + r") models")),
    ("Assets (decoded without the executable)", "TTPF textures, rpf9dump strict decode",
     Src("docs/README.md", r"(?P<d>" + NUM + r") TTPF descriptors.*?decodes (?P<n>" + NUM + r") strict-clean")),
    ("Assets (decoded without the executable)", "Multi-slice textures resolved",
     Src("docs/textures_arrays.md", r"layout-validated \(byte-exact span\)\*\* \| \*\*(?P<n>\d+) / (?P<d>\d+)")),
    ("Assets (decoded without the executable)", "Character textures matched",
     Src("docs/character_models.md", r"requested (?P<d>\d+) texture keys and matched \*\*(?P<n>\d+)\*\*")),
    ("Assets (decoded without the executable)", "PSIN block bytes reached",
     Src("docs/psin.md", r"\| \*\*all\*\* \|[^\n]*?\*\*(?P<d>" + NUM + r")\*\* \| \*\*(?P<n>" + NUM + r")\*\* \(")),
    ("Assets (decoded without the executable)", "World entity names resolved",
     Src("docs/README.md", r"(?P<p>[\d.]+)% of the " + NUM + r" entities")),
    ("Assets (decoded without the executable)", "levels.rpf bytes in accepted streams",
     Src("docs/world_census.md", r"Accepted stream payload \| " + NUM + r" \| (?P<p>[\d.]+)%")),
    ("Assets (decoded without the executable)", "navmeshes.rpf bytes in streams",
     Src("docs/navmesh.md", r"Stored \(compressed\) bytes \| " + NUM + r" \((?P<p>[\d.]+)% of span\)")),
    ("Assets (decoded without the executable)", "anim.rpf bytes readable",
     Src("docs/animation.md", r"\| readable \| (?P<p>[\d.]+)% of span")),
    ("Assets (decoded without the executable)", "common.rpf streams readable",
     Src("docs/design.md", r"`common\.rpf`: [^|]*?(?P<p>[\d.]+)% readable")),
    ("Assets (decoded without the executable)", "Radio titles resolved exactly",
     Src("docs/radio_stations.md", r"(?P<n>\d+)/(?P<d>\d+) exact `joaat")),
    ("Assets (decoded without the executable)", "Mission states named",
     Src("docs/mission_logic.md", r"\((?P<n>" + NUM + r") of (?P<d>" + NUM + r")\)")),
]
MILESTONE_AREA = "D3D12 → Vulkan boot milestones"


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def read(repo, path):
    with open(os.path.join(repo, path), encoding="utf-8") as f:
        return f.read()


def measure_row(repo, src):
    """{n, d, p, path, line, quote} or {error, path}."""
    if isinstance(src, tuple):
        path, fn = src
        text = read(repo, path)
        n, d = fn(text)
        return {"n": n, "d": d, "p": 100.0 * n / d if d else 0.0, "path": path, "line": None, "quote": None}
    text = read(repo, src.path)
    m = src.rx.search(text)
    if not m:
        return {"error": "pattern not found (the doc changed)", "path": src.path}
    g = m.groupdict()
    quote = re.sub(r"\s+", " ", m.group(0))[:220]
    base = {"path": src.path, "line": line_of(text, m.start()), "quote": quote}
    if g.get("p"):
        return {**base, "n": None, "d": None, "p": float(g["p"])}
    d = num(g["d"]) if g.get("d") else (num(g["n"]) if g.get("n") else None)
    n = d - num(g["f"]) if g.get("f") else (num(g["n"]) if g.get("n") else d)
    return {**base, "n": n, "d": d, "p": 100.0 * n / d if d else 0.0}


def milestones(repo):
    path = "docs/d3d12_vulkan.md"
    text = read(repo, path)
    out = []
    for m in re.finditer(r"^\| \*\*(M[\d.]+)\*\* \| ([^|]*) \|[^\n]*$", text, re.M):
        row = m.group(0)
        done = re.split(r"(?<!\\)\|", row)[-2]   # cells may hold escaped pipes (\|)
        if re.search(r"partly met", done, re.I):
            state = "partial"
        elif re.search(r"\bmet\b", done, re.I):
            state = "done"
        else:
            state = "open"
        out.append({"id": m.group(1), "scope": re.sub(r"[`*]", "", m.group(2)).strip()[:180], "state": state,
                    "line": line_of(text, m.start())})
    return out, path


def isa(repo, xml):
    if xml:
        r = subprocess.run([sys.executable, "-I", os.path.join(repo, "tools", "isa_coverage.py"), "--isa", xml, "--json"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            rep = json.loads(r.stdout)
            cells = sorted(rep["class"].items(), key=lambda kv: (CLASS_ORDER.index(kv[1]), kv[0]))
            return {"source": "tools/isa_coverage.py on " + os.path.basename(xml), "totals": rep["totals"],
                    "cells": [{"name": k, "cls": v} for k, v in cells], "line": None}
        print("isa_coverage.py failed, using docs/isa_coverage.md:\n" + r.stderr[-400:], file=sys.stderr)
    path = "docs/isa_coverage.md"
    text = read(repo, path)
    m = re.search(r"(" + NUM + r") RDNA2 instructions: (\d+) handled-exact, (\d+) handled-family, (\d+) refused.*?(\d+)\s+unknown",
                  text, re.S)
    if not m:
        return None
    t = dict(zip(CLASS_ORDER, (int(m.group(i)) for i in (2, 3, 4, 5))))
    return {"source": path, "totals": t, "line": line_of(text, m.start()),
            "cells": [{"name": None, "cls": c} for c in CLASS_ORDER for _ in range(t[c])]}


CLASS_ORDER = ["handled-exact", "handled-family", "refused", "unknown"]


def git_head(repo):
    try:
        r = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%H %cs"], capture_output=True, text=True)
        sha, date = r.stdout.split()
        return sha, date
    except (OSError, ValueError):
        return None, None


def build(repo, xml, local):
    sha, date = git_head(repo)
    overrides = (local or {}).get("rows", {})
    areas = {}
    for area, label, src in ROWS:
        try:
            row = measure_row(repo, src)
        except OSError as e:
            row = {"error": f"cannot read: {e.strerror}", "path": getattr(src, "path", src[0] if isinstance(src, tuple) else "")}
        if label in overrides:
            o = overrides[label]
            row = {**row, "n": o["n"], "d": o["d"], "p": 100.0 * o["n"] / o["d"] if o["d"] else 0.0,
                   "local": o.get("note", "local measurement"), "error": None}
        row["label"] = label
        areas.setdefault(area, []).append(row)
    ms, ms_path = milestones(repo)
    data = {"sha": sha, "date": date, "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "github": GITHUB, "milestone_area": MILESTONE_AREA, "milestones": ms, "milestones_path": ms_path,
            "areas": [{"name": k, "rows": v} for k, v in areas.items()], "isa": isa(repo, xml)}
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--isa", help="amdgpu_isa_rdna2.xml (optional)")
    ap.add_argument("--local", help="JSON of local measurements overriding rows")
    ap.add_argument("--out", default="progress.html")
    ap.add_argument("--json", action="store_true", help="print the data instead of writing the page")
    a = ap.parse_args()
    local = json.load(open(a.local, encoding="utf-8")) if a.local else None
    data = build(a.repo, a.isa, local)
    if a.json:
        print(json.dumps(data, indent=1))
        return 0
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html"), encoding="utf-8").read()
    page = tpl.replace("/*DATA*/null", json.dumps(data).replace("</", "<\\/"))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    bad = [r["label"] for ar in data["areas"] for r in ar["rows"] if r.get("error")]
    print(f"wrote {a.out} ({len(page):,} bytes) from {data['sha'][:8] if data['sha'] else '?'}"
          + (f"; rows without a source: {', '.join(bad)}" if bad else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
