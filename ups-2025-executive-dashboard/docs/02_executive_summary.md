# UPS 2025 Shipping Performance — Executive Summary

**Reporting basis: PROVISIONAL.** Volume and spend cover January–April 2025.
Time-in-Transit and Claims cover **March 2025 only**. Every reliability and loss
figure below therefore rests on a single month and must not be issued as an annual
service policy. The model, measures and pages are built for the full year; the
conclusion is not final until at least six completed months of all three sources are
loaded.

---

## What the data says

The firm shipped **293,921 packages** for **$4,519,934** in net spend across the four
months loaded, at a blended **$15.05 per shipment** and a realised incentive of
**65.5%** off list. Volume is stable month to month within a normal seasonal band
(64,126 in February to 81,909 in April) and cost per shipment is remarkably flat —
$15.22, $15.51, $15.38, $15.43 — which says the rate structure is behaving and there
is no cost drift to chase.

Delivery performance in March was **96.46% on time** across 67,091 measured packages.

Two findings are strong enough to act on now. One is not the one the framework was
built to find.

---

## Finding 1 — Loss risk is concentrated in one account, not spread across UPS

This is the most actionable result in the data set.

| | Loss claims | Shipments | Loss rate / 10k | vs firm |
|---|---|---|---|---|
| **EDWARD JONES / CVS** | 28 | 12,466 | **22.5** | **4.4×** |
| All other accounts | 7 | 56,061 | 1.2 | 0.2× |
| **Firm-wide** | **35** | **68,527** | **5.1** | 1.0× |

One account — 18% of March volume — accounts for **80% of all loss claims**. Strip it
out and the firm's loss rate falls from 5.1 to 1.2 per 10,000, which is a good number
by any standard.

A firm-wide claim rate describes a carrier. A concentrated one describes a *location* —
and a location can be fixed. This is a site operations review (packaging, handling,
pickup process, address quality, dock security) at that account, not a reason to change
carrier or service policy. It would have been invisible in any UPS-wide average.

Claims recovery is also worth a look: **24 of 55 issued claims were paid (43.6%)**,
recovering $1,202. Whether that reflects claim validity or claim administration is a
separate question the data cannot answer.

---

## Finding 2 — Cost per shipment is the wrong lens, and it points the wrong way

The build guide weights "Avg Net Spend per Shipment" at 10% of the recommendation. On
this data that metric is actively misleading, and it took a weight-normalised view to
see it:

| Service | Net spend / shipment | Billed lb / shipment | **Net spend / billed lb** |
|---|---|---|---|
| Ground | $14.36 | 16.13 | **$0.89** |
| 2nd Day Air / Expedited | $14.72 | 2.27 | **$6.48** |
| Next Day Air Saver | $14.87 | 0.75 | **$19.73** |
| Next Day Air / Express | $18.12 | 1.86 | **$9.76** |

Read the first column and Ground, 2nd Day Air and Next Day Air Saver cost within
$0.51 of each other per shipment — an apparently trivial premium for a two-to-three day
improvement in transit. That reading is wrong. Ground carries **seven times the weight
per piece**, and per billed pound it is **7.3× cheaper than 2nd Day Air** and **22×
cheaper than Next Day Air Saver**.

Any recommendation to migrate Ground volume to air on the strength of the per-shipment
column would be a very expensive mistake made from a package-mix artefact. The
dashboard shows both views side by side and the scoring model uses the per-pound one.

---

## Finding 3 — Service reliability differences are real but modest

March, qualified services only (≥1,000 shipments, ≥1% of volume, ≥384 measured packages):

| Rank | Service | Shipments | Measured | On-time | 95% lower bound | Score |
|---|---|---|---|---|---|---|
| 1 | 2nd Day Air / Expedited | 27,354 | 6,432 | **98.23%** | 97.88% | 94.1 |
| 2 | Next Day Air Saver | 10,500 | 2,577 | 97.67% | 97.01% | 45.8 |
| 3 | Next Day Air / Express | 38,685 | 9,038 | 96.78% | 96.40% | 31.7 |
| 4 | Ground | 212,876 | 47,916 | 96.04% | 95.86% | 20.0 |

Not ranked: 3 Day Select (99.41% on 683 measured — below the 1% volume share floor),
2nd Day Air Early A.M., and five international services, all below the volume floor.

3 Day Select posting the highest on-time rate in the file on 683 packages is precisely
the trap the volume threshold exists to prevent. Its 95% confidence floor is 98.50%,
and one bad week would move it several points. It is not a candidate for a default
service policy on this evidence.

**The premium services are not more reliable than the expedited one.** Next Day Air —
the most expensive qualified domestic service per pound after Saver — has a *lower*
on-time rate (96.78%) than 2nd Day Air (98.23%). Paying more is buying a shorter
committed transit time, not a higher probability of hitting it.

