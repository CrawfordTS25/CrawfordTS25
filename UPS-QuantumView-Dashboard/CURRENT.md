# Start here

**Deliverable:** `NEWQuantum_View_Exceptions_Dashboard_fixed.pbix`
**Guide:** `NEW-BUILD-FIXES.md` — what was wrong, plus 10 ordered Desktop steps, ~40 min

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

## What's still ahead — all of it in `NEW-BUILD-FIXES.md` §8

Turn off Auto Date/Time · delete 4 fields · work `tools/model-fixes-v2.pq` §1–9 · add
`A25T52` to the workbook · apply `tools/model-updates-v2.tmdl` · type the trace dates ·
relate the calendar · repoint the date slicers · verify · re-apply the label.

## Document map

| File | Purpose |
|---|---|
| **`NEW-BUILD-FIXES.md`** | **the current guide — follow this** |
| `WRITEBACK-AND-MAILMERGE.md` | List schema, Power Apps formulas, both flows, the blocked-tenant fallback |
| `tools/model-fixes-v2.pq` | Power Query: the missing function, the taxonomy, the dedupe fix, account keys, trace dates |
| `tools/model-updates-v2.tmdl` | the one model script — measures, relationships, `Dim Date` |
| `tools/fix_new_dashboard.py` | the report-layer pass, re-runnable against the original |
| `tools/checks/*.dax` | 6 read-only verification queries |
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
