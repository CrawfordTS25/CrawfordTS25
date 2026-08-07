"""
Generate a TMDL script that builds the ENTIRE model in one paste.

Three attempts at a hand-authored .pbit were rejected by Power BI Desktop, so
this abandons the binary route completely. TMDL is plain text: there is no
package structure, no version stamp, no byte-order mark, nothing that can be
subtly wrong in a way the product reports only as "corrupted".

One paste produces:

    * the p_Folder parameter
    * 8 tables, each with its columns and its Power Query partition
    * the _Measures table with all 112 measures, formatted and foldered
    * both what-if parameter tables
    * all 11 relationships
    * the two sort-by-column settings that are otherwise easy to forget

That replaces nine Advanced Editor pastes, 112 separate measure creations,
eleven relationship drags and two column settings.

Every syntactic convention here was read out of a TMDL script that Power BI
Desktop itself wrote, not from documentation:

    * tabs, never spaces; CRLF line endings; UTF-16 LE with no BOM
    * model at 1 tab, tables at 2, columns/measures/partitions at 3,
      their properties at 4
    * an expression introduced by a line ending in `=` is indented TWO levels
      below that line - so a measure at 3 tabs has its DAX at 5, and a
      partition's `source =` at 4 tabs has its M at 6
    * blank lines inside an expression block still carry the block's indent,
      otherwise the block terminates early

Usage:
    python powerbi/build_tmdl_full.py --folder "C:\\UPS\\2025"
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PQ = HERE / "powerquery_standalone"

TAB = "\t"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.argv = [str(path)]          # the imported module parses argv only in main()
    spec.loader.exec_module(mod)
    return mod


pbit = _load("build_pbit", HERE / "build_pbit.py")
tmdl = _load("build_tmdl", HERE / "build_tmdl.py")


# ---------------------------------------------------------------------------
# Power Query extraction
# ---------------------------------------------------------------------------

def m_body(text):
    """Strip the comment banner, returning the `let … in …` expression."""
    idx = text.index("\nlet\n")
    return text[idx:].strip()


def load_queries():
    """The nine standalone queries, keyed by the table each one becomes."""
    q = {}

    q["Dim_ServiceMapping"] = m_body(
        (PQ / "01_Parameter_and_ServiceMapping.m").read_text(encoding="utf-8"))
    q["Fact_VolumeSpend"] = m_body(
        (PQ / "02_Fact_VolumeSpend.m").read_text(encoding="utf-8"))
    q["Fact_TimeInTransit"] = m_body(
        (PQ / "03_Fact_TimeInTransit.m").read_text(encoding="utf-8"))

    both = (PQ / "04_Fact_Claims_Accessorial.m").read_text(encoding="utf-8")
    marker = ("// ===========================================================================\n"
              "// 6. QUERY  Fact_Accessorial")
    claims, accessorial = both.split(marker)
    q["Fact_Claims"] = m_body(claims)
    q["Fact_Accessorial"] = m_body(marker + accessorial)

    dims = (PQ / "05_Dimensions.m").read_text(encoding="utf-8")
    m8 = ("// ===========================================================================\n"
          "// 8. QUERY  Dim_Account")
    m9 = ("// ===========================================================================\n"
          "// 9. QUERY  Dim_Service")
    date_part, rest = dims.split(m8)
    account_part, service_part = rest.split(m9)
    q["Dim_Date"] = m_body(date_part)
    q["Dim_Account"] = m_body(m8 + account_part)
    q["Dim_Service"] = m_body(m9 + service_part)

    return q


# ---------------------------------------------------------------------------
# TMDL emission
# ---------------------------------------------------------------------------

def guid(text):
    return str(uuid.uuid5(uuid.NAMESPACE_OID, "ups2025." + text))


def quote(name):
    """TMDL quotes an identifier only when it is not a bare word."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else f"'{name}'"


def emit_expression_block(lines, indent):
    """An expression body, indented `indent` tabs.

    Blank lines are emitted as the indent prefix alone. A genuinely empty line
    ends the block as far as the TMDL parser is concerned, which truncates the
    expression without complaint."""
    out = []
    for line in lines:
        out.append(f"{TAB * indent}{line}" if line.strip() else TAB * indent)
    return out


TMDL_TYPE = {"string": "string", "double": "double", "int64": "int64",
             "dateTime": "dateTime", "boolean": "boolean"}

