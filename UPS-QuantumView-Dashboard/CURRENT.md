# Start here

**Deliverable:** `Quantum_View_Exceptions_Dashboard_v5.pbix`
**Guide:** `RUNBOOK.md` — 9 ordered Desktop steps, ~45 min

`v5` is built from your 31 July upload. **`DataModel` is byte-identical to it** — no
measure, column, relationship or query has been altered. Every change in v5 is in the
report layer; all model work is still ahead of you and is what the runbook covers.

## What v5 already contains

| | Where |
|---|---|
| Account / Vendor slicer, rail slot 6 | OVERVIEW · RESOLUTION QUEUE · ACTIVE TRACES |
| Manifest Date slicer, rail slot 7 | OVERVIEW · RESOLUTION QUEUE |
| Exceptions by Account / Vendor, worst-first | OVERVIEW |
| 5 ACTIVE TRACES KPI cards rebound, leftover filters removed | ACTIVE TRACES |
| KPI labels uppercased, drifted card realigned | all |
| `TEST-Acct Sliver` hidden, sensitivity label removed | file-wide |

Verified: 174 field references resolve · 0 overlaps · nothing off-canvas · no saved
slicer selections.

## What is still to do — all of it in RUNBOOK.md

Delete 3 duplicate measures · apply `tools/model-updates.tmdl` (account keys, aging
fixes, rate grain, `Dim Date`, 6 relationships) · type the trace date columns
(`tools/model-fixes.pq` §9) · relate the calendar to the trace side · repoint the date
slicers · re-apply the sensitivity label · publish.

## Document map

| File | Purpose |
|---|---|
| **`RUNBOOK.md`** | **the ordered guide — follow this** |
| `MEASURE-SWEEP.md` | all 25 measures audited, rate-grain reasoning, SharePoint/API sourcing |
| `ACCOUNT-DRILLDOWN.md` | why the account derives from the tracking number; the `A25T52` decision |
| `BUILD_NOTES.md` | historical — layout/theme rationale from the first pass |
| `tools/model-updates.tmdl` | the one model script |
| `tools/model-fixes.pq` | Power Query: trace dates §9, ingest and dedupe §6–8 |
| `tools/checks/*.dax` | read-only verification queries |
| `UPS_Acct_Info_.xlsx` | 24 accounts, `A25T52` added, table range extended |
