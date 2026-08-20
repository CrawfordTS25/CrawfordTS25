# v3 runbook — contacts, file automation, notes

For `QuantumView_Checkpoint_DateSlicersPassed.pbix`. About 50 minutes of Desktop work,
plus the SharePoint list and flows when you're ready for them.

## No new .pbix this round, on purpose

Everything here is model-layer. Your file already opens, and it still has its sensitivity
label — handing you back a label-stripped copy would cost you the marking and gain you
nothing. **Keep working in your own file.**

The one report-layer thing that is broken fixes itself: the two date slicers are bound to
`'Dim Date'[Date]` and that table doesn't exist. Step 5 creates it and they light up.

---

## What you got right, so I didn't touch it

The roster build is the hard part of this and it's correct. `Branch_Contacts_All` →
`Branch_Contacts` → `Trace_Contact_By_FA` is the right shape, and critically the BOA→FA
join is on the right key:

```
BOA[FA ID]  ->  FA[EMPLID]     24,972 of 25,007     99.9%
BOA[FA Name] -> FA[Contact Name]                    19.7%
```

Name-matching was the obvious approach and it would have quietly lost four fifths of the
pairings. `Trace_Contact_By_FA` is untouched by every script here.

---

## Step 1 · Model view — four edits · 3 min

TMDL can't script these safely; Power BI allows only one **active** relationship between a
given pair of tables, so scripting a new one while the old is live either errors or
deactivates something you wanted.

**a. Delete** `Current_Open_Trace[FA #] → Trace_Contact_By_FA[FA #]`
It matches 0 of 95 rows. Step 3 replaces it with `[FA Key]`.

**b. Set inactive** `Current_Open_Trace[Exception Key] → Resolutions Table`
**and** `Trace_Active[Exception Key] → Resolutions Table`
**Then set active** `Current_Open_Trace[Account Key] → Dim_Account`
**and** `Trace_Active[Account Key] → Dim_Account`

Both account relationships are inactive right now, which is why the **Vendor Acct # slicer
on ACTIVE TRACES filters nothing**. Power BI deactivated them when `Trace → Resolutions`
created a second path to `Dim_Account`. The direct path covers **95 of 95**; the indirect
one covers **60 of 95**. The direct one wins. The Exception Key link stays in the model,
inactive, for `USERELATIONSHIP`.

**c. Untick Enable load** on `Branch_Contacts_All`
46,080 staging rows, referenced by no visual, and the third side of a triangle that's
holding `Trace_Contact_By_FA[Branch Number] → Branch_Contacts` inactive.

**d. Set active** `Trace_Contact_By_FA[Branch Number] → Branch_Contacts`
Possible once (c) removes the ambiguity.

✅ Model view shows no relationship with a dashed line you didn't intend.

---

## Step 2 · Power Query — the file automation side · 10 min

`Home → Transform data`, then `tools/model-fixes-v3.pq`:

**§1 `QV_RAW`** — replace. Reads `Archive\` only and computes the run window once, at 13:30.

**The path also changes.** Your `QV_RAW` points at
`…\Administrative Services-Solutions\Quantum View\QV_Data`; your path list says
`…\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data`. Different
parent. Check which one your last successful refresh actually read — if the old path still
resolves, you have two `QV_Data` folders and only one of them is being fed.

Three things Archive-only prevents. `Folder.Files` **recurses**, and `QV_Data` already
contains `Morning QV\`, `Afternoon QV\`, `Processed\` and `Failed\` — pointed at `QV_Data`
it reads every export once per folder it appears in, and Total Shipments multiplies with no
error anywhere. It would also try to parse `QV_Automation_Helper_Lists.xlsx` as a 34-column
CSV. And `QV_RAW` currently splits the day at 17:00 while `QV_Output` splits it at 13:30 —
same rows, two answers.

**§2 `QV_Output`** — delete two steps. `#"QV Run Time"` and `#"QV Run Date"` now come from
§1. Rename `Run Window` → `Run Time` so no visual needs rebinding.

