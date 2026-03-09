# Package Recipes

## Package Selection Guide

| Need | Package | Notes |
|——|———|-——|
| General charts (bar, line, scatter, area) | `d3` | Most flexible; steep learning curve |
| Rich chart library, minimal code | `echarts` | Apache ECharts; excellent dark mode |
| Declarative grammar-of-graphics | `vega-lite` | Great for exploration; large bundle |
| Lightweight charts | `chart.js` | Simpler API; less control |
| Network graphs | `d3` + `d3-force` | Best option for this use case |
| Geo/maps | `d3-geo` + TopoJSON | Built into D3 |
| Statistical plots | `@observablehq/plot` | Modern, terse API |
| Tooltips | `powerbi-visuals-utils-tooltiputils` | Required for native PBI tooltip experience |
| Cross-filtering / selection | `powerbi-visuals-utils-interactivityutils` | Or use `ISelectionManager` directly |
| Axes, legend, labels | `powerbi-visuals-utils-chartutils` | Wraps D3 axis with PBI formatting |
| Color palette | `powerbi-visuals-utils-colorutils` | Respects host theme |
| Data view access helpers | `powerbi-visuals-utils-dataviewutils` | `DataViewObjects.getValue()` etc. |
| Number/date formatting | `powerbi-visuals-utils-formattingutils` | `valueFormatter.format()` |

—

## D3 Integration

### Install
```bash
npm install d3 @types/d3
```

### Import (tree-shakeable in v7+)
```typescript
import * as d3 from ‘d3’;
// Or selective:
import { select, scaleLinear, axisBottom, transition } from ‘d3’;
```

### Key Patterns

**Smooth enter/update/exit:**
```typescript
const bars = g.selectAll<SVGRectElement, Datum>(‘.bar’).data(data, d => d.id);

const entered = bars.enter().append(‘rect’).classed(‘bar’, true)
  .attr(‘y’, innerH).attr(‘height’, 0); // start from bottom

entered.merge(bars)
  .transition().duration(400).ease(d3.easeCubicOut)
  .attr(‘x’, d => x(d.category)!)
  .attr(‘y’, d => y(d.value))
  .attr(‘height’, d => innerH - y(d.value))
  .attr(‘width’, x.bandwidth());

bars.exit().transition().duration(200).attr(‘height’, 0).attr(‘y’, innerH).remove();
```

**Responsive text wrapping:**
```typescript
function wrapText(selection: d3.Selection<SVGTextElement, unknown, SVGGElement, unknown>, maxWidth: number) {
  selection.each(function () {
    const text   = d3.select(this);
    const words  = text.text().split(/\s+/).reverse();
    const lineHeight = 1.1;
    const x      = text.attr(‘x’);
    const y      = text.attr(‘y’);
    let word: string, line: string[] = [];
    let lineNum = 0;
    let tspan   = text.text(null).append(‘tspan’).attr(‘x’, x).attr(‘y’, y);
    while ((word = words.pop()!)) {
      line.push(word);
      tspan.text(line.join(‘ ‘));
      if ((tspan.node()!.getComputedTextLength()) > maxWidth && line.length > 1) {
        line.pop();
        tspan.text(line.join(‘ ‘));
        line = [word];
        tspan = text.append(‘tspan’)
          .attr(‘x’, x).attr(‘dy’, `${++lineNum * lineHeight}em`).text(word);
      }
    }
  });
}
```

—

## ECharts Integration

ECharts is excellent when you want rich, pre-built chart types with minimal boilerplate.

### Install
```bash
npm install echarts @types/echarts
```

### HTML-container pattern (preferred for ECharts in PBI)
```typescript
import * as echarts from ‘echarts’;

export class Visual implements IVisual {
  private chart: echarts.ECharts;

  constructor(options: VisualConstructorOptions) {
    const container = options.element as HTMLElement;
    container.style.overflow = ‘hidden’;
    this.chart = echarts.init(container, null, { renderer: ‘svg’ });
    // Use ‘svg’ renderer — it plays nicer with PBI’s sandbox
  }

  public update(options: VisualUpdateOptions): void {
    const { width, height } = options.viewport;
    this.chart.resize({ width, height });

    const data = /* parse dataViews */[];

    this.chart.setOption({
      backgroundColor: ‘transparent’,  // always transparent in PBI
      animation: true,
      animationDuration: 400,
      animationEasing: ‘cubicOut’,
      tooltip: { trigger: ‘axis’ },
      xAxis: { type: ‘category’, data: data.map(d => d.label) },
      yAxis: { type: ‘value’ },
      series: [{
        type: ‘bar’,
        data: data.map(d => d.value),
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }]
    }, /* notMerge = */ false);
  }

  public destroy(): void { this.chart.dispose(); }
}
```

