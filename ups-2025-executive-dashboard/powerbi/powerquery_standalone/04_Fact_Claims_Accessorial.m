// ===========================================================================
// 5. QUERY  Fact_Claims
// ===========================================================================
// New Source > Blank Query > rename to Fact_Claims > Advanced Editor.
//
// NOTE THE MISSING COLUMN. This extract carries Sub-Parent, Account and Claims
// Category - and no product, service, or tracking number. There is therefore no
// join path from this table to the service dimension, and no way to state a
// loss claim rate "by service" from this source.
//
// The recommendation framework assigns 30% of its weight to Loss Claim Rate and
// 20% to exceptions. Neither can be allocated at service grain until UPS adds a
// service or tracking field to this export.
//
// Do NOT create a relationship from this table to Dim_Service - not a
// many-to-many through Dim_Account, not a bi-directional filter. Filtering
// claims by service through the account path returns "claims for accounts that
// used this service" - for an account using five services, the same claim count
// five times over - and any reader will take it as claims caused by that
// service. The model leaves the join absent so a service slicer visibly does
// nothing on the claims page. A blank is a correct answer to an unanswerable
// question; a plausible wrong number is not.
//
// Column offsets, verified against the real extract:
//   Column2  Sub-Parent Number    Column3  Sub-Parent Name
//   Column4  Account Number       Column5  Account Name
//   Column6  Claims Category
//   Column7  Issued Claims Qty    Column8  Issued Claims Pkg Qty
//   Column10 Paid Claims Qty      Column11 Paid Claims Pkg Qty
//   Column13 Registered Qty       Column14 Registered Pkg Qty
//   Column16 Paid Claims Amount   Column17 Claims Declared Value
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

    // Files are located by MONTH PREFIX ("3-MAR"), not by exact name: the
    // delivered names vary in separators, spacing and request number, and two
    // files share one request number. The prefix is the stable part.
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

    NamedSheet = (prefix as text, sheet as text) as table =>
        Excel.Workbook(PickWorkbook(prefix), null, true)
            {[Item = sheet, Kind = "Sheet"]}[Data],

    ReadClaims = (prefix as text, monthNo as number) as table =>
        let
            Sheet = NamedSheet(prefix, "Claims"),
            Rows = Table.Skip(Sheet, 5),
            Pick = Table.SelectColumns(Rows, {
                "Column2", "Column3", "Column4", "Column5", "Column6", "Column7",
                "Column8", "Column10", "Column11", "Column13", "Column14",
                "Column16", "Column17"}),
            Named = Table.RenameColumns(Pick, {
                {"Column2", "SubNumberRaw"}, {"Column3", "SubNameRaw"},
                {"Column4", "AccountNumberRaw"}, {"Column5", "AccountNameRaw"},
                {"Column6", "CategoryRaw"}, {"Column7", "IssuedQtyRaw"},
                {"Column8", "IssuedPkgRaw"}, {"Column10", "PaidQtyRaw"},
                {"Column11", "PaidPkgRaw"}, {"Column13", "RegQtyRaw"},
                {"Column14", "RegPkgRaw"}, {"Column16", "PaidAmtRaw"},
                {"Column17", "DeclaredRaw"}}),
            // Blank category rows are report padding, not claim activity.
            Kept = Table.SelectRows(Named, each
                KeepRow([SubNumberRaw], [AccountNumberRaw])
                and Clean([CategoryRaw]) <> ""),
            Shaped = Table.AddColumn(Kept, "Rec", each [
                MonthNumber            = monthNo,
                SubNumber              = Clean([SubNumberRaw]),
                SubName                = SubNameOf([SubNumberRaw], [SubNameRaw]),
                AccountNumber          = Clean([AccountNumberRaw]),
                AccountName            = Clean([AccountNameRaw]),
                ClaimsCategory         = Clean([CategoryRaw]),
                IsLoss                 = if Text.Lower(Clean([CategoryRaw])) = "loss"
                                         then "Yes" else "No",
                IssuedClaimsQty        = Num([IssuedQtyRaw]),
                IssuedClaimsPkgQty     = Num([IssuedPkgRaw]),
                PaidClaimsQty          = Num([PaidQtyRaw]),
                PaidClaimsPkgQty       = Num([PaidPkgRaw]),
                RegisteredClaimsQty    = Num([RegQtyRaw]),
                RegisteredClaimsPkgQty = Num([RegPkgRaw]),
                PaidClaimsAmount       = Num([PaidAmtRaw]),
                ClaimsDeclaredValue    = Num([DeclaredRaw]),
                // Stamped on every row so the limitation travels with the data
                // into any export, drillthrough or copied visual.
                ServiceAttribution     = "Not Available"
            ]),
            Out = Table.FromRecords(Table.Column(Shaped, "Rec"))
        in
            Out,

    Mar = ReadClaims("3-MAR", 3),
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

    Typed = Table.TransformColumnTypes(WithMonthName, {
        {"MonthNumber", Int64.Type}, {"SubNumber", type text}, {"SubName", type text},
        {"AccountNumber", type text}, {"AccountName", type text},
        {"ClaimsCategory", type text}, {"IsLoss", type text},
        {"IssuedClaimsQty", type number}, {"IssuedClaimsPkgQty", type number},
        {"PaidClaimsQty", type number}, {"PaidClaimsPkgQty", type number},
        {"RegisteredClaimsQty", type number}, {"RegisteredClaimsPkgQty", type number},
        {"PaidClaimsAmount", Currency.Type}, {"ClaimsDeclaredValue", Currency.Type}})
