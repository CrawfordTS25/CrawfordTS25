"""
Generate the complete manual-build guide as print-ready HTML (then PDF).

Every line of M and DAX in the output is read from the repository source files
at build time, so the document cannot drift from the code it documents.

    python docs/guide-src/build_manual.py > /tmp/manual.html
"""

from __future__ import annotations

import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PQ = ROOT / "powerbi" / "powerquery_standalone"
DAX = ROOT / "powerbi" / "dax"

esc = lambda t: html.escape(str(t))
out = []
A = out.append


def code(text, lang=""):
    A(f'<pre class="code">{esc(text.rstrip())}</pre>')


def h1(t, page=False):
    cls = " class='newpage'" if page else ""
    A(f"<h1{cls}>{esc(t)}</h1>")


def h2(t):
    A(f"<h2>{esc(t)}</h2>")


def h3(t):
    A(f"<h3>{esc(t)}</h3>")


def p(t, cls=""):
    attr = f" class='{cls}'" if cls else ""
    A(f"<p{attr}>{t}</p>")


def callout(label, body, kind="info"):
    A(f'<div class="callout {kind}"><div class="lbl">{esc(label)}</div>'
      f'<div class="bod">{body}</div></div>')


def table(header, rows, widths=None):
    cols = ""
    if widths:
        total = sum(widths)
        cols = "<colgroup>" + "".join(
            f'<col style="width:{w / total * 100:.2f}%">' for w in widths) + "</colgroup>"
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    A(f"<table>{cols}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")


def steps(items):
    A("<ol class='steps'>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>")


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

MEASURE_START = re.compile(r"^(?!VAR\s|RETURN\b|//)([A-Za-z][A-Za-z0-9 _%/()\-\.]*?)\s*=\s*(.*)$")


def parse_dax(path):
    """Yield (name, expression) exactly as stored in the .dax library."""
    measures, name, buf = [], None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("//"):
            if name:
                buf.append("")
            continue
        m = MEASURE_START.match(line)
        if m and "[" not in m.group(1):
            if name:
                measures.append((name, "\n".join(buf).strip()))
            name = m.group(1).strip()
            buf = [m.group(2)] if m.group(2).strip() else []
        elif name is not None:
            buf.append(line)
    if name:
        measures.append((name, "\n".join(buf).strip()))
    return measures


def m_query(path, banner_marker="==========\n\nlet"):
    """Return (comment_banner, code) for a standalone .m file."""
    text = path.read_text(encoding="utf-8")
    idx = text.index("\nlet\n")
    return text[:idx].strip(), text[idx:].strip()


def split_two_queries(path):
    """04_Fact_Claims_Accessorial.m holds two queries separated by a banner."""
    text = path.read_text(encoding="utf-8")
    marker = "// ===========================================================================\n// 6. QUERY  Fact_Accessorial"
    a, b = text.split(marker)
    return a.strip(), (marker + b).strip()


# ===========================================================================
# COVER
# ===========================================================================
A('<div class="cover">')
A('<div class="eyebrow">UPS 2025 Annual Shipping Performance</div>')
A('<h1 class="title">Building the Dashboard by Hand</h1>')
A('<div class="subtitle">Complete Power Query and DAX, start to finish, '
  'in Power BI Desktop</div>')
A('<div class="facts">')
A("<p><b>What this builds:</b> 8 tables · 11 relationships · 112 measures, "
  "reading your four UPS Excel extracts directly.</p>")
A("<p><b>What you need:</b> Power BI Desktop and your four .xlsx files. "
  "Nothing else — no template, no Python, no CSV files, no downloads.</p>")
A("<p><b>How long:</b> about an hour for the model, plus report layout.</p>")
A("</div></div>")

callout("Everything here is also on GitHub",
        "If you can open a browser, you do not have to retype anything from this "
        "document. The same code is at "
        "<b>github.com/CrawfordTS25/CrawfordTS25</b>, branch "
        "<b>claude/executive-dashboard-build-09ai41</b>, under "
        "<code>ups-2025-executive-dashboard/</code>. Open a file, click <i>Raw</i>, "
        "select all, copy. That is faster and safer than copying out of a PDF.",
        "info")

