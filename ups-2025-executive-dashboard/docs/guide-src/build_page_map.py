#!/usr/bin/env python3
"""Render the report's page layout to a print-ready HTML page map.

The layout is not transcribed by hand - it is read straight out of
``build_pbit.build_sections()``, the same definition the template generator
uses. That is the point: a page map typed out separately drifts from the build
within a week and then quietly misleads whoever is following it. This one
cannot say anything the layout does not say.

Each report page gets two sheets:

  * a wireframe drawn at 1:1 against the 1280x720 canvas, so a box on the page
    is the size and position of the real visual, and
  * a binding table listing every visual's type, position, size and the exact
    fields in each well, in well order.

Then an appendix: which measures are placed on which page, and which of the
112 are defined but not placed - available for drill-through and ad-hoc use
without having to be found by trial and error.

    python3 docs/guide-src/build_page_map.py out.html
"""
from __future__ import annotations

import collections
import html
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "powerbi"))

import build_pbit as pbit  # noqa: E402

CANVAS_W, CANVAS_H = pbit.CANVAS_W, pbit.CANVAS_H

# Straight from the report theme, so the map reads like the report it maps.
THEME = json.loads((ROOT / "powerbi" / "theme"
                    / "UPS_Executive_Theme.json").read_text(encoding="utf-8"))
DATA_COLOURS = THEME["dataColors"]

# How each visual type is drawn and described. The glyph matters more than it
# looks: a page of identical grey rectangles is unreadable, and the whole value
# of a wireframe is being able to recognise the page shape at a glance.
KIND = {
    "card":                 ("card",   "Card",            "KPI"),
    "multiRowCard":         ("card",   "Multi-row card",  "KPI"),
    "textbox":              ("note",   "Text box",        "Static"),
    "lineChart":            ("chart",  "Line chart",      "Trend"),
    "clusteredBarChart":    ("chart",  "Bar chart",       "Compare"),
    "clusteredColumnChart": ("chart",  "Column chart",    "Compare"),
    "donutChart":           ("chart",  "Donut chart",     "Mix"),
    "tableEx":              ("table",  "Table",           "Detail"),
    "slicer":               ("slicer", "Slicer",          "Control"),
}

# Role names as Power BI labels them in the Visualizations pane, so a reader can
# match a row in the binding table to a well on their screen without guessing.
WELL = {
    "Values": "Values", "Category": "Axis", "Y": "Values", "Y2": "Secondary",
    "Series": "Legend", "Rows": "Rows", "Columns": "Columns",
    "Tooltips": "Tooltips",
}


def unpack(section):
    """Recover the authored intent from a section's serialised containers."""
    out = []
    for vc in section["visualContainers"]:
        cfg = json.loads(vc["config"])
        sv = cfg["singleVisual"]
        vtype = sv["visualType"]
        objects = sv.get("objects", {})

        title, title_measure = None, None
        for block in objects.get("title", []):
            props = block.get("properties", {})
            for expr in props.get("text", []):
                node = expr["expr"]
                if "Literal" in node:
                    title = node["Literal"]["Value"].strip("'").replace("''", "'")
                elif "Measure" in node:
                    title_measure = node["Measure"]["Property"]

        note = None
        if vtype == "textbox":
            paras = objects.get("general", [{}])[0].get("properties", {}) \
                           .get("paragraphs", [])
            note = ["".join(r["value"] for r in p.get("textRuns", []))
                    for p in paras]

        wells = []
        for role, items in sv.get("projections", {}).items():
            wells.append((WELL.get(role, role),
                          [i["queryRef"] for i in items]))

        sort = None
        for ob in sv.get("prototypeQuery", {}).get("OrderBy", []):
            node = ob["Expression"]
            ref = node.get("Measure") or node.get("Column")
            sort = (ref["Property"], "desc" if ob["Direction"] == 2 else "asc")

        out.append({
            "type": vtype, "x": vc["x"], "y": vc["y"],
            "w": vc["width"], "h": vc["height"],
            "title": title, "title_measure": title_measure, "note": note,
            "wells": wells, "sort": sort,
        })
    return out


