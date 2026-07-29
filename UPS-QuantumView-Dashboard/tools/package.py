#!/usr/bin/env python3
"""Repackage the .pbix: every part outside Report/definition/ is copied byte-for-byte
from the original archive; Report/definition/** comes from the rebuilt tree."""
import os, zipfile, hashlib, sys

SRC = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(SRC, 'pbix', 'dash.pbix')
BUILD = os.path.join(SRC, 'pbix', 'build')
OUT = os.path.join(SRC, 'Quantum_View_Exceptions_Dashboard.pbix')
PREFIX = 'Report/definition/'

new_parts = []
for root, _, files in os.walk(os.path.join(BUILD, 'Report', 'definition')):
    for fn in files:
        full = os.path.join(root, fn)
        new_parts.append((os.path.relpath(full, BUILD).replace(os.sep, '/'), full))
new_parts.sort()

zin = zipfile.ZipFile(ORIG)
copied = replaced = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zout:
    emitted = False
    for info in zin.infolist():
        if info.filename.startswith(PREFIX):
            if not emitted:                       # emit the new report definition here
                for arcname, full in new_parts:
                    zi = zipfile.ZipInfo(arcname, date_time=info.date_time)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = info.external_attr
                    with open(full, 'rb') as f:
                        zout.writestr(zi, f.read())
                    replaced += 1
                emitted = True
            continue
        zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zout.writestr(zi, zin.read(info.filename))
        copied += 1

# ---- verification -----------------------------------------------------------
zo = zipfile.ZipFile(OUT)
bad = zo.testzip()
assert bad is None, 'corrupt entry: %s' % bad

orig_names = set(zin.namelist())
out_names = set(zo.namelist())
untouched = {n for n in orig_names if not n.startswith(PREFIX)}
drift = [n for n in sorted(untouched)
         if hashlib.sha256(zin.read(n)).hexdigest() != hashlib.sha256(zo.read(n)).hexdigest()]

print('parts copied unchanged : %d' % copied)
print('report definition parts: %d (was %d)' % (replaced, len(orig_names - untouched)))
print('byte-identical non-report parts: %s' % ('ALL' if not drift else drift))
print('DataModel size in/out  : %d / %d' % (len(zin.read('DataModel')), len(zo.read('DataModel'))))
print('output: %s  (%.2f MB)' % (OUT, os.path.getsize(OUT) / 1024 / 1024))

import json
for n in sorted(out_names):
    if n.endswith('.json') and n.startswith('Report/definition'):
        json.loads(zo.read(n))
print('all report JSON parts parse cleanly: %d files' % sum(
    1 for n in out_names if n.startswith('Report/definition')))
sys.exit(1 if drift else 0)
