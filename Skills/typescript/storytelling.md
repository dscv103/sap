# Storytelling with Data — Principles for Power BI Custom Visuals

Every Power BI visual is a communication act. The technical implementation is only half the job — the other half is ensuring the visual efficiently transfers the right insight to the right person in as few cognitive steps as possible. These principles apply at the moment you make every design decision in `update()`.

—

## The Core Frame: Explain vs. Explore

Before writing a line of rendering code, answer one question:

**Is this visual designed to explain a known insight, or let users explore to find one?**

| Mode | Goal | Design consequences |
|——|——|———————|
| **Explain** | Deliver a specific pre-known insight | Highlight the key finding, mute context, annotate the punchline, write an insight-driven title |
| **Explore** | Let users discover patterns themselves | Offer interactivity, cross-filtering, drill-down; keep neutral colors; provide richer tooltip context |

Most Power BI custom visuals live in dashboards and lean **explanatory** — the developer knows what story the data tells, and the visual should tell it clearly. Design for that mode. When a visual tries to do both at once, it usually does neither well.

—

## Pre-Attentive Attributes — Your Most Powerful Tool

Pre-attentive attributes are visual properties processed by the brain in under 250 milliseconds — before conscious attention. They are the only truly “free” way to direct a viewer’s eye.

The four categories and their power for quantitative data:

| Attribute | Examples | Good for |
|————|-———|-———|
| **Position** | x/y placement on an axis | Most accurate for quantitative comparison — humans judge position better than any other attribute |
| **Length** | Bar height/width, line length | Accurate for magnitude comparison — the foundation of bar charts |
| **Color hue** | Red vs. blue vs. green | Categorical grouping; one accent color to flag the insight |
| **Color intensity/value** | Light gray → dark blue | Sequential magnitude (heatmaps, density maps) |
| **Size** | Circle radius, stroke weight | Rough magnitude only — humans underestimate area differences |
| **Orientation** | Angle of a line | Trend direction; poor for precise values |
| **Shape** | Circle vs. square vs. triangle | Category membership; max ~5 distinct shapes before confusion |

**Key rule**: Use only 1–2 pre-attentive attributes to carry the data message. Every additional attribute you add forces the viewer to do more work to decode what matters.

### Implementing pre-attentive highlighting in D3

The most powerful storytelling technique: mute everything to gray, then accent the insight:

```typescript
// After rendering bars normally, apply highlight:
const highlightValue = ‘Product A’; // the insight you want to tell

this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’)
  .attr(‘fill’, d => d.label === highlightValue
    ? ‘#EF4444’     // accent: the story
    : ‘#D1D5DB’     // muted: context
  )
  .attr(‘opacity’, d => d.label === highlightValue ? 1 : 0.6);

// Label only the highlighted bar
this.container.selectAll<SVGTextElement, DataPoint>(‘.dataLabel’)
  .style(‘display’, d => d.label === highlightValue ? ‘block’ : ‘none’);
```

—

## Gestalt Principles — How Viewers Group What They See

Gestalt principles describe how the human brain automatically organizes visual elements into meaningful wholes. Each one is a design lever you control through code.

### Proximity
Elements close together are perceived as a group. Use spatial arrangement to communicate grouping without borders or colors.

```typescript
// Grouped bar chart: tighten intra-group padding, widen inter-group padding
const xGroup = d3.scaleBand().domain(groups).range([0, innerW]).padding(0.3);
const xBar   = d3.scaleBand().domain(series).range([0, xGroup.bandwidth()]).padding(0.05);
// The tight xBar.padding makes bars within a group read as one unit
```

### Similarity
Elements that look alike are assumed to belong together. Encode category membership with consistent color across every chart that shares a dimension.

```typescript
// Same category → always same color across all visuals in the report
const color = this.host.colorPalette.getColor(d.category).value;
// Never reassign colors on re-render — Power BI palette is stable per session
```

### Enclosure
A boundary around elements groups them. Use bounding boxes or background fills for annotation callouts and grouped small multiples.

```typescript
// Add a subtle background panel behind an annotation
this.container.append(‘rect’)
  .attr(‘x’, annotX - 8).attr(‘y’, annotY - 6)
  .attr(‘width’, annotWidth + 16).attr(‘height’, annotHeight + 12)
  .attr(‘fill’, ‘#F9FAFB’).attr(‘rx’, 4)
  .attr(‘stroke’, ‘#E5E7EB’).attr(‘stroke-width’, 1);
```

