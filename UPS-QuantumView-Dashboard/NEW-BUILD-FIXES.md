# `NEWQuantum_View_Exceptions_Dashboard.pbix` — what was wrong and what I changed

**Deliverable:** `NEWQuantum_View_Exceptions_Dashboard_fixed.pbix` — opens, label
removed. `DataModel` is byte-identical to your upload; every change in the file itself
is in the report layer. The model work is in two scripts and takes about 40 minutes in
Desktop.

Both new dimensions had a real defect, and I found two more serious ones underneath
them that had nothing to do with the dimensions. Ranked by what breaks first.

---

## 1. The refresh is going to fail — `fnClassifyException` doesn't exist

Your file carries an **unapplied Power Query edit**. It rewrites `QV_Enriched` to call
`fnClassifyException(...)`. I checked the applied model and all 29 queries: there is no
query, function or expression by that name anywhere.

The data you're looking at is cached from a refresh that ran *before* the edit was made.
The moment you press **Close & Apply** or **Refresh**, `QV_Enriched` fails with
*"The name 'fnClassifyException' wasn't recognized"* — and `QV_Output`, `QV_Manifest`,
`Resolutions Table` and every visual in the report go down with it.

**Fix:** `tools/model-fixes-v2.pq` §1 is the missing function. It's written to be worth
having rather than just to unblock you — see §3 below.

---

## 2. `Shipper Match Key` can never carry a relationship

This is the error you were hitting on the account dimension.

`Dim_Account[Shipper Match Key]` is `UPPER(TRIM(CLEAN(Account Name)))`. Five of your
accounts are all called **EDWARD JONES MAIL SERVICES** — 75V664, 8V7494, 8V7507, 9V2538,
9V2549. Two more pairs collide the same way. **23 accounts collapse to 17 keys.** The
"one" side of a many-to-one relationship has to be unique, so Power BI refuses to build
it. Nothing you do on the fact side fixes that.

It wouldn't have worked even if it were unique, because `Shipper Name` in the shipment
feed is not the account name:

| Table | Shipper-name match | Tracking-derived `Account Key` |
|---|---|---|
| QV_Output | 21.72% | **99.13%** |
| QV_Manifest | 48.42% | **99.18%** |
| Resolutions Table | 31.19% | **98.83%** |

The misses are systematic, not typos: `EDWARD JONES/GATEWAY CDI` (25,107 rows) against
the workbook's `EDWARD JONES/GATEWAY CDI SRM`; `EDWARD JONES/ CVS` (5,896) against
`EDWARD JONES/ICVS`; and roughly 40,000 rows where `Shipper Name` is an individual's
name, not a business at all.

**Fix:** drop the column, use the account embedded in the tracking number. UPS 1Z format
is `1Z` + 6-char shipper account + 2-char service + 8-char package id:

```
1Z 2093RE 03 01360983   ->  2093RE   EDWARD JONES/Brand Addition
1Z 8E19V7 02 95095857   ->  8E19V7   EDWARD JONES/ICVS
```

You already derive it exactly this way on `Trace_Active`. `tools/model-fixes-v2.pq` §6–8
adds it to the other three tables; `tools/model-updates-v2.tmdl` §1 is the DAX
equivalent if you'd rather not touch the queries.

### `A25T52` is still missing, and it is the entire remainder

The unmatched 0.9% is **one account** and nothing else:

| Table | Unmatched rows | All of them |
|---|---|---|
| QV_Output | 404 | `A25T52` |
| QV_Manifest | 756 | `A25T52` |
| Resolutions Table | 102 | `A25T52` |

Add it and coverage is 100% on every table. The prepared row is in `UPS_Acct_Info_.xlsx`
in this repo; your live workbook is `\\nfpgshare-1...\Report Data\UPS Acct Info .xlsx`
and **the table range has to be extended to `A1:L25`** or the refresh won't see the new
row. Reasoning for the row's contents is in `ACCOUNT-DRILLDOWN.md` §3 — the name is
inferred from shipment data and flagged `UNVERIFIED` on purpose.

---

