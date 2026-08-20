# Query validation — all 14, measured

Run against `QuantumView_Checkpoint_DateSlicersPassed.pbix`. Every number below is
measured off the loaded model, not inferred from the M.

**Headline:** 13 of 14 queries are sound. One join matches nothing, and it is the one
the whole mail merge depends on.

---

## Every relationship, measured

| | From → To | Coverage | |
|---|---|---|---|
| ✅ | `QV_Output[Exception Key]` → `Resolutions Table` | 45,614 / 45,614 · 100% | |
| ✅ | `Resolutions Table[Exception Type]` → `Dim_ExceptionReason` | 8,583 / 8,583 · 100% | |
| ✅ | `QV_Manifest[Account Key]` → `Dim_Account` | 90,477 / 91,232 · 99.2% | remainder is `A25T52` |
| ✅ | `Resolutions Table[Account Key]` → `Dim_Account` | 8,481 / 8,583 · 98.8% | remainder is `A25T52` |
| ✅ | `Branch_Contacts_All[Branch Number]` → `Branch_Contacts` | 46,080 / 46,080 · 100% | |
| ✅ | `Branch_Contacts_All[FA #]` → `Trace_Contact_By_FA` | 21,073 / 21,073 · 100% | |
| ✅ | `Trace_Contact_By_FA[Branch Number]` → `Branch_Contacts` | 21,073 / 21,073 · 100% | **inactive** — see below |
| ✅ | `Current_Open_Trace[Account Key]` → `Dim_Account` | 95 / 95 · 100% | **inactive** — see below |
| ✅ | `Trace_Active[Account Key]` → `Dim_Account` | 95 / 95 · 100% | **inactive** |
| ⚠️ | `Current_Open_Trace[Exception Key]` → `Resolutions Table` | 60 / 78 · 76.9% | active, and it is what deactivated the two above |
| ⚠️ | `Trace_Active[Exception Key]` → `Resolutions Table` | 60 / 78 · 76.9% | same |
| ❌ | `Current_Open_Trace[FA #]` → `Trace_Contact_By_FA[FA #]` | **0 / 95 · 0%** | **the break** |

Every "one" side is genuinely unique — `Dim_Account` 23/23, `Dim_ExceptionReason` 14/14,
`Resolutions Table` 8,583/8,583, `Branch_Contacts` 15,894/15,894, `Trace_Contact_By_FA`
21,073/21,073. No relationship in this model is at risk of being refused for a duplicate
key, which is the thing that stopped `Shipper Match Key` working last round.

---

## Query by query

### ✅ `Branch_Contacts_All` — 46,080 rows
Reads the `Rosters` folder, takes the newest file per prefix, loads FA and BOA sheets.
21,073 FA rows, 25,007 BOA rows. `GetLatestFile` falls back to name-matching when the
folder filter finds nothing, which is the right shape — it degrades rather than erroring.

**One change:** untick *Enable load*. Nothing references it, and it is the third side of a
triangle (`Branch_Contacts_All → Branch_Contacts` directly **and**
`Branch_Contacts_All → Trace_Contact_By_FA → Branch_Contacts`) which is why
`Trace_Contact_By_FA[Branch Number] → Branch_Contacts` is stuck inactive. Stop loading it
and that relationship can go active. 46,080 staging rows out of the model as a bonus.

### ✅ `Branch_Contacts` — 15,894 rows
Groups `Branch_Contacts_All` by branch and emits FA Emails, BOA Emails, Primary Contact
Email, All Contact Emails. Unique on Branch Number, 15,894/15,894.

Correct for branch-level addressing. It is **not** the right table for FA-level addressing,
because a branch with three FAs and two BOAs collapses to one row and you can no longer
tell which BOA supports which FA. That is what `Trace_Contact_By_FA` is for, and you built
it — this note is only here so nobody wires the mail merge to the wrong one later.

### ✅ `Trace_Contact_By_FA` — 21,073 rows — **this is the good one**
One row per FA, with their BOAs attached. The join is
`BOA[FA ID] → FA[EMPLID]`, and it resolves **24,972 of 25,007 BOA rows — 99.9%**.

That is the correct key and it was not obvious. The alternative — matching on
`BOA[FA Name]` against `FA[Contact Name]` — resolves **19.7%**, because the two rosters
spell names differently. Getting this right is most of the work in "line up the BOAs to
the FAs they work for", and it is already done.

73.6% of FAs carry a BOA. The other 26.4% are solo FAs with no BOA in the roster. Not an
error; nothing to fix.

### ❌ `Current_Open_Trace` — 95 rows — **the break**

```
Current_Open_Trace[FA #]        I287748
Trace_Contact_By_FA[FA #]        287748
```

The relationship is **active and matches 0 of 95 rows**. Every contact measure —
`Selected Branch Email`, `Selected FA Email`, `Selected BOA Emails`, `Unreachable
Traces` — returns nothing for this one reason. The `Unreachable Traces` card on ACTIVE
TRACES reads 95 because *everything* is unreachable.

Strip the prefix and **66 of 66** I-prefixed rows match, resolving an FA email on all 66
and a BOA cc on 61.

The prefix is a type tag. One column is carrying two identifier spaces:

| Prefix | Meaning | Rows | Routes to |
|---|---|---|---|
| `I######` | a real FA number | 66 | the roster |
| `H#####` | a home-office department code | 28 | nothing — see below |
| `0` | data-entry miss | 1 | nowhere, and should say so |

