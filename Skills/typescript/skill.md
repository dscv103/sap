—
name: powerbi-custom-visual
description: Build production-ready Power BI Desktop custom visuals with modern aesthetics and best-practice TypeScript patterns. Use this skill whenever the user asks to create, scaffold, build, or improve a Power BI custom visual, pbiviz project, or `.pbiviz` package — including requests for charts, KPI cards, slicers, tables, or any visualization component for Power BI. Also trigger when the user mentions powerbi-visuals-tools, pbiviz CLI, capabilities.json, IVisual, data view mappings, or formatting pane integration. If the user says “Power BI visual”, “custom visual”, “pbiviz”, or wants to package a visual for Power BI Service or Desktop, use this skill without hesitation.
—

# Power BI Custom Visual Creator

This skill guides you through scaffolding, developing, and packaging production-quality Power BI custom visuals using modern TypeScript patterns, D3.js or ECharts, and polished aesthetic conventions.

> **Before rendering a single element**, read `references/storytelling.md`. It defines *why* every encoding choice matters — pre-attentive attributes, Gestalt principles, chart selection, clutter removal, and the pre-packaging checklist. The other references cover *how*.

Read `references/boilerplate.md` for full code templates, `references/packages.md` for library usage, and `references/aesthetics.md` for design patterns.

—

## Prerequisites & Setup

```bash
# One-time global install
npm install -g powerbi-visuals-tools

# Verify
pbiviz —version   # should be ≥ 5.x

# Enable Developer Visual in Power BI Desktop
# Settings → Security → Enable custom visual developer
```

Power BI API versions matter:
- **API 5.x** — current; use `FormattingModel` (declarative formatting pane)
- **API 4.x** — legacy; uses `enumerateObjectInstances`

Always target API 5.x for new visuals.

—

## Project Scaffold

```bash
pbiviz new MyVisualName
cd MyVisualName
npm install
```

Optional templates: `—template table`, `—template slicer`, `—template rhtml` (R-powered).

Install core utilities immediately:
```bash
npm install d3 @types/d3
npm install powerbi-visuals-utils-tooltiputils
npm install powerbi-visuals-utils-colorutils
npm install powerbi-visuals-utils-dataviewutils
npm install powerbi-visuals-utils-formattingutils
npm install powerbi-visuals-utils-interactivityutils  # if cross-filtering needed
npm install powerbi-visuals-utils-chartutils           # if axes/legend needed
```

—

## File Structure

```
MyVisualName/
├── pbiviz.json              ← metadata, GUID, version
├── capabilities.json        ← data roles, mappings, formatting objects
├── src/
│   ├── visual.ts            ← IVisual class (main logic)
│   ├── settings.ts          ← FormattingSettingsModel
│   └── formattingModels.ts  ← optional, for complex formatting groups
├── style/
│   └── visual.less          ← component styles (scoped to #sandbox-host)
├── assets/
│   └── icon.png             ← 20×20 PNG icon for the visuals pane
└── package.json
```

—

## capabilities.json Patterns

This file defines what data Power BI passes to your visual and what formatting properties appear in the pane.

**Categorical mapping** (most common — one category + one or more measures):
```json
{
  “dataRoles”: [
    { “name”: “category”, “kind”: “Grouping”, “displayName”: “Category” },
    { “name”: “measure”,  “kind”: “Measure”,  “displayName”: “Value” }
  ],
  “dataViewMappings”: [{
    “categorical”: {
      “categories”: { “for”: { “in”: “category” }, “dataReductionAlgorithm”: { “top”: { “count”: 30000 } } },
      “values”: { “select”: [{ “bind”: { “to”: “measure” } }] }
    }
  }]
}
```

**Matrix mapping** (for pivot / table visuals): see `references/boilerplate.md`.

**Objects** (formatting pane entries — API 5.x uses `FormattingModel` instead, but `capabilities.json` still needs `”objects”: {}`):
```json
“objects”: {
  “colorSettings”: {
    “properties”: {
      “fillColor”: { “type”: { “fill”: { “solid”: { “color”: true } } } },
      “fontSize”:  { “type”: { “formatting”: { “fontSize”: true } } }
    }
  }
}
```

—

## Core visual.ts Skeleton

See `references/boilerplate.md` for the full annotated template. Key structural rules:

1. **`constructor`** — create persistent DOM structure, set up services, initialize utilities. Do NOT render data here.
2. **`update`** — called on every data change, resize, or settings change. Parse `options.dataViews`, compute layout, render.
3. **`getFormattingModel`** — return `FormattingModel` from your settings service (API 5.x).
4. **`destroy`** — remove event listeners, clean up subscriptions.