## 3. `Dim_ExceptionReason` silently drops 16% of the queue

The dimension itself is fine — 11 rows, and all 11 keys match. The problem is what
*doesn't* reach it.

**1,406 of 8,724 `Resolutions Table` rows have a null `Exception Type`.** They match no
dimension row, so they land on the blank member: invisible in the slicer, absent from the
category chart, uncountable. That's one exception in six.

They aren't junk. 1,257 of them are one business concept:

| Description | Rows |
|---|---|
| WE TRIED TO DELIVER TO THE BUSINESS, BUT IT WAS CLOSED… | 916 |
| WE TRIED TO DELIVER TO THE BUSINESS AGAIN, BUT IT WAS CLOSED… | 127 |
| THE RECEIVING BUSINESS WAS CLOSED. WE'LL ATTEMPT… | 103 |
| THE RECEIVING BUSINESS WAS CLOSED AT THE TIME OF THE FINAL ATTEMPT | 54 |
| THE RECEIVER WAS NOT AVAILABLE FOR DELIVERY… | 37 |
| …plus the rest of the attempt/miss family | 20 |

**Fix, in two parts:**

- **The guarantee.** The classifier never returns null any more — unmatched descriptions
  fall to `"Other Exception"`, and the dimension has a row for it. No judgement calls,
  nothing can vanish. This part is non-negotiable and it's what makes the dimension
  trustworthy.
