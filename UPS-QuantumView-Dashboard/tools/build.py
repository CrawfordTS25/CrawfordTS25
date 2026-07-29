#!/usr/bin/env python3
"""
Rebuild the Report layer of Quantum_View_Exceptions_Dashboard.pbix so that all five
pages share one identical skeleton (title/nav bar, KPI band, filter rail) and one set
of component styles, per UPS_QuantumView_Master_Build_Spec.pdf p.5 (theme tokens),
p.6 (master coordinate table) and p.7 (card anatomy).

Only Report/definition/** is rewritten.  DataModel, Connections, Settings, Metadata,
DAXQueries, TMDLScripts, StaticResources and docProps are copied through byte-for-byte.
"""
import json, os, shutil, zipfile, copy, hashlib

SRC = os.path.dirname(os.path.abspath(__file__))
EXTRACTED = os.path.join(SRC, 'pbix', 'extracted')
BUILD = os.path.join(SRC, 'pbix', 'build')
PAGES_SRC = os.path.join(EXTRACTED, 'Report', 'definition', 'pages')
PAGES_DST = os.path.join(BUILD, 'Report', 'definition', 'pages')

VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# ---------------------------------------------------------------- design tokens
INK      = '#1F2D40'   # title bar, table headers, filter rail, primary text & bars
ACCENT   = '#F2A900'   # KPI top bars, active tab, primary buttons
BREACH   = '#D64545'   # aging > SLA, breach, OPEN escalation
WIP      = '#E8A13A'   # in-progress
RESOLVED = '#2F9E6F'   # resolved / positive
EMAIL    = '#7C5CBF'   # mail-merge / automation
BORDER   = '#E4E6EA'   # panel hairline (theme visualStyles border)
LABEL    = '#5A6472'   # KPI card label
WHITE    = '#FFFFFF'
SEMIBOLD_V = "'''Segoe UI Semibold'', wf_segoe-ui_semibold, helvetica, arial, sans-serif'"
REGULAR_V  = "'Segoe UI'"

# ---------------------------------------------------------------- shared geometry
BAR       = (24, 24, 1232, 44)      # title & nav bar        (spec p.6)
PAGETITLE = (40, 33, 344, 26)
NAV       = (396, 30, 456, 32)
STAMP     = (868, 27, 372, 38)
KPI_Y, KPI_W, KPI_H = 76, 232, 78   # KPI card band          (spec p.6/p.7)
KPI_X     = [24, 274, 524, 774, 1024]
RAIL      = (24, 162, 150, 534)     # filter rail            (spec p.6)
RAILHDR   = (36, 174, 126, 16)
SLICER_X, SLICER_W, SLICER_H = 36, 126, 56
SLICER_Y  = [196, 264, 332, 400, 468]
BACKBTN   = (36, 196, 126, 40)

# work area: x 186 -> 1256, y 162 -> 696
R1L = (186, 162, 525, 165)
R1R = (723, 162, 533, 165)
R1F = (186, 162, 1070, 165)
R2L = (186, 339, 525, 150)
R2R = (723, 339, 533, 150)
R2F = (186, 339, 1070, 150)
R3F = (186, 501, 1070, 195)
# Resolution work area (spec p.6, authoritative over the mockup callouts)
QUEUE = (186, 162, 452, 470)
NOTES = (650, 162, 452, 236)
AUTO  = (650, 410, 452, 222)

Z_RAIL, Z_BAR, Z_RAILHDR, Z_TITLE, Z_NAV, Z_STAMP = 100, 200, 300, 400, 500, 600
Z_KPI, Z_SLICER, Z_WORK = 1000, 1100, 2000

