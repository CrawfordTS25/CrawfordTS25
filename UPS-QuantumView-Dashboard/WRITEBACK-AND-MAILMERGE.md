# Note write-back and mail merge — the build

Spec pages 12–13. This is the largest remaining piece and the only part of the build
that lives outside Power BI.

**What I can't do from here, and why.** The write-back panel is a **Power Apps visual**
and the send button is a **Power Automate visual**. Neither can be created by editing the
`.pbix` from outside Power BI Desktop — they carry an app ID and a connection that are
minted when you add them, against your tenant. Injecting hand-written visual JSON for a
type Desktop didn't author is also exactly what produced the unopenable files earlier in
this build; I'm not doing it again. So this document is the complete build, executable
end to end, and the placeholder panel on RESOLUTION QUEUE is left where it is until you
run it.

**What's already done.** The read side is finished and live in the file:

| Piece | State |
|---|---|
| Stable join key `Exception Key` | ✅ minted, drill-through keys on it |
| `tbl_Resolution_Input` merged onto `Resolutions Table` | ✅ left-outer on `Exception Key` |
| `Resolution Status` → `Tracker Status` | ✅ blank ⇒ "New / Needs Review", 1,039 rows carry `Open` |
| `Root Cause` · `Next Action` · `Notes` · `Last Updated` · `Closed Date` | ✅ columns exist, **0% populated** |
| `Selected Root Cause / Next Action / Notes` measures | ✅ built, on the RESOLUTION QUEUE detail panel |
| Notes panel placeholder | ✅ `650, 442, 606×254`, says "Not yet wired — build order pages 12–14" |

So every column the write-back needs to land in already exists and is already on screen.
What's missing is the thing that writes to them.

---

## Step 7 · The SharePoint List

Spec p.12. **The List is the system of record; Excel is an append-only log, never a
source.** Today `tbl_Resolution_Input` reads `ResolutionTracker.xlsx`, which can't hold a
persistent timestamp — an Excel `NOW()` recalculates on every open, so it can never tell
you *when* a change actually happened. A List's `Modified` field is written once, at
save, and never drifts. That's the audit trail.

Create a List named **`QV_Exception_Resolutions`**:

| Column | Type | Settings |
|---|---|---|
| `ExceptionID` | Single line of text | **indexed**, enforce unique values — this is `Exception Key` |
| `TrackingNumber` | Single line of text | for humans; never join on it |
| `Category` | Choice | seed from `Dim_ExceptionReason[Exception Category]` |
| `Status` | Choice | `Open` · `WIP` · `Resolved` · `Escalated` — see the literals note below |
| `RootCause` | Choice | seed the top causes; allow "Fill-in" |
| `NextAction` | Single line of text | |
| `ResolutionNote` | Multiple lines of text | **append changes to existing text = Yes** |
| `Owner` | Person or Group | the assigned analyst |
| `ClosedDate` | Date only | |
| `Created` · `Modified` · `Created By` · `Modified By` | Auto | system — do not add, do not edit |

> `ExceptionID` is `TRACKING|DESCRIPTION` uppercased — e.g.
> `1Z0708F90100725981|WE TRIED TO DELIVER TO THE BUSINESS, BUT IT WAS CLOSED. A SECOND
> ATTEMPT WILL BE MADE THE NEXT BUSINESS DAY.` That is long. **Index the column** or the
> lookup on every Patch will crawl once you're past 5,000 items, and SharePoint will
> throttle. If it turns out to be too long for comfort, hash it —
> `Text.From(Number.ToText(Binary.ToText(Text.ToBinary(key), BinaryEncoding.Base64)))` —
> but do it in `QV_Enriched` so the report and the List mint the *same* string. Never let
> the two derive it independently.

**Match the status literals to the model.** The measures test on exact strings and return
0 silently on a mismatch, which looks identical to a quiet week:

```
'Resolutions Table'[Resolved Exceptions]  -> Tracker Status = "Resolved"
'Resolutions Table'[Escalated Exceptions] -> Tracker Status = "Escalated"
```

