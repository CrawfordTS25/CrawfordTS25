// ===========================================================================
// 7. QUERY  Dim_Date
// ===========================================================================
// New Source > Blank Query > rename to Dim_Date > Advanced Editor.
//
// Generated for the full calendar year rather than derived from the data. A date
// table built from the months actually present collapses the axis: if a month is
// missing, a trend line joins the months either side of it and the gap becomes
// invisible. A full-year table shows the hole.
//
// IMPORTANT - do NOT mark this as a date table.
// It is MONTH grain: twelve rows, one per month, because every fact in this
// model is month grain. DAX time-intelligence functions (TOTALYTD,
// SAMEPERIODLASTYEAR, DATEADD) require a contiguous table of DAYS and will
// return blank or silently wrong values against twelve first-of-month rows. The
// measures in this build use MonthKey arithmetic instead, which is exact here.
//
// After loading: set the Sort by Column of MonthName and MonthYearLabel to
// SortOrder. Without that, every month axis renders alphabetically -
// Apr, Aug, Dec, Feb.
// ===========================================================================

let
    ReportYear = 2025,
    // Months present in the data. Update as later months are added, or set to
    // {1..12} once the full year is loaded.
    LoadedMonths = {1, 2, 3, 4},
    // Anchors the completed-month flag. Change to a fixed date to reproduce a
    // previously published figure.
    AsOf = DateTime.Date(DateTime.LocalNow()),

    Rows = List.Transform({1 .. 12}, (m) =>
        let
            First = #date(ReportYear, m, 1),
            Last = Date.EndOfMonth(First),
            Completed = Last < AsOf,
            Loaded = List.Contains(LoadedMonths, m)
        in [
            DateKey          = First,
            Year             = ReportYear,
            MonthNumber      = m,
            MonthName        = Date.ToText(First, "MMM"),
            MonthNameLong    = Date.ToText(First, "MMMM"),
            MonthKey         = ReportYear * 100 + m,
            MonthYearLabel   = Date.ToText(First, "MMM yyyy"),
            Quarter          = "Q" & Text.From(Number.RoundUp(m / 3)),
            QuarterKey       = ReportYear * 10 + Number.RoundUp(m / 3),
            MonthEndDate     = Last,
            IsCompletedMonth = if Completed then "Yes" else "No",
            IsLoaded         = if Loaded then "Yes" else "No",
            // The only flag that should gate a trend or annual comparison: the
            // month has both ended and actually been loaded.
            IsReportable     = if Completed and Loaded then "Yes" else "No",
            SortOrder        = ReportYear * 100 + m
        ]),

    Result = Table.FromRecords(Rows, type table [
        DateKey = date, Year = Int64.Type, MonthNumber = Int64.Type,
        MonthName = text, MonthNameLong = text, MonthKey = Int64.Type,
        MonthYearLabel = text, Quarter = text, QuarterKey = Int64.Type,
        MonthEndDate = date, IsCompletedMonth = text, IsLoaded = text,
        IsReportable = text, SortOrder = Int64.Type])
in
    Result


// ===========================================================================
// 8. QUERY  Dim_Account
// ===========================================================================
// New Source > Blank Query > rename to Dim_Account > Advanced Editor.
//
// Built from the UNION of all three facts, not from Volume & Spend alone. An
// account can appear in the claims extract in a month where it has no billed
// volume; sourcing the dimension from one fact would drop it and its claims
// would land on a blank row.
// ===========================================================================

