This is actually a much cleaner foundation than a wide table. The event-log structure with entry/exit rows handles re-entries naturally. Let me recalibrate the full approach for this model.

What Your Model Likely Looks Like
Loan Table (one row per application)



|app_id|loan_type|officer|region|open_date|…|
|——|———|-——|——|———|-|

Stage Duration Table (one row per event)



|app_id|stage_name  |event_type|event_date|
|——|————|-———|-———|
|A001  |Underwriting|Entry     |2024-03-01|
|A001  |Underwriting|Exit      |2024-03-08|
|A001  |Underwriting|Entry     |2024-03-15|
|A001  |Underwriting|Exit      |2024-03-22|

Is this roughly right? The specific column names matter — confirm before building anything.

The Core Transformation Problem
You need to go from one row per event → one row per visit with enter and exit side by side, so you can calculate duration per visit. This happens in Power Query.
Step 1 — Assign Visit Numbers
Without a visit number, you can’t reliably pair entry rows to their matching exit. You need to rank events within each app_id + stage_name group by date:

// Sort by app_id, stage_name, event_date ascending first in Power Query UI
// Then add an index column — but this gives a global index, not per-group

// Instead, add a custom column:
VisitNumber = 
    let
        priorEntries = Table.SelectRows(
            StageDurationTable,
            each [app_id] = [app_id] 
              and [stage_name] = [stage_name] 
              and [event_type] = “Entry”
              and [event_date] <= [event_date]
        )
    in Table.RowCount(priorEntries)


This is expensive at scale. The more practical approach is to add this ranking in SQL before it hits Power BI:

SELECT
    app_id,
    stage_name,
    event_type,
    event_date,
    ROW_NUMBER() OVER (
        PARTITION BY app_id, stage_name, event_type
        ORDER BY event_date
    ) AS visit_number
FROM dbo.StageDurations


Push this back to SQL Server as a view, load that view into Power BI instead of the raw table. This is the right division of labor.

Step 2 — Pivot to One Row Per Visit
Once you have visit_number, split into entry and exit tables and merge:

// Entry rows
EntryRows = Table.SelectRows(Source, each [event_type] = “Entry”),
EntryRows = Table.RenameColumns(EntryRows, {{“event_date”, “stage_enter_date”}}),

// Exit rows  
ExitRows = Table.SelectRows(Source, each [event_type] = “Exit”),
ExitRows = Table.RenameColumns(ExitRows, {{“event_date”, “stage_exit_date”}}),

// Merge on app_id + stage_name + visit_number
Merged = Table.NestedJoin(
    EntryRows, {“app_id”, “stage_name”, “visit_number”},
    ExitRows,  {“app_id”, “stage_name”, “visit_number”},
    “ExitData”, JoinKind.LeftOuter
),

Expanded = Table.ExpandTableColumn(
    Merged, “ExitData”, {“stage_exit_date”}
)


Output: one row per visit with stage_enter_date and stage_exit_date side by side. Re-entries appear as visit 1, visit 2, etc.

Step 3 — Business Days Per Visit (DAX Calculated Column)
With your date table having IsBusinessDay:

Business Days = 
CALCULATE(
    COUNTROWS(DateTable),
    FILTER(
        DateTable,
        DateTable[Date] > PipelineStages[stage_enter_date] &&
        DateTable[Date] <= PipelineStages[stage_exit_date] &&
        DateTable[IsBusinessDay] = TRUE()
    )
)


This runs per visit row. For re-entered stages, you’ll have two rows contributing business days — they sum naturally in your measures.

Measure Stack

// Total business days per app per stage (sums across re-entries automatically)
Total Stage Days = SUM(PipelineStages[business_days])

// Per-application average (divide total by distinct apps, not rows)
Avg Stage Days = 
DIVIDE(
    SUMX(
        VALUES(PipelineStages[app_id]),
        CALCULATE(SUM(PipelineStages[business_days]))
    ),
    DISTINCTCOUNT(PipelineStages[app_id])
)

// YTD gate — apply to both years
CurrentDOY = DATEDIFF(DATE(YEAR(TODAY()), 1, 1), TODAY(), DAY) + 1

Avg Days 2024 = 
CALCULATE(
    [Avg Stage Days],
    FILTER(
        PipelineStages,
        YEAR(PipelineStages[stage_enter_date]) = 2024 &&
        DATEDIFF(DATE(2024, 1, 1), PipelineStages[stage_enter_date], DAY) + 1
            <= [CurrentDOY]
    )
)

Avg Days 2025 = 
CALCULATE(
    [Avg Stage Days],
    FILTER(
        PipelineStages,
        YEAR(PipelineStages[stage_enter_date]) = 2025 &&
        DATEDIFF(DATE(2025, 1, 1), PipelineStages[stage_enter_date], DAY) + 1
            <= [CurrentDOY]
    )
)

YoY Index = DIVIDE([Avg Days 2025], [Avg Days 2024]) * 100
YoY Variance (Days) = [Avg Days 2025] - [Avg Days 2024]


Model Relationships

Loan Table (app_id) ──< Stage Duration Table (app_id)
                              │
DateTable (Date) ──< Stage Duration Table (stage_enter_date)


Only relate the date table to stage_enter_date for filtering purposes. The business day calculation on stage_exit_date is handled inside the DAX column, not via a relationship.

Key Questions Before You Build
	1.	What are the actual column names in your stage duration table — specifically what distinguishes entry from exit (is it a column value, two separate date columns, or something else)?
	2.	Does the stage duration table already have a visit/sequence number, or just dates?
	3.	Does your date table already have IsBusinessDay, or does that need to be added?
Those three will determine whether the SQL view approach is necessary or if Power Query alone is sufficient.​​​​​​​​​​​​​​​​