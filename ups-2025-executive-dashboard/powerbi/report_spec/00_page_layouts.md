# Report page specification

Canvas 1280 × 720, 16:9. Eight-column grid, 16 px gutter, 24 px page margin.
Every page carries the `[Data Basis Banner]` card at the top — a report that states
its own reporting basis on every page cannot be misquoted after a screenshot.

Page order follows the build guide's Section 5, with two additions marked **NEW**.

---

## Page 1 — Executive Overview

**Question:** What is the story, and which service should leadership prefer?

| Zone | Visual | Fields / measures |
|---|---|---|
| y0, full width | Banner card | `[Data Basis Banner]`, background `[Data Basis Banner Colour]` |
| Row 1, 5 cards | KPI cards | `[Total Shipments]`, `[Total Net Spend]`, `[On-Time Delivery %]`, `[Loss Claim Rate per 10k]`, `[Avg Net Spend per Shipment]` |
| Row 2 left (5 col) | Line + reference | `[On-Time Delivery %]` by `Dim_Date[MonthYearLabel]`, constant line at `[OTD % Annual Benchmark]` |
| Row 2 right (3 col) | Recommendation callout | Card with `[Recommendation Callout]` |
| Row 3 left (5 col) | Service scorecard table | `Dim_Service[ServiceGroup]` × `[Rankable Shipments]`, `[On-Time Delivery %]`, `[OTD Wilson Lower Bound]`, `[Avg Net Spend per Shipment]`, `[Avg Net Spend per Billed Lb]`, `[Service Consistency Score]`, `[Qualification Status]` |
| Row 3 right (3 col) | Donut | `[Service Volume Mix %]` by `ServiceGroupShort` |

Title: `[Title - Executive Overview]`.

**Card sublabels are mandatory here.** Each KPI card gets a sub-line stating its
basis — the OTD card reads *"1 month of transit data"* until more months load. A
naked 96.5% on an executive page will be quoted as an annual figure within a week.

Notes:
- Sort the scorecard by `[Service Consistency Score]` descending, with unqualified
  services shown *below* a divider rather than hidden. Hiding them prompts "where did
  3 Day Select go?" in every review; showing them greyed out with their
  `[Qualification Status]` answers it before it is asked.
- Show `[Avg Net Spend per Shipment]` and `[Avg Net Spend per Billed Lb]` **adjacent**.
  See **Page 3** below, and `docs/03_recommendation_framework.md` § 5, for why either alone misleads.

---

## Page 2 — Service Performance

**Question:** Which services were most consistent across the year?

| Visual | Detail |
|---|---|
| Bar: `[On-Time Delivery %]` by ServiceGroup | Error bars from `[OTD Wilson Lower Bound]`. Data label shows `[Packages Measured]`. |
| Small multiples: monthly OTD by service | One sparkline per service; benchmark line at firm OTD |
| Stacked bar: `[Late by Day]` vs `[Late by Time]` | The severity split — a missed *day* is a materially worse client outcome than a missed *time* |
| Scatter: volume (x) vs OTD (y) | Bubble = `[Total Net Spend]`; quadrant lines at firm OTD and `[Minimum Shipment Threshold]` |
| Table: qualification detail | `[Qualification Status]`, `[OTD Confidence Label]`, `[OTD Volatility (pp)]`, `[Worst OTD Month]` |

The scatter is the page's argument: it shows in one frame that the highest OTD
percentages sit on the lowest volumes, which is precisely why the volume threshold
exists.

---

## Page 3 — Cost and Volume

**Question:** What did we ship and what did it cost?

| Visual | Detail |
|---|---|
| Column + line combo | Monthly `[Rankable Shipments]` columns, `[Avg Net Spend per Shipment]` line |
| Bar: net spend by service | With `[Service Spend Mix %]` label |
| **Paired bar: cost per shipment vs cost per billed lb** | The two cost views side by side — see below |
| Table: cost bridge by service | `[Avg Billed Weight per Shipment]`, `[Avg Net Spend per Shipment]`, `[Avg Net Spend per Billed Lb]`, `[Weight-Adjusted Cost Premium]` |
| Line: `[Incentive %]` by month | Discount realisation trend against list rates |

**The paired cost visual is not optional.** Cost per shipment on its own is the single
most misleading number available in this data set. Ground averages roughly 16 lb per
piece against roughly 2 lb for 2nd Day Air, so on a per-shipment basis the two look
almost identically priced — an artefact of package mix, not of rate. Per billed pound,
Ground is about seven times cheaper. A reader who sees only the per-shipment view will
conclude that upgrading Ground volume to air is nearly free.

Annotate the visual with that sentence. Do not rely on the reader inferring it.

---

## Page 4 — Claims and Exceptions

**Question:** Where did loss, damage and claims risk appear?

| Visual | Detail |
|---|---|
| Persistent notice bar | `[Claims Attribution Warning]` — pinned, not dismissible |
| KPI row | `[Issued Claims Pkgs]`, `[Loss Claims]`, `[Claims Recovery Rate]`, `[Paid Claims Amount]`, `[Claims Cost per 1k Shipments]` |
| Bar: claims by category | Loss / Damage / Follow-up / Casualty, issued vs paid |
| Line: claims per 10k by month | With firm-average reference line |
| **Table: account loss concentration** | `[Loss Claims]`, `[Rankable Shipments]`, `[Loss Claim Rate per 10k]`, `[Loss Rate Index vs Firm]`, `[Loss Risk Flag]` — conditional formatting on the index |
| Card | `[Top Account Share of Loss Claims]` |

