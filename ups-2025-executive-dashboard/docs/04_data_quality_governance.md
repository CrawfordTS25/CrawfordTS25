# Data quality, thresholds and governance

Every rule here was derived from a defect actually present in the supplied extracts,
not from a generic checklist. Each is implemented in `etl/ups_etl.py`, mirrored in
`powerbi/powerquery/`, and reported on the Data Quality page.

---

## 1. The critical defect: year-to-date files overlap monthly files

**Severity: would silently double revenue and volume.**

UPS supplies Volume & Net Spend in two layouts, and some deliveries are cumulative:

| File | Layout | Reporting period | Contains |
|---|---|---|---|
| `1-JAN_…Volume & Net Spend` | Monthly VnR | January 2025 | January |
| `2-FEB_…Volume & Net Spend` | **VnR_YTD 2025** | Jan–Feb 2025 | **January + February** |
| `3-MAR_…VnS` | VnS | March 2025 | March |
| `4-APR_…VnS` | VnS | April 2025 | April |

A "Get Data → Folder" append — the approach the build guide describes, and the natural
one — loads January twice.

Measured on these files:

| | Volume | Net spend |
|---|---|---|
| January, correct | 79,359 | $1,207,910 |
| January, naive append | 158,718 | $2,415,819 |
| **Error** | **+100%** | **+100%** |

No error is raised. No row count looks wrong. The annual total is simply inflated by
about 40% and remains internally consistent throughout.

**Rule.** Deduplicate on `(Year, Month, AccountKey, RawProduct)`, preferring the file
whose *reporting period is* that month over one that merely *contains* it. Every
suppressed row is written to `DQ_ExcludedRows.csv` with its reason. Current load:
**161 rows suppressed**.

In Power Query this needs `Table.Buffer` before `Table.Distinct` — without it the sort
order is not guaranteed to be honoured and the wrong row can win non-deterministically.

---

## 2. `@@` is a masked sub-parent, not a sentinel

**Severity: silently deletes real international volume.**

Some rows carry `@@` in the Sub-Parent Number and Name. The obvious response — filter
it out with the Grand Total rows — is wrong. The account number, address and activity
on those rows are real:

```
@@ | @@ | <account no.> | <account name> | <city, state> | WW EXPRESS PM / SAVER PKG | 11 pcs | $1,790.28
```

*(Account identifiers are masked here; the real values are in the local extracts.)*

`@@` masks the *sub-parent assignment*, not the shipment.

**Rule.** Reject a row only when it is a Grand Total line or has no account number at
all. Retain masked sub-parents, relabel them `Unassigned Sub-Parent`, and flag them
with `IsMaskedSubParent` so the volume is visible and auditable rather than absent.

*This rule was added after the first ETL run reconciled 11 shipments short against the
source and the discrepancy was traced back.* An unexplained variance against source is
always worth chasing to the row.

---

## 3. Two source vocabularies for the same services

**Severity: makes the recommendation impossible if unhandled.**

Volume & Net Spend and Time-in-Transit describe the same services with entirely
different product names, and neither list is a subset of the other:

| Volume & Net Spend (~30 products) | Time-in-Transit (11 products) | Service Group |
|---|---|---|
| `GROUND PKG`, `GROUND CWT`, `STANDARD GROUND` | `GROUND` | Ground |
| `NDA REG / EXPRESS PKG`, `…LTR`, `…CWT` | `NEXT DAY AIR` | Next Day Air / Express |
| `NDA PM / EXPRESS SAVER PKG`, `…LTR` | `NEXT DAY AIR SAVER` | Next Day Air Saver |
| `2DA REG / EXPEDITED PKG`, `…LTR` | `SECOND DAY AIR` | 2nd Day Air / Expedited |
| `WW EXPRESS REG PKG`, `WW EXPEDITED / 2DA PKG`, … | `INTERNATIONAL EXPRESS`, … | International (4 groups) |

Without a bridge there is no way to put cost and reliability for the same service on
the same row, and the entire service comparison collapses.

**Rule.** `Dim_ServiceMapping` is a controlled, version-controlled table with grain
`(SourceSystem, RawProduct)`. Each fact query joins to a filtered copy of it and
materialises a `ServiceGroup`. An unmapped product routes to `Unmapped - Review` and is
counted on the Data Quality page — never silently absorbed into a neighbouring group.

---

## 4. Shipper View and Payor View are different populations

Time-in-Transit is a **Shipper View** (packages despatched). Volume & Net Spend is a
**Payor View** (packages billed). For March: 67,091 measured against 68,527 billed —
**97.9%**, a real and consistent gap, not an error.

