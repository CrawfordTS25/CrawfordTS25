// ===========================================================================
// Fact_TimeInTransit
//
// Delivery performance by account and product. This is the source of the 40%
// reliability weight in the recommendation score, so two rules matter:
//
//  1. The extract supplies an "On Time %" column. It is DELIBERATELY NOT
//     loaded. Loading it invites someone to drop it into a visual, where it
//     will be averaged across rows and produce a number that is wrong in a way
//     nobody notices - averaging the March file's On Time % column returns
//     ~98.2% against a true 96.46%, because a 4-package service is weighted
//     equally with a 47,916-package one. Only the counts are loaded; the
//     percentage is computed in DAX as SUM(on-time) / SUM(measured).
//
//  2. This extract is a SHIPPER VIEW population. Fact_VolumeSpend is a PAYOR
//     VIEW population. Packages Measured and Volume are close but not equal
//     and must never be used interchangeably. The ViewType column carries the
//     distinction onto the fact so the Data Quality page can report on it.
// ===========================================================================

let
    Source = Folder.Files(p_SourceFolder),
    OnlyExcel = Table.SelectRows(Source, each Text.EndsWith(Text.Lower([Name]), ".xlsx")
        and not Text.StartsWith([Name], "~$")),

    AllSheets = Table.AddColumn(OnlyExcel, "Sheets", each
        Table.SelectRows(Excel.Workbook([Content], false, true),
            each [Kind] = "Sheet" and not Text.EndsWith(Text.Lower([Item]), "xml"))),

    Expanded = Table.ExpandTableColumn(
        Table.SelectColumns(AllSheets, {"Name", "Sheets"}),
        "Sheets", {"Item", "Data"}, {"SheetName", "Data"}),

    TransitSheets = Table.SelectRows(Expanded, each
        let Cells = List.Transform(
                List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 8)),
                    each List.Transform(_, (c) => fnCleanText(c)))), each _)
        in List.Contains(Cells, "Packages Measured")),

    WithTitle = Table.AddColumn(TransitSheets, "TitleBlock", each
        Text.Combine(List.Transform(
            List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 4)),
                each List.Transform(_, (c) => fnCleanText(c)))), each _), " ")),

    WithPeriod = Table.AddColumn(WithTitle, "FilePeriod",
        each fnParsePeriod([TitleBlock], p_ReportingYear)),

    Shaped = Table.AddColumn(WithPeriod, "Rows", each
        let
            Promoted = fnPromoteUpsHeader([Data], "Packages Measured"),
            Selected = Table.SelectColumns(Promoted, {
                "Sub-Parent Number", "Sub-Parent Name", "Account Number", "Account Name",
                "City", "State", "ZIP", "Product",
                "Packages Measured", "Late by Time", "Late by Day", "Total Late"}),
            Renamed = Table.RenameColumns(Selected, {
                {"Sub-Parent Number", "SubNumber"}, {"Sub-Parent Name", "SubName"},
                {"Account Number", "AccountNumber"}, {"Account Name", "AccountName"},
                {"Product", "RawProduct"}, {"Packages Measured", "PackagesMeasured"},
                {"Late by Time", "LateByTime"}, {"Late by Day", "LateByDay"},
                {"Total Late", "TotalLate"}}),
            Cleaned = Table.SelectRows(Renamed, each
                not fnIsSentinel([SubNumber], [AccountNumber])
                and fnCleanText([RawProduct]) <> ""),
            Typed = Table.TransformColumns(Cleaned, {
                {"PackagesMeasured", each try Number.From(_) otherwise 0, type number},
                {"LateByTime", each try Number.From(_) otherwise 0, type number},
                {"LateByDay", each try Number.From(_) otherwise 0, type number},
                {"TotalLate", each try Number.From(_) otherwise 0, type number}}),
            // Trust the components over the supplied total. Where the total is
            // absent but the components are present, rebuild it.
            Reconciled = Table.TransformColumns(Typed, {
                {"TotalLate", each _, type number}}),
            Fixed = Table.AddColumn(Reconciled, "TotalLateFixed", each
                if [TotalLate] = 0 and ([LateByTime] + [LateByDay]) > 0
                then [LateByTime] + [LateByDay] else [TotalLate], type number),
            OnTime = Table.AddColumn(Fixed, "OnTimePackages",
                each [PackagesMeasured] - [TotalLateFixed], type number),
            Labelled = Table.AddColumn(OnTime, "SubParent",
                each fnSubParentLabel([SubNumber], [SubName])),
            Final = Table.SelectColumns(
                Table.AddColumn(
                    Table.AddColumn(
                        Table.AddColumn(Labelled, "SubNumberClean", each [SubParent][SubNumber], type text),
                        "SubNameClean", each [SubParent][SubName], type text),
                    "IsMaskedSubParent", each [SubParent][IsMaskedSubParent], type text),
                {"SubNumberClean","SubNameClean","IsMaskedSubParent","AccountNumber","AccountName",
                 "City","State","ZIP","RawProduct","PackagesMeasured","LateByTime","LateByDay",
                 "TotalLateFixed","OnTimePackages"}),
            Tagged = Table.AddColumn(
                Table.AddColumn(
                    Table.AddColumn(Final, "MonthNumber", each [FilePeriod][Month], Int64.Type),
                    "SourceFile", each [Name], type text),
                "ViewType", each fnViewType([TitleBlock]), type text)
        in
            Tagged),

    Combined = Table.Combine(Table.ToList(Table.SelectColumns(Shaped, {"Rows"}), each _{0})),

    Renamed = Table.RenameColumns(Combined, {
        {"SubNumberClean", "SubNumber"}, {"SubNameClean", "SubName"},
        {"TotalLateFixed", "TotalLate"}}),

    WithKeys = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(Renamed, "Year", each p_ReportingYear, Int64.Type),
            "MonthKey", each p_ReportingYear * 100 + [MonthNumber], Int64.Type),
        "AccountKey", each fnCleanText([SubNumber]) & "|" & fnCleanText([AccountNumber]), type text),

    WithDate = Table.AddColumn(WithKeys, "DateKey", each #date([Year], [MonthNumber], 1), type date),

    // Join on the TnT vocabulary. The Time-in-Transit extract names services
    // completely differently from Volume & Net Spend ("NEXT DAY AIR" vs
    // "NDA REG / EXPRESS PKG"), which is exactly why Dim_ServiceMapping is a
    // two-vocabulary bridge rather than a simple lookup.
    MappedRaw = Table.NestedJoin(WithDate, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "TnT"), {"RawProduct"},
        "Map", JoinKind.LeftOuter),
    Mapped = Table.ExpandTableColumn(MappedRaw, "Map",
        {"ServiceGroup", "ServiceGroupShort", "ServiceTier", "Scope", "IncludeInRanking"}),
    MapDefaults = Table.TransformColumns(Mapped, {
        {"ServiceGroup", each if _ = null then "Unmapped - Review" else _, type text},
        {"ServiceGroupShort", each if _ = null then "Unmapped" else _, type text},
        {"ServiceTier", each if _ = null then "Unmapped" else _, type text},
        {"Scope", each if _ = null then "Unknown" else _, type text},
        {"IncludeInRanking", each if _ = null then "No" else _, type text}})
in
    MapDefaults