### The lateness is a missed *day*, not a missed hour

**95.9% of all late packages (2,278 of 2,376) missed the committed day**, not merely the
committed time. That distinction matters more than the headline percentage: a package
arriving at 4pm instead of 10:30am is an inconvenience; a package arriving Thursday
instead of Wednesday is a broken commitment. This is the specific, evidenced point to
raise with the UPS account team, and it is invisible in an aggregate on-time figure.

---

## Finding 4 — There is recoverable cost in the surcharge detail

Surcharges are **12.8% of March net spend ($134,417 of $1,053,748)**. Two lines stand
out:

- **Address Correction — $10,272 across 583 packages ($17.62 each).** Every unit is a
  package that shipped to a bad address the firm supplied. This is fully avoidable
  through address validation at the point of shipment, it is charged per package, and
  at March's run rate it is roughly **$123,000 a year**.
- **SCC Audit Fee — $20,170 across 43 units.** Worth confirming with the account team
  what is driving it.

Neither appears in the Volume & Net Spend extract at all. This analysis exists only
because the March file happened to include the accessorial tab — which is why the model
now carries it as a fact table and the report has a page for it.

---

## Recommendation

Stated as what the data currently supports, with the confidence each deserves.

| Category | Recommendation | Confidence |
|---|---|---|
| **Recommended default service** | **Ground.** It carries 72% of volume at $0.89 per billed pound and delivers 96.04% on time. Nothing in this data justifies moving that volume; the economics are decisive and the reliability gap to the next option is 2.2pp. | High — economics hold regardless of transit-month coverage |
| **Recommended expedited service** | **2nd Day Air / Expedited.** Best on-time rate among qualified services (98.23%), highest consistency score, and materially cheaper per pound than either overnight option. It should be the default when Ground transit time is insufficient. | Medium — one month of transit data |
| **Recommended premium service** | **Next Day Air Saver** over Next Day Air where an end-of-day commitment is acceptable: better on-time rate (97.67% vs 96.78%) at a lower cost per shipment. Reserve Next Day Air for genuine morning-critical shipments. | Medium — one month of transit data |
| **Service requiring monitoring** | **Ground**, on reliability rather than cost. At 96.04% it is the lowest-performing qualified service and it carries 72% of volume, so it sets the firm's overall on-time rate almost single-handedly. | High |
| **Immediate operational action** | **EDWARD JONES / CVS site review.** 4.4× the firm loss rate, 80% of all loss claims. | High — independent of transit coverage |
| **Immediate cost action** | **Address validation at point of shipment.** ~$123k annualised, fully avoidable. | High |

### What this analysis cannot tell you

**Loss claim rate by service is not computable from the current data.** The claims
extract carries sub-parent, account and claims category — no product, service or
tracking number. The framework assigns 30% of the recommendation weight to loss risk
and 20% to exceptions; **neither can be allocated at service grain**. The score above
runs on the two components that can be measured, reweighted to 80% reliability / 20%
cost, and says so wherever it appears.

This is not a modelling choice that can be worked around. Distributing account-level
claims across services by volume — the obvious workaround — assumes loss risk is
uniform across services within an account, which is exactly the hypothesis the metric
would be used to test. It is circular. **Adding a service or tracking-number field to
the claims export is the single highest-value change available to this model**, and it
is item 1 on the automation backlog.

---

## What must happen before this becomes an annual recommendation

1. **Load Time-in-Transit and Claims for every month.** One month of reliability data
   cannot separate a consistently good service from one having a good month. This is
   the largest gap by a wide margin.
2. **Request a service or tracking key on the claims export.** Unlocks 50% of the
   scoring framework.
3. **Load May–December Volume & Spend.** Straightforward — the pipeline already
   handles both extract layouts.
4. **Confirm the accessorial tab ships every month.** March had it; January, February
   and April did not.
5. **Re-run and re-read.** The model, measures and pages need no changes to absorb the
   full year; only the data does.

---

## One thing that would have gone wrong

The February file is a **year-to-date** extract: it contains January *and* February. The
January file contains January. A conventional Power Query "Get Data → Folder" append of
this source folder — the approach the build guide describes and the one most analysts
would reach for — **double-counts January exactly**.

Measured against these files that is a 100% overstatement of January volume and spend,
and roughly a 40% overstatement of the loaded period, with no error, no warning, and a
total that still looks entirely plausible. The load now keeps one row per month /
account / product, preferring a single-period file over a year-to-date one, and reports
**161 suppressed duplicate rows** on the Data Quality page so the suppression is
auditable rather than invisible.

It is worth stating plainly because it is the kind of defect that survives review: every
number downstream of it is internally consistent and completely wrong.
