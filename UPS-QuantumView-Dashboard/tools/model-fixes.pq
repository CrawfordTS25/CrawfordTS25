// =============================================================================
// Quantum View - Power Query fixes
//
// These three changes cannot be shipped inside the .pbix. Measures can (see the
// "Script 2" tab in TMDL view); Power Query steps live in the DataModel part,
// which is a compressed Analysis Services backup - rewriting it outside Power BI
// Desktop risks the file not opening at all.
//
// Apply in Desktop: Home > Transform data > pick the query > Advanced Editor.
// Each block below says which existing step it replaces.
// =============================================================================


// -----------------------------------------------------------------------------
// 1. REFRESH ANCHOR                                     (master spec p.9)
//
// New query named "Refresh". One row, re-stamped at each refresh. Because it
// evaluates at refresh time rather than on every interaction, aging stops drifting
// between clicks and starts agreeing with the audit log.
//
// Set Enable Load = ON for this one - it must reach the model.
// -----------------------------------------------------------------------------
let
    Now = DateTimeZone.UtcNow(),
    T   = #table( {"StampUTC"}, { { Now } } )
in
    T


// -----------------------------------------------------------------------------
// 2. AGE DAYS - measure case age, not run recency        (master spec p.8)
//
// WHY: today [Age Days] holds only as many distinct values as there are run dates.
// In the test extract that is six - 1, 11, 12, 14, 21, 22 - and each is exactly
// (2026-07-28 minus one of the six QV run dates). So it measures days since the run
// that emitted the row, not days since the exception was raised. [Avg Age (Days)]
// therefore averages run recency, and [Age Bucket] collapses to "most recent run"
// vs "an older run" wearing day labels.
//
// FIX: anchor to the Refresh stamp above, and measure from when the exception was
// FIRST seen. Replace the existing "Age Days" custom-column step in the query that
// feeds Resolutions Table.
// -----------------------------------------------------------------------------
let
    Src        = #"PREVIOUS STEP",

    // earliest run each Exception Key ever appeared in = when we first saw it
    FirstSeen  = Table.Group( Src, {"Exception Key"},
                     {{ "First Seen", each List.Min([Run Date]), type date }} ),

    Joined     = Table.NestedJoin( Src, {"Exception Key"},
                     FirstSeen, {"Exception Key"}, "fs", JoinKind.LeftOuter ),
    Expanded   = Table.ExpandTableColumn( Joined, "fs", {"First Seen"}, {"First Seen"} ),

    // anchor is the refresh stamp, never DateTime.LocalNow() / DateTime.FixedLocalNow()
    Anchor     = DateTime.Date( Refresh{0}[StampUTC] ),
    AgeDays    = Table.AddColumn( Expanded, "Age Days",
                     each Duration.Days( Anchor - [First Seen] ), Int64.Type ),

    // rebucket against the SLA bands the SOP actually uses, so the column stops
    // having a hole where no run happened
    AgeBucket  = Table.AddColumn( AgeDays, "Age Bucket", each
                     if [Age Days] <= 1 then "0-1 Days"
                     else if [Age Days] <= 2 then "2 Days"
                     else if [Age Days] <= 7 then "3-7 Days"
                     else "8+ Days", type text )
in
    AgeBucket

// If a case should stop ageing once it is resolved, freeze it instead:
//     each if [Tracker Status] = "Resolved"
//          then Duration.Days( [Closed Date] - [First Seen] )
//          else Duration.Days( Anchor - [First Seen] )


