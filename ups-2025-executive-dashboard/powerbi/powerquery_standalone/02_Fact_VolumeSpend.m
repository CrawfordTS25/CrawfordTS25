// ===========================================================================
// 3. QUERY  Fact_VolumeSpend
// ===========================================================================
// New Source > Blank Query > rename to Fact_VolumeSpend > Advanced Editor >
// paste everything below this banner.
//
// UPS ships two different Volume & Net Spend layouts and this query reads both:
//
//   Schema A - January and February files
//       Header on row 6, TY/LY/Diff sub-header on row 7, data from row 8.
//       Carries a WE/Mo/Qtr period column and prior-year comparatives, so each
//       measure appears three times across the row (this year / last year /
//       difference). Only the this-year columns are taken.
//
//   Schema B - March and April files ("VnS" sheet)
//       Header on row 5, data from row 6. One period, no comparatives.
//
// ---------------------------------------------------------------------------
// THE YEAR-TO-DATE TRAP - the most important thing in this query
// ---------------------------------------------------------------------------
// The February file is a YEAR-TO-DATE extract. It contains January AND February.
// The January file contains January.
//
// Loading both wholesale double-counts January exactly: a 100% overstatement of
// that month, roughly 40% of the loaded period, with no error, no warning, and
// a total that still looks entirely plausible.
//
// This query avoids it structurally rather than cleverly: the February step
// filters to month 2 only, and January comes from the January file. Nothing to
// deduplicate, nothing to get wrong.
//
// If a future monthly file also arrives as year-to-date, copy the February step
// and filter it to its own month the same way.
// ===========================================================================

