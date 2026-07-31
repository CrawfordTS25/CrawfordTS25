# Build checklist

Work top to bottom. Each item has a stated verification, because "done" on a data model
means "checked", not "attempted".

---

## Stage 1 — Source and load

- [ ] Raw extracts placed in the source folder. Verify: every expected month present for
      all four extract types; note gaps rather than assuming none.
- [ ] YTD files identifiable by filename (`…_YTD.xlsx`). **Verify: this is the dedupe
      precedence signal — an unmarked YTD file is the one input that can still cause a
      silent double-count.**
- [ ] `p_SourceFolder`, `p_ReportingYear`, `p_AsOfDate` parameters created.
- [ ] Helper functions created (`fnCleanText`, `fnParsePeriod`, `fnViewType`,
      `fnIsSentinel`, `fnSubParentLabel`, `fnPromoteUpsHeader`).
- [ ] `Dim_ServiceMapping` loaded from `etl/service_mapping.csv`.
- [ ] Four fact queries load without error.
- [ ] **Reconcile January against the source file.** Verify: total volume matches the
      monthly extract exactly, *not* the monthly plus the YTD file. Getting exactly
      double is the failure signature.
- [ ] `DQ_ExcludedRows` reviewed. Verify: every rejection reason is one you intended.
- [ ] `DQ_UnmappedProducts` is empty, or every entry has been added to the mapping table.

**Gate: do not proceed until source totals reconcile to the cent.** Everything
downstream inherits a load error and looks internally consistent while doing so.

---

## Stage 2 — Model

- [ ] `Dim_Date` generated for the full calendar year, not derived from the facts.
- [ ] `Dim_Date` left **unmarked** as a date table. It is month grain, and DAX time
      intelligence needs day grain — see `powerbi/model/relationships.md`. Verify:
      `[YTD Shipments]` and `[OTD % PM]` return values, not blanks.
- [ ] **`MonthName` and `MonthYearLabel` sorted by `[SortOrder]`.** Verify: a month axis
      reads Jan, Feb, Mar — not Apr, Aug, Dec. This silently resets when a column is
      retyped; re-check after any model edit.
- [ ] `Dim_Account` built from the union of all three facts, not from Volume & Spend
      alone.
- [ ] `Dim_Service` created (one row per Service Group) and related to the facts.
- [ ] All relationships single-direction. Verify: no bi-directional filters anywhere.
- [ ] **No relationship from `Fact_Claims` to `Dim_Service`.** Verify: a service slicer
      visibly does nothing to a claims visual. That is the intended behaviour.
- [ ] `Fact_TimeInTransit[On Time %]` not loaded. Verify: the column is absent from the
      field list entirely.
- [ ] Key columns hidden; only measures exposed to the report view.

---

## Stage 3 — Measures

- [ ] All five DAX files loaded, organised into display folders.
- [ ] What-If parameters created: `Volume Threshold` (0–10,000, step 250, default 1,000)
      and `Share Threshold` (0–0.10, step 0.005, default 0.01).
- [ ] Formatting applied: currency `$#,##0`, rates `0.0%`, per-10k rates `0.0`.
- [ ] **Verify `[On-Time Delivery %]` against the source Grand Total row.** For March
      that is 0.9646. If it reads ~98.2% the measure is averaging a percentage.
- [ ] **Verify `[Reconciliation Status]` returns "Reconciled"** for any month with
      accessorial detail.
- [ ] Verify `[Annual Qualification Flag]` responds to the What-If sliders.
- [ ] Verify `[Score Basis]` reports the *effective* weights, not the specified ones.
- [ ] Verify `[Service Volume Mix %]` sums to 100% across services. If it returns
      100% on *every* row, a measure is filtering an unrelated table and the
      `REMOVEFILTERS` is a no-op.

---

## Stage 4 — Report

- [ ] Theme applied (`powerbi/theme/UPS_Executive_Theme.json`).
- [ ] Eight pages built per `report_spec/00_page_layouts.md`.
- [ ] `[Data Basis Banner]` card on every page.
- [ ] Global slicers created and synced per `report_spec/01_slicer_filter_matrix.md`.
- [ ] **Month and Account slicers removed from the Recommendation page.** Verify: this
      is deliberate, not an omission.
- [ ] Hidden filters applied at the stated levels — note that `Volume > 0` is visual
      level, never report level.
- [ ] Four drillthrough pages built, each with a back button.
- [ ] Dynamic titles bound to `[Title - …]` measures.
- [ ] KPI cards set to **no interaction**. Verify: clicking a card changes nothing.
- [ ] Both cost views adjacent on the Cost page, with the weight-mix annotation.
- [ ] `[Claims Attribution Warning]` pinned on the Claims page.
- [ ] Bookmarks created, including `Threshold: none`.

---

## Stage 5 — Validation before publishing

- [ ] Annual totals reconcile against source extracts.
- [ ] Every KPI card cross-checked against the HTML dashboard
      (`python dashboard/build_dashboard.py --data data/processed --out dashboard/live.html`).
      **Any disagreement is a real defect in one of the two — resolve it, do not pick a
      favourite.**
- [ ] Ranking sanity check: toggle `Threshold: none` and confirm a low-volume service
      jumps to the top. If it does not, the qualification logic is not wired to the
      ranking visual.
- [ ] Confirm no visual shows a service-level loss claim rate.
- [ ] Data Quality page accounts for every excluded row.
- [ ] Missing months are visible as gaps on trend visuals, not collapsed away.
- [ ] Report opens on the Executive Overview with slicers cleared.
- [ ] Refresh tested from the published location, not just the desktop.

---

## Stage 6 — Before it reaches leadership

- [ ] The reporting basis banner accurately describes coverage. **With one month of
      transit data it must read PROVISIONAL.**
- [ ] The recommendation callout carries its confidence qualifier.
- [ ] The claims limitation is stated on the page, not only in the appendix.
- [ ] Someone other than the author has read the Executive Overview cold and can state
      what the recommendation is and what it rests on.

That last item is the real test. Every control in this build exists to make the report
survive being read by someone who was not in the room when it was made.
