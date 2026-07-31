// ===========================================================================
// PARAMETERS
// Create each of these in Power Query as a named parameter (Manage Parameters),
// not as a query. Every other query references them, so the model relocates to
// SharePoint, a network share, or a new year by editing these alone.
// ===========================================================================

// --- p_SourceFolder --------------------------------------------------------
// Type: Text. Suggested value: C:\UPS\2025\Source
// The folder containing the monthly UPS extracts. Use a SharePoint or OneDrive
// synced path if the report is to refresh in the Power BI Service via a
// gateway; a local C:\ path will refresh on the desktop but fail in the cloud.
"C:\UPS\2025\Source" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// --- p_ReportingYear -------------------------------------------------------
// Type: Whole Number. Suggested value: 2025
// Drives Dim_Date generation and the year filter applied on load.

// --- p_AsOfDate ------------------------------------------------------------
// Type: Date. Suggested value: DateTime.Date(DateTime.LocalNow())
// Anchors the Completed Month Flag. Parameterised rather than hard-coded to
// DateTime.LocalNow() so a refresh can be replayed for an historic as-of date
// when reproducing a published figure.

// --- p_MinimumShipmentThreshold -------------------------------------------
// Type: Whole Number. Suggested value: 1000
// Mirrors the DAX What-If default so a fresh model opens with the documented
// governance setting already in force.