callout("Why build by hand rather than open the template",
        "The .pbit template does the same job in five minutes, and it is the better "
        "route if you can get the file onto the machine. This document exists for "
        "when you cannot. It is not a lesser path: the model it produces is "
        "identical, and it reads your raw Excel files directly rather than going "
        "through intermediate CSVs, so there is one less moving part.",
        "info")

# ===========================================================================
h1("1. Before you start", page=True)

h2("1.1 Put the four files in one folder")
p("The queries reference these exact names. Rename your extracts and put all four "
  "in a single folder:")
table(["Rename to", "This is your…"],
      [["<code>UPS_2025_01_VolumeSpend.xlsx</code>", "January file"],
       ["<code>UPS_2025_02_VolumeSpend_YTD.xlsx</code>",
        "February file — the year-to-date one"],
       ["<code>UPS_2025_03_AllTabs.xlsx</code>",
        "March file — the one with TnT / Accessorial / Claims / VnS tabs"],
       ["<code>UPS_2025_04_VolumeSpend.xlsx</code>", "April file"]],
      [40, 60])
p("Note the folder path. You will need it in the next step, and it must be "
  "absolute — for example <code>C:\\UPS\\2025</code>, with no trailing backslash.")

h2("1.2 How the pieces fit together")
p("Nine queries, built in order. Each one that references another must come after it.")
table(["#", "Query", "Reads", "Depends on"],
      [["1", "<code>p_Folder</code>", "— (parameter)", "—"],
       ["2", "<code>Dim_ServiceMapping</code>", "nothing — inline table", "—"],
       ["3", "<code>Fact_VolumeSpend</code>", "all four files", "1, 2"],
       ["4", "<code>Fact_TimeInTransit</code>", "March file, TnT tab", "1, 2"],
       ["5", "<code>Fact_Claims</code>", "March file, Claims tab", "1"],
       ["6", "<code>Fact_Accessorial</code>", "March file, Accessorial tab", "1, 2"],
       ["7", "<code>Dim_Date</code>", "nothing — generated", "—"],
       ["8", "<code>Dim_Account</code>", "the fact queries", "3, 4, 5"],
       ["9", "<code>Dim_Service</code>", "the mapping table", "2"]],
      [6, 26, 40, 18])

h2("1.3 The pattern for every query")
steps([
    "In Power BI Desktop: <b>Home &gt; Transform data</b> to open Power Query.",
    "<b>Home &gt; New Source &gt; Blank Query</b>.",
    "Rename it in the Query Settings pane on the right — the name must match "
    "<i>exactly</i>, because later queries reference it.",
    "<b>Home &gt; Advanced Editor</b>.",
    "Delete everything in the box, paste the query, click <b>Done</b>.",
])
p("Paste the whole block including the comment banner — Power Query keeps comments "
  "and they are the record of why each rule exists.", "muted")

callout("If a query shows an error",
        "Do not delete it and move on. Every query here depends on the ones before "
        "it, so one broken query cascades. The error message names the step that "
        "failed; check that step's line against this document. Section 8 lists the "
        "errors you are most likely to hit and what each one means.",
        "warn")

# ===========================================================================
h1("2. Create the parameter", page=True)
p("This is a <b>parameter</b>, not a query. In Power Query: "
  "<b>Home &gt; Manage Parameters &gt; New Parameter</b>.")
table(["Field", "Value"],
      [["Name", "<code>p_Folder</code>"],
       ["Type", "Text"],
       ["Current Value", "the folder holding your four files, e.g. <code>C:\\UPS\\2025</code>"]],
      [25, 75])
callout("No trailing backslash",
        "The queries build paths as <code>p_Folder &amp; \"\\\" &amp; fileName</code>. "
        "A trailing backslash produces a doubled separator and a file-not-found "
        "error naming a path with <code>\\\\</code> in the middle — which at least "
        "tells you exactly what went wrong.",
        "warn")