### Continuity
The eye follows the smoothest path. In line charts, continuity means the viewer reads the line as a single entity and immediately perceives the trend.

```typescript
// Smooth line (monotone cubic avoids visual “bouncing”)
const line = d3.line<DataPoint>()
  .x(d => x(d.date))
  .y(d => y(d.value))
  .curve(d3.curveMonotoneX);   // smoother than d3.curveLinear; no overshoot
```

### Connection
Physically connected objects are perceived as a group. Line charts exploit this — the connecting line creates an implicit narrative of change. Use sparingly for annotation leader lines.

### Figure / Ground
The eye separates foreground (figure) from background (ground). Your data elements must always have enough contrast to read as figure against the report background. Use Power BI theme colors for the ground, your accent for the figure.

```typescript
// Always test fill against the host background
const bg = this.host.colorPalette.background?.value ?? ‘#FFFFFF’;
// Your accent should pass WCAG AA contrast ratio (≥ 4.5:1) against bg
```

—

## Data-Ink Ratio — The Tufte Principle

Edward Tufte’s foundational rule: **the larger the share of a visual’s “ink” devoted to data, the better.** Everything else is noise.

### What to eliminate by default

In `update()`, actively resist D3 and Power BI defaults that add non-data ink:

```typescript
// Remove the axis domain lines (the outer border of the axis)
this.xAxis.select(‘.domain’).remove();
this.yAxis.select(‘.domain’).remove();

// Replace heavy tick marks with short, light ones
this.xAxis.call(d3.axisBottom(xScale).tickSizeOuter(0).tickSizeInner(4));
this.yAxis.call(d3.axisLeft(yScale).ticks(5).tickSizeOuter(0).tickSizeInner(4));

// Style grid lines: faint, dashed, horizontal only
this.container.selectAll(‘.gridLine’)
  .data(yScale.ticks(5))
  .join(‘line’).classed(‘gridLine’, true)
    .attr(‘x1’, 0).attr(‘x2’, innerW)
    .attr(‘y1’, d => yScale(d)).attr(‘y2’, d => yScale(d))
    .attr(‘stroke’, ‘#E5E7EB’)
    .attr(‘stroke-dasharray’, ‘3 4’)
    .attr(‘stroke-width’, 1);
```

### Clutter checklist (review before every release)

Run through these before packaging:

- [ ] Chart border: **removed** (white space creates separation, not borders)
- [ ] Gridlines: **horizontal only**, light gray (`#E5E7EB`), dashed
- [ ] Y-axis line: **removed** (bars’ alignment implies the axis)
- [ ] Tick marks: **short** (4px inner), no outer ticks
- [ ] Background fill: **transparent** (let the report canvas show through)
- [ ] Legend: **replaced with direct labels** where possible
- [ ] Data labels: **selective** — only on key values, or toggled off by default
- [ ] 3D effects: **never** (distorts perception, adds zero information)
- [ ] Axis label: **not redundant with title** (if title says “Monthly Revenue ($M)”, x-axis label “Month” is noise)
- [ ] Decimal precision: **matches the data’s meaningful precision** (not 6 decimal places on a KPI showing millions)

—

## Chart Selection — Match Chart to Question

Start with the analytical question, then pick the chart. Never the reverse.

| Question | Best chart | Avoid |
|-———|————|-——|
| **Compare magnitudes** across categories | Horizontal bar (long labels) or column (short labels) | Pie, 3D anything |
| **Show trend over time** (continuous) | Line chart | Bar (trend; bars imply discrete), Pie |
| **Show trend over time** (discrete periods) | Column chart | Line (implies interpolation between points) |
| **Show part-to-whole** (few categories, ≤ 5) | Donut / pie | Stacked bar when comparisons across groups needed |
| **Show part-to-whole** (many categories, hierarchical) | Treemap | Pie (unreadable at scale) |
| **Show distribution** | Histogram, box plot, violin | Bar chart (wrong semantics) |
| **Show correlation** between two variables | Scatter plot | Line (implies sequence) |
| **Show correlation** with overplotting | Hexbin / 2D histogram | Scatter (points overlap) |
| **Show composition change over time** | Stacked area (few series ≤ 4) or small multiples | Stacked bar with many time periods |
| **Show performance vs. target** | Bullet chart | Gauge, speedometer |
| **Show ranking** | Sorted horizontal bar | Unsorted bar, radar/spider |
| **Show flow or transfer** | Sankey diagram | Pie |
| **Show geo patterns** | Choropleth, dot map | Bar chart labeled by region |

