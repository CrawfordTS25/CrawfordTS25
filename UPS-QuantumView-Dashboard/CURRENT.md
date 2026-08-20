# Start here

**Your working file:** `QuantumView_Checkpoint_DateSlicersPassed.pbix` — the one on your
machine. Keep using it; there is no new `.pbix` this round and there shouldn't be.
**Guide:** `V3-RUNBOOK.md` — 9 steps, about 50 minutes
**Validation:** `QUERY-VALIDATION.md` — all 14 queries, measured

Everything outstanding is model-layer, so handing you back a label-stripped copy of a file
that already opens would cost you the sensitivity marking and gain you nothing.

## The one thing that's broken

```
Current_Open_Trace[FA #]        I287748
Trace_Contact_By_FA[FA #]        287748
```

The relationship is active and matches **0 of 95**. Every contact measure returns nothing
because of that one character. Strip the prefix and 66 of 66 FA-numbered traces resolve —
an FA email on all 66, a BOA cc on 61.

| | Now | After |
|---|---|---|
| Traces with a resolvable address | **0** via roster | **90 of 95** |
| — via FA roster | 0 | 66 |
| — via home-office map | 0 | 24 |
| With a BOA cc | 0 | 61 |
| Still blocked | 95 | 5, each naming its own reason |

## What you got right

The BOA→FA join is on the correct key — `BOA[FA ID] → FA[EMPLID]`, **99.9%**. Name-matching
would have given you 19.7%. `Trace_Contact_By_FA` is untouched by every script here.

## Also fixed this round

| | |
|---|---|
| `QV_RAW` reads `Archive\` only | `Folder.Files` recurses — once Morning\ and Afternoon\ exist under QV_Data, every export loads three times and Total Shipments triples silently |
| One 13:30 cutoff | `QV_RAW` said 17:00, `QV_Output` said 13:30. Same rows, two answers |
| Two account relationships reactivated | the Vendor Acct # slicer on ACTIVE TRACES currently filters nothing |
| `Dim Date` built | two date slicers are bound to a table that doesn't exist |
| `QV_Manifest` dedupe | still keeping the oldest row per shipment |
| 28 home-office `H#####` codes | route to their own map; the roster has none of them |
| `Trace_Notes` | 199 of 200 rows blank, joins 1 of 95 — moving to a SharePoint list |

## Document map

| File | Purpose |
|---|---|
| **`V3-RUNBOOK.md`** | **the current guide — follow this** |
| `QUERY-VALIDATION.md` | all 14 queries and every relationship, measured |
| `TRACE-NOTES-AND-MAILMERGE.md` | the notes list, both flows, FA/BOA addressing |
| `tools/model-fixes-v3.pq` | Power Query — archive source, contact keys, home office, notes, send queue |
| `tools/model-updates-v3.tmdl` | contact measures, coverage measures, `Dim Date` |
| `tools/qv-file-automation.ps1` | morning/afternoon sorting, PowerShell + Task Scheduler |
| `tools/checks/10-contact-routing.dax` | can every trace reach somebody |

### Earlier rounds — reasoning kept, instructions superseded

| File | |
|---|---|
| `UPS_QuantumView_Build_Instructions.pdf` · `NEW-BUILD-FIXES.md` | the v2 pass. `V3-RUNBOOK.md` continues from it |
| `WRITEBACK-AND-MAILMERGE.md` | the **exceptions queue** write-back — a different list from the tracing notes |
| `PBIT-GUIDE.md` | using a `.pbit` template with a `.pbix` |
| `MEASURE-SWEEP.md` · `ACCOUNT-DRILLDOWN.md` · `BUILD_NOTES.md` | measure audit, account derivation, layout rationale |
| `tools/model-fixes-v2.pq` | **§10 is still outstanding** — the trace date columns |
| `tools/model-updates-v2.tmdl` · `tools/model-fixes.pq` · `tools/model-updates.tmdl` | applied or superseded. Don't re-run |
