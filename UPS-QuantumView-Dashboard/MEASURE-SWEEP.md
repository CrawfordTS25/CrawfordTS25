# Measure sweep, source flexibility, and what's left for full completion

**File:** `Quantum_View_Exceptions_Dashboard_v3.pbix` — label removed so it opens;
re-apply *Internal Use Only · Standard* before sharing. `DataModel` byte-identical to
your upload, 169 field references resolve, no overlaps.

---

## 1. The headline: four of five ACTIVE TRACES cards were wrong

When the new `Current_Open_Trace` measures were dropped in, the visual-level filters
from the earlier build stayed behind. Each card then applied its condition **twice** —
once inside the measure, once on the visual:

| Card | Was showing | Should show | Cause |
|---|---|---|---|
| Never Reviewed | **0** | 28 | measure `Review Status = "Never Reviewed"` **and** filter `= "Escalate"` — an impossible intersection |
| In Transit | **0** | 27 | measure `In Transit / Out for Delivery` **and** filter `Review Status = "Never Reviewed"` |
| Overdue Traces | **12** | 86 | measure `Overdue = TRUE` **and** filter `Lost/Damaged = "LOST"` |
| Escalated Traces | 67 | 67 | right number, wrong mechanism — counted `Days Since Review > 10`, not `Review Status = "Escalate"`. Coincidence today; diverges as data moves |

**Fixed in v3.** All five cards now bind directly to their measure with no visual
filter. This was the most consequential thing in the sweep — two KPIs on a page you're
about to roll out were reading zero.

Also uppercased two stray KPI labels (`Open Exceptions`, `Total Active Traces`) so all
three pages match spec p.7.

## 2. Full measure audit — all 25

| Measure | Verdict |
|---|---|
| `Total Shipments` | OK. `DISTINCTCOUNT(QV_Manifest[Tracking Number])` — 83,502, and the column has zero duplicates so distinct is honest |
| `Total Exceptions` | OK as *events*. 7,775 distinct Exception Keys |
| `Exception Rate` | **Fixed** — mixed grain, see §4 |
| `Successful Shipments` | **Fixed** — inherited the same mixed grain |
| `Aged 8 Plus Days` | **Fixed** — not status-aware |
| `Avg Age (Days)` | **Fixed** — not status-aware |
| `Exceptions Total` | **Delete** — byte-identical to `Total Exceptions`, unused |
| `Open Exceptions` | **Delete** — byte-identical to `Open Ex`, unused |
| `Exceptions Resolved` | **Delete** — byte-identical to `Resolved Exceptions`, unused |
| `Open Ex` | OK. 7,775 — everything, since nothing is `Resolved` yet |
| `New Needs Review` | OK (6,736). Unused by any visual — keep or drop, your call |
| `Resolved Exceptions` | OK, returns 0. Feeds `Resolved Exceptions Display` — do not delete |
| `Escalated Exceptions` | OK, returns 0. Feeds `Escalated Exceptions Display` — do not delete |
| `Resolved / Escalated Exceptions Display` | OK — `COALESCE(…, 0)` is the right guard |
| `Selected Tracking Number / Status / Root Cause / Next Action / Notes` | OK — `SELECTEDVALUE` with fallbacks. Note `Root Cause`, `Next Action` and `Notes` are still 100% empty in source |
| `Total Active Traces` | OK — 95 |
| `Escalated Traces` | OK — 67. Was unused; now drives the ESCALATIONS card |
| `Never Reviewed` | OK — 28 |
| `In Transit` | OK — 27 |
| `Overdue Traces` | OK — 86 |

**Two literals to confirm against production before rollout.** `Resolved Exceptions`
and `Escalated Exceptions` match on the strings `"Resolved"` and `"Escalated"` and
return **0 silently** on a mismatch — indistinguishable from "nothing has resolved
yet". Your model already contains one such mismatch: those measures say `"Escalated"`
while `Current_Open_Trace[Review Status]` stores `"Escalate"`.

**Calculated columns.** `Age Days` now spans 1–37 with buckets that agree with their
own labels (`0-1`→1, `2-3`→2-3, `4-7`→6-7, `8+`→8-37) — the anchor fix worked.
`Is Issue` flags 29,957 of 40,735 rows but no measure reads it any more; `Total
Exceptions` counts distinct Exception Keys instead. Either wire it in or retire it,
because right now it looks authoritative and influences nothing.

## 3. Apply in Desktop — about 5 minutes

**a. Delete three measures** (Fields pane → right-click → Delete). All three are
unused by any visual, verified:

```
'Resolutions Table'[Exceptions Total]
QV_Output[Open Exceptions]
QV_Output[Exceptions Resolved]
```

**b. Apply `tools/measure-sweep.tmdl`** (TMDL view → paste → Apply). Corrects the two
aging measures and the rate grain, and adds `Affected Shipments` plus
`Exceptions per Affected Shipment`. Every existing measure keeps its name, so **no
visual needs rebinding**.

Deletions are deliberately not in the TMDL — the syntax is easy to get wrong and three
right-clicks is faster than debugging it.