# ===========================================================================
h1("3. The queries", page=True)
p("Nine blocks. Create each as a Blank Query, name it exactly as shown in its "
  "banner, and paste the code into Advanced Editor.")

QUERIES = [
    ("Query 2 — Dim_ServiceMapping", PQ / "01_Parameter_and_ServiceMapping.m", None),
    ("Query 3 — Fact_VolumeSpend", PQ / "02_Fact_VolumeSpend.m", None),
    ("Query 4 — Fact_TimeInTransit", PQ / "03_Fact_TimeInTransit.m", None),
]

for title, path, _ in QUERIES:
    h2(title)
    code(path.read_text(encoding="utf-8"))

claims_q, acc_q = split_two_queries(PQ / "04_Fact_Claims_Accessorial.m")
h2("Query 5 — Fact_Claims")
code(claims_q)
h2("Query 6 — Fact_Accessorial")
code(acc_q)

dims = (PQ / "05_Dimensions.m").read_text(encoding="utf-8")
marker8 = "// ===========================================================================\n// 8. QUERY  Dim_Account"
marker9 = "// ===========================================================================\n// 9. QUERY  Dim_Service"
q7, rest = dims.split(marker8)
q8, q9 = rest.split(marker9)
h2("Query 7 — Dim_Date")
code(q7.strip())
h2("Query 8 — Dim_Account")
code((marker8 + q8).strip())
h2("Query 9 — Dim_Service")
code((marker9 + q9).strip())

h2("Close and apply")
p("<b>Home &gt; Close &amp; Apply</b>. All nine queries should load without error. "
  "If any fail, fix them before continuing — the model steps assume all nine exist.")

# ===========================================================================
h1("4. Set up the model", page=True)

h2("4.1 Relationships")
p("Model view. Drag from the <b>many</b> side to the <b>one</b> side. Every "
  "relationship is single-direction — <i>Cross filter direction: Single</i>.")
table(["From (many)", "Column", "To (one)", "Column"],
      [["Fact_VolumeSpend", "MonthKey", "Dim_Date", "MonthKey"],
       ["Fact_TimeInTransit", "MonthKey", "Dim_Date", "MonthKey"],
       ["Fact_Claims", "MonthKey", "Dim_Date", "MonthKey"],
       ["Fact_Accessorial", "MonthKey", "Dim_Date", "MonthKey"],
       ["Fact_VolumeSpend", "AccountKey", "Dim_Account", "AccountKey"],
       ["Fact_TimeInTransit", "AccountKey", "Dim_Account", "AccountKey"],
       ["Fact_Claims", "AccountKey", "Dim_Account", "AccountKey"],
       ["Fact_Accessorial", "AccountKey", "Dim_Account", "AccountKey"],
       ["Fact_VolumeSpend", "ServiceGroup", "Dim_Service", "ServiceGroup"],
       ["Fact_TimeInTransit", "ServiceGroup", "Dim_Service", "ServiceGroup"],
       ["Fact_Accessorial", "ServiceGroup", "Dim_Service", "ServiceGroup"]],
      [28, 22, 26, 24])

callout("Do NOT connect Fact_Claims to Dim_Service",
        "There is no key to join on — the claims extract has no product, service or "
        "tracking number. The tempting workaround is a many-to-many through "
        "Dim_Account, or a bi-directional filter. Both produce numbers; neither "
        "produces meaning. Filtering claims by service through the account path "
        "returns <i>claims for accounts that used this service</i> — for an account "
        "using five services, the same claim count five times over — and any reader "
        "will take it as claims caused by that service. "
        "<b>Leave the relationship out so a service slicer visibly does nothing on "
        "the claims page.</b> That absence is the honest signal.",
        "crit")

callout("No bi-directional relationships anywhere",
        "With three fact tables at different grains, bi-directional filtering "
        "creates ambiguous filter paths that change measure results depending on "
        "which visual the user clicked first. Every relationship stays Single.",
        "warn")

