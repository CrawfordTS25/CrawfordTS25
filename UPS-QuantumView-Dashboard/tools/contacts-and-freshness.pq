// =============================================================================
// Quantum View - branch contacts + per-source refresh stamps
//
// Two additions, independent of each other and of model-fixes-v2.pq.  Apply after
// that file, in Home > Transform data.
//
//   §1  Branch_Contacts Discovery   one-off, delete when done
//   §2  Branch_Contacts             rebuilt - it currently loads 500 empty rows
//   §3  Refresh Status              one row per source file, with its modified stamp
//
// The DAX that renders §3 in the title bars is in contacts-and-freshness.tmdl.
// =============================================================================


// -----------------------------------------------------------------------------
// SECTION 1 - Branch_Contacts Discovery                              (ONE-OFF)
//
// New blank query, name it anything.  It tells you what is actually in the
// workbook so §2's three constants can be set correctly.  I cannot see the file
// from here, so this is the step that replaces guessing.
//
// What went wrong: the current query navigates to the "branch email" SHEET and
// immediately promotes row 1 to headers.  The result is 500 rows in which every
// column is null on every row - it loads without erroring, which is why nobody
// noticed.  Two tells that row 1 is not the header row:
//
//     "Source"                        <- a metadata label, not a field name
//     "X:\hrdi_report_pickup\FA_Roster\"   <- a FILE PATH became a column name
//
// So the sheet almost certainly has a title/provenance block above the real
// header, and the promote grabbed that instead.
//
// Run this and read three things off it:
//   * is there an Item with Kind = "Table"?  If yes, use it - named tables carry
//     their own header and none of this fragility.
//   * which sheet actually holds rows?  ("Rows" below counts non-blank rows.)
//   * on that sheet, which row number contains the word Email?
// -----------------------------------------------------------------------------

let
    Workbook = "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx",

    Source = Excel.Workbook( File.Contents( Workbook ), null, true ),

    #"Non-blank rows" = Table.AddColumn( Source, "Rows",
        each try Table.RowCount(
                 Table.SelectRows( [Data], each not List.IsEmpty(
                     List.RemoveMatchingItems( Record.FieldValues( _ ), {"", null} ) ) ) )
             otherwise null, Int64.Type ),

    #"Header row" = Table.AddColumn( #"Non-blank rows", "Row holding 'Email'",
        each try
                 List.PositionOf(
                     Table.ToRows( [Data] ),
                     List.First(
                         List.Select(
                             Table.ToRows( [Data] ),
                             each List.AnyTrue( List.Transform( _, ( c ) =>
                                 c <> null
                                 and Text.Contains( Text.Lower( Text.From( c ) ), "email" ) ) ) ),
                         null ) ) + 1
             otherwise null, Int64.Type ),

    #"First data row" = Table.AddColumn( #"Header row", "First non-blank row",
        each try Text.Combine(
                 List.Transform(
                     List.FirstN(
                         List.First(
                             List.Select( Table.ToRows( [Data] ),
                                 each not List.IsEmpty(
                                     List.RemoveMatchingItems( _, {"", null} ) ) ),
                             {} ),
                         8 ),
                     each if _ = null then "" else Text.From( _ ) ),
                 " | " )
             otherwise null, type text ),

    #"Kept" = Table.SelectColumns( #"First data row",
                  { "Name", "Kind", "Rows", "Row holding 'Email'", "First non-blank row" } )
in
    #"Kept"


