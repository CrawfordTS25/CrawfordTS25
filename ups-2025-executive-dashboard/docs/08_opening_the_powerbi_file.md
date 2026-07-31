# Opening the Power BI file

## What you have

`dist/UPS_2025_Executive_Dashboard.pbit` — a Power BI **template**: the full data
model (8 tables, 11 relationships, 112 measures) and an 8-page report, with no data
embedded. Opening it in Power BI Desktop loads your data and gives you a live model.
**File → Save As → .pbix** produces the .pbix.

## Why a .pbit and not a .pbix directly

A .pbix stores its model in a `DataModel` part: the Analysis Services tabular model
serialised in a proprietary, compressed format that only Power BI Desktop and the AS
engine can write. There is no external tool — Microsoft's or anyone else's — that
emits one. A .pbit is the same package with the data removed and the model expressed
as plain TMSL JSON, which *is* authorable.

So the .pbit is not a lesser deliverable; it is the only form this can take before it
has been through Desktop once. The first Save As is the step that mints the .pbix.

---

## Steps

**1. Produce the data.** The model reads the star-schema CSVs, not the raw extracts:

```bash
python etl/ups_etl.py --raw data/raw --out data/processed --report
```

Note the absolute path of `data/processed`. For the synthetic demo instead:

```bash
python etl/make_sample_data.py --out data/sample
```

**2. Open `dist/UPS_2025_Executive_Dashboard.pbit`** in Power BI Desktop.

**3. Enter the parameters** when prompted:

| Parameter | Value |
|---|---|
| `p_DataFolder` | Absolute path to the folder holding the CSVs, no trailing slash — e.g. `C:\Users\you\ups-2025-executive-dashboard\data\processed` |
| `p_ReportingYear` | `2025` |

**4. Apply the theme.** View → Themes → Browse for themes →
`powerbi/theme/UPS_Executive_Theme.json`.

The theme is applied here rather than embedded in the template on purpose: a
malformed custom-theme resource is one of the few things that stops a .pbit opening
at all, and it is not worth risking the whole file for one click.

**5. Set the two sort-by columns.** Select `Dim_Date[MonthName]` → Column tools →
Sort by column → `SortOrder`. Repeat for `MonthYearLabel`.

Without this every month axis renders alphabetically — Apr, Aug, Dec, Feb. It cannot
be set from TMSL reliably across Desktop versions, so it is the one manual model step.

**6. File → Save As → `.pbix`.**

---

## Why the model loads CSVs rather than the raw Excel files

`powerbi/powerquery/` contains a complete Power Query implementation that reads the
raw UPS folder directly and encodes every parsing rule in M — the two extract
layouts, the YTD deduplication, the masked sub-parent handling, the service-vocabulary
bridge.

The template does not use it, because that M has never been executed. There is no
Power BI Desktop in the environment this was built in, and several hundred lines of
untested M in a template that fails on load is worse than no template at all. The
Python ETL *has* been run against your real files and reconciles to them exactly.

Once you have the model open and can iterate in Desktop, moving to direct refresh is
a contained piece of work: paste the queries from `powerbi/powerquery/`, point
`p_SourceFolder` at the raw folder, and delete the CSV step. Do it one query at a
time and reconcile January against the source after the first — that is where the
YTD double-count would show up.

---

## What is in the file

**Model** — 8 tables, 11 relationships, 112 measures in five display folders, plus
the `Volume Threshold` and `Share Threshold` what-if parameters wired to the
qualification logic.

**Report** — 8 pages, 70 visuals:

| Page | Contents |
|---|---|
| 1 Executive Overview | 5 KPI cards, OTD trend, recommendation callout, service scorecard, volume mix |
| 2 Service Performance | OTD by service, lateness severity split, reliability detail with confidence labels |
| 3 Cost and Volume | Volume and spend by month, the paired cost views, cost bridge |
| 4 Claims and Exceptions | Attribution notice, claims KPIs, category split, account concentration table |
| 5 Account and Location | Account scorecard, region and state breakdowns, transit coverage gaps |
| 6 Annual Recommendation | Recommendation matrix, score basis, threshold sliders, score components |
| 7 Accessorial and Cost Drivers | Charge decomposition, monthly trend, avoidable-cost note |
| 8 Data Quality | Coverage, exclusions, mapping inventory, known limitations |

Every page carries the `[Data Basis Banner]` card.

---

## Things the template does not do

These are in `report_spec/` and are quicker to add in Desktop than to hand-author
into the layout JSON:

- **Drillthrough pages** (Service / Account / Month / Location detail).
- **Synced slicers.** Page 6 has its threshold sliders; the global Year / Quarter /
  Month / Service / Scope / Account slicers need adding and syncing per
  `report_spec/01_slicer_filter_matrix.md`.
- **Conditional formatting** — data bars on the loss-rate index column, background
  colour on the banner card driven by `[Data Basis Banner Colour]`.
- **Bookmarks**, including the `Threshold: none` teaching bookmark.
- **Visual interaction overrides** — set KPI cards to *no interaction*.
- **Error bars** on the OTD chart from `[OTD Wilson Lower Bound]`.

---

## If the template will not open

Power BI Desktop is strict about package structure and its expectations shift between
versions. The generated package validates against everything checkable without
Desktop — encodings, part manifest, TMSL structure, every visual's field references —
but it has not been opened in Desktop, because there isn't one in the build
environment. Be aware of that before relying on it in front of an audience.

Fallbacks, in order:

**1. The PBIP project** in `dist/pbip/`. Power BI Desktop opens
`UPS_2025_Executive_Dashboard.pbip` directly (Preview features → Power BI Project
must be enabled). This is Microsoft's supported text format and has a different, more
tolerant loader than the .pbit package reader.

**2. Rebuild the template** if you want to change defaults:

```bash
python powerbi/build_pbit.py --data-folder "C:\your\path\data\processed"
```

**3. Build the model by hand** from `powerbi/dax/` and `powerbi/powerquery/`
following `docs/06_build_checklist.md`. Slower, but every artefact needed is in the
repo and the checklist has a verification step per item.

If it fails, the error text matters — Desktop usually names the part it rejected,
which points straight at the fix in `powerbi/build_pbit.py`.

---

## Regenerating

`powerbi/build_pbit.py` reads the `.dax` files as its source of truth, so editing a
measure and rebuilding keeps the template in step. The build fails rather than
emitting a broken file if any of these are wrong:

- a measure references a table or column that does not exist
- a measure filters a table with no relationship to any fact (a silent no-op that
  returns wrong numbers with no error)
- a measure uses daily-grain time intelligence against the month-grain date table
- a visual projects a field absent from its own prototype query
- a visual falls outside the canvas

Those checks exist because the first three were real defects in this build, caught by
writing the validator rather than by reading the DAX again.
