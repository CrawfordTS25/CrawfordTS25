# UPS Quantum View — Cross-Page Consistency Pass

`Quantum_View_Exceptions_Dashboard.pbix` — same file, same format. Only the **Report
layer** (`Report/definition/**`) was rewritten. The `DataModel`, `Connections`,
`Settings`, `Metadata`, `DAXQueries`, `TMDLScripts`, `StaticResources` (theme) and
`docProps` parts are byte-for-byte identical to the original archive, verified by
SHA-256 on repackage.

Authority for every number below: **UPS_QuantumView_Master_Build_Spec.pdf** p.5
(theme tokens), p.6 (master coordinate table), p.7 (card anatomy + accent map);
**UPS_Trace_Dashboard_Build_Spec.pdf** p.11–12 (trace measures, SLA);
**Overview of the Edward Jones Trace Process.docx** (tickler: 2 days researching,
10 days trace open); **Quantum View SOP v1.5** §4 / §11.1 (Morning + Afternoon run
windows, completion criteria).

---

## 1. Shared skeleton — now pixel-identical on all five pages

Master coordinate table, p.6. Every page carries the same six chrome elements at the
same rectangles, plus the same five-tile KPI band:

| Element | X | Y | W | H |
|---|---|---|---|---|
| Filter rail panel | 24 | 162 | 150 | 534 |
| Title & nav bar | 24 | 24 | 1232 | 44 |
| Rail header | 36 | 174 | 126 | 16 |
| Page title | 40 | 33 | 344 | 26 |
| Page navigator | 396 | 30 | 456 | 32 |
| Data-as-of stamp | 868 | 27 | 372 | 38 |
| KPI cards ×5 | 24 / 274 / 524 / 774 / 1024 | 76 | 232 | 78 |
| Slicer slots ×5 | 36 | 196 / 264 / 332 / 400 / 468 | 126 | 56 |

Before this pass the five pages disagreed on all of it — title bars of 1232×80,
1272×72, 416×48 and none at all; KPI cards of 290×78, 232×78, 240×80, 104×96 and
160×128; filter rails at (16,160,160,330), (16,168,160,376), (0,56,136,296) and
absent. Page background was set on two pages and defaulted on three.

## 2. One component set, one palette

Theme tokens (spec p.5) replace the hand-set colours that had drifted:

| Token | Hex | Was |
|---|---|---|
| Ink | `#1F2D40` | title bar was theme colour 2 (Breach red) on Exceptions; bars were `#3A3A3A` |
| Accent | `#F2A900` | KPI accent bars were `#FAD141`; trend area fill was `#FAD141` |
| Breach | `#D64545` | — |
| WIP | `#E8A13A` | — |
| Resolved | `#2F9E6F` | — |
| Email | `#7C5CBF` | — |
| Border | `#E4E6EA` | mixed `#DCE0E2` / white / none; panel radius mixed 8 and 12 |

Card anatomy (spec p.7): 232×78, radius 8, 4 px top accent bar (was 10 px), label
9 px uppercase `#5A6472` (was 10 px `#6B6E70`), value Segoe UI Semibold bold `#1F2D40`.
All 25 cards, 15 slicers and 20 work-area panels are now generated from a single
style definition — `tools/validate.py` asserts zero style variants per component.

**One deliberate deviation:** card value type is 24 px, not the spec's 34 px. The two
drill-through pages put identifiers (case numbers, tracking numbers) in the band, and
34 px truncates them at 232 px wide. 24 px is the largest size that renders every
page's band from one component. Change `make_card`'s `fontSize` in `tools/build.py`
if you would rather have 34 px on the three summary pages and split the component.

## 3. Work areas

Grid rhythm shared by Exceptions, Trace, Exception Detail and Trace Detail —
rows at y=162 (h 165), y=339 (h 150), y=501 (h 195); columns at x=186 (w 525),
x=723 (w 533), full width 1070.

Resolution keeps the spec's act-surface arrangement (p.6) — queue left, notes and
automation stacked right — resized to the margins: queue 186,162,452×**534** ·
notes 650,162,**606**×**268** · automation 650,**442**,**606**×**254**.

All five pages now fill the same work area: x 186 → 1256, y 162 → 696.

