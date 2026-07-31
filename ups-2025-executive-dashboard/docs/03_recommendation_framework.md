# Service recommendation framework

The build guide gives the weights. This document gives the arithmetic, the
qualification rules, and the reasoning behind both — the parts that determine whether
the ranking is defensible in a review.

---

## 1. Why weights alone are not a score

The framework specifies:

| Metric | Weight |
|---|---|
| On-Time Delivery % | 40% |
| Loss Claim Rate | 30% |
| Exception / Claims Rate | 20% |
| Avg Net Spend per Shipment | 10% |

Those four numbers are in four different units — a percentage, two rates per 10,000,
and a dollar amount — and three of them are "higher is better" while cost is "lower is
better". `0.4 × 96.04 + 0.3 × 5.1 + 0.2 × 8.0 + 0.1 × 14.36` is arithmetic, but it is
not a score: the on-time term dominates purely because percentages are numerically
larger than rates, and lowering cost would *reduce* the total.

Four things have to be specified before the weights mean anything.

---

## 2. Qualification — who is eligible to be ranked

Three gates. All must pass.

| Gate | Default | Why |
|---|---|---|
| Absolute volume | ≥ 1,000 shipments | Protects against a marginal service in a large firm |
| Relative share | ≥ 1% of ranked volume | Keeps the threshold meaningful as the firm grows |
| Measured sample | ≥ 384 measured packages | A binomial proportion needs ~384 observations for a ±5pp margin at 95% confidence. Below that, an on-time figure cannot separate services two points apart |

The third gate is the one the build guide does not have, and it is the one that does
the real work. Volume thresholds ask "is this service big enough to matter?" The
measurement gate asks the different and more important question: **"is this on-time
number precise enough to rank on?"** A service can clear a volume floor on billed
shipments while having almost no transit coverage.

Both numeric thresholds are What-If parameters. Exposing them turns the most
contestable assumption in the model into something leadership can move in the room and
watch respond — a far stronger defence than a footnote.

### Worked example, from the real March data

| Service | Shipments | Share | Measured | Result |
|---|---|---|---|---|
| Ground | 212,876 | 72.4% | 47,916 | Qualified |
| Next Day Air / Express | 38,685 | 13.2% | 9,038 | Qualified |
| 2nd Day Air / Expedited | 27,354 | 9.3% | 6,432 | Qualified |
| Next Day Air Saver | 10,500 | 3.6% | 2,577 | Qualified |
| **3 Day Select** | 2,704 | **0.9%** | 683 | **Not ranked** — below 1% share |
| Next Day Air Early | 20 | 0.0% | 4 | Not ranked |

3 Day Select posts the highest on-time rate in the file — 99.41%. It clears the
absolute volume gate. It fails on share, and rightly: 683 measured packages is a
95% confidence interval floor of 98.50%, and a single bad week would move it several
points. Recommending it as a default service on that evidence would be exactly the
error the framework's volume-threshold section warns about.

Next Day Air Early illustrates the point at its limit: 4 measured packages, 0 late,
100.00% on time — and a confidence floor of **51.01%**. The true rate could plausibly
be a coin flip.

---

## 3. Normalisation — putting four units on one scale

Min-max scaling to 0–1 **across the qualified set only**, with direction applied per
metric:

```
higher-is-better:   score = (value − min) / (max − min)
lower-is-better:    score = 1 − (value − min) / (max − min)
```

Two consequences worth understanding before quoting a score:

- **Scores are relative, not absolute.** The best qualified service always scores 1.0
  on a component and the worst always 0.0. A score of 20 does not mean "bad" — it means
  "last among those that qualified". Filtering the service list changes every score.
- **With one qualified service, every component returns 1.0.** A single service is
  trivially both best and worst. The recommendation label handles this by reporting
  "single qualified service — no comparison possible" rather than presenting a
  meaningless 100.

### Ranking on the confidence floor, not the observed rate

The reliability component uses the **Wilson score interval lower bound** rather than
the raw on-time percentage:

```
        p + z²/2n − z·√( p(1−p)/n + z²/4n² )
LB  =   ────────────────────────────────────        z = 1.96
                    1 + z²/n
```

