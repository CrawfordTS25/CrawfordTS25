# Talk track — presenting the dashboard

For a 20-minute leadership review. Page order matches the report.

The governing principle: **lead with what the data supports, and say plainly what it
does not.** A dashboard that states its own limits gets trusted with the next decision.
One that oversells the first conclusion gets audited instead.

---

## Opening — 60 seconds

> "This dashboard answers one question: which UPS service gives us the best balance of
> reliability, loss risk and cost. Before the answer, the caveat that shapes it — we
> have four months of billing data but only **one month** of delivery-performance and
> claims data. So the cost conclusions are solid, and the reliability conclusions are
> directional. The banner at the top of every page says which you are looking at."

Establishing the basis first is not throat-clearing. It is what stops someone quoting
96.5% as an annual figure in a board pack three weeks from now.

---

## Executive Overview — 4 minutes

> "293,900 shipments, $4.5 million net spend, 96.5% on time, five loss claims per ten
> thousand shipments. Cost per shipment is flat across all four months — $15.22, $15.51,
> $15.38, $15.43 — so the rate structure is behaving and there's no cost drift to chase.
>
> The scorecard ranks the four services that qualify. 2nd Day Air is top, Ground is
> bottom. **Before anyone reads that as 'stop using Ground' — it isn't.** I'll come back
> to why on the cost page."

**If asked about the score:** "It's a weighted 0–100 blend. Note the line beneath it —
the weights say reliability 80%, cost 20%, not the 40/30/20/10 the framework specifies.
That's because claims can't be attributed to a service in this data. I'll cover that on
the claims page. The score tells you where it's been reweighted so nobody quotes it as
something it isn't."

---

## Service Performance — 4 minutes

> "2nd Day Air is our most reliable qualified service at 98.2%. Ground is 96.0%.
>
> The bar you want is 3 Day Select, at 99.4% — the best number in the file. It isn't
> ranked, because it's 0.9% of our volume on 683 measured packages. Look at the notch
> on each bar: that's the 95% confidence floor. For Ground the notch is almost touching
> the bar end — 48,000 packages, we know that number cold. For the small services the
> gap is wide.
>
> Next Day Air Early is the extreme case: four packages measured, zero late, 100% on
> time — and a confidence floor of 51%. The true rate could be a coin flip."

**The demonstration.** Toggle the `Threshold: none` bookmark.

> "That's the ranking with the volume threshold removed. A four-package service is now
> our best-performing option. That's why the threshold exists."

That click makes the case for volume governance better than any slide.

> "One more thing on reliability, and it's the most useful operational point here:
> **96% of our late packages missed the committed day, not just the committed hour.**
> A package arriving at 4pm instead of 10:30 is an inconvenience. A package arriving
> Thursday instead of Wednesday is a broken commitment. That's a specific, evidenced
> thing to raise with the UPS account team, and you can't see it in an aggregate on-time
> number."

---

## Cost and Volume — 4 minutes

**The most important four minutes in the review.**

> "Two charts, same services, same period. Left: cost per shipment. Ground $14.36, 2nd
> Day Air $14.72, Next Day Air Saver $14.87. Fifty-one cents between them. Read that
> alone and upgrading Ground volume to air looks nearly free.
>
> Right: cost per billed pound. Ground 89 cents. 2nd Day Air $6.48. Saver $19.73.
>
> The difference is weight. Ground averages 16 pounds a piece; Saver averages
> three-quarters of a pound. The left chart is comparing the price of a 16-pound box
> with the price of an envelope and calling the gap a rate premium.
>
> Ground is seven times cheaper than 2nd Day Air per pound, and twenty-two times cheaper
> than Saver. **That is why Ground stays our default despite ranking last on
> reliability.** The 2.2-point on-time gap is a management problem. Moving that volume
> to air would be a multi-million-dollar mistake made from a chart that looked
> reasonable."

**If challenged — "so is the score wrong?"**

> "No, the score uses the per-pound view for exactly this reason. But the ranking answers
> 'which service performs best', and the policy question is 'which service should we
> default to'. On this data those have different answers, and the recommendation page
> keeps them separate."

---

