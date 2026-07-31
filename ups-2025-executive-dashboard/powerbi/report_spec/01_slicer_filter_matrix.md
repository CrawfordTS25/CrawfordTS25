# Slicer, filter and interaction specification

Implements Section 11 of the build guide, with the governance filters made concrete.

**Design principle.** Visible slicers help leaders ask better questions. Hidden filters
protect KPI accuracy. Hidden filters are not concealment — every one of them is
counted and named on the Data Quality page, so the report can always say exactly what
it excluded and why.

---

## 1. Global slicers (synced)

Placed in a collapsible left panel plus a top bar. Sync-slicers pane: tick **Sync** on
every page listed, tick **Visible** only where marked.

| Slicer | Field | Format | Visible on | Why it exists |
|---|---|---|---|---|
| Year | `Dim_Date[Year]` | Tile | All | Keeps the model scalable past 2025 and enables year-over-year |
| Quarter | `Dim_Date[Quarter]` | Tile | 1–5, 7 | Surfaces seasonality and operating-cycle effects |
| Month | `Dim_Date[MonthYearLabel]` | Dropdown | 1–5, 7 | Isolates abnormal periods; explains the annual average |
| Service Group | `Dim_Service[ServiceGroup]` | Dropdown | 1–3, 5–7 | The core decision variable |
| Domestic / International | `Dim_Service[Scope]` | Tile | All | Stops international activity distorting domestic recommendations |
| Account / Sub-Parent | `Dim_Account[SubName]` → `[AccountDisplay]` | Hierarchy, searchable | 2–5, 7 | Root-cause analysis by business unit |
| Location / State | `Dim_Account[Region]` → `[State]` | Hierarchy | 2, 4, 5, 7 | Separates geographic patterns from service-wide ones |

**Month is sorted by `Dim_Date[SortOrder]`, not alphabetically.** Verify this after
every model refresh; it silently resets when a column is retyped.

### Deliberate omissions

- **No Month slicer on Page 6.** An annual recommendation filtered to one month is not
  an annual recommendation. Removing the control is more effective than a warning.
- **No Account slicer on Page 6.** Same reasoning.
- **No Service slicer on Page 4.** There is no join from claims to service; the slicer
  would appear to work and do nothing. Its absence is the honest signal.

---

## 2. Page-specific slicers

| Page | Additional slicers | Rationale |
|---|---|---|
| 2 Service Performance | Raw UPS Product (`Dim_ServiceMapping[RawProduct]`), Qualified Volume Flag, Service Tier | Diagnose which underlying product drives a group result |
| 3 Cost and Volume | Weight Band, Charge Category, Spend Range | Explain cost variability from package profile rather than service choice |
| 4 Claims and Exceptions | Claims Category, Loss Risk Flag | Separate Loss / Damage / Casualty / Follow-up populations |
| 5 Account and Location | Region → State → City, Has Transit Data | Isolate geography; expose accounts with no reliability coverage |
| 6 Recommendation | Volume Threshold (what-if), Share Threshold (what-if) | Scenario-test the ranking without changing methodology |
| 7 Accessorial | Charge Category, Is Accessorial | Separate base freight from surcharges |

**Weight Band** is a calculated column on `Fact_VolumeSpend`, banding
`BilledWeightLbs / Volume`: `0–1 lb`, `1–5 lb`, `5–20 lb`, `20–70 lb`, `70 lb+`.
It is the control that makes the cost-per-shipment comparison interpretable — compare
two services *inside* one weight band and the mix effect disappears.

---

## 3. Hidden filters (filter pane, not slicers)

Applied at report or page level. Every one is reported on the Data Quality page.

| Filter | Level | Setting | Why | Reported by |
|---|---|---|---|---|
| `Dim_Date[IsReportable]` | Page 1–3, 6 | `= "Yes"` | Prevents partial and unloaded months distorting trends | `[Missing Months List]` |
| `Fact_VolumeSpend[HasVolume]` | Visual (cost/ranking) | `= "Yes"` | Removes adjustment-only rows from per-shipment metrics | `[Spend-Only Adjustment Rows]` |
| `Dim_Service[IncludeInRanking]` | Page 1, 2, 6 | `= "Yes"` | Keeps MISC / UNC out of service rankings | `[Excluded Adjustment Spend]` |
| `[Annual Qualification Flag]` | Visual (ranking only) | `= 1` | Stops thin samples ranking as best overall | `[Qualification Status]` |
| `Dim_Service[ServiceGroup]` | Page 1, 2, 6 | `<> "Unmapped - Review"` | Executive visuals show mapped categories only | `[Unmapped Product Rows]` |
| `Fact_Claims[ClaimsCategory]` | Page 4 | is not blank | Keeps claims visuals to actual claim activity | Data Quality exclusion table |

### Two filters the build guide asks for that this model does *not* apply globally

**`Volume > 0` at report level.** Applied at *visual* level on cost and ranking
visuals only — never at report level. Roughly $94k of net spend in the loaded period
sits on zero-volume adjustment rows. Filtering it out globally would make the
dashboard's total net spend disagree with the invoice, and the first person to check
would lose confidence in everything else on the page. The spend stays in financial
totals, comes out of per-shipment rates, and is named on the Data Quality page as
`[Unattributed Spend %]`.

**`IsCompletedMonth` at report level.** Applied to trend and annual-comparison pages
only. Leadership legitimately wants current-month progress; it just must not be
averaged into an annual figure. Pages 4, 5 and 7 leave the current month visible and
label it.

---

## 4. What-if parameters

Create via **Modeling → New parameter → Numeric range**.

| Parameter | Min | Max | Increment | Default |
|---|---|---|---|---|
| `Volume Threshold` | 0 | 10,000 | 250 | 1,000 |
| `Share Threshold` | 0 | 0.10 | 0.005 | 0.01 |

Both feed `[Annual Qualification Flag]`. Exposing them turns the most contestable
assumption in the model into something leadership can move in the room and watch
respond — which is a far stronger defence of the threshold than a footnote.

---

## 5. Visual interactions

| Source visual | Target | Interaction |
|---|---|---|
| KPI cards | All | **None** — a card is a statement of the filter context, not a filter |
| Monthly trend line | All on page | Filter |
| Service scorecard | Charts on page | Filter |
| Service scorecard | Other tables | **Highlight**, not filter — preserves comparison context |
| Donut / mix visuals | All | Highlight |
| Map | Tables | Filter |
| Banner card | All | None |

Set every KPI card to **no interaction** explicitly. The default is Highlight, and a
user who clicks a card and sees the page change will assume the click meant something.

---

## 6. Bookmarks

| Bookmark | State | Use |
|---|---|---|
| `Reset` | All slicers cleared, defaults restored | Recovery — put a button on every page |
| `Domestic only` | Scope = Domestic | The default lens for service recommendation |
| `International only` | Scope = International | Separate population, separate conversation |
| `Completed months only` | `IsReportable = Yes` | Board-ready view |
| `Threshold: strict` | Volume Threshold = 2,500 | Stress-test the ranking |
| `Threshold: none` | Volume Threshold = 0 | Demonstrate *why* the threshold exists |

`Threshold: none` is a teaching bookmark. Toggling it in a review shows a
sub-50-package service jumping to the top of the ranking on a perfect on-time record.
That single click makes the case for volume governance better than any slide.

Bookmarks capture **data** and **display**, not current page, unless driving navigation.