**Rule.** `ViewType` is carried onto every fact row. Delivery metrics use
`[Packages Measured]` as the denominator; claims and cost metrics use
`[Rankable Shipments]`. The two are never interchanged, and `[Measured vs Billed
Coverage %]` reports the gap — computed *over the months transit actually covers*, since
dividing one month of measured packages by four months of billed volume would report
23% coverage and look like a catastrophic failure.

---

## 5. Zero-volume spend rows

128 rows carry **$95,812** of net spend against zero shipments — billing adjustments,
`MISC / UNC` charges, and re-rating credits.

**Rule, and it is deliberately not the obvious one.** Do **not** apply `Volume > 0` at
report level. That spend is real and appears on the invoice; filtering it globally makes
the dashboard's net spend disagree with the bill, and the first person to check loses
confidence in everything else on the page.

Instead:

- Retained in all financial totals.
- Excluded at *visual* level from per-shipment rates, where it would divide by nothing.
- Reported as `[Unattributed Spend %]` on the Data Quality page.

The same reasoning applies to `MISC / UNC` — **$91,110** of net spend excluded from
service rankings but present in every spend total.

---

## 6. Never average a percentage

The Time-in-Transit extract supplies an `On Time %` column per row. **It is not
loaded.**

Averaging it across the March file returns **≈98.2%** against a true **96.46%**,
because a 4-package service is weighted equally with a 47,916-package one. Loading the
column at all invites someone to drop it into a visual, where it will be averaged by
default and produce a number that is wrong in a way nobody notices.

**Rule.** Load the counts. Compute `SUM(on-time) / SUM(measured)` in DAX. Any ratio in
this model is a sum divided by a sum.

---

## 7. Completed-month and coverage flags

`Dim_Date` is generated for the full calendar year, not derived from the data. A date
table built from the distinct months present collapses the axis — if a month is missing,
a trend line joins the months either side of it and the gap disappears.

| Flag | Meaning |
|---|---|
| `IsCompletedMonth` | The calendar month has ended as at the as-of date |
| `IsLoaded` | A fact table has rows for that month |
| `IsReportable` | Both — the only flag that should gate a trend or annual comparison |

The three facts do not have to cover the same months, and currently do not: Volume 4
months, Transit 1, Claims 1. `[Coverage Summary]` states all three separately on every
page, because an annual on-time figure built on one month must never be presented as if
it were built on twelve.

---

## 8. Free integrity check: accessorial reconciliation

The accessorial extract decomposes the same net spend the Volume & Net Spend extract
reports in total. For March both sum to **$1,053,748.13** — agreement to the cent.

**Rule.** Wire this to `[Reconciliation Status]` on the Data Quality page. A non-zero
variance means one of the two files is stale, filtered, or partially loaded. It costs
nothing and catches a class of load error that nothing else in the model would detect.

---

## 9. Structural limitation: claims carry no service key

The claims extract has Sub-Parent, Account, Claims Category — and no product, service or
tracking number.

**Rule.** No relationship from `Fact_Claims` to `Dim_Service`. Not a many-to-many
through the account, not a bi-directional filter. A service slicer must visibly do
nothing to a claims visual.

Filtering claims by service through the account path returns "claims for accounts that
used this service" — for an account using five services, the same claim count five times
over — and any reader will take it as claims caused by that service. A blank is a
correct answer to an unanswerable question; a plausible wrong number is not.

An allocated proxy exists (`[Loss Claims (Allocated Proxy)]`) for the case where
leadership insists on a service view. It is confined to the Data Quality page and
analyst drillthrough, it is labelled, and it is circular by construction: it assumes
loss risk is uniform across services within an account, which is the hypothesis it would
be used to test.

**Resolution: request a service or tracking-number field on the claims export.** This
single change unlocks 50% of the recommendation framework.

---

## Governance summary

| Control | Setting | Reported by |
|---|---|---|
| YTD deduplication | On, single-period preferred | `[Duplicates Suppressed]` |
| Masked sub-parent | Retained and relabelled | `[Masked Sub-Parent Volume]` |
| Completed month | Trend and annual pages only | `[Missing Months List]` |
| Volume > 0 | Visual level only, never report level | `[Unattributed Spend %]` |
| MISC / UNC | Excluded from rankings, retained in totals | `[Excluded Adjustment Spend]` |
| Qualification flag | On ranking visuals only | `[Qualification Status]` |
| Unmapped products | Routed to review bucket | `[Unmapped Product Rows]` |
| Spend reconciliation | Checked per month | `[Reconciliation Status]` |
| Claims → service | No relationship | `[Claims Attribution Warning]` |

Hidden filters are quality controls, not concealment. The obligation that comes with
each is that the report can always say exactly what it excluded, how much, and why —
which is what the Data Quality page is for.