# ---------------------------------------------------------------- expr helpers
def lit(v):        return {"expr": {"Literal": {"Value": v}}}
def sv(v):         return lit("'%s'" % v)
def bv(v):         return lit("true" if v else "false")
def dv(v):         return lit("%sD" % v)
def lv(v):         return lit("%sL" % v)
def col(h):        return {"solid": {"color": {"expr": {"Literal": {"Value": "'%s'" % h}}}}}
def theme(i, p=0):  return {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": i, "Percent": p}}}}}
SEMIBOLD = lit(SEMIBOLD_V)
REGULAR  = lit(REGULAR_V)

def grp(props, selector=None):
    e = {"properties": props}
    if selector: e["selector"] = selector
    return [e]

def entity_col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def entity_measure(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
def entity_agg(entity, prop, fn):
    return {"Aggregation": {"Expression": entity_col(entity, prop), "Function": fn}}

AGG_MIN, AGG_MAX, AGG_COUNTNONNULL = 2, 3, 5

_ids = set()
def new_id(seed):
    """Deterministic 20-char lowercase hex id, matching the file's existing id shape."""
    h = hashlib.sha1(('qv-skeleton::' + seed).encode()).hexdigest()[:20]
    assert h not in _ids, seed
    _ids.add(h)
    return h

# ---------------------------------------------------------------- templates
def tpl(page, vid):
    with open(os.path.join(PAGES_SRC, page, 'visuals', vid, 'visual.json')) as f:
        return json.load(f)

P1, P2, P3, P4, P5 = ('36b05998ad2a58e00312', '8db06a7e73968141bad0',
                      '653efd92bd7e39c1655a', 'df8b223ceb15c751a185',
                      '59c21ff6d2b785b053b2')

T_SHAPE  = tpl(P1, '4da0197c9b15e9fcdee3')
T_NAV    = tpl(P1, 'a3bef9a088c640cac9a5')
T_CARD   = tpl(P2, 'fc07cf5e3aa2329fc5b4')
T_SLICER = tpl(P1, 'cffbba7ded6e5178b6c8')
T_TEXT   = tpl(P2, 'e875e461e9d0dbea1eba')
T_BTN    = tpl(P4, '79c52cc25902bb5aae7b')
T_TABLE  = tpl(P1, '2c1e56f341d91febe543')

def base(template, vid, rect, z):
    v = copy.deepcopy(template)
    v["$schema"] = VC_SCHEMA
    v["name"] = vid
    v["position"] = {"x": rect[0], "y": rect[1], "z": z,
                     "width": rect[2], "height": rect[3], "tabOrder": z}
    v.pop("filterConfig", None)
    return v

# ---------------------------------------------------------------- shared styling
def panel_chrome(v, title=None, radius=8, bg=WHITE, border=True):
    """Identical container chrome for every work-area panel on every page."""
    vco = {}
    v["visual"]["visualContainerObjects"] = vco
    if title is None:
        vco["title"] = grp({"show": bv(False)})
    else:
        vco["title"] = grp({
            "show": bv(True), "text": sv(title), "titleWrap": bv(False),
            "fontSize": lit("'11'"), "fontFamily": SEMIBOLD,
            "fontColor": col(INK), "alignment": sv('left'),
            "background": col(WHITE),
        })
    vco["background"] = grp({"show": bv(True), "color": col(bg), "transparency": dv(0)})
    if border:
        vco["border"] = grp({"show": bv(True), "color": col(BORDER),
                             "radius": dv(radius), "width": dv(1)})
    else:
        vco["border"] = grp({"show": bv(False)})
    vco["dropShadow"] = grp({"show": bv(False)})
    vco["visualHeader"] = grp({"show": bv(False)})
    for k in ("subTitle", "visualTooltip", "visualHeaderTooltip"):
        vco[k] = grp({"fontSize": lit("'10'"), "fontFamily": REGULAR})
    vco["divider"] = grp({"color": col(INK)})
    return v

# ---------------------------------------------------------------- skeleton parts
def make_title_bar(vid):
    v = base(T_SHAPE, vid, BAR, Z_BAR)
    v["visual"]["objects"] = {
        "shape": grp({"tileShape": sv('rectangleRoundedByPixel')}),
        "rotation": grp({"shapeAngle": lv(0)}),
        "fill": [{"properties": {"show": bv(True)}},
                 {"properties": {"fillColor": col(INK), "transparency": dv(0)},
                  "selector": {"id": "default"}}],
        "outline": grp({"show": bv(False)}),
        "text": grp({"show": bv(False)}),
    }
    panel_chrome(v, title=None, bg=INK, border=False)
    v["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})
    return v

def make_rail_panel(vid):
    v = base(T_SHAPE, vid, RAIL, Z_RAIL)
    v["visual"]["objects"] = {
        "shape": grp({"tileShape": sv('rectangleRoundedByPixel')}),
        "rotation": grp({"shapeAngle": lv(0)}),
        "fill": [{"properties": {"show": bv(True)}},
                 {"properties": {"fillColor": col(WHITE), "transparency": dv(0)},
                  "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": bv(True)}},
                    {"properties": {"lineColor": col(BORDER), "weight": lv(1),
                                    "transparency": dv(0)},
                     "selector": {"id": "default"}}],
        "text": grp({"show": bv(False)}),
    }
    panel_chrome(v, title=None, border=False)
    v["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})
    return v

def make_textbox(vid, rect, z, runs):
    v = base(T_TEXT, vid, rect, z)
    v["visual"]["objects"] = {"general": grp({"paragraphs": runs})}
    v["visual"]["visualContainerObjects"] = {"title": grp({"show": bv(False)})}
    return v

def run(text, size, color_hex, bold=False, font="Segoe UI Semibold", align="left"):
    return {"horizontalTextAlignment": align, "textRuns": [{
        "value": text,
        "textStyle": {"fontSize": "%dpt" % size, "color": color_hex,
                      "fontWeight": "bold" if bold else "normal",
                      "fontFamily": font}}]}

def make_page_title(vid, text):
    return make_textbox(vid, PAGETITLE, Z_TITLE,
                        [run(text, 11, WHITE, True)])

def make_rail_header(vid, text):
    return make_textbox(vid, RAILHDR, Z_RAILHDR,
                        [run(text, 7, LABEL, True)])

def make_nav(vid):
    v = base(T_NAV, vid, NAV, Z_NAV)
    v["visual"]["objects"] = {
        "fill": [{"properties": {"show": bv(True)}},
                 {"properties": {"fillColor": col(INK), "transparency": dv(0)},
                  "selector": {"id": "default"}},
                 {"properties": {"fillColor": col(ACCENT), "transparency": dv(0)},
                  "selector": {"id": "selected"}}],
        "outline": grp({"show": bv(False)}),
        "text": [{"properties": {"show": bv(True)}},
                 {"properties": {"fontColor": col(WHITE), "fontSize": dv(9),
                                 "fontFamily": SEMIBOLD},
                  "selector": {"id": "default"}},
                 {"properties": {"fontColor": col(INK)}, "selector": {"id": "selected"}}],
        "pages": grp({"showHiddenPages": bv(False)}),
    }
    panel_chrome(v, title=None, border=False)
    v["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})
    return v

def make_stamp(vid):
    """'DATA AS OF' chip in the title bar - the last-refresh element of the skeleton."""
    v = base(T_CARD, vid, STAMP, Z_STAMP)
    v["visual"]["query"] = {"queryState": {"Data": {"projections": [{
        "field": entity_agg("QV_Output", "Date modified", AGG_MAX),
        "queryRef": "Max(QV_Output.Date modified)",
        "nativeQueryRef": "DATA AS OF",
    }]}}}
    o = v["visual"]["objects"]
    o["label"] = grp({"show": bv(True), "heading": sv('Heading3'),
                      "fontFamily": SEMIBOLD, "fontSize": dv(7),
                      "fontColor": col(BORDER), "position": sv('aboveValue'),
                      "transparency": dv(0), "textWrap": bv(False)},
                     {"id": "default"})
    o["value"] = grp({"fontFamily": SEMIBOLD, "fontSize": dv(11), "bold": bv(True),
                      "fontColor": col(WHITE), "horizontalAlignment": sv('right'),
                      "textWrap": bv(False)}, {"id": "default"})
    o["accentBar"] = grp({"show": bv(False)}, {"id": "default"})
    o["fillCustom"] = grp({"show": bv(False)})
    o["outline"] = grp({"show": bv(False)}, {"id": "default"})
    o["shadowCustom"] = grp({"show": bv(False)}, {"id": "default"})
    o["divider"] = grp({"show": bv(False)}, {"id": "default"})
    panel_chrome(v, title=None, border=False)
    v["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})
    return v

def make_back_button(vid, text):
    v = base(T_BTN, vid, BACKBTN, Z_SLICER)
    v["visual"]["objects"] = {
        "icon": grp({"shapeType": sv('back'), "lineColor": col(INK)}, {"id": "default"}),
        "outline": grp({"show": bv(True), "lineColor": col(BORDER), "weight": lv(1)},
                       {"id": "default"}),
        "fill": grp({"show": bv(True), "fillColor": col(WHITE), "transparency": dv(0)},
                    {"id": "default"}),
        "text": grp({"show": bv(True), "text": sv(text), "fontColor": col(INK),
                     "fontSize": dv(8), "fontFamily": SEMIBOLD,
                     "horizontalAlignment": sv('center')}, {"id": "default"}),
        "shape": grp({"tileShape": sv('rectangleRoundedByPixel'), "roundedRectRadius": dv(8)}),
    }
    v["visual"]["visualContainerObjects"] = {
        "visualLink": grp({"show": bv(True), "type": sv('Back')}),
        "title": grp({"show": bv(False), "text": sv(text)}),
    }
    return v

# ---------------------------------------------------------------- KPI cards
def make_card(vid, idx, label, field, accent, query_ref, vfilters=None):
    """One identical KPI tile; only the value, label and accent-bar token change."""
    v = base(T_CARD, vid, (KPI_X[idx], KPI_Y, KPI_W, KPI_H), Z_KPI + idx)
    v["visual"]["query"] = {"queryState": {"Data": {"projections": [{
        "field": field, "queryRef": query_ref, "nativeQueryRef": label,
    }]}}}
    o = v["visual"]["objects"]
    # spec p.7 card anatomy: label 9px uppercase #5A6472 w700, 4px top accent bar
    o["label"] = grp({"show": bv(True), "heading": sv('Heading3'),
                      "fontFamily": SEMIBOLD, "fontSize": dv(9),
                      "fontColor": col(LABEL), "position": sv('aboveValue'),
                      "transparency": dv(0), "textWrap": bv(True)},
                     {"id": "default"})
    o["value"] = grp({"fontFamily": SEMIBOLD, "fontSize": dv(24), "bold": bv(True),
                      "fontColor": col(INK), "horizontalAlignment": sv('left'),
                      "textWrap": bv(True)}, {"id": "default"})
    o["accentBar"] = grp({"show": bv(True), "position": sv('Top'),
                          "color": col(accent), "width": dv(4)}, {"id": "default"})
    o["fillCustom"] = grp({"show": bv(False)})
    o["outline"] = grp({"show": bv(False)}, {"id": "default"})
    o["shadowCustom"] = grp({"show": bv(False)}, {"id": "default"})
    o["divider"] = grp({"show": bv(False)}, {"id": "default"})
    o["shapeCustomRectangle"] = grp({"tileShape": sv('rectangleRoundedByPixel')},
                                    {"id": "default"})
    o["spacing"] = grp({"verticalSpacing": lv(1)}, {"id": "default"})
    o["layout"] = [
        {"properties": {"alignment": sv('top'), "orientation": dv(2), "columnCount": lv(10),
                        "cellPadding": lv(12), "style": sv('Cards'),
                        "showFixedSize": bv(False), "autoGrid": bv(True)}},
        {"properties": {"backgroundShow": bv(False), "paddingUniform": lv(12),
                        "paddingIndividual": bv(True)}, "selector": {"id": "default"}},
    ]
    o["referenceLabelLayout"] = grp({"position": sv('right')}, {"id": "default"})
    panel_chrome(v, title=None)
    if vfilters:
        v["filterConfig"] = {"filters": vfilters, "filterSortOrder": "Custom"}
    return v

def adv_filter(name, ordinal, entity, prop, comparison, value_literal):
    """Visual-level Advanced filter, same shape the file already uses on the trace cards."""
    return {
        "name": name, "ordinal": ordinal,
        "field": entity_col(entity, prop),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "c", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {
                "ComparisonKind": comparison,
                "Left": {"Column": {"Expression": {"SourceRef": {"Source": "c"}},
                                    "Property": prop}},
                "Right": {"Literal": {"Value": value_literal}}}}}],
        },
        "howCreated": "User",
    }

# ---------------------------------------------------------------- slicers
def make_slicer(vid, idx, label, entity, prop):
    v = base(T_SLICER, vid, (SLICER_X, SLICER_Y[idx], SLICER_W, SLICER_H), Z_SLICER + idx)
    v["visual"]["query"] = {"queryState": {"Values": {"projections": [{
        "field": entity_col(entity, prop),
        "queryRef": "%s.%s" % (entity, prop),
        "nativeQueryRef": label,
        "active": True,
    }]}}}
    v["visual"]["objects"] = {
        "data": grp({"mode": sv('Dropdown')}),
        "header": grp({"show": bv(True), "textSize": dv(8), "fontFamily": SEMIBOLD,
                       "fontColor": col(LABEL), "bold": bv(True),
                       "background": col(WHITE), "outline": sv('None')}),
        "items": grp({"background": col(WHITE), "fontColor": col(INK),
                      "textSize": dv(8), "padding": dv(2),
                      "fontFamily": REGULAR, "outline": sv('None')}),
        "selection": grp({"selectAllCheckboxEnabled": bv(True),
                          "singleSelect": bv(False), "strictSingleSelect": bv(False)}),
        "pendingChangesIcon": grp({"show": bv(False)}),
    }
    panel_chrome(v, title=None, border=False)
    v["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})
    return v

# ---------------------------------------------------------------- work-area panels
def place(template, vid, rect, z, title):
    v = base(template, vid, rect, z)
    panel_chrome(v, title=title)
    return v

def style_bar_chart(v, fill=INK):
    o = {}
    v["visual"]["objects"] = o
    o["categoryAxis"] = grp({"show": bv(True), "showAxisTitle": bv(False),
                             "labelColor": col(INK), "fontSize": dv(8),
                             "fontFamily": SEMIBOLD, "concatenateLabels": bv(False),
                             "innerPadding": lv(20), "switchAxisPosition": bv(False)})
    o["valueAxis"] = grp({"show": bv(False), "showAxisTitle": bv(False),
                          "gridlineShow": bv(False), "labelColor": col(INK),
                          "fontSize": dv(8), "fontFamily": SEMIBOLD,
                          "labelPrecision": lv(0), "start": dv(0)})
    o["dataPoint"] = grp({"fill": col(fill), "borderShow": bv(False)})
    o["labels"] = grp({"show": bv(True), "color": col(INK), "fontSize": dv(8),
                       "fontFamily": SEMIBOLD, "labelPrecision": lv(0)})
    return v

def style_area_chart(v):
    o = {}
    v["visual"]["objects"] = o
    o["categoryAxis"] = grp({"show": bv(True), "gridlineShow": bv(False),
                             "labelColor": col(INK), "fontSize": dv(8),
                             "fontFamily": SEMIBOLD})
    o["valueAxis"] = grp({"show": bv(False), "showAxisTitle": bv(False),
                          "gridlineShow": bv(False), "labelColor": col(INK),
                          "fontSize": dv(8)})
    o["dataPoint"] = grp({"fill": col(INK)})
    o["lineStyles"] = grp({"areaShow": bv(True), "areaMatchStrokeColor": bv(False),
                           "areaColor": col(ACCENT), "strokeWidth": lv(2),
                           "lineColor": col(INK)})
    o["labels"] = grp({"show": bv(False)})
    o["seriesLabels"] = grp({"show": bv(False)})
    return v

def style_table(v, web_url_on=None, web_url_entity=None, web_url_col=None):
    o = {}
    v["visual"]["objects"] = o
    values = [{"properties": {"fontSize": dv(9), "fontFamily": REGULAR,
                              "fontColor": col(INK),
                              "backColorPrimary": col(WHITE),
                              "backColorSecondary": col('#F7F8F9'),
                              "urlIcon": bv(False)}}]
    if web_url_on:
        values.append({
            "properties": {"webURL": {"expr": {"Aggregation": {
                "Expression": entity_col(web_url_entity, web_url_col),
                "Function": AGG_MAX}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                         "metadata": web_url_on},
        })
    o["values"] = values
    o["columnHeaders"] = grp({"fontSize": dv(9), "fontFamily": SEMIBOLD,
                              "fontColor": col(WHITE), "backColor": col(INK),
                              "alignment": sv('left'), "wordWrap": bv(True),
                              "autoSizeColumnWidth": bv(True)})
    o["grid"] = grp({"rowPadding": dv(4), "gridVertical": bv(False),
                     "gridHorizontal": bv(True), "gridHorizontalColor": col(BORDER),
                     "outlineColor": col(BORDER), "outlineWeight": dv(1)})
    o["total"] = grp({"totals": bv(False)})
    return v

def table_projections(pairs):
    return {"queryState": {"Values": {"projections": [
        {"field": entity_col(e, p), "queryRef": "%s.%s" % (e, p), "nativeQueryRef": n}
        for (e, p, n) in pairs]}}}

# ---------------------------------------------------------------- page assembly
PAGE_OBJECTS = {
    "outspacePane": grp({"width": lv(189), "titleSize": lv(10)}),
    "background": grp({"color": theme(0, -0.2),
                       "image": {"image": {"name": lit("''"), "url": lit("''")}},
                       "transparency": dv(0)}),
    "filterCard": grp({"fontFamily": SEMIBOLD, "border": bv(False),
                       "inputBoxColor": theme(0, 0)}, {"id": "Available"}),
    "outspace": grp({"image": {"image": {"name": lit("''"), "url": lit("''")}},
                     "transparency": dv(0)}),
}

def write_page(page_name, display_name, visuals, page_extra=None):
    pdir = os.path.join(PAGES_DST, page_name)
    vdir = os.path.join(pdir, 'visuals')
    if os.path.isdir(vdir):
        shutil.rmtree(vdir)
    os.makedirs(vdir, exist_ok=True)
    page = {"$schema": PAGE_SCHEMA, "name": page_name, "displayName": display_name,
            "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": copy.deepcopy(PAGE_OBJECTS)}
    if page_extra:
        page.update(page_extra)
    with open(os.path.join(pdir, 'page.json'), 'w', encoding='utf-8') as f:
        json.dump(page, f, indent=2)
    seen = set()
    for v in visuals:
        assert v["name"] not in seen, (page_name, v["name"])
        seen.add(v["name"])
        d = os.path.join(vdir, v["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'visual.json'), 'w', encoding='utf-8') as f:
            json.dump(v, f, indent=2)
    return len(visuals)


def skeleton(page_key, title_text, rail_header, ids):
    """The four-part chrome that is byte-identical (bar geometry, nav, rail) on every page."""
    return [
        make_rail_panel(ids['rail']),
        make_title_bar(ids['bar']),
        make_rail_header(ids['railhdr'], rail_header),
        make_page_title(ids['pagetitle'], title_text),
        make_nav(ids['nav']),
        make_stamp(ids['stamp']),
    ]

def skel_ids(page_key):
    return {k: new_id('%s/%s' % (page_key, k))
            for k in ('rail', 'bar', 'railhdr', 'pagetitle', 'nav', 'stamp')}


# ================================================================= PAGE 1
def build_p1():
    ids = skel_ids('p1')
    ids['bar'] = '4da0197c9b15e9fcdee3'      # keep the original bar / nav ids
    ids['nav'] = 'a3bef9a088c640cac9a5'
    ids['rail'] = '4a35913fbc6f170b4401'
    vis = skeleton('p1', 'UPS QUANTUM VIEW  ·  EXCEPTIONS', 'FILTERS', ids)

    # spec p.7 accents: Total Ink · Rate Breach · Shipments Ink · <green> · <amber>
    vis += [
        make_card('91dc8596a6a3e77d9a7f', 0, 'TOTAL EXCEPTIONS',
                  entity_measure('QV_Output', 'Total Exceptions'), INK,
                  'QV_Output.Total Exceptions'),
        make_card('8dbf7ab199138b09a595', 1, 'EXCEPTION RATE',
                  entity_measure('QV_Output', 'Exception Rate'), BREACH,
                  'QV_Output.Exception Rate'),
        make_card('657395733f2a0ff045ca', 2, 'TOTAL SHIPMENTS',
                  entity_measure('QV_Output', 'Total Shipments'), INK,
                  'QV_Output.Total Shipments'),
        make_card(new_id('p1/card-successful'), 3, 'SUCCESSFUL SHIPMENTS',
                  entity_measure('QV_Output', 'Successful Shipments'), RESOLVED,
                  'QV_Output.Successful Shipments'),
        make_card('9884e2f3edafbda08b7c', 4, 'AGED 8+ DAYS',
                  entity_measure('Resolutions Table', 'Aged 8 Plus Days'), ACCENT,
                  'Resolutions Table.Aged 8 Plus Days'),
    ]
    vis += [
        make_slicer('cffbba7ded6e5178b6c8', 0, 'EXCEPTION CATEGORY', 'QV_Output', 'Exception Category'),
        make_slicer(new_id('p1/slicer-exctype'), 1, 'EXCEPTION TYPE', 'QV_Output', 'Exception Type '),
        make_slicer('971aec585965e35d1d2a', 2, 'RUN TYPE', 'QV_Output', 'Run Time'),
        make_slicer('17930b0a22d5e0a60080', 3, 'SHIPPER LOCATION', 'QV_Output', 'Shipper Location'),
        make_slicer('d872338a678c76aa123c', 4, 'RUN DATE', 'QV_Output', 'Run Date'),
    ]

    c1 = style_bar_chart(place(tpl(P1, '1464f7f7b0a80df1e45b'), '1464f7f7b0a80df1e45b',
                               R1L, Z_WORK, 'Exceptions by Category'))
    c2 = style_bar_chart(place(tpl(P1, '440cc3a8f7f81d9c576c'), '440cc3a8f7f81d9c576c',
                               R1R, Z_WORK + 1, 'Exceptions by Service'))
    c3 = style_bar_chart(place(tpl(P1, 'c62f0b0a1aec5c80209a'), 'c62f0b0a1aec5c80209a',
                               R2L, Z_WORK + 2, 'Exceptions by QV Run Window'))
    c4 = style_area_chart(place(tpl(P1, 'd93bc956c906aebdc346'), 'd93bc956c906aebdc346',
                                R2R, Z_WORK + 3, 'Exceptions Trend'))
    tbl = place(tpl(P1, '2c1e56f341d91febe543'), '2c1e56f341d91febe543',
                R3F, Z_WORK + 4, 'Exception Detail  ·  click a Tracking Number to open UPS tracking')
    style_table(tbl, web_url_on='QV_Output.Tracking Number',
                web_url_entity='QV_Output', web_url_col='Tracking URL')
    tbl["visual"]["query"] = table_projections([
        ('QV_Output', 'Exception Type ', 'Exception Type'),
        ('QV_Output', 'Tracking Number', 'Tracking Number'),
        ('QV_Output', 'Service', 'Service'),
        ('QV_Output', 'Manifest Date', 'Manifest Date'),
        ('QV_Output', 'Shipper Name', 'Shipper Name'),
        ('QV_Output', 'Shipper Location', 'Shipper Location'),
        ('QV_Output', 'Ship To Name', 'Ship To'),
        ('QV_Output', 'Exception Description', 'Issue'),
        ('QV_Output', 'Recommended Action', 'Recommended Action'),
    ])
    vis += [c1, c2, c3, c4, tbl]

    extra = {"visualInteractions": [
        {"source": "c62f0b0a1aec5c80209a", "target": "d93bc956c906aebdc346", "type": "NoFilter"},
        {"source": "d93bc956c906aebdc346", "target": "c62f0b0a1aec5c80209a", "type": "DataFilter"},
        {"source": "d93bc956c906aebdc346", "target": "1464f7f7b0a80df1e45b", "type": "HighlightFilter"},
        {"source": "440cc3a8f7f81d9c576c", "target": "1464f7f7b0a80df1e45b", "type": "DataFilter"},
        {"source": "1464f7f7b0a80df1e45b", "target": "440cc3a8f7f81d9c576c", "type": "DataFilter"},
        {"source": "1464f7f7b0a80df1e45b", "target": "d93bc956c906aebdc346", "type": "NoFilter"},
    ]}
    return write_page(P1, 'QV Exceptions', vis, extra)


# ================================================================= PAGE 2
def build_p2():
    ids = skel_ids('p2')
    ids['bar'] = '6762454c15985878b8bf'
    ids['nav'] = '92709acc168ebeeacd6f'
    ids['rail'] = '856a89397330ad739e86'
    vis = skeleton('p2', 'UPS QUANTUM VIEW  ·  RESOLUTION', 'FILTERS', ids)

    # spec p.7 accents: Open Gold · Aging Breach · Resolved Green · Avg Ink · Emails Email
    vis += [
        make_card('fc07cf5e3aa2329fc5b4', 0, 'OPEN EXCEPTIONS',
                  entity_measure('Resolutions Table', 'Open Ex'), ACCENT,
                  'Resolutions Table.Open Ex'),
        make_card('7d02710dd71cb7cd8591', 1, 'AGED 8+ DAYS',
                  entity_measure('Resolutions Table', 'Aged 8 Plus Days'), BREACH,
                  'Resolutions Table.Aged 8 Plus Days'),
        make_card('5307d49ca1a3cb931126', 2, 'RESOLVED',
                  entity_measure('Resolutions Table', 'Resolved Exceptions Display'), RESOLVED,
                  'Resolutions Table.Resolved Exceptions Display'),
        make_card('703c466f2cf08c73b301', 3, 'AVG AGE (DAYS)',
                  entity_measure('Resolutions Table', 'Avg Age (Days)'), INK,
                  'Resolutions Table.Avg Age (Days)'),
        make_card('d9a5a7f4aa0a6e8a4cbf', 4, 'ESCALATED',
                  entity_measure('Resolutions Table', 'Escalated Exceptions Display'), EMAIL,
                  'Resolutions Table.Escalated Exceptions Display'),
    ]
    RT = 'Resolutions Table'
    vis += [
        make_slicer('0a319b677d4122a4f3d7', 0, 'TRACKER STATUS', RT, 'Tracker Status'),
        make_slicer('3ef728007d0c5e44223e', 1, 'ROOT CAUSE', RT, 'Root Cause'),
        make_slicer('d663dc3095675939688c', 2, 'SERVICE', RT, 'Service'),
        make_slicer('3f36e922db732d9c200e', 3, 'AGE BUCKET', RT, 'Age Bucket'),
        make_slicer('e455a62d2c8c6a259dbf', 4, 'EXCEPTION TYPE', RT, 'Exception Type '),
    ]

    queue = place(tpl(P2, '94c73661658330364cb6'), '94c73661658330364cb6',
                  QUEUE, Z_WORK, 'Resolution Queue  ·  select a row to load Notes')
    style_table(queue)
    queue["visual"]["query"] = table_projections([
        (RT, 'Tracking Number', 'Tracking Number'),
        (RT, 'Exception Category', 'Category'),
        (RT, 'Service', 'Service'),
        (RT, 'Age Days', 'Age (d)'),
        (RT, 'Age Bucket', 'Age Bucket'),
        (RT, 'Tracker Status', 'Status'),
    ])
    notes = place(tpl(P2, '081b1e0fe3ce6519f6f3'), '081b1e0fe3ce6519f6f3',
                  NOTES, Z_WORK + 1, 'Manual Notes & Status')
    style_table(notes)
    notes["visual"]["query"] = {"queryState": {"Values": {"projections": [
        {"field": entity_measure(RT, 'Selected Tracking Number'),
         "queryRef": "%s.Selected Tracking Number" % RT, "nativeQueryRef": "Tracking Number"},
        {"field": entity_measure(RT, 'Selected Status'),
         "queryRef": "%s.Selected Status" % RT, "nativeQueryRef": "Status"},
        {"field": entity_measure(RT, 'Selected Root Cause'),
         "queryRef": "%s.Selected Root Cause" % RT, "nativeQueryRef": "Root Cause"},
        {"field": entity_measure(RT, 'Selected Next Action'),
         "queryRef": "%s.Selected Next Action" % RT, "nativeQueryRef": "Next Action"},
        {"field": entity_measure(RT, 'Selected Notes'),
         "queryRef": "%s.Selected Notes" % RT, "nativeQueryRef": "Notes"},
    ]}}}

    auto = base(T_SHAPE, 'e1f6002360ed4f6634ae', AUTO, Z_WORK + 2)
    auto["visual"]["objects"] = {
        "shape": grp({"tileShape": sv('rectangleRoundedByPixel')}),
        "rotation": grp({"shapeAngle": lv(0)}),
        "fill": [{"properties": {"show": bv(True)}},
                 {"properties": {"fillColor": col(WHITE), "transparency": dv(0)},
                  "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": bv(True)}},
                    {"properties": {"lineColor": col(BORDER), "weight": lv(1),
                                    "transparency": dv(0)},
                     "selector": {"id": "default"}}],
        "text": grp({"show": bv(False)}),
    }
    panel_chrome(auto, title='Write-Back & Email Automation', border=False)
    auto["visual"]["visualContainerObjects"]["background"] = grp({"show": bv(False)})

    note_txt = make_textbox('e875e461e9d0dbea1eba', (662, 446, 428, 172), Z_WORK + 3, [
        run('SharePoint List is the system of record; Excel is an append-only log.', 8, LABEL),
        run('', 8, LABEL),
        run('Step 7  ·  SharePoint List + seed rows', 9, INK, True),
        run('Step 8  ·  Power Apps write-back, row-select passes Exception ID', 9, INK, True),
        run('Step 9  ·  Flow 1 audit log  ·  Flow 2 mail-merge (preview gate)', 9, INK, True),
        run('', 8, LABEL),
        run('Not yet wired - build order pages 12-14.', 8, EMAIL),
    ])
    vis += [queue, notes, auto, note_txt]

    extra = {"visualInteractions": [
        {"source": "94c73661658330364cb6", "target": "081b1e0fe3ce6519f6f3", "type": "DataFilter"},
    ]}
    return write_page(P2, 'QV Resolutions', vis, extra)


# ================================================================= PAGE 3
def build_p3():
    ids = skel_ids('p3')
    ids['nav'] = '572346907c66c3dbb540'
    ids['rail'] = 'ce4cae3d1b67430233de'
    vis = skeleton('p3', 'UPS QUANTUM VIEW  ·  TRACE', 'FILTERS', ids)

    COT = 'Current_Open_Trace'
    cnt = entity_agg(COT, 'CASE #', AGG_COUNTNONNULL)
    ref = 'CountNonNull(%s.CASE #)' % COT
    vis += [
        make_card('c2bc2d2fd7c4d1741e13', 0, 'ACTIVE TRACES', cnt, INK, ref),
        make_card('0920059c7b37d8512b58', 1, 'OPEN > 10 DAYS (SLA)', cnt, BREACH, ref,
                  vfilters=[adv_filter('23b1286f8045ad67b840', 0, COT,
                                       'Days Since Review', 2, '10L')]),
        make_card('c9a3ca9a9c20da00e2d8', 2, 'ESCALATIONS', cnt, WIP, ref,
                  vfilters=[adv_filter('23b1286f8045ad67b841', 0, COT,
                                       'Review Status', 0, "'Escalate'")]),
        make_card('d53bfbaba715840d83d3', 3, 'NEVER REVIEWED', cnt, ACCENT, ref,
                  vfilters=[adv_filter('23b1286f8045ad67b842', 0, COT,
                                       'Review Status', 0, "'Never Reviewed'")]),
        make_card('4b74e94189d28cacb8ba', 4, 'PACKAGES LOST', cnt, BREACH, ref,
                  vfilters=[adv_filter('cc119fa0e149c0bb7551', 0, COT,
                                       'Lost/Damaged', 0, "'LOST'")]),
    ]
    vis += [
        make_slicer('d376b3092b445db580be', 0, 'REVIEW STATUS', COT, 'Review Status'),
        make_slicer('a242a0248e438d4d2b64', 1, 'UPS STATUS', COT, 'UPS Status'),
        make_slicer('778c6be08d859756d38d', 2, 'LOCATION', COT, 'Location'),
        make_slicer('95d6e3bbccd96b0ce0a0', 3, 'SERVICE', COT, 'Service'),
        make_slicer(new_id('p3/slicer-fa'), 4, 'FA NUMBER', COT, 'FA #'),
    ]

    b1 = style_bar_chart(place(tpl(P3, 'e27002cd13ca83c7c733'), 'e27002cd13ca83c7c733',
                               R1L, Z_WORK, 'Active Traces by Review Status'))
    b2 = style_bar_chart(place(tpl(P3, 'b2d6b5d6b97b94bc088e'), 'b2d6b5d6b97b94bc088e',
                               R1R, Z_WORK + 1, 'Active Traces by UPS Status'))
    nt = place(tpl(P3, '0d4f83b789800eb00017'), '0d4f83b789800eb00017',
               R2F, Z_WORK + 2, 'Manual Notes & Status')
    style_table(nt)
    nt["visual"]["query"] = table_projections([
        (COT, 'CASE #', 'Case'),
        (COT, 'Trace_Notes.Trace Status', 'Trace Status'),
        (COT, 'Trace_Notes.Last Action', 'Last Action'),
        (COT, 'Trace_Notes.Next Follow-up Date', 'Next Follow-up'),
        (COT, 'Trace_Notes.Notes', 'Notes'),
    ])
    q = place(tpl(P3, 'a4bc518d4ca9ec4a273b'), 'a4bc518d4ca9ec4a273b',
              R3F, Z_WORK + 3, 'Open Trace Queue  ·  right-click a row to drill to Trace Detail')
    style_table(q, web_url_on='%s.Tracking Number' % COT,
                web_url_entity=COT, web_url_col='Tracking URL')
    q["visual"]["query"] = table_projections([
        (COT, 'CASE #', 'Case'),
        (COT, 'Tracking Number', 'Tracking Number'),
        (COT, 'Delivery Status', 'Delivery Status'),
        (COT, 'UPS Status', 'UPS Status'),
        (COT, 'Review Status', 'Review Status'),
        (COT, 'Days Since Review', 'Days Since Review'),
        (COT, 'Last Reviewed', 'Last Reviewed'),
        (COT, 'Location', 'Location'),
        (COT, 'FA #', 'FA #'),
        (COT, 'Exception Description', 'Exception'),
    ])
    vis += [b1, b2, nt, q]

    extra = {"visualInteractions": [
        {"source": "a4bc518d4ca9ec4a273b", "target": t, "type": "NoFilter"}
        for t in ('c2bc2d2fd7c4d1741e13', '0920059c7b37d8512b58', 'c9a3ca9a9c20da00e2d8',
                  'd53bfbaba715840d83d3', '4b74e94189d28cacb8ba',
                  'e27002cd13ca83c7c733', 'b2d6b5d6b97b94bc088e')
    ]}
    return write_page(P3, 'QV Tracing', vis, extra)


# ================================================================= PAGE 4
def build_p4():
    ids = skel_ids('p4')
    vis = skeleton('p4', 'UPS QUANTUM VIEW  ·  EXCEPTION DETAIL', 'CONTEXT', ids)
    vis.append(make_back_button('79c52cc25902bb5aae7b', 'Back to Exceptions'))

    QO = 'QV_Output'
    def dcard(vid, idx, label, prop, accent):
        return make_card(vid, idx, label, entity_agg(QO, prop, AGG_MIN), accent,
                         'Min(%s.%s)' % (QO, prop))
    vis += [
        dcard(new_id('p4/c1'), 0, 'EXCEPTION CATEGORY', 'Exception Category', INK),
        dcard(new_id('p4/c2'), 1, 'EXCEPTION TYPE', 'Exception Type ', BREACH),
        dcard(new_id('p4/c3'), 2, 'SERVICE', 'Service', INK),
        dcard(new_id('p4/c4'), 3, 'MANIFEST DATE', 'Manifest Date', RESOLVED),
        dcard(new_id('p4/c5'), 4, 'SHIPPER LOCATION', 'Shipper Location', ACCENT),
    ]

    t1 = place(tpl(P4, '4270694a1cb209308bd0'), '4270694a1cb209308bd0',
               R1F, Z_WORK, 'Exception Detail  ·  click the Tracking Number to open UPS tracking')
    style_table(t1, web_url_on='QV_Output.Tracking Number',
                web_url_entity=QO, web_url_col='Tracking URL')
    t1["visual"]["query"] = table_projections([
        (QO, 'Tracking Number', 'Tracking Number'),
        (QO, 'Exception Key', 'Exception Key'),
        (QO, 'Exception Category', 'Category'),
        (QO, 'Exception Status Description', 'Exception Status'),
        (QO, 'Service', 'Service'),
        (QO, 'Manifest Date', 'Manifest Date'),
        (QO, 'Original Scheduled Delivery Date', 'Orig. Sched. Delivery'),
        (QO, 'Scheduled Delivery', 'Scheduled Delivery'),
    ])
    t2 = place(T_TABLE, new_id('p4/t2'), R2F, Z_WORK + 1, 'Shipper & Consignee')
    style_table(t2)
    t2["visual"]["query"] = table_projections([
        (QO, 'Shipper Name', 'Shipper Name'),
        (QO, 'Shipper Location', 'Shipper Location'),
        (QO, 'Shipper Address Line 1', 'Shipper Address'),
        (QO, 'Ship To Name', 'Ship To'),
        (QO, 'Full Address', 'Ship To Address'),
    ])
    t3 = place(T_TABLE, new_id('p4/t3'), R3F, Z_WORK + 2, 'Exception, Resolution & Recommended Action')
    style_table(t3)
    t3["visual"]["query"] = table_projections([
        (QO, 'Exception Description', 'Exception Description'),
        (QO, 'Exception Resolution', 'Exception Resolution'),
        (QO, 'Carrier Delay Reason', 'Carrier Delay Reason'),
        (QO, 'Recommended Action', 'Recommended Action'),
        (QO, 'Run Date', 'Run Date'),
        (QO, 'Run Time', 'Run Window'),
    ])
    vis += [t1, t2, t3]

    extra = {
        "filterConfig": {"filters": [{
            "name": "add1b3a50c80c5fa73a8",
            "field": entity_col('QV_Output', 'Tracking Number'),
            "type": "Categorical", "howCreated": "Drillthrough"}]},
        "pageBinding": {"name": "b76efc3bd74845b1a45f", "type": "Drillthrough",
                        "parameters": [{"name": "d58a868399b2cc5b13c0",
                                        "boundFilter": "add1b3a50c80c5fa73a8",
                                        "fieldExpr": entity_col('QV_Output', 'Tracking Number')}]},
        "visibility": "HiddenInViewMode",
    }
    return write_page(P4, 'QV Exception Detail', vis, extra)


# ================================================================= PAGE 5
def build_p5():
    ids = skel_ids('p5')
    ids['pagetitle'] = 'ef87d8fa8e9402ba0740'
    vis = skeleton('p5', 'UPS QUANTUM VIEW  ·  TRACE DETAIL', 'CONTEXT', ids)
    vis.append(make_back_button('8db4c211d065035d6cc7', 'Back to Trace'))

    COT = 'Current_Open_Trace'
    def dcard(vid, idx, label, prop, accent):
        return make_card(vid, idx, label, entity_agg(COT, prop, AGG_MIN), accent,
                         'Min(%s.%s)' % (COT, prop))
    vis += [
        dcard('68be8dae928922660be0', 0, 'CASE #', 'CASE #', INK),
        dcard('0453e784bd69a6400023', 1, 'DAYS SINCE REVIEW', 'Days Since Review', BREACH),
        dcard('3c93366b03c823705205', 2, 'REVIEW STATUS', 'Review Status', WIP),
        dcard('2c344afd2152211b302a', 3, 'UPS STATUS', 'UPS Status', INK),
        dcard('29f2a33cb6288a21c71d', 4, 'TRACKING NUMBER', 'Tracking Number', ACCENT),
    ]

    t1 = place(tpl(P5, '700ac056c940a85a0766'), '700ac056c940a85a0766',
               R1L, Z_WORK, 'Trace Action Summary')
    style_table(t1)
    t1["visual"]["query"] = table_projections([
        (COT, 'Last Reviewed', 'Last Reviewed'),
        (COT, 'Review Status', 'Review Status'),
        (COT, 'Trace_Notes.Trace Status', 'Trace Status'),
        (COT, 'Trace_Notes.Last Action', 'Last Action'),
        (COT, 'Follow-up', 'Follow-up'),
        (COT, 'Trace_Notes.Next Follow-up Date', 'Next Follow-up'),
        (COT, 'FA #', 'FA #'),
        (COT, 'Location', 'Location'),
    ])
    t2 = place(tpl(P5, 'debeba175ca945a67bb7'), 'debeba175ca945a67bb7',
               R1R, Z_WORK + 1, 'Risk / Claim Summary')
    style_table(t2)
    t2["visual"]["query"] = table_projections([
        (COT, 'Account', 'Account'),
        (COT, 'Service', 'Service'),
        (COT, 'PII', 'PII'),
        (COT, 'Lost/Damaged', 'Lost / Damaged'),
        (COT, 'Claim Issued', 'Claim Issued'),
        (COT, 'Claims Paperwork Filed', 'Paperwork Filed'),
        (COT, 'Claim Approved', 'Claim Approved'),
        (COT, 'Refund Amount', 'Refund Amount'),
    ])
    t3 = place(tpl(P5, 'b60180314e31c19a2b01'), 'b60180314e31c19a2b01',
               R2F, Z_WORK + 2, 'Manual Notes')
    style_table(t3)
    t3["visual"]["query"] = table_projections([
        (COT, 'Trace_Notes.Notes', 'Notes'),
        (COT, 'Trace_Notes.Tickler Type', 'Tickler Type'),
        (COT, 'Trace_Notes.UPS Trace Number', 'UPS Trace #'),
        (COT, 'Trace_Notes.Claim Status', 'Claim Status'),
        (COT, 'Trace_Notes.Closed Date', 'Closed Date'),
    ])
    t4 = place(tpl(P5, '1abbaa2e40b29e7d3820'), '1abbaa2e40b29e7d3820',
               R3F, Z_WORK + 3, 'UPS Exception Detail')
    style_table(t4)
    t4["visual"]["query"] = table_projections([
        (COT, 'Exception Status Description', 'Exception Status'),
        (COT, 'Exception Description', 'Exception Description'),
        (COT, 'Exception Resolution', 'Exception Resolution'),
        (COT, 'UPS SCANS', 'UPS Scans'),
        (COT, 'Manifest Date', 'Manifest Date'),
        (COT, 'Original Scheduled Delivery Date', 'Orig. Sched. Delivery'),
    ])
    vis += [t1, t2, t3, t4]

    extra = {
        "filterConfig": {"filters": [
            {"name": "bba8c54a39433a05602a", "field": entity_col(COT, 'CASE #'),
             "type": "Categorical", "howCreated": "Drillthrough"},
            {"name": "530873cfb894086e835b", "field": entity_col(COT, 'Tracking Number'),
             "type": "Categorical", "howCreated": "Drillthrough"},
        ]},
        "pageBinding": {"name": "114b9a62a6d6049caaa0", "type": "Drillthrough", "parameters": [
            {"name": "8ae51b214a6c0713d209", "boundFilter": "bba8c54a39433a05602a",
             "fieldExpr": entity_col(COT, 'CASE #')},
            {"name": "5ff00583c503416c0e89", "boundFilter": "530873cfb894086e835b",
             "fieldExpr": entity_col(COT, 'Tracking Number')},
        ]},
        "visibility": "HiddenInViewMode",
    }
    return write_page(P5, 'Trace Detail', vis, extra)


# ================================================================= main
def main():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    shutil.copytree(EXTRACTED, BUILD)

    counts = {'QV Exceptions': build_p1(), 'QV Resolutions': build_p2(),
              'QV Tracing': build_p3(), 'QV Exception Detail': build_p4(),
              'Trace Detail': build_p5()}

    with open(os.path.join(PAGES_DST, 'pages.json'), 'w', encoding='utf-8') as f:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
                   "pageOrder": [P1, P2, P3, P4, P5],
                   "activePageName": P1}, f, indent=2)

    for name, n in counts.items():
        print('  %-22s %2d visuals' % (name, n))

if __name__ == '__main__':
    main()