def pretty(spec):
    """'_Measures.Total Shipments' -> ('Total Shipments', True)."""
    table, name = spec.split(".", 1)
    if table == "_Measures":
        return name, True
    return f"{table}[{name}]", False


def field_html(spec, short=False):
    name, is_measure = pretty(spec)
    cls = "fm" if is_measure else "fc"
    if short and len(name) > 34:
        name = name[:32] + "…"
    return f'<span class="{cls}">{html.escape(name)}</span>'


def paras_html(paras):
    """Text-box paragraphs, kept apart. The first is usually a heading for the
    rest, and running them together makes both unreadable."""
    return "".join(f'<p>{html.escape(p)}</p>' for p in (paras or []) if p)


def glyph(kind, vtype, series=1):
    """A small SVG that says what shape the visual makes, in theme colours.
    `series` is how many measures sit in the value well, so a single-series
    chart is not drawn as if it were split."""
    c = DATA_COLOURS
    if vtype == "lineChart":
        return (f'<svg viewBox="0 0 60 28" preserveAspectRatio="none">'
                f'<polyline points="1,20 12,13 23,17 34,7 45,10 59,3" '
                f'fill="none" stroke="{c[0]}" stroke-width="2.4" vector-effect="non-scaling-stroke"/></svg>')
    if vtype == "clusteredColumnChart":
        bars = "".join(
            f'<rect x="{2 + i * 10}" y="{28 - h}" width="7" height="{h}" '
            f'fill="{c[i % series]}"/>' for i, h in enumerate([14, 20, 11, 24, 17, 9]))
        return f'<svg viewBox="0 0 60 28" preserveAspectRatio="none">{bars}</svg>'
    if vtype == "clusteredBarChart":
        bars = "".join(
            f'<rect x="0" y="{1 + i * 7}" width="{w}" height="5" '
            f'fill="{c[i % series]}"/>' for i, w in enumerate([56, 44, 33, 21]))
        return f'<svg viewBox="0 0 60 28" preserveAspectRatio="none">{bars}</svg>'
    if vtype == "donutChart":
        arcs = ('<circle cx="14" cy="14" r="10" fill="none" stroke="%s" '
                'stroke-width="7" stroke-dasharray="34 29"/>'
                '<circle cx="14" cy="14" r="10" fill="none" stroke="%s" '
                'stroke-width="7" stroke-dasharray="18 45" '
                'stroke-dashoffset="-34"/>'
                '<circle cx="14" cy="14" r="10" fill="none" stroke="%s" '
                'stroke-width="7" stroke-dasharray="11 52" '
                'stroke-dashoffset="-52"/>') % (c[0], c[1], c[2])
        return f'<svg viewBox="0 0 28 28">{arcs}</svg>'
    if kind == "table":
        rows = "".join(
            f'<rect x="0" y="{i * 3.1}" width="60" height="2.1" '
            f'fill="{"#0b0b0b" if i == 0 else "#d5d3cd"}"/>' for i in range(9))
        return f'<svg viewBox="0 0 60 28" preserveAspectRatio="none">{rows}</svg>'
    if kind == "slicer":
        return ('<svg viewBox="0 0 60 28" preserveAspectRatio="none">'
                '<rect x="0" y="10" width="60" height="4" rx="2" fill="#c9c7c1"/>'
                f'<circle cx="38" cy="12" r="7" fill="{DATA_COLOURS[0]}"/></svg>')
    return ""


