#!/usr/bin/env python3
"""
Add the vendor ranking chart to OVERVIEW.

The work area was full, so rather than displace anything the top row goes from two
panels to three.  Vendor gets the widest slot because its labels are the longest
("2093RE - EDWARD JONES/Brand Addition"); Category and Service have short labels and
lose little at ~295px.

    before   Category 186,162,525x165   Service 723,162,533x165
    after    Category 186,162,300x165   Service 498,162,290x165   Vendor 800,162,456x165
             186+300=486 | +12 gutter | 498+290=788 | +12 | 800+456=1256  (right margin)

The chart is a clone of "Exceptions by Category" from this same page with only name,
position, query and title changed - the construction that has held up.  It is sorted
descending by Total Exceptions so the worst vendor is the top bar.
"""
import json, os, shutil, zipfile, copy, hashlib

SRC = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v3.pbix')
STAGE = os.path.join(SRC, 'stage4')
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v4.pbix')
DEF = 'Report/definition/'

OVERVIEW = '36b05998ad2a58e00312'
CATEGORY = '1464f7f7b0a80df1e45b'          # clone source, same page
SERVICE = '440cc3a8f7f81d9c576c'

ROW1 = {CATEGORY: (186, 162, 300, 165),
        SERVICE:  (498, 162, 290, 165)}
VENDOR_RECT = (800, 162, 456, 165)
VENDOR_Z = 16500                            # between the two charts and the row below


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    zin = zipfile.ZipFile(IN)
    zin.extractall(STAGE)
    vdir = os.path.join(STAGE, DEF, 'pages', OVERVIEW, 'visuals')

    # 1. re-proportion the two existing charts
    for vid, rect in ROW1.items():
        f = os.path.join(vdir, vid, 'visual.json')
        d = json.load(open(f))
        d['position'].update({'x': rect[0], 'y': rect[1], 'width': rect[2], 'height': rect[3]})
        json.dump(d, open(f, 'w'), indent=2)

    # 2. clone Category -> Vendor
    template = json.load(open(os.path.join(vdir, CATEGORY, 'visual.json')))
    v = copy.deepcopy(template)
    vid = hashlib.sha1(b'qv-vendor-ranking').hexdigest()[:20]
    v['name'] = vid
    v['position'] = {'x': VENDOR_RECT[0], 'y': VENDOR_RECT[1], 'z': VENDOR_Z,
                     'width': VENDOR_RECT[2], 'height': VENDOR_RECT[3], 'tabOrder': VENDOR_Z}
    v.pop('filterConfig', None)
    v['visual']['query'] = {
        'queryState': {
            'Category': {'projections': [{
                'field': {'Column': {'Expression': {'SourceRef': {'Entity': 'Dim_Account'}},
                                     'Property': 'Account Label'}},
                'queryRef': 'Dim_Account.Account Label',
                'nativeQueryRef': 'Account / Vendor',
                'active': True}]},
            'Y': {'projections': [{
                'field': {'Measure': {'Expression': {'SourceRef': {'Entity': 'QV_Output'}},
                                      'Property': 'Total Exceptions'}},
                'queryRef': 'QV_Output.Total Exceptions',
                'nativeQueryRef': 'Total Exceptions'}]},
        },
        'sortDefinition': {'sort': [{
            'field': {'Measure': {'Expression': {'SourceRef': {'Entity': 'QV_Output'}},
                                  'Property': 'Total Exceptions'}},
            'direction': 'Descending'}]},
    }
    v['visual']['visualContainerObjects']['title'][0]['properties']['text'] = {
        'expr': {'Literal': {'Value': "'Exceptions by Account / Vendor  ·  worst first'"}}}
    d = os.path.join(vdir, vid)
    os.makedirs(d, exist_ok=True)
    json.dump(v, open(os.path.join(d, 'visual.json'), 'w'), indent=2)

    # 3. repackage
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
    print('vendor ranking chart added: %s at %s' % (vid, VENDOR_RECT))
    print('top row re-proportioned:')
    for k, r in ROW1.items():
        print('   %s -> %s' % (k[:8], r))
    print('   right edge: %d (page margin 1256)' % (VENDOR_RECT[0] + VENDOR_RECT[2]))
    print('DataModel byte-identical: True')
    print('output: %s (%.2f MB)' % (os.path.basename(OUT), os.path.getsize(OUT) / 1024 / 1024))


if __name__ == '__main__':
    main()
