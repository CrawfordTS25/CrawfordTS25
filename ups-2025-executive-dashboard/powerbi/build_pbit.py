"""
Generate a Power BI Template (.pbit) for the UPS 2025 executive dashboard.

Why a .pbit and not a .pbix
---------------------------
A .pbix contains a `DataModel` part: the Analysis Services tabular model
serialised in a proprietary, compressed (XPress9) format that only Power BI
Desktop and the AS engine can write. It cannot be authored by any external tool.

A .pbit is the same package with the *data* removed and the model expressed as
plain TMSL JSON in `DataModelSchema`. That is fully authorable. Opening the
.pbit in Power BI Desktop prompts for the parameters, loads the data, and
produces a live model - then File > Save As gives the .pbix.

So the honest deliverable is a template that becomes a .pbix on first open.

What the model loads
--------------------
The star-schema CSVs written by `etl/ups_etl.py`, not the raw Excel extracts.

That is a deliberate trade. The Power Query implementation in
`powerbi/powerquery/` reads the raw folder directly and encodes every parsing
and dedupe rule in M - but it is several hundred lines of M that has never been
executed, and a template that fails on load is worse than useless. The Python
ETL *has* been run against the real files and reconciles to them. Loading its
output means the template works on first open; the M queries remain in the repo
as the documented upgrade path once they can be tested in Desktop.

Usage:
    python powerbi/build_pbit.py --out dist/UPS_2025_Executive_Dashboard.pbit
    python powerbi/build_pbit.py --data-folder "C:\\UPS\\processed" --out dist/x.pbit
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import uuid
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# Power BI writes Version, Settings, Metadata, DiagramLayout, DataModelSchema and
# Report/Layout as UTF-16 LE with NO byte-order mark. Everything else in the
# package (content types, rels, docProps, resource JSON) is plain UTF-8.
#
# These values were read out of a .pbix written by the target Desktop build
# rather than guessed. The first release of this generator wrote a BOM on the
# UTF-16 parts, used Version "1.28" and Metadata version 3, and Desktop reported
# the file as corrupt.
UTF16 = "utf-16-le"

PBI_VERSION = "1.33"        # Desktop 2026.06 writes this
METADATA_VERSION = 5
COMPAT_LEVEL = 1550


# ---------------------------------------------------------------------------
# DAX measure library
# ---------------------------------------------------------------------------

MEASURE_START = re.compile(r"^(?!VAR\s|RETURN\b|//)([A-Za-z][A-Za-z0-9 _%/()\-\.]*?)\s*=\s*(.*)$")
FOLDER_HEADER = re.compile(r"^// --- (.+?) -*$")

# Measure name -> (format string, home table). Anything unlisted gets a general
# format and lands on the _Measures table.
FORMATS = {
    "%": "0.0%",
    "$": r"\$#,0",
    "$$": r"\$#,0.00",
    "int": "#,0",
    "dec": "#,0.0",
    "dec2": "#,0.00",
}

MEASURE_FORMAT = {
    # counts
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
    # currency
    "Total Net Spend": "$", "Total Gross Spend": "$", "Total Incentive": "$",
    "YTD Net Spend": "$", "Net Spend PY": "$", "Paid Claims Amount": "$",
    "Claims Declared Value": "$", "Loss Claims Paid Amount": "$",
    "Excluded Adjustment Spend": "$", "Spend-Only Adjustment Value": "$",
    "Accessorial Net Spend": "$", "Spend Reconciliation Variance": "$$",
    "Avg Net Spend per Shipment": "$$", "Avg Paid per Claim": "$$",
    "Claims Cost per 1k Shipments": "$$",
    "Avg Net Spend per Billed Lb": r"\$#,0.000",
    # percentages
    "Shipments YoY %": "%", "Net Spend YoY %": "%", "Incentive %": "%",
    "Service Volume Mix %": "%", "Service Spend Mix %": "%", "Account Volume Mix %": "%",
    "On-Time Delivery %": "0.00%", "Late Delivery %": "%", "Late by Day %": "%",
    "Late by Time %": "%", "Severity Mix (Day Share of Late)": "%",
    "OTD % PM": "0.00%", "OTD % Delta MoM": "0.00%", "OTD % Annual Benchmark": "0.00%",
    "OTD Wilson Lower Bound": "0.00%", "Claims Recovery Rate": "%",
    "Loss Claim Rate": "0.00%", "Exception / Claims Rate": "0.00%",
    "Transit Coverage %": "%", "Annual Completeness %": "%",
    "Excluded Adjustment Spend %": "%", "Unattributed Spend %": "%",
    "Measured vs Billed Coverage %": "%", "Service Volume Share": "%",
    "Minimum Volume Share": "0.0%", "Weight-Adjusted Cost Premium": "%",
    # decimals
    "Loss Claim Rate per 10k": "dec2", "Claims Rate per 10k": "dec2",
    "Firm-wide Loss Rate per 10k": "dec2",
    "Loss Claim Rate per 10k (Allocated Proxy)": "dec2",
    "Loss Claims (Allocated Proxy)": "dec", "Loss Rate Index vs Firm": "dec2",
    "Top Account Share of Loss Claims": "%",
    "Avg Billed Weight per Shipment": "dec", "OTD Volatility (pp)": "dec2",
    "OTD Confidence Gap (pp)": "dec2", "Service Consistency Score": "dec",
    "Effective Weight Total": "dec2", "Score - Reliability": "dec2",
    "Score - Loss Risk": "dec2", "Score - Exception Risk": "dec2", "Score - Cost": "dec2",
    "Weight - Reliability": "0%", "Weight - Loss Risk": "0%",
    "Weight - Exception Risk": "0%", "Weight - Cost": "0%",
}

DISPLAY_FOLDER = {
    "01_base_measures.dax": "1 Volume, Spend and Cost",
    "02_reliability.dax": "2 Reliability",
    "03_claims_risk.dax": "3 Claims and Loss Risk",
    "04_scoring_recommendation.dax": "4 Scoring and Recommendation",
    "05_data_quality.dax": "5 Data Quality and Narrative",
}


def parse_dax(path: pathlib.Path):
    """Extract (name, expression, subfolder) from a .dax library file.

    The measure name always sits at column 0; VAR / RETURN lines are excluded
    explicitly because they also contain '=' at column 0 in this formatting
    style."""
    measures, name, buf, sub = [], None, [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("//"):
            header = FOLDER_HEADER.match(line)
            if header:
                sub = header.group(1).strip()
            if name:
                buf.append("")
            continue
        match = MEASURE_START.match(line)
        if match and "[" not in match.group(1):
            if name:
                measures.append((name, "\n".join(buf).strip(), sub))
            name = match.group(1).strip()
            buf = [match.group(2)] if match.group(2).strip() else []
        elif name is not None:
            buf.append(line)
    if name:
        measures.append((name, "\n".join(buf).strip(), sub))
    return measures


def load_measures():
    out = []
    for path in sorted((HERE / "dax").glob("*.dax")):
        folder = DISPLAY_FOLDER.get(path.name, "Measures")
        for name, expression, sub in parse_dax(path):
            if not expression:
                raise ValueError(f"Empty expression for measure '{name}' in {path.name}")
            token = MEASURE_FORMAT.get(name)
            fmt = FORMATS.get(token, token) if token else None
            out.append({
                "name": name,
                "expression": expression.split("\n"),
                "displayFolder": folder + ("\\" + sub if sub else ""),
                "formatString": fmt,
                # Text measures must not be summarised or Desktop offers an
                # aggregation on a sentence.
                "isText": name in TEXT_MEASURES,
            })
    return out


TEXT_MEASURES = {
    "Has Transit Data", "OTD Confidence Label", "Worst OTD Month", "Loss Risk Flag",
    "Top Account by Loss Claims", "Claims Attribution Warning", "Qualification Status",
    "Recommendation Category", "Recommendation Callout", "Score Basis",
    "Missing Months List", "Coverage Summary", "Reconciliation Status",
    "Data Basis Banner", "Data Basis Banner Colour", "Title - Executive Overview",
    "Title - Service Scorecard", "Title - Claims",
}


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

T, N, I, D, B = "string", "double", "int64", "dateTime", "boolean"

TABLES = {
    "Fact_VolumeSpend": [
        ("Year", I), ("MonthNumber", I), ("MonthName", T), ("MonthKey", I),
        ("Quarter", T), ("DateKey", D), ("AccountKey", T), ("SubNumber", T),
        ("SubName", T), ("IsMaskedSubParent", T), ("AccountNumber", T),
        ("AccountName", T), ("City", T), ("State", T), ("ZIP", T),
        ("RawProduct", T), ("ServiceGroup", T), ("ServiceGroupShort", T),
        ("ServiceTier", T), ("Scope", T), ("IncludeInRanking", T),
        ("Volume", N), ("GrossSpend", N), ("NetSpend", N), ("Incentive", N),
        ("BilledWeightLbs", N), ("VolumeLY", N), ("NetSpendLY", N),
        ("IsNonServiceRow", T), ("HasVolume", T), ("IsSpendOnlyAdjustment", T),
        ("IsNegativeSpend", T), ("SourceFile", T), ("SourceLayout", T), ("ViewType", T),
    ],
    "Fact_TimeInTransit": [
        ("Year", I), ("MonthNumber", I), ("MonthName", T), ("MonthKey", I),
        ("Quarter", T), ("DateKey", D), ("AccountKey", T), ("SubNumber", T),
        ("SubName", T), ("IsMaskedSubParent", T), ("AccountNumber", T),
        ("AccountName", T), ("City", T), ("State", T), ("ZIP", T),
        ("RawProduct", T), ("ServiceGroup", T), ("ServiceGroupShort", T),
        ("ServiceTier", T), ("Scope", T), ("IncludeInRanking", T),
        ("PackagesMeasured", N), ("LateByTime", N), ("LateByDay", N),
        ("TotalLate", N), ("OnTimePackages", N), ("SourceFile", T), ("ViewType", T),
    ],
    "Fact_Claims": [
        ("Year", I), ("MonthNumber", I), ("MonthName", T), ("MonthKey", I),
        ("Quarter", T), ("DateKey", D), ("AccountKey", T), ("SubNumber", T),
        ("SubName", T), ("IsMaskedSubParent", T), ("AccountNumber", T),
        ("AccountName", T), ("ClaimsCategory", T), ("IsLoss", T),
        ("IssuedClaimsQty", N), ("IssuedClaimsPkgQty", N), ("PaidClaimsQty", N),
        ("PaidClaimsPkgQty", N), ("RegisteredClaimsQty", N),
        ("RegisteredClaimsPkgQty", N), ("PaidClaimsAmount", N),
        ("ClaimsDeclaredValue", N), ("ServiceAttribution", T), ("SourceFile", T),
    ],
    "Fact_Accessorial": [
        ("Year", I), ("MonthNumber", I), ("MonthName", T), ("MonthKey", I),
        ("Quarter", T), ("DateKey", D), ("AccountKey", T), ("SubName", T),
        ("AccountNumber", T), ("AccountName", T), ("State", T), ("RawProduct", T),
        ("ServiceGroup", T), ("ServiceGroupShort", T), ("FreightTypeDescription", T),
        ("ChargeCategory", T), ("IsAccessorial", T), ("NumberOfUnits", N),
        ("AccessorialSpend", N), ("GrossSpend", N), ("NetSpend", N), ("SourceFile", T),
    ],
    "Dim_Date": [
        ("DateKey", D), ("Year", I), ("MonthNumber", I), ("MonthName", T),
        ("MonthNameLong", T), ("MonthKey", I), ("MonthYearLabel", T), ("Quarter", T),
        ("QuarterKey", I), ("MonthEndDate", D), ("IsCompletedMonth", T),
        ("IsLoaded", T), ("IsReportable", T), ("SortOrder", I),
    ],
    "Dim_Account": [
        ("AccountKey", T), ("SubNumber", T), ("SubName", T), ("AccountNumber", T),
        ("AccountName", T), ("City", T), ("State", T), ("ZIP", T), ("PresentIn", T),
        ("HasTransitData", T), ("HasClaimsData", T), ("Region", T),
    ],
    "Dim_ServiceMapping": [
        ("SourceSystem", T), ("RawProduct", T), ("ServiceGroup", T),
        ("ServiceGroupShort", T), ("ServiceTier", T), ("Scope", T),
        ("IncludeInRanking", T), ("ServicePriority", I), ("Notes", T),
    ],
}

# Columns hidden from the report view: keys, technical flags and lineage.
HIDDEN = {
    "MonthKey", "AccountKey", "SortOrder", "QuarterKey", "DateKey", "MonthEndDate",
    "SourceFile", "SourceLayout", "IsNonServiceRow", "SubNumber", "MonthNumber",
    "VolumeLY", "NetSpendLY", "PresentIn",
}

# Aggregating a key or a flag is always a mistake; only true additive facts get
# a default summarisation.
SUMMARISE = {
    "Volume", "GrossSpend", "NetSpend", "Incentive", "BilledWeightLbs",
    "PackagesMeasured", "LateByTime", "LateByDay", "TotalLate", "OnTimePackages",
    "IssuedClaimsQty", "IssuedClaimsPkgQty", "PaidClaimsQty", "PaidClaimsPkgQty",
    "RegisteredClaimsQty", "RegisteredClaimsPkgQty", "PaidClaimsAmount",
    "ClaimsDeclaredValue", "NumberOfUnits", "AccessorialSpend",
}

SORT_BY = {
    ("Dim_Date", "MonthName"): "SortOrder",
    ("Dim_Date", "MonthYearLabel"): "SortOrder",
    ("Dim_Date", "MonthNameLong"): "SortOrder",
}

# from-table, from-column, to-table, to-column. From is always the many side.
RELATIONSHIPS = [
    ("Fact_VolumeSpend", "MonthKey", "Dim_Date", "MonthKey"),
    ("Fact_TimeInTransit", "MonthKey", "Dim_Date", "MonthKey"),
    ("Fact_Claims", "MonthKey", "Dim_Date", "MonthKey"),
    ("Fact_Accessorial", "MonthKey", "Dim_Date", "MonthKey"),
    ("Fact_VolumeSpend", "AccountKey", "Dim_Account", "AccountKey"),
    ("Fact_TimeInTransit", "AccountKey", "Dim_Account", "AccountKey"),
    ("Fact_Claims", "AccountKey", "Dim_Account", "AccountKey"),
    ("Fact_Accessorial", "AccountKey", "Dim_Account", "AccountKey"),
    ("Fact_VolumeSpend", "ServiceGroup", "Dim_Service", "ServiceGroup"),
    ("Fact_TimeInTransit", "ServiceGroup", "Dim_Service", "ServiceGroup"),
    ("Fact_Accessorial", "ServiceGroup", "Dim_Service", "ServiceGroup"),
    # Deliberately NO Fact_Claims -> Dim_Service. The claims extract carries no
    # product, service or tracking key. A many-to-many through Dim_Account would
    # return "claims for accounts that used this service" and be read as "claims
    # caused by this service". The absence is the honest signal.
]


def m_csv_query(table_name: str) -> list:
    """One Csv.Document query per table, typed from the column list."""
    columns = TABLES[table_name]
    transforms = ", ".join(
        '{"%s", %s}' % (name, {T: "type text", N: "type number",
                               I: "Int64.Type", D: "type date"}[kind])
        for name, kind in columns
    )
    return [
        "let",
        f'    Source = Csv.Document(',
        f'        File.Contents(p_DataFolder & "\\{table_name}.csv"),',
        "        [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"    Typed = Table.TransformColumnTypes(Promoted, {{{transforms}}})",
        "in",
        "    Typed",
    ]


DIM_SERVICE_QUERY = [
    "let",
    "    // One row per Service Group. Dim_ServiceMapping has grain",
    "    // (SourceSystem, RawProduct) and so cannot be the one side of a",
    "    // relationship - RawProduct is not unique across it.",
    "    Source = Dim_ServiceMapping,",
    "    Trimmed = Table.SelectColumns(Source, {\"ServiceGroup\", \"ServiceGroupShort\",",
    "        \"ServiceTier\", \"Scope\", \"IncludeInRanking\", \"ServicePriority\"}),",
    "    Distinct = Table.Distinct(Trimmed, {\"ServiceGroup\"}),",
    "    // Review buckets so an unmapped fact row finds a parent instead of",
    "    // becoming a blank-key orphan on every visual.",
    "    WithReview = Table.Combine({Distinct, #table(",
    "        type table [ServiceGroup = text, ServiceGroupShort = text,",
    "                    ServiceTier = text, Scope = text, IncludeInRanking = text,",
    "                    ServicePriority = Int64.Type],",
    "        {{\"Unmapped - Review\", \"Unmapped\", \"Unmapped\", \"Unknown\", \"No\", 98}})}),",
    "    Deduped = Table.Distinct(WithReview, {\"ServiceGroup\"}),",
    "    Sorted = Table.Sort(Deduped, {{\"ServicePriority\", Order.Ascending}})",
    "in",
    "    Sorted",
]

DIM_SERVICE_COLUMNS = [
    ("ServiceGroup", T), ("ServiceGroupShort", T), ("ServiceTier", T),
    ("Scope", T), ("IncludeInRanking", T), ("ServicePriority", I),
]


def build_column(name, kind, table):
    column = {
        "name": name,
        "dataType": kind,
        "sourceColumn": name,
        "summarizeBy": "sum" if name in SUMMARISE else "none",
        "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
    }
    if name in HIDDEN:
        column["isHidden"] = True
    if kind == D:
        column["formatString"] = "yyyy-mm-dd"
    if kind == N and name in SUMMARISE:
        column["formatString"] = "#,0.00"
    sort_by = SORT_BY.get((table, name))
    if sort_by:
        column["sortByColumn"] = sort_by
    return column


def m_text_literal(value: str) -> str:
    """Quote a value as a Power Query M text literal.

    M does NOT use backslash escaping - a Windows path goes in verbatim, and
    doubling the separators (the reflex from every C-like language) produces a
    literal double backslash and a file-not-found on refresh. The only
    characters needing care are the quote, which doubles, and '#(' which starts
    an M escape sequence.
    """
    escaped = value.replace('"', '""').replace("#(", '#(0023)(')
    return f'"{escaped}"'


def build_model(measures, data_folder, reporting_year):
    tables = []

    for table_name, columns in TABLES.items():
        tables.append({
            "name": table_name,
            "columns": [build_column(n, k, table_name) for n, k in columns],
            "partitions": [{
                "name": table_name,
                "mode": "import",
                "source": {"type": "m", "expression": m_csv_query(table_name)},
            }],
        })

    tables.append({
        "name": "Dim_Service",
        "columns": [build_column(n, k, "Dim_Service") for n, k in DIM_SERVICE_COLUMNS],
        "partitions": [{
            "name": "Dim_Service",
            "mode": "import",
            "source": {"type": "m", "expression": DIM_SERVICE_QUERY},
        }],
    })

    # Dim_ServiceMapping is loaded but hidden: needed for the Data Quality page's
    # mapping inventory, never for a slicer.
    for table in tables:
        if table["name"] == "Dim_ServiceMapping":
            table["isHidden"] = True

    # What-if parameters. GENERATESERIES calculated tables, matching what
    # Modeling > New parameter produces.
    for name, expression, fmt, kind in [
        ("Volume Threshold", "GENERATESERIES(0, 10000, 250)", "#,0", I),
        ("Share Threshold", "GENERATESERIES(0, 0.1, 0.005)", "0.0%", N),
    ]:
        tables.append({
            "name": name,
            "columns": [{
                "name": name,
                "dataType": kind,
                "isNameInferred": True,
                "isDataTypeInferred": True,
                "sourceColumn": "[Value]",
                "formatString": fmt,
                "summarizeBy": "none",
                "type": "calculatedTableColumn",
                "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
            }],
            "partitions": [{
                "name": name,
                "mode": "import",
                "source": {"type": "calculated", "expression": expression},
            }],
            "annotations": [{"name": "PBI_Id", "value": uuid.uuid4().hex}],
        })

    # Measures live on a dedicated table so the field list separates "things you
    # slice by" from "things you measure".
    measure_objects = []
    for m in measures:
        obj = {
            "name": m["name"],
            "expression": m["expression"],
            "displayFolder": m["displayFolder"],
        }
        if m["formatString"] and not m["isText"]:
            obj["formatString"] = m["formatString"]
        measure_objects.append(obj)

    tables.append({
        "name": "_Measures",
        "columns": [{
            "name": "_",
            "dataType": "int64",
            "isHidden": True,
            "sourceColumn": "_",
            "summarizeBy": "none",
        }],
        "partitions": [{
            "name": "_Measures",
            "mode": "import",
            "source": {"type": "m", "expression": [
                "let",
                "    Source = #table(type table [_ = Int64.Type], {{0}})",
                "in",
                "    Source",
            ]},
        }],
        "measures": measure_objects,
    })

    relationships = []
    for from_table, from_column, to_table, to_column in RELATIONSHIPS:
        relationships.append({
            "name": str(uuid.uuid5(uuid.NAMESPACE_OID,
                                   f"{from_table}.{from_column}->{to_table}.{to_column}")),
            "fromTable": from_table,
            "fromColumn": from_column,
            "toTable": to_table,
            "toColumn": to_column,
            "crossFilteringBehavior": "oneDirection",
        })

    expressions = [
        {
            "name": "p_DataFolder",
            "kind": "m",
            "expression": [m_text_literal(data_folder)
                           + ' meta [IsParameterQuery=true, Type="Text", '
                             "IsParameterQueryRequired=true]"],
            "annotations": [{"name": "PBI_NavigationStepName", "value": "Navigation"}],
        },
        {
            "name": "p_ReportingYear",
            "kind": "m",
            "expression": [f'{reporting_year} meta [IsParameterQuery=true, '
                           'Type="Number", IsParameterQueryRequired=true]'],
        },
    ]

    return {
        "name": "UPS2025ExecutiveDashboard",
        "compatibilityLevel": COMPAT_LEVEL,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": relationships,
            "expressions": expressions,
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(
                    ["p_DataFolder", "p_ReportingYear"] + list(TABLES)
                    + ["Dim_Service", "_Measures"])},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "PBI_ProTooling", "value": '["DaxQueryView"]'},
            ],
        },
    }


# ---------------------------------------------------------------------------
# Report layout
#
# Report/Layout is JSON in which each visual's `config` is itself a JSON *string*.
# A visual renders only if its `prototypeQuery` correctly declares the entities
# and fields the projections reference, so both are generated from one spec
# rather than written twice by hand.
# ---------------------------------------------------------------------------

CANVAS_W, CANVAS_H = 1280, 720

# Role names differ per visual type; getting one wrong yields an empty visual.
ROLES = {
    "card": ["Values"],
    "multiRowCard": ["Values"],
    "clusteredColumnChart": ["Category", "Series", "Y"],
    "columnChart": ["Category", "Series", "Y"],
    "clusteredBarChart": ["Category", "Series", "Y"],
    "barChart": ["Category", "Series", "Y"],
    "lineChart": ["Category", "Series", "Y"],
    "donutChart": ["Category", "Y"],
    "tableEx": ["Values"],
    "slicer": ["Values"],
    "scatterChart": ["Category", "X", "Y", "Size"],
}

ALIAS = {
    "_Measures": "m", "Dim_Date": "d", "Dim_Service": "s", "Dim_Account": "a",
    "Fact_VolumeSpend": "v", "Fact_TimeInTransit": "t", "Fact_Claims": "c",
    "Fact_Accessorial": "x", "Dim_ServiceMapping": "p",
    "Volume Threshold": "vt", "Share Threshold": "st",
}


def field(spec):
    """'Table.Field' -> (table, field, is_measure)."""
    table, name = spec.split(".", 1)
    return table, name, table == "_Measures"


def prototype_query(specs):
    """Build From/Select for the given 'Table.Field' references."""
    entities, from_list = {}, []
    for spec in specs:
        table, _, _ = field(spec)
        if table not in entities:
            alias = ALIAS.get(table, table[:2].lower())
            entities[table] = alias
            from_list.append({"Name": alias, "Entity": table, "Type": 0})

    select = []
    for spec in specs:
        table, name, is_measure = field(spec)
        ref = {"Expression": {"SourceRef": {"Source": entities[table]}}, "Property": name}
        select.append({
            ("Measure" if is_measure else "Column"): ref,
            "Name": f"{table}.{name}",
            "NativeReferenceName": name,
        })
    return {"Version": 2, "From": from_list, "Select": select}


def visual(visual_type, x, y, w, h, roles, title=None, title_measure=None,
           objects=None, z=0, sort=None, hide_legend=False):
    """One visual container. `roles` maps a projection role to a list of
    'Table.Field' specs, in the order they should appear."""
    specs = []
    projections = {}
    for role in ROLES.get(visual_type, list(roles)):
        if role in roles and roles[role]:
            projections[role] = [{"queryRef": s} for s in roles[role]]
            specs.extend(roles[role])
    if not specs and visual_type not in ("textbox",):
        raise ValueError(f"{visual_type} has no projections")

    query = prototype_query(specs)
    if sort:
        spec, direction = sort
        table, name, is_measure = field(spec)
        alias = next(f["Name"] for f in query["From"] if f["Entity"] == table)
        ref = {"Expression": {"SourceRef": {"Source": alias}}, "Property": name}
        query["OrderBy"] = [{
            "Direction": 2 if direction == "desc" else 1,
            "Expression": {("Measure" if is_measure else "Column"): ref},
        }]

    vis_objects = dict(objects or {})
    if title is not None or title_measure is not None:
        title_object = {"show": [{"expr": {"Literal": {"Value": "true"}}}]}
        if title_measure:
            table, name, _ = field(title_measure)
            title_object["text"] = [{"expr": {"Measure": {
                "Expression": {"SourceRef": {"Entity": table}}, "Property": name}}}]
        elif title:
            title_object["text"] = [{"expr": {
                "Literal": {"Value": "'" + title.replace("'", "''") + "'"}}}]
        vis_objects["title"] = [{"properties": title_object}]

    if hide_legend:
        vis_objects["legend"] = [{"properties": {
            "show": [{"expr": {"Literal": {"Value": "false"}}}]}}]

    single = {
        "visualType": visual_type,
        "projections": projections,
        "prototypeQuery": query,
        "drillFilterOtherVisuals": True,
    }
    if vis_objects:
        single["objects"] = vis_objects

    config = {
        "name": uuid.uuid4().hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": single,
    }
    return {
        "x": x, "y": y, "z": z, "width": w, "height": h,
        "config": json.dumps(config, separators=(",", ":")),
        "filters": "[]",
    }


def textbox(x, y, w, h, runs, z=0):
    """Static text. `runs` is a list of (text, bold, size, colour) tuples, each
    rendered as its own paragraph."""
    paragraphs = []
    for text, bold, size, colour in runs:
        paragraphs.append({
            "textRuns": [{
                "value": text,
                "textStyle": {
                    "fontWeight": "bold" if bold else "normal",
                    "fontSize": f"{size}pt",
                    "color": colour,
                    "fontFamily": "Segoe UI",
                },
            }]
        })
    config = {
        "name": uuid.uuid4().hex[:20],
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "textbox",
            "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
        },
    }
    return {
        "x": x, "y": y, "z": z, "width": w, "height": h,
        "config": json.dumps(config, separators=(",", ":")),
        "filters": "[]",
    }


def kpi_row(y, cards, top=0, height=92, gap=10, left=16, total_width=1248):
    """Evenly spaced KPI cards. Card sub-labels are not a Power BI card feature,
    so the basis line is carried by the card title instead."""
    out = []
    width = (total_width - gap * (len(cards) - 1)) / len(cards)
    for i, (measure, title) in enumerate(cards):
        out.append(visual("card", left + i * (width + gap), y, width, height,
                          {"Values": [measure]}, title=title))
    return out


def section(index, name, visuals, filters="[]"):
    return {
        "id": index,
        "name": f"ReportSection{uuid.uuid4().hex}",
        "displayName": name,
        "filters": filters,
        "ordinal": index,
        "visualContainers": visuals,
        "config": json.dumps({}, separators=(",", ":")),
        "displayOption": 1,
        "width": CANVAS_W,
        "height": CANVAS_H,
    }


BANNER_H = 40
INK = "#0B0B0B"
MUTED = "#898781"


def page_banner(note):
    """Every page states its own reporting basis. A report that says what it is
    built on cannot be misquoted from a screenshot."""
    return [
        visual("card", 16, 8, 700, BANNER_H, {"Values": ["_Measures.Data Basis Banner"]},
               title="Reporting basis"),
        textbox(724, 8, 540, BANNER_H, [(note, False, 9, MUTED)]),
    ]


def build_sections():
    pages = []

    # ---- Page 1: Executive Overview ---------------------------------------
    v = page_banner("Cost conclusions rest on all loaded months. Reliability rests "
                    "on the months Time-in-Transit covers - see the banner.")
    v += kpi_row(56, [
        ("_Measures.Total Shipments", "Total shipments"),
        ("_Measures.Total Net Spend", "Net spend"),
        ("_Measures.On-Time Delivery %", "On-time delivery"),
        ("_Measures.Loss Claim Rate per 10k", "Loss claims / 10k"),
        ("_Measures.Avg Net Spend per Shipment", "Net spend / shipment"),
    ])
    v += [
        visual("lineChart", 16, 158, 760, 240,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.On-Time Delivery %"]},
               title="On-time delivery by month", hide_legend=True),
        visual("card", 786, 158, 478, 240,
               {"Values": ["_Measures.Recommendation Callout"]},
               title="Recommendation"),
        visual("tableEx", 16, 408, 900, 296,
               {"Values": ["Dim_Service.ServiceGroup",
                           "_Measures.Rankable Shipments",
                           "_Measures.On-Time Delivery %",
                           "_Measures.OTD Wilson Lower Bound",
                           "_Measures.Avg Net Spend per Shipment",
                           "_Measures.Avg Net Spend per Billed Lb",
                           "_Measures.Service Consistency Score",
                           "_Measures.Qualification Status"]},
               title_measure="_Measures.Title - Service Scorecard",
               sort=("_Measures.Service Consistency Score", "desc")),
        visual("donutChart", 926, 408, 338, 296,
               {"Category": ["Dim_Service.ServiceGroupShort"],
                "Y": ["_Measures.Rankable Shipments"]},
               title="Volume mix by service"),
    ]
    pages.append(section(0, "1 Executive Overview", v))

    # ---- Page 2: Service Performance --------------------------------------
    v = page_banner("Bars show the observed rate; compare against the confidence "
                    "floor column before ranking on any of them.")
    v += [
        visual("clusteredBarChart", 16, 56, 620, 320,
               {"Category": ["Dim_Service.ServiceGroup"],
                "Y": ["_Measures.On-Time Delivery %"]},
               title="On-time delivery by service", hide_legend=True,
               sort=("_Measures.On-Time Delivery %", "desc")),
        visual("clusteredColumnChart", 646, 56, 618, 320,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.Late by Day", "_Measures.Late by Time"]},
               title="Lateness severity - missed day vs missed time window"),
        visual("tableEx", 16, 386, 1248, 318,
               {"Values": ["Dim_Service.ServiceGroup",
                           "_Measures.Rankable Shipments",
                           "_Measures.Packages Measured",
                           "_Measures.On-Time Delivery %",
                           "_Measures.OTD Wilson Lower Bound",
                           "_Measures.OTD Confidence Label",
                           "_Measures.Late by Day %",
                           "_Measures.OTD Volatility (pp)",
                           "_Measures.Qualification Status"]},
               title="Service reliability detail - confidence and qualification",
               sort=("_Measures.On-Time Delivery %", "desc")),
    ]
    pages.append(section(1, "2 Service Performance", v))

    # ---- Page 3: Cost and Volume ------------------------------------------
    v = page_banner("Read both cost views. Per-shipment cost is not comparable "
                    "across services of different package weight.")
    v += [
        visual("clusteredColumnChart", 16, 56, 620, 290,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.Rankable Shipments"]},
               title="Shipment volume by month", hide_legend=True),
        visual("clusteredColumnChart", 646, 56, 618, 290,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.Total Net Spend"]},
               title="Net spend by month", hide_legend=True),
        # Two separate charts, never a dual axis: different units on one scale
        # makes unrelated magnitudes look comparable.
        visual("clusteredBarChart", 16, 356, 400, 210,
               {"Category": ["Dim_Service.ServiceGroupShort"],
                "Y": ["_Measures.Avg Net Spend per Shipment"]},
               title="Cost per shipment", hide_legend=True,
               sort=("_Measures.Avg Net Spend per Shipment", "desc")),
        visual("clusteredBarChart", 426, 356, 400, 210,
               {"Category": ["Dim_Service.ServiceGroupShort"],
                "Y": ["_Measures.Avg Net Spend per Billed Lb"]},
               title="Cost per billed pound - the comparable view",
               hide_legend=True,
               sort=("_Measures.Avg Net Spend per Billed Lb", "desc")),
        textbox(836, 356, 428, 210, [
            ("Why two cost charts", True, 11, INK),
            ("Services carry very different package weights. Ground averages "
             "roughly 16 lb per piece against roughly 2 lb for 2nd Day Air, so "
             "per-shipment cost compares the price of two different things and "
             "makes them look almost identically priced.", False, 9, MUTED),
            ("Per billed pound, Ground is about seven times cheaper. Read the "
             "right chart before concluding that upgrading volume to a faster "
             "service is cheap. The consistency score uses the per-pound view.",
             False, 9, MUTED),
        ]),
        visual("tableEx", 16, 576, 1248, 128,
               {"Values": ["Dim_Service.ServiceGroup",
                           "_Measures.Rankable Shipments",
                           "_Measures.Total Net Spend",
                           "_Measures.Avg Billed Weight per Shipment",
                           "_Measures.Avg Net Spend per Shipment",
                           "_Measures.Avg Net Spend per Billed Lb",
                           "_Measures.Service Spend Mix %"]},
               title="Cost bridge by service",
               sort=("_Measures.Total Net Spend", "desc")),
    ]
    pages.append(section(2, "3 Cost and Volume", v))

    # ---- Page 4: Claims and Exceptions ------------------------------------
    v = page_banner("Account grain only. Claims carry no service key.")
    v += [
        textbox(16, 56, 1248, 62, [
            ("Claims cannot be attributed to a service.", True, 11, "#B3261E"),
            ("The claims extract carries sub-parent, account and claims category "
             "- no product, service or tracking number. Every figure on this page "
             "is at account grain, and the Service Group slicer deliberately does "
             "nothing here. Adding a service or tracking field to this export is "
             "the single highest-value change available to this model.",
             False, 9, MUTED),
        ]),
    ]
    v += kpi_row(126, [
        ("_Measures.Issued Claims Pkgs", "Claims issued"),
        ("_Measures.Loss Claims", "Loss claims"),
        ("_Measures.Claims Recovery Rate", "Recovery rate"),
        ("_Measures.Paid Claims Amount", "Paid claims"),
        ("_Measures.Top Account Share of Loss Claims", "Worst-account share of loss"),
    ], height=86)
    v += [
        visual("clusteredBarChart", 16, 222, 400, 250,
               {"Category": ["Fact_Claims.ClaimsCategory"],
                "Y": ["_Measures.Issued Claims Pkgs", "_Measures.Paid Claims Pkgs"]},
               title="Claims by category - issued vs paid"),
        visual("lineChart", 426, 222, 838, 250,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.Claims Rate per 10k"]},
               title="Claims per 10,000 shipments by month", hide_legend=True),
        visual("tableEx", 16, 482, 1248, 222,
               {"Values": ["Dim_Account.AccountName",
                           "_Measures.Rankable Shipments",
                           "_Measures.Loss Claims",
                           "_Measures.Issued Claims Pkgs",
                           "_Measures.Loss Claim Rate per 10k",
                           "_Measures.Loss Rate Index vs Firm",
                           "_Measures.Paid Claims Amount",
                           "_Measures.Loss Risk Flag"]},
               title_measure="_Measures.Title - Claims",
               sort=("_Measures.Loss Rate Index vs Firm", "desc")),
    ]
    pages.append(section(3, "4 Claims and Exceptions", v))

    # ---- Page 5: Account and Location -------------------------------------
    v = page_banner("An account with volume and no transit coverage is invisible "
                    "in every reliability figure - the right-hand table names them.")
    v += [
        visual("tableEx", 16, 56, 820, 320,
               {"Values": ["Dim_Account.SubName", "Dim_Account.AccountName",
                           "Dim_Account.State",
                           "_Measures.Rankable Shipments",
                           "_Measures.On-Time Delivery %",
                           "_Measures.Loss Rate Index vs Firm",
                           "_Measures.Avg Net Spend per Shipment"]},
               title="Account scorecard",
               sort=("_Measures.Rankable Shipments", "desc")),
        visual("clusteredBarChart", 846, 56, 418, 320,
               {"Category": ["Dim_Account.Region"],
                "Y": ["_Measures.Rankable Shipments"]},
               title="Volume by region", hide_legend=True,
               sort=("_Measures.Rankable Shipments", "desc")),
        visual("clusteredBarChart", 16, 386, 620, 318,
               {"Category": ["Dim_Account.State"],
                "Y": ["_Measures.On-Time Delivery %"]},
               title="On-time delivery by state", hide_legend=True,
               sort=("_Measures.On-Time Delivery %", "asc")),
        visual("tableEx", 646, 386, 618, 318,
               {"Values": ["Dim_Account.AccountName",
                           "Dim_Account.HasTransitData",
                           "_Measures.Rankable Shipments",
                           "_Measures.Packages Measured"]},
               title="Transit data coverage by account",
               sort=("_Measures.Rankable Shipments", "desc")),
    ]
    pages.append(section(4, "5 Account and Location", v))

    # ---- Page 6: Annual Recommendation ------------------------------------
    v = page_banner("Controlled page. Month and Account slicers are deliberately "
                    "absent - an annual policy sliced to one month is not one.")
    v += [
        visual("card", 16, 56, 830, 120,
               {"Values": ["_Measures.Recommendation Callout"]},
               title="Recommendation"),
        visual("card", 856, 56, 408, 120,
               {"Values": ["_Measures.Score Basis"]},
               title="Score basis - the weights actually used"),
        visual("tableEx", 16, 186, 830, 300,
               {"Values": ["Dim_Service.ServiceGroup",
                           "Dim_Service.ServiceTier",
                           "_Measures.Rankable Shipments",
                           "_Measures.Service Consistency Score",
                           "_Measures.Service Rank",
                           "_Measures.Recommendation Category"]},
               title="Recommendation matrix",
               sort=("_Measures.Service Consistency Score", "desc")),
        visual("slicer", 856, 186, 408, 96,
               {"Values": ["Volume Threshold.Volume Threshold"]},
               title="Minimum annual shipments to qualify"),
        visual("slicer", 856, 292, 408, 96,
               {"Values": ["Share Threshold.Share Threshold"]},
               title="Minimum share of volume to qualify"),
        visual("slicer", 856, 398, 408, 88,
               {"Values": ["Dim_Service.Scope"]},
               title="Domestic / International"),
        visual("clusteredBarChart", 16, 496, 620, 208,
               {"Category": ["Dim_Service.ServiceGroup"],
                "Y": ["_Measures.Score - Reliability", "_Measures.Score - Cost"]},
               title="Score components (normalised 0-1 across qualified services)"),
        textbox(646, 496, 618, 208, [
            ("Reading this page", True, 11, INK),
            ("The ranking answers 'which service performs best'. The policy "
             "question is 'which service should we default to'. On this data "
             "those have different answers: the volume anchor carries the "
             "majority of shipments at a fraction of the cost per pound, and is "
             "evaluated on whether its performance is acceptable and stable - not "
             "on whether something else scores higher.", False, 9, MUTED),
            ("Move the threshold sliders to test how sensitive the ranking is. "
             "Setting the volume threshold to zero shows why the threshold "
             "exists.", False, 9, MUTED),
        ]),
    ]
    pages.append(section(5, "6 Annual Recommendation", v))

    # ---- Page 7: Accessorial and Cost Drivers -----------------------------
    v = page_banner("Charge-level detail. This table reconciles to net spend - "
                    "see the Data Quality page.")
    v += [
        visual("clusteredBarChart", 16, 56, 760, 400,
               {"Category": ["Fact_Accessorial.ChargeCategory"],
                "Y": ["_Measures.Accessorial Net Spend"]},
               title="Net spend by charge category", hide_legend=True,
               sort=("_Measures.Accessorial Net Spend", "desc")),
        visual("tableEx", 786, 56, 478, 400,
               {"Values": ["Fact_Accessorial.ChargeCategory",
                           "Fact_Accessorial.IsAccessorial",
                           "_Measures.Accessorial Net Spend"]},
               title="Charge detail",
               sort=("_Measures.Accessorial Net Spend", "desc")),
        visual("clusteredColumnChart", 16, 466, 760, 238,
               {"Category": ["Dim_Date.MonthYearLabel"],
                "Y": ["_Measures.Accessorial Net Spend"]},
               title="Charge spend by month", hide_legend=True),
        textbox(786, 466, 478, 238, [
            ("Avoidable cost", True, 11, INK),
            ("Address Correction is charged per package, and every unit is a "
             "package that shipped to a bad address the firm supplied. It is "
             "fully avoidable through address validation at the point of "
             "shipment - a process fix, not a negotiation.", False, 9, MUTED),
            ("Filter the charge category slicer to Address Correction to size it.",
             False, 9, MUTED),
        ]),
    ]
    pages.append(section(6, "7 Accessorial and Cost Drivers", v))

    # ---- Page 8: Data Quality ---------------------------------------------
    v = page_banner("This page accounts for every row the report excludes.")
    v += kpi_row(56, [
        ("_Measures.Months Loaded", "Months loaded"),
        ("_Measures.Annual Completeness %", "Annual completeness"),
        ("_Measures.Reconciliation Status", "Spend reconciliation"),
        ("_Measures.Measured vs Billed Coverage %", "Measured vs billed"),
        ("_Measures.Unattributed Spend %", "Unattributed spend"),
    ])
    v += [
        visual("card", 16, 158, 620, 80, {"Values": ["_Measures.Coverage Summary"]},
               title="Source coverage"),
        visual("card", 646, 158, 618, 80, {"Values": ["_Measures.Missing Months List"]},
               title="Completed months not yet loaded"),
        visual("tableEx", 16, 248, 620, 220,
               {"Values": ["Dim_Date.MonthYearLabel", "Dim_Date.IsCompletedMonth",
                           "Dim_Date.IsLoaded", "Dim_Date.IsReportable",
                           "_Measures.Total Shipments",
                           "_Measures.Packages Measured",
                           "_Measures.Issued Claims Pkgs"]},
               title="Coverage by month and source"),
        visual("tableEx", 646, 248, 618, 220,
               {"Values": ["Dim_ServiceMapping.SourceSystem",
                           "Dim_ServiceMapping.RawProduct",
                           "Dim_ServiceMapping.ServiceGroup",
                           "Dim_ServiceMapping.IncludeInRanking"]},
               title="Service mapping inventory - both source vocabularies"),
        visual("multiRowCard", 16, 478, 620, 226,
               {"Values": ["_Measures.Excluded Adjustment Spend",
                           "_Measures.Spend-Only Adjustment Rows",
                           "_Measures.Spend-Only Adjustment Value",
                           "_Measures.Unmapped Product Rows",
                           "_Measures.Masked Sub-Parent Volume"]},
               title="Exclusions - counted, never silent"),
        textbox(646, 478, 618, 226, [
            ("Known limitations", True, 11, INK),
            ("Claims carry no service key, so the loss (30%) and exception (20%) "
             "components of the recommendation score cannot be computed at "
             "service grain. Their weight is reallocated, and the score reports "
             "its own effective weights.", False, 9, MUTED),
            ("Time-in-Transit is a Shipper View population; Volume & Spend is a "
             "Payor View population. A consistent gap between measured packages "
             "and billed volume is expected and is not an error. They are never "
             "used as the same denominator.", False, 9, MUTED),
            ("Cost per shipment is not comparable across services without "
             "controlling for package weight.", False, 9, MUTED),
        ]),
    ]
    pages.append(section(7, "8 Data Quality", v))

    return pages


def build_layout():
    return {
        "id": 0,
        "resourcePackages": [{
            "resourcePackage": {
                "disabled": False,
                "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json",
                           "type": 202}],
                "name": "SharedResources",
                "type": 2,
            }
        }],
        "sections": build_sections(),
        "config": json.dumps({
            "version": "5.55",
            "themeCollection": {"baseTheme": {"name": "CY24SU10", "version": "5.55",
                                              "type": 2}},
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
            "settings": {"useStylableVisualContainerHeader": True,
                         "useNewFilterPaneExperience": True,
                         "allowChangeFilterTypes": True},
            "objects": {"section": [{"properties": {
                "verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
        }, separators=(",", ":")),
        "layoutOptimization": 0,
        "publicCustomVisuals": [],
    }


# ---------------------------------------------------------------------------
# Package assembly
# ---------------------------------------------------------------------------

# Declares Defaults for the extensions present and real content types on the
# JSON parts, mirroring what Desktop emits. The earlier version declared every
# ContentType as empty and had no Default for "xml".
CONTENT_TYPES = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="json" ContentType=""/>'
    '<Default Extension="xml" ContentType=""/>'
    '<Override PartName="/Version" ContentType=""/>'
    '<Override PartName="/DataModelSchema" ContentType=""/>'
    '<Override PartName="/DiagramLayout" ContentType=""/>'
    '<Override PartName="/Report/Layout" ContentType=""/>'
    '<Override PartName="/Settings" ContentType="application/json"/>'
    '<Override PartName="/Metadata" ContentType="application/json"/>'
    '</Types>'
)

# The base theme part must exist because Report/Layout references it in its
# resource package. Contents are a minimal valid theme; the full report theme in
# theme/UPS_Executive_Theme.json is applied via View > Themes > Browse, which
# keeps the package structure simple and avoids a malformed custom-theme
# resource preventing the file from opening at all.
BASE_THEME = {
    "name": "CY24SU10",
    "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                   "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "background": "#FFFFFF",
    "foreground": "#0B0B0B",
    "tableAccent": "#2a78d6",
}

DIAGRAM_LAYOUT = {
    "version": "1.1.0",
    "diagrams": [{
        "ordinal": 0,
        "scrollPosition": {"x": 0, "y": 0},
        "nodes": [],
        "name": "All tables",
        "zoomValue": 100,
        "pinKeyFieldsToTop": False,
        "showExtraHeaderInfo": False,
        "hideKeyFieldsWhenCollapsed": False,
        "tablesLocked": False,
    }],
    "selectedDiagram": "All tables",
    "defaultDiagram": "All tables",
}

SETTINGS = {
    "Version": 4,
    "ReportSettings": {},
    "QueriesSettings": {
        "TypeDetectionEnabled": True,
        "RelationshipImportEnabled": True,
        "RunBackgroundAnalysis": True,
    },
}


def metadata(description):
    return {
        "Version": METADATA_VERSION,
        "AutoCreatedRelationships": [],
        "FileDescription": description,
        "CreatedFrom": "Desktop",
    }


def utf16(text: str) -> bytes:
    """UTF-16 LE with NO byte-order mark - matching what Desktop writes.

    A BOM here is the difference between a file that opens and one reported as
    corrupt, and nothing in the error message points at it."""
    return text.encode(UTF16)


def write_pbit(out_path: pathlib.Path, model, layout, description):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    compact = dict(separators=(",", ":"), ensure_ascii=False)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as pkg:
        pkg.writestr("[Content_Types].xml", CONTENT_TYPES.encode("utf-8"))
        pkg.writestr("Version", utf16(PBI_VERSION))
        pkg.writestr("DataModelSchema", utf16(json.dumps(model, **compact)))
        pkg.writestr("DiagramLayout", utf16(json.dumps(DIAGRAM_LAYOUT, **compact)))
        pkg.writestr("Report/Layout", utf16(json.dumps(layout, **compact)))
        pkg.writestr("Settings", utf16(json.dumps(SETTINGS, **compact)))
        pkg.writestr("Metadata", utf16(json.dumps(metadata(description), **compact)))
        # Plain UTF-8: resource JSON is not a UTF-16 part.
        pkg.writestr("Report/StaticResources/SharedResources/BaseThemes/CY24SU10.json",
                     json.dumps(BASE_THEME, **compact).encode("utf-8"))
    return out_path


def write_pbip(out_dir: pathlib.Path, model, layout, name):
    """Also emit the Power BI Project (PBIP) form.

    PBIP is Microsoft's supported text format and opens directly in Desktop. It
    is the fallback if the .pbit package is rejected for any reason, and it is
    the form that belongs in source control - a reviewer can diff a measure
    change instead of a binary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = out_dir / f"{name}.SemanticModel"
    report_dir = out_dir / f"{name}.Report"
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    pretty = dict(indent=2, ensure_ascii=False)

    (out_dir / f"{name}.pbip").write_text(json.dumps({
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{name}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, **pretty), encoding="utf-8")

    (model_dir / "definition.pbism").write_text(json.dumps({
        "version": "1.0", "settings": {},
    }, **pretty), encoding="utf-8")
    (model_dir / "model.bim").write_text(json.dumps(model, **pretty), encoding="utf-8")

    (report_dir / "definition.pbir").write_text(json.dumps({
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{name}.SemanticModel"}},
    }, **pretty), encoding="utf-8")
    (report_dir / "report.json").write_text(json.dumps(layout, **pretty), encoding="utf-8")
    return out_dir


# ---------------------------------------------------------------------------
# Self-checks
#
# The one thing this generator cannot do is open the file. These checks catch
# the failure modes that are detectable without Power BI Desktop: broken
# references, malformed JSON, duplicate names, and orphaned relationships.
# ---------------------------------------------------------------------------

DAX_REF = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]")
TIME_INTELLIGENCE = re.compile(r"\b(TOTALYTD|TOTALQTD|TOTALMTD|SAMEPERIODLASTYEAR"
                               r"|DATEADD|DATESYTD|DATESQTD|DATESMTD|PARALLELPERIOD"
                               r"|PREVIOUSMONTH|NEXTMONTH|DATESINPERIOD)\s*\(")


