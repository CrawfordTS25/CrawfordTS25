"""
Build a self-contained HTML executive dashboard from the star-schema CSVs.

This is a working companion to the Power BI build, not a replacement for it. It
serves three purposes:

  1. It proves the measure definitions. Every figure it renders is computed with
     the same rules the DAX library specifies, so a discrepancy between this page
     and the .pbix is a real defect in one of them.
  2. It gives leadership something to read before the Power BI model is
     published, and something to circulate afterwards that needs no licence.
  3. It is the reference for the report spec's visual choices.

Usage:
    python dashboard/build_dashboard.py --data data/sample     --out dashboard/index.html
    python dashboard/build_dashboard.py --data data/processed  --out dashboard/live.html
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# Palette. Validated with the data-viz palette validator:
#   light surface #fcfcfb - all-pairs deutan dE 9.2, normal-vision dE 24.0
#   dark  surface #1a1a19 - all-pairs deutan dE 9.4, normal-vision dE 20.9
# Three categorical slots only. Charts here that would need more use a single
# sequential hue or emphasis instead of adding colours.
# --------------------------------------------------------------------------
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#184f95", "#0d366b"]

MIN_MEASURED = 384          # ~+/-5pp at 95% confidence on a binomial proportion
DEFAULT_THRESHOLD = 1000
DEFAULT_SHARE = 0.01

WEIGHTS = {"reliability": 0.40, "loss": 0.30, "exception": 0.20, "cost": 0.10}


# --------------------------------------------------------------------------
# Loading and metric computation
# --------------------------------------------------------------------------

def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def wilson_lower(successes, n, z=1.96):
    """Lower bound of the Wilson score interval for a binomial proportion.

    Ranking on this rather than the raw rate is what stops a 4-package service
    with a perfect record out-ranking a 48,000-package service on noise."""
    if n <= 0:
        return None
    p = successes / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denominator)


def normalise(value, low, high, higher_is_better=True):
    if value is None:
        return None
    if high == low:
        return 1.0
    scaled = (value - low) / (high - low)
    return scaled if higher_is_better else 1 - scaled


def compute(data_dir: Path):
    volume = read_csv(data_dir / "Fact_VolumeSpend.csv")
    transit = read_csv(data_dir / "Fact_TimeInTransit.csv")
    claims = read_csv(data_dir / "Fact_Claims.csv")
    accessorial = read_csv(data_dir / "Fact_Accessorial.csv")
    dim_date = read_csv(data_dir / "Dim_Date.csv")
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if not volume:
        raise SystemExit(f"No Fact_VolumeSpend.csv in {data_dir}. Run the ETL first.")

    rankable = [r for r in volume if r["IncludeInRanking"] == "Yes" and f(r["Volume"]) > 0]

    # --- headline ----------------------------------------------------------
    total_shipments = sum(f(r["Volume"]) for r in volume)
    total_net_spend = sum(f(r["NetSpend"]) for r in volume)
    total_gross_spend = sum(f(r["GrossSpend"]) for r in volume)
    rankable_shipments = sum(f(r["Volume"]) for r in rankable)
    rankable_spend = sum(f(r["NetSpend"]) for r in rankable)
    rankable_weight = sum(f(r["BilledWeightLbs"]) for r in rankable)

    measured = sum(f(r["PackagesMeasured"]) for r in transit)
    late = sum(f(r["TotalLate"]) for r in transit)
    late_day = sum(f(r["LateByDay"]) for r in transit)
    late_time = sum(f(r["LateByTime"]) for r in transit)
    otd = 1 - late / measured if measured else None

    loss_claims = sum(f(r["IssuedClaimsPkgQty"]) for r in claims if r["IsLoss"] == "Yes")
    issued_claims = sum(f(r["IssuedClaimsPkgQty"]) for r in claims)
    paid_claims = sum(f(r["PaidClaimsPkgQty"]) for r in claims)
    paid_amount = sum(f(r["PaidClaimsAmount"]) for r in claims)

    # Claims and volume months can differ; rate the claims against the volume of
    # the months claims actually cover, not against every loaded month.
    claim_months = {r["MonthKey"] for r in claims}
    volume_in_claim_months = sum(f(r["Volume"]) for r in rankable if r["MonthKey"] in claim_months)
    loss_rate_10k = loss_claims / volume_in_claim_months * 10000 if volume_in_claim_months else None
    claims_rate_10k = issued_claims / volume_in_claim_months * 10000 if volume_in_claim_months else None

    # --- monthly series ----------------------------------------------------
    order = {r["MonthKey"]: int(r["SortOrder"]) for r in dim_date} if dim_date else {}
    label = {r["MonthKey"]: r["MonthYearLabel"] for r in dim_date} if dim_date else {}

    by_month = defaultdict(lambda: {"volume": 0.0, "spend": 0.0, "weight": 0.0,
                                    "measured": 0.0, "late": 0.0,
                                    "late_day": 0.0, "late_time": 0.0,
                                    "loss": 0.0, "claims": 0.0})
    for r in volume:
        b = by_month[r["MonthKey"]]
        b["volume"] += f(r["Volume"])
        b["spend"] += f(r["NetSpend"])
        if r["IncludeInRanking"] == "Yes" and f(r["Volume"]) > 0:
            b["weight"] += f(r["BilledWeightLbs"])
    for r in transit:
        b = by_month[r["MonthKey"]]
        b["measured"] += f(r["PackagesMeasured"])
        b["late"] += f(r["TotalLate"])
        b["late_day"] += f(r["LateByDay"])
        b["late_time"] += f(r["LateByTime"])
    for r in claims:
        b = by_month[r["MonthKey"]]
        b["claims"] += f(r["IssuedClaimsPkgQty"])
        if r["IsLoss"] == "Yes":
            b["loss"] += f(r["IssuedClaimsPkgQty"])

    months = []
    for key in sorted(by_month, key=lambda k: order.get(k, k)):
        b = by_month[key]
        months.append({
            "key": key,
            "label": label.get(key, str(key)),
            "short": label.get(key, str(key)).split(" ")[0],
            "volume": b["volume"],
            "spend": b["spend"],
            "cost_per_piece": b["spend"] / b["volume"] if b["volume"] else None,
            "measured": b["measured"],
            "otd": 1 - b["late"] / b["measured"] if b["measured"] else None,
            "late_day": b["late_day"],
            "late_time": b["late_time"],
            "loss": b["loss"],
            "claims_rate": b["claims"] / b["volume"] * 10000 if b["volume"] else None,
        })

    # --- service scorecard -------------------------------------------------
    svc = defaultdict(lambda: {"volume": 0.0, "spend": 0.0, "weight": 0.0,
                               "measured": 0.0, "late": 0.0, "late_day": 0.0,
                               "late_time": 0.0, "tier": "", "scope": "",
                               "monthly_otd": defaultdict(lambda: [0.0, 0.0])})
    for r in rankable:
        s = svc[r["ServiceGroup"]]
        s["volume"] += f(r["Volume"])
        s["spend"] += f(r["NetSpend"])
        s["weight"] += f(r["BilledWeightLbs"])
        s["tier"] = r["ServiceTier"]
        s["scope"] = r["Scope"]
    for r in transit:
        if r["IncludeInRanking"] != "Yes":
            continue
        s = svc[r["ServiceGroup"]]
        s["measured"] += f(r["PackagesMeasured"])
        s["late"] += f(r["TotalLate"])
        s["late_day"] += f(r["LateByDay"])
        s["late_time"] += f(r["LateByTime"])
        bucket = s["monthly_otd"][r["MonthKey"]]
        bucket[0] += f(r["PackagesMeasured"])
        bucket[1] += f(r["TotalLate"])
        if not s["tier"]:
            s["tier"] = r["ServiceTier"]
            s["scope"] = r["Scope"]

    services = []
    for name, s in svc.items():
        share = s["volume"] / rankable_shipments if rankable_shipments else 0
        service_otd = 1 - s["late"] / s["measured"] if s["measured"] else None
        lower = wilson_lower(s["measured"] - s["late"], s["measured"]) if s["measured"] else None

        series = [1 - v[1] / v[0] for v in s["monthly_otd"].values() if v[0] > 0]
        if len(series) >= 2:
            mean = sum(series) / len(series)
            volatility = math.sqrt(sum((x - mean) ** 2 for x in series) / len(series)) * 100
        else:
            volatility = None

        qualified = (s["volume"] >= DEFAULT_THRESHOLD and share >= DEFAULT_SHARE
                     and s["measured"] >= MIN_MEASURED)
        if qualified:
            status = "Qualified"
        elif s["volume"] < DEFAULT_THRESHOLD:
            status = f"Below volume floor ({s['volume']:,.0f} of {DEFAULT_THRESHOLD:,})"
        elif share < DEFAULT_SHARE:
            status = f"Below {DEFAULT_SHARE:.1%} volume share"
        elif s["measured"] < MIN_MEASURED:
            status = f"Transit sample too small ({s['measured']:,.0f} of {MIN_MEASURED:,})"
        else:
            status = "Not ranked"

        services.append({
            "name": name,
            "short": name.replace(" / ", "/").replace("Next Day Air", "NDA")
                         .replace("2nd Day Air", "2DA").replace("International", "Intl"),
            "tier": s["tier"],
            "scope": s["scope"],
            "volume": s["volume"],
            "share": share,
            "spend": s["spend"],
            "weight": s["weight"],
            "measured": s["measured"],
            "late": s["late"],
            "late_day": s["late_day"],
            "late_time": s["late_time"],
            "otd": service_otd,
            "otd_lower": lower,
            "volatility": volatility,
            "cost_per_piece": s["spend"] / s["volume"] if s["volume"] else None,
            "cost_per_lb": s["spend"] / s["weight"] if s["weight"] else None,
            "weight_per_piece": s["weight"] / s["volume"] if s["volume"] else None,
            "qualified": qualified,
            "status": status,
        })

    # --- scoring -----------------------------------------------------------
    # Claims carry no service key, so the loss (30%) and exception (20%)
    # components cannot be computed at service grain. Their weight is
    # reallocated across the components that CAN be measured, rather than being
    # scored as zero - scoring an unmeasurable component as zero penalises every
    # service equally and silently rescales the model.
    claims_have_service_key = any(r.get("ServiceAttribution") not in (None, "", "Not Available")
                                  for r in claims)
    qualified = [s for s in services if s["qualified"]]
    if qualified:
        lowers = [s["otd_lower"] for s in qualified if s["otd_lower"] is not None]
        costs = [s["cost_per_lb"] for s in qualified if s["cost_per_lb"] is not None]
        for s in services:
            if not s["qualified"]:
                s["score"] = None
                s["components"] = {}
                continue
            comp = {
                "reliability": normalise(s["otd_lower"], min(lowers), max(lowers), True) if lowers else None,
                "cost": normalise(s["cost_per_lb"], min(costs), max(costs), False) if costs else None,
                "loss": None,
                "exception": None,
            }
            effective = sum(WEIGHTS[k] for k, v in comp.items() if v is not None)
            weighted = sum(WEIGHTS[k] * v for k, v in comp.items() if v is not None)
            s["components"] = comp
            s["score"] = weighted / effective * 100 if effective else None

    services.sort(key=lambda s: (-1 if s["qualified"] else 0,
                                 -(s["score"] or 0), -s["volume"]))
    ranked = [s for s in services if s["qualified"]]
    for index, s in enumerate(ranked, 1):
        s["rank"] = index

    effective_weights = {}
    if ranked:
        sample = ranked[0]["components"]
        total = sum(WEIGHTS[k] for k, v in sample.items() if v is not None)
        effective_weights = {k: WEIGHTS[k] / total for k, v in sample.items() if v is not None}

    # --- accounts ----------------------------------------------------------
    acct_volume = defaultdict(float)
    acct_name = {}
    for r in rankable:
        acct_volume[r["AccountKey"]] += f(r["Volume"])
        acct_name[r["AccountKey"]] = r["AccountName"]
    acct_volume_claim_months = defaultdict(float)
    for r in rankable:
        if r["MonthKey"] in claim_months:
            acct_volume_claim_months[r["AccountKey"]] += f(r["Volume"])

    acct_claims = defaultdict(lambda: {"loss": 0.0, "issued": 0.0, "paid": 0.0, "amount": 0.0})
    for r in claims:
        a = acct_claims[r["AccountKey"]]
        a["issued"] += f(r["IssuedClaimsPkgQty"])
        a["paid"] += f(r["PaidClaimsPkgQty"])
        a["amount"] += f(r["PaidClaimsAmount"])
        if r["IsLoss"] == "Yes":
            a["loss"] += f(r["IssuedClaimsPkgQty"])
        acct_name.setdefault(r["AccountKey"], r["AccountName"])

    accounts = []
    for key, c in acct_claims.items():
        vol = acct_volume_claim_months.get(key, 0)
        rate = c["loss"] / vol * 10000 if vol else None
        index = rate / loss_rate_10k if rate is not None and loss_rate_10k else None
        if c["loss"] == 0:
            flag = "No loss activity"
        elif vol < 500:
            flag = "Insufficient volume to rate"
        elif index is None:
            flag = "Not rated"
        elif index >= 3:
            flag = "Critical"
        elif index >= 2:
            flag = "Elevated"
        elif index >= 1:
            flag = "Above average"
        else:
            flag = "At or below average"
        accounts.append({
            "key": key, "name": acct_name.get(key, key),
            "volume": vol, "loss": c["loss"], "issued": c["issued"],
            "paid": c["paid"], "amount": c["amount"],
            "rate": rate, "index": index, "flag": flag,
        })
    accounts.sort(key=lambda a: -(a["index"] or 0))

    top_share = (max((a["loss"] for a in accounts), default=0) / loss_claims) if loss_claims else None

    # --- accessorial -------------------------------------------------------
    charges = defaultdict(lambda: {"spend": 0.0, "units": 0.0, "is_acc": "No"})
    for r in accessorial:
        c = charges[r["ChargeCategory"]]
        c["spend"] += f(r["NetSpend"])
        c["units"] += f(r["NumberOfUnits"])
        c["is_acc"] = r["IsAccessorial"]
    charge_rows = sorted(
        ({"name": k, **v} for k, v in charges.items()),
        key=lambda c: -c["spend"])
    accessorial_total = sum(c["spend"] for c in charge_rows)
    accessorial_only = sum(c["spend"] for c in charge_rows if c["is_acc"] == "Yes")
    address_correction = next((c for c in charge_rows if "ADDRESS CORRECTION" in c["name"]), None)

    # --- coverage / reconciliation ----------------------------------------
    volume_months = len({r["MonthKey"] for r in volume})
    transit_month_keys = {r["MonthKey"] for r in transit}
    transit_months = len(transit_month_keys)
    volume_in_transit_months = sum(f(r["Volume"]) for r in rankable
                                   if r["MonthKey"] in transit_month_keys)
    claims_months = len(claim_months)
    missing = [r["MonthYearLabel"] for r in dim_date
               if r["IsCompletedMonth"] == "Yes" and r["IsLoaded"] == "No"] if dim_date else []

    reconciliation = None
    if accessorial:
        acc_months = {r["MonthKey"] for r in accessorial}
        vol_in_acc = sum(f(r["NetSpend"]) for r in volume if r["MonthKey"] in acc_months)
        reconciliation = vol_in_acc - accessorial_total

    if transit_months == 0:
        severity, severity_label = "critical", "NO RELIABILITY DATA"
    elif transit_months < 6 or claims_months < 6:
        severity, severity_label = "warning", "PROVISIONAL"
    elif volume_months < 12:
        severity, severity_label = "serious", "PARTIAL YEAR"
    else:
        severity, severity_label = "good", "ANNUAL"

    return {
        "manifest": manifest,
        "synthetic": bool(manifest.get("SYNTHETIC")),
        "headline": {
            "total_shipments": total_shipments,
            "rankable_shipments": rankable_shipments,
            "total_net_spend": total_net_spend,
            "total_gross_spend": total_gross_spend,
            "incentive_pct": (total_gross_spend - total_net_spend) / total_gross_spend if total_gross_spend else None,
            "cost_per_piece": rankable_spend / rankable_shipments if rankable_shipments else None,
            "cost_per_lb": rankable_spend / rankable_weight if rankable_weight else None,
            "weight_per_piece": rankable_weight / rankable_shipments if rankable_shipments else None,
            "otd": otd,
            "measured": measured,
            "late": late,
            "late_day": late_day,
            "late_time": late_time,
            "day_share_of_late": late_day / late if late else None,
            "loss_claims": loss_claims,
            "issued_claims": issued_claims,
            "paid_claims": paid_claims,
            "paid_amount": paid_amount,
            "recovery_rate": paid_claims / issued_claims if issued_claims else None,
            "loss_rate_10k": loss_rate_10k,
            "claims_rate_10k": claims_rate_10k,
            "top_account_loss_share": top_share,
        },
        "months": months,
        "services": services,
        "ranked": ranked,
        "effective_weights": effective_weights,
        "claims_have_service_key": claims_have_service_key,
        "accounts": accounts,
        "charges": charge_rows,
        "accessorial_total": accessorial_total,
        "accessorial_only": accessorial_only,
        "address_correction": address_correction,
        "coverage": {
            "volume_months": volume_months,
            "transit_months": transit_months,
            "claims_months": claims_months,
            "missing": missing,
            "severity": severity,
            "severity_label": severity_label,
            "reconciliation": reconciliation,
                # Compare like with like: transit and billing do not have to cover
            # the same months, so this ratio is computed over the months transit
            # actually covers. Dividing 1 month of measured packages by 4 months
            # of billed volume would report 23% coverage and look like a defect.
            "measured_vs_billed": (measured / volume_in_transit_months
                                   if volume_in_transit_months else None),
        },
        "exclusions": {
            "adjustment_spend": sum(f(r["NetSpend"]) for r in volume if r["IncludeInRanking"] != "Yes"),
            "spend_only_rows": sum(1 for r in volume if r["IsSpendOnlyAdjustment"] == "Yes"),
            "spend_only_value": sum(f(r["NetSpend"]) for r in volume if r["IsSpendOnlyAdjustment"] == "Yes"),
            "unmapped_rows": sum(1 for r in volume if r["ServiceGroup"] == "Unmapped - Review"),
            "masked_volume": sum(f(r["Volume"]) for r in volume if r.get("IsMaskedSubParent") == "Yes"),
            "duplicates_suppressed": manifest.get("duplicateRowsSuppressed", 0),
        },
    }


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------

def fmt_int(value):
    return "—" if value is None else f"{value:,.0f}"


def fmt_money(value, decimals=0):
    if value is None:
        return "—"
    return f"${value:,.{decimals}f}"


def fmt_pct(value, decimals=1):
    return "—" if value is None else f"{value * 100:.{decimals}f}%"


def fmt_num(value, decimals=1):
    return "—" if value is None else f"{value:,.{decimals}f}"


def esc(text):
    return html.escape(str(text), quote=True)


def shorten(text, limit):
    """Truncate with an ellipsis rather than a hard cut. A mid-word clip reads as
    the real category name; an ellipsis signals that it is abbreviated."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip(" -/") + "\u2026"


