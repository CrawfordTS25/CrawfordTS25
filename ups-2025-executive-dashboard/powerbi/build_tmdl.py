"""
Generate a TMDL script that creates all 112 measures in one paste.

Power BI Desktop's TMDL view (Model view > TMDL, in recent releases) accepts a
script and applies it to the model. That turns the most tedious part of a manual
build - creating 112 measures one at a time - into a single operation.

Syntax and conventions here were taken from a TMDL script written by Power BI
Desktop itself, so the indentation, line endings and encoding match what the
product produces:

    * tabs for indentation, never spaces
    * CRLF line endings
    * UTF-16 LE, no byte-order mark
    * a measure's expression sits TWO levels deeper than the measure line;
      its properties sit ONE level deeper
    * multi-line expressions open with a bare indented line

The script only declares the `_Measures` table. `createOrReplace` replaces the
objects it names, so scoping it to one table means it cannot disturb the fact
tables, their partitions, or any relationships already built.

Usage:
    python powerbi/build_tmdl.py --out dist/UPS_2025_Measures.tmdl
"""

from __future__ import annotations

import argparse
import pathlib
import re
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

MEASURE_START = re.compile(r"^(?!VAR\s|RETURN\b|//)([A-Za-z][A-Za-z0-9 _%/()\-\.]*?)\s*=\s*(.*)$")
FOLDER_HEADER = re.compile(r"^// --- (.+?) -*$")

DISPLAY_FOLDER = {
    "01_base_measures.dax": "1 Volume, Spend and Cost",
    "02_reliability.dax": "2 Reliability",
    "03_claims_risk.dax": "3 Claims and Loss Risk",
    "04_scoring_recommendation.dax": "4 Scoring and Recommendation",
    "05_data_quality.dax": "5 Data Quality and Narrative",
}

# TMDL format strings. Text measures get none - a format string on a measure
# returning a sentence makes Desktop offer an aggregation on it.
FMT = {
    "int": "#,0",
    "money0": "\\$#,0",
    "money2": "\\$#,0.00",
    "money3": "\\$#,0.000",
    "pct1": "0.0%;-0.0%;0.0%",
    "pct2": "0.00%;-0.00%;0.00%",
    "dec1": "#,0.0",
    "dec2": "#,0.00",
    "pct0": "0%;-0%;0%",
}

MEASURE_FORMAT = {
    "Total Shipments": "int", "Rankable Shipments": "int", "YTD Shipments": "int",
    "Shipments PY": "int", "Shipments LY (Source)": "int", "Packages Measured": "int",
    "Total Late": "int", "Late by Day": "int", "Late by Time": "int",
    "On-Time Packages": "int", "Issued Claims Pkgs": "int", "Paid Claims Pkgs": "int",
    "Registered Claims Pkgs": "int", "Loss Claims": "int", "Damage Claims": "int",
    "Total Billed Weight": "int", "Qualified Service Count": "int",
    "Months Loaded": "int", "Completed Months Loaded": "int", "Missing Months": "int",
    "Volume Months Covered": "int", "Transit Months Covered": "int",
    "Claims Months Covered": "int", "Months with Transit Data": "int",
    "Spend-Only Adjustment Rows": "int", "Unmapped Product Rows": "int",
    "Masked Sub-Parent Volume": "int", "Service Rank": "int",
    "Minimum Shipment Threshold": "int", "Minimum Measured Packages": "int",
    "Annual Qualification Flag": "int", "Claims Service Key Available": "int",

    "Total Net Spend": "money0", "Total Gross Spend": "money0",
    "Total Incentive": "money0", "YTD Net Spend": "money0", "Net Spend PY": "money0",
    "Paid Claims Amount": "money0", "Claims Declared Value": "money0",
    "Loss Claims Paid Amount": "money0", "Excluded Adjustment Spend": "money0",
    "Spend-Only Adjustment Value": "money0", "Accessorial Net Spend": "money0",
    "Spend Reconciliation Variance": "money2", "Avg Net Spend per Shipment": "money2",
    "Avg Paid per Claim": "money2", "Claims Cost per 1k Shipments": "money2",
    "Avg Net Spend per Billed Lb": "money3",

    "Shipments YoY %": "pct1", "Net Spend YoY %": "pct1", "Incentive %": "pct1",
    "Service Volume Mix %": "pct1", "Service Spend Mix %": "pct1",
    "Account Volume Mix %": "pct1", "Late Delivery %": "pct1", "Late by Day %": "pct1",
    "Late by Time %": "pct1", "Severity Mix (Day Share of Late)": "pct1",
    "Claims Recovery Rate": "pct1", "Transit Coverage %": "pct1",
    "Annual Completeness %": "pct1", "Excluded Adjustment Spend %": "pct1",
    "Unattributed Spend %": "pct1", "Measured vs Billed Coverage %": "pct1",
    "Service Volume Share": "pct1", "Minimum Volume Share": "pct1",
    "Weight-Adjusted Cost Premium": "pct1", "Top Account Share of Loss Claims": "pct1",
    "On-Time Delivery %": "pct2", "OTD % PM": "pct2", "OTD % Delta MoM": "pct2",
    "OTD % Annual Benchmark": "pct2", "OTD Wilson Lower Bound": "pct2",
    "Loss Claim Rate": "pct2", "Exception / Claims Rate": "pct2",

    "Loss Claim Rate per 10k": "dec2", "Claims Rate per 10k": "dec2",
    "Firm-wide Loss Rate per 10k": "dec2",
    "Loss Claim Rate per 10k (Allocated Proxy)": "dec2",
    "Loss Claims (Allocated Proxy)": "dec1", "Loss Rate Index vs Firm": "dec2",
    "Avg Billed Weight per Shipment": "dec1", "OTD Volatility (pp)": "dec2",
    "OTD Confidence Gap (pp)": "dec2", "Service Consistency Score": "dec1",
    "Effective Weight Total": "dec2", "Score - Reliability": "dec2",
    "Score - Loss Risk": "dec2", "Score - Exception Risk": "dec2",
    "Score - Cost": "dec2",
    "Weight - Reliability": "pct0", "Weight - Loss Risk": "pct0",
    "Weight - Exception Risk": "pct0", "Weight - Cost": "pct0",
}