// -----------------------------------------------------------------------------
// 3. TRACE_NOTES - join on Exception Key                 (confirmed by owner)
//
// WHY: the merge keys on CASE # / Tracking Number, populated on 1 of 200 note rows,
// so notes resolve for 1 of 95 trace cases. Exception Key is the real key.
//
// Also pulls in the four columns the Trace spec needs that were never merged:
// Legal Notified (what "Notify Legal" keys on), Claim Required, Assigned To and
// Contents Description.
//
// Replace the existing Trace_Notes merge step in Current_Open_Trace.
// -----------------------------------------------------------------------------
let
    Src    = #"PREVIOUS STEP",

    Notes  = Table.SelectColumns( Trace_Notes, {
                 "Exception Key", "Trace Status", "PII", "Delivery Confirmed",
                 "Last Action", "Next Follow-up Date", "Tickler Type",
                 "Contents Description", "UPS Trace Number", "Claim Required",
                 "Claim Status", "Refund Amount", "Legal Notified", "Assigned To",
                 "Notes", "Closed Date" } ),

    // normalise BOTH sides - a trailing space or a casing difference in a
    // SharePoint text column is otherwise a silent join failure
    KeyL   = Table.AddColumn( Src,   "_k",
                 each Text.Upper( Text.Trim( Text.From([Exception Key]) ) ), type text ),
    KeyR   = Table.AddColumn( Notes, "_k",
                 each Text.Upper( Text.Trim( Text.From([Exception Key]) ) ), type text ),

    Joined = Table.NestedJoin( KeyL, {"_k"}, KeyR, {"_k"}, "n", JoinKind.LeftOuter ),
    Cols   = { "Trace Status", "PII", "Delivery Confirmed", "Last Action",
               "Next Follow-up Date", "Tickler Type", "Contents Description",
               "UPS Trace Number", "Claim Required", "Claim Status", "Refund Amount",
               "Legal Notified", "Assigned To", "Notes", "Closed Date" },
    Expand = Table.ExpandTableColumn( Joined, "n", Cols,
                 List.Transform( Cols, each "Trace_Notes." & _ ) ),
    Out    = Table.RemoveColumns( Expand, {"_k"} )
in
    Out

// Verify with the "Query 6 - Trace_Notes join health" tab in DAX query view.


// -----------------------------------------------------------------------------
// 4. STEP ZERO - re-mint Exception Key BEFORE notes accumulate  (spec p.3)
//
// Now that the SharePoint list keys on Exception Key, the key's stability is load
// bearing. Today it is:
//
//     TrackingNumber | <the entire UPS exception description text>
//
// ~150 characters of UPS prose. Reword a description upstream and every note written
// against it detaches - the exact failure spec p.3 calls "a broken audit trail, not a
// cosmetic bug". It also carries no date, so the same tracking + description on two
// manifest dates collapses into one key.
//
// Do this before real notes exist. After, it is a migration.
// -----------------------------------------------------------------------------
= Table.AddColumn( Source, "ExceptionID", each
      Text.Combine(
        { Text.Upper( Text.Trim( [Tracking Number] ) ),
          Text.Upper( Text.Trim( [Exception Category] ) ),
          Date.ToText( [Manifest Date], "yyyyMMdd" ) },
        "|" ),
      type text )

// Pick ONE of the three competing type columns for the middle segment first -
// [Exception Type], [Exception Type ] (trailing space) and [Exception Category]
// disagree on 67% of rows, so the key changes depending which you choose.


// =============================================================================
// 5. NOT POWER QUERY - two UI changes worth doing in the same sitting
// =============================================================================
//
// a) RELATIONSHIP DIRECTION.  Model view > QV_Output <-> Resolutions Table >
//    Cross filter direction = Both.  Filters currently run one way only
//    (QV_Manifest -> Resolutions Table -> QV_Output), so the Exceptions page
//    slicers reach only 2 of its 5 KPIs - Total Shipments, Successful Shipments
//    and Aged 8+ Days never move. One toggle, three KPIs un-frozen.
//
// b) NARROW THE MODEL.  QV_Manifest is 67.7% of the model and is referenced by zero
//    visuals - it feeds one measure that needs one column. Keep [Tracking Number],
//    drop the rest (Ship To Attention alone is 0.58 MB). Set Enable Load = OFF on
//    Res_Tracker and Trace_Active. Turn off Auto Date/Time (File > Options > Data
//    Load) to remove 12 hidden date tables both specs say to disable.
//    Combined: ~54% smaller, no visual change.


// =============================================================================
// 6. FOLDER INGEST + LATEST-WINS DEDUPE
//
// Written against your real column names.  Two things shaped it:
//
//   * there is no per-row scan-date column in your feed, so recency comes from
//     [Date modified] - the file stamp Folder.Files already emits.  In the current
//     extract that is 9 files with 9 monotonic timestamps, which is a clean signal.
//
//   * history and current state are different tables.  Run Coverage and the trend
//     need every row ever ingested; the queue needs one row per exception.  Keep
//     both: QV_Output stays the full stack, Resolutions Table becomes the deduped
//     current state.  Your model already splits this way (6,636 rows -> 2,175
//     exceptions); this makes the split explicit and repeatable.
// =============================================================================