h2("4.2 Sort the month columns")
p("Data view, select <code>Dim_Date</code>, then for each of "
  "<code>MonthName</code> and <code>MonthYearLabel</code>:")
steps(["Select the column.",
       "<b>Column tools &gt; Sort by column</b>.",
       "Choose <code>SortOrder</code>."])
callout("This one is not optional",
        "Without it every month axis in the report sorts alphabetically — Apr, Aug, "
        "Dec, Feb, Jan… Trend lines become meaningless, and it is easy to miss "
        "because the chart still looks like a chart. Check a month axis reads Jan, "
        "Feb, Mar before going further. It also silently resets if you retype a "
        "column, so re-check after any model edit.",
        "crit")

h2("4.3 Do NOT mark Dim_Date as a date table")
p("<code>Dim_Date</code> is <b>month grain</b> — twelve rows, one per month — "
  "because every fact in this model is month grain. There is no daily shipment "
  "data to join to.")
p("That makes the standard DAX time-intelligence functions unusable here. "
  "<code>TOTALYTD</code>, <code>SAMEPERIODLASTYEAR</code> and <code>DATEADD</code> "
  "all need a contiguous table of <i>days</i>; handed twelve first-of-month rows "
  "they return blank or silently wrong values rather than raising an error. The "
  "measures in Section 5 use MonthKey arithmetic instead, which is exact at this "
  "grain.")

h2("4.4 What-if parameters")
p("<b>Modeling &gt; New parameter &gt; Numeric range.</b> These drive the "
  "qualification rules, and exposing them lets leadership move the most contestable "
  "assumption in the model during a review and watch the ranking respond.")
table(["Name", "Min", "Max", "Increment", "Default"],
      [["<code>Volume Threshold</code>", "0", "10000", "250", "1000"],
       ["<code>Share Threshold</code>", "0", "0.1", "0.005", "0.01"]],
      [34, 15, 17, 18, 16])

h2("4.5 Hide what should not be sliced")
table(["Hide", "Why"],
      [["<code>Dim_ServiceMapping</code> (whole table)",
        "It is the two-vocabulary bridge, needed by the Data Quality page but never "
        "as a slicer. <b>No measure may filter it</b> — it has no relationship to "
        "any fact, so REMOVEFILTERS on it is a no-op that returns silently wrong "
        "numbers."],
       ["Key columns — <code>MonthKey</code>, <code>AccountKey</code>, "
        "<code>SortOrder</code>, <code>DateKey</code>",
        "Nothing good comes of a user dragging a surrogate key onto a visual."],
       ["Raw numeric fact columns", "Expose measures, not columns, to the report view."]],
      [34, 66])

h2("4.6 Apply the report theme (optional but recommended)")
p("The theme is a JSON file. You cannot download it either, so paste it out of "
  "Appendix A at the back of this document into Notepad and save it as "
  "<code>UPS_Executive_Theme.json</code> — in the Save dialog set "
  "<i>Save as type</i> to <b>All Files</b> so Notepad does not append "
  "<code>.txt</code>.")
p("Then: <b>View &gt; Themes &gt; Browse for themes</b> and pick the file.")
p("It carries a colour palette validated for colour-vision deficiency, hairline "
  "gridlines, data labels off by default, and — deliberately — no dual-axis "
  "configuration. Skip it if you are short of time; nothing else depends on it.",
  "muted")

h2("4.7 Create the measures table")
p("<b>Home &gt; Enter data</b>, one column, one row, name the table "
  "<code>_Measures</code>, load it, then hide its column. Every measure in Section 5 "
  "goes here, which keeps the field list split cleanly between things you slice by "
  "and things you measure.")

# ===========================================================================
h1("5. The measures", page=True)
p("112 measures. Select <code>_Measures</code> in the Fields pane, then for each "
  "one: <b>Home &gt; New measure</b>, paste the whole block including the name and "
  "the <code>=</code>, press Enter.")
p("They are grouped as they are in the source files. Create them in order — later "
  "measures reference earlier ones, and Power BI will show an error until the "
  "dependency exists.", "muted")

