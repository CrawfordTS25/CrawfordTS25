// ===========================================================================
// 4. QUERY  Fact_TimeInTransit
// ===========================================================================
// New Source > Blank Query > rename to Fact_TimeInTransit > Advanced Editor.
//
// Reads the "TnT" sheet of the March file. This is the source of the 40%
// reliability weight in the recommendation score, so two rules matter:
//
//   1. The extract supplies an "On Time %" column (Column15). It is
//      DELIBERATELY NOT LOADED. Loading it invites someone to drop it into a
//      visual, where it gets averaged across rows and produces a number that is
//      wrong in a way nobody notices - averaging that column across the March
//      file returns about 98.2% against a true 96.46%, because a 4-package
//      service is weighted equally with a 47,916-package one. Only the counts
//      are loaded; the percentage is computed in DAX as a weighted ratio.
//
//   2. This extract is a SHIPPER VIEW population. Fact_VolumeSpend is a PAYOR
//      VIEW population. Packages Measured and Volume are close but not equal
//      (67,091 vs 68,527 for March) and must never be used as the same
//      denominator. ViewType carries the distinction onto the fact.
//
// Column offsets, verified against the real extract:
//   Column2  Sub-Parent Number   Column3  Sub-Parent Name
//   Column4  Account Number      Column5  Account Name
//   Column7  City   Column8  State   Column9  ZIP
//   Column10 Product             Column11 Packages Measured
//   Column12 Late by Time        Column13 Late by Day        Column14 Total Late
//
// When Time-in-Transit files arrive for other months, copy the Mar step, point
// it at that file, change the month number, and add it to Table.Combine.
// ===========================================================================

let
    Clean = (v) as text =>
        let
            t = if v = null then "" else Text.Trim(Text.From(v))
        in
            Text.Trim(if Text.StartsWith(t, "'") then Text.RemoveRange(t, 0, 1) else t),

    Num = (v) as number => if v = null then 0 else (try Number.From(v) otherwise 0),

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

    ReadTnT = (fileName as text, monthNo as number) as table =>
        let
            Sheet = Excel.Workbook(File.Contents(p_Folder & "\" & fileName), null, true)
                        {[Item = "TnT", Kind = "Sheet"]}[Data],
            Rows = Table.Skip(Sheet, 5),
            Pick = Table.SelectColumns(Rows, {
                "Column2", "Column3", "Column4", "Column5", "Column7", "Column8",
                "Column9", "Column10", "Column11", "Column12", "Column13", "Column14"}),
            Named = Table.RenameColumns(Pick, {
                {"Column2", "SubNumberRaw"}, {"Column3", "SubNameRaw"},
                {"Column4", "AccountNumberRaw"}, {"Column5", "AccountNameRaw"},
                {"Column7", "CityRaw"}, {"Column8", "StateRaw"}, {"Column9", "ZipRaw"},
                {"Column10", "ProductRaw"}, {"Column11", "MeasuredRaw"},
                {"Column12", "LateTimeRaw"}, {"Column13", "LateDayRaw"},
                {"Column14", "TotalLateRaw"}}),
            Kept = Table.SelectRows(Named, each
                KeepRow([SubNumberRaw], [AccountNumberRaw])
                and Clean([ProductRaw]) <> ""),
            Shaped = Table.AddColumn(Kept, "Rec", each
                let
                    LateTime = Num([LateTimeRaw]),
                    LateDay = Num([LateDayRaw]),
                    // Trust the components over the supplied total. Where the
                    // total is absent but the parts are present, rebuild it.
                    Total = if Num([TotalLateRaw]) = 0 and (LateTime + LateDay) > 0
                            then LateTime + LateDay
                            else Num([TotalLateRaw]),
                    Measured = Num([MeasuredRaw])
                in [
                    MonthNumber       = monthNo,
                    SubNumber         = Clean([SubNumberRaw]),
                    SubName           = SubNameOf([SubNumberRaw], [SubNameRaw]),
                    AccountNumber     = Clean([AccountNumberRaw]),
                    AccountName       = Clean([AccountNameRaw]),
                    City              = Clean([CityRaw]),
                    State             = Clean([StateRaw]),
                    ZIP               = Clean([ZipRaw]),
                    RawProduct        = Clean([ProductRaw]),
                    PackagesMeasured  = Measured,
                    LateByTime        = LateTime,
                    LateByDay         = LateDay,
                    TotalLate         = Total,
                    OnTimePackages    = Measured - Total,
                    ViewType          = "Shipper View"
                ]),
            Out = Table.FromRecords(Table.Column(Shaped, "Rec"))
        in
            Out,

    Mar = ReadTnT("UPS_2025_03_AllTabs.xlsx", 3),

    Combined = Table.Combine({Mar}),

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

    // Join on the TnT half of the bridge. This extract names services completely
    // differently from Volume & Net Spend ("NEXT DAY AIR" vs
    // "NDA REG / EXPRESS PKG"), which is exactly why the mapping table is keyed
    // on (SourceSystem, RawProduct) rather than being a simple lookup.
    Joined = Table.NestedJoin(WithMonthName, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "TnT"), {"RawProduct"},
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

    Typed = Table.TransformColumnTypes(Defaults, {
        {"MonthNumber", Int64.Type}, {"SubNumber", type text}, {"SubName", type text},
        {"AccountNumber", type text}, {"AccountName", type text},
        {"City", type text}, {"State", type text}, {"ZIP", type text},
        {"RawProduct", type text}, {"PackagesMeasured", type number},
        {"LateByTime", type number}, {"LateByDay", type number},
        {"TotalLate", type number}, {"OnTimePackages", type number}})
in
    Typed