## 4. Why `Exception Rate` changes from 9.31% to 8.60%

The old expression divided exception **events** by **shipments**:

```
DIVIDE( DISTINCTCOUNT(QV_Output[Exception Key]),      -- 7,775 events
        DISTINCTCOUNT(QV_Manifest[Tracking Number]) ) -- 83,502 shipments
```

Mixed grain. It answers neither "what share of shipments had a problem" nor "how many
problems did we have", and it can exceed 100% in principle. Master spec p.8 is explicit:
force both sides to distinct shipments.

| | |
|---|---|
| Distinct shipments with ≥1 exception | 7,178 |
| Distinct shipments in the manifest | 83,502 |
| **Exception Rate** | **8.60%** |
| Exceptions per affected shipment | 1.08 |

Sanity check that gives me confidence in the join: **100%** of the 7,178 exception
tracking numbers are present in the manifest, and both tables cover the same window
(manifest 2026-05-09→07-29, exceptions 2026-05-11→07-29).

> Neither number is trustworthy under a filter yet, because `QV_Manifest` still has no
> relationships — see §6.

## 5. Working from SharePoint **or** an API

The source is isolated to one query. Everything downstream — key, dedupe, categorisation,
measures, visuals — never references it, so switching is a parameter change, not a
rebuild.

```m
// Parameters
//   SourceMode      text   "SharePoint" | "Folder"
//   LandingFolder   text   \\server\share\QuantumView
//   SharePointSite  text   https://<tenant>.sharepoint.com/sites/<site>

fnGetExports = () =>
    let
        raw = if SourceMode = "SharePoint"
              then SharePoint.Files( SharePointSite, [ApiVersion = 15] )
              else Folder.Files( LandingFolder ),
        csv = Table.SelectRows( raw, each
                  Text.Lower([Extension]) = ".csv"
                  and Text.StartsWith( Text.Upper([Name]), "QUANTUMVIEW" ) )
    in
        csv
```

Both connectors return the same shape — `Content`, `Name`, `Extension`, `Date modified`
— so nothing after this line changes. **`SharePoint.Files` refreshes in the cloud with
no on-premises gateway**, which is the single biggest operational advantage and worth
choosing for that reason alone.

**The API doesn't change this.** Per the Option A decision, the API writes files into
the same landing folder — it replaces the human in SOP §6.2, not the architecture. So
all three sourcing routes (manual upload, scheduled export, API fetcher) converge on
one query. Full ingest and dedupe M is in `tools/model-fixes.pq` §6–8.

One requirement to carry across: `Date modified` is connector metadata, not a UPS
field. It is the recency signal the dedupe sorts on and the Run Coverage panel reads,
so an API path must stamp it at retrieval from the `Refresh` anchor.

---

## 6. To strengthen the build — ranked by payoff

**1. Relate `QV_Manifest`. It has zero relationships.** Every rate is therefore a
constant denominator: filter to one vendor and Total Shipments still says 83,502, so
Exception Rate is wrong under every slicer. This is the biggest correctness gap left.
The account relationship in `ACCOUNT-DRILLDOWN.md` §2 fixes it for the vendor slicer;
a shared `Dim Date` fixes it for everything else.

**2. Build `Dim Date` and retire Auto Date/Time.** One date table, related to both
facts, with `USERELATIONSHIP` for the manifest/delivery roles. This is what makes
"exception rate for this vendor last week" possible — today you can have the vendor or
the week, not both. It is also the star schema Trace spec p.7 asks for.

**3. Settle the exception grain, once, in writing.** Three defensible numbers exist:
7,775 distinct Exception Keys, 29,957 rows flagged `Is Issue`, 40,735 total rows. Pick
one, make every measure use it, and retire `Is Issue` if it isn't the answer.

**4. Confirm the resolved / escalated vocabulary.** Silent zeros are the worst failure
mode you have — they look exactly like a quiet week.

**5. Trim the model.** `QV_Manifest` is 83,502 rows and only `Tracking Number` and
`Account Key` are used by anything. `Res_Tracker` is still unpromoted `Column1…Column14`.
Auto Date/Time is still generating hidden tables. All three are free savings that get
more valuable as the data grows.

**6. Add a vendor view now that the account dimension exists.** The drill-down is wired
but nothing yet *ranks* vendors. One bar chart — exceptions by `Account Label`, sorted
descending — turns "which vendor is causing problems" from a click-hunt into a glance.
That is the efficiency goal stated for this build, and it is a single visual.

**7. Then the write-back layer.** `Root Cause`, `Next Action` and `Notes` are still 100%
empty across 7,775 rows, so the Resolution page shows a queue nobody can action from.
This is the largest remaining functional gap, but it is also the biggest build — I'd
sequence it after rollout, not before.

**Before you publish:** re-apply the sensitivity label, hide or delete the
`TEST-Acct Sliver` page (currently hidden), point Power Apps/Automate connections at a
service account rather than a personal login, and set scheduled refresh to run before
the morning SOP window.