callout("Set the display folder as you go",
        "With the measure selected, use the <b>Measure tools</b> ribbon to set "
        "<i>Display folder</i> to the group name shown below. 112 measures in a flat "
        "list is unusable; in five folders it is navigable.",
        "info")

DAX_FILES = [
    ("Group 1 — Volume, Spend and Cost", "01_base_measures.dax"),
    ("Group 2 — Reliability", "02_reliability.dax"),
    ("Group 3 — Claims and Loss Risk", "03_claims_risk.dax"),
    ("Group 4 — Scoring and Recommendation", "04_scoring_recommendation.dax"),
    ("Group 5 — Data Quality and Narrative", "05_data_quality.dax"),
]

total = 0
for title, fname in DAX_FILES:
    measures = parse_dax(DAX / fname)
    total += len(measures)
    h2(f"{title}  ({len(measures)} measures)")
    for name, expr in measures:
        A(f'<div class="meas"><div class="mname">{esc(name)}</div>')
        code(f"{name} =\n{expr}")
        A("</div>")

assert total == 112, f"expected 112 measures, found {total}"

h2("Formatting")
p("With each measure selected, set the format on the <b>Measure tools</b> ribbon:")
table(["Measure type", "Format"],
      [["Counts — shipments, packages, claims", "Whole number, comma separated"],
       ["Currency totals", "Currency, 0 decimals"],
       ["Cost per shipment / per claim", "Currency, 2 decimals"],
       ["Cost per billed lb", "Currency, 3 decimals"],
       ["On-time delivery, Wilson lower bound", "Percentage, 2 decimals"],
       ["Other percentages", "Percentage, 1 decimal"],
       ["Rates per 10k, index, score", "Decimal, 1–2 places"]],
      [50, 50])

h2("4.8 Save")
p("<b>File &gt; Save as</b>, set <i>Save as type</i> to "
  "<b>Power BI files (*.pbix)</b>, and name it. Save again after each of the "
  "next sections — 112 measures is a lot of work to lose.")

# ===========================================================================
h1("6. Build the report", page=True)
p("Eight pages. The full visual-by-visual specification is in "
  "<code>powerbi/report_spec/00_page_layouts.md</code>; this is the working "
  "summary. Canvas 1280 × 720.")
p("Put a card bound to <code>[Data Basis Banner]</code> at the top of "
  "<b>every</b> page. A report that states its own reporting basis on every page "
  "cannot be misquoted from a screenshot.")

PAGES = [
    ("1. Executive Overview",
     "5 KPI cards — Total Shipments, Total Net Spend, On-Time Delivery %, "
     "Loss Claim Rate per 10k, Avg Net Spend per Shipment. Line chart of "
     "On-Time Delivery % by MonthYearLabel. Card with [Recommendation Callout]. "
     "Table: ServiceGroup × Rankable Shipments, On-Time Delivery %, "
     "OTD Wilson Lower Bound, both cost views, Service Consistency Score, "
     "Qualification Status. Donut of volume mix."),
    ("2. Service Performance",
     "Bar of On-Time Delivery % by service. Stacked column of Late by Day vs "
     "Late by Time by month — the severity split. Table with Qualification Status, "
     "OTD Confidence Label, OTD Volatility, Worst OTD Month."),
    ("3. Cost and Volume",
     "Volume by month and net spend by month as two separate charts — never a "
     "dual axis. Paired bars: cost per shipment beside cost per billed pound. "
     "Cost bridge table with Avg Billed Weight per Shipment."),
    ("4. Claims and Exceptions",
     "Pinned notice with [Claims Attribution Warning]. KPI row. Claims by "
     "category. Account concentration table sorted by Loss Rate Index vs Firm, "
     "with data bars. No service breakdown — that is deliberate."),
    ("5. Account and Location",
     "Account scorecard. Volume by region. On-time by state. A table of accounts "
     "that have volume but no transit coverage — they are invisible in every "
     "reliability figure and need naming, not averaging away."),
    ("6. Annual Recommendation",
     "Recommendation matrix. [Score Basis] card. The two threshold sliders. "
     "Score components. Remove the Month and Account slicers from this page — an "
     "annual policy sliced to one account in one month is not an annual policy."),
    ("7. Accessorial and Cost Drivers",
     "Net spend by charge category. Monthly trend. Address Correction is the "
     "line to call out: every unit is a package sent to a bad address you "
     "supplied, charged per package, fully avoidable."),
    ("8. Data Quality",
     "Coverage by month and source. Exclusion counts. Service mapping inventory "
     "(both vocabularies). Known limitations."),
]
table(["Page", "Contents"], [[f"<b>{esc(n)}</b>", esc(d)] for n, d in PAGES], [24, 76])