def validate_dax_references(model):
    """Check every Table[Column] reference in every measure against the model.

    This exists because three real defects shipped past a reading of the DAX:
    measures filtering `Dim_ServiceMapping`, which has no relationship to the
    facts, so REMOVEFILTERS on it silently did nothing and every mix percentage
    was wrong; a reference to a column that only exists on the mapping table;
    and daily-grain time-intelligence functions against a month-grain date
    table. None raise an error in Power BI - they just return wrong numbers.
    """
    problems = []
    tables = {t["name"]: t for t in model["model"]["tables"]}
    columns = {name: {c["name"] for c in t.get("columns", [])}
               for name, t in tables.items()}
    measures = {m["name"] for t in tables.values() for m in t.get("measures", [])}

    # Tables a measure may legitimately filter: those with a relationship path
    # to a fact. Anything else is a no-op filter and almost certainly a bug.
    related = {r["fromTable"] for r in model["model"]["relationships"]}
    related |= {r["toTable"] for r in model["model"]["relationships"]}
    filterable = related | {"Volume Threshold", "Share Threshold"}

    # Date-table grain: month grain cannot support DAX time intelligence.
    date_rows_are_months = True

    for table in tables.values():
        for measure in table.get("measures", []):
            body = "\n".join(measure["expression"])
            label = measure["name"]

            for quoted, bare, column in DAX_REF.findall(body):
                ref_table = quoted or bare
                if column.startswith("@"):
                    continue                       # ADDCOLUMNS extension column
                if ref_table in measures or not ref_table:
                    continue
                if ref_table not in tables:
                    problems.append(f"[{label}] references unknown table "
                                    f"'{ref_table}'")
                elif column not in columns[ref_table]:
                    problems.append(f"[{label}] references unknown column "
                                    f"{ref_table}[{column}]")

            for match in re.finditer(r"REMOVEFILTERS\s*\(([^)]*)\)", body):
                for arg in match.group(1).split(","):
                    name = arg.strip().split("[")[0].strip().strip("'")
                    if name and name in tables and name not in filterable:
                        problems.append(
                            f"[{label}] REMOVEFILTERS on '{name}', which has no "
                            f"relationship to any fact - the filter is a no-op "
                            f"and the result will be silently wrong")

            if date_rows_are_months:
                found = TIME_INTELLIGENCE.search(body)
                if found:
                    problems.append(
                        f"[{label}] uses {found.group(1)}, which requires a "
                        f"contiguous daily date table. Dim_Date is month grain "
                        f"- use MonthKey arithmetic instead")

            for name in re.findall(r"\[([A-Za-z][^\]]*)\]", body):
                if name.startswith("@"):
                    continue
                if name not in measures and not any(
                        name in cols for cols in columns.values()):
                    problems.append(f"[{label}] references unknown measure [{name}]")

    return problems


