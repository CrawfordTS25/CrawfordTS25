// =============================================================================
// Quantum View - Power Query fixes for NEWQuantum_View_Exceptions_Dashboard.pbix
//
// Apply in Home > Transform data.  Sections 1-3 are REQUIRED: without them the
// next refresh fails outright.  Sections 4-9 are correctness fixes.
//
// Each section says what it replaces and why.  Nothing here runs until you paste
// it into the Advanced Editor and click Close & Apply.
// =============================================================================


// -----------------------------------------------------------------------------
// SECTION 1 - fnClassifyException                                     (REQUIRED)
//
// THIS IS THE REFRESH BLOCKER.  The file carries an unapplied edit to QV_Enriched
// that calls fnClassifyException.  No query by that name exists in the model - I
// checked the applied model and all 29 queries.  The moment you hit Close & Apply
// or Refresh, QV_Enriched fails with "The name 'fnClassifyException' wasn't
// recognized", and QV_Output, Resolutions Table and every visual downstream go
// with it.  The data you see today is cached from a refresh that ran before the
// edit was made.
//
// New blank query, rename it exactly  fnClassifyException
//
// It returns a record so one pass produces the leaf type, the rollup category and
// enough diagnostics to tune the keyword list.  It NEVER returns null - unmatched
// descriptions fall to "Other Exception", which is what keeps 16% of the queue
// from vanishing into the dimension's blank row.
// -----------------------------------------------------------------------------