// -----------------------------------------------------------------------------
// SECTION 2 - Branch_Contacts                                        (REPLACE)
//
// Replace the whole Branch_Contacts query.
//
// Set the three constants from what §1 told you.  The defaults are my best read of
// the current query; if §1 shows a Kind = "Table" item, switch ItemKind to "Table"
// and this gets simpler and more stable - a named Excel table can never drift the
// way a sheet range does.
//
// WHAT IT DOES DIFFERENTLY
//
//   * finds the header row instead of assuming row 1 - it looks for the row
//     containing a cell whose text is "email".  That is the actual bug.
//   * drops fully-blank rows before AND after the promote, so trailing formatted-
//     but-empty rows stop inflating the table to 500.
//   * finds the email column by CONTENT (>50% of values contain "@") rather than
//     by name, so a header rename can't silently break it.
//   * keeps only rows that carry a plausible email, so a half-filled roster row
//     can never be emailed.
//   * dedupes on the key, which is what lets the relationship in the .tmdl exist
//     at all - the "one" side has to be unique.
//   * NEVER errors.  A roster that comes back empty must not take the daily
//     refresh down with it; the health measure in the .tmdl surfaces it instead.
//
// HOW IT JOINS - and the thing worth knowing before you build the mail merge
//
// This roster can reach the TRACE side and nothing else.  Current_Open_Trace[FA #]
// is populated on all 95 rows (66 as I######, 28 as H#####, one literal "0"), and
// no FA # maps to two different emails, so the join is clean.  23 of those 95 rows
// have an FA # but a blank CONTACT INFO - those are exactly the ones the roster
// fills in.
//
// The EXCEPTIONS queue has no FA identity at all.  Ship To Name on QV_Output is
// "EDWARD JONES" on 35,126 of 46,594 rows and a client's name on most of the rest;
// Ship To Attention on QV_Manifest is "EDWARD JONES" or blank on 40,770.  Neither
// identifies a person.  So for the exceptions mail merge the recipient has to come
// from the SharePoint List's Owner column, populated by the Power Apps panel -
// which is what WRITEBACK-AND-MAILMERGE.md already recommends as the interim
// route, and it turns out to be the only route.  Fixing this query does not change
// that; it makes the trace-side contact lookup work and gives Flow 2 a real roster
// to address branch traffic from.
// -----------------------------------------------------------------------------

