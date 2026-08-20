# Trace notes and the mail merge

Two things that turn out to be one thing: you cannot automate an email until you know who
to send it to, and you cannot know whether it worked until the note comes back.

> This is the **tracing** side — Trace Status, Last Action, ticklers, claims, keyed on
> `CASE #` / `Exception Key`. The **exceptions queue** write-back (Root Cause, Next Action,
> Notes on `Resolutions Table`) is a separate list and lives in
> `WRITEBACK-AND-MAILMERGE.md`. Two lists, same pattern, different grain. Don't merge them —
> a trace is one investigation across many exceptions.

---

## Part 1 · Who gets the email

### The rule

| | |
|---|---|
| **To** | the FA — they own the client relationship |
| **Cc** | the BOAs who support that FA — they act on the package |
| **Fallback** | the case contact, if somebody already typed one against this trace |

Case contact **beats** the roster. Somebody typed it against *this* case having looked at
it; the roster is a directory, not a decision.

### How the BOA lines up with their FA

This is already right in your model and it is worth knowing why, because the obvious
approach fails.

`Branch_Contacts_All` carries both rosters. Every BOA row has an `FA ID` naming the FA they
support. Joining `BOA[FA ID] → FA[EMPLID]` resolves **24,972 of 25,007 BOA rows — 99.9%**.

The obvious alternative — matching `BOA[FA Name]` against `FA[Contact Name]` — resolves
**19.7%**, because the two rosters spell names differently.

Do **not** address off `Branch_Contacts`. It groups by branch, so a branch with three FAs
and two BOAs collapses to a single row and you can no longer tell which BOA supports which
FA. It's the right table for "email the branch", the wrong one for "email the person who
owns this package."

### Three routes, and the one that has none

`Current_Open_Trace[FA #]` is carrying two identifier spaces in one column:

| Prefix | What it is | Traces | Route |
|---|---|---|---|
| `I######` | a real FA number | 66 | roster → FA to, BOAs cc |
| `H#####` | a home-office department | 28 | `Home_Office_Contacts` |
| `0` | a data-entry miss | 1 | nothing, and it should say so |

The `H` codes match **nothing** in the roster — 0 of 28 against EMPLID, JP Number, FA ID
and FA #. They're Campus Ship / World Ship / Kimler departmental shipments. Only 11 distinct
codes, and **seven already have a confirmed address** sitting in `CONTACT INFO` on their
own trace rows; those are seeded. Four need filling in.

**Result: 90 of 95 traces addressable, 61 with a BOA cc.** Today it is 0 via the roster,
because `I287748` never matched `287748`.

### `Mail_Merge_Queue` is the table the flow reads

One row per trace, already addressed. `Send To` and `Send Cc` are semicolon strings, which
is exactly what the Outlook connector's To and Cc fields take — no splitting, no lookups in
the flow.

Every join, fallback and exclusion decision lives in M where you can read it, rather than
scattered across flow actions where you can't. And `Blocked Reason` means a trace that
can't be emailed **says why in a column** instead of quietly not appearing.

---

## Part 2 · The notes list

### The list already exists — the query is pointed at the wrong thing

```
Trace_Master_Streamlined_
https://ejprod-my.sharepoint.com/personal/p258239_edwardjones_com/Lists/Trace_Master_Streamlined_
```

`Trace_Notes` still reads `…\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx`.
The notes moved to the list; the workbook is the abandoned copy. That is the whole
explanation for **200 rows of which 199 are null in every column**, joining **1 of 95**
traces — nothing was broken, the query was reading a dead file.

§7 of `model-fixes-v3.pq` repoints it.

> ### ⚠ Move it to a team site before rollout
>
> `-my.sharepoint.com/personal/` is **one individual's OneDrive**. For a system of record an
> ops team depends on, that's a real exposure:
>
> - **Deprovisioned when that person leaves or changes roles.** Read-only, then gone,
>   typically after a 30–93 day retention window. The dashboard stops refreshing and the
>   notes history goes with it.
> - **Service refresh has to run on that person's credentials.** It cannot be moved to a
>   service account, because the site belongs to the human. Every other "use a service
>   account" note in this build is a policy choice; this one is a structural block.
> - **Permissions are per-item sharing**, not site membership, so onboarding the next
>   analyst is manual and easy to get wrong.
>
> Copy the list to a team site and change `SiteUrl`. Ten minutes, and every column name
> survives. Do the same for `tbl_Resolution_Input` while you're there, so both write-backs
> live somewhere that outlives an individual.

