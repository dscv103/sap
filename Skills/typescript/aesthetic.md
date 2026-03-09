# Design System & Aesthetics

Power BI visuals exist inside a host application with its own theme, dark mode, and design language. The goal is to feel native to the report while still having a distinctive, polished character.

—

## Core Design Philosophy

1. **Theme-aware first** — always adapt to the host’s color palette and background
2. **Purposeful motion** — transitions communicate data change, not decoration
3. **Typographic precision** — hierarchy through weight and size, not color alone
4. **Breathing room** — generous margins; data never touches the edge
5. **Empty state grace** — blank/no-data states are designed moments, not voids

—

## Color Strategy

### Always Use the Host Palette for Data Colors
```typescript
// In update():
const palette = this.host.colorPalette;
data.forEach((d, i) => {
  d.color = palette.getColor(d.label).value;
  // Power BI handles dark/light theme switching automatically
});
```

### Semantic Color Tokens (LESS variables)
```less
// style/visual.less

// Never hardcode these — derive from host when possible
// Use as fallbacks only
@color-accent-blue:   #4F8EF7;
@color-accent-teal:   #0D9488;
@color-accent-violet: #7C3AED;
@color-neutral-900:   #111827;
@color-neutral-500:   #6B7280;
@color-neutral-200:   #E5E7EB;
@color-neutral-50:    #F9FAFB;

// Alert/status colors
@color-positive: #10B981;
@color-warning:  #F59E0B;
@color-negative: #EF4444;
```

### Curated Modern Palettes (for override / custom color modes)
```typescript
const PALETTES = {
  ocean:    [‘#0EA5E9’, ‘#06B6D4’, ‘#0891B2’, ‘#0E7490’, ‘#155E75’],
  sunset:   [‘#F97316’, ‘#EF4444’, ‘#EC4899’, ‘#A855F7’, ‘#8B5CF6’],
  forest:   [‘#22C55E’, ‘#16A34A’, ‘#15803D’, ‘#166534’, ‘#4ADE80’],
  corporate: [‘#3B82F6’, ‘#6366F1’, ‘#8B5CF6’, ‘#EC4899’, ‘#14B8A6’],
  neutral:  [‘#374151’, ‘#4B5563’, ‘#6B7280’, ‘#9CA3AF’, ‘#D1D5DB’],
};
```

—

## Typography

Power BI renders inside a sandboxed iframe. Use system/web-safe fonts or embed a font.

### Recommended Font Stack
```less
@font-body:    ‘Segoe UI’, -apple-system, BlinkMacSystemFont, ‘Helvetica Neue’, sans-serif;
@font-mono:    ‘Cascadia Code’, ‘SF Mono’, ‘Consolas’, monospace;

// For visuals where you control the full viewport:
@font-display: ‘Segoe UI Semibold’, ‘Helvetica Neue’, sans-serif;
```

### Type Scale
```less
@text-xs:   10px;
@text-sm:   12px;
@text-base: 14px;
@text-lg:   16px;
@text-xl:   20px;
@text-2xl:  24px;
@text-3xl:  32px;
@font-weight-normal: 400;
@font-weight-medium: 500;
@font-weight-bold:   700;
```

### D3 Text Styling
```typescript
g.append(‘text’)
  .attr(‘font-family’, “’Segoe UI’, system-ui, sans-serif”)
  .attr(‘font-size’, 12)
  .attr(‘font-weight’, 500)
  .attr(‘fill’, ‘#374151’)
  .attr(‘letter-spacing’, ‘0.01em’);
```

—

## Animation & Motion

### Transition Timing
| Use case | Duration | Easing |
|-———|-———|———|
| Data update (bars, lines) | 400ms | `d3.easeCubicOut` |
| Tooltip appear | 150ms | `d3.easeLinear` |
| Layout change (resize) | 0ms | — (instant) |
| Hover state | 150ms | `d3.easeLinear` |
| Enter animation | 600ms | `d3.easeElasticOut.amplitude(0.8)` |

```typescript
// Standard update transition
const t = d3.transition().duration(400).ease(d3.easeCubicOut);

bars.transition(t)
  .attr(‘y’, d => y(d.value))
  .attr(‘height’, d => innerH - y(d.value));
```

### Staggered Entry (KPI cards, small multiples)
```typescript
cards.enter().append(‘g’)
  .style(‘opacity’, 0)
  .transition().delay((_, i) => i * 60).duration(400)
    .style(‘opacity’, 1);
```

### Resize: Skip Animation
```typescript
public update(options: VisualUpdateOptions): void {
  const isResizing = options.type === powerbi.VisualUpdateType.Resize;
  const duration   = isResizing ? 0 : 400;
  const t = d3.transition().duration(duration);
  // ...
}
```

—

## LESS Patterns

