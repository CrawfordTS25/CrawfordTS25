// ===========================================================================
// DIMENSIONS
// Create each block below as its own query.
// ===========================================================================


// ---------------------------------------------------------------------------
// Dim_ServiceMapping
//
// A CONTROLLED table, loaded from etl/service_mapping.csv and version
// controlled alongside the report - not typed into a filter pane.
//
// It is a two-vocabulary BRIDGE, and that is the point. Volume & Net Spend
// calls a service "NDA REG / EXPRESS PKG"; Time-in-Transit calls the same
// service "NEXT DAY AIR". Without this table there is no way to put cost and
// reliability for the same service on the same row, and the entire
// recommendation is impossible. The SourceSystem column keeps the two
// vocabularies in one table without letting them collide.
//
// Because the grain is (SourceSystem, RawProduct), this table CANNOT be joined
// directly to the facts on RawProduct alone. The fact queries each join to a
// filtered copy (SourceSystem = "VnS" / "TnT"), and the model relationship runs
// from the ServiceGroup column of a de-duplicated service dimension. See
// model/relationships.md.
// ---------------------------------------------------------------------------
let
    Source = Csv.Document(
        File.Contents(p_MappingFilePath),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"SourceSystem", type text}, {"RawProduct", type text},
        {"ServiceGroup", type text}, {"ServiceGroupShort", type text},
        {"ServiceTier", type text}, {"Scope", type text},
        {"IncludeInRanking", type text}, {"ServicePriority", Int64.Type},
        {"Notes", type text}}),
    Trimmed = Table.TransformColumns(Typed, {
        {"RawProduct", Text.Trim, type text},
        {"ServiceGroup", Text.Trim, type text}})
in
    Trimmed


// ---------------------------------------------------------------------------
// Dim_Service
// The de-duplicated service dimension the model actually relates to. One row
// per Service Group; this is what slicers bind to and what the fact tables
// point at via their ServiceGroup column.
// ---------------------------------------------------------------------------
let
    Source = Dim_ServiceMapping,
    Rankable = Table.SelectColumns(Source, {
        "ServiceGroup", "ServiceGroupShort", "ServiceTier", "Scope",
        "IncludeInRanking", "ServicePriority"}),
    Distinct = Table.Distinct(Rankable, {"ServiceGroup"}),
    // Add the review buckets so an unmapped or excluded fact row still finds a
    // parent and does not become a blank-key orphan on every visual.
    WithReview = Table.Combine({
        Distinct,
        #table(
            type table [ServiceGroup = text, ServiceGroupShort = text, ServiceTier = text,
                        Scope = text, IncludeInRanking = text, ServicePriority = Int64.Type],
            {{"Unmapped - Review", "Unmapped", "Unmapped", "Unknown", "No", 98}})}),
    Deduped = Table.Distinct(WithReview, {"ServiceGroup"}),
    Sorted = Table.Sort(Deduped, {{"ServicePriority", Order.Ascending}})
in
    Sorted