TEXT_MEASURES = {
    "Has Transit Data", "OTD Confidence Label", "Worst OTD Month", "Loss Risk Flag",
    "Top Account by Loss Claims", "Claims Attribution Warning", "Qualification Status",
    "Recommendation Category", "Recommendation Callout", "Score Basis",
    "Missing Months List", "Coverage Summary", "Reconciliation Status",
    "Data Basis Banner", "Data Basis Banner Colour", "Title - Executive Overview",
    "Title - Service Scorecard", "Title - Claims",
}


def parse_dax(path):
    measures, name, buf, sub = [], None, [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("//"):
            header = FOLDER_HEADER.match(line)
            if header:
                sub = header.group(1).strip()
            if name:
                buf.append("")
            continue
        m = MEASURE_START.match(line)
        if m and "[" not in m.group(1):
            if name:
                measures.append((name, "\n".join(buf).strip(), sub))
            name = m.group(1).strip()
            buf = [m.group(2)] if m.group(2).strip() else []
        elif name is not None:
            buf.append(line)
    if name:
        measures.append((name, "\n".join(buf).strip(), sub))
    return measures


def stable_guid(text):
    """Deterministic lineage tags, so regenerating the script does not churn
    every measure's identity."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, "ups2025." + text))


def emit_measure(name, expression, folder, indent=2):
    """One measure block in Power BI's own TMDL layout.

    A measure at indent N puts its expression at N+2 and its properties at N+1 -
    the convention Desktop writes and the one its parser expects."""
    tab = "\t"
    lines = []
    body = expression.split("\n")

    if len(body) == 1 and len(body[0]) <= 70:
        lines.append(f"{tab * indent}measure '{name}' = {body[0]}")
    else:
        lines.append(f"{tab * indent}measure '{name}' =")
        lines.append(tab * (indent + 2))
        for row in body:
            lines.append(f"{tab * (indent + 2)}{row}" if row.strip()
                         else tab * (indent + 2))

    token = MEASURE_FORMAT.get(name)
    if token and name not in TEXT_MEASURES:
        lines.append(f"{tab * (indent + 1)}formatString: {FMT[token]}")
    lines.append(f"{tab * (indent + 1)}displayFolder: {folder}")
    lines.append(f"{tab * (indent + 1)}lineageTag: {stable_guid(name)}")
    lines.append("")
    return lines


def build(dax_dir):
    tab = "\t"
    out = ["createOrReplace", ""]
    out.append(f"{tab}table _Measures")
    out.append(f"{tab * 2}lineageTag: {stable_guid('_Measures')}")
    out.append("")

    total = 0
    for path in sorted(dax_dir.glob("*.dax")):
        folder = DISPLAY_FOLDER.get(path.name, "Measures")
        for name, expression, sub in parse_dax(path):
            if not expression:
                raise ValueError(f"empty expression for [{name}] in {path.name}")
            full_folder = folder + ("\\" + sub if sub else "")
            out += emit_measure(name, expression, full_folder)
            total += 1

    # A measure table still needs a column and a partition to be a valid table.
    # One hidden constant column keeps it out of the field list.
    out.append(f"{tab * 2}column _")
    out.append(f"{tab * 3}dataType: int64")
    out.append(f"{tab * 3}isHidden")
    out.append(f"{tab * 3}lineageTag: {stable_guid('_Measures._')}")
    out.append(f"{tab * 3}summarizeBy: none")
    out.append(f"{tab * 3}sourceColumn: _")
    out.append("")
    out.append(f"{tab * 3}annotation SummarizationSetBy = Automatic")
    out.append("")
    out.append(f"{tab * 2}partition _Measures = m")
    out.append(f"{tab * 3}mode: import")
    out.append(f"{tab * 3}source =")
    out.append(f"{tab * 5}let")
    out.append(f"{tab * 5}    Source = #table(type table [_ = Int64.Type], {{{{0}}}})")
    out.append(f"{tab * 5}in")
    out.append(f"{tab * 5}    Source")
    out.append("")
    out.append(f"{tab * 2}annotation PBI_Id = {stable_guid('_Measures.id').replace('-', '')}")
    out.append("")
    return "\r\n".join(out), total


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=ROOT / "dist" / "UPS_2025_Measures.tmdl")
    parser.add_argument("--dax", type=pathlib.Path, default=HERE / "dax")
    parser.add_argument("--encoding", default="utf-16-le",
                        choices=["utf-16-le", "utf-8"],
                        help="Desktop writes UTF-16 LE without a BOM; UTF-8 is "
                             "offered so the script can also be pasted from a "
                             "plain text editor.")
    args = parser.parse_args()

    script, total = build(args.dax)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(script.encode(args.encoding))

    # A UTF-8 twin, for pasting straight into the TMDL view from any editor.
    txt = args.out.with_suffix(".txt")
    txt.write_text(script, encoding="utf-8")

    print(f"Wrote {args.out} ({args.out.stat().st_size:,} bytes, {args.encoding})")
    print(f"Wrote {txt} ({txt.stat().st_size:,} bytes, utf-8)")
    print(f"  measures: {total}")
    print(f"  tabs only, no spaces for indentation: "
          f"{all(not l.startswith(' ') for l in script.split(chr(13) + chr(10)))}")


if __name__ == "__main__":
    main()