let
    // --- local helpers -----------------------------------------------------

    // UPS prefixes ID-like columns with an apostrophe to stop Excel reformatting
    // them. Left in place, "'ABC123" and "ABC123" are different keys and the
    // account relationship silently half-fails.
    Clean = (v) as text =>
        let
            t = if v = null then "" else Text.Trim(Text.From(v))
        in
            Text.Trim(if Text.StartsWith(t, "'") then Text.RemoveRange(t, 0, 1) else t),

    Num = (v) as number => if v = null then 0 else (try Number.From(v) otherwise 0),

    // Drop report artefacts only - Grand Total lines and rows with no account.
    // Deliberately NOT keyed on the sub-parent: UPS masks it with "@@" on some
    // accounts, and those rows carry a real account number and real shipment
    // volume. Filtering on "@@" - the obvious move - silently deletes genuine
    // international activity.
    KeepRow = (sub, acct) as logical =>
        let
            s = Text.Lower(Clean(sub)),
            a = Text.Lower(Clean(acct))
        in
            not (s = "grand total" or s = "total" or a = "grand total" or a = "total")
            and not (a = "" and s = ""),

    SubNameOf = (numv, namev) as text =>
        if Clean(numv) = "@@" or Clean(namev) = "@@"
        then "Unassigned Sub-Parent"
        else Clean(namev),

    MaskedOf = (numv, namev) as text =>
        if Clean(numv) = "@@" or Clean(namev) = "@@" then "Yes" else "No",

    // ------------------------------------------------------------------
    // Locating the monthly files
    //
    // The delivered names are irregular: separators drift between "_" and " ",
    // "1x" and "1X", "Volume & Net Spend" and "Volume  Net Spend", and every
    // file carries a different UPS request number. Two files even share one
    // request number. Matching an exact name would be fragile and would need
    // the names transcribed correctly in the first place.
    //
    // So files are found by their MONTH PREFIX - "1-JAN", "3-MAR" - which is
    // the one part of the convention that has held across every delivery.
    // ------------------------------------------------------------------
    Files = Folder.Files(p_Folder),

    PickWorkbook = (prefix as text) as binary =>
        let
            Hits = Table.SelectRows(Files, each
                Text.StartsWith(Text.Upper([Name]), Text.Upper(prefix))
                and Text.EndsWith(Text.Lower([Name]), ".xlsx")
                and not Text.StartsWith([Name], "~$"))
        in
            if Table.IsEmpty(Hits) then
                error Error.Record(
                    "UPS.FileNotFound",
                    "No .xlsx file in the folder starts with '" & prefix & "'.",
                    "Checked: " & p_Folder)
            else
                Hits{0}[Content],

    FirstSheet = (prefix as text) as table =>
        Table.SelectRows(
            Excel.Workbook(PickWorkbook(prefix), null, true),
            each [Kind] = "Sheet"){0}[Data],

    NamedSheet = (prefix as text, sheet as text) as table =>
        Excel.Workbook(PickWorkbook(prefix), null, true)
            {[Item = sheet, Kind = "Sheet"]}[Data],

    // --- Schema A: January / February layout -------------------------------
    // Column offsets, verified against the real extracts:
    //   Column2  Sub Number        Column3  Sub Name
    //   Column4  Account Number    Column5  Account Name
    //   Column6  City              Column7  State
    //   Column8  Product           Column9  WE/Mo/Qtr (period)
    //   Column10 Volume (TY)       Column19 Gross Spend (TY)
    //   Column22 Net Spend (TY)    Column25 Incentive (TY)
    //   Column31 Billed Weight Lbs (TY)
    ReadSchemaA = (prefix as text, monthNo as number) as table =>
        let
            Rows = Table.Skip(FirstSheet(prefix), 7),
            Pick = Table.SelectColumns(Rows, {
                "Column2", "Column3", "Column4", "Column5", "Column6", "Column7",
                "Column8", "Column9", "Column10", "Column19", "Column22",
                "Column25", "Column31"}),
            Named = Table.RenameColumns(Pick, {
                {"Column2", "SubNumberRaw"}, {"Column3", "SubNameRaw"},
                {"Column4", "AccountNumberRaw"}, {"Column5", "AccountNameRaw"},
                {"Column6", "CityRaw"}, {"Column7", "StateRaw"},
                {"Column8", "ProductRaw"}, {"Column9", "PeriodRaw"},
                {"Column10", "VolumeRaw"}, {"Column19", "GrossRaw"},
                {"Column22", "NetRaw"}, {"Column25", "IncentiveRaw"},
                {"Column31", "WeightRaw"}}),
            // The period column is authoritative here. A YTD file holds several
            // months, so this filter is what keeps January out of the February load.
            Kept = Table.SelectRows(Named, each
                KeepRow([SubNumberRaw], [AccountNumberRaw])
                and Clean([ProductRaw]) <> ""
                and Num([PeriodRaw]) = monthNo),
            Shaped = Table.AddColumn(Kept, "Rec", each [
                MonthNumber       = monthNo,
                SubNumber         = Clean([SubNumberRaw]),
                SubName           = SubNameOf([SubNumberRaw], [SubNameRaw]),
                IsMaskedSubParent = MaskedOf([SubNumberRaw], [SubNameRaw]),
                AccountNumber     = Clean([AccountNumberRaw]),
                AccountName       = Clean([AccountNameRaw]),
                City              = Clean([CityRaw]),
                State             = Clean([StateRaw]),
                ZIP               = "",
                RawProduct        = Clean([ProductRaw]),
                Volume            = Num([VolumeRaw]),
                GrossSpend        = Num([GrossRaw]),
                NetSpend          = Num([NetRaw]),
                Incentive         = Num([IncentiveRaw]),
                BilledWeightLbs   = Num([WeightRaw])
            ]),
            Out = Table.FromRecords(Table.Column(Shaped, "Rec"))
        in
            Out,

    // --- Schema B: March / April "VnS" layout ------------------------------
    //   Column2  Sub-Parent Number  Column3  Sub-Parent Name
    //   Column4  Account Number     Column5  Account Name
    //   Column7  City               Column8  State           Column9  ZIP
    //   Column10 Product            Column11 Volume
    //   Column12 Package Billed Weight Lbs
    //   Column14 Gross Spend        Column15 Net Spend
    ReadSchemaB = (sheet as table, monthNo as number) as table =>
        let
            Rows = Table.Skip(sheet, 5),
            Pick = Table.SelectColumns(Rows, {
                "Column2", "Column3", "Column4", "Column5", "Column7", "Column8",
                "Column9", "Column10", "Column11", "Column12", "Column14", "Column15"}),
            Named = Table.RenameColumns(Pick, {
                {"Column2", "SubNumberRaw"}, {"Column3", "SubNameRaw"},
                {"Column4", "AccountNumberRaw"}, {"Column5", "AccountNameRaw"},
                {"Column7", "CityRaw"}, {"Column8", "StateRaw"},
                {"Column9", "ZipRaw"}, {"Column10", "ProductRaw"},
                {"Column11", "VolumeRaw"}, {"Column12", "WeightRaw"},
                {"Column14", "GrossRaw"}, {"Column15", "NetRaw"}}),
            Kept = Table.SelectRows(Named, each
                KeepRow([SubNumberRaw], [AccountNumberRaw])
                and Clean([ProductRaw]) <> ""),
            Shaped = Table.AddColumn(Kept, "Rec", each [
                MonthNumber       = monthNo,
                SubNumber         = Clean([SubNumberRaw]),
                SubName           = SubNameOf([SubNumberRaw], [SubNameRaw]),
                IsMaskedSubParent = MaskedOf([SubNumberRaw], [SubNameRaw]),
                AccountNumber     = Clean([AccountNumberRaw]),
                AccountName       = Clean([AccountNameRaw]),
                City              = Clean([CityRaw]),
                State             = Clean([StateRaw]),
                ZIP               = Clean([ZipRaw]),
                RawProduct        = Clean([ProductRaw]),
                Volume            = Num([VolumeRaw]),
                GrossSpend        = Num([GrossRaw]),
                NetSpend          = Num([NetRaw]),
                // Schema B has no incentive column; derive it.
                Incentive         = Num([GrossRaw]) - Num([NetRaw]),
                BilledWeightLbs   = Num([WeightRaw])
            ]),
            Out = Table.FromRecords(Table.Column(Shaped, "Rec"))
        in
            Out,

    // --- the four months ---------------------------------------------------
    Jan = ReadSchemaA("1-JAN", 1),
    // Month 2 ONLY. This file also contains January - see the banner note.
    Feb = ReadSchemaA("2-FEB", 2),
    Mar = ReadSchemaB(NamedSheet("3-MAR", "VnS"), 3),
    Apr = ReadSchemaB(FirstSheet("4-APR"), 4),

    Combined = Table.Combine({Jan, Feb, Mar, Apr}),

    // --- keys and derived columns ------------------------------------------
    WithKeys = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(
                Table.AddColumn(Combined, "Year", each 2025, Int64.Type),
                "MonthKey", each 2025 * 100 + [MonthNumber], Int64.Type),
            "AccountKey", each [SubNumber] & "|" & [AccountNumber], type text),
        "Quarter", each "Q" & Text.From(Number.RoundUp([MonthNumber] / 3)), type text),

    WithDate = Table.AddColumn(WithKeys, "DateKey",
        each #date(2025, [MonthNumber], 1), type date),

    WithMonthName = Table.AddColumn(WithDate, "MonthName",
        each Date.ToText(#date(2025, [MonthNumber], 1), "MMM"), type text),

    // --- service mapping ----------------------------------------------------
    // Join to the VnS half of the bridge. An unmapped product routes to a review
    // bucket rather than silently inheriting a neighbouring service group.
    Joined = Table.NestedJoin(WithMonthName, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "VnS"), {"RawProduct"},
        "Map", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "Map",
        {"ServiceGroup", "ServiceGroupShort", "ServiceTier", "Scope",
         "IncludeInRanking"}),
    Defaults = Table.TransformColumns(Expanded, {
        {"ServiceGroup", each if _ = null then "Unmapped - Review" else _, type text},
        {"ServiceGroupShort", each if _ = null then "Unmapped" else _, type text},
        {"ServiceTier", each if _ = null then "Unmapped" else _, type text},
        {"Scope", each if _ = null then "Unknown" else _, type text},
        {"IncludeInRanking", each if _ = null then "No" else _, type text}}),

    // --- row-level quality flags -------------------------------------------
    // Kept on the fact so the Data Quality page can quantify what the executive
    // visuals exclude, rather than the exclusion being invisible in a filter pane.
    Flags = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(Defaults, "HasVolume",
                each if [Volume] > 0 then "Yes" else "No", type text),
            "IsSpendOnlyAdjustment",
            each if [Volume] <= 0 and Number.Abs([NetSpend]) > 0 then "Yes" else "No", type text),
        "IsNegativeSpend", each if [NetSpend] < 0 then "Yes" else "No", type text),

    Typed = Table.TransformColumnTypes(Flags, {
        {"MonthNumber", Int64.Type}, {"SubNumber", type text}, {"SubName", type text},
        {"AccountNumber", type text}, {"AccountName", type text},
        {"City", type text}, {"State", type text}, {"ZIP", type text},
        {"RawProduct", type text}, {"Volume", type number},
        {"GrossSpend", Currency.Type}, {"NetSpend", Currency.Type},
        {"Incentive", Currency.Type}, {"BilledWeightLbs", type number}})
in
    Typed