# build_pbit uses TMSL type names; TMDL spells dateTime the same but the model
# there declares dates as "dateTime".
TYPE_MAP = {"string": "string", "double": "double", "int64": "int64",
            "dateTime": "dateTime", "boolean": "boolean"}


def emit_column(table, name, kind):
    lines = [f"{TAB * 3}column {quote(name)}"]
    lines.append(f"{TAB * 4}dataType: {TYPE_MAP[kind]}")
    if name in pbit.HIDDEN:
        lines.append(f"{TAB * 4}isHidden")
    if kind == "dateTime":
        lines.append(f"{TAB * 4}formatString: yyyy-mm-dd")
    lines.append(f"{TAB * 4}lineageTag: {guid(table + '.' + name)}")
    lines.append(f"{TAB * 4}summarizeBy: "
                 f"{'sum' if name in pbit.SUMMARISE else 'none'}")
    lines.append(f"{TAB * 4}sourceColumn: {name}")
    sort_by = pbit.SORT_BY.get((table, name))
    if sort_by:
        lines.append(f"{TAB * 4}sortByColumn: {sort_by}")
    lines.append("")
    lines.append(f"{TAB * 4}annotation SummarizationSetBy = Automatic")
    lines.append("")
    return lines


def emit_table(name, columns, m_expression, hidden=False):
    lines = [f"{TAB * 2}table {quote(name)}"]
    if hidden:
        lines.append(f"{TAB * 3}isHidden")
    lines.append(f"{TAB * 3}lineageTag: {guid(name)}")
    lines.append("")
    for column, kind in columns:
        lines += emit_column(name, column, kind)
    lines.append(f"{TAB * 3}partition {quote(name)} = m")
    lines.append(f"{TAB * 4}mode: import")
    lines.append(f"{TAB * 4}source =")
    lines += emit_expression_block(m_expression.split("\n"), 6)
    lines.append("")
    lines.append(f"{TAB * 3}annotation PBI_ResultType = Table")
    lines.append("")
    return lines


def emit_calculated_table(name, expression, fmt, kind):
    lines = [f"{TAB * 2}table {quote(name)}"]
    lines.append(f"{TAB * 3}lineageTag: {guid(name)}")
    lines.append("")
    lines.append(f"{TAB * 3}column {quote(name)}")
    lines.append(f"{TAB * 4}dataType: {kind}")
    lines.append(f"{TAB * 4}isHidden")
    lines.append(f"{TAB * 4}lineageTag: {guid(name + '.col')}")
    lines.append(f"{TAB * 4}summarizeBy: none")
    lines.append(f"{TAB * 4}sourceColumn: [Value]")
    lines.append(f"{TAB * 4}formatString: {fmt}")
    lines.append("")
    lines.append(f"{TAB * 4}annotation SummarizationSetBy = Automatic")
    lines.append("")
    lines.append(f"{TAB * 3}partition {quote(name)} = calculated")
    lines.append(f"{TAB * 4}mode: import")
    lines.append(f"{TAB * 4}source = {expression}")
    lines.append("")
    return lines


def emit_measures_table(dax_dir):
    lines = [f"{TAB * 2}table _Measures"]
    lines.append(f"{TAB * 3}lineageTag: {guid('_Measures')}")
    lines.append("")

    total = 0
    for path in sorted(dax_dir.glob("*.dax")):
        folder = tmdl.DISPLAY_FOLDER.get(path.name, "Measures")
        for name, expression, sub in tmdl.parse_dax(path):
            full = folder + ("\\" + sub if sub else "")
            lines += tmdl.emit_measure(name, expression, full, indent=3)
            total += 1

    lines.append(f"{TAB * 3}column _")
    lines.append(f"{TAB * 4}dataType: int64")
    lines.append(f"{TAB * 4}isHidden")
    lines.append(f"{TAB * 4}lineageTag: {guid('_Measures._')}")
    lines.append(f"{TAB * 4}summarizeBy: none")
    lines.append(f"{TAB * 4}sourceColumn: _")
    lines.append("")
    lines.append(f"{TAB * 4}annotation SummarizationSetBy = Automatic")
    lines.append("")
    lines.append(f"{TAB * 3}partition _Measures = m")
    lines.append(f"{TAB * 4}mode: import")
    lines.append(f"{TAB * 4}source =")
    lines += emit_expression_block([
        "let",
        "    Source = #table(type table [_ = Int64.Type], {{0}})",
        "in",
        "    Source",
    ], 6)
    lines.append("")
    return lines, total