let
    Workbook  = "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Tracing_API_Aligned_Workflow_Optimized.xlsx",
    ItemName  = "branch email",     // <- from §1
    ItemKind  = "Sheet",            // <- "Table" if §1 shows one; prefer it
    KeyColumn = "Custom1",          // <- the FA-number column. CHECK §1's preview.

    Source = Excel.Workbook( File.Contents( Workbook ), null, true ),
    Raw    = try Source{[Item = ItemName, Kind = ItemKind]}[Data] otherwise null,

    Grid   = if Raw = null then #table( {"FA #", "Name", "Email"}, {} ) else Raw,

    // ---- 1. drop rows that are blank all the way across --------------------
    NonBlank = Table.SelectRows( Grid, each not List.IsEmpty(
                   List.RemoveMatchingItems( Record.FieldValues( _ ), {"", null} ) ) ),

    // ---- 2. find the header row rather than assuming it is the first -------
    Rows        = Table.ToRows( NonBlank ),
    HeaderRow   = List.First(
                      List.Select( Rows, each List.AnyTrue( List.Transform( _, ( c ) =>
                          c <> null
                          and Text.Lower( Text.Trim( Text.From( c ) ) ) = "email" ) ) ),
                      null ),
    HeaderAt    = if HeaderRow = null then 0 else List.PositionOf( Rows, HeaderRow ),
    FromHeader  = Table.Skip( NonBlank, HeaderAt ),
    Promoted    = Table.PromoteHeaders( FromHeader, [PromoteAllScalars = true] ),

    // ---- 3. drop the blank rows the promote leaves behind -------------------
    Body = Table.SelectRows( Promoted, each not List.IsEmpty(
               List.RemoveMatchingItems( Record.FieldValues( _ ), {"", null} ) ) ),

    // ---- 4. find the email column by what is IN it, not what it is called ---
    Cols    = Table.ColumnNames( Body ),
    AtRate  = ( col as text ) as number =>
                  let vals = List.RemoveNulls( Table.Column( Body, col ) ),
                      hits = List.Count( List.Select( vals,
                                 each try Text.Contains( Text.From( _ ), "@" ) otherwise false ) )
                  in  if List.Count( vals ) = 0 then 0 else hits / List.Count( vals ),
    EmailCol = List.First( List.Select( Cols, each AtRate( _ ) > 0.5 ),
                   if List.Contains( Cols, "Email" ) then "Email" else null ),

    NameCol  = List.First( List.Select( Cols,
                   each _ <> EmailCol and Text.Contains( Text.Lower( _ ), "name" ) ), null ),
    KeyCol   = if List.Contains( Cols, KeyColumn ) then KeyColumn else null,

    // ---- 5. normalise to a fixed three-column shape -------------------------
    //
    // Record.FieldOrDefault only substitutes when the field is MISSING, not when
    // it is present and null - and Text.Trim(null) throws. Hence the explicit
    // null check rather than a default value.
    txt = ( r as record, col as nullable text ) as nullable text =>
              if col = null then null
              else let v = Record.FieldOrDefault( r, col, null )
                   in  if v = null then null else Text.Trim( Text.From( v ) ),

    Shaped = Table.FromRecords(
        List.Transform( Table.ToRecords( Body ), ( r ) =>
            [ #"FA #" = let v = txt( r, KeyCol )   in if v = null then null else Text.Upper( v ),
              Name    = txt( r, NameCol ),
              Email   = let v = txt( r, EmailCol ) in if v = null then null else Text.Lower( v ) ] ),
        type table [ #"FA #" = nullable text, Name = nullable text, Email = nullable text ] ),

    // ---- 6. only rows that can actually be emailed --------------------------
    Valid = Table.SelectRows( Shaped,
                each [Email] <> null and [Email] <> "" and Text.Contains( [Email], "@" ) ),

    // ---- 7. unique on the key, so the relationship can exist ----------------
    Keyed = Table.SelectRows( Valid, each [#"FA #"] <> null and [#"FA #"] <> "" ),

    // If the workbook or the sheet is unreachable, hand back an empty table with
    // the right shape rather than an error. The refresh survives; the roster reads
    // 0 in [Branch Contacts Loaded], which is the signal you want.
    Final = if Raw = null
            then #table( type table [ #"FA #" = text, Name = text, Email = text ], {} )
            else Table.Distinct( Keyed, {"FA #"} )
in
    Final

// If §1 shows a Kind = "Table" item, the whole thing collapses to:
//
//     let
//         Source = Excel.Workbook( File.Contents( Workbook ), null, true ),
//         Items  = Source{[Item = "<table name>", Kind = "Table"]}[Data],
//         Shaped = Table.SelectColumns( Items, {"Custom1", "Name - Last First", "Email"} ),
//         Named  = Table.RenameColumns( Shaped,
//                      {{"Custom1", "FA #"}, {"Name - Last First", "Name"}} ),
//         Valid  = Table.SelectRows( Named, each [Email] <> null and Text.Contains( [Email], "@" ) )
//     in
//         Table.Distinct( Valid, {"FA #"} )
//
// Use that if you can. Named tables carry their own header and cannot drift.


// -----------------------------------------------------------------------------
// SECTION 3 - Refresh Status                                             (NEW)
//
// New blank query, rename it exactly  Refresh Status
//
// One row per source file the model depends on, carrying the file's last-modified
// stamp.  This is what feeds the title bars.
//
// You cannot get a modified date out of File.Contents - it hands back bytes and
// nothing else.  Folder.Contents does carry it, so each source is located by
// listing its folder and picking the file out by name.  Non-recursive, one
// directory listing per folder, negligible cost.
//
// Every lookup is wrapped in try/otherwise.  A source that has moved, been renamed
// or gone unreachable comes back with a null stamp and shows as "NO FILE" in the
// title bar - it must never take the refresh down, because the whole point is to
// tell you when something is wrong.
//
// Stale After Hours is the per-source SLA.  The QV feed runs twice a day so 18
// hours means "we missed a run"; the account list changes a few times a year, so
// its threshold is generous.  Tune them to your operation - they only drive the
// warning, never the data.
//
// One thing this replaces: Current_Open_Trace carries a column literally NAMED
//     "Updated 7/20/2026 at 1:59:16 PM - (98) Rows of delivery information
//      updated in 31 minute(s), 9 second(s)"
// Someone needed a freshness stamp and the only place to put it was a column
// header, where it froze the moment it was typed. This is that, done properly.
// -----------------------------------------------------------------------------

let
    Root     = "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data",
    QVFolder = Root & "\QV_Data",

    // newest file matching a name pattern in a folder, or null
    //
    // Two filters earn their place.  Extension <> "" drops subdirectories, which
    // Folder.Contents returns alongside files.  Excluding names that start with
    // "~$" drops Excel's lock files - those are created the moment somebody opens
    // a workbook, so without this the stamp would read "modified 10 seconds ago"
    // for as long as anyone has the file open, which is exactly backwards.
    fnNewest = ( folder as text, optional pattern as nullable text ) as record =>
        let
            listing = try Folder.Contents( folder ) otherwise null,
            files   = if listing = null then null
                      else Table.SelectRows( listing,
                               each [Extension] <> null and [Extension] <> ""
                                and not Text.StartsWith( [Name], "~$" )
                                and ( pattern = null
                                      or Text.Contains( Text.Lower( [Name] ), Text.Lower( pattern ) ) ) ),
            // List.Max, not Table.Sort + row 0. Same reason model-fixes-v2.pq §8
            // exists: an ordering you have not forced is an ordering you do not
            // have. This asks for the maximum directly.
            newest  = if files = null or Table.IsEmpty( files ) then null
                      else List.Max( files[Date modified] ),
            row     = if newest = null then null
                      else Table.SelectRows( files, each [Date modified] = newest ){0}
        in
            if row = null then [ Modified = null, File = null, Files = 0 ]
            else [ Modified = newest,
                   File     = row[Name],
                   Files    = Table.RowCount( files ) ],

    Sources = {
        [ Source = "QV export feed",    Folder = QVFolder, Pattern = null,                                       StaleAfterHours = 18   ],
        [ Source = "Trace workbook",    Folder = Root,     Pattern = "QV_Tracing_API_Aligned_Workflow_Optimized", StaleAfterHours = 30   ],
        [ Source = "Resolution tracker",Folder = Root,     Pattern = "ResolutionTracker",                         StaleAfterHours = 30   ],
        [ Source = "Account list",      Folder = Root,     Pattern = "UPS Acct Info",                             StaleAfterHours = 4320 ],
        [ Source = "Coordinate table",  Folder = Root,     Pattern = "Master Coordinate Table",                   StaleAfterHours = 8760 ]
    },

    Now   = DateTime.LocalNow(),

    Built = List.Transform( Sources, ( s ) =>
        let hit = fnNewest( s[Folder], s[Pattern] ) in
        [ Source          = s[Source],
          File            = hit[File],
          Modified        = hit[Modified],
          Files           = hit[Files],
          #"Age Hours"    = if hit[Modified] = null then null
                            else Duration.TotalHours( Now - hit[Modified] ),
          #"Stale After Hours" = s[StaleAfterHours],
          #"Refreshed At" = Now ] ),

    Table_ = Table.FromRecords( Built,
        type table [ Source = text, File = nullable text, Modified = nullable datetime,
                     Files = Int64.Type, #"Age Hours" = nullable number,
                     #"Stale After Hours" = Int64.Type, #"Refreshed At" = datetime ] )
in
    Table_

// After loading:  Table tools > Mark as ... nothing.  Leave Refresh Status
// unrelated to everything - it is a disconnected lookup and relating it would only
// create ambiguity.  Hide it from the Fields pane if you like; the measures in the
// .tmdl are what the report reads.