let
    FromVolume = Table.SelectColumns(Fact_VolumeSpend,
        {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName",
         "City", "State", "ZIP"}),
    FromTransit = Table.SelectColumns(Fact_TimeInTransit,
        {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName",
         "City", "State", "ZIP"}),
    // The claims extract carries no geography; pad so the columns align.
    FromClaims = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(
                Table.SelectColumns(Fact_Claims,
                    {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName"}),
                "City", each "", type text),
            "State", each "", type text),
        "ZIP", each "", type text),

    Combined = Table.Combine({FromVolume, FromTransit, FromClaims}),

    // Blank attributes must not win the deduplication. Sorting non-blank State
    // and City first means the surviving row carries the populated geography,
    // which the claims rows do not supply.
    Ranked = Table.Sort(Combined, {
        {"AccountKey", Order.Ascending},
        {each if [State] = null or [State] = "" then 1 else 0, Order.Ascending},
        {each if [City] = null or [City] = "" then 1 else 0, Order.Ascending}}),

    // Table.Buffer is required: without it the sort is not guaranteed to be
    // honoured by Table.Distinct and the wrong row can win.
    Distinct = Table.Distinct(Table.Buffer(Ranked), {"AccountKey"}),

    WithRegion = Table.AddColumn(Distinct, "Region", each
        let S = Text.Upper(if [State] = null then "" else [State]) in
        if List.Contains({"CT","ME","MA","NH","RI","VT","NJ","NY","PA"}, S) then "Northeast"
        else if List.Contains({"IL","IN","MI","OH","WI","IA","KS","MN","MO",
                               "NE","ND","SD"}, S) then "Midwest"
        else if List.Contains({"DE","FL","GA","MD","NC","SC","VA","DC","WV","AL","KY","MS",
                               "TN","AR","LA","OK","TX"}, S) then "South"
        else if List.Contains({"AZ","CO","ID","MT","NV","NM","UT","WY","AK",
                               "CA","HI","OR","WA"}, S) then "West"
        else "Unknown / International", type text),

    // Coverage flags. Built from buffered key lists rather than a nested
    // Table.SelectRows per row: the nested form re-scans the whole fact table
    // for every account, and inside the inner lambda [AccountKey] is ambiguous
    // between the outer and inner row.
    TransitKeys = List.Buffer(List.Distinct(Table.Column(Fact_TimeInTransit, "AccountKey"))),
    ClaimsKeys  = List.Buffer(List.Distinct(Table.Column(Fact_Claims, "AccountKey"))),

    WithFlags = Table.AddColumn(
        Table.AddColumn(WithRegion, "HasTransitData",
            each if List.Contains(TransitKeys, [AccountKey]) then "Yes" else "No", type text),
        "HasClaimsData",
            each if List.Contains(ClaimsKeys, [AccountKey]) then "Yes" else "No", type text),

    WithDisplay = Table.AddColumn(WithFlags, "AccountDisplay",
        each [AccountName] & " (" & [AccountNumber] & ")", type text),

    Sorted = Table.Sort(WithDisplay,
        {{"SubName", Order.Ascending}, {"AccountName", Order.Ascending}})
in
    Sorted


// ===========================================================================
// 9. QUERY  Dim_Service
// ===========================================================================
// New Source > Blank Query > rename to Dim_Service > Advanced Editor.
//
// The de-duplicated service dimension the MODEL relates to. Dim_ServiceMapping
// has grain (SourceSystem, RawProduct) - 42 rows across two vocabularies - so
// RawProduct is not unique and it cannot be the one side of a relationship.
// This table has one row per Service Group and is what slicers bind to.
//
// After loading, hide Dim_ServiceMapping from the report view. It is needed for
// the Data Quality page's mapping inventory but must never appear in a slicer,
// and no measure may filter it - REMOVEFILTERS on a table with no relationship
// to the facts is a no-op that returns silently wrong numbers.
// ===========================================================================

let
    Source = Dim_ServiceMapping,
    Trimmed = Table.SelectColumns(Source, {
        "ServiceGroup", "ServiceGroupShort", "ServiceTier", "Scope",
        "IncludeInRanking", "ServicePriority"}),
    Distinct = Table.Distinct(Trimmed, {"ServiceGroup"}),
    // A review bucket so an unmapped fact row finds a parent instead of becoming
    // a blank-key orphan on every visual.
    WithReview = Table.Combine({Distinct, #table(
        type table [ServiceGroup = text, ServiceGroupShort = text,
                    ServiceTier = text,
                    Scope = text, IncludeInRanking = text, ServicePriority = Int64.Type],
        {{"Unmapped - Review", "Unmapped", "Unmapped", "Unknown", "No", 98}})}),
    Deduped = Table.Distinct(WithReview, {"ServiceGroup"}),
    Sorted = Table.Sort(Deduped, {{"ServicePriority", Order.Ascending}})
in
    Sorted
