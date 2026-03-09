# Boilerplate Templates

## Full visual.ts (Categorical, D3 Bar Chart)

```typescript
‘use strict’;

import powerbi from ‘powerbi-visuals-api’;
import VisualConstructorOptions = powerbi.extensibility.visual.VisualConstructorOptions;
import VisualUpdateOptions     = powerbi.extensibility.visual.VisualUpdateOptions;
import IVisual                 = powerbi.extensibility.visual.IVisual;
import IVisualHost             = powerbi.extensibility.visual.IVisualHost;
import ISelectionManager       = powerbi.extensibility.ISelectionManager;

import { FormattingSettingsService } from ‘powerbi-visuals-utils-formattingmodel’;
import { createTooltipServiceWrapper, ITooltipServiceWrapper } from ‘powerbi-visuals-utils-tooltiputils’;

import * as d3 from ‘d3’;
import { VisualFormattingSettingsModel } from ‘./settings’;

type Selection<T extends d3.BaseType> = d3.Selection<T, unknown, null, undefined>;

export class Visual implements IVisual {
  private host: IVisualHost;
  private svg: Selection<SVGSVGElement>;
  private container: Selection<SVGGElement>;
  private xAxis: Selection<SVGGElement>;
  private yAxis: Selection<SVGGElement>;

  private tooltipServiceWrapper: ITooltipServiceWrapper;
  private selectionManager: ISelectionManager;
  private formattingSettings: VisualFormattingSettingsModel;
  private formattingSettingsService: FormattingSettingsService;

  constructor(options: VisualConstructorOptions) {
    this.host = options.host;
    this.formattingSettingsService = new FormattingSettingsService();
    this.selectionManager = options.host.createSelectionManager();
    this.tooltipServiceWrapper = createTooltipServiceWrapper(
      options.host.tooltipService, options.element
    );

    // Build persistent DOM (never recreate in update)
    this.svg = d3.select(options.element)
      .append(‘svg’)
      .classed(‘myBarChart’, true)
      .style(‘overflow’, ‘hidden’);

    this.container = this.svg.append(‘g’).classed(‘container’, true);
    this.xAxis     = this.container.append(‘g’).classed(‘xAxis’, true);
    this.yAxis     = this.container.append(‘g’).classed(‘yAxis’, true);

    // Click on background clears selection
    this.svg.on(‘click’, () => {
      this.selectionManager.clear();
      this.container.selectAll(‘.bar’).style(‘opacity’, 1);
    });
  }

  public update(options: VisualUpdateOptions): void {
    // 1. Parse formatting settings
    this.formattingSettings = this.formattingSettingsService.populateFormattingSettingsModel(
      VisualFormattingSettingsModel,
      options.dataViews?.[0]
    );

    // 2. Guard: no data
    const dataView = options.dataViews?.[0];
    if (!dataView?.categorical?.categories?.length || !dataView.categorical.values?.length) {
      this.renderEmpty();
      return;
    }

    // 3. Parse data
    const categorical  = dataView.categorical;
    const categoryCol  = categorical.categories[0];
    const valueCol     = categorical.values[0];

    interface DataPoint {
      label: string;
      value: number;
      selectionId: powerbi.visuals.ISelectionId;
    }

    const data: DataPoint[] = categoryCol.values.map((cat, i) => ({
      label: String(cat ?? ‘’),
      value: (valueCol.values[i] as number) ?? 0,
      selectionId: this.host.createSelectionIdBuilder()
        .withCategory(categoryCol, i)
        .createSelectionId()
    }));

    // 4. Layout
    const { width, height } = options.viewport;
    const margin = { top: 24, right: 24, bottom: 48, left: 56 };
    const innerW = Math.max(0, width  - margin.left - margin.right);
    const innerH = Math.max(0, height - margin.top  - margin.bottom);

    this.svg.attr(‘width’, width).attr(‘height’, height);
    this.container.attr(‘transform’, `translate(${margin.left},${margin.top})`);

    // 5. Scales
    const settings = this.formattingSettings.colorCard;
    const barColor  = settings.fillColor.value.value;

    const xScale = d3.scaleBand()
      .domain(data.map(d => d.label))
      .range([0, innerW])
      .padding(0.25);

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.value) ?? 1])
      .nice()
      .range([innerH, 0]);

    // 6. Axes
    this.xAxis
      .attr(‘transform’, `translate(0,${innerH})`)
      .transition().duration(300)
      .call(d3.axisBottom(xScale).tickSizeOuter(0));

    this.yAxis
      .transition().duration(300)
      .call(d3.axisLeft(yScale).ticks(5).tickSizeOuter(0));

    // 7. Bars (enter/update/exit)
    const bars = this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’)
      .data(data, d => d.label);

    bars.enter()
      .append(‘rect’)
      .classed(‘bar’, true)
      .attr(‘x’, d => xScale(d.label)!)
      .attr(‘y’, innerH)
      .attr(‘width’, xScale.bandwidth())
      .attr(‘height’, 0)
      .attr(‘rx’, 3)
      .attr(‘fill’, barColor)
      .on(‘click’, (event, d) => {
        event.stopPropagation();
        this.selectionManager.select(d.selectionId, event.ctrlKey || event.metaKey);
        this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’)
          .style(‘opacity’, b =>
            this.selectionManager.hasSelection()
              ? (b.selectionId === d.selectionId ? 1 : 0.35)
              : 1
          );
      })
      .merge(bars)
      .transition().duration(300)
        .attr(‘x’, d => xScale(d.label)!)
        .attr(‘y’, d => yScale(d.value))
        .attr(‘width’, xScale.bandwidth())
        .attr(‘height’, d => innerH - yScale(d.value))
        .attr(‘fill’, barColor);

    bars.exit().transition().duration(200)
      .attr(‘height’, 0).attr(‘y’, innerH).remove();

    // 8. Tooltips
    this.tooltipServiceWrapper.addTooltip(
      this.container.selectAll<SVGRectElement, DataPoint>(‘.bar’),
      (d: DataPoint) => [
        { displayName: categoryCol.source.displayName, value: d.label },
        { displayName: valueCol.source.displayName,    value: String(d.value) }
      ]
    );
  }

  private renderEmpty(): void {
    this.container.selectAll(‘*’).remove();
    this.svg.selectAll(‘.emptyState’).data([1])
      .join(‘text’)
        .classed(‘emptyState’, true)
        .attr(‘x’, ‘50%’).attr(‘y’, ‘50%’)
        .attr(‘text-anchor’, ‘middle’)
        .attr(‘dominant-baseline’, ‘middle’)
        .attr(‘fill’, ‘#999’)
        .attr(‘font-size’, 14)
        .text(‘Add data to get started’);
  }

  public getFormattingModel(): powerbi.visuals.FormattingModel {
    return this.formattingSettingsService.buildFormattingModel(this.formattingSettings);
  }

  public destroy(): void {
    // Remove event listeners if any were added imperatively
  }
}
```

