#!/usr/bin/env python3
"""Leonida progress page: one self-contained HTML file built from a Leonida checkout.

    python -I progress.py --repo <Leonida checkout> [--isa amdgpu_isa_rdna2.xml] [--local local.json] [--out index.html]

Every number is read from the checkout's docs/ with the regexes in rows.json, so the page follows the repository
instead of being typed by hand. The page embeds that result as a snapshot and, when opened, reads the same docs from
Leonida's main branch on GitHub with the same rows.json, so it is current even if nobody regenerated it.
With --isa, the ISA grid runs tools/isa_coverage.py on AMD's XML (one cell per instruction, refreshed when the page is
regenerated, e.g. by the GitHub Actions workflow); without it, the grid comes from the totals in docs/isa_coverage.md.
--local overrides rows with your own measurements: {"rows": {"<row label>": {"n": 1, "d": 2, "note": "..."}}}.
Counts only: nothing of the game goes into the page. Standard library only.
"""
import argparse, datetime, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLASS_ORDER = ["handled-exact", "handled-family", "refused", "unknown"]


def load_spec():
    with open(os.path.join(HERE, "rows.json"), encoding="utf-8") as f:
        return json.load(f)


def num(s):
    return float(s.replace(",", ""))


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def read(repo, path):
    with open(os.path.join(repo, path), encoding="utf-8") as f:
        return f.read()


def table_rows(text, header_start):
    """Cells of the rows of the first markdown table whose header line starts with header_start."""
    out, on = [], False
    for ln in text.splitlines():
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


def measure(text, row):
    """{n, d, p, line, quote} or {error}. The same rules as measure() in template.html."""
    path = row["path"]
    if "table" in row:
        rows = table_rows(text, row["table"])
        if not rows:
            return {"error": "table not found (the doc changed)", "path": path}
        n = sum(1 for r in rows if r[-1] == row["match"])
        return {"n": n, "d": len(rows), "p": 100.0 * n / len(rows), "path": path, "line": None,
                "quote": f"{n} of {len(rows)} rows of the table “{row['table']}” end in “{row['match']}”"}
    if "absent" in row:
        n = 0 if row["absent"] in text else 1
        return {"n": n, "d": 1, "p": 100.0 * n, "path": path, "line": None,
                "quote": f"“{row['absent']}” is {'in' if n == 0 else 'no longer in'} the doc"}
    m = re.search(row["regex"], text, re.S)
    if not m:
        return {"error": "pattern not found (the doc changed)", "path": path}
    g = m.groupdict()
    base = {"path": path, "line": line_of(text, m.start()), "quote": re.sub(r"\s+", " ", m.group(0))[:220]}
    if g.get("p"):
        return {**base, "n": None, "d": None, "p": float(g["p"])}
    d = num(g["d"]) if g.get("d") else num(g["n"])
    n = d - num(g["f"]) if g.get("f") else (num(g["n"]) if g.get("n") else d)
    return {**base, "n": n, "d": d, "p": 100.0 * n / d if d else 0.0}


def milestones(text):
    """The same rules as milestones() in template.html."""
    out = []
    for m in re.finditer(r"^\| \*\*(M[\d.]+)\*\* \| ([^|]*) \|[^\n]*$", text, re.M):
        done = re.split(r"(?<!\\)\|", m.group(0))[-2]   # cells may hold escaped pipes (\|)
        state = "partial" if re.search(r"partly met", done, re.I) else "done" if re.search(r"\bmet\b", done, re.I) else "open"
        out.append({"id": m.group(1), "scope": re.sub(r"[`*]", "", m.group(2)).strip()[:180], "state": state,
                    "line": line_of(text, m.start())})
    return out


def isa_from_doc(text, spec):
    m = re.search(spec["isa_doc"]["regex"], text, re.S)
    if not m:
        return None
    t = dict(zip(CLASS_ORDER, (int(m.group(i)) for i in (2, 3, 4, 5))))
    return {"source": spec["isa_doc"]["path"], "from_xml": False, "totals": t, "line": line_of(text, m.start()),
            "cells": [{"name": None, "cls": c} for c in CLASS_ORDER for _ in range(t[c])]}


def isa_from_xml(repo, xml):
    r = subprocess.run([sys.executable, "-I", os.path.join(repo, "tools", "isa_coverage.py"), "--isa", xml, "--json"],
                       capture_output=True, text=True)
    if r.returncode:
        print("isa_coverage.py failed, using docs/isa_coverage.md:\n" + r.stderr[-400:], file=sys.stderr)
        return None
    rep = json.loads(r.stdout)
    cells = sorted(rep["class"].items(), key=lambda kv: (CLASS_ORDER.index(kv[1]), kv[0]))
    return {"source": "tools/isa_coverage.py on " + os.path.basename(xml), "from_xml": True, "totals": rep["totals"],
            "cells": [{"name": k, "cls": v} for k, v in cells], "line": None}


def git_head(repo):
    try:
        r = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%H %cs"], capture_output=True, text=True)
        sha, date = r.stdout.split()
        return sha, date
    except (OSError, ValueError):
        return None, None


def build(repo, xml, local, spec):
    sha, date = git_head(repo)
    overrides = (local or {}).get("rows", {})
    rows = []
    for row in spec["rows"]:
        try:
            r = measure(read(repo, row["path"]), row)
        except OSError as e:
            r = {"error": f"cannot read: {e.strerror}", "path": row["path"]}
        if row["label"] in overrides:
            o = overrides[row["label"]]
            r = {**r, "n": o["n"], "d": o["d"], "p": 100.0 * o["n"] / o["d"] if o["d"] else 0.0,
                 "local": o.get("note", "local measurement"), "error": None}
        rows.append({**r, "label": row["label"], "area": row["area"]})
    isa = (isa_from_xml(repo, xml) if xml else None) or isa_from_doc(read(repo, spec["isa_doc"]["path"]), spec)
    return {"sha": sha, "date": date, "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "milestones": milestones(read(repo, spec["milestones"]["path"])), "rows": rows, "isa": isa,
            "isa_sha": sha}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--isa", help="amdgpu_isa_rdna2.xml (optional)")
    ap.add_argument("--local", help="JSON of local measurements overriding rows")
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--json", action="store_true", help="print the data instead of writing the page")
    a = ap.parse_args()
    spec = load_spec()
    local = json.load(open(a.local, encoding="utf-8")) if a.local else None
    data = build(a.repo, a.isa, local, spec)
    if a.json:
        print(json.dumps(data, indent=1))
        return 0
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    safe = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    page = tpl.replace("/*SPEC*/null", safe(spec)).replace("/*DATA*/null", safe(data))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    bad = [r["label"] for r in data["rows"] if r.get("error")]
    print(f"wrote {a.out} ({len(page):,} bytes) from {data['sha'][:8] if data['sha'] else '?'}"
          + (f"; rows without a source: {', '.join(bad)}" if bad else ""))
    return 0   # a row without a source shows "source not found" on the page instead of failing the build


if __name__ == "__main__":
    sys.exit(main())