### ❌ The 28 `H#####` rows are not FAs
Tested against every candidate column in the roster:

| Against | Matches |
|---|---|
| `EMPLID` | 0 of 28 |
| `JP Number` | 0 of 28 |
| `FA ID` | 0 of 28 |
| `FA #` | 0 of 28 |
| `Branch Number` | 5 of 28 — coincidence, not a route |

All 28 are `Location = Campus Ship / World Ship / Kimler` — home-office departmental
shipments. Only **11 distinct codes**, and **7 of them already have a confirmed address**
sitting in `CONTACT INFO` on their own trace rows. `Home_Office_Contacts` (§6 of
`model-fixes-v3.pq`) seeds those seven; four need somebody to fill in an address.

### ❌ `Trace_Notes` — 200 rows, **199 of them blank**
Joins **1 of 95** traces on `CASE #`, 0 on `Exception Key`, 0 on `Tracking Number`. Every
merged `Trace_Notes.*` column on `Current_Open_Trace` is populated on exactly one row.

Same failure shape as the old `Branch_Contacts`: a sheet range formatted well past its
data, loading as nulls, erroring on nothing. Moving to a SharePoint list fixes the
blank-row problem structurally and is the only version that delivers "notes update as we
make changes" — a workbook physically cannot record *when* a note was written, because an
Excel `NOW()` recalculates on open.

### ⚠️ `QV_Manifest` — 91,232 rows
`Latest per Shipment` still does the opposite of its name. `Table.Distinct` does not honour
an unbuffered `Table.Sort`, so the **oldest** manifest row per tracking number survives.
The `Table.Buffer` fix landed on `Resolutions Table` but not here.

`Account Key` is a DAX calculated column here and an M column everywhere else. Move it to M
for consistency and to keep it off the calculation engine.

### ⚠️ `QV_RAW` — two problems, both about the run window
```
QV_RAW    Run Type   splits the day at 17:00
QV_Output Run Time   splits the day at 13:30
```
Same rows, same model, two answers. And `QV_RAW` uses `Folder.Files`, which **recurses** —
the moment the automation writes into `Morning\` and `Afternoon\` under `QV_Data`, every
export is read three times and Total Shipments triples with no error anywhere. Pointing at
`Archive\` is what makes the run folders safe to create.

### ⚠️ `Exception Reason Map` — 14 rows, loaded twice
It is both a loaded table *and* the source of `Dim_ExceptionReason`, so the same 14 rows
appear twice in the Fields pane. It carries two relationships that exist only as inactive
because Power BI refused to make them active. Keep the query, untick *Enable load*.

### ⚠️ `Branch_Contacts_Old` — 500 rows, **every column null on every row**
The superseded roster query. Doing nothing except sitting next to the real one waiting to
be picked by mistake.

### ⚠️ `Res_Tracker` — 1,040 rows of unpromoted `Column1…Column14`
Both specs say drop it. `tbl_Resolution_Input` is what feeds the queue.

### ✅ `QV_Output` — 45,614 rows
Classifier, Exception Key and Account Key all correct. 100% of rows resolve to both
`Resolutions Table` and `Dim_ExceptionReason`. Only change is dropping the two run-window
steps once `QV_RAW` provides them.

### ✅ `Resolutions Table` — 8,583 rows
`Table.Buffer` on the dedupe and `First Seen` for ageing both applied correctly. Unique on
Exception Key, 8,583/8,583.

`Root Cause`, `Next Action` and `Notes` are still **0% populated** across all 8,583 rows —
the write-back gap, not a query fault. `Tracker Status` is 7,544 New / 1,039 Open.

### ✅ `Dim_Account` — 23 rows
Unique, and both fact relationships resolve at 99%. **`A25T52` is still missing** and is
the entire unmatched remainder: 755 manifest rows and 102 queue rows. Adding it takes both
to 100%.

### ✅ `Dim_ExceptionReason` — 14 rows
Includes `Other Exception`. 100% of both fact tables resolve. Nothing on the blank member.

### ✅ `Trace_Active` — 95 rows
Unique on CASE #. Needs the same `FA Key` normalisation as `Current_Open_Trace` so the two
trace tables stay interchangeable.

---

## Not a query, but it will bite

**`Dim Date` does not exist, and two slicers are bound to it.** OVERVIEW rail slot 6 and
RESOLUTION QUEUE rail slot 7 are both bound to `'Dim Date'[Date]`. The repoint happened;
the section that creates the table did not. Those two slicers are broken right now.
`model-updates-v3.tmdl` §5 builds it.

**Two account relationships are inactive**, so the Vendor Acct # slicer on ACTIVE TRACES
filters nothing. Power BI deactivated them when `Trace → Resolutions` created a second path
to `Dim_Account`. The direct path covers 95/95 and the indirect one 60/95, so the direct
one should win.

**Trace date columns are still text** on both trace tables, so no calendar can reach the
trace side — no date slicer, no trend, no SLA maths on the page whose entire job is SLA.
`model-fixes-v2.pq` §10, still outstanding.

---

## After the fixes

| | Now | After |
|---|---|---|
| Traces with a resolvable address | **0** via roster | **90 of 95** |
| — via FA roster | 0 | 66 |
| — via home-office map | 0 | 24 |
| Traces with a BOA cc | 0 | 61 of 66 |
| Still blocked | 95 | 5, each naming its own reason |
| Relationships matching nothing | 1 | 0 |
| Tables loaded carrying nothing | 3 | 0 |
| Broken slicer bindings | 2 | 0 |
