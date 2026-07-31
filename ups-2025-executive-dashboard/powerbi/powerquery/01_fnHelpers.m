// ===========================================================================
// SHARED HELPER FUNCTIONS
// Create each of these as its own blank query, named exactly as shown.
// They encapsulate the parsing rules that the fact queries all depend on, so
// a change to how UPS labels a period is fixed in one place.
// ===========================================================================


// ---------------------------------------------------------------------------
// fnCleanText
// UPS prefixes ID-like columns with an apostrophe to stop Excel reformatting
// them. Left in place, "'2W2107" and "2W2107" are different keys and the
// account relationship silently half-fails.
// ---------------------------------------------------------------------------
let
    fnCleanText = (input as any) as text =>
        let
            AsText = if input = null then "" else Text.From(input),
            Trimmed = Text.Trim(AsText),
            Unquoted = if Text.StartsWith(Trimmed, "'") then Text.RemoveRange(Trimmed, 0, 1) else Trimmed
        in
            Text.Trim(Unquoted)
in
    fnCleanText


// ---------------------------------------------------------------------------
// fnParsePeriod
// The Schema B (VnS / TnT / Claims / Accessorial) extracts state their period
// only in the title block: "March 2025 - Shipper View", "April, 2025 - Payor
// View". Returns [Year, Month] from that text.
// ---------------------------------------------------------------------------
let
    fnParsePeriod = (titleText as nullable text, optional fallbackYear as nullable number) as record =>
        let
            Source = if titleText = null then "" else Text.Lower(titleText),
            MonthNames = {"january","february","march","april","may","june",
                          "july","august","september","october","november","december"},
            // Take the LAST month named. "January - February, 2025" is a
            // year-to-date file whose reporting period ends in February.
            Found = List.Select(MonthNames, each Text.Contains(Source, _)),
            LastMonth = if List.IsEmpty(Found) then null
                        else List.Last(List.Sort(Found, (a, b) =>
                            Value.Compare(Text.PositionOf(Source, a), Text.PositionOf(Source, b)))),
            MonthNumber = if LastMonth = null then null else List.PositionOf(MonthNames, LastMonth) + 1,
            Digits = Text.Select(Source, {"0".."9"}),
            YearMatch = List.Select(
                List.Transform({0..Text.Length(Source) - 4}, each try Number.FromText(Text.Middle(Source, _, 4)) otherwise null),
                each _ <> null and _ >= 2000 and _ <= 2100),
            Year = if List.IsEmpty(YearMatch) then fallbackYear else List.First(YearMatch)
        in
            [Year = Year, Month = MonthNumber]
in
    fnParsePeriod


// ---------------------------------------------------------------------------
// fnViewType
// "Shipper View" and "Payor View" are different shipment populations. Carrying
// the label onto the fact stops anyone from reconciling a shipper-view package
// count against a payor-view volume count and concluding the data is broken.
// ---------------------------------------------------------------------------
let
    fnViewType = (titleText as nullable text) as text =>
        let
            Source = if titleText = null then "" else Text.Lower(titleText)
        in
            if Text.Contains(Source, "shipper") then "Shipper View"
            else if Text.Contains(Source, "payor") or Text.Contains(Source, "payer") then "Payor View"
            else "Unspecified"
in
    fnViewType


// ---------------------------------------------------------------------------
// fnIsSentinel
// Drops report artefacts only. Deliberately NOT keyed on the sub-parent alone:
// UPS masks the sub-parent on some accounts with "@@", and those rows carry a
// real account number and real shipment volume. Filtering on "@@" - the
// obvious thing to do - silently deletes genuine international activity.
// ---------------------------------------------------------------------------
let
    fnIsSentinel = (subNumber as any, accountNumber as any) as logical =>
        let
            Sub = Text.Lower(fnCleanText(subNumber)),
            Account = Text.Lower(fnCleanText(accountNumber)),
            IsTotal = List.Contains({"grand total", "total"}, Sub)
                   or List.Contains({"grand total", "total"}, Account),
            IsEmpty = (Account = "" or Account = "none") and (Sub = "" or Sub = "none")
        in
            IsTotal or IsEmpty
in
    fnIsSentinel


// ---------------------------------------------------------------------------
// fnSubParentLabel
// Normalises the masked sub-parent into a visible, auditable label so it can be
// reported on rather than mistaken for missing data.
// ---------------------------------------------------------------------------
let
    fnSubParentLabel = (subNumber as any, subName as any) as record =>
        let
            Number = fnCleanText(subNumber),
            Name = fnCleanText(subName),
            IsMasked = (Number = "@@" or Name = "@@")
        in
            [ SubNumber = Number,
              SubName = if IsMasked then "Unassigned Sub-Parent" else Name,
              IsMaskedSubParent = if IsMasked then "Yes" else "No" ]
in
    fnSubParentLabel


// ---------------------------------------------------------------------------
// fnPromoteUpsHeader
// The extracts carry a 3-4 row title block above the real header. Rather than
// removing a fixed number of rows - which breaks the moment UPS adds a line -
// this finds the header row by looking for a known anchor column and promotes
// from there.
// ---------------------------------------------------------------------------
let
    fnPromoteUpsHeader = (source as table, anchorColumn as text) as table =>
        let
            Indexed = Table.AddIndexColumn(source, "RowIndex", 0, 1),
            HeaderRow = Table.SelectRows(
                Indexed,
                each List.Contains(
                    List.Transform(Record.FieldValues(Record.RemoveFields(_, {"RowIndex"})),
                        each fnCleanText(_)),
                    anchorColumn)),
            HeaderIndex = if Table.IsEmpty(HeaderRow) then
                    error Error.Record(
                        "UPS.HeaderNotFound",
                        "Could not locate the header row.",
                        "Expected a cell containing '" & anchorColumn & "'. "
                            & "The extract layout has changed - check the source file before refreshing.")
                else Table.FirstValue(Table.FirstN(Table.SelectColumns(HeaderRow, {"RowIndex"}), 1)),
            Skipped = Table.Skip(source, HeaderIndex),
            Promoted = Table.PromoteHeaders(Skipped, [PromoteAllScalars = true])
        in
            Promoted
in
    fnPromoteUpsHeader
