# Standalone Power Query — build with nothing but Power BI Desktop

These queries read your four UPS Excel extracts **directly**. No Python, no CSV
files, no template, nothing to download. Paste each one into Advanced Editor and
the model builds itself.

## Why these differ from `../powerquery/`

`../powerquery/` is the general, folder-scanning implementation: it discovers any
number of monthly files, classifies sheets by shape, and deduplicates the
year-to-date overlap at runtime. It is the right long-term answer and it is a few
hundred lines of M.

These are deliberately **simpler and safer**. You have four known files, so each
query reads one known sheet at one known offset. Specifically:

- **No runtime deduplication.** The February file is year-to-date — it holds
  January *and* February. Rather than dedupe, the February query simply filters to
  month 2 and January comes from the January file. That removes the single most
  intricate piece of M in the build, and it cannot get the answer wrong.
- **No CSV dependency.** The service mapping table is inlined as a literal
  `#table`, so there is no file to keep alongside the report.
- **No header detection.** Row offsets are hard-coded, because the layouts are
  known and verified.

Every column offset and row offset here was verified against your real extracts by
the Python ETL, which reconciles to them exactly: January volume 79,359; March
on-time 96.46%; March accessorial detail summing to net spend to the cent.

## Order — paste in this order, the later ones reference the earlier

| # | Query | Notes |
|---|---|---|
| 1 | `p_Folder` | Parameter, not a query. See 01. |
| 2 | `Dim_ServiceMapping` | Inline table, no source file |
| 3 | `Fact_VolumeSpend` | All four months |
| 4 | `Fact_TimeInTransit` | March only |
| 5 | `Fact_Claims` | March only |
| 6 | `Fact_Accessorial` | March only |
| 7 | `Dim_Date` | Generated |
| 8 | `Dim_Account` | Built from the facts |
| 9 | `Dim_Service` | One row per service group |

## Before you start — rename your four files

The queries reference these exact names. Put all four in one folder:

```
UPS_2025_01_VolumeSpend.xlsx        (your January file)
UPS_2025_02_VolumeSpend_YTD.xlsx    (your February file — the YTD one)
UPS_2025_03_AllTabs.xlsx            (your March file — the one with 4 tabs)
UPS_2025_04_VolumeSpend.xlsx        (your April file)
```

## Adding May onwards

Copy the `Apr` step inside `Fact_VolumeSpend`, change the file name and the month
number, and add it to the `Table.Combine` list. If a later file arrives as a
year-to-date extract, filter it to its own month exactly as the February step does.