**Note**: Native PBI tooltips (`ITooltipServiceWrapper`) won’t work with ECharts tooltips. Either use ECharts built-in tooltips OR replace them with PBI tooltips via `mouseover` events.

—

## Tooltip Utils

```bash
npm install powerbi-visuals-utils-tooltiputils
```

```typescript
import { createTooltipServiceWrapper, ITooltipServiceWrapper, TooltipEventArgs } from ‘powerbi-visuals-utils-tooltiputils’;

// In constructor:
this.tooltipServiceWrapper = createTooltipServiceWrapper(this.host.tooltipService, options.element);

// In update(), after rendering:
this.tooltipServiceWrapper.addTooltip(
  this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’),
  (eventArgs: TooltipEventArgs<DataPoint>) => {
    const d = eventArgs.data;
    return [
      { displayName: ‘Category’, value: d.label },
      { displayName: ‘Value’,    value: d.value.toLocaleString() }
    ];
  },
  (eventArgs: TooltipEventArgs<DataPoint>) => eventArgs.data.selectionId  // identity for report page tooltips
);
```

—

## Color Utils (Host Palette)

```bash
npm install powerbi-visuals-utils-colorutils
```

```typescript
import { ColorHelper } from ‘powerbi-visuals-utils-colorutils’;

// In update():
const colorHelper = new ColorHelper(
  this.host.colorPalette,
  { objectName: ‘colorSettings’, propertyName: ‘fillColor’ },
  ‘#4F8EF7’  // default
);

// Assign a palette color to each category (respects user customization):
data.forEach(d => {
  d.color = colorHelper.getColorForSeriesValue(
    categoryCol.objects?.[data.indexOf(d)] ?? {},
    d.label
  );
});
```

—

## Number Formatting

```bash
npm install powerbi-visuals-utils-formattingutils
```

```typescript
import { valueFormatter } from ‘powerbi-visuals-utils-formattingutils’;

const formatter = valueFormatter.create({
  format: valueCol.source.format,      // e.g. ‘$#,0.00’
  precision: 2,
  value: d3.max(data, d => d.value)    // drives auto-suffix (K, M, B)
});

const label = formatter.format(12345678); // → “$12.35M”
```

—

## Selection Manager (Cross-Filtering)

```typescript
// constructor
this.selectionManager = this.host.createSelectionManager();

// on click
element.on(‘click’, (event, d: DataPoint) => {
  event.stopPropagation();
  const multiSelect = event.ctrlKey || event.metaKey;
  this.selectionManager.select(d.selectionId, multiSelect);
  this.updateOpacity();
});

// background click to clear
this.svg.on(‘click’, () => {
  this.selectionManager.clear();
  this.updateOpacity();
});

private updateOpacity(): void {
  const selected = this.selectionManager.getSelectionIds();
  this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’)
    .style(‘opacity’, d =>
      selected.length === 0 || selected.some(id => id.equals(d.selectionId))
        ? 1 : 0.3
    );
}
```

—

## Vega-Lite Integration

Best when you want declarative specs and don’t need deep customization.

```bash
npm install vega vega-lite vega-embed
```

```typescript
import embed from ‘vega-embed’;

export class Visual implements IVisual {
  private container: HTMLElement;
  private view: any;

  constructor(options: VisualConstructorOptions) {
    this.container = options.element as HTMLElement;
  }

  public async update(options: VisualUpdateOptions): Promise<void> {
    const { width, height } = options.viewport;
    const data = /* parse dataViews */[];

    const spec = {
      $schema: ‘https://vega.github.io/schema/vega-lite/v5.json’,
      width, height: height - 40,
      background: ‘transparent’,
      data: { values: data },
      mark: { type: ‘bar’, cornerRadiusTopLeft: 4, cornerRadiusTopRight: 4 },
      encoding: {
        x: { field: ‘label’, type: ‘ordinal’ },
        y: { field: ‘value’, type: ‘quantitative’ },
        color: { value: ‘#4F8EF7’ }
      }
    };

    const result = await embed(this.container, spec as any, { actions: false });
    this.view = result.view;
  }

  public destroy(): void { this.view?.finalize(); }
}
```

**Caveat**: Vega bundle is ~1.5 MB. Check Power BI’s visual size limits (currently 4 MB uncompressed) if bundling Vega-Lite.