#!/usr/bin/env python3
"""
Apply the rebuilt report definition to a Power BI project (.pbip).

WHY THIS EXISTS
    Quantum_View_Exceptions_Dashboard.pbix carries a Microsoft Purview sensitivity
    label ("Internal Use Only - Standard").  Its SecurityBindings part is a
    DPAPI-protected binding computed over the whole package, so ANY external edit -
    including a byte-perfect one that leaves DataModel untouched - invalidates it and
    Power BI Desktop refuses to open the file.  A .pbix with a label cannot be edited
    outside Desktop.  That is the control working as designed.

    A .pbip stores the same PBIR report definition as plain files on disk with no
    security binding, so it can be edited programmatically.  Desktop re-applies the
    label when you save back to .pbix.

USAGE
    1. Open the ORIGINAL .pbix in Power BI Desktop
    2. File > Save as > Power BI project (.pbip)
    3. python3 apply-to-pbip.py "<path>/Quantum_View_Exceptions_Dashboard.Report"
    4. Open the .pbip in Desktop, review, then Save as .pbix

    The existing definition/ folder is backed up first; nothing is overwritten in
    place without a copy alongside it.
"""
import os, shutil, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DEFINITION = os.path.join(os.path.dirname(HERE), 'report-definition')


def fail(msg):
    print('ERROR: ' + msg)
    sys.exit(1)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        fail('pass the path to the .Report folder of your .pbip project')

    report_dir = os.path.abspath(argv[1])
    # accept either the .pbip file or the .Report folder
    if report_dir.lower().endswith('.pbip'):
        stem = report_dir[:-5]
        report_dir = stem + '.Report'
    if not os.path.isdir(report_dir):
        fail('not a folder: %s' % report_dir)
    if not report_dir.endswith('.Report'):
        fail('expected a folder ending in .Report, got %s' % os.path.basename(report_dir))

    target = os.path.join(report_dir, 'definition')
    if not os.path.isdir(target):
        fail('no definition/ folder inside %s - is this a PBIR-format project?\n'
             '       In Desktop check File > Options > Preview features > '
             '"Power BI Project (.pbip) save option" and the PBIR report format.' % report_dir)
    if not os.path.isdir(SRC_DEFINITION):
        fail('rebuilt definition not found at %s' % SRC_DEFINITION)

    # sanity: the project must reference a semantic model, which this script never touches
    pbir = os.path.join(report_dir, 'definition.pbir')
    if os.path.isfile(pbir):
        try:
            ref = json.load(open(pbir)).get('datasetReference', {})
            print('semantic model reference (left untouched): %s' % json.dumps(ref))
        except Exception:
            pass

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(report_dir, 'definition.backup-%s' % stamp)
    shutil.copytree(target, backup)
    print('backed up your current definition -> %s' % os.path.basename(backup))

    shutil.rmtree(target)
    shutil.copytree(SRC_DEFINITION, target)

    pages = os.path.join(target, 'pages')
    n_pages = len([d for d in os.listdir(pages) if os.path.isdir(os.path.join(pages, d))])
    n_vis = sum(len(os.listdir(os.path.join(pages, d, 'visuals')))
                for d in os.listdir(pages)
                if os.path.isdir(os.path.join(pages, d, 'visuals')))
    print('applied rebuilt definition: %d pages, %d visuals' % (n_pages, n_vis))
    print()
    print('Next: open the .pbip in Power BI Desktop.')
    print('  - if a visual fails to load, tell me which one; the fix is one property')
    print('  - the sensitivity label is re-applied when you Save as .pbix')
    print('  - to revert: delete definition/ and rename %s back' % os.path.basename(backup))


if __name__ == '__main__':
    main(sys.argv)