// ---------------------------------------------------------------------------
// Dim_Date
//
// Generated for the full calendar year rather than derived from the data.
// A date table built from DISTINCT months present in the facts collapses the
// axis: if March is missing, a trend line joins February straight to April and
// the gap becomes invisible. A full-year table shows the hole.
//
// IsCompletedMonth  the month has ended as at p_AsOfDate
// IsLoaded          a fact table has rows for that month
// IsReportable      both of the above - the only flag that should gate a
//                   trend or annual comparison visual
// ---------------------------------------------------------------------------
let
    Year = p_ReportingYear,
    AsOf = p_AsOfDate,
    MonthList = List.Numbers(1, 12),

    LoadedMonths = List.Distinct(
        List.Combine({
            List.Transform(Table.Column(Fact_VolumeSpend, "MonthNumber"), each _),
            List.Transform(Table.Column(Fact_TimeInTransit, "MonthNumber"), each _),
            List.Transform(Table.Column(Fact_Claims, "MonthNumber"), each _)})),

    Rows = List.Transform(MonthList, each
        let
            First = #date(Year, _, 1),
            Last = Date.EndOfMonth(First),
            Completed = Last < AsOf,
            Loaded = List.Contains(LoadedMonths, _)
        in
            [ DateKey = First,
              Year = Year,
              MonthNumber = _,
              MonthName = Date.ToText(First, "MMM"),
              MonthNameLong = Date.ToText(First, "MMMM"),
              MonthKey = Year * 100 + _,
              MonthYearLabel = Date.ToText(First, "MMM yyyy"),
              Quarter = "Q" & Text.From(Number.RoundUp(_ / 3)),
              QuarterKey = Year * 10 + Number.RoundUp(_ / 3),
              MonthEndDate = Last,
              IsCompletedMonth = if Completed then "Yes" else "No",
              IsLoaded = if Loaded then "Yes" else "No",
              IsReportable = if Completed and Loaded then "Yes" else "No",
              SortOrder = Year * 100 + _ ]),

    Result = Table.FromRecords(Rows, type table [
        DateKey = date, Year = Int64.Type, MonthNumber = Int64.Type,
        MonthName = text, MonthNameLong = text, MonthKey = Int64.Type,
        MonthYearLabel = text, Quarter = text, QuarterKey = Int64.Type,
        MonthEndDate = date, IsCompletedMonth = text, IsLoaded = text,
        IsReportable = text, SortOrder = Int64.Type])
in
    Result
// After loading: mark as date table on [DateKey], and set the sort-by column
// of MonthName and MonthYearLabel to [SortOrder]. Without the sort-by column
// every month axis in the report renders alphabetically - Apr, Aug, Dec, Feb.


// ---------------------------------------------------------------------------
// Dim_Account
//
// Built from the UNION of all three fact tables, not from Volume & Net Spend
// alone. An account can appear in the claims extract in a month where it has no
// billed volume; sourcing the dimension from one fact would drop it and its
// claims would land on a blank row.
// ---------------------------------------------------------------------------
let
    FromVolume = Table.SelectColumns(Fact_VolumeSpend,
        {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName",
         "City", "State", "ZIP"}),
    FromTransit = Table.SelectColumns(Fact_TimeInTransit,
        {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName",
         "City", "State", "ZIP"}),
    FromClaims = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(
                Table.SelectColumns(Fact_Claims,
                    {"AccountKey", "SubNumber", "SubName", "AccountNumber", "AccountName"}),
                "City", each "", type text),
            "State", each "", type text),
        "ZIP", each "", type text),

    Combined = Table.Combine({FromVolume, FromTransit, FromClaims}),

    // Blank attributes must not win. Sorting non-blank State/City first means
    // the surviving distinct row carries the populated geography, which the
    // claims extract does not supply.
    Ranked = Table.Sort(Combined, {
        {"AccountKey", Order.Ascending},
        {each if [State] = null or [State] = "" then 1 else 0, Order.Ascending},
        {each if [City] = null or [City] = "" then 1 else 0, Order.Ascending}}),

    Distinct = Table.Distinct(Table.Buffer(Ranked), {"AccountKey"}),

    WithRegion = Table.AddColumn(Distinct, "Region", each
        let S = Text.Upper(_[State]) in
        if List.Contains({"CT","ME","MA","NH","RI","VT","NJ","NY","PA"}, S) then "Northeast"
        else if List.Contains({"IL","IN","MI","OH","WI","IA","KS","MN","MO","NE","ND","SD"}, S) then "Midwest"
        else if List.Contains({"DE","FL","GA","MD","NC","SC","VA","DC","WV","AL","KY","MS",
                               "TN","AR","LA","OK","TX"}, S) then "South"
        else if List.Contains({"AZ","CO","ID","MT","NV","NM","UT","WY","AK","CA","HI","OR","WA"}, S) then "West"
        else "Unknown / International", type text),

    WithDisplay = Table.AddColumn(WithRegion, "AccountDisplay",
        each [AccountName] & " (" & [AccountNumber] & ")", type text),

    Sorted = Table.Sort(WithDisplay, {{"SubName", Order.Ascending}, {"AccountName", Order.Ascending}})
in
    Sorted