**§3 `QV_Manifest`** — two steps. `Table.Buffer` on the dedupe (it's still keeping the
oldest row per shipment, the fix landed on `Resolutions Table` but not here), and move
`Account Key` from DAX to M.

✅ `Total Shipments` is unchanged after the refresh. If it jumped, the Archive path is wrong.

---

## Step 3 · Power Query — the contact fix · 10 min

**§4 `Current_Open_Trace`** — add three columns at the end: `FA Key`, `Home Office Code`,
`Contact Route`.

```
Current_Open_Trace[FA #]        I287748
Trace_Contact_By_FA[FA #]        287748
```

That character is why every contact measure returns nothing. Strip the prefix and 66 of 66
I-prefixed rows match.

**§5 `Trace_Active`** — the identical block, so the two trace tables stay interchangeable.

**§6 `Home_Office_Contacts`** — new. Eleven `H#####` department codes the roster can't
reach; seven already answered by addresses sitting in your own `CONTACT INFO` column.

It reads a `Home_Office_Contacts` sheet from `QV_Automation_Helper_Lists.xlsx` if one
exists, and falls back to the inline seed if not — so it works unedited today and starts
using the workbook the moment you add the sheet, without anyone touching M.

`Close & Apply`.

✅ `Contact Route` shows four values: Case contact, FA roster, Home office, Unroutable —
with Unroutable at exactly 1.

---

## Step 4 · Power Query — the send queue · 5 min

**§8 `Mail_Merge_Queue`** — new. One row per trace, already addressed, `Send To` and
`Send Cc` as semicolon strings the Outlook connector takes directly.

Needs §4 and §6 in place first.

✅ `Mail_Merge_Queue` has 95 rows, 90 with a `Send To`, 5 with a `Blocked Reason`.

---

## Step 5 · Apply the model script · 5 min

`View → TMDL view` → paste `tools/model-updates-v3.tmdl` → read it → **Apply**.

Contact measures rewritten onto the working keys (same names, so nothing needs rebinding),
the coverage measures, the mail-merge measures, `Dim Date` and its four date roles.

✅ `Dim Date` appears and starts in 2026. The two date slicers work.
✅ Mark it: `Dim Date → Table tools → Mark as date table → Date`.

---

## Step 6 · Verify · 5 min

`View → DAX query view`. `tools/checks/10-contact-routing.dax` is the new one and the one
that matters:

| | Now | Should read |
|---|---|---|
| Total Active Traces | 95 | 95 |
| **Contactable Traces** | **0 via roster** | **90** |
| Unreachable Traces | 95 | 5 |
| BOA Coverage | 0 | 61 |
| Sendable + Blocked | — | 90 + 5 |

The fourth query in that file is the blocked worklist: four home-office codes with no
address, plus the one trace whose FA # is the literal string `0`.

Then `checks/9-sources-and-contacts.dax` and `checks/4-kpi-reconciliation.dax` as before.

---

## Step 7 · Clean up · 2 min

Untick *Enable load*, or delete:

| | Why |
|---|---|
| `Branch_Contacts_Old` | 500 rows, every column null on every row |
| `Exception Reason Map` | loaded **and** the source of `Dim_ExceptionReason` — the same 14 rows twice in the Fields pane |
| `Res_Tracker` | 1,040 rows of unpromoted `Column1…Column14` |

And add **`A25T52`** to `\\nfpgshare-1...\Report Data\UPS Acct Info .xlsx` — extend the
table range to `A1:L25`. It's still the entire unmatched remainder: 755 manifest rows and
102 queue rows.

---

## Step 8 · The file automation · 15 min, once

`tools/qv-file-automation.ps1`, using the folders you already have:

