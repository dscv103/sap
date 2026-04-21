D3 fits **below React and beside Pico/Inter**—not instead of them. In a Power BI React visual, a clean mental model is:

1.  **Power BI host + visual API** supplies data, viewport size, selection/filter services, and formatting settings. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/visual-project-structure), [\[kennison.name\]](https://kennison.name/files/css/pico/docs/)
2.  **React** owns the component tree, lifecycle, and state updates from `update(...)`. Microsoft’s tutorial wires React into `visual.ts` exactly this way. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)
3.  **D3 (or another rendering library)** handles the **chart drawing and interaction math** inside a specific React component when you need custom marks, scales, axes, layouts, or transitions. Microsoft explicitly documents adding D3 as an external library with npm and importing it into the visual code. [\[picocss.com\]](https://picocss.com/docs)
4.  **Pico CSS + Inter** handle the **look of the non-chart UI**—typography, cards, labels, forms, panels, and general layout. Pico is CSS-only and Fontsource packages fonts for local bundling. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[npmjs.com\]](https://www.npmjs.com/package/powerbi-client-react), [\[bryntum.com\]](https://bryntum.com/blog/using-a-react-bryntum-gantt-as-a-custom-power-bi-visual/)

## Where D3 fits in practice

Think of D3 as the **drawing engine** for the part of the visual that Power BI does not give you out of the box. You would usually use it for:

*   scales, axes, and shapes in **SVG**, [\[picocss.com\]](https://picocss.com/docs)
*   layout math for more complex visuals, and [\[picocss.com\]](https://picocss.com/docs)
*   transitions or custom interactions inside the rendered chart area. [\[picocss.com\]](https://picocss.com/docs)

In other words:

*   **React** decides **what** to render and when to rerender. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)
*   **D3** decides **how** the chart geometry is computed and drawn. [\[picocss.com\]](https://picocss.com/docs)
*   **Pico/Inter** decide **how the chrome around the chart looks**—titles, metric labels, controls, tables, and typography. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[npmjs.com\]](https://www.npmjs.com/package/powerbi-client-react)

## A good division of labor

Here is the stack I’d recommend for most modern Power BI React visuals:

### `visual.ts`

Use this as the **Power BI adapter**. It should:

*   receive `dataViews`, `viewport`, and formatting settings from Power BI, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[kennison.name\]](https://kennison.name/files/css/pico/docs/)
*   parse or map those into a clean props object, and [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[github.com\]](https://github.com/necolas/normalize.css/)
*   hand those props to your root React component. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)

### React components

Use React for:

*   composition of panels, headers, legends, toolbars, and chart containers, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)
*   state that comes from Power BI updates or UI toggles, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)
*   conditional rendering and layout. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)

### D3

Use D3 **inside one component**—for example `Chart.tsx`—to render:

*   bars, lines, nodes, links, Sankey paths, custom KPI gauges, or other bespoke geometry. Microsoft’s external-library guidance uses D3 as the example JavaScript library for visuals. [\[picocss.com\]](https://picocss.com/docs)

### Pico + Inter

Use them for:

*   readable typography, form controls, cards, and semantic HTML defaults, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/import-visual), [\[bryntum.com\]](https://bryntum.com/blog/using-a-react-bryntum-gantt-as-a-custom-power-bi-visual/)
*   the settings or narrative portion of the visual, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/import-visual)
*   not the chart math itself. Pico is a CSS framework, not a charting engine. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual)

## What “other libraries” fit where

If you do not want to hand-code everything in D3, the other libraries usually fall into one of these slots:

### 1. **Power BI utility packages**

These fit **between `visual.ts` and your components**. They help with parsing and host integration. Microsoft documents utility packages for:

*   **Data view parsing** with `powerbi-visuals-utils-dataviewutils`, [\[github.com\]](https://github.com/necolas/normalize.css/)
*   **SVG helpers** with `powerbi-visuals-utils-svgutils`, and [\[necolas.github.io\]](https://necolas.github.io/normalize.css/)
*   **type/number helpers** with `powerbi-visuals-utils-typeutils`. [\[github.com\]](https://github.com/sindresorhus/modern-normalize/blob/main/readme.md)

These are especially useful when D3 is in the mix, because they reduce the “Power BI plumbing” around your chart code. [\[github.com\]](https://github.com/necolas/normalize.css/), [\[necolas.github.io\]](https://necolas.github.io/normalize.css/)

### 2. **Interactivity helpers**

These fit where your visual needs **cross-selection and filtering behavior**. Microsoft documents `powerbi-visuals-utils-interactivityutils` for implementing selection behavior in custom visuals.

If your chart supports clicking bars, points, or nodes and you want those clicks to interact with the report, this belongs **alongside your D3/React chart layer**, not in your typography layer. [\[kennison.name\]](https://kennison.name/files/css/pico/docs/)

### 3. **CSS frameworks and tokens**

These fit in **`visual.less`** or your imported stylesheet flow. Microsoft documents importing external CSS frameworks into the visual’s `.less` file.

That is where Pico, Bootstrap, Bulma, Fontsource CSS imports, and design-token libraries belong. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/visual-api), [\[npmjs.com\]](https://www.npmjs.com/package/powerbi-client-react)

## The simplest architecture that scales

If I were building your stack, I’d structure it like this:

```text
Power BI host
  -> visual.ts
      -> map dataViews + viewport + formatting into props
      -> React root
          -> Header / KPI / Controls (Pico + Inter)
          -> Chart component (D3)
          -> Footer / Notes / Legend (Pico + Inter)
```

That split works because Microsoft’s React tutorial already establishes React as the visual shell, while Microsoft’s external-library guidance explicitly supports bringing in D3 for rendering logic. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[picocss.com\]](https://picocss.com/docs)

## When to use D3 vs. when not to

Use **D3** when:

*   the chart is custom or unusual, [\[picocss.com\]](https://picocss.com/docs)
*   you need precise control over scales, paths, and animation, [\[picocss.com\]](https://picocss.com/docs)
*   you want SVG-level control. [\[necolas.github.io\]](https://necolas.github.io/normalize.css/), [\[picocss.com\]](https://picocss.com/docs)

Do **not** reach for D3 first when:

*   the visual is mostly **cards, text, forms, or narrative UI**, because Pico/React alone are enough there, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified)
*   the chart is simple and can be rendered with plain React and CSS, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual)
*   the complexity comes from **Power BI host integration**, in which case the utility and interactivity packages matter more than D3. [\[github.com\]](https://github.com/necolas/normalize.css/)

## One important constraint

Any library you add should still follow Power BI’s packaging and certification model:

*   install via **npm/yarn**, bundle locally, and import into the project,
*   if certification matters, stick to **public, reviewable OSS** and avoid runtime access to external services or resources. Microsoft’s certification guidance is explicit about that. [\[copilothub.directory\]](https://copilothub.directory/instructions/power-bi-custom-visuals-development-best-practices)

## My blunt recommendation

For your **Pico + Inter** starter stack:

*   keep **Pico + Inter** as the **presentation layer**, [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual), [\[npmjs.com\]](https://www.npmjs.com/package/powerbi-client-react), [\[bryntum.com\]](https://bryntum.com/blog/using-a-react-bryntum-gantt-as-a-custom-power-bi-visual/)
*   add **D3 only in the chart component**, [\[picocss.com\]](https://picocss.com/docs)
*   use **Power BI utility packages** for parsing and SVG helpers, [\[github.com\]](https://github.com/necolas/normalize.css/), [\[necolas.github.io\]](https://necolas.github.io/normalize.css/)
*   use **interactivity utils** when you need selection behavior that talks back to Power BI.

That gives you a clean separation: **Power BI host plumbing -> React shell -> D3 chart -> Pico/Inter styling**. [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/power-bi-custom-visuals-certified), [\[picocss.com\]](https://picocss.com/docs), [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/power-bi/developer/visuals/create-react-visual)

If you want, I can sketch the **actual file layout** next—`visual.ts`, `Root.tsx`, `Chart.tsx`, and `visual.less`—showing exactly where D3 code lives inside the Pico + Inter starter stack.