This makes small samples fall down the ranking automatically, in proportion to how
little is actually known about them, rather than at a cliff edge. The volume threshold
decides *eligibility*; the confidence floor decides *order*. Using both is what stops
the ranking from being an artefact of sample size.

---

## 4. Weight reallocation — the part that matters most here

**A component that cannot be measured must not be scored as zero.**

Scoring an unmeasurable component as zero penalises every service by the same amount,
which changes no ranking but silently rescales the whole model — a service that should
score 94 reports 47, and nobody can tell whether that is a bad service or a missing
input.

Instead, the weight of any component that returns blank is redistributed across the
components that returned values:

```
score = Σ(wᵢ × scoreᵢ) / Σ(wᵢ)      over components where scoreᵢ is not blank
```

On the current data the claims export carries no service key, so both claims components
are blank at service grain and the effective weights become:

| Component | Specified | Effective today |
|---|---|---|
| Reliability | 40% | **80%** |
| Loss risk | 30% | *unavailable* |
| Exception risk | 20% | *unavailable* |
| Cost (weight-normalised) | 10% | **20%** |

The `[Score Basis]` measure prints this on the same screen as the score. A score whose
composition changed must say so where it is read, not in an appendix.

The day a service or tracking key appears on the claims export, the claims measures
start returning values, the reallocation unwinds itself, and the score reverts to the
specified 40/30/20/10 with no code change.

---

## 5. Cost must be weight-normalised

The framework says "Avg Net Spend per Shipment". **Do not score on it.**

| Service | $ / shipment | lb / shipment | $ / billed lb |
|---|---|---|---|
| Ground | $14.36 | 16.13 | $0.89 |
| 2nd Day Air | $14.72 | 2.27 | $6.48 |
| Next Day Air Saver | $14.87 | 0.75 | $19.73 |

Per shipment, those three services sit within $0.51 of one another and cost looks
almost irrelevant to service choice. Per pound, Ground is 7.3× cheaper than 2nd Day Air
and 22× cheaper than Saver. The per-shipment view is comparing the price of a 16 lb
package with the price of a 0.75 lb envelope and calling the difference a rate premium.

A score built on cost per shipment would rate air service as nearly free relative to
Ground and could be used to justify a service migration costing an order of magnitude
more than the analysis implied. The score uses `[Avg Net Spend per Billed Lb]`. Both
views appear on the report, adjacent, with the reason stated on the visual.

Where a like-for-like per-shipment comparison is genuinely wanted, filter to a single
**Weight Band** — inside one band the mix effect disappears and cost per shipment
becomes meaningful again.

---

## 6. Recommendation categories

| Category | Definition |
|---|---|
| **Recommended default service** | The service carrying ≥50% of ranked volume, unless its reliability is below the firm average — in which case it is labelled a *volume anchor requiring monitoring*. Failing that, the highest-scoring non-premium qualified service |
| **Recommended premium service** | Highest confidence-floor on-time rate among qualified Premium-tier services |
| **Best overall performer** | Rank 1 on the consistency score |
| **Best on-time performer** | Highest observed on-time rate among qualified services |
| **Most reliable** | Lowest loss and exception rates — *unavailable at service grain today* |
| **Service to monitor** | On-time rate below firm average, or month-to-month volatility above 1.5pp |

### Why the volume anchor is treated separately

A pure score ranking on the current data puts 2nd Day Air first and Ground last, which
reads as "stop using Ground". That would be a serious misreading. Ground carries 72% of
volume at a seventh the cost per pound; its position at the bottom of the ranking
reflects a 2.2pp reliability gap and a deliberately weight-normalised cost view, not a
case for migration.

The framework therefore separates **"which service performs best"** from **"which
service should we default to"**. They are different questions, and on this data they
have different answers. A service carrying the majority of volume is evaluated on
whether its performance is *acceptable and stable*, not on whether something else
scores higher — because for that volume, at that weight profile, nothing else is
economically viable.

This is the single most important judgement in the framework. A ranking presented
without it invites a decision that would cost the firm several million dollars a year.