> **Departure from spec p.6.** The coordinate table sizes the three Resolution panels
> 452×470, 452×236 and 452×222, which ends the work area at x=1102, y=632 while every
> other page fills to 1256 × 696 — a 154 px empty column and a 64 px empty strip on
> one page out of five. Panels were grown to the margins instead. The queue keeps the
> spec's 452 width, the stacked right panels keep the 12 px gutter between them, and
> the automation text box derives its rectangle from the panel (`AUTO_TEXT`). To
> restore the literal spec numbers, set `QUEUE`/`NOTES`/`AUTO` in `tools/build.py`
> back to `(186,162,452,470)`, `(650,162,452,236)`, `(650,410,452,222)`.

## 4. Functional fixes

**Exceptions opened pre-filtered to almost nothing.** Four slicers carried saved
selections — Exception Category = `Refused Delivery`, Run Time = `Afternoon QV`,
Run Date = `7/16/2026`, Shipper Location = `Progress Parkway`. Every KPI and chart
on the page was reporting that intersection. All selections cleared; the Resolution
page's Exception Type slicer (selected `null`) cleared too.

**Three slicers were mislabelled.** "Exception Type" was bound to Exception Category,
"Run Type" to Run Time, and a second slicer titled "Run Date" was actually Shipper
Location. Labels now match their bindings, and Exception Type was added as a real
fifth slicer.

