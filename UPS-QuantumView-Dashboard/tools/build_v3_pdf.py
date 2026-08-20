#!/usr/bin/env python3
"""
Build the v3 printable instruction pack.

    python3 build_v3_pdf.py <output.pdf>

Layout helpers are shared with build_instructions_pdf.py (the v2 pack) so the two
look like the same document family. Only the content differs.
"""
import sys

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate

import build_instructions_pdf as B
from build_instructions_pdf import (bullets, callout, checks, code, decorate, eyebrow,
                                    gap, grid, h1, h2, h3, lede, p, step)

PW, PH = LETTER


def flatten(items):
    out = []
    for i in items:
        out.extend(flatten(i)) if isinstance(i, list) else out.append(i)
    return out


def story():
    s = []

    # ============================================================ COVER
    s += [gap(4), eyebrow('Build instructions · v3'),
          h1('Contacts, file automation and trace notes'),
          lede('For QuantumView_Checkpoint_DateSlicersPassed.pbix. Nine steps, about '
               '50 minutes. Everything here is model-layer, so there is no new .pbix — '
               'keep working in your own file.')]

    s += [callout(
        'No new .pbix this round, on purpose',
        'Your file already opens and still carries its sensitivity label. Handing back a '
        'label-stripped copy would cost you the marking and gain you nothing — every fix '
        'below is a query or a measure. The one report-layer thing that is broken fixes '
        'itself: two date slicers are bound to \'Dim Date\'[Date] and that table does not '
        'exist. Step 5 creates it and they light up.', 'info')]

    s += [h2('What you got right, so I did not touch it')]
    s += [p('The roster build is the hard part of this and it is correct. '
            'Branch_Contacts_All to Branch_Contacts to Trace_Contact_By_FA is the right '
            'shape, and critically the BOA-to-FA join is on the right key:')]
    s += grid([
        ['Join', 'Resolves'],
        ['<font face="Courier">BOA[FA ID] &#8594; FA[EMPLID]</font>',
         '<b>24,972 of 25,007 &#183; 99.9%</b>'],
        ['<font face="Courier">BOA[FA Name] &#8594; FA[Contact Name]</font>',
         '4,930 of 25,007 &#183; 19.7%'],
    ], [0.55, 0.45])
    s += [p('Name-matching was the obvious approach and it would have quietly lost four '
            'fifths of the pairings. <b>Trace_Contact_By_FA is untouched by every script '
            'in this pack.</b>')]

    s += [h2('At a glance')]
    s += grid([
        ['What is wrong', 'Impact', 'Fixed by'],
        ['Trace FA numbers never match the roster — 0 of 95',
         '<font color="#D64545"><b>Every contact measure empty</b></font>', 'Step 3'],
        ['Trace_Notes reads an abandoned workbook',
         '<font color="#D64545"><b>199 blank rows, 1 of 95 join</b></font>', 'Step 9'],
        ['QV_RAW points at a different QV_Data than your path sheet',
         '<font color="#D64545"><b>Possibly reading a dead folder</b></font>', 'Step 2'],
        ['QV_RAW would read every export once per subfolder',
         '<font color="#E8A13A"><b>Total Shipments multiplies</b></font>', 'Step 2'],
        ['Morning/afternoon defined twice, at 17:00 and 13:30',
         '<font color="#E8A13A"><b>Two answers, same rows</b></font>', 'Step 2'],
        ['Two account relationships silently deactivated',
         '<font color="#E8A13A"><b>Vendor slicer filters nothing</b></font>', 'Step 1'],
        ['Dim Date does not exist but two slicers bind to it',
         '<font color="#E8A13A"><b>Two dead slicers</b></font>', 'Step 5'],
        ['QV_Manifest dedupe still unbuffered',
         '<font color="#5A6472"><b>Oldest row per shipment wins</b></font>', 'Step 2'],
    ], [0.56, 0.26, 0.18])

    # ============================================================ THE BREAK
    s += [PageBreak(), eyebrow('Section 1'), h1('The one thing that is broken')]

    s += code([
        'Current_Open_Trace[FA #]        I287748',
        'Trace_Contact_By_FA[FA #]        287748',
    ])
    s += [p('The relationship between them is <b>active and matches 0 of 95 rows</b>. That '
            'single character is why Selected Branch Email, Selected FA Email, Selected BOA '
            'Emails and Unreachable Traces all come back empty, and why the Unreachable card '
            'on ACTIVE TRACES reads 95 — everything is unreachable.')]
    s += [p('Strip the prefix and <b>66 of 66</b> FA-numbered traces match, resolving an FA '
            'address on all 66 and a BOA cc on 61.')]

    s += [h2('The prefix is a type tag')]
    s += [p('One column is carrying two identifier spaces and one data-entry miss:')]
    s += grid([
        ['Prefix', 'What it is', 'Traces', 'Routes to'],
        ['<font face="Courier">I######</font>', 'a real FA number', '66', 'the roster'],
        ['<font face="Courier">H#####</font>', 'a home-office department code', '28',
         'its own map — the roster has none of them'],
        ['<font face="Courier">0</font>', 'a data-entry miss', '1',
         'nowhere, and it should say so'],
    ], [0.14, 0.34, 0.12, 0.40])

    s += [h3('The 28 home-office rows are not FAs')]
    s += [p('Tested against every candidate column in the roster:')]
    s += grid([
        ['Against', 'Matches'],
        ['EMPLID', '0 of 28'],
        ['JP Number', '0 of 28'],
        ['FA ID', '0 of 28'],
        ['FA #', '0 of 28'],
        ['Branch Number', '5 of 28 — coincidence, not a route'],
    ], [0.4, 0.6])
    s += [p('All 28 are <font face="Courier">Location = Campus Ship / World Ship / '
            'Kimler</font> — home-office departmental shipments. Only <b>11 distinct '
            'codes</b>, and <b>seven already have a confirmed address</b> sitting in '
            'CONTACT INFO on their own trace rows. Those are seeded in '
            'Home_Office_Contacts; four need somebody to fill in an address.')]

    s += [h2('What it is worth')]
    s += grid([
        ['', 'Now', 'After'],
        ['Traces with a resolvable address', '<b>0</b> via roster', '<b>90 of 95</b>'],
        ['— via FA roster', '0', '66'],
        ['— via home-office map', '0', '24'],
        ['With a BOA cc', '0', '61 of 66'],
        ['Still blocked', '95', '5, each naming its own reason'],
    ], [0.42, 0.28, 0.30])
    s += [p('<b>Contact Route</b> is a new column that makes the branch explicit rather than '
            'leaving it implied in a chain of fallbacks, so a trace that cannot be addressed '
            'says <i>why</i> instead of quietly not appearing in the queue.')]

    # ============================================================ PATHS
    s += [PageBreak(), eyebrow('Section 2'), h1('Your paths, reconciled')]
    s += [lede('Three of the locations on your sheet disagree with what the queries actually '
               'read. Full detail in PATHS.md.')]

    s += [h2('1 · QV_RAW is pointed at a different folder')]
    s += grid([
        ['', 'Path'],
        ['Your path sheet',
         '…\\Administrative Services-Solutions\\<b>Power BI Reporting\\Report Data</b>\\QV_Data'],
        ['QV_RAW in the .pbix',
         '…\\Administrative Services-Solutions\\<b>Quantum View</b>\\QV_Data'],
    ], [0.24, 0.76])
    s += [p('Different parent folder. Check which one your last successful refresh actually '
            'read — <b>if the old path still resolves, you have two QV_Data folders and only '
            'one of them is being fed.</b>')]

    s += [h2('2 · It must point at Archive, not QV_Data')]
    s += [p('<font face="Courier">Folder.Files</font> <b>recurses</b>, and QV_Data already '
            'contains Morning QV, Afternoon QV, Processed and Failed. Pointed at QV_Data the '
            'query reads every export once per folder it appears in — Total Shipments '
            'multiplies and nothing errors. It would also try to parse '
            'QV_Automation_Helper_Lists.xlsx as a 34-column CSV.')]
    s += [p('This is not hypothetical. Those folders exist on your share today, which is what '
            'turns Archive-only from a precaution into a requirement.')]

    s += [h2('3 · The notes query is reading a dead file')]
    s += code([
        'Trace_Notes reads   ...\\Report Data\\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx',
        'The notes live in   Trace_Master_Streamlined_  (SharePoint)',
    ])
    s += [p('<b>That is the entire explanation for 199 blank rows out of 200 and a join that '
            'lands on 1 of 95 traces.</b> Nothing was broken — the query was pointed at the '
            'abandoned copy. 199 blank rows is what an abandoned sheet looks like once '
            'somebody formats past the data.')]

    s += [callout(
        'Move the trace list off the personal OneDrive before rollout',
        '<font face="Courier">https://ejprod-my.sharepoint.com/<b>personal</b>/p258239_edwardjones_com/…</font>'
        '<br/><br/>'
        'That is one individual\'s OneDrive, not a team site. It is <b>deprovisioned when '
        'that person leaves or changes roles</b> — read-only, then gone, typically after a '
        '30 to 93 day retention window, and the notes history goes with it. Service refresh '
        'also has to run on <b>that person\'s</b> credentials: it cannot be moved to a '
        'service account, because the site belongs to the human. Every other '
        '"use a service account" note in this build is a policy choice; this one is a '
        'structural block.<br/><br/>'
        'The query works against it today and I am not holding the build up over it. But copy '
        'the list to a team site and change SiteUrl — ten minutes, and every column name '
        'survives the move.', 'warn')]

    s += [h2('Rosters — left alone deliberately')]
    s += [p('Your sheet gives <font face="Courier">X:\\hrdi_report_pickup</font>; '
            'Branch_Contacts_All reads <font face="Courier">Report Data\\Rosters</font>. The '
            'second one <b>works</b> — 46,080 rows across 21,073 FAs and 25,007 BOAs, '
            'refreshed 06:49 the morning you sent the file. Breaking a working roster to '
            'remove a copy step is a bad trade this close to rollout, so it is documented '
            'rather than changed.')]
    s += [p('Watch <font face="Courier">[Latest Roster Modified]</font>. If it stops moving, '
            'the copy from the pickup folder stopped.')]

    s += [callout(
        'Two constants now live in two files',
        'The <b>13:30 cutoff</b> and the <b>QV_Data root</b> are hard-coded in both '
        'qv-file-automation.ps1 and section 1 of model-fixes-v3.pq. Change one and you must '
        'change the other, or the share and the dashboard will disagree about which run a '
        'file belongs to — and nothing will error.<br/><br/>'
        '<b>Use UNC, not X:.</b> Drive letters are mapped per logon session. The Power BI '
        'Service has none, and a scheduled task running as the service account with nobody '
        'logged on has none either — it fails with a path-not-found that looks like a '
        'permissions problem and is not.', 'info')]

    # ============================================================ RUNBOOK
    s += [PageBreak(), eyebrow('Section 3'), h1('The runbook')]
    s += [lede('Nine steps, about 50 minutes. Do them in order — each gates the next. Keep a '
               'copy of your .pbix before you start.')]
    s += [callout('Copy code from the script files, not from this PDF',
                  'A PDF renders straight quotes as curly quotes and hyphens as en-dashes. M '
                  'and DAX both reject those, and the error message will not tell you that is '
                  'what happened. Open the .pq, .tmdl and .ps1 files from '
                  'quantum-view-v3-scripts.zip in Notepad++, VS Code or even Notepad.',
                  'info')]

    # -- 1
    s += step(1, 'Model view — four edits', '3 min')
    s += [p('TMDL cannot script these safely. Power BI allows only one <b>active</b> '
            'relationship between a given pair of tables, so scripting a new one while the '
            'old is live either errors or deactivates something you wanted.')]
    s += [p('<b>a. Delete</b> <font face="Courier">Current_Open_Trace[FA #] &#8594; '
            'Trace_Contact_By_FA[FA #]</font>. It matches 0 of 95. Step 3 replaces it with '
            '[FA Key].')]
    s += [p('<b>b. Set inactive</b> the two <font face="Courier">Exception Key &#8594; '
            'Resolutions Table</font> relationships, then <b>set active</b> the two '
            '<font face="Courier">Account Key &#8594; Dim_Account</font> ones.')]
    s += [p('Both account relationships are inactive right now, which is why the '
            '<b>Vendor Acct # slicer on ACTIVE TRACES filters nothing</b>. Power BI '
            'deactivated them when Trace to Resolutions created a second path to '
            'Dim_Account. Measured on your data:')]
    s += grid([
        ['Path to Dim_Account', 'Covers'],
        ['<font face="Courier">Account Key &#8594; Dim_Account</font> (direct)', '<b>95 of 95</b>'],
        ['<font face="Courier">Exception Key &#8594; Resolutions &#8594; Dim_Account</font>', '60 of 95'],
    ], [0.6, 0.4])
    s += [p('The direct one wins. The Exception Key link stays in the model, inactive, for '
            'USERELATIONSHIP when you genuinely want "traces for the exceptions I selected".')]
    s += [p('<b>c. Untick Enable load</b> on Branch_Contacts_All — 46,080 staging rows, '
            'referenced by no visual, and the third side of a triangle holding '
            'Trace_Contact_By_FA[Branch Number] inactive. <b>d. Set active</b> that '
            'relationship once (c) removes the ambiguity.')]
    s += checks(['Model view shows no dashed relationship you did not intend.'])

    # -- 2
    s += step(2, 'Power Query — the file side', '10 min')
    s += [p('<font face="Courier">Home &gt; Transform data</font>, then '
            '<b>scripts/model-fixes-v3.pq</b>.')]
    s += grid([
        ['§', 'Query', 'What changes'],
        ['1', 'QV_RAW <i>(replace)</i>',
         'Corrected path, reads Archive only, computes the run window once at 13:30.'],
        ['2', 'QV_Output <i>(two steps)</i>',
         'Delete #"QV Run Time" and #"QV Run Date" — they now come from §1. Rename '
         'Run Window to Run Time so no visual needs rebinding.'],
        ['3', 'QV_Manifest <i>(two steps)</i>',
         'Table.Buffer on the dedupe — it is still keeping the oldest row per shipment; the '
         'fix landed on Resolutions Table but not here. And move Account Key from DAX to M.'],
    ], [0.06, 0.24, 0.70])
    s += checks(['<b>Total Shipments is unchanged</b> after the refresh. If it jumped, the '
                 'Archive path is wrong.'])

    # -- 3
    s += step(3, 'Power Query — the contact fix', '10 min')
    s += grid([
        ['§', 'Query', 'What changes'],
        ['4', 'Current_Open_Trace <i>(add at end)</i>',
         'Three columns: FA Key, Home Office Code, Contact Route.'],
        ['5', 'Trace_Active <i>(add at end)</i>',
         'The identical block, so the two trace tables stay interchangeable. If only one can '
         'resolve a contact they will disagree the first time somebody builds on the wrong one.'],
        ['6', 'Home_Office_Contacts <i>(new)</i>',
         'Eleven codes; seven already answered by addresses in your own CONTACT INFO column. '
         'Reads a sheet from QV_Automation_Helper_Lists.xlsx if one exists, falls back to the '
         'inline seed if not — so it works unedited today and moves to the workbook without '
         'anyone touching M.'],
    ], [0.06, 0.26, 0.68])
    s += checks(['Contact Route shows four values — Case contact, FA roster, Home office, '
                 'Unroutable — with <b>Unroutable at exactly 1</b>.'])

    # -- 4
    s += step(4, 'Power Query — the send queue', '5 min')
    s += [p('<b>§8 Mail_Merge_Queue</b> — new. One row per trace, already addressed. '
            'Send To and Send Cc are semicolon strings, which is exactly what the Outlook '
            'connector\'s To and Cc fields take — no splitting, no lookups in the flow.')]
    s += [p('Every join, fallback and exclusion decision lives in M where you can read it, '
            'rather than scattered across flow actions where you cannot. <b>Blocked Reason</b> '
            'is the point of the table: a trace that cannot be emailed says why, in a column.')]
    s += [p('Needs §4 and §6 in place first.')]
    s += checks(['95 rows — 90 with a Send To, 5 with a Blocked Reason.'])

    # -- 5
    s += step(5, 'Apply the model script', '5 min')
    s += [p('<font face="Courier">View &gt; TMDL view</font> &#8594; paste '
            '<b>scripts/model-updates-v3.tmdl</b> &#8594; read it &#8594; <b>Apply</b>.')]
    s += [p('Contact measures rewritten onto the working keys — <b>same names, so nothing '
            'needs rebinding</b> — plus the coverage measures, the mail-merge measures, '
            'Dim Date and its four date roles.')]
    s += checks([
        'Dim Date appears and starts in 2026. <b>The two date slicers work.</b>',
        'Mark it: Dim Date &gt; Table tools &gt; Mark as date table &gt; Date.',
    ])

    # -- 6
    s += step(6, 'Verify', '5 min')
    s += [p('<font face="Courier">View &gt; DAX query view</font>. '
            '<b>checks/10-contact-routing.dax</b> is the one that matters.')]
    s += grid([
        ['', 'Now', 'Should read'],
        ['Total Active Traces', '95', '95'],
        ['<b>Contactable Traces</b>', '<b>0 via roster</b>', '<b>90</b>'],
        ['Unreachable Traces', '95', '5'],
        ['BOA Coverage', '0', '61'],
        ['Sendable + Blocked', '—', '90 + 5'],
    ], [0.4, 0.3, 0.3])
    s += [p('The fourth query in that file is the blocked worklist — four home-office codes '
            'with no address, plus the one trace whose FA # is the literal string "0". It is '
            'short, actionable, and every row names its own fix.')]

    # -- 7
    s += step(7, 'Clean up', '2 min')
    s += grid([
        ['Untick Enable load, or delete', 'Why'],
        ['Branch_Contacts_Old', '500 rows, every column null on every row'],
        ['Exception Reason Map',
         'loaded <b>and</b> the source of Dim_ExceptionReason — the same 14 rows twice in the '
         'Fields pane, carrying two relationships that exist only as inactive'],
        ['Res_Tracker', '1,040 rows of unpromoted Column1 to Column14'],
    ], [0.3, 0.7])
    s += [p('And add <b>A25T52</b> to <font face="Courier">…\\Report Data\\UPS Acct Info '
            '.xlsx</font>, extending the table range to A1:L25. It is still the entire '
            'unmatched remainder — 755 manifest rows and 102 queue rows.')]

    # -- 8
    s += step(8, 'The file automation', '15 min, once')
    s += [p('<b>scripts/qv-file-automation.ps1</b>, using the folders you already have:')]
    s += code([
        'Report Data\\QV_Data\\',
        '    Archive\\                        <- exports land here. THE MODEL READS THIS.',
        '    Morning QV\\                     <- copies, before 13:30',
        '    Afternoon QV\\                   <- copies, at or after',
        '    Processed\\_processed.csv        <- state, so re-runs are cheap',
        '    Failed\\                         <- copies of problems, plus a .reason.txt',
        '    _logs\\                          <- one log per month',
        '    QV_Automation_Helper_Lists.xlsx <- not touched by the script',
    ])
    s += [p('It <b>copies, never moves</b>, and never writes to Archive at all. Archive stays '
            'the source of truth, so if the script fails, is disabled, or double-fires, the '
            'dashboard is unaffected. That is the whole design — and it is why even a corrupt '
            'file gets <i>copied</i> to Failed rather than moved out of Archive.')]
    s += bullets([
        '<font face="Courier">.\\qv-file-automation.ps1 -WhatIf</font> — see what it would do',
        'Run it for real, check _logs\\',
        'Schedule it — Task Scheduler, 09:00 and 15:00, repeating every 30 minutes for 2 '
        'hours so a late export gets picked up. Full instructions in the script footer.',
    ], bullet='1')
    s += [p('<b>Use the service account, not your login</b> — same rule as the gateway '
            'credentials. And <b>UNC, not X:</b>.')]

    # -- 9
    s += step(9, 'Notes, then the flows', '5 min + the flows')
    s += [p('<b>§7</b> repoints Trace_Notes at Trace_Master_Streamlined_. Paste the first two '
            'steps, load, and look at the column names SharePoint gives you — they are '
            '<b>internal</b> names, so "Trace Status" arrives as '
            '<font face="Courier">Trace_x0020_Status</font>. Correct the renames, then paste '
            'the rest.')]
    s += [p('Then replace the single CASE # merge in Current_Open_Trace with two passes: '
            'Exception Key first, CASE # for whatever is left, <b>both sides normalised</b>. '
            'One key is stable and the other is the one analysts actually type — you need '
            'both, or you get today\'s 1 of 95.')]
    s += [p('TRACE-NOTES-AND-MAILMERGE.md has the list schema, both flow definitions, the '
            'templates and the blocked-tenant fallback. <b>Check first whether your tenant '
            'permits Flows</b> — it decides whether that part is two days or two weeks.')]

    # ============================================================ OPEN
    s += [PageBreak(), eyebrow('Section 4'), h1('Still open after this')]
    s += grid([
        ['', 'Why it is still open'],
        ['Trace date columns are still text',
         'model-fixes-v2.pq §10. Every date column on both trace tables loads as text, so no '
         'calendar can reach the trace side — no date slicer, no trend, no SLA maths on the '
         'page whose entire job is SLA. This is the largest remaining structural gap.'],
        ['Four Home_Office_Contacts addresses',
         'H03130, H05057, H05150, H44804. Filling them takes reachability from 90 to 94 of 95.'],
        ['One trace with FA # = "0"',
         'Data entry on the trace sheet. It can never resolve to a contact.'],
        ['Move the trace list to a team site',
         'Personal OneDrive cannot be refreshed by a service account and is deprovisioned '
         'when its owner leaves.'],
        ['Root Cause / Next Action / Notes 0% populated',
         'The exceptions-side write-back — a different list from the tracing notes. '
         'WRITEBACK-AND-MAILMERGE.md.'],
        ['Exception grain decision',
         '8,583 distinct keys vs 29,957 rows flagged Is Issue vs 45,614 total rows. Needs a '
         'business answer, not a build.'],
        ['A25T52 in the account workbook',
         'The entire unmatched remainder on both fact tables.'],
    ], [0.3, 0.7], header=False)

    s += [h2('The document pack')]
    s += grid([
        ['File', 'What it is'],
        ['<b>V3-RUNBOOK.md</b>', 'this document, in markdown'],
        ['<b>PATHS.md</b>', 'every location, and the three that disagree with the model'],
        ['<b>QUERY-VALIDATION.md</b>', 'all 14 queries and every relationship, measured'],
        ['<b>TRACE-NOTES-AND-MAILMERGE.md</b>',
         'the notes list, both flows, FA/BOA addressing rules'],
        ['<b>WRITEBACK-AND-MAILMERGE.md</b>',
         'the <b>exceptions-side</b> write-back. A different list — do not merge the two'],
        ['<b>PBIT-GUIDE.md</b>', 'using a .pbit template with a .pbix'],
        ['<b>CURRENT.md</b>', 'the entry point'],
    ], [0.34, 0.66])

    s += [callout(
        'The v2 pack is superseded',
        'UPS_QuantumView_Build_Instructions.pdf and NEW-BUILD-FIXES.md describe the previous '
        'file — NEWQuantum_View_Exceptions_Dashboard_fixed.pbix — and a 12-step runbook whose '
        'model work you have already applied. Keep them for the reasoning behind the '
        'classifier, the dedupe direction and the account key derivation. <b>Do not follow '
        'them as instructions, and do not re-run model-fixes-v2.pq sections 1 to 9 or '
        'model-updates-v2.tmdl</b> — the only part of v2 still outstanding is section 10, the '
        'trace date columns.', 'warn')]

    return s


def build(out):
    doc = BaseDocTemplate(out, pagesize=LETTER,
                          leftMargin=B.MARGIN, rightMargin=B.MARGIN,
                          topMargin=B.MARGIN + 14, bottomMargin=B.MARGIN,
                          title='UPS Quantum View - v3 Build Instructions',
                          author='Quantum View build')
    frame = Frame(B.MARGIN, B.MARGIN, B.CW, PH - 2 * B.MARGIN - 14, id='body')
    doc.addPageTemplates([PageTemplate(id='p', frames=[frame], onPage=decorate)])
    doc.build(flatten(story()))


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'v3-instructions.pdf')
    print('written')
