#!/usr/bin/env python3
"""
Surgical edits to the current Quantum View .pbix.

Deliberately NOT a rebuild.  The file has evolved (renamed pages, a new test page,
Dim_Account wired to the trace tables) and the brief is to keep formatting and
functionality exactly as they are.  So this touches four things and nothing else:

  1. adds one slicer to rail slot 6 on the three visible pages, bound to
     Dim_Account[Account Label] - a column that ALREADY exists in the model, so the
     slicer works the moment the file opens
  2. realigns one KPI card on ACTIVE TRACES that had drifted off the grid
  3. hides (does not delete) the TEST-Acct Sliver page
  4. removes the sensitivity label so the file opens

Every new visual is a clone of an existing slicer ON THE SAME PAGE with only name,
position, z and query changed - the construction the bisect proved safe.
"""
import json, os, re, shutil, zipfile, copy, hashlib

SRC = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(SRC, 'current.pbix')
STAGE = os.path.join(SRC, 'stage')
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard_v2.pbix')
DEF = 'Report/definition/'

# rail slot 6 - the rail runs y=162..696, existing slicers occupy 196..524
SLOT6 = (36, 536, 126, 56)
Z_SLOT6 = 15500          # between the last slicer (15000) and the first chart (16000)

# page -> (template slicer to clone, page label)
TARGETS = {
    '36b05998ad2a58e00312': ('cffbba7ded6e5178b6c8', 'OVERVIEW'),
    '8db06a7e73968141bad0': ('0a319b677d4122a4f3d7', 'RESOLUTION QUEUE'),
    '653efd92bd7e39c1655a': ('d376b3092b445db580be', 'ACTIVE TRACES'),
}
DRIFTED = ('653efd92bd7e39c1655a', 'd53bfbaba715840d83d3', (774, 76, 232, 78))
TEST_PAGE_MARKER = 'TEST'


def new_id(seed):
    return hashlib.sha1(('qv-account::' + seed).encode()).hexdigest()[:20]


def make_account_slicer(template, vid):
    """Clone a proven rail slicer, repoint it at Dim_Account[Account Label]."""
    v = copy.deepcopy(template)
    v['name'] = vid
    v['position'] = {'x': SLOT6[0], 'y': SLOT6[1], 'z': Z_SLOT6,
                     'width': SLOT6[2], 'height': SLOT6[3], 'tabOrder': Z_SLOT6}
    v.pop('filterConfig', None)
    v['visual']['query'] = {'queryState': {'Values': {'projections': [{
        'field': {'Column': {'Expression': {'SourceRef': {'Entity': 'Dim_Account'}},
                             'Property': 'Account Label'}},
        'queryRef': 'Dim_Account.Account Label',
        'nativeQueryRef': 'ACCOUNT / VENDOR',
        'active': True,
    }]}}}
    # a saved selection is what broke the Exceptions page once before - never ship one
    for e in v['visual'].get('objects', {}).get('general', []):
        e.get('properties', {}).pop('filter', None)
    return v


def strip_ct(b):
    x = b.decode('utf-8')
    x = re.sub(r'<Override\s+PartName="/SecurityBindings"[^/]*/>', '', x)
    assert 'SecurityBindings' not in x
    return x.encode('utf-8')


def strip_props(b):
    x = b.decode('utf-8')
    x = re.sub(r'<property\b[^>]*name="MSIP_Label_[^"]*"[^>]*>.*?</property>', '', x, flags=re.S)
    assert 'MSIP' not in x
    return x.encode('utf-8')


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    zin = zipfile.ZipFile(ORIG)
    zin.extractall(STAGE)
    pages = os.path.join(STAGE, DEF, 'pages')

    added = []
    for page, (tpl_id, label) in TARGETS.items():
        tdir = os.path.join(pages, page, 'visuals', tpl_id, 'visual.json')
        with open(tdir) as f:
            template = json.load(f)
        vid = new_id(page)
        v = make_account_slicer(template, vid)
        d = os.path.join(pages, page, 'visuals', vid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'visual.json'), 'w', encoding='utf-8') as f:
            json.dump(v, f, indent=2)
        added.append((label, vid))

    # realign the drifted card
    pg, vid, rect = DRIFTED
    f = os.path.join(pages, pg, 'visuals', vid, 'visual.json')
    d = json.load(open(f))
    before = (d['position']['x'], d['position']['y'], d['position']['width'], d['position']['height'])
    d['position'].update({'x': rect[0], 'y': rect[1], 'width': rect[2], 'height': rect[3]})
    json.dump(d, open(f, 'w'), indent=2)

    # hide, do not delete, the test page
    hidden = None
    for p in os.listdir(pages):
        pj = os.path.join(pages, p, 'page.json')
        if not os.path.isfile(pj):
            continue
        d = json.load(open(pj))
        if TEST_PAGE_MARKER in d.get('displayName', ''):
            d['visibility'] = 'HiddenInViewMode'
            json.dump(d, open(pj, 'w'), indent=2)
            hidden = d['displayName']

    # repackage, label stripped
    new_parts = sorted((os.path.relpath(os.path.join(r, fn), STAGE).replace(os.sep, '/'),
                        os.path.join(r, fn))
                       for r, _, fs in os.walk(os.path.join(STAGE, DEF)) for fn in fs)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zo:
        emitted = False
        for info in zin.infolist():
            n = info.filename
            if n == 'SecurityBindings':
                continue
            if n.startswith(DEF):
                if not emitted:
                    for arc, full in new_parts:
                        zi = zipfile.ZipInfo(arc, date_time=info.date_time)
                        zi.compress_type = zipfile.ZIP_DEFLATED
                        zi.external_attr = info.external_attr
                        zo.writestr(zi, open(full, 'rb').read())
                    emitted = True
                continue
            data = zin.read(n)
            if n == '[Content_Types].xml':
                data = strip_ct(data)
            elif n == 'docProps/custom.xml':
                data = strip_props(data)
            zi = zipfile.ZipInfo(n, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zo.writestr(zi, data)

    z = zipfile.ZipFile(OUT)
    assert z.testzip() is None
    assert z.read('DataModel') == zin.read('DataModel'), 'DataModel must not change'
    print('account slicers added (rail slot 6, %s):' % str(SLOT6))
    for label, vid in added:
        print('   %-18s %s' % (label, vid))
    print('realigned drifted card on ACTIVE TRACES: %s -> %s' % (before, rect))
    print('hidden test page: %s' % hidden)
    print('label removed: SecurityBindings=%s  MSIP=%s'
          % ('SecurityBindings' in z.namelist(), b'MSIP' in z.read('docProps/custom.xml')))
    print('DataModel byte-identical: True')
    print('visuals: %d -> %d' % (sum(1 for x in zin.namelist() if x.endswith('visual.json')),
                                 sum(1 for x in z.namelist() if x.endswith('visual.json'))))
    print('output: %s (%.2f MB)' % (OUT, os.path.getsize(OUT) / 1024 / 1024))


if __name__ == '__main__':
    main()
