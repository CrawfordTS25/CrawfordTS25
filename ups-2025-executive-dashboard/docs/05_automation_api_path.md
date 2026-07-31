# Automation, source upgrades and refresh path

Ordered by value delivered, not by technical difficulty. The first item is worth more
than the rest combined.

---

## Priority 1 — Get a service key onto the claims export

**Unlocks 50% of the recommendation framework. Nothing else on this list comes close.**

The claims extract carries Sub-Parent, Account and Claims Category. It does not carry a
product, service, or tracking number, so loss claim rate and exception rate — 30% and
20% of the specified scoring weights — cannot be computed by service. The score
currently runs on reliability and cost alone, reweighted to 80/20.

**Ask the UPS account team for, in order of preference:**

1. **Tracking number** on each claim row. Best outcome: joins to shipment detail and
   gives service, weight, origin, destination and date — enabling loss rate by service,
   by lane, and by weight band.
2. **Service / product** field on each claim row. Sufficient for the scoring framework.
3. **Claim status** (open / paid / denied / withdrawn). Separates a carrier-performance
   problem from a claims-administration problem — the current 43.6% recovery rate could
   be either.

The DAX is already written for this. `Score - Loss Risk` and `Score - Exception Risk`
exist in full, gated behind a `[Claims Service Key Available]` flag. Flip it to 1, point
the measures at the real column, and the weight reallocation unwinds itself back to the
specified 40/30/20/10 with no other change.

---

## Priority 2 — Complete the monthly file set

| Source | Have | Need |
|---|---|---|
| Volume & Net Spend | Jan, Feb, Mar, Apr | May–Dec |
| Time-in-Transit | **Mar only** | **Jan, Feb, Apr–Dec** |
| Claims | **Mar only** | **Jan, Feb, Apr–Dec** |
| Accessorial | **Mar only** | All months |

Time-in-Transit is the binding constraint on the whole analysis. One month cannot
distinguish a consistently reliable service from one having a good month, which is
exactly the question an annual recommendation has to answer.

The March file arrived with all four tabs (TnT, Accessorial, Claims, VnS); January,
February and April did not. **Ask for the March file's format as the standing monthly
deliverable** — this is likely a report-subscription setting rather than a new
development request, and it is the cheapest large win available.

---

## Priority 3 — Standardise naming and folder structure

The pipeline classifies sheets by *shape* rather than name precisely because UPS renames
tabs between months (`Monthly VnR by Product by Accou`, `VnR_YTD 2025`, `VnS`). That
resilience is deliberate, but consistent naming still removes a class of ambiguity:

```
/UPS/2025/
  VolumeSpend/   UPS_2025_01_VolumeSpend.xlsx …
  TimeInTransit/ UPS_2025_01_TnT.xlsx …
  Claims/        UPS_2025_01_Claims.xlsx …
  Accessorial/   UPS_2025_01_Accessorial.xlsx …
```

**Flag YTD deliveries explicitly in the filename** (`…_YTD.xlsx`). The dedupe logic uses
this as its precedence signal; a YTD file that is not marked as one is the one input
that could still produce a silent double-count.

---

## Priority 4 — Move the source folder somewhere a gateway can reach

A local `C:\` path refreshes on the desktop and fails in the Power BI Service. Move to
SharePoint or a OneDrive-synced folder before publishing, and change only the
`p_SourceFolder` parameter.

---

## Priority 5 — Automate delivery

| Data need | Source | Action |
|---|---|---|
| Volume and spend | UPS billing / reporting export | Confirm whether the monthly extract can be scheduled to SFTP or a mailbox |
| Transit performance | Time-in-Transit scheduled export | Confirm month, service, packages measured and late counts are all present |
| Claims | Claims export or claims API | **Request tracking number, service, status and paid amount** (see Priority 1) |
| Shipment events | UPS Tracking / Quantum View | Only needed if per-shipment analysis is wanted; the aggregate extracts cover the current questions |
| Refresh | Power BI scheduled refresh | Configure after the source location and schema are stable, not before |

A note on sequencing: automate delivery *after* the schema stops changing. Automating
an unstable source produces a pipeline that breaks monthly and erodes trust in the
report faster than manual loading ever would.

---

## Priority 6 — Incremental refresh

Only worth configuring once the model moves to a database or a large automated source.
At the current volume — a few thousand rows per month — a full refresh takes seconds and
incremental refresh adds partition-management complexity for no benefit.

When it is warranted: `RangeStart` / `RangeEnd` parameters filtering on
`Fact_VolumeSpend[DateKey]`, archive 3 years, incremental 3 months.

**Caution.** Incremental refresh partitions data by date and only reprocesses recent
partitions. The YTD deduplication in this pipeline compares rows *across files* for the
same month — if a YTD file arrives after its months are already partitioned and sealed,
the dedupe will not see the overlap. If incremental refresh is adopted, either move
deduplication upstream into a staging layer, or guarantee that YTD files are never
loaded after their constituent months have been processed.

---

## What to validate with IT and the Power BI administration team

- Gateway availability for the chosen source location
- Workspace licensing (Pro vs Premium) — Premium is required for incremental refresh
- Row-level security requirements: should a business unit see only its own accounts?
- Retention: how many years of extracts are kept, and where
- Whether UPS Developer / API access is already licensed to the firm

## What to validate with the UPS account team

- Standing subscription to the all-tabs monthly report format
- Service or tracking key on the claims export **(Priority 1)**
- Claim status field availability
- Confirmation that all firm accounts are in scope for the Time-in-Transit extract —
  an account with volume and no transit coverage is invisible in every reliability
  figure on the report, and the Account and Location page has a table that names them
- What drives the SCC Audit Fee ($20,171 in March across 43 units)