### Why a list and not the workbook

The blank rows are fixable in M. What isn't fixable in a workbook is the thing you actually
asked for — notes that update as you make changes:

| | Workbook | SharePoint list |
|---|---|---|
| When was this note written? | An Excel `NOW()` recalculates every time the file opens. It physically cannot tell you. | `Modified` is stamped at save and never drifts |
| Two people at once | One wins, one loses | Both land |
| Refresh from the Service | Needs the on-prem gateway | `SharePoint.Tables` needs **none** |
| History | Whatever the last save happened to contain | Version history per item |

### List schema — `Trace_Master_Streamlined_`

Yours already exists, so treat this as the target shape rather than a create script. The
two that matter are the indexes and the append-on multi-line columns; the rest you probably
have.

| Column | Type | Settings |
|---|---|---|
| `ExceptionKey` | Single line | **Indexed.** The stable key |
| `CaseNumber` | Single line | **Indexed.** The human key, and the fallback join |
| `TrackingNumber` | Single line | For people; never join on it |
| `TraceStatus` | Choice | `Open` · `Awaiting UPS` · `Awaiting Branch` · `Claim Filed` · `Closed` |
| `LastAction` | Multi-line | **Append changes to existing text = Yes** |
| `NextFollowUpDate` | Date only | Drives the tickler |
| `TicklerType` | Choice | `2 day` · `5 day` · `10 day` · `Manual` |
| `UPSTraceNumber` | Single line | |
| `ClaimRequired` | Yes/No | |
| `ClaimStatus` | Choice | `Not required` · `Filed` · `Approved` · `Denied` · `Paid` |
| `RefundAmount` | Currency | |
| `PII` | Yes/No | Gates whether contents can go in an email |
| `DeliveryConfirmed` | Yes/No | |
| `AssignedTo` | Person | |
| `Notes` | Multi-line | **Append = Yes** |
| `ClosedDate` | Date only | |
| `Created` · `Modified` · `Created By` · `Modified By` | Auto | System. Do not add, do not edit |

**Index `ExceptionKey` and `CaseNumber`.** Past 5,000 items SharePoint throttles unindexed
lookups, and every Patch does one.

> **Match the status literals to the model.** Measures test exact strings and return 0
> silently on a mismatch, which looks identical to a quiet week. Your model already contains
> one such mismatch: the measures say `"Escalated"` while `Current_Open_Trace[Review Status]`
> stores `"Escalate"`. Pick one vocabulary, put it in the Choice column, and run
> `checks/5-status-vocabulary.dax` after the first real note flows through.

### Keying — the part that actually broke

Notes get written against whichever key the analyst had to hand. So resolve on
`ExceptionKey`, fall back to `CaseNumber`, and **normalise both sides** — trim and
uppercase. That's why today's join lands 1 of 95: not because the notes are missing, but
because nothing normalised the keys.

In `Current_Open_Trace`, replace the single `CASE #` merge with two passes: merge on
`Exception Key`, then merge the still-unmatched rows on `CASE #`. §7 of `model-fixes-v3.pq`
has the query.

**SharePoint returns internal names, not display names.** A column shown as "Trace Status"
arrives as `Trace_x0020_Status`, and a column renamed after creation keeps whatever it was
first called. Load the first two steps of §7, look at what you actually get, then correct
the renames.

### Checking coverage

Once it's repointed, `checks/6-trace-notes-join.dax` tells you how many of the 95 traces
carry a note. If it's still near zero after the repoint, it's a key problem, not a source
problem — check that `Exception Key` in the list is the full
`TRACKING|DESCRIPTION` composite and not just the tracking number.

Confirm one note round-trips — edit in the list, refresh, see it on Trace Details —
**before** building anything on top.

---

## Part 3 · The flows

### Flow 1 · Notes audit log

```
TRIGGER    SharePoint · When an item is created or modified
           List: QV_Trace_Notes

ACTION     Excel Online (Business) · Add a row into a table
           Table: tbl_Trace_Audit
           Timestamp : utcNow()
           CaseNumber: triggerOutputs()?['body/CaseNumber']
           Status    : triggerOutputs()?['body/TraceStatus/Value']
           Action    : triggerOutputs()?['body/LastAction']
           By        : triggerOutputs()?['body/Editor/DisplayName']
```

