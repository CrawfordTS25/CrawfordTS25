# Desktop runbook — everything you need to do, in order

Start from **`Quantum_View_Exceptions_Dashboard_v5.pbix`**. Every report-layer change is
already in it. What's below is the model work, which can only be done in Power BI
Desktop.

**Time:** about 45 minutes end to end. Steps 1–5 are the ones that matter; 6–9 are
polish and publish.

**Before you start:** keep a copy of v5 somewhere safe. Every step below is reversible,
but a known-good starting point costs nothing.

---

## Step 1 — Turn off Auto Date/Time · 1 min

`File → Options and settings → Options → Current File → Data Load` → untick
**Auto date/time**.

Do this **before** Step 3. Otherwise Power BI keeps generating a hidden calendar behind
every date column and you end up with two competing date tables.

✅ **Check:** the Fields pane loses the little date hierarchies under each date column.

---

## Step 2 — Delete three duplicate measures · 2 min

Fields pane → right-click → *Delete from model*, one at a time:

```
'Resolutions Table'[Exceptions Total]
QV_Output[Open Exceptions]
QV_Output[Exceptions Resolved]
```

All three are byte-identical copies of measures you're keeping, and I verified none is
referenced by any visual.

✅ **Check:** no visual shows an error afterwards. If one does, you deleted the wrong
copy — undo with Ctrl+Z.

---

## Step 3 — Apply the model script · 5 min

`View → TMDL view` → new script → paste **`tools/model-updates.tmdl`** → read it →
**Apply**.

> **Stop before section 7.** That last section relates the calendar to the trace tables
> and can't work until Step 4 types those columns. Delete section 7 from the script for
> now, or let it fail and re-run it after Step 4.

This creates:

| | |
|---|---|
| `Account Key` | on `Resolutions Table` and `QV_Manifest` |
| `Aged 8 Plus Days`, `Avg Age (Days)` | rewritten to exclude resolved cases |
| `Exception Rate`, `Successful Shipments` | rewritten onto one grain |
| `Affected Shipments`, `Exceptions per Affected Shipment` | new |
| `Dim Date` | the calendar, bounds derived from your data |
| 6 relationships | 2 account, 4 date |

✅ **Check:** `Exception Rate` reads **8.60%**, not 9.31%. `Dim Date` appears in the
Fields pane and starts in 2026 — if it starts in 1900, stop and re-read Step 4.

✅ **Check:** the **vendor ranking chart on OVERVIEW is no longer flat** — that's the
account relationship landing.

---

## Step 4 — Type the trace date columns · 10 min

`Home → Transform data` → select **`Current_Open_Trace`** → `Advanced Editor`.

Paste the block from **`tools/model-fixes.pq` section 9**, placed **after** the
Trace_Notes merge step. Then repeat for **`Trace_Active`**.

Two things in that code are doing real work:

- **`"Not Avail."` and `1/3/1900` become null, not dates.** 28 of 95 `Follow-up` values
  are `1/3/1900` — an Excel epoch artifact from a blank cell that got date-formatted.
  Convert those naively and `Dim Date` stretches back to 1900, roughly 46,000 rows, and
  every date axis becomes unreadable.
- **`Culture = "en-US"` is explicit.** `"7/8/2026"` is 8 July under en-US and 7 August
  under en-GB. Without the culture pinned, a Service refresh can silently disagree with
  Desktop.

`Close & Apply`.

✅ **Check:** `Manifest Date` on `Current_Open_Trace` now shows a calendar icon, not
*abc*. `Follow-up` has 28 blanks. `Dim Date` still starts in 2026.

---

## Step 5 — Relate the calendar to the trace side · 2 min

Now re-run **section 7** of `model-updates.tmdl` (the part you skipped in Step 3), or do
it by hand in Model view:

| From (many) | To (one) | Active |
|---|---|---|
| `Current_Open_Trace[Manifest Date]` | `'Dim Date'[Date]` | **yes** |
| `Current_Open_Trace[Last Reviewed]` | `'Dim Date'[Date]` | no |

✅ **Check:** Model view shows `Dim Date` connected to three fact tables.

---

## Step 6 — Two 20-second follow-ups · 2 min

**a. Repoint the date slicers.** On OVERVIEW and RESOLUTION QUEUE, the Manifest Date
slicer in the bottom rail slot is bound to `'Resolutions Table'[Manifest Date]` — chosen
so it worked before `Dim Date` existed. Swap the field for `'Dim Date'[Date]`. It then
also filters `QV_Manifest`, which makes Total Shipments and Exception Rate
date-responsive.

**b. Add a date slicer to ACTIVE TRACES.** Now possible for the first time. Drag
`'Dim Date'[Date]` into the rail, then set its position precisely under
`Format → General → Properties → Position`:

```
X 36    Y 604    Width 126    Height 56
```

That's rail slot 7 and matches the other two pages exactly.

**c. Mark the date table** if it isn't already: select `Dim Date` →
`Table tools → Mark as date table` → column `Date`.

---

## Step 7 — Verify · 5 min

`View → DAX query view`. The four tabs in **`tools/checks/`** are read-only:

| Query | Confirms |
|---|---|
| `4-kpi-reconciliation.dax` | Affected Shipments 7,178 · Total Shipments 83,502 · rate 8.60% |
| `5-status-vocabulary.dax` | the exact strings your status measures match on |
| `3-age-days-anchor.dax` | ageing measures case age, not run recency |
| `6-trace-notes-join.dax` | notes actually land (run after the Trace_Notes key fix) |

Then click through each page: every KPI should move when you change the Account/Vendor
slicer, and the trace page numbers should read **95 / 67 / 28 / 27 / 86**.

---

## Step 8 — Re-apply the sensitivity label · 1 min

`Sensitivity → Internal Use Only · Standard`.

I removed it to make the file openable — the label's tamper binding rejects any edit
made outside Desktop. Saving from Desktop regenerates a valid one.

**Do this before the file leaves your machine.**

---

## Step 9 — Publish · 15 min

1. Publish to a **dedicated workspace**, not My Workspace
2. Point Power Query credentials at a **service account**, not your login — otherwise
   everything breaks the day you're on PTO or change roles
3. **Gateway:** needed for a UNC path; **not** needed if the landing folder is
   SharePoint and you switch to `SharePoint.Files` (see `tools/model-fixes.pq` §5)
4. Scheduled refresh **before** the 08:00 SOP window
5. Publish as an **App** to the ops team rather than sharing the raw report

---

## Still open after this — for after rollout

| | Why it can wait |
|---|---|
| Exception grain decision (7,775 keys vs 29,957 `Is Issue` rows vs 40,735 rows) | needs a business answer, not a build |
| Confirm resolved/escalated literals against production | needs live data flowing |
| Write-back layer — `Root Cause`, `Next Action`, `Notes` are 100% empty | biggest remaining build |
| Trim `QV_Manifest`, drop `Res_Tracker` | performance, not correctness |
| Folder ingest + dedupe (`model-fixes.pq` §6–8) | only once the feed is automated |

**One to watch, not fix:** `Resolved Exceptions` and `Escalated Exceptions` return **0**
today because nothing in the extract is resolved. That's correct behaviour on this data
— but it's indistinguishable from a literal mismatch, which is why Step 7's vocabulary
check matters once real resolutions start flowing.
