Perfect, that clarifies everything. Here’s exactly what to build.

What Your Stage Table Looks Like



|app_id|stage_name  |event_date|exit_flag|
|——|————|-———|———|
|A001  |Underwriting|2024-03-01|0        |
|A001  |Underwriting|2024-03-08|1        |
|A001  |Underwriting|2024-03-15|0        |
|A001  |Underwriting|2024-03-22|1        |

Two problems to solve before Power BI can use this:
	∙	No visit number → can’t pair entry to its matching exit
	∙	One row per event → need one row per visit with both dates side by side
Both are cleanest to solve in SQL before the data hits Power BI.

Step 1 — SQL View: Add Visit Numbers + Pivot to One Row Per Visit

CREATE VIEW dbo.v_StageDurations AS

WITH Numbered AS (
    SELECT
        app_id,
        stage_name,
        event_date,
        exit_flag,
        — Rank entries and exits independently within each app+stage
        ROW_NUMBER() OVER (
            PARTITION BY app_id, stage_name, exit_flag
            ORDER BY event_date
        ) AS visit_number
    FROM dbo.StageDurations
),

Entries AS (
    SELECT app_id, stage_name, event_date AS stage_enter_date, visit_number
    FROM Numbered
    WHERE exit_flag = 0
),

Exits AS (
    SELECT app_id, stage_name, event_date AS stage_exit_date, visit_number
    FROM Numbered
    WHERE exit_flag = 1
)

SELECT
    e.app_id,
    e.stage_name,
    e.visit_number,
    e.stage_enter_date,
    x.stage_exit_date,                          — NULL if still in-flight
    YEAR(e.stage_enter_date)    AS entry_year,
    DATEDIFF(
        DAY, DATE(YEAR(e.stage_enter_date), 1, 1), e.stage_enter_date
    ) + 1                       AS day_of_year  — for YTD gating in DAX
FROM Entries e
LEFT JOIN Exits x
    ON  e.app_id        = x.app_id
    AND e.stage_name    = x.stage_name
    AND e.visit_number  = x.visit_number;


The LEFT JOIN preserves in-flight applications where no exit row exists yet — important for your current pipeline page.
Load this view into Power BI instead of the raw table.

Step 2 — DAX Calculated Column: Business Days Per Visit
With stage_enter_date and stage_exit_date now on the same row and your date table already having IsBusinessDay:

Business Days = 
CALCULATE(
    COUNTROWS(DateTable),
    FILTER(
        DateTable,
        DateTable[Date] > StageDurations[stage_enter_date] &&
        DateTable[Date] <= StageDurations[stage_exit_date] &&
        DateTable[IsBusinessDay] = TRUE()
    )
)


This returns BLANK for in-flight rows where stage_exit_date is NULL, which is correct — exclude them from duration averages automatically.

Step 3 — DAX Measure Stack

// Average business days per application per stage
// SUMX per app_id first, then average — avoids double-counting re-entry visits
Avg Stage Days =
DIVIDE(
    SUMX(
        VALUES(StageDurations[app_id]),
        CALCULATE(SUM(StageDurations[Business Days]))
    ),
    DISTINCTCOUNT(StageDurations[app_id])
)

// Day-of-year ceiling for YTD gating
CurrentDOY =
DATEDIFF(DATE(YEAR(TODAY()), 1, 1), TODAY(), DAY) + 1

// 2024 YTD-gated average
Avg Days 2024 =
CALCULATE(
    [Avg Stage Days],
    StageDurations[entry_year] = 2024,
    StageDurations[day_of_year] <= [CurrentDOY]
)

// 2025 YTD-gated average
Avg Days 2025 =
CALCULATE(
    [Avg Stage Days],
    StageDurations[entry_year] = 2025,
    StageDurations[day_of_year] <= [CurrentDOY]
)

// Index: 100 = same pace, >100 = slower in 2025, <100 = faster
YoY Index =
DIVIDE([Avg Days 2025], [Avg Days 2024]) * 100

// Raw day difference
YoY Variance (Days) = [Avg Days 2025] - [Avg Days 2024]


Step 4 — Model Relationships

LoanTable[app_id]  ──<  StageDurations[app_id]

DateTable[Date]  ──<  StageDurations[stage_enter_date]


	∙	Relate DateTable only to stage_enter_date — this drives your slicers and year filters
	∙	The business day calculation references stage_exit_date internally inside the DAX column, not via a relationship

One Thing to Verify in Your Data
The ROW_NUMBER() pairing assumes the nth entry always pairs with the nth exit for a given app + stage. This holds as long as exits are never recorded before their corresponding entry. Run this sanity check:

SELECT app_id, stage_name, COUNT(*) AS event_count
FROM dbo.StageDurations
GROUP BY app_id, stage_name
HAVING COUNT(*) % 2 != 0  — odd number of events = unpaired entry or exit


Any rows returned here are data quality issues that will produce NULL stage_exit_date unexpectedly, separate from genuine in-flight applications. Worth cleaning before building the report.

What does exit_flag actually hold — 0/1, True/False, or text like “Entry”/“Exit”? The SQL above uses 0/1 but that WHERE clause needs to match your actual values.​​​​​​​​​​​​​​​​