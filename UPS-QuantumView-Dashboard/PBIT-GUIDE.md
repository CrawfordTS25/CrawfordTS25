# Using a `.pbit` with a `.pbix`

## The short answer

**You can't apply a `.pbit` to an existing `.pbix`.** There is no import-template
command in Power BI Desktop. A template is a *starting point*, not a patch — opening one
always produces a brand-new report, never a modification of a file you already have.

So the question really resolves into one of four things, and they have different answers.

| What you actually want | How it works |
|---|---|
| Start a new report from a template | `File → Open` the `.pbit`. Supported, one step |
| Move **model** objects from a template into an existing `.pbix` | TMDL view, copy the script across. Supported |
| Move **report** pages from a template into an existing `.pbix` | Copy/paste visuals page by page. Works, but fiddly |
| Ship the build to someone without shipping the data | This is what `.pbit` is *for* |

---

## What a `.pbit` actually is

Same OPC zip package as a `.pbix`, minus the data.

| Carries | Does not carry |
|---|---|
| Every Power Query query and parameter | Any data rows at all |
| The full model schema — tables, columns, measures, relationships, hierarchies, RLS roles, format strings | Cached visual results |
| The entire report layout and theme | Your credentials |

Your `.pbix` is 7.03 MB. The equivalent `.pbit` will be a few hundred KB, because 7 MB of
it is compressed data.

---

## Creating one from your file

```
File → Export → Power BI template → type a description → Save
```

The description is worth writing properly — whoever opens the template sees it in the
prompt dialog, and it is the only context they get.

**If Export is greyed out**, you have unapplied query changes. Apply them first. (Your
current file is in exactly that state — see the `fnClassifyException` warning in the main
instructions.)

---

## Opening one

`File → Open` the `.pbit`, or double-click it. Desktop then:

1. **Prompts for every parameter** marked Required, pre-filled with the value that was
   current when the template was exported
2. **Runs a full refresh** against every source
3. Builds the model and the report
4. Hands you an **Untitled** report — `Save As` to make it a `.pbix`

> **Step 2 is the one that bites.** A template open is a full refresh, so every source has
> to be reachable *and* credentialed on that machine, right then. On this build that means
> the `\\nfpgshare-1...` UNC share — open the template off the network and it fails on the
> first query. This is one more reason to move the ingestion to `SharePoint.Files` before
> you distribute anything.

---

## Moving *model* objects into an existing `.pbix`

This is the supported "merge" path, and it is what the `.tmdl` files in `tools/` already
are.

1. Open the template (it becomes an untitled `.pbix`)
2. `View → TMDL view`
3. In the TMDL explorer, select the tables / measures / relationships you want and script
   them out
4. Copy that script
5. Open your real `.pbix`, `View → TMDL view`, paste, read it, **Apply**

Two things to know before you do it:

- **`createOrReplace` replaces the whole object.** Scripting out a table brings its
  partition, its columns and its measures with it — if the target already has that table
  with different queries behind it, you will overwrite them. Script the smallest thing
  that does the job: usually just the measures.
- **Relationships need both endpoints to exist first.** Same ordering rule as the scripts
  in `tools/` — that is why `model-updates-v2.tmdl` §9 has to wait for the trace date
  columns.

---

## Moving *report* pages into an existing `.pbix`

No import command. What works:

1. Open both files in Desktop (two windows)
2. On the source page, click the canvas and `Ctrl+A`, then `Ctrl+C`
3. In the target file, add a page and `Ctrl+V`

Fields rebind **by name**. Anything the target model doesn't have comes across as a broken
visual with a "can't find field" error — which is recoverable, but it means the model has
to go first.

Background shapes and locked objects paste too, but page-level settings (canvas size, page
background, drill-through configuration, page filters) **do not**. You reset those by hand.

For anything more than a page or two it is cheaper to start from the template and repoint
its queries than to paste pages into an existing file.

---

## Why `.pbit` is worth using on this build specifically

Five concrete reasons, in rough order of payoff.

**1. Parameters, done properly.** The SharePoint-versus-folder switch in
`MEASURE-SWEEP.md` §5 is exactly what a template prompt is for. Define `SourceMode`,
`LandingFolder` and `SharePointSite` as real Power Query parameters (`Home → Manage
Parameters`, not just a `let` step) and mark them Required. Whoever opens the template
gets asked for them before a single query runs, so the same template serves the test
environment and production without anyone editing M.

**2. No data leaves the building.** A `.pbit` contains zero rows. Your `.pbix` carries
92,630 manifest rows including client names and ship-to addresses. For an Internal Use
Only build, that is the difference between handing someone the design and handing them the
data.

**3. The sensitivity-label problem disappears.** `SecurityBindings` is a tamper binding
computed over the whole package, which is why every edited copy in this project has needed
the label stripped and re-applied. Desktop rebuilds a template from scratch on open, so
there is nothing to invalidate. If this build has to go to another person or another
tenant, `.pbit` is the clean vehicle.

**4. It is version-controllable in a way a `.pbix` is not.** In a `.pbix` the model lives
in `DataModel` — a compressed Analysis Services backup, opaque to everything except Power
BI. In a `.pbit` the same model is `DataModelSchema`: plain JSON. Commit a `.pbit` at each
milestone and you get a diff you can actually read. Commit a `.pbix` and you get "binary
files differ."

**5. It would let me edit the model directly.** This is the one worth thinking about.
Every model change in this project has had to be written as a script for you to paste in
Desktop, because `DataModel` cannot be edited from outside Power BI — that constraint is
why `model-updates-v2.tmdl` and `contacts-and-freshness.tmdl` exist in the form they do.
`DataModelSchema` in a `.pbit` is editable JSON. **Export a `.pbit` and send it to me and I
can make measure, column and relationship changes directly**, hand it back, and your
Desktop work drops to: open it, enter the parameters, Save As. That turns a 55-minute
runbook into about five minutes.

The catch is honest and worth stating: a template open is a full refresh, so you would
need every source reachable at that moment, and the report layer still has the same
copy-paste constraints. But for model work specifically it is a materially better loop
than what we have been doing.

---

## A rollout pattern that works

| | |
|---|---|
| **Working file** | the `.pbix` on your machine. Never shared directly |
| **Versioned artifact** | export a `.pbit` at each milestone, commit that |
| **Distribution** | publish the App from the Service. Nobody downloads either file |
| **Handover / DR** | the `.pbit` plus this repo reconstructs the whole build from nothing |

The last row is the one people skip and then regret. Right now, if your machine died
tomorrow, rebuilding this dashboard means re-deriving several weeks of decisions. A
`.pbit` in source control means it means opening a file.

---

## Gotchas, collected

| | |
|---|---|
| Export greyed out | apply pending query changes first |
| Template open fails immediately | a source is unreachable or uncredentialed — it is a full refresh, not a lazy load |
| Parameters show the wrong defaults | they bake in whatever was current at export; re-export after changing them |
| A broken query is still broken | `.pbit` carries queries verbatim, errors included. It is not a repair mechanism |
| Pasted visuals show "can't find field" | the model has to be in place before the report layer |
| Page filters and drill-through vanish on paste | page-level settings do not travel with copied visuals |
| RLS roles carry, role *members* do not | membership is assigned in the Service, per workspace |