def validate(model, layout):
    problems = validate_dax_references(model)
    tables = {t["name"]: t for t in model["model"]["tables"]}

    columns = {}
    for name, table in tables.items():
        columns[name] = {c["name"] for c in table.get("columns", [])}

    measures = set()
    for table in tables.values():
        for m in table.get("measures", []):
            if m["name"] in measures:
                problems.append(f"Duplicate measure name: {m['name']}")
            measures.add(m["name"])

    # Relationships must point at columns that exist on both sides.
    for rel in model["model"]["relationships"]:
        for side in ("from", "to"):
            table = rel[f"{side}Table"]
            column = rel[f"{side}Column"]
            if table not in tables:
                problems.append(f"Relationship references missing table {table}")
            elif column not in columns[table]:
                problems.append(f"Relationship references missing column "
                                f"{table}[{column}]")

    # Every field a visual projects must resolve to a real measure or column.
    for sec in layout["sections"]:
        for container in sec["visualContainers"]:
            config = json.loads(container["config"])
            single = config.get("singleVisual", {})
            for role, items in single.get("projections", {}).items():
                for item in items:
                    table, name = item["queryRef"].split(".", 1)
                    if table == "_Measures":
                        if name not in measures:
                            problems.append(
                                f"{sec['displayName']}: unknown measure "
                                f"[{name}] in role {role}")
                    elif table not in tables:
                        problems.append(f"{sec['displayName']}: unknown table {table}")
                    elif name not in columns[table]:
                        problems.append(f"{sec['displayName']}: unknown column "
                                        f"{table}[{name}]")

            # A projection with no matching Select entry renders empty.
            select_names = {s["Name"] for s in single.get("prototypeQuery", {})
                            .get("Select", [])}
            for items in single.get("projections", {}).values():
                for item in items:
                    if item["queryRef"] not in select_names:
                        problems.append(f"{sec['displayName']}: {item['queryRef']} "
                                        f"projected but absent from prototypeQuery")

            # Visuals must sit inside the canvas.
            if (container["x"] < 0 or container["y"] < 0
                    or container["x"] + container["width"] > CANVAS_W + 1
                    or container["y"] + container["height"] > CANVAS_H + 1):
                problems.append(f"{sec['displayName']}: visual outside canvas "
                                f"({container['x']},{container['y']} "
                                f"{container['width']}x{container['height']})")

    # Sort expressions must reference a field the query actually selects.
    for sec in layout["sections"]:
        for container in sec["visualContainers"]:
            query = json.loads(container["config"]).get("singleVisual", {}) \
                        .get("prototypeQuery", {})
            aliases = {f["Name"] for f in query.get("From", [])}
            for order in query.get("OrderBy", []):
                expr = order["Expression"]
                ref = expr.get("Measure") or expr.get("Column")
                source = ref["Expression"]["SourceRef"]["Source"]
                if source not in aliases:
                    problems.append(f"{sec['displayName']}: OrderBy references "
                                    f"unknown source alias {source}")

    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=ROOT / "dist" / "UPS_2025_Executive_Dashboard.pbit")
    parser.add_argument("--pbip-out", type=pathlib.Path,
                        default=ROOT / "dist" / "pbip")
    parser.add_argument("--data-folder", default=r"C:\UPS\2025\processed",
                        help="Default value for the p_DataFolder parameter.")
    parser.add_argument("--reporting-year", type=int, default=2025)
    parser.add_argument("--no-pbip", action="store_true")
    args = parser.parse_args()

    measures = load_measures()
    model = build_model(measures, args.data_folder, args.reporting_year)
    layout = build_layout()

    problems = validate(model, layout)
    if problems:
        print(f"VALIDATION FAILED ({len(problems)} issues):")
        for problem in problems:
            print("  -", problem)
        raise SystemExit(1)

    write_pbit(args.out, model, layout,
               "UPS 2025 Annual Shipping Performance - executive dashboard")
    size = args.out.stat().st_size / 1024
    print(f"Wrote {args.out} ({size:.1f} KB)")
    print(f"  measures     {len(measures)}")
    print(f"  tables       {len(model['model']['tables'])}")
    print(f"  relationships{len(model['model']['relationships']):>4}")
    print(f"  pages        {len(layout['sections'])}")
    print(f"  visuals      {sum(len(s['visualContainers']) for s in layout['sections'])}")

    if not args.no_pbip:
        out = write_pbip(args.pbip_out, model, layout, "UPS_2025_Executive_Dashboard")
        print(f"Wrote {out} (PBIP fallback / source-control form)")


if __name__ == "__main__":
    main()
