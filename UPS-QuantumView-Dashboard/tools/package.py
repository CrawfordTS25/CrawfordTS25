#!/usr/bin/env python3
"""
Repackage the .pbix from the rebuilt report definition.

    python3 package.py                  # faithful repackage (will NOT open - see below)
    python3 package.py --strip-label    # also remove the sensitivity label

WHY --strip-label EXISTS
    The source .pbix carries a Microsoft Purview sensitivity label
    (6426_Internal_Use_Only_Standard_6426).  Its SecurityBindings part is a
    DPAPI-protected binding computed over the whole package, so ANY external edit
    invalidates it and Power BI Desktop reports the file as corrupted - even an edit
    that leaves DataModel byte-identical.

    The label is Method=Standard, ContentBits=0: a classification marking, not
    rights-management encryption (which is why the package is readable at all).
    Stripping it removes the marking and the tamper binding so the rebuilt file opens.

    THE OUTPUT IS AN UNCLASSIFIED COPY.  It no longer carries "Internal Use Only -
    Standard".  Re-apply the label in Desktop (Sensitivity > Internal Use Only) before
    sharing or publishing; tenant policy may also re-apply it automatically on save.

    The supported alternative, which keeps the label throughout, is the .pbip route -
    see apply-to-pbip.py.
"""
import os, re, zipfile, hashlib, sys

SRC = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(SRC, 'pbix', 'dash.pbix')
BUILD = os.path.join(SRC, 'pbix', 'build')
PREFIX = 'Report/definition/'
SCRIPT_DIRS = ('TMDLScripts/', 'DAXQueries/')
LABEL_PART = 'SecurityBindings'

STRIP = '--strip-label' in sys.argv[1:]
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard%s.pbix'
                        % ('_unlabelled' if STRIP else ''))

new_parts = []
for sub in (('Report', 'definition'), ('TMDLScripts',), ('DAXQueries',)):
    for root, _, files in os.walk(os.path.join(BUILD, *sub)):
        for fn in files:
            full = os.path.join(root, fn)
            new_parts.append((os.path.relpath(full, BUILD).replace(os.sep, '/'), full))
new_parts.sort()


def strip_content_types(xml_bytes):
    """Drop the SecurityBindings Override so the package stops declaring the part."""
    x = xml_bytes.decode('utf-8')
    x2 = re.sub(r'<Override\s+PartName="/SecurityBindings"[^/]*/>', '', x)
    assert 'SecurityBindings' not in x2, 'Override not removed'
    return x2.encode('utf-8')


def strip_custom_props(xml_bytes):
    """Remove every MSIP_Label_* property.  Keep the part itself - _rels/.rels
    references it, so deleting it would break the OPC package."""
    x = xml_bytes.decode('utf-8')
    x2 = re.sub(r'<property\b[^>]*name="MSIP_Label_[^"]*"[^>]*>.*?</property>', '', x, flags=re.S)
    assert 'MSIP' not in x2, 'MSIP property survived'
    # renumber any survivors from pid=2 as OPC requires
    pid = [1]
    def renum(m):
        pid[0] += 1
        return re.sub(r'pid="\d+"', 'pid="%d"' % pid[0], m.group(0))
    x2 = re.sub(r'<property\b[^>]*>.*?</property>', renum, x2, flags=re.S)
    return x2.encode('utf-8')


zin = zipfile.ZipFile(ORIG)
copied = replaced = 0
removed_parts, rewritten_parts = [], []

with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zout:
    emitted = False
    for info in zin.infolist():
        name = info.filename
        if name.startswith(SCRIPT_DIRS):
            continue                                   # re-emitted from the build tree
        if name.startswith(PREFIX):
            if not emitted:
                for arcname, full in new_parts:
                    zi = zipfile.ZipInfo(arcname, date_time=info.date_time)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = info.external_attr
                    with open(full, 'rb') as f:
                        zout.writestr(zi, f.read())
                    replaced += 1
                emitted = True
            continue

        data = zin.read(name)
        if STRIP:
            if name == LABEL_PART:
                removed_parts.append(name)
                continue
            if name == '[Content_Types].xml':
                data = strip_content_types(data); rewritten_parts.append(name)
            elif name == 'docProps/custom.xml':
                data = strip_custom_props(data); rewritten_parts.append(name)

        zi = zipfile.ZipInfo(name, date_time=info.date_time)
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zout.writestr(zi, data)
        copied += 1

# ---- verification -----------------------------------------------------------
zo = zipfile.ZipFile(OUT)
assert zo.testzip() is None, 'corrupt entry'

print('mode                   : %s' % ('STRIP LABEL' if STRIP else 'faithful repackage'))
print('parts copied unchanged : %d' % copied)
print('report + script parts  : %d' % replaced)
if STRIP:
    print('parts removed          : %s' % (removed_parts or 'none'))
    print('parts rewritten        : %s' % (rewritten_parts or 'none'))
    ct = zo.read('[Content_Types].xml').decode()
    cp = zo.read('docProps/custom.xml').decode()
    print()
    print('  SecurityBindings part present      :', LABEL_PART in zo.namelist())
    print('  SecurityBindings declared in [CT]  :', 'SecurityBindings' in ct)
    print('  MSIP_Label properties remaining    :', cp.count('MSIP_Label_'))
    print('  docProps/custom.xml still a part   :', 'docProps/custom.xml' in zo.namelist(),
          '(referenced by _rels/.rels)')
    print('  custom.xml well-formed             :', end=' ')
    import xml.dom.minidom as md
    md.parseString(cp); print(True)
    md.parseString(ct)

print()
print('DataModel byte-identical to original :',
      hashlib.sha256(zin.read('DataModel')).hexdigest()
      == hashlib.sha256(zo.read('DataModel')).hexdigest())
for part in ('Connections', 'Settings', 'Metadata', 'Report/LinguisticSchema',
             'DiagramLayout', 'Version'):
    same = zin.read(part) == zo.read(part)
    if not same:
        print('  !! %s changed' % part)
print('output: %s  (%.2f MB)' % (OUT, os.path.getsize(OUT) / 1024 / 1024))

import json
for n in sorted(zo.namelist()):
    if n.endswith('.json') and n.startswith('Report/definition'):
        json.loads(zo.read(n))
print('all report JSON parses cleanly')