h2("Two visual rules worth stating")
callout("Show both cost views side by side, always",
        "Cost per shipment on its own is the single most misleading number in this "
        "data. Ground averages about 16 lb per piece against about 2 lb for 2nd Day "
        "Air, so per shipment they look almost identically priced — a package-mix "
        "artefact, not a rate. Per billed pound Ground is roughly seven times "
        "cheaper. A reader who sees only the per-shipment view will conclude that "
        "upgrading Ground volume to air is nearly free. Annotate the visual with "
        "that sentence; do not rely on the reader inferring it.",
        "crit")
callout("Set KPI cards to no interaction",
        "<b>Format &gt; Edit interactions</b>, set each card to None. The default is "
        "Highlight, and a user who clicks a card and sees the page change will "
        "assume the click meant something.",
        "info")

# ===========================================================================
h1("7. Verify before you publish", page=True)
p("Seven checks. Each catches a specific failure mode, and each takes seconds. "
  "The first four matter most — they catch errors that produce numbers which are "
  "internally consistent and completely wrong.")

table(["#", "Check", "What it catches"],
      [["1", "January volume equals your January extract — <b>not double it</b>",
        "The year-to-date overlap. The February file contains January too. Getting "
        "exactly double is the signature."],
       ["2", "On-time delivery = <b>96.46%</b> for March",
        "Compare against the Grand Total row of the TnT sheet. A reading near 98.2% "
        "means a percentage is being averaged rather than weighted."],
       ["3", "Page 8 Reconciliation Status = <b>Reconciled</b>",
        "Accessorial detail must sum to net spend to the cent — $1,053,748.13 for "
        "March. A variance means a source file is stale or partly loaded."],
       ["4", "Service Volume Mix % sums to 100% across services",
        "If it reads 100% on every row, a measure is filtering a table with no "
        "relationship to the facts and the REMOVEFILTERS is a no-op."],
       ["5", "A month axis reads Jan → Dec",
        "The sort-by columns in step 4.2 were not applied."],
       ["6", "[YTD Shipments] and [OTD % PM] return values, not blanks",
        "Time-intelligence functions used against the month-grain date table."],
       ["7", "The banner reads PROVISIONAL",
        "With one month of transit and claims data it must not say ANNUAL."]],
      [5, 33, 62])

h2("Reference figures from your data")
p("Jan–Apr volume and spend; March transit, claims and accessorial:")
table(["Figure", "Value"],
      [["Total shipments", "293,921"],
       ["Total net spend", "$4,519,934"],
       ["January volume", "79,359"],
       ["March net spend", "$1,053,748.13"],
       ["March on-time delivery", "96.46% across 67,091 measured packages"],
       ["March loss claims", "35, a rate of 5.1 per 10,000"],
       ["Ground cost per billed lb", "$0.89 (vs $6.48 for 2nd Day Air)"]],
      [45, 55])

