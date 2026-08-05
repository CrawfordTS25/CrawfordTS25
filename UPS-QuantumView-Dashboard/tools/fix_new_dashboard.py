#!/usr/bin/env python3
"""
Repair pass over NEWQuantum_View_Exceptions_Dashboard.pbix.

    python3 fix_new_dashboard.py <source.pbix> <output.pbix>

Report-layer only.  `DataModel` is copied byte-for-byte - it is an Analysis
Services backup and cannot be edited from outside Power BI Desktop.  Everything
that needs the model (the classifier, the account key, the calendar, the measure
sweep) ships as `model-updates-v2.tmdl` and `model-fixes-v2.pq`.

WHAT IT CHANGES

  1. Points every visual that displays the exception classification at
     `Dim_ExceptionReason` instead of the flat, misnamed columns on the fact
     tables.  `QV_Output[Exception Category]` is an alias of the *type*, not a
     category, so the two disagreed on 36.5% of rows.
  2. Turns the RESOLUTION QUEUE exception slicer into the same two-level
     Category -> Type hierarchy already on OVERVIEW.
  3. Clears three saved selections that were baked into the file: a slicer
     selection on RESOLUTION QUEUE, one on the hidden test page, and a stuck
     drill-through value on Exception Details.
  4. Snaps the OVERVIEW filter rail back onto the 68px slot pitch the other two
     pages use, so the three pages line up again.
  5. Strips the Purview sensitivity label so the file opens.

WHY THE LABEL HAS TO GO
    `SecurityBindings` is a DPAPI-protected binding computed over the whole
    package.  Any external edit invalidates it and Desktop then reports the file
    as corrupted.  The label here is Method=Standard, ContentBits=0 - a
    classification marking, not rights-management encryption.  THE OUTPUT IS AN
    UNCLASSIFIED COPY.  Re-apply Sensitivity > Internal Use Only in Desktop
    before the file leaves the machine.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

DIM = 'Dim_ExceptionReason'

OVERVIEW = '36b05998ad2a58e00312'
RESQ = '8db06a7e73968141bad0'
TRACES = '653efd92bd7e39c1655a'
EXC_DETAIL = 'df8b223ceb15c751a185'
TRACE_DETAIL = '59c21ff6d2b785b053b2'
TEST_PAGE = '11836c7f528e000638bc'

# visual -> (old entity, old property, new entity, new property)
REBIND = {
    (OVERVIEW, '1464f7f7b0a80df1e45b'):
        ('QV_Output', 'Exception Category', DIM, 'Exception Category'),
    (OVERVIEW, '2c1e56f341d91febe543'):
        ('QV_Output', 'Exception Type ', DIM, 'Exception Type'),
    (RESQ, '94c73661658330364cb6'):
        ('Resolutions Table', 'Exception Category', DIM, 'Exception Category'),
    (EXC_DETAIL, '4270694a1cb209308bd0'):
        ('QV_Output', 'Exception Category', DIM, 'Exception Category'),
}

# the OVERVIEW rail had drifted to an 80px pitch with 120/126/128 widths; the
# other two pages sit on the spec's 68px pitch at a uniform 126
RAIL_SLOTS = [196, 264, 332, 400, 468, 536, 604]
RAIL_X, RAIL_W, RAIL_H = 36, 126, 56

log = []


def note(msg):
    log.append(msg)
    print(' ', msg)


# ---------------------------------------------------------------- json helpers
def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def save(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write('\n')


def walk(node, fn):
    """Depth-first visit of every dict in the tree."""
    if isinstance(node, dict):
        fn(node)
        for v in node.values():
            walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            walk(v, fn)


def retarget(tree, old_e, old_p, new_e, new_p):
    """Repoint every Column reference, queryRef and selector from one field to
    another.  Leaves nativeQueryRef alone so the on-screen header text and any
    per-column formatting keep their identity."""
    old_ref = '%s.%s' % (old_e, old_p)
    new_ref = '%s.%s' % (new_e, new_p)
    hits = {'field': 0, 'queryRef': 0, 'selector': 0}

    def fix(d):
        col = d.get('Column')
        if isinstance(col, dict) and col.get('Property') == old_p:
            src = col.get('Expression', {}).get('SourceRef', {})
            if src.get('Entity') == old_e:
                src['Entity'] = new_e
                col['Property'] = new_p
                hits['field'] += 1
        if d.get('queryRef') == old_ref:
            d['queryRef'] = new_ref
            hits['queryRef'] += 1
        if d.get('metadata') == old_ref:
            d['metadata'] = new_ref
            hits['selector'] += 1

    walk(tree, fix)
    return hits


# ------------------------------------------------------------------ label strip
def strip_content_types(xml_bytes):
    x = xml_bytes.decode('utf-8')
    x2 = re.sub(r'<Override\s+PartName="/SecurityBindings"[^/]*/>', '', x)
    assert 'SecurityBindings' not in x2, 'Override not removed'
    return x2.encode('utf-8')


def strip_custom_props(xml_bytes):
    """Drop every MSIP_Label_* property but keep the part - _rels/.rels
    references it, so removing it would break the OPC package."""
    x = xml_bytes.decode('utf-8')
    x2 = re.sub(r'<property\b[^>]*name="MSIP_Label_[^"]*"[^>]*>.*?</property>',
                '', x, flags=re.S)
    assert 'MSIP' not in x2, 'MSIP property survived'
    pid = [1]

    def renum(m):
        pid[0] += 1
        return re.sub(r'pid="\d+"', 'pid="%d"' % pid[0], m.group(0))

    x2 = re.sub(r'<property\b[^>]*>.*?</property>', renum, x2, flags=re.S)
    return x2.encode('utf-8')


# ------------------------------------------------------------------------ edits
def vpath(root, page, visual):
    return os.path.join(root, 'Report', 'definition', 'pages', page,
                        'visuals', visual, 'visual.json')


def edit_rebinds(root):
    for (page, vis), (oe, op, ne, np_) in REBIND.items():
        p = vpath(root, page, vis)
        d = load(p)
        hits = retarget(d, oe, op, ne, np_)
        assert hits['field'], 'no field rebound in %s' % vis
        save(p, d)
        note('%s  %s[%s] -> %s[%s]  (%d fields, %d queryRefs, %d selectors)'
             % (vis[:8], oe, op, ne, np_,
                hits['field'], hits['queryRef'], hits['selector']))


def edit_resq_slicer(root):
    """Make the RESOLUTION QUEUE exception slicer the same two-level
    Category -> Type hierarchy as the one on OVERVIEW, and drop the selection
    that was saved into the file."""
    src = load(vpath(root, OVERVIEW, 'cffbba7ded6e5178b6c8'))['visual']
    p = vpath(root, RESQ, 'e455a62d2c8c6a259dbf')
    d = load(p)
    vis = d['visual']

    vis['query']['queryState']['Values']['projections'] = \
        copy.deepcopy(src['query']['queryState']['Values']['projections'])
    d['visual']['expansionStates'] = copy.deepcopy(src['expansionStates'])

    hdr = vis['objects'].setdefault('header', [{'properties': {}}])
    hdr[0]['properties']['text'] = {'expr': {'Literal': {'Value': "'Exception Reason'"}}}

    dropped = 'general' in vis['objects'] and \
              'filter' in vis['objects']['general'][0].get('properties', {})
    if dropped:
        del vis['objects']['general'][0]['properties']['filter']
        if not vis['objects']['general'][0]['properties']:
            del vis['objects']['general']

    save(p, d)
    note('e455a62d  slicer -> %s Category > Type hierarchy, header '
         '"Exception Reason"%s' % (DIM, ', saved selection cleared' if dropped else ''))


def edit_clear_test_slicer(root):
    p = vpath(root, TEST_PAGE, '8b12cfdfb2db35cc83d3')
    d = load(p)
    props = d['visual']['objects'].get('general', [{}])[0].get('properties', {})
    if 'filter' in props:
        del props['filter']
        if not props:
            del d['visual']['objects']['general']
        save(p, d)
        note('8b12cfdf  saved selection cleared on the hidden test page')


def edit_clear_drillthrough(root):
    """Exception Details had a live drill-through value baked in, so the page
    opened showing one hard-coded exception.  Trace Details is already clean -
    match it."""
    p = os.path.join(root, 'Report', 'definition', 'pages', EXC_DETAIL, 'page.json')
    d = load(p)
    changed = False
    for f in d.get('filterConfig', {}).get('filters', []):
        if f.get('howCreated') == 'Drillthrough' and 'filter' in f:
            del f['filter']
            changed = True
    if changed:
        save(p, d)
        note('Exception Details  stuck drill-through value cleared')


def edit_overview_rail(root):
    base = os.path.join(root, 'Report', 'definition', 'pages', OVERVIEW, 'visuals')
    rail = []
    for vid in sorted(os.listdir(base)):
        p = os.path.join(base, vid, 'visual.json')
        d = load(p)
        if (d.get('visual') or {}).get('visualType') == 'slicer':
            rail.append((d['position']['y'], vid, p, d))
    rail.sort()
    assert len(rail) <= len(RAIL_SLOTS), 'more slicers than rail slots'
    for slot, (_, vid, p, d) in zip(RAIL_SLOTS, rail):
        pos = d['position']
        before = (pos['x'], pos['y'], pos['width'], pos['height'])
        pos['x'], pos['y'], pos['width'], pos['height'] = RAIL_X, slot, RAIL_W, RAIL_H
        if before != (RAIL_X, slot, RAIL_W, RAIL_H):
            save(p, d)
            note('%s  rail slicer %s -> (%d, %d, %dx%d)'
                 % (vid[:8], before, RAIL_X, slot, RAIL_W, RAIL_H))


def edit_chrome(root):
    """Line up the two bits of page chrome that had drifted: the FILTERS label
    over the rail, and the page title in the header bar."""
    pages = {OVERVIEW: 'OVERVIEW', RESQ: 'RESOLUTION QUEUE', TRACES: 'ACTIVE TRACES',
             EXC_DETAIL: 'Exception Details', TRACE_DETAIL: 'Trace Details'}
    for page in pages:
        base = os.path.join(root, 'Report', 'definition', 'pages', page, 'visuals')
        for vid in sorted(os.listdir(base)):
            p = os.path.join(base, vid, 'visual.json')
            d = load(p)
            if (d.get('visual') or {}).get('visualType') != 'textbox':
                continue
            pos = d['position']
            before = (round(pos['x'], 1), round(pos['y'], 1), round(pos['height'], 1))
            if 150 < pos['y'] < 175:                      # rail "FILTERS" label
                want = (36.4, 162.3, 33.7)
                pos['x'], pos['width'] = 36.4, 125.9
            elif pos['y'] < 60:                           # page title
                want = (36.4, 26.6, 38.1)
                pos['x'] = 36.4
            else:
                continue
            pos['y'], pos['height'] = want[1], want[2]
            if before != want:
                save(p, d)
                note('%s  %s textbox %s -> %s' % (vid[:8], pages[page], before, want))


def edit_slicer_headers(root):
    """`'Vendor Acct # '` on ACTIVE TRACES had a trailing space the other two
    pages did not."""
    p = vpath(root, TRACES, '8f26d4b44e5b3fcca295')
    d = load(p)
    props = d['visual']['objects']['header'][0]['properties']
    cur = props['text']['expr']['Literal']['Value']
    want = "'Vendor Acct #'"
    if cur != want:
        props['text']['expr']['Literal']['Value'] = want
        save(p, d)
        note('8f26d4b4  slicer header %s -> %s' % (cur, want))


# ------------------------------------------------------------------------- main
def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    work = tempfile.mkdtemp(prefix='qvfix-')
    try:
        with zipfile.ZipFile(src) as z:
            z.extractall(work)

        print('report-layer edits')
        edit_rebinds(work)
        edit_resq_slicer(work)
        edit_clear_test_slicer(work)
        edit_clear_drillthrough(work)
        edit_overview_rail(work)
        edit_chrome(work)
        edit_slicer_headers(work)

        print('\nrepackaging')
        zin = zipfile.ZipFile(src)
        removed, rewritten, replaced, copied = [], [], 0, 0
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
            for info in zin.infolist():
                name = info.filename
                if name == 'SecurityBindings':
                    removed.append(name)
                    continue
                if name.startswith('Report/definition/') and name.endswith('.json'):
                    with open(os.path.join(work, name), 'rb') as f:
                        data = f.read()
                    replaced += 1
                else:
                    data = zin.read(name)
                    if name == '[Content_Types].xml':
                        data = strip_content_types(data)
                        rewritten.append(name)
                    elif name == 'docProps/custom.xml':
                        data = strip_custom_props(data)
                        rewritten.append(name)
                    copied += 1
                zi = zipfile.ZipInfo(name, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zo.writestr(zi, data)

        print('  parts copied    : %d' % copied)
        print('  parts rewritten : %d (%s)' % (replaced, 'Report/definition/*.json'))
        print('  parts removed   : %s' % (removed or 'none'))

        print('\nverification')
        zc = zipfile.ZipFile(out)
        assert zc.testzip() is None, 'corrupt entry'
        ct = zc.read('[Content_Types].xml').decode()
        cp = zc.read('docProps/custom.xml').decode()
        import xml.dom.minidom as md
        md.parseString(ct)
        md.parseString(cp)
        print('  SecurityBindings part          :', 'SecurityBindings' in zc.namelist())
        print('  SecurityBindings in [CT]       :', 'SecurityBindings' in ct)
        print('  MSIP_Label properties left     :', cp.count('MSIP_Label_'))
        print('  docProps/custom.xml still here :', 'docProps/custom.xml' in zc.namelist())
        print('  DataModel byte-identical       :',
              hashlib.sha256(zin.read('DataModel')).hexdigest()
              == hashlib.sha256(zc.read('DataModel')).hexdigest())
        n = 0
        for nm in zc.namelist():
            if nm.startswith('Report/definition/') and nm.endswith('.json'):
                json.loads(zc.read(nm))
                n += 1
        print('  report JSON parts parsed       :', n)
        print('\n  %d edits applied' % len(log))
        print('  output: %s  (%.2f MB)' % (out, os.path.getsize(out) / 1024 / 1024))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