// --- 6a. Parameter -----------------------------------------------------------
// Text parameter named LandingFolder.  If the drop is a SharePoint library, swap
// Folder.Files for SharePoint.Files below - same logic, and it refreshes in the
// cloud with NO on-premises gateway, which removes the most fragile part of the
// publish story (master spec p.4 and p.15).

    "\\\\CompanyServer\\Shared\\Reports\\QuantumView"


// --- 6b. QV_Ingest : stack every export in the folder ------------------------
// Enable Load = OFF.  Staging only.
let
    Files    = Folder.Files(LandingFolder),

    OnlyCsv  = Table.SelectRows(Files, each
                   Text.Lower([Extension]) = ".csv"
                   and Text.StartsWith(Text.Upper([Name]), "QUANTUMVIEW")),

    Parsed   = Table.AddColumn(OnlyCsv, "Rows", each
                   Table.PromoteHeaders(
                       Csv.Document([Content],
                           [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
                       [PromoteAllScalars = true])),

    // Carry the file stamp onto every row.  `let` captures the OUTER row's values
    // before entering the nested table's scope - without it, [Date modified] would
    // resolve against the inner row and fail.
    Tagged   = Table.AddColumn(Parsed, "Tagged", each
                   let
                       stamp = [Date modified],
                       fname = [Name]
                   in
                       Table.AddColumn(
                           Table.AddColumn([Rows], "Source File", each fname, type text),
                           "Date modified", each stamp, type datetime)),

    Stack    = Table.Combine(Tagged[Tagged]),

    // Drop the blank formatted rows before anything else touches them
    HasKey   = Table.SelectRows(Stack, each
                   [Tracking Number] <> null
                   and Text.Trim(Text.From([Tracking Number])) <> "")
in
    HasKey


// --- 6c. Stable key ----------------------------------------------------------
// MUST run after your categorisation step, because it consumes [Exception Category].
// This is section 4's key, restated here because dedupe is only ever as good as it.
// Normalise both components - a trailing space makes one exception look like two.
    Keyed = Table.AddColumn(Categorised, "Exception Key", each
                Text.Combine({
                    Text.Upper(Text.Trim(Text.From([Tracking Number]))),
                    Text.Upper(Text.Trim(Text.From([Exception Category]))),
                    Date.ToText(Date.From([Manifest Date]), "yyyyMMdd")
                }, "|"), type text)


// --- 6d. Latest wins : one row per exception ---------------------------------
// Reference QV_Ingest; this becomes Resolutions Table.
// Table.Buffer before Table.Distinct is not optional - without it the engine may
// discard the sort and keep an arbitrary row instead of the newest one.
let
    Src      = QV_Ingest,
    Sorted   = Table.Sort(Src, {{"Date modified", Order.Descending}}),
    Buffered = Table.Buffer(Sorted),
    Latest   = Table.Distinct(Buffered, {"Exception Key"}),

    // First-seen date per key, so ageing measures from when the exception appeared
    // rather than from the run that emitted the row (see section 2)
    FirstSeen = Table.Group(Src, {"Exception Key"},
                    {{"First Seen", each List.Min([Date modified]), type datetime}}),
    Joined    = Table.NestedJoin(Latest, {"Exception Key"},
                    FirstSeen, {"Exception Key"}, "fs", JoinKind.LeftOuter),
    WithFirst = Table.ExpandTableColumn(Joined, "fs", {"First Seen"}, {"First Seen"}),

    // Terminal status closes a case.  CONFIRM THIS LIST against production: in the
    // current extract [Status] is "Exception" on all 6,636 rows, so the terminal
    // vocabulary is unverified, and an unmatched value silently leaves everything
    // Active forever.  Point it at whichever column actually carries the outcome.
    Terminal  = {"DELIVERED", "RETURNED", "REFUND", "RESOLVED",
                 "RETIRED", "DENIED", "ABANDONED"},
    Flagged   = Table.AddColumn(WithFirst, "Is Active", each
                    if List.Contains(Terminal,
                          Text.Upper(Text.Trim(Text.From([Status])))) then 0 else 1,
                    Int64.Type)
in
    Flagged


// --- 6e. What this does and does not guarantee -------------------------------
// GUARANTEES: the newest export is always read; re-dropping or back-filling files
// cannot double-count; every exception resolves to exactly one current row.
//
// DOES NOT GUARANTEE ACCURACY.  Dedupe trusts the key. If the key moves, one
// exception becomes two and the count inflates quietly - which is why section 4
// must land BEFORE this runs daily, not after.
//
// And ingest is robust to duplicates but blind to GAPS. If a run never produced a
// file, nothing here can tell. The Run Coverage panel on the Exceptions page is the
// only thing that surfaces a missing run; watch it.


// =============================================================================
// 7. IF THE SOURCE BECOMES AN API
//
// Only step 6b knows where data comes from.  6c onward - key, dedupe, first-seen,
// flags - never reference the source, so in principle an API swaps one query and
// nothing downstream changes.  In practice there is one consequence to settle first.
//
// A FOLDER ACCUMULATES.  AN API ANSWERS "NOW".
//
// Folder.Files gives you an archive: 9 files = 9 point-in-time snapshots, and
// [Date modified] stamps each one.  That is what makes the trend, Run Coverage and
// latest-wins dedupe possible.  A live API call returns current state only.  Point
// Power Query straight at it and every refresh REPLACES the picture rather than
// adding to it - you lose run history, and the recency signal dedupe sorts on.
// =============================================================================


// --- 7a. The decision --------------------------------------------------------
//
// OPTION A - API writes files, Power Query still reads the folder   RECOMMENDED
//     UPS API -> small script/Flow -> landing folder -> section 6 unchanged
//   The API replaces the human in SOP 6.2, not the architecture.  History is kept,
//   [Date modified] still exists, dedupe still works, nothing below 6b changes, and
//   you can reprocess any past day because the files are still there.
//
// OPTION B - Power Query calls the API directly
//     UPS API -> Web.Contents -> model
//   Refreshes in the cloud with no gateway, which is a real advantage over a UNC
//   path.  But it is current-state only.  To keep history you then need incremental
//   refresh with a persisted partition, or to write results somewhere durable -
//   i.e. you rebuild the archive the folder was already giving you for free.
//
// Take Option A unless you specifically need on-demand intraday lookups.


// --- 7b. If you do go direct: the two things that break scheduled refresh -----
//
// 1. DYNAMIC DATA SOURCES.  A URL built by string concatenation cannot be refreshed
//    by the Service - it refuses to validate the source.  The base URL must be
//    static and everything variable must go in RelativePath / Query:
//
//        Web.Contents(
//            "https://onlinetools.ups.com",                    // static, always
//            [ RelativePath = "api/track/v1/details/" & id,    // variable here
//              Query        = [ locale = "en_US" ],
//              Headers      = [ Authorization = "Bearer " & token,
//                               #"Content-Type" = "application/json" ] ] )
//
// 2. OAUTH TOKEN LIFETIME.  UPS moved to OAuth 2.0; tokens are short-lived, so the
//    token cannot be a hard-coded parameter.  Fetch it in the same refresh:
//
//        GetToken = () =>
//            let
//                resp = Web.Contents("https://onlinetools.ups.com",
//                    [ RelativePath = "security/v1/oauth/token",
//                      Headers = [ #"Content-Type" = "application/x-www-form-urlencoded",
//                                  Authorization  = "Basic " & ClientCredsBase64 ],
//                      Content = Text.ToBinary("grant_type=client_credentials") ])
//            in
//                Json.Document(resp)[access_token]
//
//    Store the client id/secret as parameters, never in the query text.  Confirm
//    endpoint paths and your account's entitlements on the UPS developer portal -
//    do not take the paths above as verbatim.


// --- 7c. Columns you must synthesise -----------------------------------------
// Section 6 depends on five fields.  Four arrive in the payload.  One does not:
//
//   Tracking Number     UPS field
//   Manifest Date       UPS field
//   Status              UPS field
//   Exception Category  derived by your keyword mapping - keep that step
//   Date modified       Folder.Files METADATA. There is no equivalent in an API
//                       response, and dedupe sorts on it.
//
// So stamp it at retrieval time, from the Refresh anchor in section 1 rather than
// a volatile clock, so every row from one refresh shares one timestamp exactly as
// every row from one file does today:
//
//     Stamped = Table.AddColumn(Payload, "Date modified",
//                   each Refresh{0}[StampUTC], type datetime)
//
// Keep the column NAME. Everything downstream - and the Run Coverage panel on the
// Exceptions page - reads it.


// --- 7d. Check the shape of the endpoint before you scope this ---------------
// If the only available endpoint is per-tracking-number rather than a bulk feed,
// one refresh means one call per shipment:
//
//     2,127 calls to cover the exceptions currently in QV_Output
//    45,561 calls to cover everything in QV_Manifest
//
// That is slow, throttling-prone, and a poor fit for a daily bulk sweep. Bulk
// Quantum View delivery is historically a subscription that lands FILES - which is
// Option A again. Ask your UPS rep which of the two you are entitled to before
// committing to a build; the answer decides this whole section.


// =============================================================================
// 8. OPTION A - BUILD SHEET
//
//   UPS API  ->  fetcher  ->  landing folder  ->  section 6, unchanged
//
// The fetcher replaces the human in SOP 6.2. Nothing in the model changes, so the
// whole job is: produce a CSV that looks exactly like the portal export, land it in
// the folder, on a schedule, without corrupting anything when it fails.
// =============================================================================


// --- 8a. THE CONTRACT - match the export schema exactly ----------------------
// Your transform chain is built on these headers. Emit these 18, spelled and cased
// exactly like this, in this order:
//
//    1  Tracking Number                    10  Shipper Name
//    2  Service                            11  Shipper Address Line 1
//    3  Status                             12  Ship To Attention
//    4  Exception Status Description       13  Ship To Name
//    5  Exception Description              14  Ship To Address Line 1
//    6  Exception Resolution               15  Ship To Address Line 2
//    7  Manifest Date                      16  Ship To City
//    8  Original Scheduled Delivery Date   17  Ship To State/Province
//    9  Scheduled Delivery                 18  Ship To Postal Code
//
// Do NOT emit: Full Address, Is Issue, Carrier Delay Reason, Recommended Action,
// Tracking URL, Shipper Location, Exception Type, Exception Type , Exception
// Category, Exception Key, Run Date, Run Time, Date modified.  Every one of those
// is derived downstream; producing them either gets ignored or collides.
//
// Cross-check against SOP Appendix A before you build - that is the approved QV
// Manager field set, and it is the contract the portal export honours today.


// --- 8b. FILE NAMING ---------------------------------------------------------
// Section 6b filters on Text.StartsWith(Text.Upper([Name]), "QUANTUMVIEW"), so:
//
//     QuantumView_20260729_0930.csv        <- morning run
//     QuantumView_20260729_1500.csv        <- afternoon run
//
// UTF-8, comma-delimited, quoted. One file per run window, never appended to.


// --- 8c. WRITE ATOMICALLY - the failure everyone hits ------------------------
// Power Query can read a half-written file if a refresh lands mid-write, and it
// will not error - it will just ingest a truncated run. Write to a name the folder
// filter ignores, then rename:
//
//     write   _incoming_20260729_0930.tmp      (does not match QUANTUMVIEW*)
//     rename  QuantumView_20260729_0930.csv    (atomic on the same volume)


// --- 8d. FAILURE BEHAVIOUR - distinguish "no data" from "no run" -------------
// These are different and must look different:
//
//   API returned zero rows   -> DO write the file, headers only. A real quiet run.
//   API call failed          -> write NOTHING, and alert. A gap you can see.
//
// Never write a partial or empty file on error. An empty file is indistinguishable
// from a genuine zero-exception run, and it will quietly understate your numbers
// forever. A missing file at least shows up as a hole in Run Coverage.


// --- 8e. SCHEDULING ----------------------------------------------------------
// Two routes, matching the two the specs already assume:
//
//   POWER AUTOMATE (preferred - no machine to keep on, aligns with Flows 1-3)
//     Recurrence  weekdays, just after each SOP window (SOP 4: 08:00-10:00, 14:00-16:00)
//     HTTP        get OAuth token, then call the UPS endpoint
//     Compose     map JSON -> the 18 columns in 8a
//     Create file SharePoint/OneDrive, .tmp name
//     Rename      to QuantumView_*.csv
//     On failure  post to Teams; do not create a file
//
//   POWERSHELL + TASK SCHEDULER (fallback if flow creation is blocked - spec p.16)
//     Same sequence. Master spec p.4 already documents the Task Scheduler traps:
//     use the full \\server\share UNC path not a mapped drive, -ExecutionPolicy
//     Bypass for unsigned scripts, and remember an on-prem share still needs a
//     gateway for unattended Service refresh.
//
// If the landing folder is SharePoint, prefer Power Automate AND switch section 6b
// to SharePoint.Files - that combination needs no gateway at all.


// --- 8f. RETENTION - this will bite around month three -----------------------
// Every refresh re-reads every file in the folder. You are at 9 files for QV_Output
// and 20 for QV_Manifest today; at 4 runs a day that is roughly 1,000 a year, and
// refresh time grows with it.
//
//     keep    the last 90 days in the landing folder
//     archive older files to a sibling folder the query does not enumerate
//
// Archive rather than delete - the files are your only replay mechanism if a
// transform turns out to have been wrong. Move them; never let the fetcher delete.


// --- 8g. ORDER OF WORK -------------------------------------------------------
//   1. Confirm with UPS: bulk feed or per-shipment endpoint (decides feasibility)
//   2. Section 4 - re-mint Exception Key. BEFORE daily ingest, not after.
//   3. Section 1 + 2 - Refresh anchor and Age Days
//   4. Section 6 - folder ingest and dedupe
//   5. This section - the fetcher
//   6. Scheduled refresh, gateway if needed, service-account connections (spec p.15)
//
// Steps 2 and 3 come first for the same reason: automating the feed onto a moving
// key and a broken anchor produces fresher wrong numbers, arriving daily.


// =============================================================================
// 9. TRACE DATE COLUMNS - type them so a calendar can reach the trace side
//
// Every date column on Current_Open_Trace and Trace_Active loads as TEXT, which is why
// Dim Date cannot relate to either. No date slicer, no trend, no "opened vs closed",
// and no SLA maths on the page whose entire job is SLA.
//
// The values are clean and consistent - all M/D/YYYY - with two things that must
// become null rather than dates:
//
//   "Not Avail."   UPS placeholder            3 rows (Orig Sched), 2 rows (Sched)
//   1/3/1900       Excel epoch artifact      28 of 95 Follow-up rows
//
// The 1900 one matters more than it looks. Type that column naively and Dim Date's
// bounds stretch from 1900 to 2026 - about 46,000 rows - and every date axis becomes
// unreadable. It is a blank cell that was date-formatted, not a real follow-up.
//
// Apply to BOTH Current_Open_Trace and Trace_Active. Place it AFTER the Trace_Notes
// merge so the two merged columns are covered too.
// =============================================================================
let
    Src = #"PREVIOUS STEP",

    Sentinels = { "", "Not Avail.", "N/A", "NA", "TBD",
                  "1/3/1900", "1/2/1900", "1/1/1900", "12/30/1899" },

    // Culture is NOT optional. "7/8/2026" is 8 July under en-US and 7 August under
    // en-GB - the same string, two different dates. Without an explicit culture a
    // Service refresh can silently disagree with Desktop.
    fnDate = (v) as nullable date =>
        let
            t     = if v = null then null else Text.Trim( Text.From(v) ),
            clean = if t = null or List.Contains( Sentinels, t ) then null else t,
            out   = if clean = null then null
                    else try Date.FromText( clean, [Format = "M/d/yyyy", Culture = "en-US"] )
                         otherwise null
        in
            out,

    Typed = Table.TransformColumns( Src, {
        { "Manifest Date",                    fnDate, type nullable date },
        { "Original Scheduled Delivery Date", fnDate, type nullable date },
        { "Scheduled Delivery",               fnDate, type nullable date },
        { "Last Reviewed",                    fnDate, type nullable date },
        { "Follow-up",                        fnDate, type nullable date },
        { "Trace_Notes.Next Follow-up Date",  fnDate, type nullable date },
        { "Trace_Notes.Closed Date",          fnDate, type nullable date }
    })
in
    Typed

// Once Last Reviewed is a real date, recompute Days Since Review against the Refresh
// anchor from section 1 rather than whatever produced it before:
//
//     Table.AddColumn( Typed, "Days Since Review",
//         each if [Last Reviewed] = null then null
//              else Duration.Days( DateTime.Date( Refresh{0}[StampUTC] ) - [Last Reviewed] ),
//         Int64.Type )
//
// Sanity check after refresh: Follow-up should have 28 nulls, not 28 dates in 1900,
// and Dim Date should still start in 2026.