# ===========================================================================
h1("8. Troubleshooting", page=True)
table(["Error or symptom", "Cause", "Fix"],
      [["<code>We couldn't find the file</code>",
        "Wrong <code>p_Folder</code>, trailing backslash, or a file not renamed",
        "Check the path in the error text — it shows exactly what was built"],
       ["<code>The column 'Column22' of the table wasn't found</code>",
        "The sheet has fewer columns than expected — usually the wrong file in the "
        "wrong name, e.g. a VnS file named as the January file",
        "Confirm each renamed file is the layout the query expects"],
       ["<code>The key didn't match any rows in the table</code>",
        "A sheet name differs — the March file's tabs must be TnT, Claims, "
        "Accessorial, VnS",
        "Open the file and check the tab names"],
       ["<code>Expression.Error: The name 'Dim_ServiceMapping' wasn't recognized</code>",
        "Queries created out of order, or a name typo",
        "Names must match exactly; create query 2 before 3, 4 and 6"],
       ["A measure shows a red squiggle",
        "It references a measure you have not created yet",
        "Create the measures in the order given in Section 5"],
       ["January volume is exactly double",
        "The February file was not filtered to month 2",
        "Check the <code>Feb</code> step passes <code>2</code> to ReadSchemaA"],
       ["Month axis alphabetical",
        "Sort-by columns not set",
        "Section 4.2"],
       ["All visuals blank",
        "Close &amp; Apply not run, or relationships missing",
        "Check the Model view shows 11 relationships"]],
      [30, 36, 34])

h2("If the M does not work at all")
p("These queries were written against your actual extracts and every column and "
  "row offset was verified by an independent implementation that reconciles to "
  "them exactly. But they have never been executed inside Power BI Desktop — there "
  "is no copy of Desktop in the environment they were written in. Treat the first "
  "run as a test.")
p("If a query fails in a way this section does not cover, the fallback is to load "
  "each sheet manually — <b>Get Data &gt; Excel</b>, pick the sheet, remove the top "
  "rows (7 for the January and February layout, 5 for all others), and rename "
  "columns to match the names used here. Slower, but the measures and the model "
  "structure are unaffected.")

callout("The one thing not to skip",
        "Whatever route you take, verify check 1. The February file being "
        "year-to-date is the single trap in this data set that produces a plausible, "
        "confident, wrong answer — a 100% overstatement of January with no error "
        "message anywhere.",
        "crit")

# ===========================================================================
h1("Appendix A — Report theme JSON", page=True)
p("Paste into Notepad, save as <code>UPS_Executive_Theme.json</code> with "
  "<i>Save as type</i> set to <b>All Files</b>, then "
  "<b>View &gt; Themes &gt; Browse for themes</b>.")
p("The categorical colours are assigned in a fixed order and never cycled. The "
  "order matters: it was chosen so that adjacent series stay distinguishable "
  "under the common forms of colour-vision deficiency. Do not reorder them.",
  "muted")
code((ROOT / "powerbi" / "theme" / "UPS_Executive_Theme.json").read_text(encoding="utf-8"))

h1("Appendix B — What this build adds to the original guide", page=True)
p("Seven things the source build guide does not cover, each found while building "
  "against your actual extracts. They are the reason this model gives different "
  "answers from a literal reading of the guide.")
table(["#", "Finding"],
      [["1", "<b>The year-to-date double-count.</b> The February file contains "
             "January too. A folder append overstates January by 100% with no error."],
       ["2", "<b>Two source vocabularies.</b> Volume &amp; Net Spend and "
             "Time-in-Transit name the same services differently, and neither list "
             "contains the other. Without the bridge, cost and reliability can never "
             "meet on one row."],
       ["3", "<b>The scoring arithmetic.</b> The guide gives four weights across "
             "four different units with mixed direction. Added: min-max "
             "normalisation across the qualified set, and weight reallocation when a "
             "component cannot be measured."],
       ["4", "<b>Cost must be weight-normalised.</b> Ground averages 16.1 lb per "
             "piece against 2.3 lb for 2nd Day Air. Per shipment they differ by 36 "
             "cents; per billed pound Ground is 7.3&times; cheaper."],
       ["5", "<b>Claims carry no service key</b>, so 50% of the scoring weight "
             "cannot be allocated at service grain. The model leaves the join "
             "absent rather than approximating it."],
       ["6", "<b>Statistical confidence, not just a volume floor.</b> Ranking uses "
             "the Wilson lower bound, so thin samples fall in proportion to how "
             "little is known. Next Day Air Early: 4 packages measured, 100% "
             "on-time, confidence floor 51%."],
       ["7", "<b>Accessorial detail</b> is the only source that explains why cost "
             "per piece moves, and it surfaces roughly $123k a year of avoidable "
             "Address Correction charges."]],
      [5, 95])

