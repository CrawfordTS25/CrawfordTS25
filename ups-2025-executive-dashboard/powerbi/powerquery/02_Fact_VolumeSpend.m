// ===========================================================================
// Fact_VolumeSpend
//
// Folder-based load of every Volume & Net Spend extract in the source folder,
// handling BOTH layouts UPS ships and resolving the overlap between them.
//
// ---------------------------------------------------------------------------
// THE DOUBLE-COUNT TRAP - the single most important thing in this query
// ---------------------------------------------------------------------------
// UPS supplies two different Volume & Net Spend layouts:
//
//   Schema A  "Monthly VnR by Product by Account" / "VnR_YTD <year>"
//             Header on row 6, TY/LY/Diff sub-header on row 7, data from row 8.
//             Carries a WE/Mo/Qtr period column and prior-year comparatives.
//             CRITICALLY: some of these files are YEAR-TO-DATE. The February
//             file contains January AND February.
//
//   Schema B  "VnS"
//             Header on row 5, data from row 6. Single period, no comparatives,
//             period stated only in the title block.
//
// A straight "Get Data > Folder" append of a January monthly file and a
// February year-to-date file double-counts January exactly. Measured against
// the real files this is a 100% overstatement of January volume and spend, and
// roughly a 40% overstatement of the Q1 total - with no error, no warning, and
// a total that still looks entirely plausible.
//
// The dedupe step below is therefore not a tidy-up. It is the difference
// between a correct model and a confidently wrong one, and it must survive any
// future edit to this query.
// ===========================================================================

