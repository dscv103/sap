Without SLA targets, you can calculate stage delays using alternative benchmarks such as historical averages, percentiles, or peer comparisons. Here are several DAX measures for **Total Stage Delay** that don’t require predefined SLA targets:

## Historical Average as Baseline

**Total Delay vs Historical Avg (Days)**
```dax
Total Delay vs Historical Avg = 
VAR HistoricalAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        REMOVEFILTERS(‘Date’),
        Applications[Stage_Status] = “Completed”
    )
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - HistoricalAvg
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This uses your overall historical average duration as the baseline, identifying applications that exceed typical processing time.[1][2]

## Median as Baseline (More Robust)

**Total Delay vs Median Duration (Days)**
```dax
Total Delay vs Median = 
VAR MedianDuration = 
    MEDIANX(
        FILTER(
            ALL(Applications),
            Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    )
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - MedianDuration
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

Using the median is more robust against outliers and provides a better “typical” baseline than the average.[3][4]

## 75th Percentile as Performance Threshold

**Total Delay vs 75th Percentile (Days)**
```dax
Total Delay vs P75 = 
VAR P75Duration = 
    PERCENTILEX.INC(
        FILTER(
            ALL(Applications),
            Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY),
        0.75
    )
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - P75Duration
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This identifies applications in the slowest 25%, using the 75th percentile as your performance threshold.[4][3]

## Stage-Specific Historical Average

**Total Delay vs Stage Average (Days)**
```dax
Total Delay vs Stage Avg = 
SUMX(
    Applications,
    VAR CurrentStage = Applications[Stage_Name]
    VAR StageAvg = 
        CALCULATE(
            AVERAGEX(
                Applications,
                DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
            ),
            Applications[Stage_Name] = CurrentStage,
            REMOVEFILTERS(‘Date’),
            Applications[Stage_Status] = “Completed”
        )
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - StageAvg
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This calculates delay against stage-specific historical averages, recognizing that different stages have different normal durations.[2][1]

## Card Type Specific Baseline

**Total Delay vs Card Type Avg (Days)**
```dax
Total Delay vs Card Type Avg = 
SUMX(
    Applications,
    VAR CurrentCardType = Applications[Card_Type]
    VAR CurrentStage = Applications[Stage_Name]
    VAR CardTypeStageAvg = 
        CALCULATE(
            AVERAGEX(
                Applications,
                DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
            ),
            Applications[Card_Type] = CurrentCardType,
            Applications[Stage_Name] = CurrentStage,
            REMOVEFILTERS(‘Date’),
            Applications[Stage_Status] = “Completed”
        )
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - CardTypeStageAvg
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This recognizes that Consumer, Business, and Commercial cards may have different normal processing times and calculates delay accordingly.[5][1]

## Rolling Average Baseline (Last 90 Days)

**Total Delay vs Rolling 90-Day Avg**
```dax
Total Delay vs Rolling Avg = 
SUMX(
    Applications,
    VAR CurrentStage = Applications[Stage_Name]
    VAR CurrentDate = Applications[Stage_End_Date]
    VAR Rolling90Avg = 
        CALCULATE(
            AVERAGEX(
                Applications,
                DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
            ),
            Applications[Stage_Name] = CurrentStage,
            Applications[Stage_End_Date] >= CurrentDate - 90,
            Applications[Stage_End_Date] < CurrentDate,
            Applications[Stage_Status] = “Completed”
        )
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Rolling90Avg
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This uses a rolling 90-day average as the baseline, which adapts to recent performance trends and seasonal variations.[6][3]

## Best Performance Baseline (Top 25%)

**Total Delay vs Best Quartile (Days)**
```dax
Total Delay vs Best Performance = 
VAR BestQuartile = 
    PERCENTILEX.INC(
        FILTER(
            ALL(Applications),
            Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY),
        0.25
    )
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - BestQuartile
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This uses your best performance (25th percentile) as the aspirational target, showing how much each application deviates from best-in-class processing.[3][4]

## Month-over-Month Variance

**Total Delay vs Prior Month Avg**
```dax
Total Delay vs Prior Month = 
VAR PriorMonthAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        DATEADD(‘Date’[Date], -1, MONTH),
        Applications[Stage_Status] = “Completed”
    )
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - PriorMonthAvg
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This measures current performance against the previous month’s average, highlighting month-over-month deterioration.[7][5]

## Standard Deviation Threshold

**Total Delay Beyond 1 Std Dev (Days)**
```dax
Total Delay Beyond StdDev = 
VAR AvgDuration = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        REMOVEFILTERS(‘Date’),
        Applications[Stage_Status] = “Completed”
    )
VAR StdDev = 
    STDEV.P(
        CALCULATETABLE(
            ADDCOLUMNS(
                Applications,
                “Duration”, DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
            ),
            Applications[Stage_Status] = “Completed”
        )[Duration]
    )
VAR Threshold = AvgDuration + StdDev
RETURN
SUMX(
    Applications,
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Threshold
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This identifies applications that exceed one standard deviation above the mean, flagging statistical outliers as delays.[5]

These approaches allow you to establish dynamic, data-driven baselines for measuring delays without requiring predefined SLA targets, using your own historical performance data to define what constitutes a delay for Consumer, Business, and Commercial purchasing card applications.[1][2][4][3]

Sources
[1] Re: calculate average delay in (days,hours,minutes,seconds) https://community.fabric.microsoft.com/t5/DAX-Commands-and-Tips/calculate-average-delay-in-days-hours-minutes-seconds/m-p/1523512
[2] Power BI DAX measures - Average Delivery Time - LinkedIn https://www.linkedin.com/pulse/power-bi-dax-measures-average-delivery-time-mark-bujarski-mba-mis
[3] Power BI: Create Moving Average & Percentile Charts with DAX https://www.youtube.com/watch?v=blfY6Na8WlI
[4] How to find PERCENTILE using Power BI DAX - YouTube https://www.youtube.com/watch?v=JM_l54E8_IU
[5] Variance measure, how to make it work with date hi... https://community.fabric.microsoft.com/t5/DAX-Commands-and-Tips/Variance-measure-how-to-make-it-work-with-date-hierarchy-e-g/m-p/1642883
[6] Calculate A Rolling Average In Power BI Using DAX - YouTube https://www.youtube.com/watch?v=MHKPfoNEyDU
[7] Solved: Calculate variance between academic/financial year... https://community.fabric.microsoft.com/t5/Desktop/Calculate-variance-between-academic-financial-years/td-p/4120822
[8] Slow Dax Measure is there anyway to increase the p... https://community.powerbi.com/t5/Desktop/Slow-Dax-Measure-is-there-anyway-to-increase-the-performance-or/td-p/997529
[9] Power BI DAX - Calculate a delay with filter and avoid circular ... https://stackoverflow.com/questions/67422199/power-bi-dax-calculate-a-delay-with-filter-and-avoid-circular-dependency
[10] Analyzing events with a duration in DAX - SQLBI https://www.sqlbi.com/articles/analyzing-events-with-a-duration-in-dax/


Perfect! You need to exclude the “Complete” and “Booked” stages from your standard deviation calculation since those stages continue accumulating time even though the application process is functionally complete. Here’s the corrected DAX measure:

## Exclude Complete and Booked Stages

**Total Delay Beyond StdDev (Excluding Complete/Booked)**
```dax
Total Delay Beyond StdDev Excluding Final = 
VAR CleanedAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        Applications[Stage_Name] <> “Complete”,
        Applications[Stage_Name] <> “Booked”,
        Applications[Stage_Status] = “Completed”
    )
VAR CleanedStdDev = 
    STDEVX.S(
        FILTER(
            ALL(Applications),
            Applications[Stage_Name] <> “Complete”
            && Applications[Stage_Name] <> “Booked”
            && Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    )
VAR Threshold = CleanedAvg + CleanedStdDev
RETURN
SUMX(
    FILTER(
        Applications,
        Applications[Stage_Name] <> “Complete”
        && Applications[Stage_Name] <> “Booked”
    ),
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Threshold
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

## Alternative: Using NOT IN for Multiple Exclusions

**Total Delay Beyond StdDev (NOT IN Version)**
```dax
Total Delay Beyond StdDev Clean = 
VAR ExcludedStages = {“Complete”, “Booked”}
VAR CleanedAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        NOT(Applications[Stage_Name] IN ExcludedStages),
        Applications[Stage_Status] = “Completed”
    )
VAR CleanedStdDev = 
    STDEVX.S(
        FILTER(
            ALL(Applications),
            NOT(Applications[Stage_Name] IN ExcludedStages)
            && Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    )
VAR Threshold = CleanedAvg + CleanedStdDev
RETURN
SUMX(
    FILTER(
        Applications,
        NOT(Applications[Stage_Name] IN ExcludedStages)
    ),
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Threshold
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This version uses the `NOT IN` syntax, making it easier to add additional stages to exclude in the future.[1][2]

## With Additional Percentile Filtering

**Total Delay Beyond StdDev (Exclude Stages + Outliers)**
```dax
Total Delay StdDev Final Clean = 
VAR ExcludedStages = {“Complete”, “Booked”}
VAR P95 = 
    PERCENTILEX.INC(
        FILTER(
            ALL(Applications),
            NOT(Applications[Stage_Name] IN ExcludedStages)
            && Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY),
        0.95
    )
VAR CleanedAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        NOT(Applications[Stage_Name] IN ExcludedStages),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY) <= P95,
        Applications[Stage_Status] = “Completed”
    )
VAR CleanedStdDev = 
    STDEVX.S(
        FILTER(
            ALL(Applications),
            NOT(Applications[Stage_Name] IN ExcludedStages)
            && Applications[Stage_Status] = “Completed”
            && DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY) <= P95
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    )
VAR Threshold = CleanedAvg + CleanedStdDev
RETURN
SUMX(
    FILTER(
        Applications,
        NOT(Applications[Stage_Name] IN ExcludedStages)
    ),
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Threshold
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This combines both approaches: excluding the Complete and Booked stages AND filtering out the top 5% of outliers from the remaining stages, giving you the most robust calculation.[2][3]

## Stage-Specific Version

**Total Delay by Active Stages Only**
```dax
Total Delay Active Stages = 
VAR ActiveStages = {“Application Review”, “Credit Analysis”, “Underwriting”, “Approval”, “Documentation”}
VAR StageAvg = 
    CALCULATE(
        AVERAGEX(
            Applications,
            DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
        ),
        Applications[Stage_Name] IN ActiveStages,
        Applications[Stage_Status] = “Completed”
    )
VAR StageStdDev = 
    STDEVX.S(
        FILTER(
            ALL(Applications),
            Applications[Stage_Name] IN ActiveStages
            && Applications[Stage_Status] = “Completed”
        ),
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    )
VAR Threshold = StageAvg + StageStdDev
RETURN
SUMX(
    FILTER(
        Applications,
        Applications[Stage_Name] IN ActiveStages
    ),
    VAR ActualDuration = DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    VAR Delay = ActualDuration - Threshold
    RETURN
    IF(Delay > 0, Delay, 0)
)
```

This approach explicitly includes only the active processing stages, which may be cleaner if you have a defined list of operational stages.[1][2]

By excluding Complete and Booked stages from your calculations, your average should remain around 2.77 days, and your standard deviation will be much more reasonable—likely in the range of 1-3 days rather than thousands. This will give you a meaningful threshold for identifying delayed applications in your Consumer, Business, and Commercial purchasing card workflows.[4][2][1]

Sources
[1] Solved: How to exclude certain value within Filter (illust... https://community.fabric.microsoft.com/t5/DAX-Commands-and-Tips/How-to-exclude-certain-value-within-Filter-illustrated-on-the/m-p/3762465
[2] Need help with multiple filter values in DAX! - Fabric Community https://community.fabric.microsoft.com/t5/Desktop/Need-help-with-multiple-filter-values-in-DAX/td-p/3296393
[3] Remove outliers- greater than 2 standard deviation from mean https://community.fabric.microsoft.com/t5/Desktop/Remove-outliers-greater-than-2-standard-deviation-from-mean/m-p/865721
[4] How to exclude certain row values in dax measure? https://community.fabric.microsoft.com/t5/Desktop/How-to-exclude-certain-row-values-in-dax-measure/m-p/632861
[5] How to ignore a specific filter in measure and keep all other filters? https://community.powerbi.com/t5/Desktop/How-to-ignore-a-specific-filter-in-measure-and-keep-all-other/td-p/2496324
[6] ALLEXCEPT function (DAX) - Microsoft Learn https://learn.microsoft.com/en-us/dax/allexcept-function-dax
[7] DAX for Power BI Part 5.4 - Removing Filters with AllSelected and ... https://www.youtube.com/watch?v=YU30TD1qIvQ
[8] Learn methods to exclude measures in calculation groups with DAX ... https://www.youtube.com/watch?v=Op-JUSyP4XM
[9] How to Exclude Selected Values in a Power BI Slicer - YouTube https://www.youtube.com/watch?v=tqMnmHKdcVQ
[10] How to create a DAX measure to filter a table on multiple levels https://www.reddit.com/r/PowerBI/comments/qg8fv9/how_to_create_a_dax_measure_to_filter_a_table_on/
[11] DAX code to ignore the row context... help! : r/PowerBI - Reddit https://www.reddit.com/r/PowerBI/comments/gevy0j/dax_code_to_ignore_the_row_context_help/