def emit_relationships():
    lines = []
    for from_table, from_column, to_table, to_column in pbit.RELATIONSHIPS:
        rid = guid(f"{from_table}.{from_column}->{to_table}.{to_column}")
        lines.append(f"{TAB * 2}relationship {rid}")
        lines.append(f"{TAB * 3}fromColumn: {quote(from_table)}.{quote(from_column)}")
        lines.append(f"{TAB * 3}toColumn: {quote(to_table)}.{quote(to_column)}")
        lines.append("")
    return lines


def build(folder, dax_dir):
    queries = load_queries()
    out = ["createOrReplace", ""]
    out.append(f"{TAB}model Model")
    out.append(f"{TAB * 2}culture: en-US")
    out.append(f"{TAB * 2}defaultPowerBIDataSourceVersion: powerBI_V3")
    out.append(f"{TAB * 2}sourceQueryCulture: en-US")
    out.append(f"{TAB * 2}dataAccessOptions")
    out.append(f"{TAB * 3}legacyRedirects")
    out.append(f"{TAB * 3}returnErrorValuesAsNull")
    out.append("")

    # The parameter the fact partitions read. Declared before them: TMDL is
    # declarative and resolves references either way, but a reader following the
    # script top to bottom should meet p_Folder before its first use.
    out.append(f"{TAB * 2}expression p_Folder = "
               f'"{folder}" meta [IsParameterQuery=true, Type="Text", '
               f"IsParameterQueryRequired=true]")
    out.append(f"{TAB * 3}lineageTag: {guid('p_Folder')}")
    out.append("")
    out.append(f"{TAB * 3}annotation PBI_NavigationStepName = Navigation")
    out.append("")
    out.append(f"{TAB * 3}annotation PBI_ResultType = Text")
    out.append("")

    # Order matters only for readability - TMDL resolves references itself - but
    # keeping dependencies first makes the script readable top to bottom.
    order = ["Dim_ServiceMapping", "Fact_VolumeSpend", "Fact_TimeInTransit",
             "Fact_Claims", "Fact_Accessorial", "Dim_Date", "Dim_Account",
             "Dim_Service"]

    for name in order:
        if name == "Dim_Service":
            columns = pbit.DIM_SERVICE_COLUMNS
        else:
            columns = pbit.TABLES[name]
        out += emit_table(name, columns, queries[name],
                          hidden=(name == "Dim_ServiceMapping"))

    measures, total = emit_measures_table(dax_dir)
    out += measures

    out += emit_calculated_table("Volume Threshold",
                                 "GENERATESERIES(0, 10000, 250)", "#,0", "int64")
    out += emit_calculated_table("Share Threshold",
                                 "GENERATESERIES(0, 0.1, 0.005)", "0.0%", "double")

    out += emit_relationships()

    return "\r\n".join(out), total


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--folder",
        default=r"X:\support_services\External_Provisioning\UPS"
                r"\Reports Provided by UPS\2025\Volume Spend",
        help="Default value for p_Folder - the folder holding the monthly UPS "
             ".xlsx extracts. Queries locate files by month prefix (1-JAN, "
             "2-FEB, ...), so the exact file names do not matter.")
    parser.add_argument("--out", type=pathlib.Path,
                        default=ROOT / "dist" / "UPS_2025_Full_Model.tmdl")
    parser.add_argument("--dax", type=pathlib.Path, default=HERE / "dax")
    args = parser.parse_args()

    script, total = build(args.folder, args.dax)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(script.encode("utf-16-le"))
    txt = args.out.with_suffix(".txt")
    txt.write_text(script, encoding="utf-8")

    lines = script.split("\r\n")
    print(f"Wrote {args.out} ({args.out.stat().st_size:,} bytes, UTF-16 LE, no BOM)")
    print(f"Wrote {txt} ({txt.stat().st_size:,} bytes, UTF-8)")
    print(f"  tables        {len(pbit.TABLES) + 1}  (+ _Measures, + 2 what-if)")
    print(f"  measures      {total}")
    print(f"  relationships {len(pbit.RELATIONSHIPS)}")
    print(f"  lines         {len(lines):,}")
    print(f"  no space indentation: {all(not l.startswith(' ') for l in lines)}")


if __name__ == "__main__":
    main()