def nice_ceiling(value):
    """Round an axis maximum up to a clean number so ticks read 0 / 20k / 40k
    rather than 0 / 18,432 / 36,864."""
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


def tick_label(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    if value >= 10:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# SVG chart builders
#
# Mark specs held constant across every chart, per the visual system:
#   bars      <= 24px thick, 4px rounded data-end, square at the baseline
#   lines     2px, round join and cap
#   markers   r >= 4 with a 2px surface ring so they stay legible on crossings
#   grid      hairline, solid, one step off surface, recessive
#   stacks    2px surface-coloured gap between touching segments
# Text always wears a text token, never a series colour.
# --------------------------------------------------------------------------

def svg_open(width, height, label):
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}" '
            f'preserveAspectRatio="xMidYMid meet" class="chart">')


def y_axis(x0, x1, y0, y1, maximum, ticks=4, formatter=tick_label):
    parts = []
    for i in range(ticks + 1):
        value = maximum * i / ticks
        y = y1 - (y1 - y0) * (i / ticks)
        parts.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{x0 - 8}" y="{y + 3.5:.1f}" '
                     f'text-anchor="end">{esc(formatter(value))}</text>')
    return "".join(parts)


def column_chart(rows, value_key, label_key, chart_id, title,
                 formatter=tick_label, tip_fmt=None, highlight=None):
    """Single-series columns. One hue, not the categorical set: the series here
    is not the subject, the magnitude is."""
    width, height = 640, 220
    left, right, top, bottom = 52, 12, 16, 34
    x0, x1, y0, y1 = left, width - right, top, height - bottom
    values = [r[value_key] or 0 for r in rows]
    maximum = nice_ceiling(max(values) if values else 1)
    band = (x1 - x0) / max(len(rows), 1)
    bar_w = min(24, band * 0.6)

    parts = [svg_open(width, height, title), y_axis(x0, x1, y0, y1, maximum, 4, formatter)]
    parts.append(f'<line class="baseline" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    for i, row in enumerate(rows):
        value = row[value_key] or 0
        cx = x0 + band * (i + 0.5)
        h = (y1 - y0) * (value / maximum) if maximum else 0
        y = y1 - h
        colour = "var(--emphasis)" if highlight and row[label_key] in highlight else "var(--series-1)"
        tip = tip_fmt(row) if tip_fmt else f"{row[label_key]}: {formatter(value)}"
        # 4px rounded data-end, square at the baseline: a full round-rect would
        # round the baseline corners too and detach the bar from the axis.
        r = min(4, h)
        parts.append(
            f'<g class="mark" tabindex="0" data-tip="{esc(tip)}">'
            f'<rect class="hit" x="{cx - band / 2:.1f}" y="{y0}" width="{band:.1f}" height="{y1 - y0}"/>'
            f'<path d="M{cx - bar_w / 2:.1f},{y1:.1f} L{cx - bar_w / 2:.1f},{y + r:.1f} '
            f'Q{cx - bar_w / 2:.1f},{y:.1f} {cx - bar_w / 2 + r:.1f},{y:.1f} '
            f'L{cx + bar_w / 2 - r:.1f},{y:.1f} Q{cx + bar_w / 2:.1f},{y:.1f} '
            f'{cx + bar_w / 2:.1f},{y + r:.1f} L{cx + bar_w / 2:.1f},{y1:.1f} Z" fill="{colour}"/>'
            f'</g>')
        if len(rows) <= 14:
            parts.append(f'<text class="tick" x="{cx:.1f}" y="{y1 + 16}" '
                         f'text-anchor="middle">{esc(row[label_key])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def line_chart(rows, value_key, label_key, chart_id, title, benchmark=None,
               benchmark_label="", formatter=None, y_pad=0.35):
    """Single series, so no legend box - the title names what is plotted.
    Direct-labels the endpoint and the minimum only."""
    formatter = formatter or (lambda v: f"{v * 100:.1f}%")
    width, height = 640, 220
    left, right, top, bottom = 52, 30, 22, 34
    x0, x1, y0, y1 = left, width - right, top, height - bottom

    points = [(i, r) for i, r in enumerate(rows) if r[value_key] is not None]
    if not points:
        return f'<div class="empty">No data available for this view.</div>'

    values = [r[value_key] for _, r in points]
    if benchmark is not None:
        values = values + [benchmark]
    span = (max(values) - min(values)) or 0.01
    lo = min(values) - span * y_pad
    hi = max(values) + span * y_pad
    band = (x1 - x0) / max(len(rows) - 1, 1)

    def sx(i):
        return x0 + band * i

    def sy(v):
        return y1 - (y1 - y0) * ((v - lo) / (hi - lo))

    parts = [svg_open(width, height, title)]
    for i in range(5):
        value = lo + (hi - lo) * i / 4
        y = sy(value)
        parts.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{x0 - 8}" y="{y + 3.5:.1f}" '
                     f'text-anchor="end">{esc(formatter(value))}</text>')

    if benchmark is not None:
        by = sy(benchmark)
        parts.append(f'<line class="benchmark" x1="{x0}" y1="{by:.1f}" x2="{x1}" y2="{by:.1f}"/>')
        # Anchored at the left edge, above the line: the right edge is where the
        # endpoint direct-label lives and the two would otherwise collide.
        parts.append(f'<text class="annotation" x="{x0 + 4}" y="{by - 5:.1f}">'
                     f'{esc(benchmark_label)}</text>')

    path = " ".join(f'{"M" if n == 0 else "L"}{sx(i):.1f},{sy(r[value_key]):.1f}'
                    for n, (i, r) in enumerate(points))
    parts.append(f'<path class="line" d="{path}"/>')

    worst = min(points, key=lambda p: p[1][value_key])
    last = points[-1]
    for i, row in points:
        cx, cy = sx(i), sy(row[value_key])
        parts.append(
            f'<g class="mark" tabindex="0" data-tip="{esc(row[label_key])}: '
            f'{esc(formatter(row[value_key]))}">'
            f'<circle class="hit-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="14"/>'
            f'<circle class="dot" cx="{cx:.1f}" cy="{cy:.1f}" r="4"/></g>')
    for i, row in {id(worst): worst, id(last): last}.values():
        cx, cy = sx(i), sy(row[value_key])
        anchor = "end" if i == len(rows) - 1 else "middle"
        parts.append(f'<text class="point-label" x="{cx:.1f}" y="{cy - 12:.1f}" '
                     f'text-anchor="{anchor}">{esc(formatter(row[value_key]))}</text>')

    step = max(1, len(rows) // 12)
    for i, row in enumerate(rows):
        if i % step == 0:
            parts.append(f'<text class="tick" x="{sx(i):.1f}" y="{y1 + 18}" '
                         f'text-anchor="middle">{esc(row[label_key])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart_with_interval(services, chart_id, title):
    """Horizontal bars for on-time delivery, with the Wilson lower bound drawn
    as a whisker. The whisker is the point of the chart: it shows how much of a
    high percentage is knowledge and how much is a thin sample."""
    rows = [s for s in services if s["otd"] is not None]
    rows.sort(key=lambda s: -(s["otd"] or 0))
    if not rows:
        return '<div class="empty">No Time-in-Transit data loaded.</div>'

    row_h, top, bottom = 30, 12, 30
    width = 640
    height = top + bottom + row_h * len(rows)
    left, right = 132, 58
    x0, x1 = left, width - right

    lo = min(min(s["otd_lower"] or s["otd"] for s in rows), min(s["otd"] for s in rows))
    # Snap the floor to a whole percent, then widen until the span divides into
    # four clean ticks - otherwise the axis reads 93 / 94.75 / 96.5 / 98.25.
    lo = math.floor(lo * 100) / 100
    hi = 1.0
    while round((hi - lo) * 100) % 4 != 0:
        lo = round(lo - 0.01, 4)

    def sx(v):
        return x0 + (x1 - x0) * ((v - lo) / (hi - lo))

    parts = [svg_open(width, height, title)]
    for i in range(5):
        value = lo + (hi - lo) * i / 4
        x = sx(value)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" '
                     f'y2="{height - bottom}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{height - bottom + 16}" '
                     f'text-anchor="middle">{value * 100:.0f}%</text>')

    for i, s in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        bar_h = min(16, row_h - 12)
        x_end = sx(s["otd"])
        qualified = s["qualified"]
        colour = "var(--series-1)" if qualified else "var(--muted-mark)"
        tip = (f'{s["name"]} — OTD {s["otd"]*100:.2f}%, '
               f'95% lower bound {(s["otd_lower"] or 0)*100:.2f}%, '
               f'{s["measured"]:,.0f} packages measured. {s["status"]}')
        r = min(4, max(0, x_end - x0))
        parts.append(
            f'<g class="mark" tabindex="0" data-tip="{esc(tip)}">'
            f'<rect class="hit" x="0" y="{top + row_h * i}" width="{width}" height="{row_h}"/>'
            f'<path d="M{x0},{cy - bar_h/2:.1f} L{x_end - r:.1f},{cy - bar_h/2:.1f} '
            f'Q{x_end:.1f},{cy - bar_h/2:.1f} {x_end:.1f},{cy - bar_h/2 + r:.1f} '
            f'L{x_end:.1f},{cy + bar_h/2 - r:.1f} Q{x_end:.1f},{cy + bar_h/2:.1f} '
            f'{x_end - r:.1f},{cy + bar_h/2:.1f} L{x0},{cy + bar_h/2:.1f} Z" fill="{colour}"/>')
        if s["otd_lower"] is not None:
            lx = sx(s["otd_lower"])
            parts.append(
                f'<line class="whisker" x1="{lx:.1f}" y1="{cy:.1f}" x2="{x_end:.1f}" y2="{cy:.1f}"/>'
                f'<line class="whisker-cap" x1="{lx:.1f}" y1="{cy - 5:.1f}" '
                f'x2="{lx:.1f}" y2="{cy + 5:.1f}"/>')
        parts.append(
            f'<text class="row-label" x="{x0 - 10}" y="{cy + 3.5:.1f}" '
            f'text-anchor="end">{esc(s["short"])}</text>'
            f'<text class="row-value" x="{width - right + 8}" y="{cy + 3.5:.1f}">'
            f'{s["otd"]*100:.1f}%</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def stacked_bar(rows, keys, labels, chart_id, title, formatter=tick_label):
    """Two-series stack. A 2px surface-coloured gap separates the segments -
    the gap does the separating, never a stroke around the mark."""
    width, height = 640, 220
    left, right, top, bottom = 52, 12, 16, 34
    x0, x1, y0, y1 = left, width - right, top, height - bottom
    totals = [sum(r[k] or 0 for k in keys) for r in rows]
    maximum = nice_ceiling(max(totals) if totals else 1)
    band = (x1 - x0) / max(len(rows), 1)
    bar_w = min(24, band * 0.6)
    colours = ["var(--series-1)", "var(--series-2)"]

    parts = [svg_open(width, height, title), y_axis(x0, x1, y0, y1, maximum, 4, formatter)]
    parts.append(f'<line class="baseline" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    for i, row in enumerate(rows):
        cx = x0 + band * (i + 0.5)
        cursor = y1
        for k_index, key in enumerate(keys):
            value = row[key] or 0
            if value <= 0:
                continue
            h = (y1 - y0) * (value / maximum)
            gap = 2 if k_index > 0 else 0
            y = cursor - h
            tip = f'{row["label"]} — {labels[k_index]}: {value:,.0f}'
            parts.append(
                f'<g class="mark" tabindex="0" data-tip="{esc(tip)}">'
                f'<rect x="{cx - bar_w/2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{max(0, h - gap):.1f}" fill="{colours[k_index]}" '
                f'rx="{2 if k_index == len(keys) - 1 else 0}"/></g>')
            cursor = y - gap
        if len(rows) <= 14:
            parts.append(f'<text class="tick" x="{cx:.1f}" y="{y1 + 16}" '
                         f'text-anchor="middle">{esc(row["short"])}</text>')
    parts.append("</svg>")
    legend = "".join(
        f'<span class="key"><i style="background:{colours[i]}"></i>{esc(labels[i])}</span>'
        for i in range(len(keys)))
    return f'<div class="legend">{legend}</div>' + "".join(parts)


def hbar_chart(rows, value_key, label_key, chart_id, title, formatter=fmt_money,
               emphasis_key=None, max_rows=12, tick_formatter=None, caption=None,
               label_gutter=176, value_gutter=76, label_chars=24):
    """Horizontal magnitude bars, single sequential hue. Where an `emphasis_key`
    is given, one bar carries the accent and the rest recede - the honest form
    when the story is 'this one', not 'these categories'."""
    rows = rows[:max_rows]
    if not rows:
        return '<div class="empty">No data available for this view.</div>'
    row_h, top, bottom = 26, 8, 26
    width = 640
    height = top + bottom + row_h * len(rows)
    left, right = label_gutter, value_gutter
    x0, x1 = left, width - right
    maximum = nice_ceiling(max(r[value_key] or 0 for r in rows))
    tick_formatter = tick_formatter or tick_label

    parts = [svg_open(width, height, title)]
    for i in range(5):
        value = maximum * i / 4
        x = x0 + (x1 - x0) * (i / 4)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" '
                     f'y2="{height - bottom}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{height - bottom + 16}" '
                     f'text-anchor="middle">{esc(tick_formatter(value))}</text>')

    for i, row in enumerate(rows):
        value = row[value_key] or 0
        cy = top + row_h * i + row_h / 2
        bar_h = min(14, row_h - 10)
        w = (x1 - x0) * (value / maximum) if maximum else 0
        accent = emphasis_key and row.get(emphasis_key)
        colour = "var(--emphasis)" if accent else "var(--series-1)"
        r = min(4, w)
        tip = f'{row[label_key]}: {formatter(value)}'
        parts.append(
            f'<g class="mark" tabindex="0" data-tip="{esc(tip)}">'
            f'<rect class="hit" x="0" y="{top + row_h * i}" width="{width}" height="{row_h}"/>'
            f'<path d="M{x0},{cy - bar_h/2:.1f} L{x0 + w - r:.1f},{cy - bar_h/2:.1f} '
            f'Q{x0 + w:.1f},{cy - bar_h/2:.1f} {x0 + w:.1f},{cy - bar_h/2 + r:.1f} '
            f'L{x0 + w:.1f},{cy + bar_h/2 - r:.1f} Q{x0 + w:.1f},{cy + bar_h/2:.1f} '
            f'{x0 + w - r:.1f},{cy + bar_h/2:.1f} L{x0},{cy + bar_h/2:.1f} Z" fill="{colour}"/>'
            f'<text class="row-label" x="{x0 - 10}" y="{cy + 3.5:.1f}" text-anchor="end">'
            f'{esc(shorten(str(row[label_key]), label_chars))}</text>'
            f'<text class="row-value" x="{x1 + 8}" y="{cy + 3.5:.1f}">'
            f'{esc(formatter(value))}</text></g>')
    parts.append("</svg>")
    head = f'<div class="chart-caption">{esc(caption)}</div>' if caption else ""
    return head + "".join(parts)


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:400 15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.viz-root{
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a;
  --emphasis:#eb6834; --muted-mark:#c3c2b7;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
  --good-ink:#006300;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])) .viz-root{
    --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
    --emphasis:#d95926; --muted-mark:#4a4a47;
    --good-ink:#0ca30c;
  }
}
:root[data-theme="dark"] .viz-root{
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
  --emphasis:#d95926; --muted-mark:#4a4a47;
  --good-ink:#0ca30c;
}
.wrap{max-width:1180px;margin:0 auto;padding:32px 20px 72px}

/* ---- banner ---- */
.banner{border-radius:8px;padding:12px 16px;margin-bottom:22px;font-size:13px;
  line-height:1.5;border:1px solid var(--border);background:var(--surface);
  display:flex;gap:12px;align-items:flex-start}
.banner .sev{font-weight:700;letter-spacing:.04em;font-size:11px;padding:3px 8px;
  border-radius:4px;white-space:nowrap;flex:none;margin-top:1px}
.sev.good{background:#0ca30c1f;color:var(--good-ink)}
.sev.serious{background:#ec835a2b;color:#a8471f}
.sev.warning{background:#fab2192e;color:#8a5c00}
.sev.critical{background:#d03b3b26;color:#a32020}
:root[data-theme="dark"] .sev.serious,:root[data-theme="dark"] .sev.warning{color:#f0c98a}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .sev.serious,
  :root:where(:not([data-theme="light"])) .sev.warning{color:#f0c98a}}
.synthetic{background:#fab2192e;border-color:#fab21966}

/* ---- head ---- */
header h1{font-size:26px;line-height:1.25;margin:0 0 6px;letter-spacing:-.01em}
header .sub{color:var(--ink-2);font-size:14px;margin:0 0 20px}

/* ---- stat tiles ---- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px;
  margin-bottom:28px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:14px 16px}
.tile .label{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.05em;margin-bottom:7px}
.tile .value{font-size:30px;font-weight:600;letter-spacing:-.02em;line-height:1.1}
.tile .basis{font-size:11px;color:var(--muted);margin-top:6px;line-height:1.4}

/* ---- panels ---- */
section{margin-bottom:34px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
  margin:0 0 12px;font-weight:600}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:18px 20px;margin-bottom:14px}
.panel h3{font-size:15px;margin:0 0 3px;font-weight:600}
.panel .note{font-size:12.5px;color:var(--ink-2);margin:0 0 14px;line-height:1.55}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:860px){.grid2{grid-template-columns:1fr}}

/* ---- charts ---- */
.chart{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.baseline{stroke:var(--axis);stroke-width:1}
.benchmark{stroke:var(--muted);stroke-width:1;stroke-dasharray:none;opacity:.65}
.line{fill:none;stroke:var(--series-1);stroke-width:2;stroke-linejoin:round;
  stroke-linecap:round}
.dot{fill:var(--series-1);stroke:var(--surface);stroke-width:2}
.hit,.hit-dot{fill:transparent}
.whisker{stroke:var(--surface);stroke-width:2;opacity:.9}
.whisker-cap{stroke:var(--ink-2);stroke-width:1.5}
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.tick{font-size:10px;fill:var(--muted);font-variant-numeric:tabular-nums}
.row-label{font-size:11.5px;fill:var(--ink-2)}
.row-value{font-size:11.5px;fill:var(--ink);font-variant-numeric:tabular-nums;
  font-weight:600}
.point-label{font-size:11px;fill:var(--ink);font-weight:600}
.annotation{font-size:10px;fill:var(--muted)}
.mark{cursor:default;outline:none}
.mark:hover,.mark:focus-visible{opacity:.82}
.mark:focus-visible rect,.mark:focus-visible path{outline:2px solid var(--ink);
  outline-offset:1px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px;font-size:12px;
  color:var(--ink-2)}
.legend .key{display:inline-flex;align-items:center;gap:6px}
.legend i{width:11px;height:11px;border-radius:2px;display:inline-block}
.chart-caption{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.05em;margin-bottom:6px;font-weight:600}
.empty{padding:26px;text-align:center;color:var(--muted);font-size:13px;
  border:1px dashed var(--grid);border-radius:6px}

/* ---- tables ---- */
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:640px}
th,td{text-align:right;padding:8px 10px;border-bottom:1px solid var(--grid);
  white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:150px}
th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  font-weight:600;border-bottom:1px solid var(--axis)}
td{font-variant-numeric:tabular-nums}
tbody tr.unqualified td{color:var(--muted)}
tbody tr.divider td{border-top:2px solid var(--axis);padding-top:12px}
.rank{display:inline-flex;width:20px;height:20px;border-radius:4px;font-size:11px;
  align-items:center;justify-content:center;background:var(--series-1);color:#fff;
  font-weight:700;margin-right:8px;vertical-align:middle}
.rank.none{background:var(--muted-mark);color:var(--ink-2)}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;padding:2px 8px;
  border-radius:11px;font-weight:600;white-space:nowrap}
.chip.good{background:#0ca30c1f;color:var(--good-ink)}
.chip.warn{background:#fab2192e;color:#8a5c00}
.chip.serious{background:#ec835a2b;color:#a8471f}
.chip.crit{background:#d03b3b26;color:#a32020}
.chip.mute{background:var(--grid);color:var(--ink-2)}
:root[data-theme="dark"] .chip.warn,:root[data-theme="dark"] .chip.serious{color:#f0c98a}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .chip.warn,
  :root:where(:not([data-theme="light"])) .chip.serious{color:#f0c98a}}

/* ---- callout ---- */
.callout{border-left:3px solid var(--series-1);background:var(--surface);
  padding:14px 18px;border-radius:0 8px 8px 0;margin:0 0 14px;font-size:14px;
  line-height:1.6;border-top:1px solid var(--border);
  border-right:1px solid var(--border);border-bottom:1px solid var(--border)}
.callout.warn{border-left-color:var(--warning)}
.callout.crit{border-left-color:var(--critical)}
.callout strong{font-weight:650}
.callout p{margin:0 0 9px}.callout p:last-child{margin:0}

/* ---- footnotes ---- */
.foot{font-size:12px;color:var(--muted);line-height:1.65}
.foot h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--ink-2);margin:20px 0 8px}
.foot ul{margin:0 0 10px;padding-left:18px}
.foot li{margin-bottom:5px}
.defs{display:grid;grid-template-columns:auto 1fr;gap:5px 16px;font-size:12px}
.defs dt{font-weight:600;color:var(--ink-2);white-space:nowrap}
.defs dd{margin:0;color:var(--muted)}
@media (max-width:640px){.defs{grid-template-columns:1fr}
  .defs dd{margin-bottom:8px}}

/* ---- tooltip ---- */
#tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--ink);color:var(--plane);font-size:12px;padding:6px 9px;
  border-radius:5px;max-width:290px;line-height:1.45;z-index:99}
"""

JS = """
(function(){
  var tip=document.getElementById('tip');
  function show(e,t){tip.textContent=t;tip.style.opacity='1';move(e);}
  function move(e){
    var x=(e.clientX!==undefined?e.clientX:0)+14, y=(e.clientY!==undefined?e.clientY:0)+16;
    var r=tip.getBoundingClientRect();
    if(x+r.width>window.innerWidth-8)x=window.innerWidth-r.width-8;
    if(y+r.height>window.innerHeight-8)y=y-r.height-28;
    tip.style.left=x+'px';tip.style.top=y+'px';
  }
  function hide(){tip.style.opacity='0';}
  document.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mouseenter',function(e){show(e,el.dataset.tip);});
    el.addEventListener('mousemove',move);
    el.addEventListener('mouseleave',hide);
    el.addEventListener('focus',function(e){
      var b=el.getBoundingClientRect();
      show({clientX:b.left+b.width/2,clientY:b.top},el.dataset.tip);
    });
    el.addEventListener('blur',hide);
  });
})();
"""


def tile(label, value, basis=""):
    return (f'<div class="tile"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div>'
            f'<div class="basis">{esc(basis)}</div></div>')


def chip(text, kind="mute"):
    return f'<span class="chip {kind}">{esc(text)}</span>'


def render(model, data_dir, out_path):
    h = model["headline"]
    cov = model["coverage"]
    exc = model["exclusions"]
    months = model["months"]
    services = model["services"]
    ranked = model["ranked"]

    parts = []
    A = parts.append

    A('<div class="viz-root"><div class="wrap">')

    # ---- synthetic notice ------------------------------------------------
    if model["synthetic"]:
        A('<div class="banner synthetic"><span class="sev warning">SAMPLE</span>'
          '<div><strong>Synthetic demonstration data.</strong> Account names, volumes '
          'and spend below are generated by <code>etl/make_sample_data.py</code> and '
          'correspond to no real organisation, carrier contract or shipment. '
          'Rebuild against <code>data/processed</code> for live figures.</div></div>')

    # ---- header + basis banner -------------------------------------------
    A('<header><h1>UPS 2025 Annual Shipping Performance</h1>'
      '<p class="sub">Executive overview — reliability, loss risk, cost efficiency '
      'and the resulting service recommendation.</p></header>')

    missing_txt = (f' Not yet loaded: {", ".join(cov["missing"])}.' if cov["missing"] else "")
    recon_txt = ""
    if cov["reconciliation"] is not None:
        recon_txt = (" Accessorial detail reconciles to net spend."
                     if abs(cov["reconciliation"]) < 1
                     else f' Reconciliation variance {fmt_money(cov["reconciliation"], 2)} — investigate.')
    A(f'<div class="banner"><span class="sev {cov["severity"]}">{esc(cov["severity_label"])}</span>'
      f'<div>Volume &amp; Spend <strong>{cov["volume_months"]} month(s)</strong> · '
      f'Time-in-Transit <strong>{cov["transit_months"]} month(s)</strong> · '
      f'Claims <strong>{cov["claims_months"]} month(s)</strong>.{esc(missing_txt)}'
      f'{esc(recon_txt)}</div></div>')

    # ---- KPI row ---------------------------------------------------------
    otd_basis = (f'{fmt_int(h["measured"])} packages measured · '
                 f'{cov["transit_months"]} month(s)')
    A('<section><div class="kpis">')
    A(tile("Total shipments", fmt_int(h["total_shipments"]),
           f'{cov["volume_months"]} month(s) of billing'))
    A(tile("Net spend", fmt_money(h["total_net_spend"]),
           f'{fmt_pct(h["incentive_pct"])} incentive off list'))
    A(tile("On-time delivery", fmt_pct(h["otd"], 2), otd_basis))
    A(tile("Loss claims / 10k", fmt_num(h["loss_rate_10k"], 2),
           f'{fmt_int(h["loss_claims"])} loss claims · account grain only'))
    A(tile("Net spend / shipment", fmt_money(h["cost_per_piece"], 2),
           f'{fmt_money(h["cost_per_lb"], 3)} per billed lb'))
    A('</div></section>')

    # ---- recommendation callout ------------------------------------------
    A('<section><h2>Recommendation</h2>')
    if not ranked:
        A('<div class="callout crit"><p><strong>No service qualifies for ranking.</strong> '
          'Either no Time-in-Transit data is loaded, or no service clears the volume and '
          'measurement thresholds. No service recommendation can be made.</p></div>')
    else:
        best = ranked[0]
        anchor = max(ranked, key=lambda s: s["volume"])
        premium = [s for s in ranked if s["tier"] == "Premium"]
        best_premium = max(premium, key=lambda s: s["otd_lower"] or 0) if premium else None
        firm_otd = h["otd"] or 0
        watch = [s for s in ranked if s["otd"] is not None and s["otd"] < firm_otd]

        kind = "warn" if cov["transit_months"] < 6 else ""
        A(f'<div class="callout {kind}">')
        if cov["transit_months"] < 6:
            A(f'<p><strong>Provisional — {cov["transit_months"]} month(s) of '
              f'Time-in-Transit data.</strong> Do not issue as an annual service policy '
              f'until at least six completed months are loaded.</p>')
        A(f'<p><strong>Volume anchor:</strong> {esc(anchor["name"])} carries '
          f'{fmt_pct(anchor["share"])} of ranked shipments at '
          f'{fmt_money(anchor["cost_per_lb"], 3)} per billed lb — '
          f'{fmt_num((max(s["cost_per_lb"] for s in ranked) / anchor["cost_per_lb"]) if anchor["cost_per_lb"] else None)}× '
          f'cheaper per pound than the most expensive qualified service. It remains the '
          f'default on economics; its on-time rate of {fmt_pct(anchor["otd"], 2)} is the '
          f'question to manage, not a reason to migrate volume.</p>')
        A(f'<p><strong>Highest-scoring qualified service:</strong> {esc(best["name"])} '
          f'(score {fmt_num(best["score"])}, on-time {fmt_pct(best["otd"], 2)} across '
          f'{fmt_int(best["measured"])} measured packages).</p>')
        if best_premium:
            A(f'<p><strong>Recommended premium service:</strong> {esc(best_premium["name"])} — '
              f'best 95% lower-bound on-time rate '
              f'({fmt_pct(best_premium["otd_lower"], 2)}) among qualified premium tiers.</p>')
        if watch:
            worst = min(watch, key=lambda s: s["otd"])
            A(f'<p><strong>Service to monitor:</strong> {esc(worst["name"])} — on-time '
              f'{fmt_pct(worst["otd"], 2)}, below the firm-wide '
              f'{fmt_pct(firm_otd, 2)}.</p>')
        A('</div>')

        weights = model["effective_weights"]
        if weights:
            weight_txt = ", ".join(f'{k} {v:.0%}' for k, v in weights.items())
            A(f'<div class="callout warn"><p><strong>Score basis — read before quoting '
              f'the ranking.</strong> Effective weights: {esc(weight_txt)}. '
              f'The claims export carries no service or tracking key, so the loss (30%) '
              f'and exception (20%) components specified in the framework cannot be '
              f'computed at service grain. Their weight is reallocated across the '
              f'components that can be measured rather than scored as zero. '
              f'Claims risk is assessed at account level below.</p></div>')
    A('</section>')

    # ---- service scorecard ----------------------------------------------
    A('<section><h2>Service scorecard</h2><div class="panel">')
    A(f'<h3>Qualified services ranked on the consistency score</h3>')
    A(f'<p class="note">A service qualifies at {DEFAULT_THRESHOLD:,}+ shipments, '
      f'{DEFAULT_SHARE:.0%}+ of ranked volume, and {MIN_MEASURED:,}+ measured packages — '
      f'the last is the sample size a binomial proportion needs for a ±5pp margin at 95% '
      f'confidence. Unqualified services are shown below the rule with the reason, not '
      f'hidden. Cost is given two ways because per-shipment cost alone is misleading '
      f'when package weight differs this much between services.</p>')
    A('<div class="scroll"><table><thead><tr>'
      '<th>Service</th><th>Shipments</th><th>Share</th><th>Measured</th>'
      '<th>On-time</th><th>95% lower</th><th>Late/day</th>'
      '<th>$ / shipment</th><th>lb / shipment</th><th>$ / billed lb</th>'
      '<th>Score</th></tr></thead><tbody>')
    seen_divider = False
    for s in services:
        classes = []
        if not s["qualified"]:
            classes.append("unqualified")
            if not seen_divider:
                classes.append("divider")
                seen_divider = True
        rank_html = (f'<span class="rank">{s["rank"]}</span>' if s.get("rank")
                     else '<span class="rank none">–</span>')
        status = "" if s["qualified"] else f'<br><span class="chip mute">{esc(s["status"])}</span>'
        late_day_pct = (s["late_day"] / s["measured"]) if s["measured"] else None
        A(f'<tr class="{" ".join(classes)}">'
          f'<td>{rank_html}{esc(s["name"])}{status}</td>'
          f'<td>{fmt_int(s["volume"])}</td>'
          f'<td>{fmt_pct(s["share"])}</td>'
          f'<td>{fmt_int(s["measured"])}</td>'
          f'<td>{fmt_pct(s["otd"], 2)}</td>'
          f'<td>{fmt_pct(s["otd_lower"], 2)}</td>'
          f'<td>{fmt_pct(late_day_pct, 2)}</td>'
          f'<td>{fmt_money(s["cost_per_piece"], 2)}</td>'
          f'<td>{fmt_num(s["weight_per_piece"], 1)}</td>'
          f'<td>{fmt_money(s["cost_per_lb"], 3)}</td>'
          f'<td>{fmt_num(s["score"], 1) if s["score"] is not None else "—"}</td>'
          f'</tr>')
    A('</tbody></table></div></div>')

    # ---- OTD by service with confidence interval -------------------------
    A('<div class="panel"><h3>On-time delivery by service, with 95% confidence floor</h3>'
      '<p class="note">The bar is the observed rate; the notch is the lower bound of its '
      '95% confidence interval. A wide gap between them means the rate rests on a small '
      'sample. Greyed bars did not qualify for ranking. This is why a service showing '
      '100% on-time can still be the wrong recommendation.</p>')
    A(bar_chart_with_interval(services, "otd-svc", "On-time delivery by service"))
    A('</div>')

    # ---- cost lens -------------------------------------------------------
    qualified = [s for s in services if s["qualified"]]
    if qualified:
        by_piece = sorted(qualified, key=lambda s: -(s["cost_per_piece"] or 0))
        by_lb = sorted(qualified, key=lambda s: -(s["cost_per_lb"] or 0))
        flip = [s["short"] for s in by_piece] != [s["short"] for s in by_lb]
        A('<div class="panel"><h3>Cost, two ways — and why the difference matters</h3>')
        A(f'<p class="note">Left: net spend per shipment. Right: net spend per billed '
          f'pound. {"The ranking inverts between them. " if flip else ""}'
          f'Services carry very different package weights — '
          f'{esc(by_piece[0]["short"])} averages '
          f'{fmt_num(by_piece[0]["weight_per_piece"])} lb per piece against '
          f'{fmt_num(min(qualified, key=lambda s: s["weight_per_piece"] or 0)["weight_per_piece"])} lb '
          f'for {esc(min(qualified, key=lambda s: s["weight_per_piece"] or 0)["short"])} — so '
          f'per-shipment cost compares the price of two different things. Read the right '
          f'chart before concluding that upgrading volume to a faster service is cheap. '
          f'The consistency score uses the per-pound view for exactly this reason.</p>')
        A('<div class="grid2">')
        money_tick = lambda v: f"${v:,.0f}"
        A('<div>' + hbar_chart(
            [{"label": s["short"], "v": s["cost_per_piece"]} for s in by_piece],
            "v", "label", "cpp", "Net spend per shipment",
            formatter=lambda v: fmt_money(v, 2), tick_formatter=money_tick,
            caption="Per shipment") + '</div>')
        A('<div>' + hbar_chart(
            [{"label": s["short"], "v": s["cost_per_lb"]} for s in by_lb],
            "v", "label", "cpl", "Net spend per billed pound",
            formatter=lambda v: fmt_money(v, 2), tick_formatter=money_tick,
            caption="Per billed pound") + '</div>')
        A('</div></div>')
    A('</section>')

    # ---- trend -----------------------------------------------------------
    A('<section><h2>Monthly trend</h2><div class="grid2">')
    A('<div class="panel"><h3>Shipment volume by month</h3>'
      '<p class="note">Billed volume, all services.</p>')
    A(column_chart(months, "volume", "short", "vol", "Shipment volume by month",
                   tip_fmt=lambda r: f'{r["label"]}: {r["volume"]:,.0f} shipments, '
                                     f'{fmt_money(r["spend"])} net spend'))
    A('</div>')

    otd_months = [m for m in months if m["otd"] is not None]
    A('<div class="panel"><h3>On-time delivery by month</h3>')
    if len(otd_months) < 2:
        A(f'<p class="note">Only {len(otd_months)} month(s) of Time-in-Transit data is '
          f'loaded, so there is no trend to plot. A single month cannot distinguish a '
          f'stable service from a seasonal one — this is the highest-value gap in the '
          f'data set.</p><div class="empty">Trend requires at least two months of '
          f'Time-in-Transit data.</div>')
    else:
        A('<p class="note">Dashed reference line is the period average. The question is '
          'consistency, not level.</p>')
        A(line_chart(months, "otd", "short", "otd-trend", "On-time delivery by month",
                     benchmark=h["otd"], benchmark_label="avg"))
    A('</div></div>')

    # ---- lateness severity ----------------------------------------------
    if any(m["late_day"] or m["late_time"] for m in months):
        A('<div class="panel"><h3>Lateness severity — missed day vs missed time window</h3>'
          f'<p class="note">A package that misses its committed <em>day</em> is a materially '
          f'worse client outcome than one that arrives late on the right day. '
          f'{fmt_pct(h["day_share_of_late"])} of all late packages missed the day. That split '
          f'is what turns "delivery performance" into a specific conversation with the '
          f'carrier.</p>')
        A(stacked_bar(months, ["late_day", "late_time"],
                      ["Late by day", "Late by time"], "sev",
                      "Lateness severity by month", formatter=lambda v: f"{v:,.0f}"))
        A('</div>')
    A('</section>')

    # ---- claims ----------------------------------------------------------
    accounts = model["accounts"]
    A('<section><h2>Loss and claims risk</h2>')
    A('<div class="callout crit"><p><strong>Claims cannot be attributed to a service.</strong> '
      'The claims extract carries sub-parent, account and claims category — no product, '
      'service or tracking number. Every figure in this section is therefore at '
      '<em>account</em> grain. There is deliberately no service breakdown here: a service '
      'filter applied through the account path would return "claims for accounts that used '
      'this service", which anyone reading it would take as claims caused by that service. '
      'Adding a service or tracking field to this export is the single highest-value '
      'change available to this model.</p></div>')

    A('<div class="kpis">')
    A(tile("Claims issued", fmt_int(h["issued_claims"]),
           f'{fmt_int(h["loss_claims"])} loss · {cov["claims_months"]} month(s)'))
    A(tile("Recovery rate", fmt_pct(h["recovery_rate"]),
           f'{fmt_int(h["paid_claims"])} paid of {fmt_int(h["issued_claims"])} issued'))
    A(tile("Paid claims", fmt_money(h["paid_amount"]),
           f'{fmt_money((h["paid_amount"] / h["loss_claims"]) if h["loss_claims"] else None, 2)} per loss claim'))
    A(tile("Concentration", fmt_pct(h["top_account_loss_share"]),
           "share of all loss claims in the single worst account"))
    A('</div>')

    if accounts:
        worst = accounts[0]
        if worst["index"] and worst["index"] >= 2:
            A(f'<div class="callout"><p><strong>Loss risk is concentrated, not systemic.</strong> '
              f'{esc(worst["name"])} runs a loss rate of {fmt_num(worst["rate"], 1)} per 10,000 '
              f'shipments — {fmt_num(worst["index"], 1)}× the firm-wide '
              f'{fmt_num(h["loss_rate_10k"], 1)} — on {fmt_pct(worst["volume"] / (h["rankable_shipments"] or 1))} '
              f'of ranked volume. A firm-wide claim rate describes a carrier; a concentrated '
              f'one describes a location, and a location can be fixed. This is an operational '
              f'review at that site, not a reason to change carrier or service policy.</p></div>')

        A('<div class="panel"><h3>Loss claim rate by account, indexed to the firm average</h3>'
          '<p class="note">1.0× is the firm-wide rate. The accent bar is the highest-risk '
          'account. Accounts below 500 shipments are not rated — the rate would be noise.</p>')
        rated = [a for a in accounts if a["index"] is not None and a["volume"] >= 500]
        for a in rated:
            a["is_top"] = a is rated[0] if rated else False
        A(hbar_chart(rated, "index", "name", "loss-idx",
                     "Loss claim rate index by account",
                     formatter=lambda v: f"{v:.1f}×", emphasis_key="is_top",
                     tick_formatter=lambda v: f"{v:.1f}×",
                     label_gutter=210, value_gutter=64, label_chars=28))
        A('<div class="scroll"><table><thead><tr><th>Account</th><th>Shipments</th>'
          '<th>Loss claims</th><th>All claims</th><th>Rate / 10k</th><th>vs firm</th>'
          '<th>Paid</th><th>Assessment</th></tr></thead><tbody>')
        kinds = {"Critical": "crit", "Elevated": "serious", "Above average": "warn",
                 "At or below average": "good"}
        for a in accounts:
            A(f'<tr><td>{esc(a["name"])}</td><td>{fmt_int(a["volume"])}</td>'
              f'<td>{fmt_int(a["loss"])}</td><td>{fmt_int(a["issued"])}</td>'
              f'<td>{fmt_num(a["rate"], 1)}</td>'
              f'<td>{fmt_num(a["index"], 1) + "×" if a["index"] is not None else "—"}</td>'
              f'<td>{fmt_money(a["amount"], 2)}</td>'
              f'<td>{chip(a["flag"], kinds.get(a["flag"], "mute"))}</td></tr>')
        A('</tbody></table></div></div>')
    A('</section>')

    # ---- accessorial -----------------------------------------------------
    charges = model["charges"]
    if charges:
        A('<section><h2>Cost drivers</h2><div class="panel">')
        A('<h3>What the net spend is actually made of</h3>')
        addr = model["address_correction"]
        acc_share = (model["accessorial_only"] / model["accessorial_total"]
                     if model["accessorial_total"] else None)
        note = (f'Surcharges account for {fmt_pct(acc_share)} of net spend. '
                f'This decomposition is not in the original build guide\'s data model, but '
                f'it is the only source that explains <em>why</em> cost per piece moves — '
                f'the difference between a carrier conversation and an internal process fix.')
        if addr and addr["units"]:
            note += (f' Address Correction alone is {fmt_money(addr["spend"])} across '
                     f'{fmt_int(addr["units"])} packages '
                     f'({fmt_money(addr["spend"] / addr["units"], 2)} each) — fully avoidable '
                     f'through address validation at the point of shipment, and charged per '
                     f'package.')
        A(f'<p class="note">{note}</p>')
        for c in charges:
            c["is_avoidable"] = "ADDRESS CORRECTION" in c["name"]
        A(hbar_chart(charges, "spend", "name", "charges", "Net spend by charge category",
                     formatter=lambda v: fmt_money(v), emphasis_key="is_avoidable",
                     max_rows=12, tick_formatter=lambda v: "$" + tick_label(v),
                     label_gutter=210, value_gutter=104, label_chars=28))
        A('</div></section>')

    # ---- data quality ----------------------------------------------------
    A('<section><h2>Data quality and method</h2><div class="panel foot">')
    A('<h3>Coverage</h3><ul>')
    A(f'<li>Volume &amp; Spend: <strong>{cov["volume_months"]}</strong> month(s). '
      f'Time-in-Transit: <strong>{cov["transit_months"]}</strong>. '
      f'Claims: <strong>{cov["claims_months"]}</strong>.</li>')
    if cov["missing"]:
        A(f'<li>Completed months not yet loaded: {esc(", ".join(cov["missing"]))}.</li>')
    if cov["measured_vs_billed"]:
        A(f'<li>Packages measured are <strong>{fmt_pct(cov["measured_vs_billed"])}</strong> of '
          f'ranked billed volume. Time-in-Transit is a <em>Shipper View</em> population and '
          f'Volume &amp; Spend is a <em>Payor View</em> population — a consistent gap is '
          f'expected and is not an error. The two are never used as the same denominator.</li>')
    if cov["reconciliation"] is not None:
        state = ("reconciles exactly" if abs(cov["reconciliation"]) < 1
                 else f'shows a variance of {fmt_money(cov["reconciliation"], 2)}')
        A(f'<li>Accessorial charge detail {esc(state)} against Volume &amp; Spend net spend '
          f'for the months both cover — an independent integrity check on the load.</li>')
    A('</ul>')

    A('<h3>Exclusions — every one is counted, none is silent</h3><ul>')
    if exc["duplicates_suppressed"]:
        A(f'<li><strong>{exc["duplicates_suppressed"]:,} duplicate rows suppressed.</strong> '
          f'UPS supplies some Volume &amp; Spend files as year-to-date extracts. Appending a '
          f'monthly file and a YTD file that both contain the same month double-counts it '
          f'exactly. The load keeps one row per month / account / product, preferring the '
          f'single-period file.</li>')
    A(f'<li>{fmt_money(exc["adjustment_spend"])} of net spend sits on non-service rows '
      f'(MISC / UNC billing adjustments). Excluded from every service ranking; retained in '
      f'financial totals so the dashboard agrees with the invoice.</li>')
    A(f'<li>{exc["spend_only_rows"]:,} rows carry {fmt_money(exc["spend_only_value"])} of spend '
      f'against zero shipments. Removed from per-shipment rates; retained in totals.</li>')
    if exc["masked_volume"]:
        A(f'<li>{fmt_int(exc["masked_volume"])} shipments sit under a masked "@@" sub-parent. '
          f'These carry a valid account number and real activity, so they are retained and '
          f'relabelled rather than filtered out — the obvious "@@" filter silently deletes '
          f'genuine international volume.</li>')
    if exc["unmapped_rows"]:
        A(f'<li>{exc["unmapped_rows"]:,} rows carry a product not present in the service '
          f'mapping table. Routed to a review bucket, never silently absorbed into an '
          f'existing service group.</li>')
    A('</ul>')

    A('<h3>Metric definitions</h3><dl class="defs">')
    for term, definition in [
        ("On-time delivery %", "SUM(on-time packages) ÷ SUM(packages measured). Never an average of the supplied per-row percentage — that weights a 4-package service equally with a 48,000-package one."),
        ("95% lower bound", "Wilson score interval lower bound on the true on-time rate. Ranking uses this rather than the observed rate so a thin sample cannot out-rank a proven one on noise."),
        ("Qualified", f"≥{DEFAULT_THRESHOLD:,} shipments AND ≥{DEFAULT_SHARE:.0%} of ranked volume AND ≥{MIN_MEASURED:,} measured packages."),
        ("Net spend / shipment", "Net spend ÷ shipments, both excluding adjustment and zero-volume rows. Not comparable between services of different package weight."),
        ("Net spend / billed lb", "Net spend ÷ billed weight. The weight-normalised cost view, and the one the consistency score uses."),
        ("Loss claim rate / 10k", "Loss-category issued claim packages ÷ shipments × 10,000, at account grain only."),
        ("vs firm", "That account's loss rate divided by the firm-wide loss rate. 1.0× is average."),
        ("Consistency score", "Weighted 0–100 blend of min-max normalised components across qualified services only, with unmeasurable components' weight reallocated rather than scored as zero."),
    ]:
        A(f'<dt>{esc(term)}</dt><dd>{esc(definition)}</dd>')
    A('</dl>')

    A('<h3>Known limitations</h3><ul>')
    A('<li><strong>Claims carry no service key.</strong> The 30% loss and 20% exception '
      'weights in the recommendation framework cannot be computed at service grain. '
      'Requesting a service or tracking-number field on the claims export is the highest-value '
      'change available.</li>')
    if cov["transit_months"] < 6:
        A(f'<li><strong>Reliability rests on {cov["transit_months"]} month(s) of data.</strong> '
          f'A single period cannot separate a consistently good service from one having a good '
          f'month. Treat every on-time figure as provisional until at least six completed '
          f'months are loaded.</li>')
    A('<li>Shipper View and Payor View populations differ by design; package counts and '
      'billed volume are never used as the same denominator.</li>')
    A('<li>Cost per shipment is not comparable across services without controlling for '
      'package weight. Both views are shown; the score uses the weight-normalised one.</li>')
    A('</ul>')

    src = model["manifest"].get("sourceFiles") or []
    if src:
        A('<h3>Source files</h3><ul>')
        for name in src:
            A(f'<li><code>{esc(name)}</code></li>')
        A('</ul>')

    A(f'<p style="margin-top:18px">Generated {date.today().isoformat()} from '
      f'<code>{esc(str(data_dir))}</code> by <code>dashboard/build_dashboard.py</code>. '
      f'Measure definitions mirror <code>powerbi/dax/</code>; any disagreement between this '
      f'page and the Power BI model is a defect in one of them.</p>')
    A('</div></section>')

    A('</div></div><div id="tip" role="status" aria-live="polite"></div>')

    body = "".join(parts)
    page = (f'<title>UPS 2025 Annual Shipping Performance</title>\n'
            f'<style>{CSS}</style>\n{body}\n<script>{JS}</script>\n')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/sample", type=Path)
    parser.add_argument("--out", default="dashboard/index.html", type=Path)
    parser.add_argument("--json", type=Path,
                        help="Also write the computed metrics as JSON, for testing.")
    args = parser.parse_args()

    model = compute(args.data)
    out = render(model, args.data, args.out)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(model, indent=2, default=str) + "\n", encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"Wrote {out} ({size:.1f} KB) from {args.data}")
    print(f"  months: volume {model['coverage']['volume_months']}, "
          f"transit {model['coverage']['transit_months']}, "
          f"claims {model['coverage']['claims_months']}")
    print(f"  qualified services: {len(model['ranked'])} of {len(model['services'])}")


if __name__ == "__main__":
    main()
