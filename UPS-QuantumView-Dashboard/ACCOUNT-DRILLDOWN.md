# Account / Vendor drill-down — what shipped and what's left

**File:** `Quantum_View_Exceptions_Dashboard_v2.pbix` (sensitivity label removed, so it
opens; re-apply *Internal Use Only · Standard* in Desktop before sharing).

The account number is **embedded in the tracking number** — UPS 1Z format is
`1Z` + 6-char shipper account + 2-char service + 8-char package ID. No join on
shipping address is needed:

```
1Z 2093RE 03 01360983   ->  2093RE  EDWARD JONES/Brand Addition
1Z 8E19V7 02 95095857   ->  8E19V7  EDWARD JONES/ICVS
1Z XH8186 03 39818208   ->  XH8186  Nova EDWARD JONES DISTRIBUTION
```

Verified against your workbook across the whole model:

| Table | Rows | Derived account matches `Dim_Account` |
|---|---|---|
| QV_Output | 40,735 | 99.06% |
| QV_Manifest | 83,502 | 99.15% |
| Resolutions Table | 7,775 | 98.74% |
| Current_Open_Trace | 95 | 100% |

You already derive it exactly this way on the trace tables — `Account Key` equals
`MID(Tracking Number, 3, 6)` on all 95 rows.

---

## 1. Already in the .pbix — nothing for you to do

**Account / Vendor slicer** in rail slot 6 (`36, 536, 126×56`) on **OVERVIEW**,
**RESOLUTION QUEUE** and **ACTIVE TRACES**. Bound to `Dim_Account[Account Label]`,
which already exists in your model — so the slicer is live the moment you open the
file. It filters ACTIVE TRACES immediately, because `Dim_Account → Current_Open_Trace`
is already related. It starts filtering the other two pages the moment you finish
step 2 below.

Each slicer is a clone of an existing rail slicer *on its own page*, with only name,
position and field changed, so formatting matches exactly.

**Also done:** one KPI card on ACTIVE TRACES had drifted to `782.07, 68.28,
232.32×78.03` — snapped back to `774, 76, 232×78`. The **TEST-Acct Sliver** page is
**hidden, not deleted**. `DataModel` is byte-identical; 179 field references resolve;
no overlaps, nothing off-canvas, no saved slicer selections.

## 2. The model work — 4 minutes in Desktop

The slicer can't reach the exceptions side until `Dim_Account` is related to it.
Two calculated columns, two relationships.

**Calculated columns** (Modeling → New column):

```dax
-- on 'Resolutions Table'
Account Key = UPPER ( MID ( 'Resolutions Table'[Tracking Number], 3, 6 ) )

-- on QV_Manifest
Account Key = UPPER ( MID ( QV_Manifest[Tracking Number], 3, 6 ) )
```

**Relationships** (Model view → drag, or Manage relationships):

| From (many) | To (one) | Active |
|---|---|---|
| `'Resolutions Table'[Account Key]` | `Dim_Account[Account Key]` | yes |
| `QV_Manifest[Account Key]` | `Dim_Account[Account Key]` | yes |

> **Do not also relate `QV_Output` directly to `Dim_Account`.** `QV_Output` already
> reaches `Dim_Account` through `Resolutions Table`, and a second path makes it
> ambiguous — Power BI will refuse the relationship or silently deactivate one.
> Filtering flows `Dim_Account → Resolutions Table → QV_Output` on its own.

That's it. Both new slicers go live, and drill-through on either detail page inherits
the account filter.

**Optional fast path** — `tools/account-drilldown.tmdl` does the same thing in one
Apply from TMDL view. It is untested against your model, so review it in the editor
before applying; if the syntax argues with you, the four manual steps above are
guaranteed and quicker than debugging it.

## 3. One decision needed: account `A25T52`

Not in the workbook, and it is the only unmatched code anywhere:

| Table | Unmapped rows | Share |
|---|---|---|
| Resolutions Table | 98 | 1.26% |
| QV_Output | 382 | 0.94% |
| QV_Manifest | 708 | 0.85% |

It resolves to `Shipper Location = "Other Branch Origin"` across **17 distinct shipper
names**, with individual branch addresses including Canadian ones (`1931 MT NEWTON
CROSS ROAD`, `178 PTH 12 N`). It looks like a branch-origin or Canada account that
never made the sheet.