def wireframe(visuals):
    """The page canvas, drawn 1:1. Every box carries its own index so the
    binding table on the facing sheet can be read against it."""
    boxes = []
    for n, v in enumerate(visuals, 1):
        kind, label, family = KIND.get(v["type"], ("chart", v["type"], ""))
        title = v["title"] or (f'ƒ {v["title_measure"]}'
                               if v["title_measure"] else "")

        fields = [field_html(s, short=True)
                  for _, specs in v["wells"] for s in specs]
        shown, more = fields[:6], len(fields) - 6
        if more > 0:
            shown.append(f'<span class="more">+{more} more</span>')

        # The basis banner row is only 40 px tall. A header bar plus a body
        # does not fit in 40 px, so anything that short collapses to one line
        # and relies on the binding sheet for the detail.
        if v["h"] < 56:
            inner = (f'<div class="bt one"><span class="num">{n}</span>'
                     f'<span class="vt">{html.escape(label)}</span>'
                     f'<span class="ttl">{html.escape(title)}</span>'
                     + (f'<span class="notetext one">'
                        f'{html.escape(" ".join(v["note"] or []))}</span>'
                        if kind == "note" else "".join(shown))
                     + '</div>')
        elif kind == "note":
            inner = (f'<div class="bt"><span class="num">{n}</span>'
                     f'<span class="vt">{html.escape(label)}</span></div>'
                     f'<div class="bb"><div class="notetext">'
                     f'{paras_html(v["note"])}</div></div>')
        else:
            # Fields sit directly under the header where they are read first;
            # the glyph takes whatever height is left, so a tall visual looks
            # tall and the page reads as a dashboard rather than a grid of
            # identical rectangles.
            n_series = max(1, sum(len(s) for w, s in v["wells"]
                                  if w in ("Values", "Legend")))
            g = glyph(kind, v["type"], series=min(n_series, len(DATA_COLOURS)))
            filler = ""
            if kind == "card":
                filler = '<div class="bignum">###</div>'
            elif g:
                filler = f'<div class="glyph">{g}</div>'
            inner = (f'<div class="bt"><span class="num">{n}</span>'
                     f'<span class="vt">{html.escape(label)}</span>'
                     f'<span class="ttl">{html.escape(title)}</span></div>'
                     f'<div class="bb"><div class="fields">{"".join(shown)}'
                     f'</div>{filler}</div>')

        boxes.append(
            f'<div class="box {kind}" style="left:{v["x"]}px;top:{v["y"]}px;'
            f'width:{v["w"]}px;height:{v["h"]}px">{inner}</div>')
    return (f'<div class="canvas" style="width:{CANVAS_W}px;'
            f'height:{CANVAS_H}px">{"".join(boxes)}</div>')


def bindings(visuals):
    rows = []
    for n, v in enumerate(visuals, 1):
        _, label, family = KIND.get(v["type"], ("chart", v["type"], ""))
        title = v["title"] or ""
        if v["title_measure"]:
            title = f'ƒ {v["title_measure"]} (dynamic)'
        if v["type"] == "textbox":
            title = "—"

        if v["type"] == "textbox":
            wells = f'<div class="note-cell">{paras_html(v["note"])}</div>'
        else:
            parts = []
            for well, specs in v["wells"]:
                items = " ".join(field_html(s) for s in specs)
                parts.append(f'<div class="wl"><span class="wn">{well}</span>'
                             f'{items}</div>')
            if v["sort"]:
                parts.append(f'<div class="wl"><span class="wn sortn">Sort</span>'
                             f'<span class="fm">{html.escape(v["sort"][0])}</span>'
                             f'<span class="dir">{v["sort"][1]}</span></div>')
            wells = "".join(parts)

        rows.append(
            f'<tr><td class="c-n">{n}</td>'
            f'<td class="c-t"><b>{html.escape(label)}</b>'
            f'<span class="fam">{family}</span></td>'
            f'<td class="c-p">{v["x"]:.0f}, {v["y"]:.0f}<br>'
            f'<span class="dim">{v["w"]:.0f} × {v["h"]:.0f}</span></td>'
            f'<td class="c-ti">{html.escape(title)}</td>'
            f'<td class="c-w">{wells}</td></tr>')

    return ('<table class="bind"><colgroup>'
            '<col style="width:34px"><col style="width:118px">'
            '<col style="width:86px"><col style="width:250px"><col>'
            '</colgroup><thead><tr>'
            '<th>#</th><th>Visual</th><th>X, Y / size</th><th>Title</th>'
            '<th>Field wells — drop these in this order</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table>')