—

## Full settings.ts

```typescript
‘use strict’;

import { formattingSettings } from ‘powerbi-visuals-utils-formattingmodel’;
import Card      = formattingSettings.SimpleCard;
import Model     = formattingSettings.Model;
import Slice     = formattingSettings.Slice;

// ── Color & Typography Card ────────────────────────────────────────────
class ColorCard extends Card {
  fillColor = new formattingSettings.ColorPicker({
    name: ‘fillColor’,
    displayName: ‘Bar color’,
    description: ‘Primary color for data bars’,
    value: { value: ‘#4F8EF7’ }
  });

  hoverColor = new formattingSettings.ColorPicker({
    name: ‘hoverColor’,
    displayName: ‘Hover color’,
    value: { value: ‘#2563EB’ }
  });

  fontSize = new formattingSettings.NumUpDown({
    name: ‘fontSize’,
    displayName: ‘Label font size’,
    value: 12, options: { minValue: { value: 8, type: powerbi.visuals.ValidatorType.Min },
                          maxValue: { value: 32, type: powerbi.visuals.ValidatorType.Max } }
  });

  showDataLabels = new formattingSettings.ToggleSwitch({
    name: ‘showDataLabels’,
    displayName: ‘Show data labels’,
    value: false
  });

  name        = ‘colorSettings’;
  displayName = ‘Colors & Typography’;
  slices: Slice[] = [this.fillColor, this.hoverColor, this.fontSize, this.showDataLabels];
}

// ── Axis Card ──────────────────────────────────────────────────────────
class AxisCard extends Card {
  showXAxis = new formattingSettings.ToggleSwitch({
    name: ‘showXAxis’, displayName: ‘Show X axis’, value: true
  });
  showYAxis = new formattingSettings.ToggleSwitch({
    name: ‘showYAxis’, displayName: ‘Show Y axis’, value: true
  });
  gridLines = new formattingSettings.ToggleSwitch({
    name: ‘gridLines’, displayName: ‘Show grid lines’, value: true
  });

  name        = ‘axisSettings’;
  displayName = ‘Axes’;
  slices: Slice[] = [this.showXAxis, this.showYAxis, this.gridLines];
}

// ── Model ──────────────────────────────────────────────────────────────
export class VisualFormattingSettingsModel extends Model {
  colorCard = new ColorCard();
  axisCard  = new AxisCard();
  cards     = [this.colorCard, this.axisCard];
}
```

—

## Matrix Data View Mapping (capabilities.json)

Use for pivot-table style visuals or when you need row/column groupings:

```json
{
  “dataRoles”: [
    { “name”: “rows”,    “kind”: “Grouping”, “displayName”: “Rows” },
    { “name”: “columns”, “kind”: “Grouping”, “displayName”: “Columns” },
    { “name”: “values”,  “kind”: “Measure”,  “displayName”: “Values” }
  ],
  “dataViewMappings”: [{
    “matrix”: {
      “rows”:    { “for”: { “in”: “rows” },    “dataReductionAlgorithm”: { “top”: { “count”: 1000 } } },
      “columns”: { “for”: { “in”: “columns” }, “dataReductionAlgorithm”: { “top”: { “count”: 100 } } },
      “values”:  { “select”: [{ “bind”: { “to”: “values” } }] }
    }
  }]
}
```

Parsing matrix in `update()`:
```typescript
const matrix = dataView.matrix;
// matrix.rows.root  — tree of row headers
// matrix.columns.root — tree of column headers
// matrix.rows.root.children[i].values[measureIndex].value — cell value
```

—

## pbiviz.json Notes

After `pbiviz new`, update these fields before packaging:
```json
{
  “visual”: {
    “name”:        “MyVisualName”,
    “displayName”: “My Visual Display Name”,
    “guid”:        “myVisualName_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX”,
    “visualClassName”: “Visual”,
    “version”:     “1.0.0”,
    “description”: “A description of what this visual does”,
    “supportUrl”:  “https://example.com/support”,
    “gitHubUrl”:   “”
  },
  “apiVersion”: “5.3.0”,
  “author”: { “name”: “Your Name”, “email”: “you@example.com” },
  “assets”: { “icon”: “assets/icon.png” }
}
```

The GUID must be unique. Generate one at https://www.uuidgenerator.net/ or via `node -e “const {v4}=require(‘uuid’); console.log(v4())”`.