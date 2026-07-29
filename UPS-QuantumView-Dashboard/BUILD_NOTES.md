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
automation stacked right — with one deliberate departure: queue 186,162,**452**×470 ·
notes 650,162,**606**×236 · automation 650,410,**606**×222.

> **Departure from spec p.6.** The coordinate table gives all three panels 452 wide,
> which stops the work area at x=1102 while every other page runs to the 1256 right
> margin — a 154 px empty column on one page out of five. The queue stays at the
> spec's 452; the right column was widened to 606 so Resolution is flush with the
> rest of the report. Revert by setting `NOTES` and `AUTO` back to 452 in
> `tools/build.py` (`AUTO_TEXT` follows automatically).
>
> Still open: Resolution's panels bottom out at y=632 because the spec's heights
> (470, and 236+12+222) are 64 px short of the 696 bottom margin the other four
> pages reach. To close that too, take the queue to 534 and the right column to
> 268 / 254.

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

**Drill-through.** Both hidden pages keep their bindings — Exception Detail on
`QV_Output[Tracking Number]`, Trace Detail on `Current_Open_Trace[CASE #]` +
`[Tracking Number]`. Trace Detail's hard-coded leftover drill values (case
`20260629005`, tracking `1Z8E19V71292549531`) were removed so it no longer opens on a
stale record. Both back buttons kept, restyled, and moved into the rail's first slot.

**Other cleanups.** The stray inverted Shipper Location filter on the Exceptions
detail table; the missing `NoFilter` interaction from the Trace queue to the
Escalations card; the trailing space in the "QV Tracing " page name; and the
"Shrepoint write-back pending" text box, which now lists the actual outstanding
build-order steps 7–9.

## 5. Not changed

No measures were added or edited and no model change was made — the `DataModel` part
is untouched. That means the spec's `Avg Transit Days`, `Top Carrier`, `Aging > 48h`
anchored to a `'Refresh'[StampUTC]` table, `Emails Sent (7d)`, and the Trace spec's
`$ Recovered` / `Recovery Rate` / `Notify Legal` measures are still to be authored in
Power BI Desktop. The Exceptions and Resolution bands use the closest existing
measures in the meantime. Likewise the SharePoint write-back, Flow 1 audit log and
Flow 2 mail-merge (spec pp.12–13) remain unbuilt; the Resolution automation panel now
names those steps instead of a typo.

## 6. Reproducing / verifying

```
python3 tools/build.py       # rewrite Report/definition from the extracted original
python3 tools/validate.py    # style uniformity, skeleton identity, canvas bounds, refs
python3 tools/package.py     # rezip; asserts non-report parts are byte-identical
python3 tools/render.py      # layout-proof.svg, drawn to scale from the packaged file
```

`layout-proof.svg` is a to-scale render of all five pages straight from the packaged
file — the fastest way to confirm the chrome lines up before opening Desktop.