Your model already contains one such mismatch: those measures say `"Escalated"` while
`Current_Open_Trace[Review Status]` stores `"Escalate"`. Pick one vocabulary, put it in
the List's Choice column, and run `tools/checks/5-status-vocabulary.dax` after the first
real resolution flows through.

**Seed 5–10 items** keyed to real `Exception Key` values, then confirm a note
round-trips before building anything on top.

### Repoint `tbl_Resolution_Input` at the List

One query change. Everything downstream — the merge, `Tracker Status`, the ageing, the
measures, the panel — is unaffected:

```m
let
    Source = SharePoint.Tables(
                 "https://<tenant>.sharepoint.com/sites/<site>",
                 [ApiVersion = 15] ),
    List   = Source{[Title = "QV_Exception_Resolutions"]}[Items],
    #"Renamed" = Table.RenameColumns( List,
        { {"ExceptionID",    "Exception Key"},
          {"Status",         "Resolution Status"},
          {"RootCause",      "Root Cause"},
          {"NextAction",     "Next Action"},
          {"ResolutionNote", "Notes"},
          {"Modified",       "Last Updated"},
          {"ClosedDate",     "Closed Date"} } ),
    #"Changed Type" = Table.TransformColumnTypes( #"Renamed",
        { {"Exception Key", type text}, {"Resolution Status", type text},
          {"Root Cause", type text}, {"Next Action", type text},
          {"Notes", type text}, {"Last Updated", type datetime},
          {"Closed Date", type date} } )
in
    #"Changed Type"
```

`SharePoint.Tables` refreshes in the cloud with **no on-premises gateway**, which is the
single biggest operational advantage available to you here — the UNC-path queries all
need one.

---

## Step 8 · The Power Apps write-back panel

Spec p.12. This replaces the placeholder shape and textbox at `650, 442, 606×254` on
RESOLUTION QUEUE.

