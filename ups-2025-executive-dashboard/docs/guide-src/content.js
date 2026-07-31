// Single source of truth for the guide. Rendered to .docx by render_docx.js and
// to .html (then PDF) by render_html.js, so the two cannot drift apart.
//
// Run shorthand:  s('plain')  b('bold')  i('italic')  c('code')

const s = (text) => ({ text });
const b = (text) => ({ text, bold: true });
const i = (text) => ({ text, italic: true });
const c = (text) => ({ text, code: true });

module.exports = {
  meta: {
    eyebrow: "UPS 2025 Annual Shipping Performance",
    title: "Converting the Power BI Template",
    subtitle: "From .pbit to .pbix — step by step, with verification",
    facts: [
      [s("File: "), c("dist/UPS_2025_Executive_Dashboard.pbit")],
      [s("Contents: "), s("8 tables · 11 relationships · 112 measures · 8 report pages · 70 visuals")],
      [s("Requires: "), s("Power BI Desktop (free), Windows. Roughly 15 minutes end to end.")],
    ],
    header: "UPS 2025 Executive Dashboard  ·  .pbit → .pbix",
  },

  blocks: [
    { t: "callout", kind: "warn", label: "Read this first", body: [
      s("This template has not been opened in Power BI Desktop. It was generated in a Linux "
      + "environment where no copy of Desktop exists. Everything checkable without one is "
      + "validated — file encodings, the package manifest, the model schema, and every field "
      + "reference in every visual — and the generator refuses to emit a file that fails those "
      + "checks. But the first open is still a test. Section 10 covers what to do if it fails, "
      + "and there are two working fallbacks."),
    ]},
    { t: "pagebreak" },

    { t: "h1", text: "1. Why there is a template and not a .pbix" },
    { t: "p", runs: [s("A .pbix stores its data model in a part called DataModel: the Analysis "
      + "Services tabular model, serialised in a proprietary compressed format that only Power BI "
      + "Desktop and the Analysis Services engine can write. No external tool produces one — not "
      + "Microsoft's, not anyone's.")] },
    { t: "p", runs: [s("A .pbit is the same package with the data removed and the model expressed "
      + "as plain TMSL JSON, which can be authored externally. Opening it in Desktop loads your "
      + "data and materialises a live model. The first Save As is the step that mints the .pbix.")] },
    { t: "p", runs: [s("So the template is not a lesser deliverable. It is the only form this can "
      + "take before it has been through Desktop once, and "),
      b("that pass is what these directions walk through.")] },

    { t: "h1", text: "2. Before you start" },
    { t: "table", widths: [2600, 6760], header: ["You need", "Detail"], rows: [
      [[[s("Power BI Desktop")]], [[s("Free from the Microsoft Store or powerbi.microsoft.com/desktop. "
        + "Windows only — there is no Mac build.")]]],
      [[[s("The template")]], [[c("dist/UPS_2025_Executive_Dashboard.pbit")]]],
      [[[s("The repository")]], [[s("For the theme file and the DAX/M sources, in case you need a fallback.")]]],
      [[[s("Python 3.9+")]], [[s("Only to generate the data files in Step 1. Any recent version.")]]],
      [[[s("Your data")]], [[s("Either the real UPS extracts, or the synthetic sample that ships with the repo.")]]],
    ]},
    { t: "callout", kind: "info", label: "A note on the data path", body: [
      s("The model reads CSV files from a folder you nominate. Power BI needs an "), b("absolute"),
      s(" path — "), c("C:\\Users\\you\\ups-2025-executive-dashboard\\data\\processed"),
      s(", not a relative one. Have that path ready before Step 3, with no trailing backslash."),
    ]},

    { t: "h1", text: "3. Step 1 — Produce the data files" },
    { t: "p", runs: [s("The model loads the star-schema CSVs written by the ETL, not the raw Excel "
      + "extracts. Generate them first; the template will fail on load if the folder is empty.")] },

    { t: "h3", text: "Option A — your real UPS extracts" },
    { t: "p", runs: [s("Place the monthly extracts in "), c("data/raw/"), s(", then run:")] },
    { t: "code", lines: [
      "pip install -r etl/requirements.txt",
      "python etl/ups_etl.py --raw data/raw --out data/processed --report",
    ]},
    { t: "p", runs: [s("Note the absolute path of "), c("data/processed"),
      s(". Check the reconciliation summary it prints — if January's volume is exactly double what "
      + "the January extract shows, the year-to-date deduplication did not run.")] },

    { t: "h3", text: "Option B — the synthetic sample" },
    { t: "p", runs: [s("Use this to test the template, or to demonstrate the dashboard without "
      + "exposing client data.")] },
    { t: "code", lines: ["python etl/make_sample_data.py --out data/sample"] },

    { t: "h3", text: "What you should have" },
    { t: "p", runs: [s("Seven CSV files plus a manifest in the output folder:")] },
    { t: "table", widths: [4680, 4680], header: ["Fact tables", "Dimensions and manifest"], rows: [
      [[[c("Fact_VolumeSpend.csv")]], [[c("Dim_Date.csv")]]],
      [[[c("Fact_TimeInTransit.csv")]], [[c("Dim_Account.csv")]]],
      [[[c("Fact_Claims.csv")]], [[c("Dim_ServiceMapping.csv")]]],
      [[[c("Fact_Accessorial.csv")]], [[c("manifest.json")]]],
    ]},
    { t: "p", muted: true, runs: [s("If any are missing, the template fails with a file-not-found "
      + "naming that exact file, which makes the cause obvious.")] },

    { t: "h1", text: "4. Step 2 — Open the template" },
    { t: "p", runs: [s("Double-click "), c("UPS_2025_Executive_Dashboard.pbit"),
      s(", or from Desktop use File → Import → Power BI template.")] },
    { t: "p", runs: [s("Power BI Desktop opens a parameter dialog before it loads anything. This is "
      + "normal and is the defining behaviour of a template — it is asking where your data lives.")] },

    { t: "h1", text: "5. Step 3 — Enter the parameters" },
    { t: "table", widths: [2400, 6960], header: ["Parameter", "What to enter"], rows: [
      [[[c("p_DataFolder")]], [
        [s("The absolute path to the folder from Step 1. No trailing backslash.")],
        [c("C:\\Users\\you\\ups-2025-executive-dashboard\\data\\processed")],
      ]],
      [[[c("p_ReportingYear")]], [[s("2025")]]],
    ]},
    { t: "p", runs: [s("Click Load.")] },
    { t: "callout", kind: "warn", label: "The most common mistake", body: [
      s("A trailing backslash, or a path to the repository root rather than to the folder "
      + "containing the CSVs. Both produce a file-not-found error naming a path with a doubled "
      + "separator or a missing folder level — read the path in the error message and it tells you "
      + "which."),
    ]},

    { t: "h1", text: "6. Step 4 — Let the model load" },
    { t: "p", runs: [s("Desktop runs eight queries and builds the model. On the sample data this "
      + "takes a few seconds; on a full year of real extracts, under a minute.")] },
    { t: "p", runs: [s("When it finishes you should see, in the Data pane on the right:")] },
    { t: "table", widths: [3000, 6360], header: ["Item", "Expected"], rows: [
      [[[s("Tables")]], [[s("8 data tables plus Volume Threshold, Share Threshold, and _Measures")]]],
      [[[c("_Measures")]], [[s("112 measures in five numbered display folders")]]],
      [[[c("Dim_ServiceMapping")]], [[s("Present but hidden — it is the two-vocabulary mapping "
        + "table, needed by the Data Quality page and deliberately kept out of the field list")]]],
      [[[s("Report pages")]], [[s("8 tabs along the bottom, from Executive Overview to Data Quality")]]],
    ]},

    { t: "h1", text: "7. Step 5 — Two manual settings" },
    { t: "p", runs: [s("Two things cannot be set reliably from the template and must be applied by "
      + "hand. Both take under a minute and both matter.")] },

    { t: "h2", text: "5a. Apply the report theme" },
    { t: "p", runs: [s("View → Themes → Browse for themes → select:")] },
    { t: "code", lines: ["powerbi\\theme\\UPS_Executive_Theme.json"] },
    { t: "p", runs: [s("The theme carries a colour palette validated for colour-vision deficiency, "
      + "hairline gridlines, data labels off by default, and no dual-axis configuration.")] },
    { t: "p", muted: true, runs: [s("It is applied here rather than embedded in the template on "
      + "purpose: a malformed custom-theme resource is one of the few things that can stop a .pbit "
      + "opening at all, and that is not worth risking the whole file for one click.")] },

    { t: "h2", text: "5b. Set the month sort order" },
    { t: "p", runs: [s("In the Data pane, expand Dim_Date and do this twice:")] },
    { t: "table", widths: [900, 8460], header: ["", "Action"], rows: [
      [[[s("1")]], [[s("Select "), c("MonthName")]]],
      [[[s("2")]], [[s("Column tools ribbon → Sort by column")]]],
      [[[s("3")]], [[s("Choose "), c("SortOrder")]]],
      [[[s("4")]], [[s("Repeat all three for "), c("MonthYearLabel")]]],
    ]},
    { t: "callout", kind: "crit", label: "Why this is not optional", body: [
      s("Without it, every month axis in the report sorts alphabetically: Apr, Aug, Dec, Feb, Jan… "
      + "Trend lines become meaningless and it is easy not to notice, because the chart still looks "
      + "like a chart. Check the volume-by-month column chart on page 3 reads Jan through Dec before "
      + "you go further."),
    ]},

    { t: "h1", text: "8. Step 6 — Verify before you save" },
    { t: "p", runs: [s("Six checks. Each catches a specific, known failure mode, and each takes "
      + "seconds.")] },
    { t: "table", widths: [480, 3480, 5400], header: ["#", "Check", "What it catches"], rows: [
      [[[s("1")]], [[s("Page 3 volume chart reads Jan → Dec")]],
       [[s("The sort-by columns from Step 5b were not applied.")]]],
      [[[s("2")]], [[s("On-time delivery equals the "), i("Grand Total"),
        s(" row of the source Time-in-Transit extract (96.46% for March 2025)")]],
       [[s("A reading around 98.2% means a percentage is being averaged rather than weighted — a "
         + "4-package service counted equally with a 48,000-package one.")]]],
      [[[s("3")]], [[s("Page 8 shows Reconciliation Status = "), b("Reconciled")]],
       [[s("The accessorial detail must sum to net spend to the cent. A variance means one source "
         + "file is stale or partly loaded.")]]],
      [[[s("4")]], [[s("January volume matches the January extract, not double it")]],
       [[s("The year-to-date deduplication. February's extract contains January as well; a naive "
         + "load double-counts it with no error.")]]],
      [[[s("5")]], [[s("Service Volume Mix % sums to 100% across services")]],
       [[s("If it shows 100% on every row, a measure is filtering a table with no relationship to "
         + "the facts and the result is silently wrong.")]]],
      [[[s("6")]], [[s("The banner card on every page describes your actual coverage")]],
       [[s("With one month of transit data it must read PROVISIONAL, not ANNUAL.")]]],
    ]},
    { t: "callout", kind: "crit", label: "If check 2 or 4 fails", body: [
      s("Stop and fix it before saving. Both failure modes produce numbers that are internally "
      + "consistent and completely wrong — nothing downstream will look odd, and the error will "
      + "survive review. "),
      b("Getting exactly double is the signature of the year-to-date overlap."),
    ]},

    { t: "h1", text: "9. Step 7 — Save as .pbix" },
    { t: "table", widths: [900, 8460], header: ["", "Action"], rows: [
      [[[s("1")]], [[s("File → Save as")]]],
      [[[s("2")]], [[s("Set "), b("Save as type"), s(" to "), b("Power BI files (*.pbix)")]]],
      [[[s("3")]], [[s("Name it, for example "), c("UPS_2025_Executive_Dashboard.pbix")]]],
      [[[s("4")]], [[s("Save")]]],
    ]},
    { t: "p", runs: [s("That file is a full .pbix: model, data, and report in one. From here it "
      + "behaves like any other — Publish to send it to the Power BI Service, or share the file "
      + "directly.")] },
    { t: "callout", kind: "info", label: "Keep the template", body: [
      s("The .pbit stays useful. It is a fraction of the size, contains no data, and is the thing to "
      + "hand to a colleague who needs the same dashboard against their own folder. Regenerate it "
      + "any time from the DAX sources with "), c("python powerbi/build_pbit.py"), s("."),
    ]},

    { t: "h1", text: "10. Troubleshooting" },
    { t: "h2", text: "The template will not open at all" },
    { t: "p", runs: [s("Power BI Desktop is strict about package structure and its expectations "
      + "shift between versions. If Desktop rejects the file, the error text usually names the part "
      + "it did not like — note it, because it points straight at the fix.")] },
    { t: "p", runs: [s("Two working fallbacks, in order:")] },

    { t: "h3", text: "Fallback A — the Power BI Project" },
    { t: "p", runs: [s("Open "), c("dist\\pbip\\UPS_2025_Executive_Dashboard.pbip"), s(" instead.")] },
    { t: "p", runs: [s("This is Microsoft's supported text-based project format and uses a "
      + "different, more tolerant loader than the .pbit package reader. It contains the same model "
      + "and report.")] },
    { t: "p", runs: [s("You may need to enable it first: File → Options and settings → Options → "
      + "Preview features → "), b("Power BI Project (.pbip) save option"), s(", then restart Desktop.")] },

    { t: "h3", text: "Fallback B — build it by hand" },
    { t: "p", runs: [s("Slower, but everything needed is in the repository and nothing is lost:")] },
    { t: "table", widths: [2900, 6460], header: ["Source", "What it gives you"], rows: [
      [[[c("powerbi/powerquery/*.m")]], [[s("The queries, which read the raw extracts directly")]]],
      [[[c("powerbi/dax/*.dax")]], [[s("All 112 measures, in five files, ready to paste")]]],
      [[[c("powerbi/model/relationships.md")]], [[s("The relationship table and the reasoning behind "
        + "three specific joins")]]],
      [[[c("powerbi/report_spec/")]], [[s("Page layouts, the slicer matrix, and interaction rules")]]],
      [[[c("docs/06_build_checklist.md")]], [[s("The build order, with a verification step for every item")]]],
    ]},

    { t: "h2", text: "Common errors during load" },
    { t: "table", widths: [3200, 3100, 3060], header: ["Symptom", "Cause", "Fix"], rows: [
      [[[s("\u201CWe couldn't find the file\u201D naming a CSV")]],
       [[s("Wrong p_DataFolder, or Step 1 not run")]],
       [[s("Check the path is absolute and has no trailing backslash")]]],
      [[[s("A column type conversion error")]],
       [[s("The CSVs were opened and re-saved in Excel, changing date or number formats")]],
       [[s("Re-run the ETL; do not open the CSVs in Excel between steps")]]],
      [[[s("Blank visuals on every page, no error")]],
       [[s("The model loaded but the tables are empty")]],
       [[s("Check the CSVs have rows beyond the header line")]]],
      [[[s("Blank on-time delivery, everything else fine")]],
       [[s("No Time-in-Transit data for the months loaded")]],
       [[s("Expected if only some months have transit extracts — the banner will say so")]]],
      [[[s("Month axes alphabetical")]],
       [[s("Step 5b not applied")]],
       [[s("Set the sort-by columns")]]],
    ]},

    { t: "h1", text: "11. After the .pbix exists" },
    { t: "p", runs: [s("The template deliberately omits several things that are faster to add in "
      + "Desktop than to hand-author into the report definition. All are specified in "),
      c("powerbi/report_spec/"), s(".")] },
    { t: "table", widths: [3000, 6360], header: ["Addition", "Why it matters"], rows: [
      [[[s("Global synced slicers — Year, Quarter, Month, Service Group, Domestic/International, "
        + "Account, State")]],
       [[s("The spec says which pages each appears on, and which pages deliberately omit one")]]],
      [[[s("Drillthrough pages — Service, Account, Month, Location detail")]],
       [[s("Keeps the main pages clean while allowing investigation. Account Detail is the "
         + "workhorse, since claims are account-grain")]]],
      [[[s("Conditional formatting — data bars on the loss-rate index; banner background driven by "
        + "[Data Basis Banner Colour]")]],
       [[s("Turns the concentration table from a list into an obvious answer")]]],
      [[[s("Bookmarks, including \u201CThreshold: none\u201D")]],
       [[s("Toggling it in a review shows a tiny service jumping to the top of the ranking, which "
         + "makes the case for volume governance better than any slide")]]],
      [[[s("Set KPI cards to no interaction")]],
       [[s("The default is Highlight; a user who clicks a card and sees the page change assumes the "
         + "click meant something")]]],
      [[[s("Error bars on the on-time chart from [OTD Wilson Lower Bound]")]],
       [[s("Shows how much of each percentage is knowledge and how much is a small sample")]]],
    ]},

    { t: "h1", text: "12. Moving to direct refresh from the raw extracts" },
    { t: "p", runs: [s("The template loads CSVs produced by the Python ETL. That was a deliberate "
      + "choice: the Power Query implementation that reads the raw UPS folder directly is several "
      + "hundred lines of M that has never been executed, and a template that fails on load is worse "
      + "than none. The ETL has been run against the real extracts and reconciles to them exactly.")] },
    { t: "p", runs: [s("Once the model is open and you can iterate in Desktop, switching is "
      + "contained work:")] },
    { t: "table", widths: [900, 8460], header: ["", "Step"], rows: [
      [[[s("1")]], [[s("Add the parameters from "), c("powerbi/powerquery/00_Parameters.m")]]],
      [[[s("2")]], [[s("Add the helper functions from "), c("01_fnHelpers.m"),
        s(" as blank queries, named exactly as shown")]]],
      [[[s("3")]], [[s("Replace one fact query at a time, starting with Volume & Spend")]]],
      [[[s("4")]], [[s("After the first, reconcile January against the source extract. "),
        b("This is where the year-to-date double-count would appear.")]]],
      [[[s("5")]], [[s("Repeat for Time-in-Transit, Claims and Accessorial")]]],
    ]},
    { t: "callout", kind: "crit", label: "Why January is the test", body: [
      s("The February extract is a year-to-date file: it contains January as well as February. The "
      + "January extract contains January. A conventional Get Data → Folder append — the obvious "
      + "approach — double-counts January exactly. Measured on the real files that is a 100% "
      + "overstatement of the month, with no error, no warning, and a total that still looks "
      + "entirely plausible."),
    ]},

    { t: "hr" },
    { t: "p", muted: true, runs: [s("Reference: "), c("docs/08_opening_the_powerbi_file.md"),
      s(" in the repository carries the same steps in short form, plus notes on regenerating the "
      + "template.")] },
  ],
};
