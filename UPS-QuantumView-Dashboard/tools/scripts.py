#!/usr/bin/env python3
"""
Write apply-ready fixes into the pbix's own script layer.

TMDLScripts/** and DAXQueries/** are saved-script parts: Power BI Desktop opens them
as tabs in TMDL view and DAX query view.  They are inert text until the user clicks
Apply / Run, so nothing here can stop the file opening or alter the DataModel on load.

Existing "Script 1" / "Query 1" / "Query 2" tabs are preserved; new tabs are appended.
"""
import json, os

SRC = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(SRC, 'pbix', 'build')

# the file's script parts are UTF-16-LE, CRLF, no BOM - match exactly
def write_script(relpath, text):
    full = os.path.join(BUILD, relpath)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    data = text.replace('\n', '\r\n').encode('utf-16-le')
    with open(full, 'wb') as f:
        f.write(data)
    return relpath

def write_json(relpath, obj):
    full = os.path.join(BUILD, relpath)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as f:
        f.write(json.dumps(obj, separators=(',', ':')).encode('utf-8'))
    return relpath


TMDL_FIX = """// =====================================================================
// Quantum View - measure fixes.  Review, then click Apply in TMDL view.
//
// Applies two changes and nothing else.  Both keep the existing measure
// names, so no visual needs rebinding - the numbers simply become correct.
//
// BEFORE YOU APPLY: confirm the literal "Resolved" below matches the exact
// string the production source emits.  These measures match on literals and
// return 0 silently on a mismatch.  This model already contains one such
// mismatch - the Resolutions measures spell the escalated state "Escalated"
// while Current_Open_Trace[Review Status] stores "Escalate".
// =====================================================================

createOrReplace

\tref table 'Resolutions Table'

\t\t/// Open exceptions aged 8+ days.  Excludes resolved items - without the
\t\t/// status filter this keeps counting cases that are already closed, which
\t\t/// only becomes visible once the queue starts resolving.
\t\tmeasure 'Aged 8 Plus Days' =
\t\t\t\t
\t\t\t\tCALCULATE(
\t\t\t\t    COUNTROWS('Resolutions Table'),
\t\t\t\t    'Resolutions Table'[Age Bucket] = "8+ Days",
\t\t\t\t    'Resolutions Table'[Tracker Status] <> "Resolved"
\t\t\t\t)
\t\t\tformatString: #,0

\t\t/// Average age of the OPEN queue.  Excludes resolved items for the same
\t\t/// reason as above.
\t\t///
\t\t/// NOTE: this is only as meaningful as [Age Days], which currently measures
\t\t/// days since the QV run that produced the row - not days since the exception
\t\t/// was raised.  See the "Check - Age Days anchor" DAX query.  Fixing that is
\t\t/// a Power Query change (tools/model-fixes.pq).
\t\tmeasure 'Avg Age (Days)' =
\t\t\t\t
\t\t\t\tCALCULATE(
\t\t\t\t    AVERAGE('Resolutions Table'[Age Days]),
\t\t\t\t    'Resolutions Table'[Tracker Status] <> "Resolved"
\t\t\t\t)
\t\t\tformatString: 0.0
"""

DAX_AGE = """// Check - Age Days anchor
//
// Does [Age Days] measure how long a case has been open, or just how long ago
// the QV run that produced the row happened?
//
// If it measured case age you would expect a smooth spread of values.  If every
// value instead lines up with one run date - and the row count per value matches
// the exception count of that run - then the column is anchored to the run, and
// [Avg Age (Days)] is averaging run recency rather than case age.

EVALUATE
\tADDCOLUMNS(
\t\tSUMMARIZE(
\t\t\t'Resolutions Table',
\t\t\t'Resolutions Table'[Age Days],
\t\t\t'Resolutions Table'[Run Date]
\t\t),
\t\t"Rows", CALCULATE( COUNTROWS('Resolutions Table') ),
\t\t"Earliest Manifest Date", CALCULATE( MIN('Resolutions Table'[Manifest Date]) ),
\t\t"Latest Manifest Date", CALCULATE( MAX('Resolutions Table'[Manifest Date]) )
\t)
\tORDER BY 'Resolutions Table'[Age Days] ASC
"""

DAX_RECON = """// Check - KPI reconciliation (master spec p.9)
//
// The spec asks for three ties before trusting the cards:
//   1. [Total Exceptions] equals your known row count
//   2. [Exception Rate] equals Total Exceptions / Total Shipments
//   3. aging on a known row equals the hours since its stamp
//
// Rows 1 and 2 are below.  Watch the three different answers to "how many
// exceptions" - distinct keys, rows flagged Is Issue, and total rows - and note
// that every row carries Status = "Exception" while a large share are flagged 0.
// Pick one grain and make every measure use it.

EVALUATE
\tROW(
\t\t"Total Exceptions (measure)",       [Total Exceptions],
\t\t"Total Shipments (measure)",        [Total Shipments],
\t\t"Exception Rate (measure)",         [Exception Rate],
\t\t"-- grain check --",                BLANK(),
\t\t"Distinct Exception Key",           DISTINCTCOUNT('QV_Output'[Exception Key]),
\t\t"Rows flagged Is Issue = 1",        CALCULATE( COUNTROWS('QV_Output'), 'QV_Output'[Is Issue] = 1 ),
\t\t"Rows in QV_Output",                COUNTROWS('QV_Output'),
\t\t"Distinct Tracking Number",         DISTINCTCOUNT('QV_Output'[Tracking Number]),
\t\t"-- denominator scope --",          BLANK(),
\t\t"Distinct Tracking in QV_Manifest", DISTINCTCOUNT('QV_Manifest'[Tracking Number]),
\t\t"Run dates covered by QV_Output",   DISTINCTCOUNT('QV_Output'[Run Date])
\t)
"""

