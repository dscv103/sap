Based on the efficiency and bottleneck metrics for your nCino credit card application dashboard, here are comprehensive DAX measures organized by metric category:

## Stage Duration Measures

**Average Time in Stage (Days)**

```dax
Avg Stage Duration = 
AVERAGEX(
    Applications,
    DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
)
```

**Median Time in Stage (Days)**

```dax
Median Stage Duration = 
MEDIANX(
    Applications,
    DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
)
```

**Stage Cycle Time by Card Type**

```dax
Stage Cycle Time = 
CALCULATE(
    AVERAGEX(
        Applications,
        DATEDIFF(Applications[Stage_Start_Date], Applications[Stage_End_Date], DAY)
    ),
    ALLSELECTED(Applications[Card_Type])
)
```

**Time to First Action (Hours)**

```dax
Time to First Action = 
AVERAGEX(
    Applications,
    DATEDIFF(Applications[Stage_Entry_DateTime], Applications[First_Action_DateTime], HOUR)
)
```

## Bottleneck Identification Measures

**Stage Velocity (Applications per Day)**

```dax
Stage Velocity = 
VAR TotalApps = COUNT(Applications[Application_ID])
VAR DateRange = DATEDIFF(MIN(Applications[Stage_Start_Date]), MAX(Applications[Stage_End_Date]), DAY)
RETURN
DIVIDE(TotalApps, DateRange, 0)
```

**Queue Depth (Current Applications Waiting)**

```dax
Queue Depth = 
CALCULATE(
    COUNT(Applications[Application_ID]),
    Applications[Stage_Status] = "Queued",
    Applications[Stage_End_Date] = BLANK()
)
```

**Touch Time vs Queue Time Ratio**

```dax
Touch Time Ratio = 
VAR TouchTime = SUM(Applications[Active_Processing_Hours])
VAR QueueTime = SUM(Applications[Queue_Waiting_Hours])
VAR TotalTime = TouchTime + QueueTime
RETURN
DIVIDE(TouchTime, TotalTime, 0)
```

**Stage Abandonment Rate (%)**

```dax
Stage Abandonment Rate = 
VAR Abandoned = CALCULATE(COUNT(Applications[Application_ID]), Applications[Status] = "Withdrawn")
VAR Total = COUNT(Applications[Application_ID])
RETURN
DIVIDE(Abandoned, Total, 0) * 100
```

**Exception Rate by Stage (%)**

```dax
Exception Rate = 
VAR Exceptions = CALCULATE(COUNT(Applications[Application_ID]), Applications[Exception_Flag] = TRUE())
VAR Total = COUNT(Applications[Application_ID])
RETURN
DIVIDE(Exceptions, Total, 0) * 100
```

## Comparative Performance Measures

**Stage Duration Variance by Card Type**

```dax
Duration Variance = 
VAR ConsumerAvg = CALCULATE([Avg Stage Duration], Applications[Card_Type] = "Consumer")
VAR BusinessAvg = CALCULATE([Avg Stage Duration], Applications[Card_Type] = "Business")
VAR CommercialAvg = CALCULATE([Avg Stage Duration], Applications[Card_Type] = "Commercial")
VAR OverallAvg = [Avg Stage Duration]
RETURN
SWITCH(
    SELECTEDVALUE(Applications[Card_Type]),
    "Consumer", ConsumerAvg - OverallAvg,
    "Business", BusinessAvg - OverallAvg,
    "Commercial", CommercialAvg - OverallAvg,
    0
)
```

**Stage-to-Stage Transition Time (Hours)**

```dax
Transition Time = 
VAR CurrentStage = SELECTEDVALUE(Applications[Stage_Name])
VAR PreviousStageEnd = 
    CALCULATE(
        MAX(Applications[Stage_End_Date]),
        Applications[Stage_Sequence] = SELECTEDVALUE(Applications[Stage_Sequence]) - 1
    )
VAR CurrentStageStart = MIN(Applications[Stage_Start_Date])
RETURN
DATEDIFF(PreviousStageEnd, CurrentStageStart, HOUR)
```

**Percentage Above Target SLA (%)**

```dax
Above SLA % = 
VAR AboveSLA = 
    CALCULATE(
        COUNT(Applications[Application_ID]),
        Applications[Actual_Duration] > Applications[SLA_Target_Duration]
    )
VAR Total = COUNT(Applications[Application_ID])
RETURN
DIVIDE(AboveSLA, Total, 0) * 100
```

**Stage Throughput Rate (%)**

```dax
Throughput Rate = 
VAR OnTime = 
    CALCULATE(
        COUNT(Applications[Application_ID]),
        Applications[Actual_Duration] <= Applications[SLA_Target_Duration]
    )
VAR Total = COUNT(Applications[Application_ID])
RETURN
DIVIDE(OnTime, Total, 0) * 100
```

## Workload Distribution Measures

**Applications in Progress by Stage**

```dax
Apps in Progress = 
CALCULATE(
    COUNT(Applications[Application_ID]),
    Applications[Stage_Status] = "In Progress",
    Applications[Stage_End_Date] = BLANK()
)
```

**Stage Utilization Rate (%)**

```dax
Utilization Rate = 
VAR ActualHours = SUM(Applications[Active_Processing_Hours])
VAR AvailableHours = SUM(Resources[Available_Capacity_Hours])
RETURN
DIVIDE(ActualHours, AvailableHours, 0) * 100
```

**Backlog Age (Days)**

