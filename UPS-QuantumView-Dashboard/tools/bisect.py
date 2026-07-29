#!/usr/bin/env python3
"""
Isolate why the rebuilt .pbix will not open.  Builds two test files.

  T0_control.pbix    the ORIGINAL report definition, byte-for-byte, repackaged by the
                     same pipeline, label stripped.  Zero content changes.
                     Opens  -> packaging + label strip are fine, the bug is my JSON
                     Fails  -> the bug is in the packaging or the label strip

  T1_geometry.pbix   the ORIGINAL visual.json files with ONLY `position` rewritten to
                     the shared skeleton.  No formatting, query, filter or page-level
                     edits; no visuals added or removed.
                     Opens  -> the bug is in my formatting/query rewrites
                     Fails  -> even repositioning breaks it
"""
import os, re, json, shutil, zipfile, copy, hashlib

SRC = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(SRC, 'pbix', 'dash.pbix')
EXTRACTED = os.path.join(SRC, 'pbix', 'extracted')

BAR       = (24, 24, 1232, 44)
PAGETITLE = (40, 33, 344, 26)
NAV       = (396, 30, 456, 32)
KPI       = [(x, 76, 232, 78) for x in (24, 274, 524, 774, 1024)]
RAIL      = (24, 162, 150, 534)
SLICER    = [(36, y, 126, 56) for y in (196, 264, 332, 400, 468)]
BACKBTN   = (36, 196, 126, 40)
R1L, R1R  = (186, 162, 525, 165), (723, 162, 533, 165)
R2L, R2R  = (186, 339, 525, 150), (723, 339, 533, 150)
R2F, R3F  = (186, 339, 1070, 150), (186, 501, 1070, 195)
R_FULL    = (186, 162, 1070, 534)
QUEUE     = (186, 162, 452, 534)
NOTES     = (650, 162, 606, 268)
AUTO      = (650, 442, 606, 254)
AUTO_TXT  = (662, 478, 582, 204)

P1, P2, P3, P4, P5 = ('36b05998ad2a58e00312', '8db06a7e73968141bad0',
                      '653efd92bd7e39c1655a', 'df8b223ceb15c751a185',
                      '59c21ff6d2b785b053b2')

