# Locations — one place, checked against the model

From your path sheet, reconciled against what the queries actually read. **Three
discrepancies**, marked ⚠.

---

## The data folder

```
X:  X:\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data

UNC \\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data
```

**Always use UNC in queries and scheduled tasks.** `X:` is a per-logon-session mapping. The
Power BI Service has no drive letters, and a task running as the service account with
nobody logged on has no `X:` either — it fails with a path-not-found that looks like a
permissions problem and isn't.

| Folder | Role | Who writes |
|---|---|---|
| `Archive\` | landing zone, **and the only folder the model reads** | the exporter |
| `Morning QV\` | copies, written before 13:30 | the script |
| `Afternoon QV\` | copies, written at or after 13:30 | the script |
| `Processed\` | `_processed.csv` — what's been handled, so re-runs are cheap | the script |
| `Failed\` | a **copy** of anything unhandled, plus a `.reason.txt` | the script |
| `_logs\` | one log per month | the script |
| `QV_Automation_Helper_Lists.xlsx` | lookup lists — `Home_Office_Contacts` reads a sheet here if present | you |

Nothing writes to `Archive`. Not the script, not the model. That invariant is what makes a
failed or double-fired run harmless.

### ⚠ 1 · `QV_RAW` is pointed somewhere else

| | |
|---|---|
| Your path sheet | `…\Administrative Services-Solutions\`**`Power BI Reporting\Report Data`**`\QV_Data` |
| `QV_RAW` in the .pbix | `…\Administrative Services-Solutions\`**`Quantum View`**`\QV_Data` |

Different parent folder. Check which one your last successful refresh actually read — if
the old path still resolves, **you have two `QV_Data` folders and only one of them is being
fed.** `model-fixes-v3.pq` §1 uses the path sheet's.

### ⚠ 2 · It must point at `Archive\`, not `QV_Data\`

`Folder.Files` **recurses**. Pointed at `QV_Data` it reads every export once per folder it
appears in — Archive plus both run folders — and Total Shipments multiplies with no error
anywhere. It would also try to parse `QV_Automation_Helper_Lists.xlsx` as a 34-column CSV.

This isn't hypothetical: those folders exist on your share today. Archive-only is what makes
the layout safe.

---

## Rosters

```
Your path sheet     X:\hrdi_report_pickup
Branch_Contacts_All …\Power BI Reporting\Report Data\Rosters\
```

### ⚠ 3 · Two different locations, and the second one works

The loaded model shows `Source Folder = \\nfpgshare-1…\Report Data\Rosters\` with 46,080
rows across 21,073 FAs and 25,007 BOAs, refreshed 06:49 the morning you sent the file. So
somebody is copying `hrdi_report_pickup` → `Report Data\Rosters`, or the pickup folder is
the upstream drop.

**I've left this alone** — it works, and breaking a working roster to remove a copy step is
a bad trade the week before rollout. But it's worth knowing:

- if the copy is manual, the roster is as fresh as the last time someone remembered
- `Branch_Contacts_All` already picks the newest file per prefix, so pointing it straight at
  `\\nfpgshare-1…\export\hrdi_report_pickup` would remove the copy step entirely
- `[Latest Roster Modified]` is on the model — watch it. If it stops moving, the copy stopped

The old `Branch_Contacts_Old` query has a column literally named
`X:\hrdi_report_pickup\FA_Roster\`, which is the provenance row it accidentally promoted to
a header. That's the tell that the pickup folder is the true origin.

---

## The trace notes list

```
Site  https://ejprod-my.sharepoint.com/personal/p258239_edwardjones_com
List  Trace_Master_Streamlined_
```

**`Trace_Notes` is not pointed at this.** It still reads
`…\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx`, which is the abandoned copy
— hence 199 blank rows out of 200 and a join that lands on 1 of 95 traces. `model-fixes-v3.pq`
§7 repoints it.

### ⚠ It's on a personal OneDrive

`-my.sharepoint.com/personal/` is one individual's OneDrive, not a team site.

| | |
|---|---|
| **Lifecycle** | deprovisioned when that person leaves or changes roles — read-only, then gone, typically 30–93 days. The dashboard stops refreshing and the notes history goes with it |
| **Credentials** | Service refresh must run on **that person's** account. It cannot be moved to a service account, because the site belongs to the human |
| **Access** | per-item sharing rather than site membership |

Every other "use a service account" note in this build is a policy choice. This one is a
structural block — you *cannot* comply while the list lives there.

Copy the list to a team site and change `SiteUrl`. Ten minutes, every column name survives.

---

## Other sources, unchanged and working

| Query | Path |
|---|---|
| `Dim_Account` | `…\Report Data\UPS Acct Info .xlsx` → table `tbl_Account_List` |
| `tbl_Resolution_Input` | `…\Report Data\ResolutionTracker.xlsx` → table `Res_Tracker_` |
| `Trace_Active` · `Trace_Notes` (current) | `…\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx` |
| `Master Coordinate Table` | `…\Report Data\Master Coordinate Table.csv` |

`UPS Acct Info .xlsx` still needs `A25T52` added and the table range extended to `A1:L25` —
it's the entire unmatched remainder on both fact tables.

---

## Where the same value lives twice

Two constants are duplicated by necessity. Change one, change the other:

| Value | Places |
|---|---|
| **13:30** cutoff | `qv-file-automation.ps1` `$CutoffHour/$CutoffMinute`, and `model-fixes-v3.pq` §1 |
| **QV_Data root** | the same two files |

If they drift, the share and the dashboard disagree about which run a file belongs to, and
nothing errors.