```less
// style/visual.less

// All selectors MUST be scoped under your root class
.myBarChart {
  font-family: ‘Segoe UI’, system-ui, sans-serif;
  overflow: hidden;

  // Axis styling
  .xAxis, .yAxis {
    .domain { stroke: @color-neutral-200; }
    .tick line { stroke: @color-neutral-200; }
    .tick text {
      fill: @color-neutral-500;
      font-size: @text-sm;
    }
  }

  // Grid lines
  .gridLine {
    stroke: @color-neutral-200;
    stroke-dasharray: 3 4;
    stroke-width: 1;
  }

  // Bar hover state (controlled via JS, but baseline)
  .bar {
    cursor: pointer;
    transition: opacity 150ms ease;
    &:hover { filter: brightness(1.1); }
  }

  // Data labels
  .dataLabel {
    fill: @color-neutral-500;
    font-size: @text-xs;
    font-weight: @font-weight-medium;
    pointer-events: none;
    user-select: none;
  }

  // Empty state
  .emptyState {
    fill: @color-neutral-500;
    font-size: @text-base;
    font-weight: @font-weight-normal;
  }

  // KPI value (for KPI card visuals)
  .kpiValue {
    fill: @color-neutral-900;
    font-size: @text-3xl;
    font-weight: @font-weight-bold;
    letter-spacing: -0.02em;
  }

  // Trend badge
  .trendPositive { fill: @color-positive; }
  .trendNegative { fill: @color-negative; }
}
```

—

## Dark Mode

Power BI passes theme information through the host. The visual must adapt.

```typescript
// Detect dark mode via background luminance
private isDarkMode(): boolean {
  const bg = this.host.colorPalette.background?.value ?? ‘#FFFFFF’;
  // Parse hex and compute relative luminance
  const r = parseInt(bg.slice(1, 3), 16) / 255;
  const g = parseInt(bg.slice(3, 5), 16) / 255;
  const b = parseInt(bg.slice(5, 7), 16) / 255;
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance < 0.5;
}

// Then in update():
const dark       = this.isDarkMode();
const textColor  = dark ? ‘#D1D5DB’ : ‘#374151’;
const gridColor  = dark ? ‘#374151’ : ‘#E5E7EB’;
const axisColor  = dark ? ‘#4B5563’ : ‘#D1D5DB’;
```

—

## Common Visual Archetypes

### KPI Card
- Large numeric value (32–48px, bold)
- Subtitle label (12px, muted)
- Trend indicator (up/down arrow with green/red coloring)
- Sparkline (optional)
- Comparison delta (e.g., “+12.3% vs LY”)

### Bar / Column Chart
- Rounded top corners (`rx=3` or `border-radius: 3px 3px 0 0`)
- Hover brightens bar slightly
- Gridlines: horizontal only, dashed, very subtle
- X-axis labels: rotate 45° if > 8 categories
- Optional data labels above bars (toggle via formatting pane)

### Line Chart
- Path with `stroke-width: 2.5`, no fill unless area chart
- Dots on data points: `r=4`, filled, stroke-white outline `r=6`
- Hover: show dot + tooltip
- Gradient fill for area: use `<linearGradient>` with 40% → 0% opacity

### Scatter Plot
- Circle `r=6`, 70% opacity to handle overplotting
- Jitter optional for categorical x-axis
- Reference lines: dashed, muted color

—

## Accessibility

```typescript
// ARIA labels on SVG elements
this.svg
  .attr(‘role’, ‘img’)
  .attr(‘aria-label’, `Bar chart showing ${categoryCol.source.displayName}`);

// Tab-focusable bars for keyboard navigation
bars.attr(‘tabindex’, 0)
  .attr(‘role’, ‘graphics-symbol’)
  .attr(‘aria-label’, d => `${d.label}: ${d.value}`);
```

Use `host.colorPalette` — it is already designed to be accessible. Avoid encoding meaning in color alone; pair with shape or pattern.

—

## Icon Design (assets/icon.png)

- **Size**: 20×20 pixels (PNG)
- **Style**: Flat, single-color or two-tone (avoid gradients, they look muddy at small size)
- **Background**: Transparent
- The icon appears in the Power BI Visualizations pane

Quick icon with Node + `canvas`:
```bash
npm install canvas
node -e “
const { createCanvas } = require(‘canvas’);
const fs = require(‘fs’);
const c = createCanvas(20, 20);
const ctx = c.getContext(‘2d’);
ctx.fillStyle = ‘#4F8EF7’;
// Draw bar chart icon
[[2,14,4,6],[7,10,4,10],[13,6,4,14]].forEach(([x,y,w,h]) => ctx.fillRect(x,y,w,h));
fs.writeFileSync(‘assets/icon.png’, c.toBuffer(‘image/png’));
“
```