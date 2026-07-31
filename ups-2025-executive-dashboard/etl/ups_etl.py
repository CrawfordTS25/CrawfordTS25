"""
UPS 2025 Annual Shipping Performance - source-to-star-schema ETL.

Reads the raw UPS billing extracts (Volume & Net Spend, Time-in-Transit, Claims,
Accessorial) and produces the conformed star-schema tables that the Power BI
model consumes:

    Fact_VolumeSpend.csv      Fact_TimeInTransit.csv   Fact_Claims.csv
    Fact_Accessorial.csv      Dim_Date.csv             Dim_ServiceMapping.csv
    Dim_Account.csv           DQ_SourceInventory.csv   DQ_UnmappedProducts.csv
    DQ_ExcludedRows.csv

The same normalisation rules are mirrored in powerbi/powerquery/*.m so the Power
BI model can refresh directly from the raw folder without this script. This
script is the reference implementation and the validation harness: it is what
proves the rules are correct against real files before they are hand-carried
into Power Query.

Usage:
    python etl/ups_etl.py --raw data/raw --out data/processed
    python etl/ups_etl.py --raw data/raw --out data/processed --report
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install -r etl/requirements.txt")


# --------------------------------------------------------------------------
# Extract-shape constants
#
# UPS delivers two different Volume & Net Spend layouts. Both are handled.
#   Schema A "Monthly VnR by Product by Account" / "VnR_YTD"
#       header row 6, TY/LY/Diff sub-header row 7, data from row 8,
#       carries a WE/Mo/Qtr period column and prior-year comparatives.
#   Schema B "VnS"
#       header row 5, data from row 6, single period, no comparatives,
#       period is only stated in the title block on row 3.
# --------------------------------------------------------------------------

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

QUARTER_OF = {m: (m - 1) // 3 + 1 for m in range(1, 13)}

# Rows that are structurally not shipment activity.
SENTINEL_KEYS = {"grand total", "total", "", "none"}

# UPS masks the sub-parent on some accounts with '@@'. This is NOT a sentinel:
# the account number, address and shipment activity on those rows are real
# (J222E7 / EDWARD JONES / TCO carries genuine international volume). Dropping
# them on a naive '@@' match silently loses shipments, so they are retained and
# relabelled instead.
MASKED_SUB_PARENT = "@@"
MASKED_SUB_PARENT_LABEL = "Unassigned Sub-Parent"

# Products that carry billing adjustments rather than shipment activity.
NON_SERVICE_PRODUCTS = {"MISC / UNC"}


@dataclass
class Rejects:
    """Every row the ETL drops, with the reason, so the Data Quality page can
    account for 100% of the source rows rather than silently losing them."""

    rows: list = field(default_factory=list)

    def add(self, source_file, sheet, row_no, reason, detail=""):
        self.rows.append(
            {
                "SourceFile": source_file,
                "Sheet": sheet,
                "SourceRow": row_no,
                "Reason": reason,
                "Detail": str(detail)[:200],
            }
        )


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def clean_text(value) -> str:
    """UPS exports prefix ID-like columns with an apostrophe to force Excel to
    treat them as text. Strip it, collapse whitespace, and normalise None."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("'"):
        text = text[1:]
    return re.sub(r"\s+", " ", text).strip()


