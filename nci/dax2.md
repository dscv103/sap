No problem — everything moves to Power Query. Here’s the full M code to replace the SQL view.

Power Query: Full Transformation
Open Power Query, select your stage table, then go to Advanced Editor and replace the contents with this — keeping your existing Source step name:

let
    // — 1. Load raw table (keep your existing source step) —
    Source = Sql.Database(“your_server”, “your_database”, 
                [Query = “SELECT * FROM dbo.StageDurations”]),

    // — 2. Sort so visit numbering is deterministic —
    Sorted = Table.Sort(Source, {
        {“app_id”,     Order.Ascending},
        {“stage_name”, Order.Ascending},
        {“exit_flag”,  Order.Ascending},
        {“event_date”, Order.Ascending}
    }),

    // — 3. Add visit number per app + stage + exit_flag group —
    //    Table.Group preserves all columns via the inner AddIndexColumn
    Grouped = Table.Group(
        Sorted,
        {“app_id”, “stage_name”, “exit_flag”},
        {{“grp”, each Table.AddIndexColumn(_, “visit_number”, 1, 1), type table}}
    ),

    Expanded = Table.ExpandTableColumn(
        Grouped, “grp”,
        {“event_date”, “visit_number”},
        {“event_date”, “visit_number”}
    ),

    // — 4. Split into entry and exit tables —
    Entries = Table.SelectRows(Expanded, each [exit_flag] = 0),
    EntryRenamed = Table.RenameColumns(Entries, {{“event_date”, “stage_enter_date”}}),
    EntryFinal = Table.SelectColumns(EntryRenamed, 
                    {“app_id”, “stage_name”, “visit_number”, “stage_enter_date”}),

    Exits = Table.SelectRows(Expanded, each [exit_flag] = 1),
    ExitRenamed = Table.RenameColumns(Exits, {{“event_date”, “stage_exit_date”}}),
    ExitFinal = Table.SelectColumns(ExitRenamed, 
                    {“app_id”, “stage_name”, “visit_number”, “stage_exit_date”}),

    // — 5. Left join entries to exits on app + stage + visit —
    //    Left join preserves in-flight rows (no exit yet)
    Merged = Table.NestedJoin(
        EntryFinal, {“app_id”, “stage_name”, “visit_number”},
        ExitFinal,  {“app_id”, “stage_name”, “visit_number”},
        “ExitData”, JoinKind.LeftOuter
    ),

    Unpacked = Table.ExpandTableColumn(
        Merged, “ExitData”, {“stage_exit_date”}, {“stage_exit_date”}
    ),

    // — 6. Add helper columns for YTD gating (avoids DAX complexity) —
    AddYear = Table.AddColumn(
        Unpacked, “entry_year”,
        each Date.Year([stage_enter_date]),
        Int64.Type
    ),

    AddDOY = Table.AddColumn(
        AddYear, “day_of_year”,
        each Duration.Days([stage_enter_date] - #date(Date.Year([stage_enter_date]), 1, 1)) + 1,
        Int64.Type
    ),

    // — 7. Set final column types —
    TypeSet = Table.TransformColumnTypes(AddDOY, {
        {“stage_enter_date”, type date},
        {“stage_exit_date”,  type date},
        {“entry_year”,       Int64.Type},
        {“day_of_year”,      Int64.Type},
        {“visit_number”,     Int64.Type}
    })

in
    TypeSet


What Each Step Produces



|Step                  |Output                                                          |
|-———————|-—————————————————————|
|Sorted                |Raw events in deterministic order                               |
|Grouped + Expanded    |Visit number 1, 2, 3… per app + stage + entry/exit independently|
|EntryFinal / ExitFinal|Two clean tables, one per event type                            |
|Merged + Unpacked     |**One row per visit** with both dates side by side              |
|AddYear / AddDOY      |Helper columns so DAX YTD measures stay simple                  |
|TypeSet               |Correct types so DAX date functions work without casting        |

One Thing to Watch
The Table.Group + Table.AddIndexColumn pattern can be slow on large tables because Power Query evaluates it row by row in some engine modes. If refresh is slow:
	∙	Add a Table.Buffer(Sorted) call before the Table.Group step — this forces evaluation before grouping and usually speeds it up significantly:

Buffered = Table.Buffer(Sorted),
Grouped  = Table.Group(Buffered, ...


After This — DAX and Relationships Unchanged
The rest of the approach from the previous response applies as-is:
	∙	Business Days calculated column using DateTable[IsBusinessDay]
	∙	Avg Stage Days, Avg Days 2024, Avg Days 2025, YoY Index measures
	∙	Relate DateTable[Date] → StageDurations[stage_enter_date] only

Two quick checks once loaded:
	1.	Row count sanity — the output row count should equal the number of entry rows in your raw table (exits without a matching entry won’t appear, which is correct)
	2.	Re-entry check — filter to a known re-entry app_id and confirm you see visit_number = 1 and visit_number = 2 rows for that stage
What are your actual column names in the stage table? The code above uses app_id, stage_name, event_date, exit_flag — swap those out if yours differ.​​​​​​​​​​​​​​​​