1. On RESOLUTION QUEUE, delete the placeholder **textbox** (keep the panel shape behind
   it — it's the card background).
2. `Insert → Power Apps` → position it to **`X 662 · Y 478 · W 582 · H 204`** under
   `Format → General → Properties → Position`. That's the placeholder's exact footprint,
   so nothing else moves.
3. Drag these into the visual's **data** well, in this order — they become
   `PowerBIIntegration.Data`:

   ```
   'Resolutions Table'[Exception Key]
   'Resolutions Table'[Tracking Number]
   'Resolutions Table'[Tracker Status]
   'Resolutions Table'[Root Cause]
   'Resolutions Table'[Next Action]
   'Resolutions Table'[Notes]
   ```

4. **Create new** → Power Apps Studio opens with the data context wired.

**In the app.** Add the List as a data source (`QV_Exception_Resolutions`), then:

```powerfx
// App.OnStart — nothing needed; PowerBIIntegration.Data arrives with the selection

// lblExceptionId.Text
First(PowerBIIntegration.Data).Exception_x0020_Key

// drpStatus.Items
Choices(QV_Exception_Resolutions.Status)

// drpStatus.DefaultSelectedItems
LookUp(
    Choices(QV_Exception_Resolutions.Status),
    Value = First(PowerBIIntegration.Data).Tracker_x0020_Status
)

// txtNote.Default
""                                    // always start empty; the List appends

// btnSave.DisplayMode — nothing saves without a row selected and a note typed
If( IsBlank(First(PowerBIIntegration.Data).Exception_x0020_Key)
    Or IsBlank(Trim(txtNote.Text)),
    DisplayMode.Disabled, DisplayMode.Edit )

// btnSave.OnSelect
With(
    { key: First(PowerBIIntegration.Data).Exception_x0020_Key,
      trk: First(PowerBIIntegration.Data).Tracking_x0020_Number,
      existing: LookUp(QV_Exception_Resolutions, ExceptionID = key) },
    Patch(
        QV_Exception_Resolutions,
        Coalesce( existing, Defaults(QV_Exception_Resolutions) ),
        {
            ExceptionID:    key,
            TrackingNumber: trk,
            Status:         drpStatus.Selected,
            RootCause:      drpRootCause.Selected,
            NextAction:     txtNextAction.Text,
            ResolutionNote: txtNote.Text,       // append-on = the List keeps history
            Owner:          { '@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser",
                              Claims: "i:0#.f|membership|" & Lower(User().Email),
                              DisplayName: User().FullName, Email: User().Email },
            ClosedDate:     If( drpStatus.Selected.Value = "Resolved", Today(), Blank() )
        }
    );
    Reset(txtNote);
    Notify( "Saved — refresh the report to see it", NotificationType.Success )
)
```

`Patch` with `Coalesce(existing, Defaults(...))` is an **upsert** — it updates the item
if one exists for that key and creates it if not. That matters: your queue has 8,724
exceptions and the List will only ever hold the ones somebody has touched.

**Save, publish, and share the app with the ops team** — a Power Apps visual only works
for people who have access to both the app and the List.

✅ **Round-trip test before you go further:** select a queue row, type a note, Save,
check the List item, refresh the report, confirm the note appears in the detail panel and
`Tracker Status` moves off "New / Needs Review".

---

## Step 9 · Flow 1 — the audit log

Spec p.12. Append-only. Each action is a new row, never an overwrite; that history is
what feeds the "Emails Sent" and "Avg Resolution" KPIs later.

```
TRIGGER    SharePoint · When an item is created or modified
           Site: <site>   List: QV_Exception_Resolutions

ACTION 1   Excel Online (Business) · Add a row into a table
           File:  .../Report Data/QV_Audit_Log.xlsx
           Table: tbl_Audit
           Timestamp (UTC) : utcNow()
           ExceptionID     : triggerOutputs()?['body/ExceptionID']
           Action          : if(equals(triggerOutputs()?['body/Status/Value'],
                                       triggerOutputs()?['body/{VersionNumber}']),
                                'Note saved', 'Status change')
           Status          : triggerOutputs()?['body/Status/Value']
           By              : triggerOutputs()?['body/Editor/DisplayName']
```

Create `QV_Audit_Log.xlsx` first with a real Excel **table** named `tbl_Audit` and those
five columns — the connector writes to tables, not sheets.

> **Use `utcNow()` in the flow, not a formula in the sheet.** An Excel `NOW()`
> recalculates every time the file opens, so it can't record when anything happened. This
> is the same reason the List is the system of record.

---

## Step 9b · Flow 2 — the mail merge

Spec p.13. **The preview gate is non-negotiable** — the Send button opens a preview of the
merged batch and nothing dispatches until the analyst confirms count and template. That's
the guardrail against a 148-email misfire.

### Blocker first: `Branch_Contacts` returns 500 empty rows

Every column is null on every row. The `Promoted Headers` step is promoting a header row
from a sheet whose data doesn't line up beneath it, and it loads without erroring, which
is why it went unnoticed. **`{Owner.Email}` has nothing to resolve against until this is
fixed.** Open the query, look at what `#"branch email_Sheet"` actually returns before the
promote, and adjust the navigation — it's almost certainly reading the wrong sheet range.

`Current_Open_Trace[CONTACT INFO]` does hold real addresses (72 of 95) and is the working
recipient source on the trace side today. Two viable routes:

- **Preferred** — fix `Branch_Contacts`, relate it to the queue on FA number, resolve
  `{Owner.Email}` from the roster.
- **Interim** — use the List's `Owner` person column, populated by the Power Apps panel
  from `User()`. Every emailed exception has an owner because somebody touched it. This
  works from day one and needs no roster.

### The flow

```
TRIGGER       Power BI · Power Automate visual button
              Passes: 'Resolutions Table'[Exception Key], [Tracking Number],
                      Dim_ExceptionReason[Exception Category],
                      'Resolutions Table'[Age Days]

ACTION 1      SharePoint · Get items
              Filter Query: Status eq 'Open'
              Top Count:    100          <- hard ceiling; a bad filter can't fan out

ACTION 2      Compose · preview payload
              length(body('Get_items')?['value'])  + the template name

CONDITION     Preview gate — approval or a confirmed second click.
              @greater(length(body('Get_items')?['value']), 0)

APPLY TO EACH body('Get_items')?['value']
  ACTION 3    Compose · build the HTML body, substituting merge fields
  ACTION 4    Office 365 Outlook · Send an email (V2)
              To:  items('Apply_to_each')?['Owner/Email']
              CC:  <ops mailbox>
  ACTION 5    Excel · Add a row into tbl_Audit
              Action = 'Email sent', Timestamp = utcNow()
```

### Template

```
To:   {Owner.Email}
Subj: Action needed — Exception {ExceptionID} ({Category})

Hi {Owner.FirstName},

Shipment {TrackingNumber} has an open exception: {Category}, aging {AgeDays} days.
{RecommendedAction}

Please review in the Resolution dashboard and update status by {DueBy}.

— UPS Quantum View · Operations
```

`{RecommendedAction}` comes free — `QV_Enriched` already writes a specific instruction per
exception type ("Notify branch: package at UPS Access Point. Pickup required within 5
business days."), including for the two new types. Merging it turns a notification into an
instruction, which is most of the efficiency win.

### Template library

| Template | Trigger category | Key merge fields | Send |
|---|---|---|---|
| Address Correction | `Address Issue` | Tracking, Consignee, DueBy | on demand |
| Delivery Refused | `Delivery Issue` | Tracking, Reason, Owner | on demand |
| Access Point Pickup | `Access Point` | Tracking, AP location, 5-day deadline | on demand |
| Delivery Attempt | `Delivery Issue` → `Delivery Attempt` | Tracking, attempt count, receiving hours | on demand |
| Missing Docs | `Customs / Documentation` | Tracking, DocType, DueBy | on demand |
| Daily Aging Digest | `Age Days > 7` | count, top-10 table | scheduled 07:30 CT |

Two of those categories — **Delivery Attempt** and **Customs / Documentation** — only
exist once the classifier fix lands. Delivery Attempt is 1,273 rows, 15% of the queue, and
it's the one where an email actually changes the outcome: the branch tells UPS when
somebody will be there.

**Place the button** on RESOLUTION QUEUE at `X 662 · Y 690 · W 582 · H 28`, directly
under the write-back panel, using the Email token `#7C5CBF` from the theme.

---

## If flow creation is blocked

Spec p.16. Some Edward Jones tenants restrict it. The layout and the pipeline are
unchanged — only the automation swaps, and **every timestamp stays persistent**:

| Blocked | Fallback |
|---|---|
| Flow 1 (audit log) | Keep the List for write-back. Replace Flow 1 with an **Office Script** bound to a button in the log workbook that stamps a static timestamp on run. |
| Flow 2 (mail merge) | Export the filtered queue; use Outlook's native mail merge. Same templates, same merge fields, less automation. |
| Flow 3 (digest) | Skip, or send the aging summary manually from the exported queue. |

**Check this before you build anything in Step 9** — it's spec build-order step 2 for a
reason, and it decides whether Steps 9 and 9b are two days or two weeks.

---

## Order, and what gates what

| | Step | Gated on |
|---|---|---|
| 1 | Confirm tenant permits Flows + Lists | nothing — do it first |
| 2 | Create the List, seed 5–10 rows | — |
| 3 | Repoint `tbl_Resolution_Input` at the List | List exists |
| 4 | Embed the Power Apps panel, test the round trip | List + repointed query |
| 5 | Flow 1 audit log | round trip proven |
| 6 | Fix `Branch_Contacts` **or** commit to the List `Owner` route | — |
| 7 | Flow 2 mail merge behind the preview gate | Flow 1 + a recipient source |
| 8 | Flow 3 digest | Flow 2 proven on 2–3 rows |

**Run every Power Apps and Power Automate connection on a service account, not a personal
login.** Otherwise the write-back and every flow break the day you're on PTO or change
roles — spec p.15, and the single most common way builds like this die.
