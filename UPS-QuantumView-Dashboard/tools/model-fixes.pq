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