# original visual id -> new rectangle.  Nothing else about the visual is touched.
LAYOUT = {
    P1: {'4da0197c9b15e9fcdee3': BAR,  'a3bef9a088c640cac9a5': NAV,
         '4a35913fbc6f170b4401': RAIL,
         '91dc8596a6a3e77d9a7f': KPI[0], '8dbf7ab199138b09a595': KPI[1],
         '657395733f2a0ff045ca': KPI[2], '9884e2f3edafbda08b7c': KPI[3],
         'cffbba7ded6e5178b6c8': SLICER[0], '971aec585965e35d1d2a': SLICER[1],
         '17930b0a22d5e0a60080': SLICER[2], 'd872338a678c76aa123c': SLICER[3],
         '1464f7f7b0a80df1e45b': R1L, '440cc3a8f7f81d9c576c': R1R,
         'c62f0b0a1aec5c80209a': R2L, 'd93bc956c906aebdc346': R2R,
         '2c1e56f341d91febe543': R3F},
    P2: {'6762454c15985878b8bf': BAR,  '92709acc168ebeeacd6f': NAV,
         '856a89397330ad739e86': RAIL,
         'fc07cf5e3aa2329fc5b4': KPI[0], '7d02710dd71cb7cd8591': KPI[1],
         '5307d49ca1a3cb931126': KPI[2], '703c466f2cf08c73b301': KPI[3],
         'd9a5a7f4aa0a6e8a4cbf': KPI[4],
         '0a319b677d4122a4f3d7': SLICER[0], '3ef728007d0c5e44223e': SLICER[1],
         'd663dc3095675939688c': SLICER[2], '3f36e922db732d9c200e': SLICER[3],
         'e455a62d2c8c6a259dbf': SLICER[4],
         '94c73661658330364cb6': QUEUE, '081b1e0fe3ce6519f6f3': NOTES,
         'e1f6002360ed4f6634ae': AUTO,  'e875e461e9d0dbea1eba': AUTO_TXT},
    P3: {'572346907c66c3dbb540': NAV, 'ce4cae3d1b67430233de': RAIL,
         'c2bc2d2fd7c4d1741e13': KPI[0], '0920059c7b37d8512b58': KPI[1],
         'c9a3ca9a9c20da00e2d8': KPI[2], 'd53bfbaba715840d83d3': KPI[3],
         '4b74e94189d28cacb8ba': KPI[4],
         'd376b3092b445db580be': SLICER[0], 'a242a0248e438d4d2b64': SLICER[1],
         '778c6be08d859756d38d': SLICER[2], '95d6e3bbccd96b0ce0a0': SLICER[3],
         'e27002cd13ca83c7c733': R1L, 'b2d6b5d6b97b94bc088e': R1R,
         '0d4f83b789800eb00017': R2F, 'a4bc518d4ca9ec4a273b': R3F},
    P4: {'79c52cc25902bb5aae7b': BACKBTN, '4270694a1cb209308bd0': R_FULL},
    P5: {'8db4c211d065035d6cc7': BACKBTN, 'ef87d8fa8e9402ba0740': PAGETITLE,
         '68be8dae928922660be0': KPI[0], '0453e784bd69a6400023': KPI[1],
         '3c93366b03c823705205': KPI[2], '2c344afd2152211b302a': KPI[3],
         '29f2a33cb6288a21c71d': KPI[4],
         'c7070b727e998883b560': SLICER[1], '9d328cdc0910195b6792': SLICER[2],
         '700ac056c940a85a0766': R1L, 'debeba175ca945a67bb7': R1R,
         'b60180314e31c19a2b01': R2F, '1abbaa2e40b29e7d3820': R3F},
}


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


def build(out_name, transform=None):
    """Repackage the original, optionally transforming Report/definition parts."""
    out = os.path.join(SRC, out_name)
    zin = zipfile.ZipFile(ORIG)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
        for info in zin.infolist():
            name = info.filename
            if name == 'SecurityBindings':
                continue
            data = zin.read(name)
            if name == '[Content_Types].xml':
                data = strip_ct(data)
            elif name == 'docProps/custom.xml':
                data = strip_props(data)
            elif transform and name.startswith('Report/definition/'):
                data = transform(name, data)
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zo.writestr(zi, data)
    z = zipfile.ZipFile(out)
    assert z.testzip() is None
    assert z.read('DataModel') == zin.read('DataModel')
    print('  %-22s %d entries, %.2f MB, DataModel identical' %
          (out_name, len(z.namelist()), os.path.getsize(out) / 1024 / 1024))
    return out


def reposition(name, data):
    parts = name.split('/')
    if not name.endswith('visual.json'):
        return data
    page, vid = parts[3], parts[5]
    rect = LAYOUT.get(page, {}).get(vid)
    if not rect:
        return data
    d = json.loads(data)
    p = d['position']
    p['x'], p['y'], p['width'], p['height'] = rect
    return json.dumps(d, indent=2).encode('utf-8')


if __name__ == '__main__':
    print('building bisect files (label stripped on both):')
    build('T0_control.pbix')
    build('T1_geometry.pbix', reposition)

    # report what T1 actually moved
    z = zipfile.ZipFile(os.path.join(SRC, 'T1_geometry.pbix'))
    moved = kept = 0
    for n in z.namelist():
        if n.endswith('visual.json'):
            page, vid = n.split('/')[3], n.split('/')[5]
            if LAYOUT.get(page, {}).get(vid): moved += 1
            else: kept += 1
    print('\nT1: %d visuals repositioned, %d left exactly where they were' % (moved, kept))
    print('    no visual added, removed, restyled or rebound')