def measure_index(pages):
    """Every measure the pages use, and every measure they do not."""
    used = collections.defaultdict(set)
    for idx, (name, visuals) in enumerate(pages, 1):
        for v in visuals:
            for _, specs in v["wells"]:
                for s in specs:
                    m, is_measure = pretty(s)
                    if is_measure:
                        used[m].add(idx)
            if v["title_measure"]:
                used[v["title_measure"]].add(idx)

    defined = list(pbit.load_measures())
    by_name = {m["name"]: m for m in defined}

    rows = []
    for name in sorted(used):
        pgs = ", ".join(str(p) for p in sorted(used[name]))
        folder = by_name.get(name, {}).get("displayFolder", "").replace("\\", " \u203a ")
        rows.append(f'<tr><td class="c-m">{html.escape(name)}</td>'
                    f'<td class="c-f">{html.escape(folder)}</td>'
                    f'<td class="c-pg">{pgs}</td></tr>')
    placed = ('<table class="bind idx"><colgroup><col style="width:300px">'
              '<col style="width:210px"><col></colgroup><thead><tr>'
              '<th>Measure</th><th>Display folder</th><th>On page(s)</th>'
              f'</tr></thead><tbody>{"".join(rows)}</tbody></table>')

    spare = [m for m in defined if m["name"] not in used]
    groups = collections.OrderedDict()
    for m in spare:
        groups.setdefault(m.get("displayFolder", "").replace("\\", " \u203a ")
                          or "Other", []).append(m["name"])
    blocks = []
    for folder, names in groups.items():
        items = "".join(f'<span class="fm">{html.escape(n)}</span>'
                        for n in sorted(names))
        blocks.append(f'<div class="sparegrp"><div class="sparehdr">'
                      f'{html.escape(folder)} <span class="ct">{len(names)}</span>'
                      f'</div><div class="sparelist">{items}</div></div>')

    return placed, "".join(blocks), len(used), len(defined)


