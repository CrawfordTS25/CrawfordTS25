# Build guide → implementation map

Where each section of the *UPS 2025 Annual Power BI Dashboard Build Guide v2* is
implemented, and where the implementation deliberately departs from it.

Departures are marked **[CHANGED]** with the reason. Every one of them came from a
defect or ambiguity found while building against the real extracts, not from
preference.

---

| Guide section | Implemented in | Notes |
|---|---|---|
| 1. Annual Build Objective | `docs/02_executive_summary.md` | Recommendation stated with a confidence level per line |
| 2. Annual Data Model Design | `powerbi/model/relationships.md`, `etl/ups_etl.py` | **[CHANGED]** — see 2a–2c below |
| 3. Full-Year Build Instructions | `powerbi/powerquery/*.m`, `docs/06_build_checklist.md` | **[CHANGED]** — see 3a |
| 4. KPI Definitions and DAX | `powerbi/dax/01`–`03` | **[CHANGED]** — see 4a–4c |
| 5. Dashboard Page Layout | `powerbi/report_spec/00_page_layouts.md` | Two pages added |
| 6. Annual Executive Summary | `docs/02_executive_summary.md` | Placeholders replaced with computed values |
| 7. Service Recommendation Framework | `powerbi/dax/04`, `docs/03_recommendation_framework.md` | **[CHANGED]** — see 7a–7c |
| 8. Automation and API Path | `docs/05_automation_api_path.md` | Reordered by value |
| 9. Data Quality and Governance | `powerbi/dax/05`, `docs/04_data_quality_governance.md` | **[CHANGED]** — see 9a |
| 10. Build Checklist | `docs/06_build_checklist.md` | Verification added per item |
| 11. Slicers, Filters, Rationale | `powerbi/report_spec/01_slicer_filter_matrix.md` | **[CHANGED]** — see 11a |

---

## Departures, and why

### 2a. `Dim_ServiceMapping` is a two-vocabulary bridge, not a lookup

The guide's mapping table has one `Raw Product` column. The real extracts need two
vocabularies: Volume & Net Spend says `NDA REG / EXPRESS PKG`, Time-in-Transit says
`NEXT DAY AIR`, and neither list contains the other's terms.

The table is keyed on `(SourceSystem, RawProduct)`. Because `RawProduct` is not unique
across it, the model relates through a separate one-row-per-group `Dim_Service`.
Without this there is no way to place cost and reliability for the same service on the
same row, and the whole comparison is impossible.

### 2b. `Fact_Accessorial` added

Not in the guide's model. It is the only source that explains *why* cost per shipment
moves, and it independently reconciles to Volume & Spend net spend — a free integrity
check. It also surfaces ~$123k/year of avoidable Address Correction charges that appear
nowhere else.

### 2c. No relationship from `Fact_Claims` to the service dimension

The guide's model implies claims can be sliced by service. The extract carries no
product, service or tracking key, so it cannot. The relationship is deliberately absent
rather than approximated — see 7b.

### 3a. Load by sheet shape, not sheet name

The guide says "Get Data > Folder once monthly files are standardised". Two problems in
practice:

- **Tab names change between months** (`Monthly VnR by Product by Accou`, `VnR_YTD 2025`,
  `VnS`), so name matching breaks on the next delivery. Sheets are classified by probing
  for anchor columns instead.
- **A plain folder append double-counts January**, because the February file is a
  year-to-date extract. This is the single most consequential change in the build; it is
  documented at length in `docs/04_data_quality_governance.md` § 1.

### 4a. On-Time Delivery % is a weighted ratio, and the supplied column is not loaded

The guide's DAX is correct (`DIVIDE([On-Time Packages],[Packages Measured])`). The
addition is *defensive*: `Fact_TimeInTransit[On Time %]` is excluded from the model
entirely. Averaging that column across the March file returns ≈98.2% against a true
96.46%. Loading it invites someone to use it.

### 4b. `Avg Net Spend per Billed Lb` added, and it is what the score uses

The guide's `Avg Net Spend per Shipment` is not comparable across services here: Ground
averages 16.1 lb per piece against 2.3 lb for 2nd Day Air. Per shipment they differ by
$0.36; per pound Ground is 7.3× cheaper. Scoring on the per-shipment figure would make
migrating Ground volume to air look nearly free.

Both measures exist. Both appear on the report, adjacent. The score uses the
weight-normalised one.

### 4c. Claim rates expressed per 10,000

`DIVIDE([Loss Claims],[Total Shipments])` renders as "0.05%" and every service looks
identical. Per 10,000 shipments is the readable unit for a rare event. The guide's
original ratio measures are retained for continuity.

### 7a. The scoring arithmetic is specified

The guide gives four weights across four different units, three "higher is better" and
one "lower is better". Added: min-max normalisation across the qualified set only,
per-metric direction, and ranking on the Wilson confidence floor rather than the point
estimate.

### 7b. Weight reallocation when a component cannot be measured

The guide assigns 30% to Loss Claim Rate and 20% to Exception Rate. Neither is
computable at service grain. Scoring them as zero would penalise every service equally
and silently rescale the model — a service that should score 94 would report 47 with no
indication why.

Unavailable components have their weight redistributed across the components that
returned values, and `[Score Basis]` prints the effective weights on the same screen as
the score. The DAX for the claims components is written in full behind a flag, so the
model reverts to the specified 40/30/20/10 the day a service key appears on the export.

### 7c. Volume anchor treated separately from the ranking

A pure score ranking puts Ground last, which reads as "stop using Ground". Ground moves
72% of volume at a seventh the cost per pound of the next option.

The framework separates *"which service performs best"* from *"which service should we
default to"*. A service carrying the majority of volume is evaluated on whether its
performance is acceptable and stable, not on whether something else scores higher. This
is the most important judgement in the build; without it the report invites a decision
that would cost several million dollars a year.

### 9a. `Volume > 0` is a visual-level filter, never report-level

The guide lists it as a hidden report filter. Roughly $96k of net spend sits on
zero-volume adjustment rows. Filtering globally makes the dashboard's total disagree
with the invoice, and the first person to check loses confidence in everything else.

Retained in financial totals, excluded from per-shipment rates, reported as
`[Unattributed Spend %]`.

### 11a. Some slicers deliberately removed

The guide's principle — "visible slicers should help leaders ask better questions" —
implies its converse: a control that produces a misleading answer should not exist.

- No Month or Account slicer on the Recommendation page. An annual policy sliced to one
  account in one month is not an annual policy.
- No Service slicer on the Claims page. It would appear to work and do nothing.

---

## Sections implemented as written

The guide's page structure, KPI list, service groupings, threshold options, drillthrough
design, slicer layout zones and governance intent are all implemented as specified.
Nothing above changes what the dashboard is for or what it reports on — the changes are
about making each of those things come out right against the actual data.
