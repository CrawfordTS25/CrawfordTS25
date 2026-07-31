"""
Generate a SYNTHETIC sample data set with the same schema as the real UPS
extracts, so the dashboard, the DAX and the report spec can be demonstrated and
tested without publishing real carrier billing data.

Why this exists
---------------
The real extracts contain a named client's account numbers, shipping addresses
and negotiated spend. That belongs in a private folder, not in a repository. The
ETL therefore writes real output to data/processed/ (git-ignored) while this
script writes a clearly-labelled synthetic set to data/sample/ (committed).

Every figure below is generated from a seeded random process. The *shapes* are
deliberately realistic - a dominant ground service, a small number of premium
services, one account carrying disproportionate loss claims, a heavy-vs-light
weight split between ground and air - because those shapes are what the
dashboard is designed to reveal. The *values* are invented and correspond to no
real firm, carrier contract or shipment.

Usage:
    python etl/make_sample_data.py --out data/sample
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from calendar import monthrange
from datetime import date
from pathlib import Path

SEED = 20250131
BANNER = "SYNTHETIC SAMPLE DATA - NOT REAL SHIPMENT, ACCOUNT OR SPEND DATA"

# Generic business units. No resemblance to any real organisation intended.
ACCOUNTS = [
    # (SubNumber, SubName, AccountNumber, AccountName, City, State, ZIP, weight)
    ("0009100011", "Technology Operations", "TCH001", "Technology Operations - Central", "Columbus", "OH", "43004", 0.34),
    ("0009100012", "Mail Services", "MAI002", "Mail Services - Regional", "Kansas City", "MO", "64108", 0.06),
    ("0009100013", "Vendor Programs", "VEN003", "Vendor Programs - Print", "Aurora", "IL", "60502", 0.09),
    ("0009100013", "Vendor Programs", "VEN004", "Vendor Programs - Fulfilment", "Aurora", "IL", "60502", 0.07),
    ("0009100014", "Field Administration", "FLD005", "Field Administration - North", "Madison", "WI", "53703", 0.13),
    ("0009100015", "Corporate HQ", "HQX006", "Corporate HQ - Facilities", "Columbus", "OH", "43004", 0.04),
    ("0009100016", "Retail Partner Network", "RTL007", "Retail Partner Network - Stores", "Phoenix", "AZ", "85004", 0.19),
    ("0009100017", "Cash Operations", "CSH008", "Cash Operations - Processing", "Newark", "NJ", "07102", 0.07),
    ("@@", "@@", "TCO009", "Transfer Co Operations", "Whippany", "NJ", "07981", 0.01),
]

# (RawProduct, share of volume, mean billed lb/piece, mean net $/lb, base OTD)
VNS_PRODUCTS = [
    ("GROUND PKG",                    0.700, 17.0, 0.86, 0.9605),
    ("GROUND CWT",                    0.004, 30.0, 1.20, 0.9605),
    ("STANDARD GROUND",               0.012,  9.0, 1.05, 0.9605),
    ("3DS PKG",                       0.010,  3.7, 3.80, 0.9940),
    ("2DA REG / EXPEDITED PKG",       0.070,  3.1, 6.10, 0.9820),
    ("2DA REG / EXPEDITED LTR",       0.020,  0.5, 9.90, 0.9820),
    ("2DA AM PKG",                    0.004,  0.3, 12.0, 0.9790),
    ("NDA PM / EXPRESS SAVER PKG",    0.028,  1.1, 15.0, 0.9765),
    ("NDA PM / EXPRESS SAVER LTR",    0.008,  0.4, 22.0, 0.9765),
    ("NDA REG / EXPRESS PKG",         0.055,  3.0, 9.20, 0.9680),
    ("NDA REG / EXPRESS LTR",         0.078,  0.4, 21.0, 0.9680),
    ("NDA AM / EXPRESS PLUS PKG",     0.0006, 2.0, 42.0, 0.9900),
    ("WW EXPRESS REG PKG",            0.0007, 9.0, 14.0, 0.9510),
    ("WW EXPRESS PM / SAVER PKG",     0.0005, 8.0, 13.0, 0.9800),
    ("WW EXPEDITED / 2DA PKG",        0.0002, 7.0, 12.0, 0.9700),
    ("MISC / UNC",                    0.0000, 0.0, 0.00, 0.0000),
]

VNS_TO_TNT = {
    "GROUND PKG": "GROUND", "GROUND CWT": "GROUND", "STANDARD GROUND": "GROUND",
    "3DS PKG": "THREE DAY SELECT",
    "2DA REG / EXPEDITED PKG": "SECOND DAY AIR", "2DA REG / EXPEDITED LTR": "SECOND DAY AIR",
    "2DA AM PKG": "SECOND DAY EARLY AM",
    "NDA PM / EXPRESS SAVER PKG": "NEXT DAY AIR SAVER",
    "NDA PM / EXPRESS SAVER LTR": "NEXT DAY AIR SAVER",
    "NDA REG / EXPRESS PKG": "NEXT DAY AIR", "NDA REG / EXPRESS LTR": "NEXT DAY AIR",
    "NDA AM / EXPRESS PLUS PKG": "UPS EXPRESS EARLY",
    "WW EXPRESS REG PKG": "INTERNATIONAL EXPRESS",
    "WW EXPRESS PM / SAVER PKG": "INTERNATIONAL EXPRESS SAVER",
    "WW EXPEDITED / 2DA PKG": "INTERNATIONAL EXPEDITED",
}

# Seasonal multipliers on monthly volume.
SEASONALITY = {1: 1.06, 2: 0.86, 3: 0.92, 4: 1.09, 5: 1.02, 6: 0.97,
               7: 0.94, 8: 1.00, 9: 1.03, 10: 1.08, 11: 1.14, 12: 0.89}

# One account carries disproportionate loss risk, and one month degrades on
# ground service. Both are planted so the dashboard has something true to find.
HIGH_LOSS_ACCOUNT = "RTL007"
DEGRADED_MONTH = 11

CLAIM_CATEGORIES = [("Loss", 0.60), ("Damage", 0.28), ("Follow-up", 0.09), ("Casualty", 0.03)]

ACCESSORIAL_CHARGES = [
    ("BASE (FREIGHT) CHARGES", "BASE (FREIGHT) CHARGE", 0.872, 0.42),
    ("FUEL SURCHARGE", "ACCESSORIAL", 0.088, 1.00),
    ("SCC AUDIT FEE", "ACCESSORIAL", 0.019, 0.0006),
    ("ADDRESS CORRECTION", "ACCESSORIAL", 0.010, 0.0072),
    ("COMMERCIAL SIGNATURE REQUIRED", "ACCESSORIAL", 0.0019, 0.0034),
    ("FIRST WEEKEND DAY-SATURDAY-DELIVERY", "ACCESSORIAL", 0.0013, 0.0021),
    ("DECLARED VALUE", "ACCESSORIAL", 0.0010, 0.0003),
    ("DELIVERY AREA SURCHARGE", "ACCESSORIAL", 0.0026, 0.0090),
    ("RESIDENTIAL SURCHARGE", "ACCESSORIAL", 0.0021, 0.0061),
    ("ADDITIONAL HANDLING", "ACCESSORIAL", 0.0011, 0.0008),
]

QUARTER_OF = {m: (m - 1) // 3 + 1 for m in range(1, 13)}


def load_mapping(path: Path):
    lookup = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            lookup[(row["SourceSystem"].upper(), row["RawProduct"].upper())] = row
    return lookup


def jitter(rng, value, spread=0.10):
    return value * (1 + rng.uniform(-spread, spread))


def month_fields(year, month):
    first = date(year, month, 1)
    return {
        "Year": year,
        "MonthNumber": month,
        "MonthName": first.strftime("%b"),
        "MonthKey": year * 100 + month,
        "Quarter": f"Q{QUARTER_OF[month]}",
        "DateKey": first.isoformat(),
    }


def generate(out_dir: Path, mapping_path: Path, year: int, months: int, base_volume: int):
    rng = random.Random(SEED)
    lookup = load_mapping(mapping_path)

    volume_rows, transit_rows, claim_rows, accessorial_rows = [], [], [], []

    for month in range(1, months + 1):
        mf = month_fields(year, month)
        month_volume = base_volume * SEASONALITY[month]

        # ---- Volume & Spend -------------------------------------------------
        transit_acc = {}
        for sub_no, sub_name, acct_no, acct_name, city, state, zip_code, acct_share in ACCOUNTS:
            for raw_product, prod_share, lb_per_pc, dollars_per_lb, base_otd in VNS_PRODUCTS:
                if raw_product == "MISC / UNC":
                    continue
                expected = month_volume * acct_share * prod_share
                if expected < 0.4:
                    continue
                volume = max(0, int(jitter(rng, expected, 0.22)))
                if volume == 0:
                    continue

                weight = round(volume * jitter(rng, lb_per_pc, 0.18), 1)
                net_spend = round(weight * jitter(rng, dollars_per_lb, 0.12), 2)
                gross_spend = round(net_spend / jitter(rng, 0.34, 0.10), 2)
                svc = lookup[("VNS", raw_product)]

                volume_rows.append({
                    **mf,
                    "AccountKey": f"{sub_no}|{acct_no}",
                    "SubNumber": sub_no,
                    "SubName": "Unassigned Sub-Parent" if sub_name == "@@" else sub_name,
                    "IsMaskedSubParent": "Yes" if sub_name == "@@" else "No",
                    "AccountNumber": acct_no, "AccountName": acct_name,
                    "City": city, "State": state, "ZIP": zip_code,
                    "RawProduct": raw_product,
                    "ServiceGroup": svc["ServiceGroup"],
                    "ServiceGroupShort": svc["ServiceGroupShort"],
                    "ServiceTier": svc["ServiceTier"],
                    "Scope": svc["Scope"],
                    "IncludeInRanking": svc["IncludeInRanking"],
                    "Volume": volume,
                    "GrossSpend": gross_spend,
                    "NetSpend": net_spend,
                    "Incentive": round(gross_spend - net_spend, 2),
                    "BilledWeightLbs": weight,
                    "VolumeLY": "", "NetSpendLY": "",
                    "IsNonServiceRow": "No",
                    "HasVolume": "Yes",
                    "IsSpendOnlyAdjustment": "No",
                    "IsNegativeSpend": "No",
                    "SourceFile": f"SAMPLE_{year}_{month:02d}_VolumeSpend.xlsx",
                    "SourceLayout": "Synthetic",
                    "ViewType": "Payor View",
                })

                # Roll up to the Time-in-Transit grain, which uses a different
                # product vocabulary - the same bridge the real data needs.
                tnt_product = VNS_TO_TNT[raw_product]
                key = (sub_no, acct_no, tnt_product)
                otd = base_otd
                if month == DEGRADED_MONTH and tnt_product == "GROUND":
                    otd -= 0.021          # planted seasonal degradation
                bucket = transit_acc.setdefault(key, {
                    "sub_no": sub_no, "sub_name": sub_name, "acct_no": acct_no,
                    "acct_name": acct_name, "city": city, "state": state,
                    "zip": zip_code, "product": tnt_product,
                    "measured": 0, "late": 0.0, "otd": otd})
                # Shipper View measures slightly fewer packages than the Payor
                # View bills - the real extracts behave the same way.
                measured = int(volume * jitter(rng, 0.978, 0.015))
                bucket["measured"] += measured
                bucket["late"] += measured * (1 - jitter(rng, otd, 0.004))

            # Adjustment row: spend with no shipments behind it.
            adj = round(jitter(rng, 12000 * acct_share, 0.5), 2)
            if adj > 20:
                svc = lookup[("VNS", "MISC / UNC")]
                volume_rows.append({
                    **mf,
                    "AccountKey": f"{sub_no}|{acct_no}",
                    "SubNumber": sub_no,
                    "SubName": "Unassigned Sub-Parent" if sub_name == "@@" else sub_name,
                    "IsMaskedSubParent": "Yes" if sub_name == "@@" else "No",
                    "AccountNumber": acct_no, "AccountName": acct_name,
                    "City": city, "State": state, "ZIP": zip_code,
                    "RawProduct": "MISC / UNC",
                    "ServiceGroup": svc["ServiceGroup"],
                    "ServiceGroupShort": svc["ServiceGroupShort"],
                    "ServiceTier": svc["ServiceTier"],
                    "Scope": svc["Scope"],
                    "IncludeInRanking": svc["IncludeInRanking"],
                    "Volume": 0, "GrossSpend": adj, "NetSpend": adj,
                    "Incentive": 0.0, "BilledWeightLbs": 0.0,
                    "VolumeLY": "", "NetSpendLY": "",
                    "IsNonServiceRow": "Yes", "HasVolume": "No",
                    "IsSpendOnlyAdjustment": "Yes", "IsNegativeSpend": "No",
                    "SourceFile": f"SAMPLE_{year}_{month:02d}_VolumeSpend.xlsx",
                    "SourceLayout": "Synthetic", "ViewType": "Payor View",
                })

        # ---- Time in Transit ------------------------------------------------
        for bucket in transit_acc.values():
            measured = bucket["measured"]
            if measured == 0:
                continue
            total_late = int(round(bucket["late"]))
            # Most lateness is a missed calendar day rather than a missed time
            # window - the split that makes the metric actionable.
            late_time = int(total_late * rng.uniform(0.0, 0.12))
            late_day = total_late - late_time
            svc = lookup[("TNT", bucket["product"])]
            transit_rows.append({
                **mf,
                "AccountKey": f"{bucket['sub_no']}|{bucket['acct_no']}",
                "SubNumber": bucket["sub_no"],
                "SubName": "Unassigned Sub-Parent" if bucket["sub_name"] == "@@" else bucket["sub_name"],
                "IsMaskedSubParent": "Yes" if bucket["sub_name"] == "@@" else "No",
                "AccountNumber": bucket["acct_no"], "AccountName": bucket["acct_name"],
                "City": bucket["city"], "State": bucket["state"], "ZIP": bucket["zip"],
                "RawProduct": bucket["product"],
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
                "SourceFile": f"SAMPLE_{year}_{month:02d}_TnT.xlsx",
                "ViewType": "Shipper View",
            })

        # ---- Claims (account grain only - no service key, as in the real data)
        month_account_volume = {}
        for row in volume_rows:
            if row["MonthNumber"] == month and row["Volume"] > 0:
                month_account_volume[row["AccountKey"]] = \
                    month_account_volume.get(row["AccountKey"], 0) + row["Volume"]

        for sub_no, sub_name, acct_no, acct_name, *_ in ACCOUNTS:
            key = f"{sub_no}|{acct_no}"
            acct_volume = month_account_volume.get(key, 0)
            if acct_volume < 50:
                continue
            base_rate = 0.00055 if acct_no != HIGH_LOSS_ACCOUNT else 0.00240
            for category, share in CLAIM_CATEGORIES:
                expected = acct_volume * base_rate * (share / 0.60)
                issued = max(0, int(jitter(rng, expected, 0.55) + rng.random()))
                if issued == 0:
                    continue
                paid = int(issued * rng.uniform(0.30, 0.62))
                paid_amount = round(paid * rng.uniform(28, 180), 2)
                claim_rows.append({
                    **mf,
                    "AccountKey": key,
                    "SubNumber": sub_no,
                    "SubName": "Unassigned Sub-Parent" if sub_name == "@@" else sub_name,
                    "IsMaskedSubParent": "Yes" if sub_name == "@@" else "No",
                    "AccountNumber": acct_no, "AccountName": acct_name,
                    "ClaimsCategory": category,
                    "IsLoss": "Yes" if category == "Loss" else "No",
                    "IssuedClaimsQty": issued,
                    "IssuedClaimsPkgQty": issued,
                    "PaidClaimsQty": paid,
                    "PaidClaimsPkgQty": paid,
                    "RegisteredClaimsQty": 0,
                    "RegisteredClaimsPkgQty": 0,
                    "PaidClaimsAmount": paid_amount,
                    "ClaimsDeclaredValue": round(paid_amount * rng.uniform(0.4, 1.1), 2),
                    "ServiceAttribution": "Not Available",
                    "SourceFile": f"SAMPLE_{year}_{month:02d}_Claims.xlsx",
                })

        # ---- Accessorial ----------------------------------------------------
        # Must sum to exactly the month's net spend so the reconciliation check
        # on the Data Quality page passes, as it does against the real files.
        month_spend = sum(r["NetSpend"] for r in volume_rows if r["MonthNumber"] == month)
        allocated = 0.0
        for idx, (charge, freight_type, spend_share, unit_share) in enumerate(ACCESSORIAL_CHARGES):
            is_last = idx == len(ACCESSORIAL_CHARGES) - 1
            spend = round(month_spend - allocated, 2) if is_last \
                else round(month_spend * spend_share, 2)
            allocated += spend
            accessorial_rows.append({
                **mf,
                "AccountKey": "ALL", "SubName": "All business units",
                "AccountNumber": "ALL", "AccountName": "All accounts", "State": "",
                "RawProduct": "ALL", "ServiceGroup": "All services",
                "ServiceGroupShort": "All",
                "FreightTypeDescription": freight_type,
                "ChargeCategory": charge,
                "IsAccessorial": "Yes" if freight_type == "ACCESSORIAL" else "No",
                "NumberOfUnits": int(month_volume * unit_share),
                "AccessorialSpend": spend if freight_type == "ACCESSORIAL" else 0.0,
                "GrossSpend": round(spend * 2.6, 2),
                "NetSpend": spend,
                "SourceFile": f"SAMPLE_{year}_{month:02d}_Accessorial.xlsx",
            })

    # ---- Dimensions --------------------------------------------------------
    today = date(year, months + 1, 1) if months < 12 else date(year + 1, 1, 1)
    dim_date = []
    loaded = {r["MonthNumber"] for r in volume_rows}
    for month in range(1, 13):
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
        complete = last < today
        dim_date.append({
            "DateKey": first.isoformat(), "Year": year, "MonthNumber": month,
            "MonthName": first.strftime("%b"), "MonthNameLong": first.strftime("%B"),
            "MonthKey": year * 100 + month, "MonthYearLabel": first.strftime("%b %Y"),
            "Quarter": f"Q{QUARTER_OF[month]}", "QuarterKey": year * 10 + QUARTER_OF[month],
            "MonthEndDate": last.isoformat(),
            "IsCompletedMonth": "Yes" if complete else "No",
            "IsLoaded": "Yes" if month in loaded else "No",
            "IsReportable": "Yes" if complete and month in loaded else "No",
            "SortOrder": year * 100 + month,
        })

    regions = {"OH": "Midwest", "MO": "Midwest", "IL": "Midwest", "WI": "Midwest",
               "AZ": "West", "NJ": "Northeast"}
    dim_account = [{
        "AccountKey": f"{s}|{a}",
        "SubNumber": s,
        "SubName": "Unassigned Sub-Parent" if sn == "@@" else sn,
        "AccountNumber": a, "AccountName": an, "City": c, "State": st, "ZIP": z,
        "PresentIn": "VolumeSpend + TimeInTransit + Claims",
        "HasTransitData": "Yes", "HasClaimsData": "Yes",
        "Region": regions.get(st, "Unknown / International"),
    } for s, sn, a, an, c, st, z, _ in ACCOUNTS]

    with mapping_path.open(newline="", encoding="utf-8-sig") as handle:
        mapping_rows = list(csv.DictReader(handle))

    # ---- Write -------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)

    def write(name, rows):
        path = out_dir / name
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write("Fact_VolumeSpend.csv", volume_rows)
    write("Fact_TimeInTransit.csv", transit_rows)
    write("Fact_Claims.csv", claim_rows)
    write("Fact_Accessorial.csv", accessorial_rows)
    write("Dim_Date.csv", dim_date)
    write("Dim_Account.csv", dim_account)
    write("Dim_ServiceMapping.csv", mapping_rows)

    manifest = {
        "SYNTHETIC": True,
        "notice": BANNER,
        "generatedBy": "etl/make_sample_data.py",
        "seed": SEED,
        "generatedOn": date.today().isoformat(),
        "monthsLoaded": [f"{year}-{m:02d}" for m in sorted(loaded)],
        "rowCounts": {
            "Fact_VolumeSpend": len(volume_rows),
            "Fact_TimeInTransit": len(transit_rows),
            "Fact_Claims": len(claim_rows),
            "Fact_Accessorial": len(accessorial_rows),
            "Dim_Date": len(dim_date),
            "Dim_Account": len(dim_account),
            "Dim_ServiceMapping": len(mapping_rows),
        },
        "plantedSignals": {
            "highLossAccount": HIGH_LOSS_ACCOUNT,
            "degradedGroundMonth": DEGRADED_MONTH,
            "note": "Planted so the dashboard has something real to surface in the demo.",
        },
        "duplicateRowsSuppressed": 0,
        "rowsRejected": 0,
        "unmappedProducts": 0,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "README.txt").write_text(
        BANNER + "\n\n"
        "Generated by etl/make_sample_data.py with a fixed seed.\n"
        "Account names, numbers, addresses, volumes and spend are invented and\n"
        "correspond to no real organisation, carrier contract or shipment.\n\n"
        "The schema matches data/processed/ exactly, so the dashboard, the DAX\n"
        "measures and the report spec can be exercised end to end without\n"
        "publishing real carrier billing data.\n",
        encoding="utf-8")

    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/sample", type=Path)
    parser.add_argument("--mapping", default="etl/service_mapping.csv", type=Path)
    parser.add_argument("--year", default=2025, type=int)
    parser.add_argument("--months", default=12, type=int)
    parser.add_argument("--base-volume", default=74000, type=int)
    args = parser.parse_args()

    manifest = generate(args.out, args.mapping, args.year, args.months, args.base_volume)
    print(BANNER)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