def num(value) -> float:
    """Coerce to float. Blanks, dashes and stray text become 0.0 so that sums
    are never poisoned by a NULL, while genuinely negative values (credits and
    rating adjustments) are preserved."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if text in {"", "-", "--", "N/A", "NA"}:
        return 0.0
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def is_sentinel(sub_number, account_number) -> bool:
    """A row is dropped only when it is a report artefact - a Grand Total line
    or a row with no account at all. Deliberately *not* keyed on the sub-parent
    alone: a masked '@@' sub-parent still has a real account and real volume."""
    sub = clean_text(sub_number).lower()
    account = clean_text(account_number).lower()
    if sub in {"grand total", "total"} or account in {"grand total", "total"}:
        return True
    return account in {"", "none"} and sub in {"", "none"}


def sub_parent_label(sub_number, sub_name) -> tuple:
    """Normalise the masked sub-parent so it is visible and auditable in the
    report rather than being confused for missing data."""
    number = clean_text(sub_number)
    name = clean_text(sub_name)
    if number == MASKED_SUB_PARENT or name == MASKED_SUB_PARENT:
        return MASKED_SUB_PARENT, MASKED_SUB_PARENT_LABEL, "Yes"
    return number, name, "No"


def account_key(sub_number: str, account_number: str) -> str:
    """Account numbers repeat across sub-parents in these extracts, so the
    grain of Dim_Account is Sub-Parent + Account."""
    return f"{clean_text(sub_number)}|{clean_text(account_number)}"


def parse_period_from_title(cells, fallback_month=None):
    """Schema B states its period only in the title block, e.g.
    'March 2025 - Shipper View' or 'April, 2025 - Payor View'.
    Schema A uses 'January, 2025' or 'January - February, 2025'."""
    blob = " ".join(clean_text(c) for c in cells if c)
    year_match = re.search(r"(20\d{2})", blob)
    year = int(year_match.group(1)) if year_match else None
    found = [MONTHS[w] for w in re.findall(r"[A-Za-z]+", blob.lower()) if w in MONTHS]
    month = found[-1] if found else fallback_month
    return year, month


def parse_period_from_filename(path: Path):
    """Fallback and cross-check: UPS_2025_03_AllTabs.xlsx -> (2025, 3)."""
    match = re.search(r"(20\d{2})[_\-](\d{1,2})", path.name)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"^(\d{1,2})[\s_\-]*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)",
                      path.name.upper())
    if match:
        return None, int(match.group(1))
    return None, None


def view_type_from_title(cells) -> str:
    """'Shipper View' and 'Payor View' are different shipment populations.
    Recording this stops anyone from reconciling a shipper-view package count
    against a payor-view volume count and concluding the data is broken."""
    blob = " ".join(clean_text(c) for c in cells if c).lower()
    if "shipper" in blob:
        return "Shipper View"
    if "payor" in blob or "payer" in blob:
        return "Payor View"
    return "Unspecified"


def header_rows(ws, limit=8):
    return [row for row in ws.iter_rows(min_row=1, max_row=limit, values_only=True)]


def title_cells(ws, limit=4):
    cells = []
    for row in ws.iter_rows(min_row=1, max_row=limit, values_only=True):
        cells.extend(row)
    return cells


# --------------------------------------------------------------------------
# Service mapping
# --------------------------------------------------------------------------

def load_service_mapping(path: Path):
    """Dim_ServiceMapping is a controlled table, not an ad hoc text filter in a
    visual. It is a conformed bridge: Volume & Net Spend and Time-in-Transit
    describe the same services with different vocabularies
    ('NDA REG / EXPRESS PKG' vs 'NEXT DAY AIR'), so both source vocabularies
    map into one executive Service Group."""
    lookup = {}
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            row = {k: (v or "").strip() for k, v in row.items()}
            lookup[(row["SourceSystem"].upper(), row["RawProduct"].upper())] = row
            rows.append(row)
    return lookup, rows


def map_product(lookup, source_system, raw_product):
    key = (source_system.upper(), clean_text(raw_product).upper())
    hit = lookup.get(key)
    if hit:
        return hit
    return {
        "ServiceGroup": "Unmapped - Review",
        "ServiceGroupShort": "Unmapped",
        "ServiceTier": "Unmapped",
        "Scope": "Unknown",
        "IncludeInRanking": "No",
        "ServicePriority": "98",
    }


# --------------------------------------------------------------------------
# Fact builders
# --------------------------------------------------------------------------

def read_volume_spend_schema_a(ws, path: Path, lookup, rejects, sheet_name):
    """Monthly VnR / VnR_YTD layout: wide, with TY / LY / Diff triplets.

    Column offsets (0-based against the values_only tuple; column A is empty):
        1 Sub Number      2 Sub Name       3 Account Number  4 Account Name
        5 City            6 State          7 Product         8 WE/Mo/Qtr
        9 Volume TY      10 Volume LY     12 Gross Freight TY
       18 Gross Spend TY 21 Net Spend TY  24 Incentive TY
       30 Billed Wt TY   33 Actual Wt TY
    """
    title = title_cells(ws)
    file_year, file_month = parse_period_from_title(title)
    _, name_month = parse_period_from_filename(path)
    year = file_year or 2025
    view = view_type_from_title(title)

    records = []
    for row_no, row in enumerate(ws.iter_rows(min_row=8, values_only=True), start=8):
        if is_sentinel(row[1], row[3]):
            if clean_text(row[1]):
                rejects.add(path.name, sheet_name, row_no, "Sentinel row",
                            clean_text(row[1]))
            continue

        raw_product = clean_text(row[7])
        if not raw_product:
            rejects.add(path.name, sheet_name, row_no, "Missing product", "")
            continue

        # The period column is the authority in this layout: a YTD export
        # carries several months in one file.
        period = clean_text(row[8])
        month = int(num(period)) if period else (file_month or name_month)
        if not month or not 1 <= month <= 12:
            rejects.add(path.name, sheet_name, row_no, "Unresolvable period", period)
            continue

        svc = map_product(lookup, "VnS", raw_product)
        records.append(
            build_volume_spend_record(
                year=year, month=month,
                sub_number=row[1], sub_name=row[2],
                account_number=row[3], account_name=row[4],
                city=row[5], state=row[6], zip_code="",
                street="", raw_product=raw_product, svc=svc,
                volume=num(row[9]), gross_spend=num(row[18]),
                net_spend=num(row[21]), billed_weight=num(row[30]),
                incentive=num(row[24]),
                volume_ly=num(row[10]), net_spend_ly=num(row[22]),
                source_file=path.name, source_layout="Schema A (Monthly/YTD VnR)",
                view_type=view,
            )
        )
    return records


def read_volume_spend_schema_b(ws, path: Path, lookup, rejects, sheet_name):
    """VnS layout: narrow, single period, period only in the title block.

    Column offsets:
        1 Sub-Parent Number  2 Sub-Parent Name  3 Account Number  4 Account Name
        5 Street  6 City  7 State  8 ZIP  9 Product
       10 Volume 11 Package Billed Weight Lbs  13 Gross Spend  14 Net Spend
    """
    title = title_cells(ws)
    title_year, title_month = parse_period_from_title(title)
    name_year, name_month = parse_period_from_filename(path)
    year = title_year or name_year or 2025
    month = title_month or name_month
    view = view_type_from_title(title)

    if not month:
        rejects.add(path.name, sheet_name, 3, "Unresolvable period",
                    "No month in title block or filename")
        return []

    records = []
    for row_no, row in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
        if is_sentinel(row[1], row[3]):
            if clean_text(row[1]):
                rejects.add(path.name, sheet_name, row_no, "Sentinel row",
                            clean_text(row[1]))
            continue

        raw_product = clean_text(row[9])
        if not raw_product:
            rejects.add(path.name, sheet_name, row_no, "Missing product", "")
            continue

        svc = map_product(lookup, "VnS", raw_product)
        records.append(
            build_volume_spend_record(
                year=year, month=month,
                sub_number=row[1], sub_name=row[2],
                account_number=row[3], account_name=row[4],
                city=row[6], state=row[7], zip_code=row[8], street=row[5],
                raw_product=raw_product, svc=svc,
                volume=num(row[10]), gross_spend=num(row[13]),
                net_spend=num(row[14]), billed_weight=num(row[11]),
                incentive=num(row[13]) - num(row[14]),
                volume_ly=None, net_spend_ly=None,
                source_file=path.name, source_layout="Schema B (VnS)",
                view_type=view,
            )
        )
    return records


def build_volume_spend_record(**kw):
    volume = kw["volume"]
    net_spend = kw["net_spend"]
    is_non_service = kw["raw_product"].upper() in NON_SERVICE_PRODUCTS
    sub_number, sub_name, is_masked = sub_parent_label(kw["sub_number"], kw["sub_name"])
    return {
        "Year": kw["year"],
        "MonthNumber": kw["month"],
        "MonthName": date(kw["year"], kw["month"], 1).strftime("%b"),
        "MonthKey": kw["year"] * 100 + kw["month"],
        "Quarter": f"Q{QUARTER_OF[kw['month']]}",
        "DateKey": date(kw["year"], kw["month"], 1).isoformat(),
        "AccountKey": account_key(sub_number, kw["account_number"]),
        "SubNumber": sub_number,
        "SubName": sub_name,
        "IsMaskedSubParent": is_masked,
        "AccountNumber": clean_text(kw["account_number"]),
        "AccountName": clean_text(kw["account_name"]),
        "City": clean_text(kw["city"]),
        "State": clean_text(kw["state"]),
        "ZIP": clean_text(kw["zip_code"]),
        "RawProduct": kw["raw_product"],
        "ServiceGroup": kw["svc"]["ServiceGroup"],
        "ServiceGroupShort": kw["svc"]["ServiceGroupShort"],
        "ServiceTier": kw["svc"]["ServiceTier"],
        "Scope": kw["svc"]["Scope"],
        "IncludeInRanking": kw["svc"]["IncludeInRanking"],
        "Volume": volume,
        "GrossSpend": round(kw["gross_spend"], 2),
        "NetSpend": round(net_spend, 2),
        "Incentive": round(kw["incentive"] or 0.0, 2),
        "BilledWeightLbs": round(kw["billed_weight"], 2),
        "VolumeLY": "" if kw["volume_ly"] is None else kw["volume_ly"],
        "NetSpendLY": "" if kw["net_spend_ly"] is None else round(kw["net_spend_ly"], 2),
        # Row-level quality flags. Kept on the fact so the Data Quality page can
        # quantify what the executive visuals exclude, rather than the exclusion
        # being invisible inside a filter pane.
        "IsNonServiceRow": "Yes" if is_non_service else "No",
        "HasVolume": "Yes" if volume > 0 else "No",
        "IsSpendOnlyAdjustment": "Yes" if volume <= 0 and abs(net_spend) > 0 else "No",
        "IsNegativeSpend": "Yes" if net_spend < 0 else "No",
        "SourceFile": kw["source_file"],
        "SourceLayout": kw["source_layout"],
        "ViewType": kw["view_type"],
    }


def read_time_in_transit(ws, path: Path, lookup, rejects):
    """Time-in-Transit: packages measured and late counts by account and product.

    Column offsets:
        1 Sub-Parent Number  3 Account Number  6 City  7 State  8 ZIP
        9 Product 10 Packages Measured 11 Late by Time 12 Late by Day
       13 Total Late 14 On Time %
    """
    title = title_cells(ws)
    title_year, title_month = parse_period_from_title(title)
    name_year, name_month = parse_period_from_filename(path)
    year = title_year or name_year or 2025
    month = title_month or name_month
    view = view_type_from_title(title)
    if not month:
        rejects.add(path.name, "TnT", 3, "Unresolvable period", "")
        return []

    records = []
    for row_no, row in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
        if is_sentinel(row[1], row[3]):
            if clean_text(row[1]):
                rejects.add(path.name, "TnT", row_no, "Sentinel row", clean_text(row[1]))
            continue
        raw_product = clean_text(row[9])
        if not raw_product:
            rejects.add(path.name, "TnT", row_no, "Missing product", "")
            continue

        svc = map_product(lookup, "TnT", raw_product)
        sub_number, sub_name, is_masked = sub_parent_label(row[1], row[2])
        measured = num(row[10])
        late_time = num(row[11])
        late_day = num(row[12])
        total_late = num(row[13])
        # Trust the components over the pre-computed total, and never trust the
        # supplied On Time % - percentages cannot be averaged when aggregated.
        if total_late == 0 and (late_time or late_day):
            total_late = late_time + late_day

        records.append(
            {
                "Year": year,
                "MonthNumber": month,
                "MonthName": date(year, month, 1).strftime("%b"),
                "MonthKey": year * 100 + month,
                "Quarter": f"Q{QUARTER_OF[month]}",
                "DateKey": date(year, month, 1).isoformat(),
                "AccountKey": account_key(sub_number, row[3]),
                "SubNumber": sub_number,
                "SubName": sub_name,
                "IsMaskedSubParent": is_masked,
                "AccountNumber": clean_text(row[3]),
                "AccountName": clean_text(row[4]),
                "City": clean_text(row[6]),
                "State": clean_text(row[7]),
                "ZIP": clean_text(row[8]),
                "RawProduct": raw_product,
                "ServiceGroup": svc["ServiceGroup"],
                "ServiceGroupShort": svc["ServiceGroupShort"],
                "ServiceTier": svc["ServiceTier"],
                "Scope": svc["Scope"],
                "IncludeInRanking": svc["IncludeInRanking"],
                "PackagesMeasured": measured,
                "LateByTime": late_time,
                "LateByDay": late_day,
                "TotalLate": total_late,
                "OnTimePackages": measured - total_late,
                "SourceFile": path.name,
                "ViewType": view,
            }
        )
    return records


def read_claims(ws, path: Path, rejects):
    """Claims: account-level only. There is no product or tracking number on
    this extract, so claims cannot be attributed to a service group. Every
    downstream claim rate is therefore an account-level rate, and any
    service-level claim figure must be labelled an allocated proxy.

    Column offsets:
        1 Sub-Parent Number 3 Account Number 5 Claims Category
        6 Issued Qty 7 Issued Pkg Qty 9 Paid Qty 10 Paid Pkg Qty
       12 Registered Qty 13 Registered Pkg Qty 15 Paid Amount 16 Declared Value
    """
    title = title_cells(ws)
    title_year, title_month = parse_period_from_title(title)
    name_year, name_month = parse_period_from_filename(path)
    year = title_year or name_year or 2025
    month = title_month or name_month
    if not month:
        rejects.add(path.name, "Claims", 3, "Unresolvable period", "")
        return []

    records = []
    for row_no, row in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
        if is_sentinel(row[1], row[3]):
            if clean_text(row[1]):
                rejects.add(path.name, "Claims", row_no, "Sentinel row",
                            clean_text(row[1]))
            continue
        category = clean_text(row[5])
        if not category:
            rejects.add(path.name, "Claims", row_no, "Blank claims category", "")
            continue

        sub_number, sub_name, is_masked = sub_parent_label(row[1], row[2])
        records.append(
            {
                "Year": year,
                "MonthNumber": month,
                "MonthName": date(year, month, 1).strftime("%b"),
                "MonthKey": year * 100 + month,
                "Quarter": f"Q{QUARTER_OF[month]}",
                "DateKey": date(year, month, 1).isoformat(),
                "AccountKey": account_key(sub_number, row[3]),
                "SubNumber": sub_number,
                "SubName": sub_name,
                "IsMaskedSubParent": is_masked,
                "AccountNumber": clean_text(row[3]),
                "AccountName": clean_text(row[4]),
                "ClaimsCategory": category,
                "IsLoss": "Yes" if category.lower() == "loss" else "No",
                "IssuedClaimsQty": num(row[6]),
                "IssuedClaimsPkgQty": num(row[7]),
                "PaidClaimsQty": num(row[9]),
                "PaidClaimsPkgQty": num(row[10]),
                "RegisteredClaimsQty": num(row[12]),
                "RegisteredClaimsPkgQty": num(row[13]),
                "PaidClaimsAmount": round(num(row[15]), 2),
                "ClaimsDeclaredValue": round(num(row[16]), 2),
                "ServiceAttribution": "Not Available",
                "SourceFile": path.name,
            }
        )
    return records


def read_accessorial(ws, path: Path, lookup, rejects):
    """Accessorial: charge-level detail behind net spend. Not in the original
    build guide's model, but it is the only table that explains *why* cost per
    piece moves, so it is worth carrying.

    Column offsets:
        1 Sub-Parent Number 3 Account Number 6 City 7 State 8 ZIP 9 Product
       10 Freight Type Description 11 Base or Accessorial Charge
       12 Number of Units 13 Accessorial Spend 14 Gross Spend 15 Net Spend
    """
    title = title_cells(ws)
    title_year, title_month = parse_period_from_title(title)
    name_year, name_month = parse_period_from_filename(path)
    year = title_year or name_year or 2025
    month = title_month or name_month
    if not month:
        rejects.add(path.name, "Accessorial", 3, "Unresolvable period", "")
        return []

    records = []
    for row_no, row in enumerate(ws.iter_rows(min_row=6, values_only=True), start=6):
        if is_sentinel(row[1], row[3]):
            if clean_text(row[1]):
                rejects.add(path.name, "Accessorial", row_no, "Sentinel row",
                            clean_text(row[1]))
            continue
        charge = clean_text(row[11])
        if not charge:
            rejects.add(path.name, "Accessorial", row_no, "Blank charge type", "")
            continue

        svc = map_product(lookup, "VnS", row[9])
        sub_number, sub_name, _ = sub_parent_label(row[1], row[2])
        freight_type = clean_text(row[10])
        records.append(
            {
                "Year": year,
                "MonthNumber": month,
                "MonthName": date(year, month, 1).strftime("%b"),
                "MonthKey": year * 100 + month,
                "Quarter": f"Q{QUARTER_OF[month]}",
                "DateKey": date(year, month, 1).isoformat(),
                "AccountKey": account_key(sub_number, row[3]),
                "SubName": sub_name,
                "AccountNumber": clean_text(row[3]),
                "AccountName": clean_text(row[4]),
                "State": clean_text(row[7]),
                "RawProduct": clean_text(row[9]),
                "ServiceGroup": svc["ServiceGroup"],
                "ServiceGroupShort": svc["ServiceGroupShort"],
                "FreightTypeDescription": freight_type,
                "ChargeCategory": charge,
                "IsAccessorial": "Yes" if freight_type.upper() == "ACCESSORIAL" else "No",
                "NumberOfUnits": num(row[12]),
                "AccessorialSpend": round(num(row[13]), 2),
                "GrossSpend": round(num(row[14]), 2),
                "NetSpend": round(num(row[15]), 2),
                "SourceFile": path.name,
            }
        )
    return records


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------

def dedupe_volume_spend(records, rejects):
    """The single most dangerous trap in this source set.

    The February file is a *year-to-date* export: it contains January and
    February. The January file contains January. A naive 'Get Data > Folder'
    append therefore double-counts January - roughly a 40% overstatement of Q1
    volume and spend, with no error message.

    Rule: for each (Year, Month, Account, RawProduct) grain, keep exactly one
    row, preferring the file whose reporting period *is* that month over a YTD
    file that merely contains it. Everything dropped is written to
    DQ_ExcludedRows.csv so the suppression is auditable.
    """
    def specificity(record):
        # Lower is better. A single-period export beats a YTD export.
        return 0 if "YTD" not in record["SourceFile"].upper() else 1

    best = {}
    for record in records:
        key = (record["Year"], record["MonthNumber"], record["AccountKey"],
               record["RawProduct"])
        current = best.get(key)
        if current is None or specificity(record) < specificity(current):
            if current is not None:
                rejects.add(current["SourceFile"], "VolumeSpend", "-",
                            "Duplicate period-account-product (YTD overlap)",
                            f"{current['Year']}-{current['MonthNumber']:02d} "
                            f"{current['AccountKey']} {current['RawProduct']}")
            best[key] = record
        else:
            rejects.add(record["SourceFile"], "VolumeSpend", "-",
                        "Duplicate period-account-product (YTD overlap)",
                        f"{record['Year']}-{record['MonthNumber']:02d} "
                        f"{record['AccountKey']} {record['RawProduct']}")
    return list(best.values())


# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------

def build_dim_date(months_present, today: date):
    """Full-year calendar so that months with no activity still appear on trend
    visuals as a genuine gap rather than silently collapsing the axis."""
    if not months_present:
        months_present = {(today.year, today.month)}
    years = sorted({y for y, _ in months_present})
    loaded = set(months_present)
    rows = []
    for year in years:
        for month in range(1, 13):
            first = date(year, month, 1)
            last = date(year, month, monthrange(year, month)[1])
            is_complete = last < today
            rows.append(
                {
                    "DateKey": first.isoformat(),
                    "Year": year,
                    "MonthNumber": month,
                    "MonthName": first.strftime("%b"),
                    "MonthNameLong": first.strftime("%B"),
                    "MonthKey": year * 100 + month,
                    "MonthYearLabel": first.strftime("%b %Y"),
                    "Quarter": f"Q{QUARTER_OF[month]}",
                    "QuarterKey": year * 10 + QUARTER_OF[month],
                    "MonthEndDate": last.isoformat(),
                    "IsCompletedMonth": "Yes" if is_complete else "No",
                    "IsLoaded": "Yes" if (year, month) in loaded else "No",
                    # A month is only fit for trend comparison when it is both
                    # calendar-complete and actually present in the data.
                    "IsReportable": "Yes" if is_complete and (year, month) in loaded else "No",
                    "SortOrder": year * 100 + month,
                }
            )
    return rows


def build_dim_account(volume_rows, transit_rows, claim_rows):
    """Conformed account dimension assembled from every fact that carries
    account attributes, so a claims-only or transit-only account still resolves."""
    accounts = {}
    for source, rows in (("VolumeSpend", volume_rows), ("TimeInTransit", transit_rows),
                         ("Claims", claim_rows)):
        for row in rows:
            key = row["AccountKey"]
            entry = accounts.setdefault(
                key,
                {
                    "AccountKey": key,
                    "SubNumber": row.get("SubNumber", ""),
                    "SubName": row.get("SubName", ""),
                    "AccountNumber": row.get("AccountNumber", ""),
                    "AccountName": row.get("AccountName", ""),
                    "City": "",
                    "State": "",
                    "ZIP": "",
                    "PresentIn": set(),
                },
            )
            entry["PresentIn"].add(source)
            for field_name in ("City", "State", "ZIP"):
                if not entry[field_name] and row.get(field_name):
                    entry[field_name] = row[field_name]
            for field_name in ("SubName", "AccountName"):
                if not entry[field_name] and row.get(field_name):
                    entry[field_name] = row[field_name]

    out = []
    for entry in accounts.values():
        present = sorted(entry.pop("PresentIn"))
        entry["PresentIn"] = " + ".join(present)
        entry["HasTransitData"] = "Yes" if "TimeInTransit" in present else "No"
        entry["HasClaimsData"] = "Yes" if "Claims" in present else "No"
        entry["Region"] = us_region(entry["State"])
        out.append(entry)
    return sorted(out, key=lambda r: (r["SubName"], r["AccountName"]))


US_REGIONS = {
    "Northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "Midwest": {"IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"},
    "South": {"DE", "FL", "GA", "MD", "NC", "SC", "VA", "DC", "WV", "AL", "KY", "MS",
              "TN", "AR", "LA", "OK", "TX"},
    "West": {"AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"},
}


def us_region(state: str) -> str:
    state = (state or "").strip().upper()
    for region, members in US_REGIONS.items():
        if state in members:
            return region
    return "Unknown / International"


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def discover_sheets(path: Path):
    """Classify each worksheet by shape rather than by name. UPS changes tab
    names between months ('Monthly VnR by Product by Accou', 'VnR_YTD 2025',
    'VnS'), so name matching alone is brittle."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    classified = []
    for ws in workbook.worksheets:
        name = ws.title.strip()
        if name.lower().endswith("xml"):
            continue  # Cognos/OBIEE query definition, not data
        header6 = [clean_text(c) for c in next(ws.iter_rows(min_row=6, max_row=6,
                                                            values_only=True), ())]
        header5 = [clean_text(c) for c in next(ws.iter_rows(min_row=5, max_row=5,
                                                            values_only=True), ())]
        if "WE/Mo/Qtr" in header6:
            classified.append(("volume_spend_a", ws, name))
        elif "Packages Measured" in header5:
            classified.append(("time_in_transit", ws, name))
        elif "Claims Category" in header5:
            classified.append(("claims", ws, name))
        elif "Base or Accessorial Charge" in header5 or "Number of Units" in header5:
            classified.append(("accessorial", ws, name))
        elif "Net Spend per Piece" in header5 or "Package Billed Weight Lbs" in header5:
            classified.append(("volume_spend_b", ws, name))
        else:
            classified.append(("unknown", ws, name))
    return workbook, classified