```typescript
export class Visual implements IVisual {
  private host: IVisualHost;
  private svg: d3.Selection<SVGElement, unknown, null, undefined>;
  private formattingSettings: VisualFormattingSettingsModel;
  private formattingSettingsService: FormattingSettingsService;

  constructor(options: VisualConstructorOptions) {
    this.host = options.host;
    this.formattingSettingsService = new FormattingSettingsService();
    this.svg = d3.select(options.element).append(‘svg’).classed(‘myVisual’, true);
  }

  public update(options: VisualUpdateOptions): void {
    this.formattingSettings = this.formattingSettingsService.populateFormattingSettingsModel(
      VisualFormattingSettingsModel, options.dataViews[0]
    );
    const dataView = options.dataViews?.[0];
    if (!dataView?.categorical) return;
    // parse + render
  }

  public getFormattingModel(): powerbi.visuals.FormattingModel {
    return this.formattingSettingsService.buildFormattingModel(this.formattingSettings);
  }
}
```

—

## Data Parsing Pattern

```typescript
const categorical = dataView.categorical;
const categories  = categorical.categories[0];
const values      = categorical.values[0];

const data = categories.values.map((cat, i) => ({
  label: cat as string,
  value: values.values[i] as number,
  selectionId: this.host.createSelectionIdBuilder()
    .withCategory(categories, i)
    .createSelectionId()
}));
```

Always guard: `if (!dataView?.categorical?.categories?.length) { this.renderEmpty(); return; }`

—

## settings.ts (FormattingModel API 5.x)

```typescript
import { formattingSettings } from ‘powerbi-visuals-utils-formattingmodel’;
import Card = formattingSettings.SimpleCard;
import Model = formattingSettings.Model;

class ColorCard extends Card {
  fillColor = new formattingSettings.ColorPicker({
    name: ‘fillColor’, displayName: ‘Bar Color’,
    value: { value: ‘#4F8EF7’ }
  });
  fontSize = new formattingSettings.NumUpDown({
    name: ‘fontSize’, displayName: ‘Font Size’,
    value: 12
  });
  name = ‘colorSettings’;
  displayName = ‘Colors & Typography’;
  slices = [this.fillColor, this.fontSize];
}

export class VisualFormattingSettingsModel extends Model {
  colorCard = new ColorCard();
  cards = [this.colorCard];
}
```

—

## Viewport & Responsiveness

```typescript
const { width, height } = options.viewport;
this.svg.attr(‘width’, width).attr(‘height’, height);
const margin = { top: 20, right: 20, bottom: 40, left: 50 };
const innerW = width  - margin.left - margin.right;
const innerH = height - margin.top  - margin.bottom;
```

Always recompute layout from `options.viewport` on every `update()` call.

—

## Dev Server & Debugging

```bash
pbiviz start          # starts HTTPS dev server at localhost:8080
```

In Power BI Desktop: Insert → Developer visual. The visual live-reloads on save. Accept the self-signed cert in your browser first (`https://localhost:8080/assets/status`).

—

## Build & Package

```bash
pbiviz package        # outputs dist/MyVisualName.pbiviz
```

Import the `.pbiviz` file into Power BI Desktop via: Visualizations pane → `...` → Import a visual from a file.

For AppSource submission: run `pbiviz package —resources —no-minify —verbose` and follow Microsoft’s submission checklist.

—

## Design Principles

See `references/aesthetics.md` for the full design system. Short rules:

- **Respect the host theme** — use `this.host.colorPalette` for series colors; never hardcode palette colors
- **Smooth transitions** — every data update should `transition().duration(300)` in D3
- **Handle empty state** — show a styled “No data” placeholder, never a crash or blank void
- **Clip to viewport** — use `<clipPath>` in SVG or `overflow: hidden` in HTML visuals
- **Dark mode** — test in both light and dark Power BI themes

—

## Common Pitfalls

| Pitfall | Fix |
|———|——|
| Visual crashes on no data | Guard `dataViews?.[0]` at the top of `update()` |
| Tooltip flicker | Initialize `ITooltipServiceWrapper` once in constructor, not on every render |
| Old data visible after field removed | Clear SVG in `update()` before re-rendering, or use D3 `exit().remove()` |
| LESS styles bleeding out | All selectors must start with `.myVisual` (the class you put on your root element) |
| Packaging fails | Run `npm run build` first; ensure no TypeScript errors |
| Selection not working | Call `this.selectionManager.select(selectionId)` and re-render with highlighted state |

—

## Reference Files

- **`references/storytelling.md`** ← **Read this first for any new visual** — Pre-attentive attributes, Gestalt principles, data-ink ratio, chart selection guide, clutter checklist, annotation patterns, color semantics, number formatting, and the full pre-packaging storytelling checklist
- **`references/boilerplate.md`** — Full annotated `visual.ts` + `settings.ts` templates, matrix mapping pattern
- **`references/packages.md`** — D3, ECharts, Vega-Lite integration recipes; tooltip, selection, color utils usage
- **`references/aesthetics.md`** — Design system: color palettes, typography, animation, dark mode, LESS patterns