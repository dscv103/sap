cpk_65254f0104f248e6984c6d5d9c85cc60.d590d98f53f350fcbf0152361deb93c4.IKlmU8l6AqAeNT9nZ55fyA3ZTWBuF47h

Based on your nCino credit card application dashboard, here are the most effective visual types and layouts specifically for **efficiency and bottleneck analysis**:

***

## **Primary Bottleneck Identification Visuals**

### **1. Stage Duration Heat Map** ⭐ Most Critical
**Visual Type:** Matrix with Conditional Formatting
- **Rows:** Application Stages (8-12 stages typical)
- **Columns:** Card Types (Consumer, Business, Commercial)
- **Values:** Average days OR % exceeding SLA
- **Formatting:** 
  - Red gradient (>SLA target by 50%+)
  - Yellow (10-50% over target)
  - Green (within target)
  - White (under target)
- **Why it works:** Instantly shows which stage-card type combinations are problematic
- **Placement:** Top-left, largest visual on bottleneck page

### **2. Waterfall Chart for Stage Flow**
**Visual Type:** Waterfall Chart
- **X-axis:** Sequential stages
- **Y-axis:** Application count
- **Shows:** Drop-off at each stage
- **Color coding:**
  - Green bars = applications moving forward
  - Red bars = applications stuck/rejected
- **Why it works:** Visualizes where applications get stuck or abandoned
- **Placement:** Top-right of bottleneck page

### **3. Pareto Chart (80/20 Analysis)**
**Visual Type:** Combo Chart (Clustered Column + Line)
- **Columns:** Stages ranked by total delay contribution (descending)
- **Line:** Cumulative percentage
- **Target line:** 80% marker
- **Why it works:** Identifies which 2-3 stages cause 80% of delays
- **Insight:** Focus improvement efforts on these stages
- **Placement:** Center-left, medium size

***

## **Efficiency Measurement Visuals**

### **4. Cycle Time Trend** ⭐ Critical for Tracking Improvement
**Visual Type:** Line Chart with Forecast
- **X-axis:** Time (daily/weekly rolling average)
- **Y-axis:** Average application duration (days)
- **Multiple lines:** One per card type
- **Target line:** SLA benchmark (horizontal reference)
- **Analytics:** Add trend line and forecast
- **Why it works:** Shows if efficiency is improving over time
- **Placement:** Top of efficiency section, full width

### **5. Box and Whisker Plot**
**Visual Type:** Box and Whisker (or Violin Plot if using Python visual)
- **X-axis:** Stages
- **Shows:** 
  - Median (line in box)
  - Q1-Q3 (box)
  - Min/Max (whiskers)
  - Outliers (dots)
- **Why it works:** Reveals variability and consistency issues; outliers indicate process breakdowns
- **Filter:** Add slicer for card type
- **Placement:** Center-right, medium size

### **6. Stage Velocity Gauge Charts**
**Visual Type:** Multiple Gauge Charts (Small Multiples)
- **One gauge per stage**
- **Shows:** Current throughput rate vs. target
- **Color zones:**
  - Red zone: <70% of target
  - Yellow zone: 70-90% of target
  - Green zone: >90% of target
- **Why it works:** Quick visual health check for each stage
- **Placement:** Bottom row, 6-8 gauges in a row

***

## **Comparative Efficiency Visuals**

### **7. Small Multiples - Stage Duration by Card Type**
**Visual Type:** Small Multiples (Bar Charts)
- **Create:** Three identical horizontal bar charts side-by-side
- **One chart per card type:** Consumer | Business | Commercial
- **Bars:** Each stage's average duration
- **Why it works:** Easy visual comparison across card types
- **Placement:** Mid-page, spans full width

### **8. Scatter Plot - Relationship Manager Performance**
**Visual Type:** Scatter Chart
- **X-axis:** Application volume (count)
- **Y-axis:** Average duration (days)
- **Bubble size:** Completion rate %
- **Color:** Card type or region
- **Quadrants:**
  - Top-right: High volume, slow (bottleneck)
  - Bottom-right: High volume, fast (efficient)
  - Top-left: Low volume, slow (training issue?)
  - Bottom-left: Low volume, fast (ideal)
- **Why it works:** Identifies individual performance patterns
- **Placement:** Bottom-left of efficiency page

***

## **Aging & At-Risk Applications**

### **9. Aging Analysis - Stacked Area Chart**
**Visual Type:** Stacked Area Chart
- **X-axis:** Date
- **Y-axis:** Application count
- **Stacks:** Age buckets
  - 0-7 days (green)
  - 8-14 days (yellow)
  - 15-21 days (orange)
  - 22+ days (red)
- **Why it works:** Shows buildup of aged applications over time
- **Alert indicator:** Rising red area = growing bottleneck
- **Placement:** Top-right of operational page

### **10. Current Pipeline Funnel with Duration**
**Visual Type:** Enhanced Funnel Chart
- **Stages:** Top to bottom
- **Width:** Number of applications
- **Color intensity:** Average days in stage (darker = longer)
- **Callout boxes:** Show exact counts and avg duration
- **Why it works:** Combines volume and duration in single visual
- **Placement:** Center-left, large focal point

