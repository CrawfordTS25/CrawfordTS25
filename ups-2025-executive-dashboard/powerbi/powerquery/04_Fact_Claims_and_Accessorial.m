// ===========================================================================
// Fact_Claims  and  Fact_Accessorial
// Create these as two separate queries; both are given here because they share
// the same discovery and title-parsing scaffolding.
// ===========================================================================


// ---------------------------------------------------------------------------
// Fact_Claims
//
// NOTE THE MISSING COLUMN. This extract carries Sub-Parent, Account and Claims
// Category - and no product, service, or tracking number. There is therefore
// no join path from this table to Dim_ServiceMapping, and no way to state a
// loss claim rate "by service" from this source.
//
// The build guide assigns 30% of the recommendation weight to Loss Claim Rate.
// That weight cannot be allocated at service grain until UPS adds a service or
// tracking field to this export. Do NOT create a relationship from this table
// to Dim_ServiceMapping - an inactive or many-to-many relationship here would
// produce plausible-looking service-level claim rates that are pure artefact.
// The model deliberately leaves the join absent so the gap is structural and
// visible rather than hidden inside a measure.
// ---------------------------------------------------------------------------
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

    ClaimsSheets = Table.SelectRows(Expanded, each
        let Cells = List.Transform(
                List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 8)),
                    each List.Transform(_, (c) => fnCleanText(c)))), each _)
        in List.Contains(Cells, "Claims Category")),

    WithTitle = Table.AddColumn(ClaimsSheets, "TitleBlock", each
        Text.Combine(List.Transform(
            List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 4)),
                each List.Transform(_, (c) => fnCleanText(c)))), each _), " ")),
    WithPeriod = Table.AddColumn(WithTitle, "FilePeriod",
        each fnParsePeriod([TitleBlock], p_ReportingYear)),

    Shaped = Table.AddColumn(WithPeriod, "Rows", each
        let
            Promoted = fnPromoteUpsHeader([Data], "Claims Category"),
            Selected = Table.SelectColumns(Promoted, {
                "Sub-Parent Number", "Sub-Parent Name", "Account Number", "Account Name",
                "Claims Category", "Issued Claims Qty", "Issued Claims Pkg Qty",
                "Paid Claims Qty", "Paid Claims Pkg Qty",
                "Registered Claims Qty", "Registered Claims Pkg Qty",
                "Paid Claims Amount", "Claims Declared Value"}),
            Renamed = Table.RenameColumns(Selected, {
                {"Sub-Parent Number", "SubNumber"}, {"Sub-Parent Name", "SubName"},
                {"Account Number", "AccountNumber"}, {"Account Name", "AccountName"},
                {"Claims Category", "ClaimsCategory"},
                {"Issued Claims Qty", "IssuedClaimsQty"},
                {"Issued Claims Pkg Qty", "IssuedClaimsPkgQty"},
                {"Paid Claims Qty", "PaidClaimsQty"},
                {"Paid Claims Pkg Qty", "PaidClaimsPkgQty"},
                {"Registered Claims Qty", "RegisteredClaimsQty"},
                {"Registered Claims Pkg Qty", "RegisteredClaimsPkgQty"},
                {"Paid Claims Amount", "PaidClaimsAmount"},
                {"Claims Declared Value", "ClaimsDeclaredValue"}}),
            // Blank category rows are report padding, not claim activity.
            Cleaned = Table.SelectRows(Renamed, each
                not fnIsSentinel([SubNumber], [AccountNumber])
                and fnCleanText([ClaimsCategory]) <> ""),
            Typed = Table.TransformColumns(Cleaned, {
                {"IssuedClaimsQty", each try Number.From(_) otherwise 0, type number},
                {"IssuedClaimsPkgQty", each try Number.From(_) otherwise 0, type number},
                {"PaidClaimsQty", each try Number.From(_) otherwise 0, type number},
                {"PaidClaimsPkgQty", each try Number.From(_) otherwise 0, type number},
                {"RegisteredClaimsQty", each try Number.From(_) otherwise 0, type number},
                {"RegisteredClaimsPkgQty", each try Number.From(_) otherwise 0, type number},
                {"PaidClaimsAmount", each try Number.From(_) otherwise 0, Currency.Type},
                {"ClaimsDeclaredValue", each try Number.From(_) otherwise 0, Currency.Type}}),
            Labelled = Table.AddColumn(Typed, "SubParent",
                each fnSubParentLabel([SubNumber], [SubName])),
            Expandedsp = Table.AddColumn(
                Table.AddColumn(Labelled, "SubNumberClean", each [SubParent][SubNumber], type text),
                "SubNameClean", each [SubParent][SubName], type text),
            Loss = Table.AddColumn(Expandedsp, "IsLoss",
                each if Text.Lower(fnCleanText([ClaimsCategory])) = "loss" then "Yes" else "No", type text),
            // Stamped on every row so the limitation travels with the data into
            // any export, drillthrough, or copied visual.
            Attribution = Table.AddColumn(Loss, "ServiceAttribution",
                each "Not Available", type text),
            Tagged = Table.AddColumn(
                Table.AddColumn(Attribution, "MonthNumber", each [FilePeriod][Month], Int64.Type),
                "SourceFile", each [Name], type text)
        in
            Table.SelectColumns(Tagged, {
                "SubNumberClean","SubNameClean","AccountNumber","AccountName","ClaimsCategory",
                "IsLoss","IssuedClaimsQty","IssuedClaimsPkgQty","PaidClaimsQty","PaidClaimsPkgQty",
                "RegisteredClaimsQty","RegisteredClaimsPkgQty","PaidClaimsAmount",
                "ClaimsDeclaredValue","ServiceAttribution","MonthNumber","SourceFile"})),

    Combined = Table.Combine(Table.ToList(Table.SelectColumns(Shaped, {"Rows"}), each _{0})),
    Renamed2 = Table.RenameColumns(Combined,
        {{"SubNumberClean", "SubNumber"}, {"SubNameClean", "SubName"}}),
    WithKeys = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(Renamed2, "Year", each p_ReportingYear, Int64.Type),
            "MonthKey", each p_ReportingYear * 100 + [MonthNumber], Int64.Type),
        "AccountKey", each fnCleanText([SubNumber]) & "|" & fnCleanText([AccountNumber]), type text),
    WithDate = Table.AddColumn(WithKeys, "DateKey", each #date([Year], [MonthNumber], 1), type date)
in
    WithDate


// ---------------------------------------------------------------------------
// Fact_Accessorial
//
// Not in the original build guide's data model. Added because it is the only
// table that explains WHY cost per shipment moves. Net spend on its own says
// costs rose; this says the rise was fuel surcharge, address corrections, or
// residential delivery - the difference between a carrier conversation and an
// internal process fix.
//
// Address Correction in particular is a pure self-inflicted cost: every unit is
// a package that shipped to a bad address the firm supplied. It is the single
// most actionable line in the entire data set and it appears nowhere in the
// Volume & Net Spend extract.
//
// Reconciliation guarantee: for a given month this table's NetSpend must sum to
// exactly the same value as Fact_VolumeSpend's NetSpend. That equality is a
// free, strong integrity check and is wired to [Reconciliation Status].
// ---------------------------------------------------------------------------
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

    AccSheets = Table.SelectRows(Expanded, each
        let Cells = List.Transform(
                List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 8)),
                    each List.Transform(_, (c) => fnCleanText(c)))), each _)
        in List.Contains(Cells, "Base or Accessorial Charge")),

    WithTitle = Table.AddColumn(AccSheets, "TitleBlock", each
        Text.Combine(List.Transform(
            List.Combine(List.Transform(Table.ToRows(Table.FirstN([Data], 4)),
                each List.Transform(_, (c) => fnCleanText(c)))), each _), " ")),
    WithPeriod = Table.AddColumn(WithTitle, "FilePeriod",
        each fnParsePeriod([TitleBlock], p_ReportingYear)),

    Shaped = Table.AddColumn(WithPeriod, "Rows", each
        let
            Promoted = fnPromoteUpsHeader([Data], "Base or Accessorial Charge"),
            Selected = Table.SelectColumns(Promoted, {
                "Sub-Parent Number", "Sub-Parent Name", "Account Number", "Account Name",
                "City", "State", "ZIP", "Product", "Freight Type Description",
                "Base or Accessorial Charge", "Number of Units",
                "Accessorial Spend", "Gross Spend", "Net Spend"}),
            Renamed = Table.RenameColumns(Selected, {
                {"Sub-Parent Number", "SubNumber"}, {"Sub-Parent Name", "SubName"},
                {"Account Number", "AccountNumber"}, {"Account Name", "AccountName"},
                {"Product", "RawProduct"},
                {"Freight Type Description", "FreightTypeDescription"},
                {"Base or Accessorial Charge", "ChargeCategory"},
                {"Number of Units", "NumberOfUnits"},
                {"Accessorial Spend", "AccessorialSpend"},
                {"Gross Spend", "GrossSpend"}, {"Net Spend", "NetSpend"}}),
            Cleaned = Table.SelectRows(Renamed, each
                not fnIsSentinel([SubNumber], [AccountNumber])
                and fnCleanText([ChargeCategory]) <> ""),
            Typed = Table.TransformColumns(Cleaned, {
                {"NumberOfUnits", each try Number.From(_) otherwise 0, type number},
                {"AccessorialSpend", each try Number.From(_) otherwise 0, Currency.Type},
                {"GrossSpend", each try Number.From(_) otherwise 0, Currency.Type},
                {"NetSpend", each try Number.From(_) otherwise 0, Currency.Type}}),
            Flagged = Table.AddColumn(Typed, "IsAccessorial",
                each if Text.Upper(fnCleanText([FreightTypeDescription])) = "ACCESSORIAL"
                     then "Yes" else "No", type text),
            Labelled = Table.AddColumn(Flagged, "SubParent",
                each fnSubParentLabel([SubNumber], [SubName])),
            Clean2 = Table.AddColumn(
                Table.AddColumn(Labelled, "SubNumberClean", each [SubParent][SubNumber], type text),
                "SubNameClean", each [SubParent][SubName], type text),
            Tagged = Table.AddColumn(
                Table.AddColumn(Clean2, "MonthNumber", each [FilePeriod][Month], Int64.Type),
                "SourceFile", each [Name], type text)
        in
            Table.SelectColumns(Tagged, {
                "SubNumberClean","SubNameClean","AccountNumber","AccountName","State",
                "RawProduct","FreightTypeDescription","ChargeCategory","IsAccessorial",
                "NumberOfUnits","AccessorialSpend","GrossSpend","NetSpend",
                "MonthNumber","SourceFile"})),

    Combined = Table.Combine(Table.ToList(Table.SelectColumns(Shaped, {"Rows"}), each _{0})),
    Renamed2 = Table.RenameColumns(Combined,
        {{"SubNumberClean", "SubNumber"}, {"SubNameClean", "SubName"}}),
    WithKeys = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(Renamed2, "Year", each p_ReportingYear, Int64.Type),
            "MonthKey", each p_ReportingYear * 100 + [MonthNumber], Int64.Type),
        "AccountKey", each fnCleanText([SubNumber]) & "|" & fnCleanText([AccountNumber]), type text),
    WithDate = Table.AddColumn(WithKeys, "DateKey", each #date([Year], [MonthNumber], 1), type date),
    MappedRaw = Table.NestedJoin(WithDate, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "VnS"), {"RawProduct"},
        "Map", JoinKind.LeftOuter),
    Mapped = Table.ExpandTableColumn(MappedRaw, "Map", {"ServiceGroup", "ServiceGroupShort"}),
    MapDefaults = Table.TransformColumns(Mapped, {
        {"ServiceGroup", each if _ = null then "Unmapped - Review" else _, type text},
        {"ServiceGroupShort", each if _ = null then "Unmapped" else _, type text}})
in
    MapDefaults
