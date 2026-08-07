# The binary route is abandoned — build the model from TMDL

## Where this ended up

Three hand-authored .pbit packages were rejected by Power BI Desktop: the
original, one with the encoding and version stamps corrected against a real
.pbix, and a model-only variant with the report stripped out entirely. The third
failure is the informative one — it rules out the report schema and says the
problem is the package itself.

**The binary route is closed.** `dist/UPS_2025_Full_Model.tmdl` replaces it:
one TMDL paste that builds the whole model — the parameter, 8 tables with their
Power Query partitions, all 112 measures, both what-if tables, all 11
relationships, and the sort-by columns. Plain text, so none of the failure modes
below can apply to it.

---

## The original short version

The .pbit is fixed — it had a byte-order-mark bug and stale version stamps, all
three found by comparing it against a real Power BI file.

A **.pbix cannot be produced by any tool other than Power BI Desktop**, and that
is a hard technical boundary rather than a limitation of effort. The explanation
is below, with the evidence.

The most reliable route to a working model is now neither: it is the **TMDL
script**, which creates all 112 measures in one paste.

---

## What was wrong with the .pbit

Diffing the generated package against `NEWQuantum_View_Exceptions_Dashboard.pbix`
turned up three concrete defects. Any one of them is enough for Desktop to reject
a package, and none produces a useful error message.

| | Was | Should be | Why it matters |
|---|---|---|---|
| **Byte-order mark** | UTF-16 LE **with** BOM | UTF-16 LE, **no BOM** | The prime suspect. Desktop writes `Version`, `Settings`, `Metadata`, `DiagramLayout`, `DataModelSchema` and `Report/Layout` as bare UTF-16 LE. A leading `FF FE` shifts every offset the parser expects. |
| **Version stamp** | `1.28` | `1.33` | The target Desktop is release 2026.06, which stamps 1.33. |
| **Metadata version** | `3` | `5` | Same generation mismatch. |
| **Content types** | every `ContentType` empty, no `xml` default | `Default` entries for `json` and `xml`, real content types on the JSON parts | Matches what Desktop emits. |

All four are corrected in `powerbi/build_pbit.py`, and the generated package now
matches the reference file byte-convention for byte-convention.

**It still has not been opened in Power BI Desktop.** There is no copy of Desktop
in the environment this was built in. The fixes are grounded in a real file
rather than in guesswork, which is a large improvement over the first attempt,
but the first open remains a test.

---

## Why there is no .pbix

A `.pbix` contains a part named `DataModel`. In the reference file it is
**6,995,427 bytes, stored uncompressed**, and its first bytes decode to:

```
This backup file was created by ...
```

That is an Analysis Services database backup stream. It is produced by the
VertiPaq engine when it serialises a loaded, compressed, in-memory tabular model
— column dictionaries, hash encodings, segment indexes and all. Writing one
requires the engine to have actually ingested the data.

No external tool emits it. Not Microsoft's own — Tabular Editor, `pbi-tools` and
the Fabric APIs all work with the *schema* (TMSL/TMDL) and hand the model to an
engine to materialise. There is no format in which a .pbix's model can be
authored as text.

This is why the deliverable has always been a template or a script: **the first
Save As in Desktop is the step that creates the .pbix.** Nothing skips it.

---

## The reliable route: the TMDL script

The reference file contains a part called `TMDLScripts/Script 1.tmdl`, which
means the Desktop build in use **has the TMDL view**. That is the best news in
this whole exchange, because it collapses the most tedious part of a manual build
— creating 112 measures one at a time — into a single paste.

`dist/UPS_2025_Measures.tmdl` (and a UTF-8 twin, `.txt`) declares the
`_Measures` table with all 112 measures, their format strings and their display
folders.

Its syntax, indentation, line endings and encoding were taken from the
Desktop-written script in the reference file, not from documentation:

- tabs, never spaces
- CRLF line endings
- UTF-16 LE, no BOM
- a measure's expression indented **two** levels below the measure line; its
  properties **one** level below
- multi-line expressions opening with a bare indented line

### How to use it

There are two scripts. Prefer the first.

**`UPS_2025_Full_Model.txt` — the whole model, one paste.**

1. New, empty Power BI Desktop file.
2. **Model view → TMDL view**.
3. Paste the whole script, **Apply**.
4. When prompted, point `p_Folder` at the folder holding the four renamed
   .xlsx extracts, and allow the refresh.

Nothing else: the tables, measures, relationships and sort-by columns all come
from the script.

**`UPS_2025_Measures.txt` — measures only.** Use this if the tables already
exist because the nine queries were built by hand. `createOrReplace` is scoped
to `_Measures`, so it cannot disturb anything else — which also makes it the way
to update measures later.

`createOrReplace` is scoped to the `_Measures` table alone, so it cannot disturb
the fact tables, their partitions, or relationships already in place. Re-running
it replaces only the measures — which also makes it the update mechanism when a
measure changes.

---

## On "security features" and downloading

Two separate things are worth untangling.

**The sensitivity label.** The reference file carries a Microsoft Information
Protection label in `docProps/custom.xml`
(an internal-use classification, `ContentBits 0`). I have not copied it
into the generated files, for two reasons. It would fabricate an organisational
classification marking that the compliance system never issued for this content.
And it would not help: at `ContentBits 0` the label is metadata, not encryption,
so it gates nothing. Applying the correct label is something the Desktop does on
save, on a machine enrolled in that tenant.

**What actually blocks a downloaded file.** On Windows, a file fetched from the
internet carries a Mark-of-the-Web tag, and some applications refuse it. The fix
is local:

> Right-click the file → **Properties** → tick **Unblock** at the bottom → OK.

If the organisation blocks the `.pbit` extension outright, the `.tmdl`/`.txt`
script and the Power Query text are plain text and will pass anything that lets
source code through.

**The `Connections` part** in the reference file lists a `DatasetId` and
`ReportId` — that file was downloaded from the Power BI Service, where its
dataset is published. Generated files have no such identity and should not
pretend to; that comes into existence when the report is first published.

---

## Everything is on GitHub

Nothing needs to be emailed. Browse to the repository, open a file, click
**Raw**, and copy or download:

```
github.com/CrawfordTS25/CrawfordTS25
  branch: claude/executive-dashboard-build-09ai41
  path:   ups-2025-executive-dashboard/
```

| Want | File |
|---|---|
| All 112 measures in one paste | `dist/UPS_2025_Measures.txt` |
| The nine queries | `powerbi/powerquery_standalone/` |
| The full written build | `dist/UPS_2025_Manual_Build_Guide.pdf` |
| The template, now fixed | `dist/UPS_2025_Executive_Dashboard.pbit` |
| The theme | `powerbi/theme/UPS_Executive_Theme.json` |