let
    Source = Folder.Files(p_SourceFolder),

    OnlyExcel = Table.SelectRows(
        Source,
        each Text.EndsWith(Text.Lower([Name]), ".xlsx")
            and not Text.StartsWith([Name], "~$")),

    // Read every worksheet in every workbook, discarding the Cognos/OBIEE
    // query-definition tabs that UPS appends ("TnT Xml", "VnS Xml", ...).
    AllSheets = Table.AddColumn(OnlyExcel, "Sheets", each
        Table.SelectRows(
            Excel.Workbook([Content], false, true),
            each [Kind] = "Sheet" and not Text.EndsWith(Text.Lower([Item]), "xml"))),

    Expanded = Table.ExpandTableColumn(
        Table.SelectColumns(AllSheets, {"Name", "Sheets"}),
        "Sheets", {"Item", "Data"}, {"SheetName", "Data"}),

    // Classify by SHAPE, not by sheet name. UPS renames the tab between months
    // ("Monthly VnR by Product by Accou", "VnR_YTD 2025", "VnS"), so name
    // matching alone breaks on the next delivery.
    Classified = Table.AddColumn(Expanded, "Layout", each
        let
            Probe = Table.FirstN([Data], 8),
            Cells = List.Transform(
                List.Combine(List.Transform(Table.ToRows(Probe),
                    each List.Transform(_, (c) => fnCleanText(c)))), each _)
        in
            if List.Contains(Cells, "WE/Mo/Qtr") then "SchemaA"
            else if List.Contains(Cells, "Packages Measured") then "TnT"
            else if List.Contains(Cells, "Claims Category") then "Claims"
            else if List.Contains(Cells, "Base or Accessorial Charge") then "Accessorial"
            else if List.Contains(Cells, "Net Spend per Piece")
                 or List.Contains(Cells, "Package Billed Weight Lbs") then "SchemaB"
            else "Unknown"),

    VolumeSheets = Table.SelectRows(Classified, each [Layout] = "SchemaA" or [Layout] = "SchemaB"),

    // Capture the title block before the header is promoted - it is the only
    // place a Schema B file states its reporting period.
    WithTitle = Table.AddColumn(VolumeSheets, "TitleBlock", each
        Text.Combine(
            List.Transform(
                List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 4)),
                    each List.Transform(_, (c) => fnCleanText(c)))),
                each _),
            " ")),

    WithPeriod = Table.AddColumn(WithTitle, "FilePeriod",
        each fnParsePeriod([TitleBlock], p_ReportingYear)),
    WithView = Table.AddColumn(WithPeriod, "ViewType", each fnViewType([TitleBlock])),

    // -----------------------------------------------------------------------
    // Normalise each layout to a common column set.
    // -----------------------------------------------------------------------
    Normalised = Table.AddColumn(WithView, "Normalised", each
        let
            Layout = [Layout],
            Period = [FilePeriod],
            Promoted = fnPromoteUpsHeader([Data],
                if Layout = "SchemaA" then "WE/Mo/Qtr" else "Net Spend per Piece"),

            // Schema A repeats each measure as TY / LY / Diff, which arrives
            // from Excel.Workbook as Volume / Column10 / Column11 style names.
            // Select positionally against the promoted header instead of
            // guessing at the generated names.
            Cols = Table.ColumnNames(Promoted),
            Pick = (name as text, offset as number) as text =>
                let Base = List.PositionOf(Cols, name)
                in if Base = -1 then error Error.Record(
                        "UPS.ColumnNotFound",
                        "Expected column '" & name & "' was not found.",
                        "Available: " & Text.Combine(Cols, ", "))
                   else Cols{Base + offset},

            Shaped =
                if Layout = "SchemaA" then
                    Table.SelectColumns(Promoted, {
                        "Sub Number", "Sub Name", "Account Number", "Account Name",
                        "City", "State", "Product", "WE/Mo/Qtr",
                        Pick("Volume", 0), Pick("Gross Spend", 0),
                        Pick("Net Spend", 0), Pick("Incentive", 0),
                        Pick("Billed Weight Lbs", 0), Pick("Volume", 1), Pick("Net Spend", 1)})
                else
                    Table.SelectColumns(Promoted, {
                        "Sub-Parent Number", "Sub-Parent Name", "Account Number", "Account Name",
                        "City", "State", "ZIP", "Product",
                        "Volume", "Gross Spend", "Net Spend", "Package Billed Weight Lbs"}),

            Renamed =
                if Layout = "SchemaA" then
                    Table.RenameColumns(Shaped, List.Zip({
                        Table.ColumnNames(Shaped),
                        {"SubNumber","SubName","AccountNumber","AccountName","City","State",
                         "RawProduct","PeriodColumn","Volume","GrossSpend","NetSpend",
                         "Incentive","BilledWeightLbs","VolumeLY","NetSpendLY"}}))
                else
                    Table.RenameColumns(Shaped, List.Zip({
                        Table.ColumnNames(Shaped),
                        {"SubNumber","SubName","AccountNumber","AccountName","City","State",
                         "ZIP","RawProduct","Volume","GrossSpend","NetSpend","BilledWeightLbs"}})),

            WithMissing = Table.AddColumn(
                if Layout = "SchemaA"
                    then Table.AddColumn(Renamed, "ZIP", each "", type text)
                    else Table.AddColumn(
                            Table.AddColumn(
                                Table.AddColumn(Renamed, "Incentive",
                                    each (try Number.From([GrossSpend]) otherwise 0)
                                       - (try Number.From([NetSpend]) otherwise 0), type number),
                                "VolumeLY", each null, type number),
                            "NetSpendLY", each null, type number),
                "PeriodResolved",
                each if Layout = "SchemaA"
                     // The period column is authoritative here: a YTD file
                     // carries several months in one sheet.
                     then try Number.From([PeriodColumn]) otherwise Period[Month]
                     else Period[Month]),

            Cleaned = Table.SelectRows(WithMissing, each
                not fnIsSentinel([SubNumber], [AccountNumber])
                and fnCleanText([RawProduct]) <> ""
                and [PeriodResolved] <> null),

            Typed = Table.TransformColumns(Cleaned, {
                {"Volume", each try Number.From(_) otherwise 0, type number},
                {"GrossSpend", each try Number.From(_) otherwise 0, type number},
                {"NetSpend", each try Number.From(_) otherwise 0, type number},
                {"Incentive", each try Number.From(_) otherwise 0, type number},
                {"BilledWeightLbs", each try Number.From(_) otherwise 0, type number}}),

            Labelled = Table.AddColumn(Typed, "SubParent",
                each fnSubParentLabel([SubNumber], [SubName])),

            Final = Table.SelectColumns(
                Table.AddColumn(
                    Table.AddColumn(
                        Table.AddColumn(Labelled, "SubNumberClean", each [SubParent][SubNumber], type text),
                        "SubNameClean", each [SubParent][SubName], type text),
                    "IsMaskedSubParent", each [SubParent][IsMaskedSubParent], type text),
                {"SubNumberClean","SubNameClean","IsMaskedSubParent","AccountNumber","AccountName",
                 "City","State","ZIP","RawProduct","PeriodResolved","Volume","GrossSpend",
                 "NetSpend","Incentive","BilledWeightLbs","VolumeLY","NetSpendLY"})
        in
            Final),

    Combined = Table.Combine(
        Table.ToList(Table.SelectColumns(
            Table.AddColumn(Normalised, "Tagged", each
                Table.AddColumn(
                    Table.AddColumn(
                        Table.AddColumn([Normalised], "SourceFile", each [Name], type text),
                        "SourceLayout", each [Layout], type text),
                    "ViewType", each [ViewType], type text)),
            {"Tagged"}), each _{0})),

    Renamed2 = Table.RenameColumns(Combined, {
        {"SubNumberClean", "SubNumber"}, {"SubNameClean", "SubName"},
        {"PeriodResolved", "MonthNumber"}}),

    WithKeys = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(Renamed2, "Year", each p_ReportingYear, Int64.Type),
            "MonthKey", each p_ReportingYear * 100 + [MonthNumber], Int64.Type),
        "AccountKey", each fnCleanText([SubNumber]) & "|" & fnCleanText([AccountNumber]), type text),

    WithDate = Table.AddColumn(WithKeys, "DateKey",
        each #date([Year], [MonthNumber], 1), type date),
    WithQuarter = Table.AddColumn(WithDate, "Quarter",
        each "Q" & Text.From(Number.RoundUp([MonthNumber] / 3)), type text),

    // -----------------------------------------------------------------------
    // DEDUPE - see the header note. Read before editing.
    //
    // Sort so that single-period files precede year-to-date files, then keep
    // the first row per (Year, Month, Account, Product). Table.Buffer is
    // required: without it the sort is not guaranteed to be honoured by the
    // distinct step and the wrong row can win non-deterministically.
    // -----------------------------------------------------------------------
    WithPrecedence = Table.AddColumn(WithQuarter, "SourcePrecedence",
        each if Text.Contains(Text.Upper([SourceFile]), "YTD") then 1 else 0, Int64.Type),

    Sorted = Table.Buffer(Table.Sort(WithPrecedence, {
        {"Year", Order.Ascending}, {"MonthNumber", Order.Ascending},
        {"AccountKey", Order.Ascending}, {"RawProduct", Order.Ascending},
        {"SourcePrecedence", Order.Ascending}})),

    Deduped = Table.Distinct(Sorted, {"Year", "MonthNumber", "AccountKey", "RawProduct"}),

    // -----------------------------------------------------------------------
    // Service mapping and row-level quality flags.
    // -----------------------------------------------------------------------
    MappedRaw = Table.NestedJoin(
        Deduped, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "VnS"), {"RawProduct"},
        "Map", JoinKind.LeftOuter),

    Mapped = Table.ExpandTableColumn(MappedRaw, "Map",
        {"ServiceGroup", "ServiceGroupShort", "ServiceTier", "Scope", "IncludeInRanking"}),

    // An unmapped product must never silently inherit a service group. It is
    // routed to a review bucket and surfaced on the Data Quality page.
    MapDefaults = Table.TransformColumns(Mapped, {
        {"ServiceGroup", each if _ = null then "Unmapped - Review" else _, type text},
        {"ServiceGroupShort", each if _ = null then "Unmapped" else _, type text},
        {"ServiceTier", each if _ = null then "Unmapped" else _, type text},
        {"Scope", each if _ = null then "Unknown" else _, type text},
        {"IncludeInRanking", each if _ = null then "No" else _, type text}}),

    Flags = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(MapDefaults, "HasVolume",
                each if [Volume] > 0 then "Yes" else "No", type text),
            "IsSpendOnlyAdjustment",
            each if [Volume] <= 0 and Number.Abs([NetSpend]) > 0 then "Yes" else "No", type text),
        "IsNegativeSpend", each if [NetSpend] < 0 then "Yes" else "No", type text),

    FinalTypes = Table.TransformColumnTypes(Flags, {
        {"SubNumber", type text}, {"SubName", type text}, {"AccountNumber", type text},
        {"AccountName", type text}, {"City", type text}, {"State", type text},
        {"ZIP", type text}, {"RawProduct", type text}, {"MonthNumber", Int64.Type},
        {"Volume", type number}, {"GrossSpend", Currency.Type}, {"NetSpend", Currency.Type},
        {"Incentive", Currency.Type}, {"BilledWeightLbs", type number}})
in
    FinalTypes