CSS = """
@page { size: 15in 9in; margin: 0.5in; }
* { box-sizing: border-box; }
body { margin:0; font-family:"Segoe UI",-apple-system,"Helvetica Neue",Arial,
       sans-serif; color:#0b0b0b; background:#fff;
       -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.sheet { width:1344px; height:768px; page-break-after:always;
         position:relative; overflow:hidden; }
.sheet.flow { height:auto; min-height:768px; overflow:visible; }
.sheet:last-child { page-break-after:auto; }

.shead { display:flex; align-items:baseline; gap:12px; height:34px;
         border-bottom:2px solid #0b0b0b; margin-bottom:12px; }
.shead .pn { font-size:19px; font-weight:700; letter-spacing:-.01em; }
.shead .ps { font-size:12.5px; color:#57554f; }
.shead .pr { margin-left:auto; font-size:10.5px; color:#898781;
             text-transform:uppercase; letter-spacing:.09em; }

/* ---- wireframe ---- */
.canvas { position:relative; background:#fcfcfb; border:1px solid #c9c7c1;
          margin:0 auto; }
.box { position:absolute; background:#fff; border:1px solid #c9c7c1;
       border-radius:3px; overflow:hidden; }
.box .bt { display:flex; align-items:center; gap:6px; padding:3px 6px;
           border-bottom:1px solid #e4e2dd; background:#f6f5f2;
           white-space:nowrap; }
.num { display:inline-flex; align-items:center; justify-content:center;
       min-width:15px; height:15px; padding:0 3px; border-radius:3px;
       background:#0b0b0b; color:#fff; font-size:9.5px; font-weight:700; }
.vt { font-size:9px; color:#898781; text-transform:uppercase;
      letter-spacing:.06em; }
.ttl { font-size:10.5px; font-weight:600; overflow:hidden;
       text-overflow:ellipsis; }
.box .bb { padding:5px 6px 7px; display:flex; flex-direction:column; gap:5px;
           height:calc(100% - 22px); }
.glyph { flex:1 1 auto; min-height:22px; max-height:112px; opacity:.8;
         display:flex; align-items:center; }
.glyph svg { height:100%; width:100%; }
.box.donutChart .glyph svg, .glyph svg[viewBox="0 0 28 28"] { width:auto;
         margin:0 auto; }
.bignum { flex:1 1 auto; display:flex; align-items:center;
          font-size:26px; font-weight:700; color:#dcdad4; letter-spacing:.04em; }
.fields { display:flex; flex-wrap:wrap; gap:2px 4px; align-content:flex-start;
          overflow:hidden; flex:none; }
.bt.one { border-bottom:none; height:100%; background:transparent;
          overflow:hidden; }
.bt.one .fm, .bt.one .fc { flex:none; }
.notetext.one { font-size:9px; color:#57554f; overflow:hidden;
                text-overflow:ellipsis; }
.fm, .fc { font-size:9px; line-height:1.35; padding:0 4px; border-radius:2px;
           white-space:nowrap; }
.fm { background:#e7f0fc; color:#14406f; border:1px solid #c6dcf7; }
.fc { background:#f0efec; color:#4a4842; border:1px solid #dddbd5; }
.more { font-size:8.5px; color:#898781; padding:0 3px; }
.notetext { font-size:9.5px; color:#57554f; line-height:1.42; overflow:hidden; }
.notetext p { margin:0 0 5px; }
.notetext p:first-child { font-weight:600; color:#33312c; }
.note-cell p { margin:0 0 4px; }
.note-cell p:first-child { font-style:normal; font-weight:600; }

.box.card { border-color:#c6dcf7; }
.box.card .bt { background:#eef5fd; border-bottom-color:#dbe9fa; }
.box.chart .bt { background:#f4f7fa; }
.box.table .bt { background:#f2f1ee; }
.box.slicer { border-color:#d9d2ee; }
.box.slicer .bt { background:#f1edfa; }
.box.note { border-style:dashed; border-color:#d5d3cd; background:#fbfbf9; }
.box.note .bt { background:transparent; border-bottom:none; padding-bottom:0; }

/* ---- binding table ---- */
table.bind { width:100%; border-collapse:collapse; font-size:10.5px;
             table-layout:fixed; }
table.bind th { text-align:left; font-size:9px; text-transform:uppercase;
                letter-spacing:.08em; color:#57554f; padding:0 8px 5px;
                border-bottom:1.5px solid #0b0b0b; }
table.bind td { padding:5px 8px; border-bottom:1px solid #e8e6e1;
                vertical-align:top; }
table.bind tr:nth-child(even) td { background:#faf9f7; }
.c-n { font-weight:700; color:#fff; }
.c-n { background:#0b0b0b !important; text-align:center; width:34px;
       border-bottom:1px solid #fff !important; }
.c-t .fam { display:block; font-size:9px; color:#898781;
            text-transform:uppercase; letter-spacing:.06em; }
.c-p { font-variant-numeric:tabular-nums; font-size:10px; color:#57554f; }
.c-p .dim { color:#898781; }
.c-ti { font-size:10px; }
.wl { margin-bottom:3px; display:flex; flex-wrap:wrap; gap:3px;
      align-items:baseline; }
.wn { font-size:8.5px; text-transform:uppercase; letter-spacing:.07em;
      color:#898781; min-width:56px; }
.sortn { color:#b26b00; }
.dir { font-size:8.5px; color:#898781; text-transform:uppercase; }
.note-cell { font-size:10px; color:#57554f; font-style:italic; }

/* ---- cover / legend ---- */
.cover { padding-top:120px; }
.eyebrow { font-size:11px; text-transform:uppercase; letter-spacing:.16em;
           color:#898781; }
h1.big { font-size:46px; line-height:1.05; margin:14px 0 0;
         letter-spacing:-.022em; max-width:900px; }
.sub { font-size:16px; color:#57554f; margin-top:14px; max-width:820px;
       line-height:1.5; }
.facts { display:flex; gap:44px; margin-top:44px; padding-top:22px;
         border-top:1px solid #d8d6d0; }
.fact .n { font-size:30px; font-weight:700; letter-spacing:-.02em; }
.fact .l { font-size:11px; color:#898781; text-transform:uppercase;
           letter-spacing:.08em; margin-top:2px; }
.cols { column-count:2; column-gap:46px; }
h2 { font-size:15px; margin:0 0 8px; letter-spacing:-.01em; }
h2.spaced { margin-top:20px; }
p.body { font-size:11.5px; line-height:1.62; color:#33312c; margin:0 0 10px;
         break-inside:avoid; }
ul.body { font-size:11.5px; line-height:1.6; color:#33312c; margin:0 0 10px;
          padding-left:17px; }
ul.body li { margin-bottom:5px; break-inside:avoid; }
.legend { display:flex; gap:26px; flex-wrap:wrap; margin:14px 0 20px; }
.lg { display:flex; align-items:center; gap:7px; font-size:11px; }
.sw { width:26px; height:17px; border-radius:3px; border:1px solid #c9c7c1; }
.toc { font-size:11.5px; width:100%; border-collapse:collapse; }
.toc td { padding:5px 0; border-bottom:1px solid #ebe9e4; }
.toc td.k { width:34px; font-weight:700; }
.toc td.d { color:#57554f; }
.sparegrp { break-inside:avoid; margin-bottom:11px; }
.sparehdr { font-size:10px; text-transform:uppercase; letter-spacing:.07em;
            color:#57554f; margin-bottom:4px; border-bottom:1px solid #e8e6e1;
            padding-bottom:2px; }
.sparehdr .ct { color:#898781; }
.sparelist { display:flex; flex-wrap:wrap; gap:3px; }
.warn { border-left:3px solid #b26b00; background:#fdf6ea; padding:9px 12px;
        font-size:11px; line-height:1.55; color:#4a3c22; margin:12px 0;
        break-inside:avoid; }
.foot { position:absolute; bottom:0; left:0; right:0; font-size:9.5px;
        color:#a9a7a1; display:flex; justify-content:space-between; }
"""


