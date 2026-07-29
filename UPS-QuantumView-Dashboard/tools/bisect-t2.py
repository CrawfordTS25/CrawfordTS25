#!/usr/bin/env python3
"""
Third rung of the bisect ladder.

  T0 control      original definition, repackaged, label stripped     -> OPENS
  T1 geometry     original visuals, only `position` rewritten         -> OPENS
  T2 (this)       full rebuild MINUS the 31 visuals that were invented.
                  Keeps every formatting, query and page.json edit made to the
                  61 visuals that already existed in the source file.

  T2 opens  -> the fault is in one of the 31 invented visuals
               (11 cardVisual, 9 textbox, 5 shape, 2 pageNavigator, 2 slicer, 2 tableEx)
  T2 fails  -> the fault is in the formatting / query rewrites applied to existing
               visuals, i.e. among the 89 unproven formatting properties

Run tools/build.py first so pbix/build/ exists.
"""
import os, glob, json, shutil, zipfile, re

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get('QV_WORK', SRC)
ORIG = os.path.join(WORK, 'pbix', 'dash.pbix')
FULL = os.path.join(WORK, 'pbix', 'build', 'Report', 'definition')
BASE = os.path.join(WORK, 'pbix', 'extracted', 'Report', 'definition')
STAGE = os.path.join(WORK, 'pbix', 't2')

orig_ids = {p.split(os.sep)[-2] for p in glob.glob(BASE + '/pages/*/visuals/*/visual.json')}
if os.path.isdir(STAGE):
    shutil.rmtree(STAGE)
shutil.copytree(FULL, STAGE)

dropped = 0
for vf in glob.glob(STAGE + '/pages/*/visuals/*/visual.json'):
    if vf.split(os.sep)[-2] not in orig_ids:
        shutil.rmtree(os.path.dirname(vf)); dropped += 1

alive = {p.split(os.sep)[-2] for p in glob.glob(STAGE + '/pages/*/visuals/*/visual.json')}
for pj in glob.glob(STAGE + '/pages/*/page.json'):
    d = json.load(open(pj))
    vis = d.get('visualInteractions', [])
    keep = [v for v in vis if v['source'] in alive and v['target'] in alive]
    if len(keep) != len(vis):
        d['visualInteractions'] = keep
        json.dump(d, open(pj, 'w'), indent=2)

sub = lambda pat, s: re.sub(pat, '', s, flags=re.S)
new = sorted(('Report/definition/' + os.path.relpath(os.path.join(r, f), STAGE).replace(os.sep, '/'),
              os.path.join(r, f))
             for r, _, fs in os.walk(STAGE) for f in fs)

out = os.path.join(WORK, 'T2_no_new_visuals.pbix')
zin = zipfile.ZipFile(ORIG)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
    emitted = False
    for info in zin.infolist():
        n = info.filename
        if n == 'SecurityBindings':
            continue
        if n.startswith('Report/definition/'):
            if not emitted:
                for arc, f in new:
                    zi = zipfile.ZipInfo(arc, date_time=info.date_time)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = info.external_attr
                    zo.writestr(zi, open(f, 'rb').read())
                emitted = True
            continue
        data = zin.read(n)
        if n == '[Content_Types].xml':
            data = sub(r'<Override\s+PartName="/SecurityBindings"[^/]*/>', data.decode()).encode()
        elif n == 'docProps/custom.xml':
            data = sub(r'<property\b[^>]*name="MSIP_Label_[^"]*"[^>]*>.*?</property>', data.decode()).encode()
        zi = zipfile.ZipInfo(n, date_time=info.date_time)
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zo.writestr(zi, data)

z = zipfile.ZipFile(out)
assert z.testzip() is None
assert z.read('DataModel') == zin.read('DataModel')
print('dropped %d invented visuals; %d rebuilt originals remain' % (dropped, len(alive)))
print('%s  %d entries  %.2f MB  DataModel identical'
      % (os.path.basename(out), len(z.namelist()), os.path.getsize(out) / 1024 / 1024))