```dax
Backlog Age = 
AVERAGEX(
    FILTER(Applications, Applications[Stage_Status] = "Queued"),
    DATEDIFF(Applications[Stage_Entry_DateTime], TODAY(), DAY)
)
```

**Maximum Backlog Age**

```dax
Max Backlog Age = 
MAXX(
    FILTER(Applications, Applications[Stage_Status] = "Queued"),
    DATEDIFF(Applications[Stage_Entry_DateTime], TODAY(), DAY)
)
```

## Predictive Efficiency Measures

**Average Days to Completion**

```dax
Days to Completion = 
VAR CurrentStage = SELECTEDVALUE(Applications[Stage_Name])
VAR HistoricalAvg = 
    CALCULATE(
        AVERAGEX(
            FILTER(Applications, Applications[Status] = "Completed"),
            DATEDIFF(Applications[Application_Start_Date], Applications[Completion_Date], DAY)
        ),
        Applications[Stage_Name] = CurrentStage,
        Applications[Card_Type] = SELECTEDVALUE(Applications[Card_Type])
    )
RETURN
HistoricalAvg
```

**Stage Completion Probability (%)**

```dax
Completion Probability = 
VAR CurrentDuration = SELECTEDVALUE(Applications[Days_in_Current_Stage])
VAR HistoricalSuccess = 
    CALCULATE(
        DIVIDE(
            COUNTROWS(FILTER(Applications, Applications[Status] = "Approved")),
            COUNTROWS(Applications)
        ),
        Applications[Days_in_Current_Stage] >= CurrentDuration
    )
RETURN
HistoricalSuccess * 100
```

**Bottleneck Impact Score**

```dax
Bottleneck Impact = 
VAR CurrentStageDelay = [Avg Stage Duration] - [SLA Target]
VAR DownstreamStages = 
    CALCULATE(
        COUNT(Applications[Stage_Name]),
        Applications[Stage_Sequence] > SELECTEDVALUE(Applications[Stage_Sequence])
    )
VAR ImpactMultiplier = CurrentStageDelay * DownstreamStages
RETURN
ImpactMultiplier
```

## Trend Analysis Measures

**Stage Duration Trend (30-Day Moving Average)**

```dax
Duration Trend MA30 = 
CALCULATE(
    [Avg Stage Duration],
    DATESINPERIOD(
        'Date'[Date],
        LASTDATE('Date'[Date]),
        -30,
        DAY
    )
)
```

**Month-over-Month Stage Performance (%)**

```dax
MoM Stage Performance = 
VAR CurrentMonth = [Avg Stage Duration]
VAR PreviousMonth = 
    CALCULATE(
        [Avg Stage Duration],
        DATEADD('Date'[Date], -1, MONTH)
    )
RETURN
DIVIDE(CurrentMonth - PreviousMonth, PreviousMonth, 0) * 100
```

**Peak Load Hour Indicator**

```dax
Peak Load Hours = 
TOPN(
    5,
    SUMMARIZE(
        Applications,
        Applications[Stage_Entry_Hour],
        "App Count", COUNT(Applications[Application_ID])
    ),
    [App Count],
    DESC
)
```

## Card Type Comparison Measures

**Consumer vs Business Duration Delta (Days)**

```dax
Consumer vs Business Delta = 
VAR ConsumerDuration = CALCULATE([Avg Stage Duration], Applications[Card_Type] = "Consumer")
VAR BusinessDuration = CALCULATE([Avg Stage Duration], Applications[Card_Type] = "Business")
RETURN
ConsumerDuration - BusinessDuration
```

**Card Type with Longest Duration**

```dax
Slowest Card Type = 
MAXX(
    SUMMARIZE(
        Applications,
        Applications[Card_Type],
        "Avg Duration", [Avg Stage Duration]
    ),
    Applications[Card_Type]
)
```

These DAX measures provide comprehensive stage-level tracking across your consumer, business, and commercial purchasing card applications, enabling you to identify bottlenecks, monitor efficiency, and optimize your nCino credit card application workflow.[1][2][3][4]

Sources
[1] Analyzing events with a duration in DAX - SQLBI <https://www.sqlbi.com/articles/analyzing-events-with-a-duration-in-dax/>
[2] DATEDIFF function (DAX) - Microsoft Learn <https://learn.microsoft.com/en-us/dax/datediff-function-dax>
[3] How to Calculate Mean, Median & Mode in Power BI using DAX <https://www.youtube.com/watch?v=75HO3lFyWPc>
[4] How to Calculate Date Differences in Power BI with DAX Functions <https://www.singdata.com/trending/powerbi-date-difference-dax-calculations/>
[5] DAX Measure Help - Calculate time duration between two records? <https://www.reddit.com/r/PowerBI/comments/w25dzz/dax_measure_help_calculate_time_duration_between/>
[6] DAX with Dates: The Power Plays - CODE Magazine <https://www.codemag.com/Article/2111051/DAX-with-Dates-The-Power-Plays>
[7] CALCULATE TIME DURATION between two periods in POWER BI ... <https://www.youtube.com/watch?v=FAer11RUsDc>
[8] Identify Power BI Performance Bottlenecks Using the ... - B EYE <https://b-eye.com/blog/power-bi-performance-analyzer-tutorial/>
[9] Power BI DAX - Running the MEDIAN or MEDIANX formu... <https://community.powerbi.com/t5/Desktop/Power-BI-DAX-Running-the-MEDIAN-or-MEDIANX-formula-for-a/td-p/1082305>
[10] Identify Model Bottlenecks - DAX Optimizer <https://www.daxoptimizer.com/features/identify-model-bottlenecks/>
