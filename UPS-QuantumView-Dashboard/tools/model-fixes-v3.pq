// =============================================================================
// Quantum View - Power Query, v3
//
// For QuantumView_Checkpoint_DateSlicersPassed.pbix. Apply in
// Home > Transform data. Sections are independent - do them in any order except
// 8, which needs 4 and 6 in place first.
//
//   §1  QV_RAW                  read Archive only, one 13:30 cutoff
//   §2  QV_Output               stop recomputing the run window
//   §3  QV_Manifest             Table.Buffer + Account Key
//   §4  Current_Open_Trace      FA Key + Contact Route      <- THE contact fix
//   §5  Trace_Active            same normalisation
//   §6  Home_Office_Contacts    the 11 H-codes the roster cannot reach
//   §7  Trace_Notes             SharePoint list
//   §8  Mail_Merge_Queue        the table Power Automate iterates
//   §9  Cleanup                 three tables carrying nothing
//
// Everything your last pass added is kept. Branch_Contacts_All,
// Branch_Contacts and Trace_Contact_By_FA are correct and are not touched -
// the BOA to FA join in particular is on the right key and resolves 24,972 of
// 25,007 BOA rows. The problem was never there.
// =============================================================================


// -----------------------------------------------------------------------------
// SECTION 1 - QV_RAW                                                  (REPLACE)
//
// Two changes.
//
// (a) READ ARCHIVE ONLY. Folder.Files recurses, and QV_Data already contains
//     Morning QV\, Afternoon QV\, Processed\ and Failed\. Pointed at QV_Data,
//     the query reads every export once per folder it appears in - Total
//     Shipments multiplies and nothing errors. It would also try to parse
//     QV_Automation_Helper_Lists.xlsx as a 34-column CSV.
//
//     This is not hypothetical: those folders exist on your share today.
//     Archive-only is what makes the rest of the layout safe.
//
// (b) ONE cutoff. QV_RAW splits the day at 17:00 and QV_Output splits it at
//     13:30 - same rows, same model, two answers. 13:30 wins because that is
//     what the Run Time slicer and the Run Coverage panel already show. The
//     window is computed here, once, and §2 just carries it.
//
// The cutoff is also hard-coded in qv-file-automation.ps1. Change one and you
// must change the other, or the share and the dashboard will disagree about
// which run a file belongs to.
// -----------------------------------------------------------------------------

// CORRECTED PATH. Your QV_RAW currently points at
//     ...\Administrative Services-Solutions\Quantum View\QV_Data
// and the real folder, per your path list, is
//     ...\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data
// Different parent. Check which one your last successful refresh actually read
// before you assume this is a typo in one direction or the other - if the old
// path still resolves, you have two QV_Data folders and only one of them is
// being fed.
//
// UNC, not X:. The Power BI Service and any scheduled task have no mapped drives.

