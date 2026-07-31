#!/usr/bin/env python3
"""
Add a Manifest Date slicer to rail slot 7 on the three visible pages.

The rail runs y=162..696 with 12px inner padding, so its usable bottom is 684.
Slots 1-6 occupy 196..592.  Slot 7 at y=604 ends at 660 - fits with room to spare.

Bound to 'Resolutions Table'[Manifest Date] - a column that EXISTS today, so the
slicer works the moment the file opens and carries no dependency on Dim Date being
applied first.  Filtering flows Resolutions Table -> QV_Output, so it drives the
OVERVIEW charts as well as the queue.

Deliberately NOT bound to 'Dim Date'[Date]: that table does not exist in the model
yet, and binding a visual to a missing table is the risk profile that produced the
unopenable files earlier in this build.  Repoint it once Dim Date is applied - see
MEASURE-SWEEP.md - which additionally makes Total Shipments date-responsive.

ACTIVE TRACES gets no date slicer: every date column on Current_Open_Trace is TEXT,
so no date table can reach it until those are typed.
"""
import json, os, shutil, zipfile, copy, hashlib

SRC = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v4.pbix')
STAGE = os.path.join(SRC, 'stage5')
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v5.pbix')
DEF = 'Report/definition/'

SLOT7 = (36, 604, 126, 56)
Z_SLOT7 = 15600

TARGETS = {
    '36b05998ad2a58e00312': 'cffbba7ded6e5178b6c8',   # OVERVIEW
    '8db06a7e73968141bad0': '0a319b677d4122a4f3d7',   # RESOLUTION QUEUE
}


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    zin = zipfile.ZipFile(IN)
    zin.extractall(STAGE)
    pages = os.path.join(STAGE, DEF, 'pages')
    added = []
    for page, tpl_id in TARGETS.items():
        template = json.load(open(os.path.join(pages, page, 'visuals', tpl_id, 'visual.json')))
        v = copy.deepcopy(template)
        vid = hashlib.sha1(('qv-datesl::' + page).encode()).hexdigest()[:20]
        v['name'] = vid
        v['position'] = {'x': SLOT7[0], 'y': SLOT7[1], 'z': Z_SLOT7,
                         'width': SLOT7[2], 'height': SLOT7[3], 'tabOrder': Z_SLOT7}
        v.pop('filterConfig', None)
        v['visual']['query'] = {'queryState': {'Values': {'projections': [{
            'field': {'Column': {'Expression': {'SourceRef': {'Entity': 'Resolutions Table'}},
                                 'Property': 'Manifest Date'}},
            'queryRef': 'Resolutions Table.Manifest Date',
            'nativeQueryRef': 'MANIFEST DATE',
            'active': True}]}}}
        for e in v['visual'].get('objects', {}).get('general', []):
            e.get('properties', {}).pop('filter', None)
        d = os.path.join(pages, page, 'visuals', vid)
        os.makedirs(d, exist_ok=True)
        json.dump(v, open(os.path.join(d, 'visual.json'), 'w'), indent=2)
        added.append((page[:8], vid))

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
    print('date slicers added at %s:' % str(SLOT7))
    for p, v in added:
        print('   %s  %s' % (p, v))
    print('output: %s (%.2f MB)' % (os.path.basename(OUT), os.path.getsize(OUT) / 1024 / 1024))