# ---------------------------------------------------------------------------
CSS = """
@page { size: Letter; margin: 0.85in 0.8in 0.7in 0.8in; }
* { box-sizing: border-box; }
body { margin:0; color:#1a1a1a; background:#fff;
  font:400 10pt/1.45 Calibri,Carlito,"Segoe UI",system-ui,sans-serif;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }
p { margin:0 0 6pt; }
p.muted { color:#5f5e5a; font-size:9.5pt; }
h1 { font-size:16pt; font-weight:700; margin:16pt 0 8pt; page-break-after:avoid;
     border-bottom:1pt solid #1f5fa9; padding-bottom:3pt; }
h1.newpage { page-break-before:always; }
h2 { font-size:12pt; font-weight:700; margin:13pt 0 5pt; page-break-after:avoid; }
h3 { font-size:10.5pt; font-weight:700; color:#5f5e5a; margin:9pt 0 4pt;
     page-break-after:avoid; }
code { font-family:Consolas,"DejaVu Sans Mono",monospace; font-size:9pt; color:#1a3a5a; }
pre.code { font-family:Consolas,"DejaVu Sans Mono",monospace; font-size:7.5pt;
  line-height:1.32; color:#20303a; background:#f4f4f1; border-left:2pt solid #c9c8c0;
  padding:5pt 7pt; margin:4pt 0 8pt; white-space:pre; overflow:visible; }
table { border-collapse:collapse; width:100%; margin:3pt 0 9pt; }
th,td { text-align:left; vertical-align:top; padding:3.5pt 5pt; font-size:9pt;
  border-top:0.5pt solid #d8d7d0; border-bottom:0.5pt solid #d8d7d0; }
th { background:#e9ecf1; color:#4a4945; font-weight:700; }
tr { page-break-inside:avoid; }
thead { display:table-header-group; }
ol.steps { margin:0 0 8pt; padding-left:16pt; }
ol.steps li { margin-bottom:3pt; font-size:9.5pt; }
.callout { background:#f3f5f8; padding:6pt 9pt; margin:7pt 0 9pt;
  page-break-inside:avoid; }
.callout .lbl { font-weight:700; font-size:9.5pt; margin-bottom:2pt; }
.callout .bod { font-size:9.5pt; }
.callout.info { border-left:2.5pt solid #1f5fa9; } .callout.info .lbl { color:#1f5fa9; }
.callout.warn { border-left:2.5pt solid #8a5a00; } .callout.warn .lbl { color:#8a5a00; }
.callout.crit { border-left:2.5pt solid #a32020; } .callout.crit .lbl { color:#a32020; }
.meas { page-break-inside:avoid; margin-bottom:2pt; }
.mname { font-size:9pt; font-weight:700; color:#1f5fa9;
  font-family:Consolas,"DejaVu Sans Mono",monospace; margin-top:5pt; }
.cover { padding-top:0.7in; margin-bottom:14pt; }
.cover .eyebrow { font-size:10.5pt; color:#5f5e5a; }
.cover .title { font-size:24pt; font-weight:700; margin:3pt 0 4pt; border:0; padding:0; }
.cover .subtitle { font-size:13pt; color:#1f5fa9; margin-bottom:11pt; }
.cover .facts { border-top:0.5pt solid #d8d7d0; padding-top:8pt; }
.cover .facts p { font-size:9.5pt; color:#3a3a37; }
"""

print(f"""<!doctype html><html><head><meta charset="utf-8">
<title>Building the UPS 2025 Dashboard by Hand</title>
<style>{CSS}</style></head><body>{''.join(out)}</body></html>""")