The account concentration table is the most actionable visual in the report. Firm-wide
claim rates describe a carrier; concentrated claim rates describe a *location*, and
locations can be fixed. Sort by `[Loss Rate Index vs Firm]` descending and apply a
data bar.

There is **no service breakdown on this page**. That is deliberate and is what the
notice bar explains.

---

## Page 5 — Account and Location Insights

**Question:** Are specific accounts, locations or lanes driving issues?

| Visual | Detail |
|---|---|
| Account scorecard matrix | Account × `[Rankable Shipments]`, `[On-Time Delivery %]`, `[Loss Rate Index vs Firm]`, `[Avg Net Spend per Shipment]` |
| Filled map by state | Colour `[On-Time Delivery %]`, size `[Rankable Shipments]` |
| Bar: top 10 accounts by volume | With `[Account Volume Mix %]` |
| Matrix: account × service | `[Rankable Shipments]`, heat-formatted |
| Table: accounts with volume but no transit coverage | `[Rankable Shipments]` where `[Has Transit Data] = "No"` |

That last table matters: an account with volume and no transit data is invisible in
every reliability figure on the report. It needs to be named, not averaged away.

---

## Page 6 — Annual Recommendation

**Question:** What service policy should we recommend going forward?

| Visual | Detail |
|---|---|
| Recommendation matrix | `Dim_Service[ServiceGroup]` × `[Recommendation Category]`, `[Service Consistency Score]`, `[Service Rank]` |
| Four callout cards | Recommended default / Recommended premium / Best on-time performer / Service to monitor |
| Score decomposition | Stacked bar of `[Score - Reliability]`, `[Score - Loss Risk]`, `[Score - Exception Risk]`, `[Score - Cost]` weighted |
| Footnote card | `[Score Basis]` — states the effective weights actually used |
| What-If slicers | `Volume Threshold`, `Share Threshold` |

Locked-down page. Global slicers reduced to Year, Domestic/International and the
threshold parameters. Month and Account slicers are **removed** — an annual service
policy sliced to one account in one month is not an annual service policy, and leaving
the control there invites exactly that.

`[Score Basis]` is mandatory on this page. A score whose components were reweighted
because claims could not be attributed must say so on the same screen as the score.

---

## Page 7 — Accessorial and Cost Drivers  **NEW**

**Question:** Which charges are driving spend, and which of them are self-inflicted?

Not in the original build guide. Added because the accessorial extract is the only
source that explains *why* cost per piece moves, and because it surfaces avoidable
cost that no other page can see.

| Visual | Detail |
|---|---|
| Waterfall: base freight → accessorials → net spend | `[Accessorial Net Spend]` by `ChargeCategory` |
| Bar: top 15 charge categories | Net spend, with unit counts |
| **Card row: avoidable charges** | Address Correction spend and unit count, cost per correction |
| Line: fuel surcharge as % of net spend by month | Contract exposure to fuel |
| Table: accessorial rate by account | Accessorial spend as a share of that account's net spend |

Address Correction deserves its own card. Every unit is a package that shipped to a
bad address the firm supplied — the charge is fully avoidable through address
validation at the point of shipment, and it is charged per package.

---

## Page 8 — Data Quality and Appendix

**Question:** What data was included, excluded and assumed?

| Visual | Detail |
|---|---|
| Coverage matrix | Month × source (Volume / Transit / Claims / Accessorial), loaded Y/N |
| Cards | `[Months Loaded]`, `[Missing Months]`, `[Annual Completeness %]`, `[Reconciliation Status]` |
| Source file inventory | From `DQ_SourceInventory.csv` |
| Exclusion summary | `[Excluded Adjustment Spend]`, `[Spend-Only Adjustment Rows]`, `[Unattributed Spend %]`, `[Unmapped Product Rows]`, `[Masked Sub-Parent Volume]` |
| Service mapping inventory | Full `Dim_ServiceMapping`, both vocabularies |
| Metric definitions | Static text, one line per KPI, matching `docs/03_recommendation_framework.md` |
| Known limitations | Static text — claims attribution, shipper/payor split, transit coverage |

---

## Drillthrough pages

| Page | Drillthrough field | Purpose |
|---|---|---|
| Service Detail | `Dim_Service[ServiceGroup]` | Monthly performance, spend, late split, account usage for one service |
| Account Detail | `Dim_Account[AccountKey]` | Volume, spend, delays, claims, accessorials for one account |
| Month Detail | `Dim_Date[MonthKey]` | What happened in one month across services, accounts and claims |
| Location Detail | `Dim_Account[State]` | Geographic performance and exception patterns |

Each carries a back button and a header card naming the drilled value. Keep
`Dim_Date` filters flowing through on Service and Account Detail — a reviewer who
drills from a Q2 view expects Q2 detail, not the full year.

**Account Detail is the workhorse.** Because claims are account-grain, it is the only
page where reliability, cost and claims for a single entity appear together and can be
read as one story.
