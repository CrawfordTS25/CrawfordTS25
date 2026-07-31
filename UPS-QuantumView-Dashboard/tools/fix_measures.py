#!/usr/bin/env python3
"""
Report-layer half of the measure sweep.

The ACTIVE TRACES KPI cards carry visual-level filters left over from an earlier build.
When the new Current_Open_Trace measures were dropped in, those filters stayed, so each
card now applies its filter TWICE - once inside the measure, once on the visual. Two
cards read literally zero as a result.

  card                shows  should  cause
  Never Reviewed          0      28  measure(Review Status='Never Reviewed') AND filter(='Escalate')
  In Transit              0      27  measure(In Transit/Out for Delivery) AND filter(Review Status='Never Reviewed')
  Overdue Traces         12      86  measure(Overdue=TRUE) AND filter(Lost/Damaged='LOST')
  Escalated Traces       67      67  right number, wrong mechanism - counts Days Since Review>10,
                                     not Review Status='Escalate'; will diverge as data moves

Fixes: drop the leftover filters, repoint Escalated Traces at its measure, and uppercase
the KPI labels so all three pages match (spec p.7 - label 9px uppercase).
"""
import json, os, re, shutil, zipfile, copy, zipfile

SRC = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v2.pbix')
STAGE = os.path.join(SRC, 'stage3')
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v3.pbix')
DEF = 'Report/definition/'

TRACE = '653efd92bd7e39c1655a'
COT = 'Current_Open_Trace'

# card id -> (measure to bind, label).  All four lose their leftover visual filter.
TRACE_CARDS = {
    'c2bc2d2fd7c4d1741e13': ('Total Active Traces', 'ACTIVE TRACES'),
    '0920059c7b37d8512b58': ('Escalated Traces',    'ESCALATIONS'),
    'c9a3ca9a9c20da00e2d8': ('Never Reviewed',      'NEVER REVIEWED'),
    'd53bfbaba715840d83d3': ('In Transit',          'IN TRANSIT'),
    '4b74e94189d28cacb8ba': ('Overdue Traces',      'OVERDUE'),
}


def measure_projection(entity, name, label):
    return {'queryState': {'Data': {'projections': [{
        'field': {'Measure': {'Expression': {'SourceRef': {'Entity': entity}},
                              'Property': name}},
        'queryRef': '%s.%s' % (entity, name),
        'nativeQueryRef': label,
    }]}}}


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    zin = zipfile.ZipFile(IN)
    zin.extractall(STAGE)
    pages = os.path.join(STAGE, DEF, 'pages')

    fixed, relabelled = [], []

    # --- ACTIVE TRACES cards: rebind + strip the leftover filters
    for vid, (measure, label) in TRACE_CARDS.items():
        f = os.path.join(pages, TRACE, 'visuals', vid, 'visual.json')
        d = json.load(open(f))
        had = 'filterConfig' in d and any(x.get('filter') for x in d['filterConfig'].get('filters', []))
        d.pop('filterConfig', None)
        d['visual']['query'] = measure_projection(COT, measure, label)
        json.dump(d, open(f, 'w'), indent=2)
        fixed.append((label, measure, had))

    # --- uppercase every KPI label so the three pages read the same
    for page in os.listdir(pages):
        vdir = os.path.join(pages, page, 'visuals')
        if not os.path.isdir(vdir):
            continue
        for vid in os.listdir(vdir):
            f = os.path.join(vdir, vid, 'visual.json')
            d = json.load(open(f))
            if d['visual']['visualType'] != 'cardVisual':
                continue
            try:
                pr = d['visual']['query']['queryState']['Data']['projections'][0]
            except Exception:
                continue
            lbl = pr.get('nativeQueryRef')
            if lbl and lbl != lbl.upper():
                pr['nativeQueryRef'] = lbl.upper()
                json.dump(d, open(f, 'w'), indent=2)
                relabelled.append((lbl, lbl.upper()))

    # --- repackage (label already stripped in v2, keep it that way)
    new_parts = sorted((os.path.relpath(os.path.join(r, fn), STAGE).replace(os.sep, '/'),
                        os.path.join(r, fn))
                       for r, _, fs in os.walk(os.path.join(STAGE, DEF)) for fn in fs)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zo:
        emitted = False
        for info in zin.infolist():
            n = info.filename
            if n.startswith(DEF):
                if not emitted:
                    for arc, full in new_parts:
                        zi = zipfile.ZipInfo(arc, date_time=info.date_time)
                        zi.compress_type = zipfile.ZIP_DEFLATED
                        zi.external_attr = info.external_attr
                        zo.writestr(zi, open(full, 'rb').read())
                    emitted = True
                continue
            zi = zipfile.ZipInfo(n, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zo.writestr(zi, zin.read(n))

    z = zipfile.ZipFile(OUT)
    assert z.testzip() is None
    assert z.read('DataModel') == zin.read('DataModel')
    print('ACTIVE TRACES cards rebound (leftover filter removed where present):')
    for label, measure, had in fixed:
        print('   %-18s -> [%s]%s' % (label, measure, '   (filter removed)' if had else ''))
    print('\nKPI labels uppercased for cross-page consistency: %d' % len(relabelled))
    for a, b in relabelled:
        print('   %-24s -> %s' % (a, b))
    print('\nDataModel byte-identical: True')
    print('output: %s (%.2f MB)' % (os.path.basename(OUT), os.path.getsize(OUT) / 1024 / 1024))


if __name__ == '__main__':
    main()