### The bar chart bias correction

Horizontal bars are underused. Use them whenever:
- Category labels are more than ~8 characters
- There are more than ~8 categories
- The visual is taller than it is wide

```typescript
// Horizontal bar — swap x/y scales
const xScale = d3.scaleLinear().domain([0, maxVal]).range([0, innerW]);
const yScale = d3.scaleBand().domain(data.map(d => d.label)).range([0, innerH]).padding(0.2);

bars.attr(‘x’, 0)
    .attr(‘y’, d => yScale(d.label)!)
    .attr(‘width’, d => xScale(d.value))
    .attr(‘height’, yScale.bandwidth());
```

### Sorting rule

Always sort bars by value (descending) unless there is a natural order (time, alphabetical expectation, ordinal scale). Sorted bars make ranking immediately visible without reading every label.

```typescript
data.sort((a, b) => b.value - a.value);
// Then bind sorted data to xScale domain
xScale.domain(data.map(d => d.label));
```

—

## Titles as Insight Statements

The title is the most-read element of any visual. Make it do the storytelling work.

| Type | Example | Use when |
|——|———|-———|
| **Descriptive** | “Revenue by Region” | Exploratory visual; audience is technical |
| **Insight statement** | “West Region Revenue Fell 18% in Q4” | Explanatory visual; you know the story |
| **Question** | “Which Region Drove Q4 Decline?” | Inviting the viewer to find the answer you’ll reveal |

For Power BI custom visuals, the title is often set by the report designer in the Format pane — but the visual should visually reinforce the insight through its encoding (color, annotation) regardless of what title the user types.

When the visual is self-contained (e.g., a KPI card with no report-level title), embed the insight directly:

```typescript
// KPI title rendered inside the visual
this.svg.append(‘text’)
  .classed(‘insightTitle’, true)
  .attr(‘x’, width / 2).attr(‘y’, margin.top)
  .attr(‘text-anchor’, ‘middle’)
  .attr(‘font-size’, 13).attr(‘font-weight’, 500)
  .attr(‘fill’, ‘#6B7280’)
  .text(valueCol.source.displayName);   // e.g., “YTD Revenue”
```

—

## Annotations — The Storyteller’s Scalpel

Annotations are the single most powerful way to move a visual from “showing data” to “telling a story.” Use them sparingly — one per chart maximum in most cases.

```typescript
interface Annotation {
  value: number;
  label: string;
  xOffset?: number;
  yOffset?: number;
}

function addAnnotation(g: Selection<SVGGElement>, ann: Annotation, xScale: d3.ScaleBand<string>, yScale: d3.ScaleLinear<number, number>) {
  const cx = xScale(ann.label)! + xScale.bandwidth() / 2;
  const cy = yScale(ann.value);

  // Leader line
  g.append(‘line’)
    .attr(‘x1’, cx).attr(‘y1’, cy - 4)
    .attr(‘x2’, cx + (ann.xOffset ?? 20)).attr(‘y2’, cy + (ann.yOffset ?? -24))
    .attr(‘stroke’, ‘#9CA3AF’).attr(‘stroke-width’, 1);

  // Callout text
  g.append(‘text’)
    .attr(‘x’, cx + (ann.xOffset ?? 22)).attr(‘y’, cy + (ann.yOffset ?? -26))
    .attr(‘font-size’, 11).attr(‘fill’, ‘#374151’).attr(‘font-weight’, 500)
    .text(ann.label);
}
```

**When to annotate:**
- The maximum or minimum value in a series
- A significant inflection point (trend reversal)
- A target line or benchmark
- An outlier that needs explanation

**When NOT to annotate:**
- Every data point (this is labeling, not storytelling)
- To decorate rather than explain

—

## Reference Lines & Benchmarks

Reference lines add context that transforms raw values into meaningful comparisons:

```typescript
// Target / goal line
const targetValue = 1_000_000;

this.container.append(‘line’).classed(‘targetLine’, true)
  .attr(‘x1’, 0).attr(‘x2’, innerW)
  .attr(‘y1’, yScale(targetValue)).attr(‘y2’, yScale(targetValue))
  .attr(‘stroke’, ‘#F59E0B’)
  .attr(‘stroke-dasharray’, ‘6 3’)
  .attr(‘stroke-width’, 1.5);

this.container.append(‘text’).classed(‘targetLabel’, true)
  .attr(‘x’, innerW + 4).attr(‘y’, yScale(targetValue) + 4)
  .attr(‘font-size’, 10).attr(‘fill’, ‘#F59E0B’)
  .attr(‘font-weight’, 600)
  .text(‘Target’);

// Average line
const avg = d3.mean(data, d => d.value)!;
this.container.append(‘line’)
  .attr(‘x1’, 0).attr(‘x2’, innerW)
  .attr(‘y1’, yScale(avg)).attr(‘y2’, yScale(avg))
  .attr(‘stroke’, ‘#9CA3AF’).attr(‘stroke-dasharray’, ‘3 3’).attr(‘stroke-width’, 1);
```

—

## Color as a Communication Channel

Color is the most misused element in data visualization. Every color choice should answer: **what does this color mean?**

### The one-accent rule

Use a single accent color to mark the insight. Everything else should be neutral gray:

```typescript
const ACCENT   = ‘#3B82F6’;   // the story
const NEUTRAL  = ‘#D1D5DB’;   // the context
const POSITIVE = ‘#10B981’;   // above target / up
const NEGATIVE = ‘#EF4444’;   // below target / down
const TARGET   = ‘#F59E0B’;   // goal / benchmark

// Apply semantically:
bars.attr(‘fill’, d => {
  if (d.label === topPerformer) return ACCENT;
  if (d.value > targetValue)    return POSITIVE;
  if (d.value < targetValue)    return NEGATIVE;
  return NEUTRAL;
});
```

### Diverging vs. sequential vs. categorical

| Data type | Palette type | Example use |
|————|-————|-————|
| Sequential (low → high) | Single hue, light → dark | Revenue intensity, count, age |
| Diverging (negative → zero → positive) | Two hues meeting at neutral | Variance from target, profit/loss, YoY change |
| Categorical (unordered groups) | `host.colorPalette` (max 8 hues) | Product lines, regions, segments |

For diverging scales in D3:
```typescript
const colorScale = d3.scaleDiverging<string>()
  .domain([minVal, 0, maxVal])
  .interpolator(d3.interpolateRdYlGn);  // red → yellow → green
```

### Color accessibility

Always verify that your visual conveys meaning through more than color alone. Pair color with:
- Position (already present in most charts)
- Labels (direct annotation)
- Shape (for scatter plots)
- Pattern (for high-stakes accessibility needs)

Simulate deuteranopia (red-green colorblindness, affects ~8% of males) before releasing. Avoid red/green pairs without a secondary encoding.

—

## Number Formatting — The Last Inch of Storytelling

Humans cannot parse `$4,138,842.25` at a glance. They can parse `$4.1M` instantly.

```typescript
import { valueFormatter } from ‘powerbi-visuals-utils-formattingutils’;

// Smart auto-suffix formatter (K/M/B based on magnitude)
const formatter = valueFormatter.create({
  format: valueCol.source.format,
  value: d3.max(data, d => d.value),   // sets the suffix threshold
  precision: 1
});

// On data labels and tooltips:
const label = formatter.format(d.value);   // → “$4.1M”, “12.3K”, etc.
```

**Precision rules:**
- KPIs visible from across a room: 0 decimal places, use K/M/B suffix
- Bar chart labels: 1 decimal place maximum
- Tooltips (user has leaned in to read): full precision with original format
- Percentages: 1 decimal place for comparisons; 0 for round numbers

—

## Visual Hierarchy — Where the Eye Goes First

In Power BI dashboards, the report layout controls the macro Z-pattern (top-left = most important). Inside a single visual, you control the micro-hierarchy:

1. **Size** — the largest element is read first; use it for the primary metric
2. **Color** — high-contrast accent draws the eye; reserve it for the single most important element
3. **Position** — top and left edges are read first within an SVG frame
4. **Weight** — bold text reads before regular weight; use it for the KPI value, not the label