DAX_VOCAB = """// Check - status vocabulary
//
// Every status measure matches on a hard-coded string.  A mismatch returns 0
// silently, which is indistinguishable from "nothing has resolved yet".  Run this
// against production before trusting Resolved / Escalated on any card.
//
// Expect to find that the Resolutions measures look for "Escalated" while the
// trace table stores "Escalate" - two spellings of one state in one model.

EVALUATE
\tUNION(
\t\tSELECTCOLUMNS(
\t\t\tSUMMARIZE( 'Resolutions Table', 'Resolutions Table'[Tracker Status] ),
\t\t\t"Table",  "Resolutions Table",
\t\t\t"Column", "Tracker Status",
\t\t\t"Value",  'Resolutions Table'[Tracker Status],
\t\t\t"Rows",   CALCULATE( COUNTROWS('Resolutions Table') )
\t\t),
\t\tSELECTCOLUMNS(
\t\t\tSUMMARIZE( 'Resolutions Table', 'Resolutions Table'[Age Bucket] ),
\t\t\t"Table",  "Resolutions Table",
\t\t\t"Column", "Age Bucket",
\t\t\t"Value",  'Resolutions Table'[Age Bucket],
\t\t\t"Rows",   CALCULATE( COUNTROWS('Resolutions Table') )
\t\t),
\t\tSELECTCOLUMNS(
\t\t\tSUMMARIZE( 'Current_Open_Trace', 'Current_Open_Trace'[Review Status] ),
\t\t\t"Table",  "Current_Open_Trace",
\t\t\t"Column", "Review Status",
\t\t\t"Value",  'Current_Open_Trace'[Review Status],
\t\t\t"Rows",   CALCULATE( COUNTROWS('Current_Open_Trace') )
\t\t)
\t)
"""

DAX_NOTES = """// Check - Trace_Notes join health
//
// Trace_Notes keys on Exception Key.  Run this after re-pointing the merge
// (tools/model-fixes.pq) to confirm notes actually land on trace rows.
//
// "Traces with a note" should be > 0 and should track the number of notes your
// team has actually written.  If it stays at 0 the keys are not matching - most
// likely a whitespace or casing difference, or the Exception Key was re-minted on
// one side only.

EVALUATE
\tROW(
\t\t"Trace rows",                COUNTROWS('Current_Open_Trace'),
\t\t"Traces with a Trace Status", CALCULATE(
\t\t\t\tCOUNTROWS('Current_Open_Trace'),
\t\t\t\tNOT ISBLANK('Current_Open_Trace'[Trace_Notes.Trace Status]) ),
\t\t"Traces with a note",        CALCULATE(
\t\t\t\tCOUNTROWS('Current_Open_Trace'),
\t\t\t\tNOT ISBLANK('Current_Open_Trace'[Trace_Notes.Notes]) ),
\t\t"Traces with a follow-up",   CALCULATE(
\t\t\t\tCOUNTROWS('Current_Open_Trace'),
\t\t\t\tNOT ISBLANK('Current_Open_Trace'[Trace_Notes.Next Follow-up Date]) )
\t)
"""


def main():
    written = []
    # --- TMDL: keep the user's Script 1, append the fix as Script 2
    written.append(write_script('TMDLScripts/Script%202.tmdl', TMDL_FIX))
    written.append(write_json('TMDLScripts/.pbi/tmdlScripts.json',
                              {"version": "1.0.0",
                               "tabOrder": ["Script 1", "Script 2"],
                               "defaultTab": "Script 2"}))
    # --- DAX: keep Query 1 / Query 2, append four checks
    for name, body in (('Query%203.dax', DAX_AGE), ('Query%204.dax', DAX_RECON),
                       ('Query%205.dax', DAX_VOCAB), ('Query%206.dax', DAX_NOTES)):
        written.append(write_script('DAXQueries/' + name, body))
    written.append(write_json('DAXQueries/.pbi/daxQueries.json',
                              {"version": "1.0.0",
                               "tabOrder": ["Query 1", "Query 2", "Query 3",
                                            "Query 4", "Query 5", "Query 6"],
                               "defaultTab": "Query 3"}))
    for w in written:
        print('  wrote', w)


if __name__ == '__main__':
    main()