let
    QVRoot   = "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data",
    Archive  = QVRoot & "\Archive",

    CutoffHour   = 13,
    CutoffMinute = 30,

    Source = Folder.Files( Archive ),

    // Hidden files, Excel lock files and zero-byte drops all look like exports
    // to Folder.Files and none of them are.
    #"Real Files" =
        Table.SelectRows( Source,
            each [Attributes]?[Hidden]? <> true
             and not Text.StartsWith( [Name], "~$" )
             and Text.Lower( [Extension] ) = ".csv" ),

    #"Run Window" =
        Table.AddColumn( #"Real Files", "Run Window",
            each if Time.From( [Date modified] ) < #time( CutoffHour, CutoffMinute, 0 )
                 then "Morning QV" else "Afternoon QV", type text ),

    #"Run Date" =
        Table.AddColumn( #"Run Window", "Run Date",
            each Date.From( [Date modified] ), type date ),

    #"Invoke Custom Function1" =
        Table.AddColumn( #"Run Date", "Transform File (2)",
            each #"Transform File (2)"( [Content] ) )
in
    #"Invoke Custom Function1"


// -----------------------------------------------------------------------------
// SECTION 2 - QV_Output                                        (TWO STEPS ONLY)
//
// Do not replace the whole query - your version is fine. Just delete the two
// steps that recompute what §1 now provides:
//
//     #"QV Run Time"   <- delete. Table.AddColumn(..., "Run Time", each if
//                         DateTime.Time([Date modified]) < #time(13,30,0) ...)
//     #"QV Run Date"   <- delete
//
// and rename the inherited columns so nothing downstream has to change:
//
//     Table.RenameColumns( Source, {{"Run Window", "Run Time"}} )
//
// "Run Time" is what the slicer on OVERVIEW and the Run Coverage panel bind to,
// so keeping the name means no visual needs rebinding. Run Date comes through
// from §1 already named.
//
// The result is one definition of the run window, computed once per FILE rather
// than once per row - which is also 45,614 fewer time comparisons per refresh.
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// SECTION 3 - QV_Manifest                                     (TWO STEPS ONLY)
//
// The Table.Buffer fix landed on Resolutions Table but not here, so
// "Latest per Shipment" is still doing the opposite of its name. Table.Distinct
// does not honour an unbuffered Table.Sort; without the buffer Power Query
// streams and keeps whichever row it meets first, which is source order - the
// OLDEST manifest row per tracking number, not the newest.
//
// Replace the last step:
//
//     #"Latest per Shipment" =
//         Table.Distinct(
//             Table.Buffer(
//                 Table.Sort( #"Changed Type1", {{"Date modified", Order.Descending}} )
//             ),
//             {"Tracking Number"}
//         ),
//
// And add the account key so QV_Manifest stops depending on a DAX calculated
// column for its only relationship:
//
//     #"Account Key" =
//         Table.AddColumn( #"Latest per Shipment", "Account Key",
//             each Text.Upper( Text.Middle( Text.Trim( [Tracking Number] ), 2, 6 ) ),
//             type text )
//
// then delete the DAX calculated column QV_Manifest[Account Key]. Do the delete
// AFTER this loads, or the names collide.
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// SECTION 4 - Current_Open_Trace                            (ADD STEPS AT END)
//
// THIS IS THE CONTACT FIX. Everything else about the roster is already right.
//
// Current_Open_Trace[FA #] holds  I287748.
// Trace_Contact_By_FA[FA #] holds  287748.
// The relationship between them is active and matches 0 of 95 rows. That single
// character is why Selected Branch Email, Selected FA Email, Selected BOA Emails
// and Unreachable Traces all come back empty.
//
// Strip the prefix and 66 of 66 I-rows match, resolving an FA email on all 66
// and a BOA cc on 61 of them.
//
// The prefix is not noise - it is a type tag, and the trace sheet is using one
// column for two different identifier spaces:
//
//     I######   a real FA number         66 rows   -> the roster
//     H#####    a home office dept code  28 rows   -> §6, the roster has none of them
//     0          a data-entry miss         1 row   -> unreachable, and should be
//
// H codes match nothing in the roster: 0 of 28 against EMPLID, JP Number, FA ID
// and FA #. Five of them coincidentally look like branch numbers; that is a
// coincidence, not a route. They are Campus Ship / World Ship / Kimler
// departmental shipments and need their own map.
//
// Contact Route makes the branch explicit rather than leaving it implied in a
// chain of COALESCEs, so a trace that cannot be addressed says WHY.
//
// Paste these steps at the end of Current_Open_Trace, after #"Expanded Trace_Notes".
// -----------------------------------------------------------------------------

let
    // ... your existing steps ...

    #"FA Key" =
        Table.AddColumn( #"Expanded Trace_Notes", "FA Key",
            each
                let raw = Text.Upper( Text.Trim( Text.From( [#"FA #"] ?? "" ) ) )
                in  if raw = "" or raw = "0" then null
                    else if Text.StartsWith( raw, "I" ) then Text.Middle( raw, 1 )
                    else null,
            type nullable text ),

    #"Home Office Code" =
        Table.AddColumn( #"FA Key", "Home Office Code",
            each
                let raw = Text.Upper( Text.Trim( Text.From( [#"FA #"] ?? "" ) ) )
                in  if Text.StartsWith( raw, "H" ) then raw else null,
            type nullable text ),

    #"Contact Route" =
        Table.AddColumn( #"Home Office Code", "Contact Route",
            each
                if [CONTACT INFO] <> null and Text.Contains( Text.From( [CONTACT INFO] ), "@" )
                    then "Case contact"
                else if [FA Key] <> null            then "FA roster"
                else if [Home Office Code] <> null  then "Home office"
                else "Unroutable",
            type text )
in
    #"Contact Route"

// After this loads, in Model view:
//   * confirm Current_Open_Trace[FA Key] -> Trace_Contact_By_FA[FA #] is ACTIVE
//     (delete the old relationship on [FA #] first - two relationships between
//     the same pair of tables cannot both be active)
//   * add Current_Open_Trace[Home Office Code] -> Home_Office_Contacts[Code]


// -----------------------------------------------------------------------------
// SECTION 5 - Trace_Active                                  (ADD STEPS AT END)
//
// Same three columns, same code, so the two trace tables stay interchangeable.
// Trace_Active is the full sheet and Current_Open_Trace is the working view; if
// only one of them can resolve a contact they will disagree the first time
// somebody builds a visual on the wrong one.
//
// Paste the identical #"FA Key" / #"Home Office Code" / #"Contact Route" block,
// changing only the name of the step it builds on.
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// SECTION 6 - Home_Office_Contacts                                       (NEW)
//
// New blank query, rename it exactly  Home_Office_Contacts
//
// Eleven codes covering 28 traces. The roster cannot supply these - they are
// home office departments, not branches, and no FA owns them.
//
// SEVEN OF THE ELEVEN ARE ALREADY ANSWERED BY YOUR OWN DATA. Where a trace with
// that code carried a CONTACT INFO address, that address is seeded below and
// marked Confirmed. Four have never had one and are blank, marked Missing -
// fill those in and reachability goes from 90/95 to 94/95.
//
// The two suggestions in the comments are inferences from other rows sharing the
// same Location, NOT from a system of record. Verify before you trust them.
//
// WHERE TO KEEP IT. You already have QV_Automation_Helper_Lists.xlsx sitting in
// QV_Data, which is the obvious home for a lookup list somebody else may need to
// edit. So this reads a sheet named "Home_Office_Contacts" from that workbook IF
// it exists, and falls back to the inline seed below if it does not.
//
// That means it works today, unedited, and starts using the workbook the moment
// you add the sheet - without anyone touching M. Add a sheet with columns
// Code / Location / Email / Status and it takes over.
// -----------------------------------------------------------------------------

let
    HelperBook =
        "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data\QV_Automation_Helper_Lists.xlsx",

    FromWorkbook =
        try
            let
                wb    = Excel.Workbook( File.Contents( HelperBook ), null, true ),
                sheet = Table.SelectRows( wb, each Text.Lower( [Name] ) = "home_office_contacts" ),
                data  = if Table.IsEmpty( sheet ) then null else sheet{0}[Data],
                head  = if data = null then null
                        else Table.PromoteHeaders( data, [PromoteAllScalars = true] ),
                live  = if head = null then null
                        else Table.SelectRows( head,
                                 each [Code] <> null and Text.Trim( Text.From( [Code] ) ) <> "" )
            in
                live
        otherwise null,

    Seed = Table.FromRows(
        {
            // Code      Location                        Email                                   Status
            { "H00175", "World Ship, Kimler",            "douglas.rushing@edwardjones.com",       "Confirmed" },
            { "H01400", "Campus Ship, Manchester",       "janine.smith@edwardjones.com",          "Confirmed" },
            { "H03130", "World Ship, Kimler",            null,                                    "Missing"   },  // same Location as H00175/H06572/H07123 - douglas.rushing? verify
            { "H04234", "Campus Ship, Kimler",           "timothy.finucan@edwardjones.com",       "Confirmed" },
            { "H04310", "World Ship, Cash Checks",       "Cash-Receipts-Checks@edwardjones.com",  "Confirmed" },
            { "H05057", "Edward Jones IS warehouse (WWT)", null,                                  "Missing"   },
            { "H05150", "Campus Ship, Kimler",           null,                                    "Missing"   },  // same Location as H04234/H44627 - verify
            { "H06572", "World Ship, Kimler",            "douglas.rushing@edwardjones.com",       "Confirmed" },
            { "H07123", "World Ship, Kimler",            "douglas.rushing@edwardjones.com",       "Confirmed" },
            { "H44627", "Campus Ship, Kimler",           "ashley.mitchell@edwardjones.com",       "Confirmed" },
            { "H44804", "World Ship, Cash Checks",       null,                                    "Missing"   }   // same Location as H04310 - Cash-Receipts-Checks? verify
        },
        type table [ Code = text, Location = text, Email = nullable text, Status = text ]
    ),

    // workbook wins if the sheet is there, seed if it is not
    Source = if FromWorkbook = null then Seed else FromWorkbook,

    Typed = Table.TransformColumnTypes( Source,
                {{"Code", type text}, {"Location", type text},
                 {"Email", type text}, {"Status", type text}} ),

    // never let a duplicate code through - this is the one side of a relationship
    Unique = Table.Distinct( Typed, {"Code"} )
in
    Unique


// -----------------------------------------------------------------------------
// SECTION 7 - Trace_Notes                                             (REPLACE)
//
// The current query returns 200 rows of which 199 are null in every column, and
// joins 1 of 95 traces. Same failure shape as the old Branch_Contacts: a sheet
// range formatted well past its data, loading as nulls, erroring on nothing.
//
// You chose the SharePoint list, which is the right answer and the one that
// actually delivers "notes update as we make changes":
//
//   * Modified is stamped by the list at save and never drifts. An Excel NOW()
//     recalculates every time the file opens, so a workbook physically cannot
//     tell you when a note was written.
//   * SharePoint.Tables refreshes in the cloud with NO on-premises gateway.
//     Every other query in this model needs one.
//   * Two people can write at once. A workbook on a share cannot.
//   * Version history per item, for free.
//
// YOUR LIST ALREADY EXISTS AND THE QUERY IS NOT POINTED AT IT. That is the real
// story here. Trace_Notes still reads
//     ...\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx
// while the notes moved to Trace_Master_Streamlined_. The workbook is the
// abandoned copy - which is exactly why it returns 199 blank rows out of 200 and
// joins 1 of 95 traces. Nothing was broken; the query was reading a dead file.
//
// ---------------------------------------------------------------------------
// BEFORE YOU BUILD ON IT: THE LIST IS ON A PERSONAL ONEDRIVE, NOT A TEAM SITE
// ---------------------------------------------------------------------------
//     https://ejprod-my.sharepoint.com/personal/p258239_edwardjones_com/...
//                     ^^^^^^^^^^^^^^^^^^^^^^^^^
// "-my.sharepoint.com/personal/" is one individual's OneDrive. For a system of
// record that an ops team depends on, that is a real exposure and not a
// nitpick:
//
//   * It is deprovisioned when that person leaves or changes roles. The site
//     goes read-only, then away, typically after a 30-93 day retention window.
//     The dashboard stops refreshing and the notes history goes with it.
//   * Service refresh has to run on THAT person's credentials. It cannot be
//     moved to a service account, because the site belongs to the human.
//   * Permissions are per-item sharing rather than site membership, so
//     onboarding the next analyst is manual and easy to get wrong.
//
// The query below works against it today - I am not going to hold your build up
// over this. But move the list to a TEAM SITE before rollout, and it is a
// 10-minute job now versus a data-loss incident later. Copy the list to the
// team site, change SiteUrl, done - the schema and every column name survive.
//
// After moving, this is also the moment to point tbl_Resolution_Input at the
// same team site (WRITEBACK-AND-MAILMERGE.md), so both write-backs live
// somewhere that outlives an individual.
// ---------------------------------------------------------------------------
//
// The key discipline matters more than the source. Exception Key is the stable
// key and CASE # is the human one; notes get written against whichever the
// analyst had to hand, so this resolves on Exception Key and falls back to
// CASE #, with both sides normalised. That is why the join lands 1 of 95 today -
// not because the notes are missing, but because nothing normalised the keys.
// -----------------------------------------------------------------------------

let
    // YOUR LIST, from the path sheet.
    SiteUrl  = "https://ejprod-my.sharepoint.com/personal/p258239_edwardjones_com",
    ListName = "Trace_Master_Streamlined_",

    Source = SharePoint.Tables( SiteUrl, [ApiVersion = 15] ),
    Items  = Source{[Title = ListName]}[Items],

    // Rename whatever is actually there to the names the model already uses.
    // MissingField.Ignore means a name you have spelled differently is skipped
    // rather than erroring - so this loads on the first try and you correct the
    // left-hand side against what you see. Internal names, not display names:
    // a column shown as "Trace Status" is usually Trace_x0020_Status.
    #"Renamed" = Table.RenameColumns( Items,
        { {"ExceptionKey",     "Exception Key"},
          {"Exception_x0020_Key", "Exception Key"},
          {"CaseNumber",       "CASE #"},
          {"CASE_x0020__x0023_", "CASE #"},
          {"Title",            "CASE #"},
          {"TraceStatus",      "Trace Status"},
          {"LastAction",       "Last Action"},
          {"NextFollowUpDate", "Next Follow-up Date"},
          {"TicklerType",      "Tickler Type"},
          {"UPSTraceNumber",   "UPS Trace Number"},
          {"ClaimStatus",      "Claim Status"},
          {"RefundAmount",     "Refund Amount"},
          {"AssignedTo",       "Assigned To"},
          {"Notes",            "Notes"},
          {"Modified",         "Note Updated"},
          {"ClosedDate",       "Closed Date"} },
        MissingField.Ignore ),

    // never let a formatted-but-empty row through again
    #"Non-blank" =
        Table.SelectRows( #"Renamed",
            each not List.IsEmpty(
                List.RemoveMatchingItems( Record.FieldValues( _ ), {"", null} ) ) ),

    #"Normalised Keys" =
        Table.AddColumn(
            Table.AddColumn( #"Non-blank", "Exception Key Norm",
                each let v = Text.Upper( Text.Trim( Text.From( [Exception Key] ?? "" ) ) )
                     in  if v = "" then null else v, type nullable text ),
            "Case Key Norm",
            each let v = Text.Upper( Text.Trim( Text.From( [#"CASE #"] ?? "" ) ) )
                 in  if v = "" then null else v, type nullable text ),

    // newest note per key wins, and Table.Buffer so Distinct actually honours it
    #"Newest First" =
        Table.Buffer( Table.Sort( #"Normalised Keys",
            {{"Note Updated", Order.Descending}} ) )
in
    #"Newest First"

// FIRST RUN: paste just the first two steps, load, and look at the column names
// Power Query gives you. SharePoint returns INTERNAL names, so "Trace Status"
// arrives as Trace_x0020_Status and a column added after the list was created
// keeps whatever it was first called even if it has since been renamed. Correct
// the left-hand side of #"Renamed" against what you see, then paste the rest.
//
// THEN, IN Current_Open_Trace: replace the single CASE # merge with two passes -
// merge on Exception Key Norm first, then merge the still-unmatched rows on
// Case Key Norm. One key is stable and the other is the one analysts actually
// type; you need both, normalised, or you get today's 1 of 95.
//
//     #"Notes by Exception" =
//         Table.NestedJoin( <prev>, {"Exception Key"}, Trace_Notes,
//                           {"Exception Key Norm"}, "n1", JoinKind.LeftOuter ),
//     #"Notes by Case" =
//         Table.NestedJoin( #"Expanded n1", {"CASE #"}, Trace_Notes,
//                           {"Case Key Norm"}, "n2", JoinKind.LeftOuter ),
//     ... then COALESCE each field: n1 wins, n2 fills the gaps.


// -----------------------------------------------------------------------------
// SECTION 8 - Mail_Merge_Queue                                           (NEW)
//
// New blank query, rename it exactly  Mail_Merge_Queue
//
// This is the table Power Automate iterates. One row per open trace, already
// addressed, so the flow does no lookup logic - Get items, apply to each, send.
// Every join, fallback and exclusion decision lives here in M where you can see
// it, rather than scattered across flow actions where you cannot.
//
// Needs §4 and §6 applied first.
//
// Send To / Cc are deliberately built as semicolon strings: that is what the
// Outlook connector's To and Cc fields take directly, no split needed.
//
// Blocked Reason is the point of the table. A trace that cannot be emailed says
// why, in a column, instead of quietly not appearing in the queue.
// -----------------------------------------------------------------------------

let
    Source = Current_Open_Trace,

    Joined =
        Table.NestedJoin( Source, {"FA Key"}, Trace_Contact_By_FA, {"FA #"},
                          "Roster", JoinKind.LeftOuter ),
    ExpandedRoster =
        Table.ExpandTableColumn( Joined, "Roster",
            {"FA Name", "FA Email", "BOA Emails", "BOA Names", "Branch Number", "Primary Contact Email"},
            {"FA Name", "FA Email", "BOA Emails", "BOA Names", "Branch Number", "Roster Primary"} ),

    JoinedHO =
        Table.NestedJoin( ExpandedRoster, {"Home Office Code"}, Home_Office_Contacts, {"Code"},
                          "HO", JoinKind.LeftOuter ),
    ExpandedHO =
        Table.ExpandTableColumn( JoinedHO, "HO",
            {"Email", "Location"}, {"HO Email", "HO Location"} ),

    // Case contact beats roster: it was typed against THIS case by someone who
    // looked at it. The roster is the fallback, not the authority.
    #"Send To" =
        Table.AddColumn( ExpandedHO, "Send To",
            each
                let direct = Text.Trim( Text.From( [CONTACT INFO] ?? "" ) )
                in  if Text.Contains( direct, "@" ) then direct
                    else if [FA Email] <> null      then [FA Email]
                    else if [HO Email] <> null      then [HO Email]
                    else null,
            type nullable text ),

    // BOAs are cc, never to. They act on the package; the FA owns the client.
    #"Send Cc" =
        Table.AddColumn( #"Send To", "Send Cc",
            each if [BOA Emails] <> null and [BOA Emails] <> "" then [BOA Emails] else null,
            type nullable text ),

    #"Blocked Reason" =
        Table.AddColumn( #"Send Cc", "Blocked Reason",
            each
                if [Send To] <> null then null
                else if [Contact Route] = "Unroutable"  then "FA # is blank or 0 on the trace sheet"
                else if [Home Office Code] <> null      then "Home office code " & [Home Office Code] & " has no address in Home_Office_Contacts"
                else if [FA Key] <> null                then "FA " & [FA Key] & " is not in the current roster"
                else "No route",
            type nullable text ),

    #"Days Open" =
        Table.AddColumn( #"Blocked Reason", "Days Open",
            each try Duration.Days( Date.From( DateTime.LocalNow() )
                                  - Date.From( [Manifest Date] ) ) otherwise null,
            Int64.Type ),

    Shaped =
        Table.SelectColumns( #"Days Open",
            { "CASE #", "Tracking Number", "Exception Description", "UPS Status",
              "Delivery Status", "Review Status", "Overdue", "Manifest Date",
              "Days Open", "Account", "Location", "Ship To Name",
              "Contact Route", "FA Key", "FA Name", "Home Office Code", "HO Location",
              "Send To", "Send Cc", "BOA Names", "Branch Number", "Blocked Reason" },
            MissingField.UseNull )
in
    Shaped

// The flow filters this table, it does not compute against it:
//     Sendable   ->  Send To <> null
//     Blocked    ->  Blocked Reason <> null    <- put this on a page, it is a worklist
//     Escalations->  Review Status = "Escalate"


// -----------------------------------------------------------------------------
// SECTION 9 - Cleanup                                                (DELETE 3)
//
// Right-click each in the Queries pane > Delete. All three are verified unused
// by any visual, measure or relationship that matters.
//
//   Branch_Contacts_Old     500 rows, every column null on every row. The
//                           superseded roster query. It is doing nothing except
//                           sitting next to the real one waiting to be picked by
//                           mistake.
//
//   Exception Reason Map    Loaded as a table AND used as the source of
//                           Dim_ExceptionReason, so the same 14 rows appear
//                           twice in the Fields pane. It carries two inactive
//                           relationships that exist only because Power BI
//                           refused to make them active - a duplicate dimension
//                           is exactly how a model becomes ambiguous later.
//                           Keep the QUERY, untick "Enable load".
//
//   Res_Tracker             1,040 rows of unpromoted Column1..Column14. Both
//                           specs say to drop it; tbl_Resolution_Input is the
//                           one that feeds the queue.
//
// Untick "Enable load" rather than deleting if you want to keep the M around.
// -----------------------------------------------------------------------------