let
    // Both lookups are built ONCE, here in the enclosing let, and the function
    // closes over them.  Sorting or scanning a table inside the function body
    // would re-run it for every one of the ~46,000 rows.
    //
    // Keyword Table is authored in PRIORITY order and the Priority column makes
    // that explicit, so re-sorting the sheet can no longer change the answer.
    Rules = List.Buffer(
                Table.ToRecords(
                    Table.Sort( #"Keyword Table", {{"Priority", Order.Ascending}} ) ) ),

    Map   = Record.FromList( #"Exception Reason Map"[Exception Category],
                             #"Exception Reason Map"[Exception Type] ),

    fnClassifyException = ( description as nullable text ) as record =>
        let
            text    = if description = null then "" else Text.Upper( Text.Trim( description ) ),

            matches = if text = "" then {}
                      else List.Select( Rules, each Text.Contains( text, _[Keywords] ) ),

            hit     = if List.IsEmpty( matches ) then null else matches{0},
            leaf    = if hit = null then "Other Exception" else hit[Exception Type],
            rollup  = Record.FieldOrDefault( Map, leaf, "Other Exception" )
        in
            [ Matched Keyword     = if hit = null then null else hit[Keywords],
              Exception Type      = leaf,
              Exception Category  = rollup,
              Keyword Match Count = List.Count( matches ),
              All Keyword Matches = Text.Combine(
                                        List.Distinct(
                                            List.Transform( matches, each _[Exception Type] ) ),
                                        " | " ) ]
in
    fnClassifyException


// -----------------------------------------------------------------------------
// SECTION 2 - Exception Reason Map                                    (REQUIRED)
//
// New blank query, rename it exactly  Exception Reason Map
//
// One place where the taxonomy lives.  fnClassifyException reads it for the
// rollup; Dim_ExceptionReason IS it.  Edit the taxonomy here and both follow.
//
// "Other Exception" is the fallback member.  Without it the dimension has no row
// for unclassified exceptions and they disappear onto the blank member - which is
// exactly what is happening today to 1,406 of 8,724 rows.
// -----------------------------------------------------------------------------

let
    Source = Table.FromRows(
        {
            { "Address Issue",           "P.O. Box"                },
            { "Address Issue",           "Address Issue"           },
            { "Address Issue",           "Missing Suite Number"    },
            { "Address Issue",           "Incorrect Street Number" },
            { "Address Issue",           "Incomplete Address"      },
            { "Access Point",            "Access Point Hold"       },
            { "Delivery Issue",          "Refused Delivery"        },
            { "Delivery Issue",          "Wrong Recipient"         },
            { "Delivery Issue",          "Delivery Attempt"        },
            { "Carrier Delay",           "Carrier Delay"           },
            { "Schedule Change",         "Schedule Change"         },
            { "Package Issue",           "Package Issue"           },
            { "Customs / Documentation", "Customs / Documentation" },
            { "Other Exception",         "Other Exception"         }
        },
        type table [ Exception Category = text, Exception Type = text ]
    )
in
    Source


// -----------------------------------------------------------------------------
// SECTION 3 - Keyword Table                                           (REQUIRED)
//
// Replace the whole Keyword Table query.
//
// TWO CHANGES.
//
// (a) Priority is now an explicit column.  The classifier already depended on row
//     order - "ACCESS POINT ... HOLD" resolves to Access Point Hold only because
//     ACCESS POINT sits above HOLD - but nothing recorded that, so re-sorting the
//     table would silently reclassify thousands of rows.  Priority pins it.
//
// (b) 18 new rules, all appended BELOW the existing 29 so they can only ever
//     catch what nothing else caught.  Verified: 0 previously-classified rows
//     change.  Unclassified goes 1,394 -> 64 on Resolutions Table (16.0% -> 0.7%)
//     and 2,445 -> 207 on QV_Output (5.2% -> 0.4%).
//
//     The big one is Delivery Attempt: 1,273 rows of "WE TRIED TO DELIVER TO THE
//     BUSINESS, BUT IT WAS CLOSED", "THE RECEIVER WAS NOT AVAILABLE", "WE MISSED
//     YOU AGAIN".  That is 15% of the exception queue and it is a real, actionable
//     category - it was landing in the blank row.
//
//     Delete any rule you disagree with; the fallback catches whatever is left.
//
// The base 29 rules are unchanged in wording and order, so nothing you have
// already looked at moves.
// -----------------------------------------------------------------------------

let
    Rules = Table.FromRows(
        {
            // ---- existing 29 rules, unchanged, in their original order ----
            {  1, "P.O.",                       "P.O. Box"                },
            {  2, "PO BOX",                     "P.O. Box"                },
            {  3, "APARTMENT",                  "Address Issue"           },
            {  4, "SUITE",                      "Missing Suite Number"    },
            {  5, "STREET NUMBER",              "Incorrect Street Number" },
            {  6, "POSTAL CODE",                "Address Issue"           },
            {  7, "INCOMPLETE ADDRESS",         "Incomplete Address"      },
            {  8, "ACCESS POINT",               "Access Point Hold"       },
            {  9, "REFUSED",                    "Refused Delivery"        },
            { 10, "DOES NOT WANT",              "Refused Delivery"        },
            { 11, "CANCELED",                   "Refused Delivery"        },
            { 12, "MOVED",                      "Wrong Recipient"         },
            { 13, "NO LONGER IN BUSINESS",      "Wrong Recipient"         },
            { 14, "NOT LISTED",                 "Wrong Recipient"         },
            { 15, "COMPANY OR RECEIVER",        "Wrong Recipient"         },
            { 16, "MECHANICAL",                 "Carrier Delay"           },
            { 17, "WEATHER",                    "Carrier Delay"           },
            { 18, "LATE",                       "Carrier Delay"           },
            { 19, "DELAY",                      "Carrier Delay"           },
            { 20, "DISRUPTION",                 "Carrier Delay"           },
            { 21, "SORTED",                     "Carrier Delay"           },
            { 22, "OPERATING",                  "Carrier Delay"           },
            { 23, "RESCHEDULED",                "Schedule Change"         },
            { 24, "RECALCULATED",                "Schedule Change"        },
            { 25, "FUTURE DELIVERY",            "Schedule Change"         },
            { 26, "DELIVERY CHANGE",            "Schedule Change"         },
            { 27, "HOLD",                       "Schedule Change"         },
            { 28, "MISSING",                    "Package Issue"           },
            { 29, "VERIFY",                     "Package Issue"           },

            // ---- new: delivery attempted, nobody there. 1,273 rows ----
            { 30, "BUSINESS WAS CLOSED",        "Delivery Attempt"        },
            { 31, "IT WAS CLOSED",              "Delivery Attempt"        },
            { 32, "RECEIVER WAS NOT AVAILABLE", "Delivery Attempt"        },
            { 33, "WE MISSED YOU",              "Delivery Attempt"        },
            { 34, "SECURITY ACCESS",            "Delivery Attempt"        },
            { 35, "NOT AVAILABLE",              "Delivery Attempt"        },

            // ---- new: long tail ----
            { 36, "DAMAGED",                    "Package Issue"           },
            { 37, "VACANT",                     "Wrong Recipient"         },
            { 38, "BEING RETURNED",             "Refused Delivery"        },
            { 39, "SATURDAY DELIVERY",          "Schedule Change"         },
            { 40, "CHANGE OF DELIVERY",         "Schedule Change"         },
            { 41, "CHANGE DELIVERY",            "Schedule Change"         },
            { 42, "DELIVERY INSTRUCTIONS",      "Schedule Change"         },
            { 43, "REDIRECTED",                 "Schedule Change"         },
            { 44, "CUSTOMS",                    "Customs / Documentation" },
            { 45, "INVOICE",                    "Customs / Documentation" },
            { 46, "COMMODITY INFORMATION",      "Customs / Documentation" },
            { 47, "GOVERNMENT AGENCY",          "Customs / Documentation" }
        },
        type table [ Priority = Int64.Type, Keywords = text, Exception Type = text ]
    )
in
    Rules


// -----------------------------------------------------------------------------
// SECTION 4 - Dim_ExceptionReason                                     (REQUIRED)
//
// Replace the whole Dim_ExceptionReason query.
//
// It currently derives from Keyword Table and re-states the category mapping in a
// second if/then chain, so the taxonomy lives in two places that can drift.  Now
// it is the map, straight through, including the "Other Exception" member.
//
// 11 rows today -> 14.  Every value the classifier can emit has a row, so nothing
// can fall onto the blank member again.
// -----------------------------------------------------------------------------

let
    Source   = #"Exception Reason Map",
    Distinct = Table.Distinct( Source, {"Exception Type"} ),
    Sorted   = Table.Sort( Distinct, {{"Exception Category", Order.Ascending},
                                      {"Exception Type",     Order.Ascending}} ),
    Typed    = Table.TransformColumnTypes( Sorted, {{"Exception Category", type text},
                                                    {"Exception Type",     type text}} )
in
    Typed


// -----------------------------------------------------------------------------
// SECTION 5 - QV_Enriched
//
// Replace the whole QV_Enriched query.  This is your pending edit with three
// corrections; paste this instead of applying what is sitting in the editor.
//
// (a) fnClassifyException now exists (section 1).
//
// (b) Exception Category is the real rollup from the map, not
//         each [Exception Type Detail]
//     which is what your version does.  That alias is why the fact table's
//     "Exception Category" holds type-level values like "Access Point Hold" and
//     "Wrong Recipient", and why it disagrees with Dim_ExceptionReason on 36.5%
//     of rows.  Same reason the applied version disagrees - it has always been a
//     type wearing a category's name.
//
// (c) The leaf column is named  Exception Type  with NO trailing space.  See
//     section 6 for why the trailing space has to go.
//
// Recommended Action still keys off the leaf type, unchanged, and now also has a
// branch for the two new types.
// -----------------------------------------------------------------------------

let
    Source = QV_CLEAN,

    #"Full Address Column" =
        Table.AddColumn( Source, "Full Address",
            each Text.Combine(
                List.Select(
                    { [Ship To Address Line 1], [Ship To City],
                      [#"Ship To State/Province"], [Ship To Postal Code] },
                    each _ <> null and _ <> "" ),
                ", " ),
            type text ),

    #"Removed Old Classification Columns" =
        Table.RemoveColumns( #"Full Address Column",
            { "Matched Keyword", "Exception Type", "Exception Type ",
              "Exception Type Detail", "Keyword Match Count",
              "All Keyword Matches", "Exception Category" },
            MissingField.Ignore ),

    #"Added Exception Classification" =
        Table.AddColumn( #"Removed Old Classification Columns", "Exception Classification",
            each fnClassifyException( [Exception Description] ), type record ),

    #"Expanded Exception Classification" =
        Table.ExpandRecordColumn( #"Added Exception Classification", "Exception Classification",
            { "Matched Keyword", "Exception Type", "Exception Category",
              "Keyword Match Count", "All Keyword Matches" },
            { "Matched Keyword", "Exception Type", "Exception Category",
              "Keyword Match Count", "All Keyword Matches" } ),

    #"Carrier Delay Reason" =
        Table.AddColumn( #"Expanded Exception Classification", "Carrier Delay Reason",
            each
                if [Exception Type] <> "Carrier Delay" then null
                else if Text.Contains( [Exception Description], "MECHANICAL",          Comparer.OrdinalIgnoreCase ) then "Mechanical failure"
                else if Text.Contains( [Exception Description], "WEATHER",             Comparer.OrdinalIgnoreCase ) then "Severe weather"
                else if Text.Contains( [Exception Description], "LATE UPS TRAILER",    Comparer.OrdinalIgnoreCase ) then "Late trailer arrival"
                else if Text.Contains( [Exception Description], "OPERATING CONDITIONS",Comparer.OrdinalIgnoreCase ) then "Operating conditions"
                else if Text.Contains( [Exception Description], "SORTED",              Comparer.OrdinalIgnoreCase ) then "Incorrect sort"
                else "Other delay",
            type text ),

    #"Recommended Action" =
        Table.AddColumn( #"Carrier Delay Reason", "Recommended Action",
            each
                if   [Exception Type] = "P.O. Box"                then "Contact branch: obtain physical address. UPS cannot deliver to PO Boxes."
                else if List.Contains( { "Address Issue", "Missing Suite Number",
                                         "Incorrect Street Number", "Incomplete Address" },
                                       [Exception Type] )         then "Verify apt/suite/street number. Contact recipient or branch to update address."
                else if [Exception Type] = "Access Point Hold"     then "Notify branch: package at UPS Access Point. Pickup required within 5 business days."
                else if [Exception Type] = "Refused Delivery"      then "Notify branch. Package returning. Confirm return address."
                else if [Exception Type] = "Wrong Recipient"       then "Locate correct recipient or return to sender."
                else if [Exception Type] = "Delivery Attempt"      then "Confirm receiving hours with the branch. Redirect to an Access Point if attempts are exhausted."
                else if [Exception Type] = "Package Issue"         then "Escalate to UPS. Notify branch of potential loss."
                else if [Exception Type] = "Carrier Delay"         then "Monitor. No action unless delay exceeds SLA."
                else if [Exception Type] = "Schedule Change"       then "Note updated delivery date. Re-notify recipient if needed."
                else if [Exception Type] = "Customs / Documentation" then "Send required documentation to UPS. Confirm commodity detail with the shipper."
                else "Review manually and determine action.",
            type text ),

    #"Tracking URL" =
        Table.AddColumn( #"Recommended Action", "Tracking URL",
            each "https://www.ups.com/track?loc=en_US&tracknum=" & Text.From( [Tracking Number] ),
            type text ),

    #"Shipper Location" =
        Table.AddColumn( #"Tracking URL", "Shipper Location",
            each
                if   [Shipper Address Line 1] = null                                                                        then "Other Branch Origin"
                else if Text.Contains( [Shipper Address Line 1], "PROGRESS PKWY",       Comparer.OrdinalIgnoreCase ) then "Progress Parkway"
                else if Text.Contains( [Shipper Address Line 1], "MANCHESTER RD",       Comparer.OrdinalIgnoreCase ) then "Manchester"
                else if Text.Contains( [Shipper Address Line 1], "909 N 20TH ST",       Comparer.OrdinalIgnoreCase ) then "Gateway CDI (909 N 20th)"
                else if Text.Contains( [Shipper Address Line 1], "CHASTAIN RD",         Comparer.OrdinalIgnoreCase ) then "Kennesaw Distribution"
                else if Text.Contains( [Shipper Address Line 1], "LAKEVIEW CORPORATE",  Comparer.OrdinalIgnoreCase ) then "Edwardsville (Worldwide Tech)"
                else if Text.Contains( [Shipper Address Line 1], "KILNER",              Comparer.OrdinalIgnoreCase ) then "Kilner"
                else "Other Branch Origin",
            type text )
in
    #"Shipper Location"


// -----------------------------------------------------------------------------
// SECTION 6 - QV_Output
//
// Replace the whole QV_Output query.
//
// (a) The inline keyword classifier is GONE.  It was a second, independent copy of
//     the same logic producing a column called "Exception Type " - with a trailing
//     space - sitting next to a DAX calculated column called "Exception Type"
//     without one.  Two columns, one character apart in the Fields pane, holding
//     different answers on 28,286 of 46,594 rows.  Whoever picks the wrong one
//     next will not find out for weeks.  Classification now happens once, in
//     QV_Enriched.
//
//     ALSO DELETE the DAX calculated column QV_Output[Exception Type]:
//         COALESCE(MAXX(FILTER('Keyword Table', SEARCH(...)>0),
//                       'Keyword Table'[Exception Type]), "Other")
//     MAXX returns the alphabetically last matching type, not the highest-priority
//     one, so "MISSING SUITE NUMBER" scores Package Issue over Missing Suite
//     Number, and "ACCESS POINT ... HOLD" scores Schedule Change over Access Point
//     Hold.  It is wrong by construction.  Delete it BEFORE applying this section,
//     otherwise the new Exception Type column collides with it.
//
// (b) Shipper Match Key is GONE - see section 7.
//
// (c) Account Key added, recovered from the tracking number.
// -----------------------------------------------------------------------------

let
    Source = QV_Enriched,

    #"QV Run Time" =
        Table.AddColumn( Source, "Run Time",
            each if DateTime.Time( [Date modified] ) < #time( 13, 30, 0 )
                 then "Morning QV" else "Afternoon QV", type text ),

    #"QV Run Date" =
        Table.AddColumn( #"QV Run Time", "Run Date", each Date.From( [Date modified] ), type date ),

    #"Exception Key List" =
        Table.AddColumn( #"QV Run Date", "Exception Key",
            each Text.Upper( Text.Trim( [Tracking Number] ) ) & "|"
               & Text.Upper( Text.Trim( [Exception Description] ) ), type text ),

    // UPS 1Z format is 1Z + 6-char shipper account + 2-char service + 8-char
    // package id, so characters 3-8 are the account.  Same derivation already used
    // on Trace_Active.  99.13% of QV_Output matches Dim_Account today; the entire
    // remainder is A25T52, which is missing from the workbook - see section 7.
    #"Account Key" =
        Table.AddColumn( #"Exception Key List", "Account Key",
            each Text.Upper( Text.Middle( Text.Trim( [Tracking Number] ), 2, 6 ) ), type text ),

    #"Changed Type" =
        Table.TransformColumnTypes( #"Account Key", {{"Carrier Delay Reason", type text}} ),

    #"Removed Columns1" =
        Table.RemoveColumns( #"Changed Type",
            { "Ship To Attention", "Ship To Address Line 1", "Ship To Address Line 2",
              "Ship To City", "Ship To State/Province", "Ship To Postal Code" },
            MissingField.Ignore )
in
    #"Removed Columns1"


// -----------------------------------------------------------------------------
// SECTION 7 - Dim_Account
//
// Replace the whole Dim_Account query.
//
// THIS IS THE DIMENSION THAT WOULD NOT WORK.  Shipper Match Key is
// UPPER(TRIM(CLEAN(Account Name))), and five of your accounts are all called
// "EDWARD JONES MAIL SERVICES" - 75V664, 8V7494, 8V7507, 9V2538, 9V2549.  Two more
// pairs collide the same way.  23 accounts collapse to 17 keys, so Power BI cannot
// build a many-to-one relationship onto it at all: the "one" side has to be
// unique.  That is the error, and no amount of adjusting the fact side fixes it.
//
// It would not have worked even if it were unique.  Shipper Name in the shipment
// feed is not the account name:
//
//     shipper-name match          tracking-derived
//     QV_Output          21.72%   99.13%
//     QV_Manifest        48.42%   99.18%
//     Resolutions Table  31.19%   98.83%
//
// "EDWARD JONES/GATEWAY CDI" (25,107 rows) vs the account list's "EDWARD
// JONES/GATEWAY CDI SRM"; "EDWARD JONES/ CVS" (5,896) vs "EDWARD JONES/ICVS"; and
// 40,000-odd rows where Shipper Name is an individual's name.  Account Key from
// the tracking number is unique, 99%+ on every table, and 100% once A25T52 is
// added.
//
// ADD A25T52 TO THE WORKBOOK.  It is the entire unmatched remainder - 404 rows in
// QV_Output, 756 in QV_Manifest, 102 in Resolutions Table, nothing else.  The
// prepared row is in UPS_Acct_Info_.xlsx in this repo; your live workbook is
//     \\nfpgshare-1...\Report Data\UPS Acct Info .xlsx
// and the table range must be extended to A1:L25 or the refresh will not see it.
// -----------------------------------------------------------------------------

let
    Source = Excel.Workbook(
        File.Contents( "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\UPS Acct Info .xlsx" ),
        null, true ),

    #"Navigation 1" = Source{[Item = "tbl_Account_List", Kind = "Table"]}[Data],

    #"Changed column type" = Table.TransformColumnTypes( #"Navigation 1",
        { {"Sub/Parent Number", Int64.Type}, {"Account #", type text},
          {"Account Name", type text}, {"Account Start Date", Int64.Type},
          {"Account Status ", type text}, {"Attention Name", type text},
          {"Address", type text}, {"City", type text}, {"St", type text},
          {"Zip Code", Int64.Type}, {"Internal  Contact Name", type text} } ),

    #"Account Key" = Table.AddColumn( #"Changed column type", "Account Key",
        each Text.Upper( Text.Trim( Text.From( [#"Account #"] ) ) ), type text ),

    #"Account Label" = Table.AddColumn( #"Account Key", "Account Label",
        each [Account Key] & " - " & Text.Trim( [Account Name] ), type text ),

    // guarantees the "one" side of every account relationship stays unique
    #"Removed Duplicates" = Table.Distinct( #"Account Label", {"Account Key"} )
in
    #"Removed Duplicates"


// -----------------------------------------------------------------------------
// SECTION 8 - Resolutions Table
//
// Replace the whole Resolutions Table query.
//
// THE DEDUPE IS DOING THE OPPOSITE OF WHAT IT SAYS.  The query sorts Date modified
// descending and then takes Table.Distinct on Exception Key, intending to keep the
// newest sighting of each exception.  It does not.  Table.Distinct does not honour
// a preceding Table.Sort unless the sort is buffered - without Table.Buffer, Power
// Query streams and keeps whichever row it meets first, which is source order.
//
// Measured on your data: of the 4,075 exception keys that appear in more than one
// export, the row that survived is the OLDEST one in 4,075 cases and the newest in
// zero.  So the resolution queue is showing each exception's first-known state -
// its first Status, first Exception Resolution, first Scheduled Delivery - and has
// been quietly ignoring every update since.
//
// Table.Buffer fixes it in one line.  Age Days then has to be computed separately,
// because ageing should run from when the exception FIRST appeared, not from the
// latest row - so First Seen is grouped off the full table before the dedupe.
//
// Today those two errors cancel out and Age Days happens to be right.  After the
// fix it is right on purpose: 1,110 rows move Age Bucket, mostly out of "0-1" and
// into "8+", because a recurring exception is no longer treated as brand new every
// time it reappears.
//
// QV_MANIFEST HAS THE SAME BUG.  Its "Latest per Shipment" step is
//     Table.Distinct( Table.Sort( ..., {{"Date modified", Order.Descending}} ),
//                     {"Tracking Number"} )
// - identical construction, same defect.  Wrap that Table.Sort in Table.Buffer
// too, and add the Account Key column while you are in there:
//     Table.AddColumn( ..., "Account Key",
//         each Text.Upper( Text.Middle( Text.Trim( [Tracking Number] ), 2, 6 ) ), type text )
// -----------------------------------------------------------------------------

let
    Source = QV_Output,

    // first sighting per exception, taken across ALL exports before any dedupe
    #"First Seen" =
        Table.Group( Source, {"Exception Key"},
            { {"First Seen", each List.Min( [Date modified] ), type nullable datetime} } ),

    // Table.Buffer forces the sort to materialise so Distinct really does keep the
    // newest row.  Without it the sort is discarded and the oldest row survives.
    #"Sorted Rows"       = Table.Buffer( Table.Sort( Source, {{"Date modified", Order.Descending}} ) ),
    #"Removed Duplicates"= Table.Distinct( #"Sorted Rows", {"Exception Key"} ),

    #"Merged First Seen" = Table.NestedJoin( #"Removed Duplicates", {"Exception Key"},
                                             #"First Seen", {"Exception Key"},
                                             "fs", JoinKind.LeftOuter ),
    #"Expanded First Seen" = Table.ExpandTableColumn( #"Merged First Seen", "fs",
                                             {"First Seen"}, {"First Seen"} ),

    #"Merged Queries" = Table.NestedJoin( #"Expanded First Seen", {"Exception Key"},
                                          tbl_Resolution_Input, {"Exception Key"},
                                          "tbl_Resolution_Input", JoinKind.LeftOuter ),
    #"Expanded tbl_Resolution_Input" = Table.ExpandTableColumn( #"Merged Queries",
        "tbl_Resolution_Input",
        {"Resolution Status", "Root Cause", "Next Action", "Notes", "Last Updated", "Closed Date"},
        {"Resolution Status", "Root Cause", "Next Action", "Notes", "Last Updated", "Closed Date"} ),

    #"Tracker Status" = Table.AddColumn( #"Expanded tbl_Resolution_Input", "Tracker Status",
        each if [Resolution Status] = null or Text.Trim( [Resolution Status] ) = ""
             then "New / Needs Review" else Text.Trim( [Resolution Status] ), type text ),

    // age from FIRST sighting, so a recurring exception keeps ageing
    #"Aged Days" = Table.AddColumn( #"Tracker Status", "Age Days",
        each Duration.Days( Date.From( DateTime.LocalNow() )
                          - Date.From( [First Seen] ?? [Date modified] ) ), Int64.Type ),

    #"Age Bucket" = Table.AddColumn( #"Aged Days", "Age Bucket",
        each if      [Age Days] <= 1 then "0-1 Days"
             else if [Age Days] <= 3 then "2-3 Days"
             else if [Age Days] <= 7 then "4-7 Days"
             else                         "8+ Days", type text ),

    #"Changed Type" = Table.TransformColumnTypes( #"Age Bucket", {{"Age Days", Int64.Type}} )
in
    #"Changed Type"


// -----------------------------------------------------------------------------
// SECTION 9 - Current_Open_Trace, Review Status literal
//
// One character.  The conditional column writes
//         else "Escalate "
// with a trailing space, while the measure Escalated Traces matches
//         Current_Open_Trace[Review Status] = "Escalate"
// with none.  DAX string comparison does not trim.  It reads 67 today, so the
// space is being lost somewhere between Power Query and the model - but that is
// luck, not design, and it will bite the first time the pipeline changes.
//
// In the #"Added Conditional Column" step, change  "Escalate "  to  "Escalate".
//
// While you are there: Trace_Active[Account Key] derives from the [Account] column
// rather than the tracking number.  It is 100% today so leave it, but if that
// column is ever blank the trace page silently drops off the vendor slicer.  The
// safe form is the same one used everywhere else:
//     Text.Upper( Text.Middle( Text.Trim( [Tracking Number] ), 2, 6 ) )
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// SECTION 10 - trace date columns, still outstanding
//
// Unchanged from model-fixes.pq section 9 and still not done: every date column on
// Current_Open_Trace and Trace_Active loads as TEXT, so no calendar can reach the
// trace side - no date slicer, no trend, no SLA maths on the page whose entire job
// is SLA.
//
// Paste after the Trace_Notes merge step, on both queries.
//
// The sentinel list is load-bearing.  28 of 95 Follow-up values are 1/3/1900, an
// Excel epoch artefact from a blank cell that got date-formatted.  Convert those
// naively and Dim Date stretches back to 1900 - roughly 46,000 rows - and every
// date axis becomes unreadable.
//
// Culture is pinned because "7/8/2026" is 8 July under en-US and 7 August under
// en-GB, and a Service refresh can otherwise disagree with Desktop.
// -----------------------------------------------------------------------------

let
    Sentinels = { "", "Not Avail.", "N/A", "NA", "TBD",
                  "1/3/1900", "1/2/1900", "1/1/1900", "12/30/1899" },

    fnDate = ( v ) as nullable date =>
        let
            t     = if v = null then null else Text.Trim( Text.From( v ) ),
            clean = if t = null or List.Contains( Sentinels, t ) then null else t,
            out   = if clean = null then null
                    else try Date.FromText( clean, [Format = "M/d/yyyy", Culture = "en-US"] )
                         otherwise null
        in
            out,

    DateCols = { "Manifest Date", "Original Scheduled Delivery Date", "Scheduled Delivery",
                 "Last Reviewed", "Follow-up", "Next Follow-up Date", "Closed Date" },

    #"Typed Dates" =
        List.Accumulate(
            List.Select( DateCols, each List.Contains( Table.ColumnNames( PREVIOUS_STEP ), _ ) ),
            PREVIOUS_STEP,
            ( state, col ) => Table.TransformColumns( state, {{ col, fnDate, type nullable date }} ) )
in
    #"Typed Dates"

// Replace PREVIOUS_STEP with the real name of the step above it - on
// Current_Open_Trace that is #"Expanded Trace_Notes".