Until it is mapped those rows sit under a **blank** member in the slicer, and any
account selection excludes them silently. Two options:

1. Add a row to `UPS_Acct_Info_.xlsx` — `Account # = A25T52`, name it whatever the
   business calls it — and refresh. Cleanest.
2. Give the blank a name so it is visibly unmapped rather than invisible:

```dax
Account Label =
VAR k = UPPER ( MID ( 'Resolutions Table'[Tracking Number], 3, 6 ) )
RETURN COALESCE (
    LOOKUPVALUE ( Dim_Account[Account Label], Dim_Account[Account Key], k ),
    k & " — UNMAPPED" )
```

I'd do option 1. Silent exclusion is the worse failure mode, especially on a page
whose whole purpose is finding which vendor is causing problems.

---

## 4. Other things worth fixing before production

**`QV_Manifest` is orphaned — no relationships at all.** So `Total Shipments` is a
flat 83,502 and `Exception Rate` is `exceptions ÷ 83,502` under every filter. Step 2
fixes this *for the account slicer*, but Total Shipments still won't respond to
Exception Category, Run Date or Service. The real fix is a shared `Dim Date` and
`Dim Service` that both fact tables hang off — that is the star schema the Trace spec
p.7 asks for, and it is the difference between a rate you can trust per vendor and one
you can only trust in total.

**Two aging measures still count resolved items.** Neither is status-aware, so both
keep counting cases after they close. Invisible today because `Tracker Status` only
holds `New / Needs Review` and `Open` in this extract — it will start drifting the day
resolution flows through:

```dax
Aged 8 Plus Days = CALCULATE ( COUNTROWS ( 'Resolutions Table' ),
    'Resolutions Table'[Age Bucket] = "8+ Days",
    'Resolutions Table'[Tracker Status] <> "Resolved" )

Avg Age (Days) = CALCULATE ( AVERAGE ( 'Resolutions Table'[Age Days] ),
    'Resolutions Table'[Tracker Status] <> "Resolved" )
```

**Confirm the status vocabulary before rollout.** `Resolved Exceptions` and
`Escalated Exceptions` match on the literals `"Resolved"` and `"Escalated"` and return
**0 silently** on a mismatch — indistinguishable from "nothing has resolved yet". Your
model already contains one such mismatch: those measures say `"Escalated"` while
`Current_Open_Trace[Review Status]` stores `"Escalate"`.

**Three duplicate measure pairs** — identical DAX under two names, on two home tables:

| | |
|---|---|
| `QV_Output[Total Exceptions]` | `'Resolutions Table'[Exceptions Total]` |
| `QV_Output[Open Exceptions]` | `'Resolutions Table'[Open Ex]` |
| `QV_Output[Exceptions Resolved]` | `'Resolutions Table'[Resolved Exceptions]` |

Delete one of each before more visuals bind to the wrong copy.

**Model weight.** `QV_Manifest` is the largest table and only one column of it is used
by any measure. Once it is related to `Dim_Account` you need `Tracking Number` and
`Account Key` and little else — dropping the address columns is a large, free saving
at 83k rows and growing. `Res_Tracker` (unpromoted `Column1…Column14`) and Auto
Date/Time are still loaded; both specs say to remove them.

**Good news on `Age Days`:** you fixed the anchor. It now spans 1–22 with genuine
spread and four real buckets (`0-1`, `2-3`, `4-7`, `8+`) instead of six values keyed to
run dates. That was the one thing making a KPI actually wrong, and it's resolved.

---

## 5. Suggested order for your rollout

| | Step | Effort |
|---|---|---|
| 1 | Step 2 above — columns + relationships | 4 min |
| 2 | Decide `A25T52` | 5 min |
| 3 | Status-aware aging measures | 5 min |
| 4 | Confirm resolved/escalated literals against production | ask |
| 5 | Delete the 3 duplicate measures | 5 min |
| 6 | Trim `QV_Manifest`, drop `Res_Tracker`, kill Auto Date/Time | 30 min |
| 7 | Re-apply the sensitivity label, publish, scheduled refresh + service account | — |
| 8 | *Then* the shared `Dim Date` / `Dim Service` star | next iteration |

Items 1–5 are inside a lunch break and cover everything blocking the vendor drill-down.
Item 8 is the one I would not rush into next week — it touches every measure, and
you'll want the vendor view stable and tested first.