in
    Typed


// ===========================================================================
// 6. QUERY  Fact_Accessorial
// ===========================================================================
// New Source > Blank Query > rename to Fact_Accessorial > Advanced Editor >
// paste everything below this banner (NOT the Fact_Claims query above).
//
// Not in the original build guide's data model. Added because it is the only
// table that explains WHY cost per piece moves. Net spend on its own says costs
// rose; this says the rise was fuel surcharge, address corrections or
// residential delivery - the difference between a carrier conversation and an
// internal process fix.
//
// Address Correction in particular is a pure self-inflicted cost: every unit is
// a package that shipped to a bad address the firm supplied. It is charged per
// package, it is fully avoidable through address validation at the point of
// shipment, and it appears nowhere in the Volume & Net Spend extract.
//
// Reconciliation guarantee: for a given month this table's NetSpend must sum to
// exactly the same value as Fact_VolumeSpend's NetSpend. For March both are
// $1,053,748.13. That equality is a free, strong integrity check and is wired to
// the [Reconciliation Status] measure on the Data Quality page.
//
// Column offsets:
//   Column2  Sub-Parent Number   Column3  Sub-Parent Name
//   Column4  Account Number      Column5  Account Name
//   Column8  State               Column10 Product
//   Column11 Freight Type Description     Column12 Base or Accessorial Charge
//   Column13 Number of Units     Column14 Accessorial Spend
//   Column15 Gross Spend         Column16 Net Spend
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

    // Files are located by MONTH PREFIX ("3-MAR"), not by exact name: the
    // delivered names vary in separators, spacing and request number, and two
    // files share one request number. The prefix is the stable part.
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

    NamedSheet = (prefix as text, sheet as text) as table =>
        Excel.Workbook(PickWorkbook(prefix), null, true)
            {[Item = sheet, Kind = "Sheet"]}[Data],

    ReadAcc = (prefix as text, monthNo as number) as table =>
        let
            Sheet = NamedSheet(prefix, "Accessorial"),
            Rows = Table.Skip(Sheet, 5),
            Pick = Table.SelectColumns(Rows, {
                "Column2", "Column3", "Column4", "Column5", "Column8", "Column10",
                "Column11", "Column12", "Column13", "Column14", "Column15", "Column16"}),
            Named = Table.RenameColumns(Pick, {
                {"Column2", "SubNumberRaw"}, {"Column3", "SubNameRaw"},
                {"Column4", "AccountNumberRaw"}, {"Column5", "AccountNameRaw"},
                {"Column8", "StateRaw"}, {"Column10", "ProductRaw"},
                {"Column11", "FreightTypeRaw"}, {"Column12", "ChargeRaw"},
                {"Column13", "UnitsRaw"}, {"Column14", "AccSpendRaw"},
                {"Column15", "GrossRaw"}, {"Column16", "NetRaw"}}),
            Kept = Table.SelectRows(Named, each
                KeepRow([SubNumberRaw], [AccountNumberRaw])
                and Clean([ChargeRaw]) <> ""),
            Shaped = Table.AddColumn(Kept, "Rec", each [
                MonthNumber            = monthNo,
                SubNumber              = Clean([SubNumberRaw]),
                SubName                = SubNameOf([SubNumberRaw], [SubNameRaw]),
                AccountNumber          = Clean([AccountNumberRaw]),
                AccountName            = Clean([AccountNameRaw]),
                State                  = Clean([StateRaw]),
                RawProduct             = Clean([ProductRaw]),
                FreightTypeDescription = Clean([FreightTypeRaw]),
                ChargeCategory         = Clean([ChargeRaw]),
                IsAccessorial          = if Text.Upper(Clean([FreightTypeRaw])) = "ACCESSORIAL"
                                         then "Yes" else "No",
                NumberOfUnits          = Num([UnitsRaw]),
                AccessorialSpend       = Num([AccSpendRaw]),
                GrossSpend             = Num([GrossRaw]),
                NetSpend               = Num([NetRaw])
            ]),
            Out = Table.FromRecords(Table.Column(Shaped, "Rec"))
        in
            Out,

    Mar = ReadAcc("3-MAR", 3),
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

    Joined = Table.NestedJoin(WithMonthName, {"RawProduct"},
        Table.SelectRows(Dim_ServiceMapping, each [SourceSystem] = "VnS"), {"RawProduct"},
        "Map", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "Map",
        {"ServiceGroup", "ServiceGroupShort"}),
    Defaults = Table.TransformColumns(Expanded, {
        {"ServiceGroup", each if _ = null then "Unmapped - Review" else _, type text},
        {"ServiceGroupShort", each if _ = null then "Unmapped" else _, type text}}),

    Typed = Table.TransformColumnTypes(Defaults, {
        {"MonthNumber", Int64.Type}, {"NumberOfUnits", type number},
        {"AccessorialSpend", Currency.Type}, {"GrossSpend", Currency.Type},
        {"NetSpend", Currency.Type}})
in
    Typed
