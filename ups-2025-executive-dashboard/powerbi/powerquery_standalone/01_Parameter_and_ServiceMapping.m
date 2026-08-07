// ===========================================================================
// 1. PARAMETER  p_Folder
// ===========================================================================
// This is a PARAMETER, not a query. Create it via:
//   Home > Transform data > Manage Parameters > New Parameter
//     Name:          p_Folder
//     Type:          Text
//     Current Value: X:\support_services\External_Provisioning\UPS\Reports Provided by UPS\2025\Volume Spend
// No trailing backslash. Paste the path exactly - no quotes around it.
//
// The queries do NOT hard-code file names. Each one asks the folder for the
// first .xlsx whose name begins with a month prefix - "1-JAN", "2-FEB",
// "3-MAR", "4-APR" - and is case-insensitive about it. That means UPS can keep
// renaming the files, and adding the rest of the year's files to the same
// folder changes nothing, until you wire those months in deliberately.
//
// If a month is missing the query stops with a named error
// (UPS.FileNotFound) that tells you which prefix it could not find and which
// folder it looked in, rather than failing somewhere deeper with a confusing
// column error.


// ===========================================================================
// 2. QUERY  Dim_ServiceMapping
// ===========================================================================
// Home > New Source > Blank Query, rename to Dim_ServiceMapping, then
// Home > Advanced Editor and paste everything below this banner.
//
// This is the two-vocabulary bridge and it is the reason the dashboard can put
// cost and reliability for the same service on one row.
//
// The Volume & Net Spend extract calls a service "NDA REG / EXPRESS PKG".
// The Time-in-Transit extract calls the same service "NEXT DAY AIR". Neither
// list contains the other's terms, so a single product column cannot join them.
// Keying on (SourceSystem, RawProduct) lets both vocabularies live in one table
// and resolve to one ServiceGroup.
//
// It is inlined as a literal table rather than read from a CSV so the model has
// no external dependency beyond your four Excel files. To change a mapping,
// edit the row here.
let
    Source = #table(
        type table [
            SourceSystem = text, RawProduct = text, ServiceGroup = text,
            ServiceGroupShort = text, ServiceTier = text, Scope = text,
            IncludeInRanking = text, ServicePriority = Int64.Type
        ],
    {
        {"VnS", "GROUND PKG",
         "Ground", "Ground", "Deferred", "Domestic", "Yes", 1},
        {"VnS", "GROUND CWT",
         "Ground", "Ground", "Deferred", "Domestic", "Yes", 1},
        {"VnS", "STANDARD GROUND",
         "Ground", "Ground", "Deferred", "Domestic", "Yes", 1},
        {"VnS", "3DS PKG",
         "3 Day Select", "3DS", "Deferred", "Domestic", "Yes", 2},
        {"VnS", "2DA REG / EXPEDITED PKG",
         "2nd Day Air / Expedited", "2DA", "Expedited", "Domestic", "Yes", 3},
        {"VnS", "2DA REG / EXPEDITED LTR",
         "2nd Day Air / Expedited", "2DA", "Expedited", "Domestic", "Yes", 3},
        {"VnS", "2DA REG / XPD LTR BILLED AS PKG",
         "2nd Day Air / Expedited", "2DA", "Expedited", "Domestic", "Yes", 3},
        {"VnS", "2DA AM PKG",
         "2nd Day Air Early A.M.", "2DA AM", "Expedited", "Domestic", "Yes", 4},
        {"VnS", "2DA AM LTR",
         "2nd Day Air Early A.M.", "2DA AM", "Expedited", "Domestic", "Yes", 4},
        {"VnS", "2DA AM LTR BILLED AS PKG",
         "2nd Day Air Early A.M.", "2DA AM", "Expedited", "Domestic", "Yes", 4},
        {"VnS", "NDA PM / EXPRESS SAVER PKG",
         "Next Day Air Saver", "NDA Saver", "Premium", "Domestic", "Yes", 5},
        {"VnS", "NDA PM / EXPRESS SAVER LTR",
         "Next Day Air Saver", "NDA Saver", "Premium", "Domestic", "Yes", 5},
        {"VnS", "NDA PM / XPR SVR LTR BLD AS PKG",
         "Next Day Air Saver", "NDA Saver", "Premium", "Domestic", "Yes", 5},
        {"VnS", "NDA REG / EXPRESS PKG",
         "Next Day Air / Express", "NDA", "Premium", "Domestic", "Yes", 6},
        {"VnS", "NDA REG / EXPRESS LTR",
         "Next Day Air / Express", "NDA", "Premium", "Domestic", "Yes", 6},
        {"VnS", "NDA REG / EXPRESS CWT",
         "Next Day Air / Express", "NDA", "Premium", "Domestic", "Yes", 6},
        {"VnS", "NDA REG / XPR LTR BILLED AS PKG",
         "Next Day Air / Express", "NDA", "Premium", "Domestic", "Yes", 6},
        {"VnS", "NDA AM / EXPRESS PLUS PKG",
         "Next Day Air Early", "NDA Early", "Premium", "Domestic", "Yes", 7},
        {"VnS", "NDA AM / EXPRESS PLUS LTR",
         "Next Day Air Early", "NDA Early", "Premium", "Domestic", "Yes", 7},
        {"VnS", "WW EXPRESS REG PKG",
         "International Express", "Intl Express", "Premium", "International", "Yes", 8},
        {"VnS", "WW EXPRESS REG LTR",
         "International Express", "Intl Express", "Premium", "International", "Yes", 8},
        {"VnS", "WW EXPRESS REG DOC",
         "International Express", "Intl Express", "Premium", "International", "Yes", 8},
        {"VnS", "WW EXPRESS REG PAK",
         "International Express", "Intl Express", "Premium", "International", "Yes", 8},
        {"VnS", "WW EXPRESS PM / SAVER PKG",
         "International Express Saver", "Intl Saver", "Premium", "International", "Yes", 9},
        {"VnS", "WW EXPRESS PM / SAVER LTR",
         "International Express Saver", "Intl Saver", "Premium", "International", "Yes", 9},
        {"VnS", "WW EXPRESS PM / SAVER DOC",
         "International Express Saver", "Intl Saver", "Premium", "International", "Yes", 9},
        {"VnS", "WW EXPRESS PM / SVR LTR BLD AS DOC",
         "International Express Saver", "Intl Saver", "Premium", "International", "Yes", 9},
        {"VnS", "WW EXPEDITED / 2DA PKG",
         "International Expedited", "Intl Expedited", "Expedited", "International", "Yes", 10},
        {"VnS", "WW EXPEDITED / 2DA LTR",
         "International Expedited", "Intl Expedited", "Expedited", "International", "Yes", 10},
        {"VnS", "WW 3DS PKG",
         "International Standard", "Intl Standard", "Deferred", "International", "Yes", 11},
        {"VnS", "MISC / UNC",
         "Excluded - Adjustments", "Excluded", "Non-Service", "Not Applicable", "No", 99},
        {"TnT", "GROUND",
         "Ground", "Ground", "Deferred", "Domestic", "Yes", 1},
        {"TnT", "THREE DAY SELECT",
         "3 Day Select", "3DS", "Deferred", "Domestic", "Yes", 2},
        {"TnT", "SECOND DAY AIR",
         "2nd Day Air / Expedited", "2DA", "Expedited", "Domestic", "Yes", 3},
        {"TnT", "SECOND DAY EARLY AM",
         "2nd Day Air Early A.M.", "2DA AM", "Expedited", "Domestic", "Yes", 4},
        {"TnT", "NEXT DAY AIR SAVER",
         "Next Day Air Saver", "NDA Saver", "Premium", "Domestic", "Yes", 5},
        {"TnT", "NEXT DAY AIR",
         "Next Day Air / Express", "NDA", "Premium", "Domestic", "Yes", 6},
        {"TnT", "UPS EXPRESS EARLY",
         "Next Day Air Early", "NDA Early", "Premium", "Domestic", "Yes", 7},
        {"TnT", "INTERNATIONAL EXPRESS",
         "International Express", "Intl Express", "Premium", "International", "Yes", 8},
        {"TnT", "INTERNATIONAL EXPRESS SAVER",
         "International Express Saver", "Intl Saver", "Premium", "International", "Yes", 9},
        {"TnT", "INTERNATIONAL EXPEDITED",
         "International Expedited", "Intl Expedited", "Expedited", "International", "Yes", 10},
        {"TnT", "INTERNATIONAL STANDARD",
         "International Standard", "Intl Standard", "Deferred", "International", "Yes", 11}
    })
in
    Source