- **The taxonomy.** 18 new keyword rules, all appended *below* the existing 29 so they
  can only catch what nothing else caught. **Verified: zero previously-classified rows
  change.** Unclassified goes **1,394 → 64** on the queue (16.0% → 0.7%) and
  **2,445 → 207** on `QV_Output`. The headline new type is **Delivery Attempt** — 1,273
  rows, 15% of your queue, genuinely actionable ("confirm receiving hours with the
  branch"). Delete any rule you disagree with; the fallback catches whatever's left.

### And the fact's `Exception Category` was never a category

`Resolutions Table[Exception Category]` and `QV_Output[Exception Category]` disagree with
the dimension's mapping on **36.5% of matched rows**. Not a data problem — a naming one.
Inside `QV_Enriched` the column is literally defined as an alias of the type:

```m
#"Added Exception Category Alias" =
    Table.AddColumn( ..., "Exception Category", each [Exception Type Detail], type text ),
```

So the fact says `Access Point Hold` (2,347 rows) where the dimension says
`Access Point`; `Wrong Recipient` (213) where the dimension says `Delivery Issue`. Two
columns with the same name at two different grains, and no way to tell them apart on
screen.

**Fix:** the dimension is authoritative. `fnClassifyException` now returns both the leaf
type *and* the real rollup from one shared map, so there is only one category column and
nothing left to disagree with. Every visual that displays the classification has been
repointed at `Dim_ExceptionReason` — see §7.

### Two `Exception Type` columns, one character apart

`QV_Output` has **both**:

| Column | Source | How it picks |
|---|---|---|
| `Exception Type` | DAX calculated column | `MAXX` — the **alphabetically last** match |
| `Exception Type ` *(trailing space)* | Power Query | the **first** rule in table order |

They disagree on **28,286 of 46,594 rows**. The DAX one is wrong by construction: `MAXX`
has no idea about priority, so `"MISSING SUITE NUMBER"` scores `Package Issue` over
`Missing Suite Number`, and `"ACCESS POINT … HOLD"` scores `Schedule Change` over
`Access Point Hold`. The Power Query one is right — but only by accident, because your
`Keyword Table` happens to be authored in priority order and nothing recorded that.

**Fix:** delete the DAX column. The keyword table gets an explicit `Priority` column so
re-sorting the sheet can't silently reclassify thousands of rows. One `Exception Type`
column, no trailing space.

---

## 4. The resolution queue is showing each exception's *oldest* state

This one has nothing to do with the dimensions and it's the most consequential thing I
found.

`Resolutions Table` sorts `Date modified` descending and then takes `Table.Distinct` on
`Exception Key`, intending to keep the newest sighting. **It does the opposite.**
`Table.Distinct` doesn't honour an unbuffered `Table.Sort` — without `Table.Buffer`,
Power Query streams and keeps whichever row it meets first, which is source order.

Measured on your data, on the 4,075 exception keys that appear in more than one export:

| | |
|---|---|
| Kept the **newest** row | **0** |
| Kept the **oldest** row | **4,075** |

So for 47% of the queue, `Status`, `Exception Resolution`, `Scheduled Delivery` and
everything else are the *first* thing UPS ever said about that exception, and every
update since has been discarded.

**`QV_Manifest` has the identical construction** in its `Latest per Shipment` step, so it
has the identical defect.

**Fix:** `Table.Buffer` around the sorted table — one function call, both queries.

Ageing has to move at the same time. `Age Days` currently runs off the surviving row's
`Date modified`, which by luck is the *first* sighting — so it's accidentally right
today, and would silently invert the moment the buffer fix lands. `tools/model-fixes-v2.pq`
§8 computes `First Seen` explicitly off the full table before the dedupe, so ageing is
right *on purpose*: a recurring exception keeps ageing instead of resetting to zero every
time it reappears. **1,110 rows change `Age Bucket`**, mostly out of `0-1` into `8+` —
which is the honest picture.

---

## 5. The measure sweep didn't survive the round trip

The new file is back on the pre-sweep measure set. All of this was fixed in `v5` and
needs re-applying:

| | Now | Should be |
|---|---|---|
| `Exception Rate` | `DIVIDE([Total Exceptions],[Total Shipments])` — events ÷ shipments, mixed grain | distinct affected shipments ÷ distinct shipments · **9.31% → 8.60%** |
| `Successful Shipments` | inherits the same mixed grain | same correction |
| `Aged 8 Plus Days` | counts resolved cases too | `Tracker Status <> "Resolved"` |
| `Avg Age (Days)` | plain `AVERAGE`, counts resolved | same |
| `Exceptions Total` · `Open Exceptions` · `Exceptions Resolved` | three byte-identical duplicate measures | delete — verified unused by any visual |
| Auto Date/Time | **on** — 12 hidden `LocalDateTable_*` + a template | off |
| `Dim Date` | doesn't exist | the conformed calendar |
| `QV_Manifest` | still **orphaned**, no relationships at all | related to `Dim_Account` and `Dim Date` |

Until `QV_Manifest` has a relationship, `Total Shipments` is a flat 92,630 under every
filter and `Exception Rate` is wrong on any sliced view — and the vendor ranking chart on
OVERVIEW shows the same total on every bar.

`Selected Exception Category` needed more than a repoint. The card is on a drill-through
page and `QV_Output → Resolutions Table` is single-direction, so a plain
`SELECTEDVALUE(Dim_ExceptionReason[...])` would always read "Multiple". It's now an
explicit `LOOKUPVALUE` — same name, same home table, so the card doesn't need rebinding.

---

## 6. Smaller things worth knowing

**`Branch_Contacts` was completely empty** — 500 rows, every column null on every row.
Rebuilt; see §7.

**`Review Status` writes `"Escalate "` with a trailing space** while the measure
`Escalated Traces` matches `"Escalate"` with none. DAX doesn't trim. It reads 67 today,
so the space is being lost somewhere between Power Query and the model — but that's luck,
not design. One character in `tools/model-fixes-v2.pq` §9.

**`Account Label` has a double space on one row** — `XH8186 -  Nova EDWARD JONES
DISTRIBUTION`, because the account name in the workbook has a leading space and the label
concatenates it raw. Cosmetic, but it's the slicer's display text. `Text.Trim` added in
`tools/model-fixes-v2.pq` §7.

**Trace dates are still text.** Every date column on `Current_Open_Trace` and
`Trace_Active` loads as text, so no calendar can reach the trace side — no date slicer,
no trend, no SLA maths on the page whose entire job is SLA. Carried forward unchanged as
`tools/model-fixes-v2.pq` §10.

**`Resolution Status` is starting to flow** — 1,039 rows now carry `Open`, up from zero.
`Root Cause`, `Next Action`, `Notes`, `Last Updated` and `Closed Date` are still 100%
empty across all 8,724 rows, which is the write-back gap; see
`WRITEBACK-AND-MAILMERGE.md`.

---

## 7. Branch contacts, and refresh stamps in the title bars

Both ship as `tools/contacts-and-freshness.pq` + `tools/contacts-and-freshness.tmdl`.
Neither is in the `.pbix` — see the note under Step 8b in §9 for why.

### `Branch_Contacts` — 500 rows of nothing

The query navigates to the `branch email` **sheet** and promotes row 1 to headers. Row 1
isn't the header row, and two of the column names it produced say so out loud:

```
"Source"                            <- a metadata label, not a field name
"X:\hrdi_report_pickup\FA_Roster\"  <- a FILE PATH became a column name
```

So there's a title/provenance block above the real header and the promote grabbed that.
Everything below it came through as null, the table loaded 500 empty rows, and no error
was raised — which is precisely why it survived this long.

I can't see the workbook from here, so §1 of the `.pq` is a **discovery query**: it lists
every item in the file with its kind, its non-blank row count, which row contains the word
"Email", and a preview of the first real row. Run it once, read three values off it, set
three constants in §2, delete it. If it shows a `Kind = "Table"` item, use that instead —
a named Excel table carries its own header and can't drift the way a sheet range does, and
the query collapses to six lines.

§2 is the rebuild. It:

- **finds the header row** instead of assuming row 1 — that's the actual bug
- drops fully-blank rows before *and* after the promote, so trailing formatted-but-empty
  rows stop inflating it to 500
- **identifies the email column by content** (>50% of values contain `@`) rather than by
  name, so a header rename can't quietly break it again
- keeps only rows carrying a plausible address, so a half-filled roster row can never be
  emailed
- dedupes on the key — the "one" side of a relationship has to be unique
- **never errors.** A roster that comes back empty must not take the daily refresh down
  with it. `[Branch Contacts Loaded]` surfaces it instead, as a number you can put on a
  page.

### The roster can only reach the trace side — and that's the whole story

Worth knowing before you build Flow 2, because it changes the plan.

**Trace side: clean.** `Current_Open_Trace[FA #]` is populated on all 95 rows — 66 as
`I######`, 28 as `H#####`, one literal `"0"` — and **no FA # maps to two different
emails**, so the join is unambiguous. 23 of the 95 have an FA # but a blank `CONTACT INFO`;
those are exactly the rows the roster rescues.

**Exceptions side: there is nothing to join to.** The queue carries no FA identity at all.
`QV_Output[Ship To Name]` is `EDWARD JONES` on 35,126 of 46,594 rows and a client's name on
most of the remainder; `QV_Manifest[Ship To Attention]` is `EDWARD JONES` or blank on
40,770. Neither identifies a person.

So the exceptions mail merge has to take its recipient from the SharePoint List's `Owner`
column, populated by the Power Apps panel from `User()`. `WRITEBACK-AND-MAILMERGE.md`
offered that as the interim route pending a roster fix — it turns out to be the only
route, and it works from day one. Fixing this query buys you the trace-side contact
lookup and a real roster for branch traffic, not an exceptions recipient.

### Per-source refresh stamps

`File.Contents` hands back bytes and nothing else — there's no modified date in it. So
`Refresh Status` (§3 of the `.pq`) locates each source by listing its **folder** and
picking the file out by name, which does carry `Date modified`. One row per source:

| Source | SLA | What it feeds |
|---|---|---|
| QV export feed | 18h | `QV_Output` · `QV_Manifest` · `Resolutions Table` |
| Trace workbook | 30h | `Trace_Active` · `Current_Open_Trace` · `Trace_Notes` · `Branch_Contacts` |
| Resolution tracker | 30h | `tbl_Resolution_Input` · `Res_Tracker` |
| Account list | 180d | `Dim_Account` |
| Coordinate table | 365d | `Master Coordinate Table` |

The SLA is per source because the sources move at wildly different speeds — the feed runs
twice a day, so 18 hours means you missed a run; the account list changes a few times a
year. They only drive the warning, never the data.

Two details that earn their place. Subdirectories are filtered out, and so is anything
starting with `~$` — Excel writes a lock file the moment somebody opens a workbook, so
without that filter the stamp would read "modified 10 seconds ago" for as long as anyone
had the file open, which is exactly backwards.

**In the title bar**, `[Data As Of]` renders compact when everything's current and names
the problem when it isn't:

```
8/5 2:32 PM
8/5 2:32 PM   ·   1 SOURCE STALE
NO FEED FILES FOUND
```

The trace pages get `[Trace Data As Of]`, which reads the tracing workbook instead — those
pages aren't driven by the QV export, so today's card is showing them the wrong file's
date. Both measures wrap their scan in `ALL('Refresh Status')`, so "data as of" stays a
property of the data rather than of your slicer selection; right now Exception Details
reports the file date of whichever single exception you drilled into.

`[Source Health]` returns all five sources one per line for a tooltip or an admin panel,
and `[Stalest Source]` names the worst offender with missing files outranking merely-old
ones.

> This also retires a column on `Current_Open_Trace` literally named
> `Updated 7/20/2026 at 1:59:16 PM - (98) Rows of delivery information updated in 31
> minute(s), 9 second(s)`. Somebody needed a freshness stamp and the only place to put it
> was a column header, where it froze the instant it was typed.

---

## 8. What I changed inside the file

Report layer only — `DataModel` is untouched and verifiably byte-identical.

**Repointed at the dimension** (5 visuals). Each keeps its own header text, column width
and sort, so nothing moves on screen:

| Page | Visual | Was | Now |
|---|---|---|---|
| OVERVIEW | Exceptions by Category | `QV_Output[Exception Category]` | `Dim_ExceptionReason[Exception Category]` |
| OVERVIEW | exception detail table | `QV_Output[Exception Type ]` | `Dim_ExceptionReason[Exception Type]` |
| RESOLUTION QUEUE | queue table | `Resolutions Table[Exception Category]` | `Dim_ExceptionReason[Exception Category]` |
| RESOLUTION QUEUE | exception slicer | `Resolutions Table[Exception Type ]` | `Dim_ExceptionReason` **Category → Type**, same two-level hierarchy as OVERVIEW |
| Exception Details | detail table | `QV_Output[Exception Category]` | `Dim_ExceptionReason[Exception Category]` |

**Cleared three things that were baked into the file:** a saved slicer selection on
RESOLUTION QUEUE, another on the hidden test page, and a stuck drill-through value on
Exception Details — that page was opening pre-filtered to one hard-coded exception
(`1Z0708F90100725981|WE TRIED TO DELIVER…`).

**Put the OVERVIEW filter rail back on the grid.** It had drifted to an 80px slot pitch
with 120/126/128px widths while RESOLUTION QUEUE and ACTIVE TRACES sat on the spec's 68px
pitch at a uniform 126. All three rails now line up exactly: `x 36`, `y 196/264/332/400/468/536`,
`126×56`. Also squared up the five page-title textboxes and five FILTERS labels, and took
the trailing space out of the ACTIVE TRACES slicer header (`'Vendor Acct # '`).

**Removed the sensitivity label** so the file opens. `SecurityBindings` is a
DPAPI-protected binding computed over the whole package — any external edit invalidates
it and Desktop then calls the file corrupted. The label is `Method=Standard`,
`ContentBits=0`: a classification marking, not rights-management encryption. **The output
is an unclassified copy.** Re-apply *Sensitivity → Internal Use Only · Standard* in
Desktop before it leaves your machine.

Verified after the edits: **180 field references resolve**, 0 overlaps, nothing
off-canvas, all 106 report JSON parts parse, `DataModel` SHA-256 identical.

The whole pass is `tools/fix_new_dashboard.py` — re-runnable against the original if you
want to see it work.

---

## 9. Desktop steps, in order — about 55 minutes

Do these in order; each one gates the next.

### Step 1 · Turn off Auto Date/Time · 1 min
`File → Options and settings → Options → Current File → Data Load` → untick
**Auto date/time**.

Before Step 5, or Power BI keeps generating a hidden calendar per date column and you end
up with two competing date tables.

✅ the little date hierarchies disappear from under each date column in the Fields pane.

### Step 2 · Delete four fields · 2 min
Fields pane → right-click → *Delete from model*:

```
QV_Output[Exception Type]                  <- the DAX column. MAXX-based, wrong by construction
'Resolutions Table'[Exceptions Total]
QV_Output[Open Exceptions]
QV_Output[Exceptions Resolved]
```

All four verified unused by any visual. The first one **has to go before Step 3**, or the
new `Exception Type` column collides with it.

### Step 3 · Power Query · 20 min
`Home → Transform data`. Work through `tools/model-fixes-v2.pq` in order —
§1 `fnClassifyException`, §2 `Exception Reason Map`, §3 `Keyword Table`,
§4 `Dim_ExceptionReason`, §5 `QV_Enriched`, §6 `QV_Output`, §7 `Dim_Account`,
§8 `Resolutions Table` + the `QV_Manifest` note, §9 the one-character `Review Status` fix.

> **Discard the pending edit sitting in your editor.** §5 is that edit with the three
> corrections in it — paste this instead of applying what's there.

`Close & Apply`.

✅ the refresh completes. That alone is the §1 fix landing.
✅ `Dim_ExceptionReason` has **14 rows**, including `Other Exception`.
✅ `Dim_Account` has no `Shipper Match Key` and every table has an `Account Key`.

### Step 4 · Add `A25T52` to the workbook · 5 min
Add the row from `UPS_Acct_Info_.xlsx` to
`\\nfpgshare-1...\Report Data\UPS Acct Info .xlsx`, **extend the table range to
`A1:L25`**, refresh.

✅ `Dim_Account` shows 24 rows and no tracking number fails to match.

### Step 5 · Apply the model script · 5 min
`View → TMDL view` → new script → paste `tools/model-updates-v2.tmdl` → read it → **Apply**.

> **Stop before section 9.** It relates the calendar to the trace tables and can't work
> until Step 6 types those columns. Delete §9 for now, or let it fail and re-run after.
>
> **Skip section 1** if you took the Power Query route in Step 3 — it's the same two
> columns done twice.

✅ `Exception Rate` reads **8.60%**, not 9.31%.
✅ `Dim Date` appears and starts in 2026 — if it starts in 1900, stop and read Step 6.
✅ the **vendor ranking chart on OVERVIEW is no longer flat**.

### Step 6 · Type the trace date columns · 10 min
`tools/model-fixes-v2.pq` §10, on `Current_Open_Trace` and `Trace_Active`, after the
Trace_Notes merge step.

✅ `Manifest Date` on `Current_Open_Trace` shows a calendar icon, not *abc*.
✅ `Follow-up` has 28 blanks. `Dim Date` still starts in 2026.

### Step 7 · Relate the calendar to the trace side · 2 min
Re-run §9 of the TMDL script, the part you skipped.

### Step 8 · Branch contacts and refresh stamps · 12 min
`Home → Transform data` again, then `tools/contacts-and-freshness.pq`:

1. **§1 discovery** — new blank query, paste, look at the four columns it returns.
   Note the item name, its `Kind`, and which row holds "Email". Then delete the query.
2. **§2 `Branch_Contacts`** — set `ItemName`, `ItemKind` and `KeyColumn` from what §1
   showed you, then replace the whole existing query.
3. **§3 `Refresh Status`** — new blank query, rename it exactly `Refresh Status`.

`Close & Apply`. Then `View → TMDL view` → paste `tools/contacts-and-freshness.tmdl` →
**Apply**. That adds the roster relationship and nine measures; it touches nothing that
already exists.

✅ `Branch_Contacts` has real rows with real addresses — **not 500, and not 0**.
✅ `Refresh Status` has 5 rows and every `Modified` is populated. A null means that
   source's folder or filename doesn't match what §3 expects — fix the pattern, not the
   data.

### Step 8b · Point the title bars at the right source · 3 min
Five cards, one per page, at `x 868 · y 27 · 372×38`. Each currently shows
`Max(QV_Output[Date modified])`. For each: click the card, drag the measure below into the
**Data** well, remove the old field, and set the field's rename to `DATA AS OF` so the
label doesn't change.

| Page | Measure |
|---|---|
| OVERVIEW | `[Data As Of]` |
| RESOLUTION QUEUE | `[Data As Of]` |
| Exception Details | `[Data As Of]` |
| ACTIVE TRACES | `[Trace Data As Of]` |
| Trace Details | `[Trace Data As Of]` |

The trace pages get the tracing workbook's stamp because that's what actually feeds them —
right now they're showing the QV export's date, which has nothing to do with what's on the
page.

> **Why this isn't already done in the file.** Both measures live on `Refresh Status`, a
> table that doesn't exist until Step 8 runs. Binding a visual to a missing table is the
> exact risk profile that produced the unopenable files earlier in this build, and I'm not
> spending your openability on a three-minute step. Same reason the Manifest Date slicer
> shipped bound to `'Resolutions Table'[Manifest Date]` rather than `'Dim Date'[Date]`.

### Step 9 · Two follow-ups · 2 min
- **Repoint the date slicers.** On OVERVIEW and RESOLUTION QUEUE the Manifest Date slicer
  is bound to `'Resolutions Table'[Manifest Date]` — chosen so it worked before
  `Dim Date` existed. Swap it for `'Dim Date'[Date]`; it then also filters `QV_Manifest`,
  which makes Total Shipments and Exception Rate date-responsive.
- **Add a date slicer to ACTIVE TRACES.** Possible for the first time. Drag
  `'Dim Date'[Date]` into the rail, then set `Format → General → Properties → Position`
  to `X 36 · Y 604 · W 126 · H 56` — slot 7, matching the other two pages exactly.
- **Mark the date table** if it isn't already: `Dim Date` → `Table tools → Mark as date
  table` → column `Date`.

### Step 10 · Verify · 5 min
`View → DAX query view`. The seven tabs in `tools/checks/` are read-only. The three new
ones matter most here:

| Query | Confirms |
|---|---|
| `7-classification-coverage.dax` | **Unclassified = 0**, no fact type without a dim row |
| `8-dedupe-recency.dax` | **Stale rows = 0** — the queue is showing current state |
| `9-sources-and-contacts.dax` | **Branch contacts loaded > 0**, 5 sources current, and the 23 traces the roster rescues |
| `4-kpi-reconciliation.dax` | rate 8.60% |
| `5-status-vocabulary.dax` | the exact strings the status measures match on |

Then click each page: every KPI should move with the Vendor Acct # slicer, and ACTIVE
TRACES should read **95 / 67 / 28 / 27 / 86**.

### Step 11 · Re-apply the sensitivity label · 1 min
`Sensitivity → Internal Use Only · Standard`. **Before the file leaves your machine.**

---

## 10. Still open after this

| | Why it can wait |
|---|---|
| Write-back + mail merge | the biggest remaining build — `WRITEBACK-AND-MAILMERGE.md` |
| Exception grain decision — 8,724 keys vs 29,957 `Is Issue` rows vs 46,594 rows | needs a business answer, not a build |
| Confirm the resolved/escalated literals against production | needs live data flowing |
| The one trace row whose `FA #` is the literal string `"0"` | data entry on the trace sheet; it can never resolve to a contact |
| Trim `QV_Manifest`, drop `Res_Tracker` | performance, not correctness |
| Folder ingest + dedupe (`model-fixes.pq` §6–8) | only once the feed is automated |

**One to watch, not fix:** `Resolved Exceptions` and `Escalated Exceptions` return **0**
today because nothing in the extract is resolved. Correct behaviour on this data — but
indistinguishable from a literal mismatch, which is why Step 10's vocabulary check matters
the moment real resolutions start flowing.