def write_csv(path: Path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("" if not fieldnames else ",".join(fieldnames) + "\n",
                        encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(raw_dir: Path, out_dir: Path, mapping_path: Path, today: date):
    lookup, mapping_rows = load_service_mapping(mapping_path)
    rejects = Rejects()

    volume_rows, transit_rows, claim_rows, accessorial_rows = [], [], [], []
    inventory = []

    files = sorted(p for p in raw_dir.glob("*.xlsx") if not p.name.startswith("~$"))
    if not files:
        sys.exit(f"No .xlsx files found in {raw_dir}")

    for path in files:
        workbook, sheets = discover_sheets(path)
        for kind, ws, name in sheets:
            before = {
                "volume_spend_a": len(volume_rows), "volume_spend_b": len(volume_rows),
                "time_in_transit": len(transit_rows), "claims": len(claim_rows),
                "accessorial": len(accessorial_rows), "unknown": 0,
            }[kind]

            if kind == "volume_spend_a":
                volume_rows += read_volume_spend_schema_a(ws, path, lookup, rejects, name)
                after, table = len(volume_rows), "Fact_VolumeSpend"
            elif kind == "volume_spend_b":
                volume_rows += read_volume_spend_schema_b(ws, path, lookup, rejects, name)
                after, table = len(volume_rows), "Fact_VolumeSpend"
            elif kind == "time_in_transit":
                transit_rows += read_time_in_transit(ws, path, lookup, rejects)
                after, table = len(transit_rows), "Fact_TimeInTransit"
            elif kind == "claims":
                claim_rows += read_claims(ws, path, rejects)
                after, table = len(claim_rows), "Fact_Claims"
            elif kind == "accessorial":
                accessorial_rows += read_accessorial(ws, path, lookup, rejects)
                after, table = len(accessorial_rows), "Fact_Accessorial"
            else:
                rejects.add(path.name, name, "-", "Unrecognised sheet layout", "")
                continue

            title = title_cells(ws)
            year, month = parse_period_from_title(title)
            inventory.append(
                {
                    "SourceFile": path.name,
                    "Sheet": name,
                    "TargetTable": table,
                    "PeriodLabel": clean_text(title[3] if len(title) > 3 else ""),
                    "Year": year or "",
                    "Month": month or "",
                    "ViewType": view_type_from_title(title),
                    "RowsLoaded": after - before,
                    "FileSizeKB": round(path.stat().st_size / 1024, 1),
                }
            )
        workbook.close()

    loaded_before_dedupe = len(volume_rows)
    volume_rows = dedupe_volume_spend(volume_rows, rejects)
    duplicates_removed = loaded_before_dedupe - len(volume_rows)

    months_present = {(r["Year"], r["MonthNumber"]) for r in volume_rows}
    months_present |= {(r["Year"], r["MonthNumber"]) for r in transit_rows}
    months_present |= {(r["Year"], r["MonthNumber"]) for r in claim_rows}

    dim_date = build_dim_date(months_present, today)
    dim_account = build_dim_account(volume_rows, transit_rows, claim_rows)

    unmapped = {}
    for row in volume_rows:
        if row["ServiceGroup"] == "Unmapped - Review":
            unmapped.setdefault(("VnS", row["RawProduct"]), 0)
            unmapped[("VnS", row["RawProduct"])] += 1
    for row in transit_rows:
        if row["ServiceGroup"] == "Unmapped - Review":
            unmapped.setdefault(("TnT", row["RawProduct"]), 0)
            unmapped[("TnT", row["RawProduct"])] += 1
    unmapped_rows = [
        {"SourceSystem": s, "RawProduct": p, "RowCount": c}
        for (s, p), c in sorted(unmapped.items(), key=lambda kv: -kv[1])
    ]

    sort_key = lambda r: (r["Year"], r["MonthNumber"], r.get("SubName", ""),
                          r.get("AccountName", ""), r.get("RawProduct", ""))
    volume_rows.sort(key=sort_key)
    transit_rows.sort(key=sort_key)
    claim_rows.sort(key=lambda r: (r["Year"], r["MonthNumber"], r["SubName"],
                                   r["AccountName"], r["ClaimsCategory"]))
    accessorial_rows.sort(key=lambda r: (r["Year"], r["MonthNumber"], r["AccountName"],
                                         r["ChargeCategory"]))

    write_csv(out_dir / "Fact_VolumeSpend.csv", volume_rows)
    write_csv(out_dir / "Fact_TimeInTransit.csv", transit_rows)
    write_csv(out_dir / "Fact_Claims.csv", claim_rows)
    write_csv(out_dir / "Fact_Accessorial.csv", accessorial_rows)
    write_csv(out_dir / "Dim_Date.csv", dim_date)
    write_csv(out_dir / "Dim_Account.csv", dim_account)
    write_csv(out_dir / "Dim_ServiceMapping.csv", mapping_rows)
    write_csv(out_dir / "DQ_SourceInventory.csv", inventory)
    write_csv(out_dir / "DQ_ExcludedRows.csv", rejects.rows,
              ["SourceFile", "Sheet", "SourceRow", "Reason", "Detail"])
    write_csv(out_dir / "DQ_UnmappedProducts.csv", unmapped_rows,
              ["SourceSystem", "RawProduct", "RowCount"])

    manifest = {
        "generatedOn": today.isoformat(),
        "rawDirectory": str(raw_dir),
        "sourceFiles": [p.name for p in files],
        "monthsLoaded": sorted(f"{y}-{m:02d}" for y, m in months_present),
        "rowCounts": {
            "Fact_VolumeSpend": len(volume_rows),
            "Fact_TimeInTransit": len(transit_rows),
            "Fact_Claims": len(claim_rows),
            "Fact_Accessorial": len(accessorial_rows),
            "Dim_Date": len(dim_date),
            "Dim_Account": len(dim_account),
            "Dim_ServiceMapping": len(mapping_rows),
        },
        "duplicateRowsSuppressed": duplicates_removed,
        "rowsRejected": len(rejects.rows),
        "unmappedProducts": len(unmapped_rows),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                           encoding="utf-8")
    return manifest, volume_rows, transit_rows, claim_rows, accessorial_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", default="data/raw", type=Path)
    parser.add_argument("--out", default="data/processed", type=Path)
    parser.add_argument("--mapping", default="etl/service_mapping.csv", type=Path)
    parser.add_argument("--as-of", default=None,
                        help="Override today's date (YYYY-MM-DD) for completed-month logic.")
    parser.add_argument("--report", action="store_true",
                        help="Print a reconciliation summary after loading.")
    args = parser.parse_args()

    today = date.fromisoformat(args.as_of) if args.as_of else date.today()
    manifest, volume, transit, claims, accessorial = run(
        args.raw, args.out, args.mapping, today
    )

    print(json.dumps(manifest, indent=2))

    if args.report:
        print("\n--- Reconciliation ---")
        total_volume = sum(r["Volume"] for r in volume)
        total_spend = sum(r["NetSpend"] for r in volume)
        print(f"Total shipments      {total_volume:>15,.0f}")
        print(f"Total net spend      ${total_spend:>14,.2f}")
        measured = sum(r["PackagesMeasured"] for r in transit)
        late = sum(r["TotalLate"] for r in transit)
        if measured:
            print(f"Packages measured    {measured:>15,.0f}")
            print(f"On-time delivery     {1 - late / measured:>15.2%}")
        print(f"Claims rows          {len(claims):>15,}")
        print(f"Accessorial rows     {len(accessorial):>15,}")


if __name__ == "__main__":
    main()