```
Report Data\QV_Data\
    Archive\                        <- exports land here. The model reads THIS, only this.
    Morning QV\                     <- copies, before 13:30
    Afternoon QV\                   <- copies, at or after
    Processed\_processed.csv        <- state, so re-runs are cheap
    Failed\                         <- a COPY of anything unhandled, plus a .reason.txt
    _logs\                          <- one log per month
    QV_Automation_Helper_Lists.xlsx <- not touched
```

It **copies, never moves**, and never writes to Archive at all. Archive stays the source of
truth, so if the script fails, is disabled, or double-fires, the dashboard is unaffected.
That's the whole design — and it's why even a corrupt file gets *copied* to `Failed\` rather
than moved out of Archive.

1. `.\qv-file-automation.ps1 -WhatIf` — see what it would do
2. Run it for real, check `_logs\`
3. Schedule it — Task Scheduler, 09:00 and 15:00, repeating every 30 min for 2 hours so a
   late export gets picked up. Full instructions in the script's footer.

**Use UNC, not `X:`.** Drive letters are mapped per logon session. A task running as the
service account with nobody logged on has no `X:`, and it fails instantly with a
path-not-found that looks like a permissions problem and isn't.

**Use the service account, not your login** — same rule as the gateway credentials.

> **The 13:30 cutoff is in two places** — the script and `QV_RAW`. Change one and you must
> change the other, or the share and the dashboard will disagree about which run a file
> belongs to.

---

## Step 9 · Notes · 5 min, then the flows

**Your list already exists and the query isn't pointed at it.** `Trace_Notes` still reads
`QV_Tracing_API_Aligned_Workflow_Optimized.xlsx` while the notes moved to
`Trace_Master_Streamlined_`. The workbook is the abandoned copy — which is exactly why it
returns 199 blank rows out of 200 and joins 1 of 95 traces. Nothing was broken; the query
was reading a dead file.

**§7** repoints it. Paste the first two steps, load, look at the column names SharePoint
gives you — they're **internal** names, so "Trace Status" arrives as `Trace_x0020_Status` —
correct the renames, then paste the rest.

> ### Move the list off the personal OneDrive before rollout
>
> ```
> https://ejprod-my.sharepoint.com/personal/p258239_edwardjones_com/...
>                 ^^^^^^^^^^^^^^^^^^^^^^^^^
> ```
>
> That's one individual's OneDrive, not a team site. For a system of record an ops team
> depends on:
>
> - it's **deprovisioned when that person leaves or changes roles** — read-only, then gone,
>   typically after 30–93 days. The dashboard stops refreshing and the notes history goes
>   with it
> - Service refresh has to run on **that person's credentials**. It cannot be moved to a
>   service account, because the site belongs to the human
> - permissions are per-item sharing rather than site membership
>
> The query works against it today and I'm not holding your build up over this. But copy the
> list to a team site and change `SiteUrl` — 10 minutes now versus a data-loss incident
> later. Every column name survives the move.

Then `TRACE-NOTES-AND-MAILMERGE.md` for both flow definitions, the templates, and the
blocked-tenant fallback.

**Check first whether your tenant permits Flows.** It decides whether this is two days or
two weeks.

Steps 2–4 above are worth doing even if the flows never happen. They take the trace page
from "nobody knows who to contact" to a named FA, a named BOA, and a reason when neither
exists.

---

## Still open after all of this

| | |
|---|---|
| Trace date columns are still text | `model-fixes-v2.pq` §10 — no calendar can reach the trace side until this lands |
| Four `Home_Office_Contacts` addresses | H03130, H05057, H05150, H44804 — fills the last gap |
| One trace with `FA # = "0"` | data entry on the trace sheet |
| `Root Cause` / `Next Action` / `Notes` 0% populated | the exceptions-side write-back, `WRITEBACK-AND-MAILMERGE.md` |
| Exception grain decision | 8,583 keys vs 29,957 `Is Issue` rows vs 45,614 rows — a business answer, not a build |