`utcNow()` in the flow, never a formula in the sheet — same reason the list is the system
of record.

### Flow 2 · The mail merge

```
TRIGGER       Power BI · Power Automate visual button on ACTIVE TRACES
              Passes: Mail_Merge_Queue[CASE #]

ACTION 1      Get rows from Mail_Merge_Queue where Send To is not null
              Top count 100          <- hard ceiling. A bad filter cannot fan out.

ACTION 2      Compose the preview: row count + template name

CONDITION     PREVIEW GATE. Nothing sends until the analyst confirms
              count and template. Non-negotiable.

APPLY TO EACH
  ACTION 3    Build the HTML body from the merge fields
  ACTION 4    Outlook · Send an email (V2)
                 To:  Send To      <- the FA
                 Cc:  Send Cc      <- their BOAs
                 CC also the ops mailbox
  ACTION 5    Patch QV_Trace_Notes: append "Emailed {template} {utcNow()}"
              to LastAction, set NextFollowUpDate
  ACTION 6    Append "Email sent" to tbl_Trace_Audit
```

**Action 5 is what closes the loop** — the email writes its own note back, so the next
refresh shows the trace as actioned without anybody typing it. That is the difference
between automating the send and automating the workflow.

### Template

```
To:   {Send To}
Cc:   {Send Cc}
Subj: Package trace {CASE #} — {UPS Status} — action needed

{FA Name},

Tracking {Tracking Number}, shipped {Manifest Date}, is {Days Open} days open.

  UPS status      {UPS Status}
  Our status      {Review Status}
  Issue           {Exception Description}
  Ship to         {Ship To Name}

{Recommended Action}

Reply to this email or update the trace log. We follow up in {TicklerType}.

— UPS Quantum View · Operations
```

`{Recommended Action}` comes free — `QV_Enriched` already writes a specific instruction per
exception type ("Notify branch: package at UPS Access Point. Pickup required within 5
business days."). Merging it turns a notification into an instruction, which is most of the
efficiency win.

**Never merge `Contents Description` or anything gated by `PII` into an email body**
without checking the PII flag first. That column exists for a reason.

### Templates by exception type

| Template | Trigger | Send |
|---|---|---|
| Access Point Pickup | `Access Point` | on demand |
| Delivery Attempt | `Delivery Attempt` | on demand |
| Address Correction | `Address Issue` | on demand |
| Refused / Wrong Recipient | `Delivery Issue` | on demand |
| Missing Docs | `Customs / Documentation` | on demand |
| Lost / Damaged escalation | `Package Issue` | on demand |
| Daily tickler digest | `NextFollowUpDate <= today` | scheduled 07:30 CT |

### If flow creation is blocked

Some Edward Jones tenants restrict it. **Check this before building anything else.** The
layout and the pipeline are unchanged; only the automation swaps, and every timestamp stays
persistent:

| Blocked | Fallback |
|---|---|
| Flow 1 | Keep the list. An Office Script bound to a button in the log workbook stamps a static timestamp on run |
| Flow 2 | Export `Mail_Merge_Queue` to CSV; Outlook native mail merge. Same templates, same To/Cc columns, less automation |
| Flow 3 | Send the tickler digest by hand from the exported queue |

---

## Order

| | Step | Gated on |
|---|---|---|
| 1 | Confirm the tenant permits Flows and Lists | nothing — do it first |
| 2 | Apply `model-fixes-v3.pq` §4–§6 and `model-updates-v3.tmdl` | — |
| 3 | Check `checks/10-contact-routing.dax` reads **Contactable 90** | step 2 |
| 4 | Fill in the four missing `Home_Office_Contacts` addresses | — |
| 5 | Create `QV_Trace_Notes`, seed the 95 open traces | — |
| 6 | Repoint `Trace_Notes` (§7), prove one note round-trips | step 5 |
| 7 | Flow 1 audit log | step 6 |
| 8 | Flow 2 mail merge, behind the preview gate, tested on 2–3 rows | steps 3 and 7 |
| 9 | Flow 3 tickler digest | step 8 |

**Steps 2–4 are worth doing on their own even if the flows never happen.** They take the
trace page from "nobody knows who to contact" to a named FA, a named BOA and a reason when
neither exists. The automation is what you do once that is true.

**Run every Power Apps and Power Automate connection on a service account.** Otherwise the
whole thing breaks the day you're on PTO or change roles.
