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
