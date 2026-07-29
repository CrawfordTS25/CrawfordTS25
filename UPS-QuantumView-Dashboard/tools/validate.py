"""Structural + consistency validation of the rebuilt Report layer."""
import json, glob, os, collections, sys
B = 'pbix/build/Report/definition/pages'
ORIG = 'pbix/extracted/Report/definition/pages'
order = ['36b05998ad2a58e00312','8db06a7e73968141bad0','653efd92bd7e39c1655a',
         'df8b223ceb15c751a185','59c21ff6d2b785b053b2']
errs = []

# ---- 1. every formatting property value must be an expr object / solid color / known struct
def check_props(f, group, props):
    for k, v in props.items():
        if k == 'paragraphs':                       # textbox rich text
            if not isinstance(v, list): errs.append(f'{f}: {group}.{k} not a list')
            continue
        if not isinstance(v, dict):
            errs.append(f'{f}: {group}.{k} = {v!r} is not an expression object'); continue
        if 'expr' in v or 'solid' in v or 'image' in v or 'filter' in v: continue
        errs.append(f'{f}: {group}.{k} has unexpected shape {list(v)}')

def walk_objects(f, container):
    for group, entries in (container or {}).items():
        if not isinstance(entries, list):
            errs.append(f'{f}: object group {group} is not a list'); continue
        for e in entries:
            if not isinstance(e, dict) or 'properties' not in e:
                errs.append(f'{f}: {group} entry missing properties'); continue
            check_props(f, group, e['properties'])
            for extra in set(e) - {'properties', 'selector'}:
                errs.append(f'{f}: {group} entry has unknown key {extra}')

files = sorted(glob.glob(B + '/*/visuals/*/visual.json'))
for vf in files:
    d = json.load(open(vf)); rel = '/'.join(vf.split('/')[-3:-1])
    v = d['visual']
    walk_objects(rel, v.get('objects'))
    walk_objects(rel, v.get('visualContainerObjects'))
    for k in ('$schema', 'name', 'position', 'visual'):
        if k not in d: errs.append(f'{rel}: missing {k}')
    if d['name'] != vf.split('/')[-2]: errs.append(f'{rel}: name != folder')
    p = d['position']
    if not (0 <= p['x'] and p['x']+p['width'] <= 1280 and 0 <= p['y'] and p['y']+p['height'] <= 720):
        errs.append(f'{rel}: out of canvas {p}')

# ---- 2. component style uniformity, per component role AND per visual type
def strip(o, drop):
    if isinstance(o, dict): return {k: strip(v, drop) for k, v in o.items() if k not in drop}
    if isinstance(o, list): return [strip(x, drop) for x in o]
    return o

roles = collections.defaultdict(lambda: collections.defaultdict(list))
for vf in files:
    d = json.load(open(vf)); v = d['visual']; z = d['position']['z']; vt = v['visualType']
    role = ('KPI card' if 1000 <= z < 1005 else 'slicer' if 1100 <= z < 1105 and vt=='slicer'
            else 'back button' if vt == 'actionButton'
            else 'work panel:' + vt if z >= 2000 else 'chrome:%s@%d' % (vt, z))
    o = json.loads(json.dumps(v.get('objects', {})))
    if 'values' in o:   # drop the per-table Web URL conditional-formatting entry
        o['values'] = [e for e in o['values'] if 'webURL' not in e.get('properties', {})]
    style = json.dumps(strip({'o': o, 'c': v.get('visualContainerObjects', {})},
                             {'text', 'color', 'fill', 'areaColor', 'paragraphs'}),
                       sort_keys=True)
    roles[role][style].append('%s/%s' % (vf.split('/')[-4][:6], d['name'][:8]))

print('COMPONENT STYLE UNIFORMITY')
for role in sorted(roles):
    var = roles[role]; n = sum(len(x) for x in var.values())
    ok = len(var) == 1
    print('  %-28s %3d instances  %s' % (role, n, 'UNIFORM' if ok else '%d VARIANTS' % len(var)))
    if not ok:
        for i, (s, mem) in enumerate(var.items()): print('        variant %d: %s' % (i, mem))
        errs.append('style drift in ' + role)

# ---- 3. skeleton geometry identical on all pages
sk = {}
for p in order:
    sk[p] = tuple(sorted((json.load(open(vf))['position']['z'],
                          tuple(json.load(open(vf))['position'][k] for k in ('x','y','width','height')),
                          json.load(open(vf))['visual']['visualType'])
                         for vf in glob.glob(f'{B}/{p}/visuals/*/visual.json')
                         if json.load(open(vf))['position']['z'] < 1100))
if len(set(sk.values())) != 1:
    errs.append('skeleton geometry differs between pages')
print('\nSKELETON GEOMETRY IDENTICAL ON ALL 5 PAGES:', len(set(sk.values())) == 1)

# ---- 4. page.json shape
for p in order:
    pg = json.load(open(f'{B}/{p}/page.json'))
    if (pg['width'], pg['height']) != (1280, 720): errs.append(f'{p}: canvas != 1280x720')
    if pg['displayName'] != pg['displayName'].strip(): errs.append(f'{p}: displayName has padding')
    for vi in pg.get('visualInteractions', []):
        for side in ('source', 'target'):
            if not os.path.isdir(f'{B}/{p}/visuals/{vi[side]}'):
                errs.append(f'{p}: visualInteraction {side} {vi[side]} does not exist')
meta = json.load(open(f'{B}/pages.json'))
for p in meta['pageOrder']:
    if not os.path.isdir(f'{B}/{p}'): errs.append(f'pages.json references missing page {p}')
if set(meta['pageOrder']) != set(order): errs.append('pageOrder set mismatch')
if meta['activePageName'] not in meta['pageOrder']: errs.append('activePageName invalid')

# ---- 5. no leftover slicer selections / stray visual filters
for vf in files:
    d = json.load(open(vf)); v = d['visual']
    for e in v.get('objects', {}).get('general', []):
        if 'filter' in e.get('properties', {}):
            errs.append('%s: slicer still carries a saved selection' % d['name'])

print('\nERRORS: %d' % len(errs))
for e in errs: print('  !', e)
sys.exit(1 if errs else 0)
