# Start here

**Deliverable:** `NEWQuantum_View_Exceptions_Dashboard_fixed.pbix`
**Guide:** `UPS_QuantumView_Build_Instructions.pdf` — 21 pages, print it
**Same thing in markdown:** `NEW-BUILD-FIXES.md` — 12 ordered Desktop steps, ~55 min
**Script pack:** `quantum-view-scripts.zip` — copy code from these, never from the PDF

Built from your `NEWQuantum_View_Exceptions_Dashboard.pbix` upload — the one with
`Dim_Account` and `Dim_ExceptionReason` in it. **`DataModel` is byte-identical to that
upload**; every change in the file itself is in the report layer. The sensitivity label
is removed so it opens — re-apply *Internal Use Only · Standard* before it leaves your
machine.

## The four things that were actually broken

| | |
|---|---|
| **The next refresh fails** | an unapplied query edit calls `fnClassifyException`, which doesn't exist anywhere in the model |
| **`Shipper Match Key` can't carry a relationship** | 5 accounts share the name "EDWARD JONES MAIL SERVICES" — 23 accounts, 17 keys, so the "one" side isn't unique. This is the dimension error you hit |
| **`Dim_ExceptionReason` loses 16% of the queue** | 1,406 rows have a null Exception Type and land on the blank member |
| **The resolution queue shows each exception's *oldest* state** | `Table.Distinct` ignores the unbuffered `Table.Sort` — on all 4,075 repeat exceptions the oldest row survived, not the newest |

Full evidence and row counts in `NEW-BUILD-FIXES.md`.

## What's already done inside the file

| | Where |
|---|---|
| 5 visuals repointed at `Dim_ExceptionReason` | OVERVIEW · RESOLUTION QUEUE · Exception Details |
| RESOLUTION QUEUE slicer → Category → Type hierarchy | matches OVERVIEW exactly |
| 3 baked-in selections cleared (2 slicers, 1 stuck drill-through) | file-wide |
| OVERVIEW filter rail snapped back to the 68px pitch | all three rails now identical |
| Page titles, FILTERS labels, slicer header text squared up | all 5 visible pages |
| Sensitivity label removed | file-wide |

Verified: 180 field references resolve · 0 overlaps · nothing off-canvas · 106 report JSON
parts parse · `DataModel` SHA-256 unchanged.

## Two additions

| | |
|---|---|
| **`Branch_Contacts` rebuilt** | it was loading 500 rows of pure nulls — row 1 of the sheet isn't the header row. Now finds the header, detects the email column by content, keys on `FA #`, and can't silently return empty again |
| **Per-source refresh stamps** | `Refresh Status` carries the last-modified time of all five source files. `[Data As Of]` renders it in the title bar and names any source that's past its own SLA; the trace pages get the tracing workbook's stamp instead of the QV export's |

One structural finding that changes the mail-merge plan: **the roster can only reach the
trace side.** The exceptions queue carries no FA identity to join to — `Ship To Name` is
"EDWARD JONES" on 35,126 of 46,594 rows. Exception recipients have to come from the
SharePoint List's `Owner`.

## What's still ahead — all of it in `NEW-BUILD-FIXES.md` §9

Turn off Auto Date/Time · delete 4 fields · work `tools/model-fixes-v2.pq` §1–9 · add
`A25T52` to the workbook · apply `tools/model-updates-v2.tmdl` · type the trace dates ·
relate the calendar · run `tools/contacts-and-freshness.pq` + `.tmdl` · repoint the 5
title-bar cards and the date slicers · verify · re-apply the label.

## Document map

| File | Purpose |
|---|---|
| **`UPS_QuantumView_Build_Instructions.pdf`** | **the printable guide — follow this** |
| `NEW-BUILD-FIXES.md` | the same content in markdown |
| `WRITEBACK-AND-MAILMERGE.md` | List schema, Power Apps formulas, both flows, the blocked-tenant fallback |
| `PBIT-GUIDE.md` | using a `.pbit` template with a `.pbix` |
| `quantum-view-scripts.zip` | the scripts and checks, packaged for copy-paste |
| `tools/build_instructions_pdf.py` | regenerates the PDF |
| `tools/model-fixes-v2.pq` | Power Query: the missing function, the taxonomy, the dedupe fix, account keys, trace dates |
| `tools/model-updates-v2.tmdl` | the one model script — measures, relationships, `Dim Date` |
| `tools/contacts-and-freshness.pq` | roster discovery + rebuild, and the `Refresh Status` source scan |
| `tools/contacts-and-freshness.tmdl` | the roster relationship and the nine freshness / contact measures |
| `tools/fix_new_dashboard.py` | the report-layer pass, re-runnable against the original |
| `tools/checks/*.dax` | 7 read-only verification queries |
| `UPS_Acct_Info_.xlsx` | 24 accounts, `A25T52` added, table range extended |

### Earlier passes — kept for the reasoning, superseded as instructions

| File | |
|---|---|
| `RUNBOOK.md` | the v5 Desktop guide. `NEW-BUILD-FIXES.md` §8 replaces it |
| `MEASURE-SWEEP.md` | all 25 measures audited, rate-grain reasoning, SharePoint/API sourcing |
| `ACCOUNT-DRILLDOWN.md` | why the account derives from the tracking number; the `A25T52` decision |
| `BUILD_NOTES.md` | layout/theme rationale from the first pass |
| `Quantum_View_Exceptions_Dashboard_v5.pbix` | the 31 July deliverable |
| `tools/model-updates.tmdl` · `tools/model-fixes.pq` | the v5 scripts — **don't run these and the v2 pair** |