def sheet(head_num, head_name, right, body, flow=False):
    """`flow=True` lets the sheet paginate instead of clipping. Only the
    wireframe needs a fixed 768 px canvas; a table that silently loses its last
    row off the bottom edge is worse than a longer document."""
    return (f'<div class="sheet{" flow" if flow else ""}"><div class="shead">'
            f'<span class="pn">{html.escape(head_num)}</span>'
            f'<span class="ps">{html.escape(head_name)}</span>'
            f'<span class="pr">{html.escape(right)}</span></div>'
            f'{body}</div>')


def build():
    sections = pbit.build_sections()
    pages = [(s["displayName"], unpack(s)) for s in sections]
    placed_tbl, spare_html, n_used, n_defined = measure_index(pages)
    n_visuals = sum(len(v) for _, v in pages)

    out = [f"<style>{CSS}</style>"]

    # --- cover ---
    toc = "".join(
        f'<tr><td class="k">{i}</td><td>{html.escape(name.split(" ", 1)[1])}</td>'
        f'<td class="d">{len(v)} visuals</td></tr>'
        for i, (name, v) in enumerate(pages, 1))
    out.append(
        '<div class="sheet"><div class="cover">'
        '<div class="eyebrow">UPS 2025 Executive Dashboard</div>'
        '<h1 class="big">Page map and measure placement</h1>'
        '<div class="sub">Every report page drawn to scale against the '
        '1280 &times; 720 canvas, with the exact field wells behind each '
        'visual. Generated from the layout definition itself, not written '
        'alongside it.</div>'
        f'<div class="facts">'
        f'<div class="fact"><div class="n">{len(pages)}</div>'
        f'<div class="l">Report pages</div></div>'
        f'<div class="fact"><div class="n">{n_visuals}</div>'
        f'<div class="l">Visuals</div></div>'
        f'<div class="fact"><div class="n">{n_used}</div>'
        f'<div class="l">Measures placed</div></div>'
        f'<div class="fact"><div class="n">{n_defined}</div>'
        f'<div class="l">Measures defined</div></div></div>'
        f'<table class="toc" style="margin-top:40px;max-width:620px">{toc}</table>'
        '</div></div>')

    # --- how to read ---
    lg = lambda cls, txt: (f'<div class="lg"><span class="sw" style="'
                           f'{cls}"></span>{txt}</div>')
    out.append(sheet("How to read this", "", "Conventions", flow=True, body=f'''
      <div class="legend">
        {lg("background:#eef5fd;border-color:#c6dcf7", "Card / KPI")}
        {lg("background:#f4f7fa", "Chart")}
        {lg("background:#f2f1ee", "Table")}
        {lg("background:#f1edfa;border-color:#d9d2ee", "Slicer")}
        {lg("background:#fbfbf9;border-style:dashed", "Text box (static)")}
        <div class="lg"><span class="fm">Measure</span>
          <span class="fc">Table[Column]</span></div>
      </div>
      <div class="cols">
        <h2>The wireframe is 1:1</h2>
        <p class="body">Boxes are drawn at the exact X, Y, width and height the
        visual takes on the report canvas. Power BI&rsquo;s canvas is 1280
        &times; 720 at 16:9, so a box measuring 620 &times; 320 here is 620
        &times; 320 there. Set <b>View &rarr; Page view &rarr; Actual size</b>
        and the two match.</p>
        <p class="body">You do not have to place anything by eye. Select a
        visual, open the <b>Format</b> pane, expand <b>General &rarr;
        Properties &rarr; Size</b> and <b>Position</b>, and type the four
        numbers from the binding sheet. That is faster than dragging and it is
        the only way the pages line up with each other.</p>

        <h2 class="spaced">Field wells are ordered</h2>
        <p class="body">Fields are listed in the order they must be dropped.
        For a table the order is the column order left to right. For a chart
        with two series, the order sets which one draws first and therefore
        which colour it takes from the theme. Dropping them in a different
        order gives a different-looking report.</p>
        <p class="body">Blue chips are measures &mdash; all of them live in the
        <b>_Measures</b> table. Grey chips are columns, shown as
        <b>Table[Column]</b>.</p>

        <h2 class="spaced">Titles marked &fnof; are measure-driven</h2>
        <p class="body">A handful of titles are bound to a measure rather than
        typed. Set them under <b>Format &rarr; General &rarr; Title &rarr;
        Text &rarr; fx &rarr; Field value</b> and pick the named measure. These
        titles restate the filters in force, so a screenshot of a filtered page
        cannot be read as an annual number.</p>

        <h2 class="spaced">Every page carries the basis banner</h2>
        <p class="body">Visual 1 on every page is the same card, bound to
        <b>Data Basis Banner</b>, and visual 2 is a static note specific to
        that page. Build them once, then copy the pair onto each new page
        before anything else &mdash; they occupy the top 48 px and everything
        else is positioned below them.</p>

        <div class="warn"><b>Reliability rests on one month.</b> On-time
        delivery is 40% of the recommendation score, and Time-in-Transit
        currently covers March only. The banner says so on screen. Treat every
        OTD figure as provisional until a second month is loaded &mdash; the
        December extract has a transit tab and would be the one to add.</div>
      </div>'''))

    # --- per page ---
    for i, (name, visuals) in enumerate(pages, 1):
        label = name.split(" ", 1)[1]
        out.append(sheet(f"Page {i}", label,
                         f"Layout — {len(visuals)} visuals",
                         wireframe(visuals)))
        out.append(sheet(f"Page {i}", label, "Field wells",
                         bindings(visuals), flow=True))

    # --- appendix ---
    out.append(sheet("Appendix A", "Measures placed on the canvas",
                     f"{n_used} of {n_defined}",
                     '<div style="column-count:2;column-gap:40px">'
                     + placed_tbl + '</div>', flow=True))
    out.append(sheet("Appendix B", "Measures defined but not placed",
                     f"{n_defined - n_used} available",
                     '<p class="body" style="max-width:1000px">These are built '
                     'by the model and ready to use, but no visual references '
                     'them. They exist for drill-through pages, tooltip pages, '
                     'and the ad-hoc questions that follow a leadership '
                     'meeting &mdash; a reader can drag any of them onto a new '
                     'visual without writing DAX. Nothing here is dead weight: '
                     'several are intermediate steps the placed measures '
                     'depend on.</p>'
                     '<div style="column-count:3;column-gap:34px;'
                     'margin-top:14px">' + spare_html + '</div>', flow=True))

    return "\n".join(out)


def main():
    dest = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else "/tmp/page_map.html")
    doc = ("<!doctype html><html><head><meta charset=\"utf-8\">"
           "<title>UPS 2025 Executive Dashboard - Page Map</title></head>"
           "<body>" + build() + "</body></html>")
    dest.write_text(doc, encoding="utf-8")
    print(f"Wrote {dest} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