***

## **Detail & Drill-Down Visuals**

### **11. Top 10 Slowest Applications Table**
**Visual Type:** Table with Conditional Formatting
**Columns:**
- Application ID (link/drill-through)
- Card Type (icon)
- Current Stage
- Days in Stage (conditional bar)
- Total Days Open (conditional bar)
- Assigned To
- Risk Level (icon: 🔴🟡🟢)

**Formatting:**
- Row-level color coding based on severity
- Data bars for duration columns
- Icons for quick scanning

**Why it works:** Action-oriented, identifies specific problems
**Placement:** Right panel, always visible

### **12. Stage-to-Stage Transition Matrix**
**Visual Type:** Matrix (Sankey Diagram alternative)
- **Rows:** From Stage
- **Columns:** To Stage
- **Values:** Average transition time + count
- **Why it works:** Shows where handoffs slow down
- **Advanced:** Use Python/R visual for Sankey diagram
- **Placement:** Drill-through page

***

## **Recommended Dashboard Layout (Bottleneck & Efficiency Page)**

```
┌─────────────────────────────────────────────────────────────┐
│  [Slicers: Card Type | Date Range | Region]                 │
├────────────────────┬────────────────────────────────────────┤
│  KPI Cards:        │                                        │
│  ┌──────┐┌──────┐  │    Stage Duration Heat Map             │
│  │Apps  ││Avg   │  │    (Matrix - Conditional Formatting)   │
│  │Over  ││Delay │  │    ⭐ PRIMARY FOCUS VISUAL            │
│  │SLA   ││Days  │  │                                        │
│  └──────┘└──────┘  │                                        │
├────────────────────┼────────────────────┬───────────────────┤
│  Pareto Analysis   │  Cycle Time Trend  │  Waterfall Chart  │
│  (80/20 Rule)      │  (Line Chart)      │  (Stage Flow)     │
│  ⭐ FOCUS AREAS    │  📈 TREND          │  📊 DROP-OFFS     │
├────────────────────┴────────────────────┴───────────────────┤
│  Box & Whisker: Stage Duration Variability                  │
│  (Shows outliers and consistency)                           │
├──────────────────┬──────────────────┬──────────────────────┤
│  Small Multiple: │  Small Multiple: │  Small Multiple:     │
│  Consumer Cards  │  Business Cards  │  Commercial Cards    │
│  (Stage Bars)    │  (Stage Bars)    │  (Stage Bars)        │
├──────────────────┴──────────────────┴──────────────────────┤
│  Stage Velocity Gauges (6-8 gauges in row)                 │
│  [Submit][Review][Credit][UW][Approve][Fulfill]             │
├─────────────────────────────────────┬───────────────────────┤
│  RM Performance Scatter Plot        │  Top 10 Slowest Apps  │
│  (Volume vs Duration)               │  (Action Table)       │
│  🎯 PEOPLE ANALYSIS                 │  🚨 URGENT ITEMS      │
└─────────────────────────────────────┴───────────────────────┘
```

***

## **Visual Hierarchy Best Practices**

### **Size Priority (Largest to Smallest)**
1. **Stage Duration Heat Map** (30-35% of page)
2. **Cycle Time Trend** (20% of page)
3. **Pareto Chart** (15% of page)
4. **Waterfall Chart** (15% of page)
5. **Box & Whisker** (12% of page)
6. **Supporting visuals** (remaining space)

### **Eye Flow Pattern**
- **Top-left:** Critical bottleneck identification (heat map)
- **Top-right:** Immediate actionable items (slowest apps, waterfall)
- **Center:** Analytical deep dives (Pareto, trends)
- **Bottom:** Supporting context (comparative analysis, gauges)

### **Color Strategy for Efficiency/Bottlenecks**
- **Red (#C0152F):** Critical delays, SLA breaches
- **Orange (#E68161):** At-risk, approaching SLA
- **Yellow (#F5A623):** Warning, needs attention
- **Green (#21808D):** On-target, healthy
- **Grey (#626C71):** Completed, neutral

***

## **Interactive Features to Add**

1. **Drill-through:** Click any stage in heat map → detail page for that stage
2. **Cross-filtering:** Select card type → all visuals filter
3. **Tooltips:** Hover over heat map cell → shows min/max/median durations
4. **Dynamic titles:** "Bottleneck: [Stage Name] averaging [X] days"
5. **Bookmarks:** Toggle between "All Applications" and "Only Overdue"
6. **What-if parameter:** Adjust SLA targets to see impact on compliance rates

***

## **Advanced Analytics to Consider**

If you're incorporating **R/Python visuals**:
- **Correlation matrix:** Which stages' durations correlate (delays cascade?)
- **Anomaly detection:** Flag unusual duration spikes
- **Predictive duration:** ML model predicting completion time based on current stage
- **Network diagram:** Stage transitions with weighted edges (thicker = longer transition time)

***

These visuals will give you a powerful, action-oriented dashboard that immediately highlights bottlenecks while tracking efficiency improvements over time. The heat map + Pareto combination is especially effective for executive presentations.

Would you like me to provide specific DAX measures for any of these visuals, or help with the Python/R code for advanced visualizations?

Sources