## Claims and Exceptions — 4 minutes

Open with the limitation, then the finding.

> "First, what this page can't do. Our claims export has account and claim category —
> no product, no service, no tracking number. So there is **no way to say which service
> loses more packages**. That's why there's no service breakdown here and why the
> service slicer does nothing on this page. I'd rather show you a blank than a number
> that looks like an answer.
>
> That's also 50% of the scoring framework we can't compute. **Getting a tracking number
> onto the claims export is the single highest-value change available to this model** —
> it's one field, and it's on the automation list as priority one.
>
> Now, what the page does say, and it's the most actionable thing in the whole analysis.
> One account — the CVS account, 18% of our March volume — carries **80% of all our loss
> claims**. Its loss rate is 22.5 per ten thousand against a firm-wide 5.1. That's 4.4
> times the average.
>
> Take that one account out and our firm-wide loss rate drops from 5.1 to 1.2. That is a
> good number.
>
> **So this isn't a UPS problem. It's a site problem.** A firm-wide claim rate describes
> a carrier; a concentrated one describes a location — and a location can be fixed.
> Packaging, handling, pickup process, dock security. That's an operations review at one
> site, and it would have been completely invisible in a UPS-wide average."

---

## Cost Drivers — 2 minutes

> "Surcharges are 12.8% of net spend. One line is worth your attention: **Address
> Correction — $10,272 in March across 583 packages, about $17.62 each.** Every one of
> those is a package we sent to a bad address we supplied. It's charged per package and
> it's entirely avoidable with address validation at the point of shipment. At March's
> run rate that's roughly $123,000 a year for a process fix, not a negotiation.
>
> This didn't come from the carrier conversation. It came from a tab that happened to be
> in the March file."

---

## Annual Recommendation — 2 minutes

> "Ground stays the default — the economics are decisive and nothing here challenges
> that. 2nd Day Air becomes our expedited default when Ground transit isn't enough; it's
> our most reliable service and cheaper per pound than either overnight option. Next Day
> Air Saver over Next Day Air where end-of-day is acceptable — better on-time rate at
> lower cost. Ground goes on the monitoring list on reliability, because at 72% of volume
> it sets our overall number almost by itself.
>
> Two things to action now, both independent of the data gaps: the CVS site review, and
> address validation at point of shipment.
>
> And to be clear about status — the service recommendations are **provisional** on one
> month of delivery data. I would not issue them as annual policy until we have at least
> six months. The model is built for the full year; it's the data that's missing, not
> the analysis."

---

## Questions you should expect

**"Should we switch carriers?"**
> "Nothing here supports that. 96.5% on time is a normal performance band, and our loss
> risk is concentrated in one of our own locations rather than spread across the carrier.
> The evidenced conversation with UPS is about missed-day performance on Ground, not
> about the relationship."

**"Why is Ground last if it's our main service?"**
> "Because the ranking measures performance, not fitness for purpose. Ground is last on
> reliability by 2.2 points and last on weight-normalised cost efficiency — but it moves
> 72% of our volume at a seventh the cost per pound of the next option. The ranking says
> 'watch Ground's on-time rate'. It does not say 'stop using Ground', and the
> recommendation page separates those two readings deliberately."

**"Can we trust one month of data?"**
> "For cost, yes — four months, and they're consistent. For reliability, treat it as
> directional. One month can't separate a consistently good service from one having a
> good month. That's the top item on the data list."

**"What would change your recommendation?"**
> "Three things. Twelve months of transit data could show a service that looked good in
> March is volatile across the year. A tracking key on claims could show loss risk that
> genuinely varies by service, which would restore half the scoring model. And a weight
> profile shift — if Ground volume moved toward lighter packages, the cost argument for
> it weakens."

**"How much of this is judgement versus what the data says?"**
> "The numbers are the numbers, and they reconcile to the source extracts to the cent.
> The judgements are: where to set the volume threshold, weighting cost per pound rather
> than per shipment, and treating Ground as a volume anchor rather than a ranked
> competitor. All three are on the dashboard and adjustable — the thresholds are live
> sliders. If you disagree with any of them, we can move them now and see what changes."