**All five Trace KPI cards returned the same thing.** Each was `Min(CASE #)` — a case
number string, not a count — and the "Needs Review" card filtered on
`Review Status = "Needs Review"`, a value that does not exist in the data (the column
holds `Escalate` and `Never Reviewed`), so it rendered blank. Rebuilt as counts
(`CountNonNull(CASE #)`, the aggregation the page's own bar charts already use) with
filters that match real values, and aligned to the Trace spec's KPI band:

| Card | Filter | Accent |
|---|---|---|
| Active Traces | none | Ink |
| Open > 10 Days (SLA) | `Days Since Review > 10` | Breach |
| Escalations | `Review Status = "Escalate"` | WIP |
| Never Reviewed | `Review Status = "Never Reviewed"` | Accent |
| Packages Lost | `Lost/Damaged = "LOST"` | Breach |

The SLA threshold is 10 days per the tickler schedule in the Trace Process overview
and the Trace spec's "OPEN > 10 DAYS (SLA)" KPI; it was previously 7.

**Trace Detail's "Days Since Review" card used Count**, so it always showed `1`.
Changed to `Min` like the other single-record cards on that page.

**Exceptions had four KPI cards where the spec calls for five.** Added
Successful Shipments (green slot). Accent order on Exceptions follows spec p.7 —
Ink · Breach · Ink · Resolved · Accent; Resolution follows its own —
Accent · Breach · Resolved · Ink · Email.

**Tracking-number links.** The Exceptions detail table's Web URL conditional
formatting (`webURL` → `Max(QV_Output[Tracking URL])`) is preserved and the same
wiring was added to the Exception Detail and Open Trace Queue tables. If Power BI
does not render them as links, set the `Tracking URL` column's **Data category =
Web URL** in the model — that is a model-side property this file cannot carry
(spec p.10, step 3).

**Exceptions Trend was neither sorted nor a trend.** It sorted by `Total Exceptions`
descending, and its axis — `Run Date` — is stored as text, so even a date sort orders
alphabetically: `7/14, 7/16, 7/17, 7/27, 7/6, 7/7`, putting July 6–7 at the right-hand
end of the line. "Sort by column" is a model property this file cannot set, so the
axis moved to `Manifest Date`, a real datetime with 47 days of history (22 May →
27 Jul), sorted ascending. Title now reads *Exceptions Trend · by Manifest Date* so
the axis is explicit. `Run Date` remains available as a slicer.

**Drill-through keyed on a non-unique column.** Exception Detail bound on
`QV_Output[Tracking Number]`, but **1,216 of 2,127** tracking numbers carry more than
one exception row — up to 9 — and Category / Exception Type genuinely differ across
them on ~30, so the page's `Min()` cards landed on an arbitrary record. Rebound to
`QV_Output[Exception Key]`, which holds Category, Exception Type, Service, Manifest
Date, Shipper Location and Ship To constant across **all 2,175** of its groups, making
`Min()` exact. The remaining multiplicity is the same exception seen across several QV
runs, which the detail table now shows usefully. `Exception Key` was added to the
Exceptions detail table as a narrow 50 px "Key" column so right-click can pass it;
that table switched to explicit column widths (1,043 px of 1,070) instead of autosize.

Trace Detail keeps its `CASE #` + `Tracking Number` binding — `CASE #` is unique across
all 95 rows. Its hard-coded leftover drill values (case `20260629005`, tracking
`1Z8E19V71292549531`) were removed so it no longer opens on a stale record. Both back
buttons kept, restyled, and moved into the rail's first slot.

**Other cleanups.** The stray inverted Shipper Location filter on the Exceptions
detail table; the missing `NoFilter` interaction from the Trace queue to the
Escalations card; the trailing space in the "QV Tracing " page name; and the
"Shrepoint write-back pending" text box, which now lists the actual outstanding
build-order steps 7–9.

## 5. Known gaps that need a model change

These are visible in the report but cannot be fixed from `Report/definition`. Listed
worst-first; numbers are measured against the data in this file.

| Gap | Evidence | Fix lives in |
|---|---|---|
| Exceptions slicers reach only 2 of 5 KPIs | relationships run `QV_Manifest → Resolutions Table → QV_Output`, all M:1 single, so `QV_Output` slicers propagate to nothing upstream. Total Shipments pinned at 45,561; Aged 8+ Days pinned at 1,664; Successful Shipments dominated by the constant | relationship cross-filter direction |
| Exception Rate reads **4.77%**, spec target ~75% | 2,175 distinct Exception Keys ÷ 45,561 manifest tracking numbers — different grain *and* different scope (6 run dates vs all history) | measure + query scope |
| "How many exceptions" has 3 answers | 2,175 distinct keys / 4,683 rows with `Is Issue = 1` / 6,636 rows, all of which carry `Status = "Exception"` | pick one grain |
| Exception Key is not the Step 0 key | it is `TrackingNumber\|<full UPS description text>`; reword the description upstream and every saved note detaches. No date component | Power Query |
| 3 competing type columns | `Exception Type`, `Exception Type ` and `Exception Category` disagree on **4,429 of 6,636** rows (67%) | Power Query |
| Resolution tracks a workflow that never closes | `Tracker Status` only ever `New / Needs Review` (1,136) or `Open` (1,039) → Resolved = 0, Escalated = 0, Open = 100% permanently. `Root Cause`, `Notes`, `Next Action`, `Last Updated`, `Closed Date` are **0 of 2,175** populated | write-back layer |
| Trace can't support half its spec | `Refund Amount` text and 0 of 95 filled; `PII` 6 of 95 all `"NO"`; `Tickler` 0 of 95; `Delivery Status` one distinct value; every Trace date is text | Power Query + source |
| Measure coverage | master spec pp.7–8: **4 of 13**; trace spec p.11: **0 of 9** | DAX |
| No refresh anchor | no `'Refresh'[StampUTC]` table, so aging cannot be anchored per pp.8–9. The DATA AS OF chip uses `Max(QV_Output[Date modified])` as a stand-in | Power Query |
| Model hygiene | `Branch_Contacts` load broken (500 null rows, a column named `X:\hrdi_report_pickup\FA_Roster\`) so Flow 2 has no roster; `Res_Tracker` is 1,040 rows of `Column1…Column14`; `Trace_Active` and `Current_Open_Trace` are duplicate facts; Auto Date/Time on, generating 12 hidden date tables both specs say to disable | Power Query + options |

Easy win not yet built: `Run Time` cleanly separates `Morning QV` (4,311) from
`Afternoon QV` (2,325), so a "both run windows completed today" measure against
SOP §11.1 is available from data already in the model.

## 6. Not changed

No measures were added or edited and no model change was made — the `DataModel` part
is untouched. That means the spec's `Avg Transit Days`, `Top Carrier`, `Aging > 48h`
anchored to a `'Refresh'[StampUTC]` table, `Emails Sent (7d)`, and the Trace spec's
`$ Recovered` / `Recovery Rate` / `Notify Legal` measures are still to be authored in
Power BI Desktop. The Exceptions and Resolution bands use the closest existing
measures in the meantime. Likewise the SharePoint write-back, Flow 1 audit log and
Flow 2 mail-merge (spec pp.12–13) remain unbuilt; the Resolution automation panel now
names those steps instead of a typo.

## 7. Reproducing / verifying

```
python3 tools/build.py       # rewrite Report/definition from the extracted original
python3 tools/validate.py    # style uniformity, skeleton identity, canvas bounds, refs
python3 tools/package.py     # rezip; asserts non-report parts are byte-identical
python3 tools/render.py      # layout-proof.svg, drawn to scale from the packaged file
```

`layout-proof.svg` is a to-scale render of all five pages straight from the packaged
file — the fastest way to confirm the chrome lines up before opening Desktop.