```typescript
// KPI card hierarchy: value first, label second, delta third
// Value — largest, boldest, primary color
this.svg.append(‘text’).attr(‘font-size’, 40).attr(‘font-weight’, 700).attr(‘fill’, ‘#111827’).text(mainValue);
// Label — smaller, muted
this.svg.append(‘text’).attr(‘font-size’, 12).attr(‘font-weight’, 400).attr(‘fill’, ‘#6B7280’).text(metricName);
// Delta — small, semantic color
this.svg.append(‘text’).attr(‘font-size’, 12).attr(‘font-weight’, 500).attr(‘fill’, delta >= 0 ? ‘#10B981’ : ‘#EF4444’).text(deltaLabel);
```

—

## Tooltips as a Secondary Storytelling Layer

Tooltips let you present full precision and additional context without cluttering the primary visual. Treat them as a second-level story:

```typescript
this.tooltipServiceWrapper.addTooltip(
  this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’),
  (d: DataPoint) => [
    // Primary metric (what they see)
    { displayName: categoryCol.source.displayName, value: d.label },
    { displayName: valueCol.source.displayName,    value: formatter.format(d.value) },
    // Secondary context (what the tooltip adds)
    { displayName: ‘% of Total’,  value: `${((d.value / totalValue) * 100).toFixed(1)}%` },
    { displayName: ‘vs. Target’,  value: `${d.value >= target ? ‘▲’ : ‘▼’} ${Math.abs(d.value - target).toFixed(0)}` },
    { displayName: ‘Rank’,        value: `#${d.rank} of ${data.length}` }
  ]
);
```

Keep tooltip entries ordered: most important first, supporting context below.

—

## The Empty State as Storytelling

A blank visual is a missed opportunity. Design the empty/no-data state with the same care as the data state:

```typescript
private renderEmptyState(width: number, height: number): void {
  this.container.selectAll(‘*’).remove();

  const g = this.svg.append(‘g’).classed(‘emptyState’, true);

  // Subtle illustration: 3 muted ghost bars
  [0.4, 0.7, 0.55].forEach((h, i) => {
    g.append(‘rect’)
      .attr(‘x’, width * 0.3 + i * (width * 0.12))
      .attr(‘y’, height * 0.5 - h * height * 0.25)
      .attr(‘width’, width * 0.08).attr(‘height’, h * height * 0.25)
      .attr(‘fill’, ‘#F3F4F6’).attr(‘rx’, 3);
  });

  g.append(‘text’)
    .attr(‘x’, width / 2).attr(‘y’, height * 0.65)
    .attr(‘text-anchor’, ‘middle’).attr(‘font-size’, 13)
    .attr(‘fill’, ‘#9CA3AF’).attr(‘font-weight’, 500)
    .text(‘Add a field to get started’);

  g.append(‘text’)
    .attr(‘x’, width / 2).attr(‘y’, height * 0.65 + 18)
    .attr(‘text-anchor’, ‘middle’).attr(‘font-size’, 11)
    .attr(‘fill’, ‘#D1D5DB’)
    .text(‘Drag a category and a measure into the Fields pane’);
}
```

—

## The Storytelling Checklist (Run Before Packaging)

Answer each question before shipping:

**Clarity**
- [ ] What is the single most important insight this visual communicates?
- [ ] Can a first-time viewer identify that insight in under 5 seconds?
- [ ] Is there anything in the visual that doesn’t serve that insight?

**Pre-attentive encoding**
- [ ] Have I used color intentionally — does the accent mark the insight?
- [ ] Is position the primary encoding for quantitative comparison?
- [ ] Am I using more than 2 pre-attentive attributes to carry meaning?

**Declutter**
- [ ] Are gridlines minimal, horizontal only, and light?
- [ ] Is the chart border removed?
- [ ] Are axis labels non-redundant with the title?
- [ ] Is the legend replaced with direct labels where possible?
- [ ] Are numbers formatted with appropriate precision and suffixes?

**Accessibility**
- [ ] Does the visual still communicate meaning without color (e.g., in grayscale)?
- [ ] Is text contrast ≥ 4.5:1 against the background?
- [ ] Are all SVG elements labeled for screen readers?

**Interaction**
- [ ] Does cross-filtering correctly dim non-selected elements?
- [ ] Do tooltips add meaningful secondary context, not just repeat the axis?
- [ ] Is the empty state designed, not blank?