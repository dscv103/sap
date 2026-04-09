## Copilot instructions

- Write **complete, runnable output**. State assumptions first. If schema, inputs, or business rules are missing, ask only for what is required. Omit filler. Prefer clear names and small functions.

- **Python**
  - Target **Python 3.13**.
  - Use modern type syntax: `list[str]`, `dict[str, int]`, and `A | B`.
  - Type all public functions and methods.
  - For parameters, prefer abstract types such as `Sequence`, `Mapping`, and `Iterable`. For return values, prefer concrete types such as `list` and `dict`.
  - Use `object` instead of `Any` unless a value is truly unconstrained.
  - Use f-strings, `pathlib`, context managers, and `dataclasses` when they simplify the code.
  - Prefer the standard library. Add a package only when it clearly improves the result.

- **Python packaging**
  - Put project metadata and dependencies in `pyproject.toml`.
  - Include both `[build-system]` and `[project]`.
  - Use **Hatchling** for builds.
  - Use **uv** to create the environment, add dependencies, and maintain `uv.lock`.
  - Keep runtime dependencies in `[project.dependencies]`. Keep optional features in `[project.optional-dependencies]`.
  - Set `requires-python = ">=3.13"`.
  - Do not use `setup.py` unless code-based build logic is required.

- **SQL Server**
  - Target **SQL Server 2016 (13.x)** syntax and behavior.
  - Write **read-only** T-SQL only.
  - Use `SELECT`, CTEs, window functions, and views when needed.
  - Do **not** emit `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, `CREATE`, `ALTER`, `DROP`, or permission changes unless the prompt explicitly asks for administration.
  - Qualify objects with schema names. Avoid `SELECT *`. Use parameters, not string-built SQL.
  - Assume least privilege. For broad read access, prefer `db_datareader`. For narrower access, prefer `GRANT SELECT` on the needed schema or object.
  - If row filtering is required, prefer **Row-Level Security**.

- **DAX for Power BI Desktop**
  - Prefer **explicit measures** over implicit aggregation.
  - Write measures that respond to filter context.
  - Use `VAR ... RETURN` to reduce repetition and improve readability.
  - Use `DIVIDE()` when the denominator may be zero or `BLANK()`. Prefer returning `BLANK()` unless the business rule requires another result.
  - Use `CALCULATE` to change filter context. Use iterators only when a simple aggregation will not do.
  - Use clear measure names. Fully qualify columns as `Table[Column]`. Do not qualify measures as `Table[Measure]`.

- **C# for Tabular Editor 3**
  - Write safe, reviewable scripts.
  - Check `Selected` and object existence before changing anything.
  - Prefer small, idempotent scripts. Make bulk edits only when the rule is clear.
  - Preserve names, descriptions, display folders, and format strings unless the prompt says otherwise.
  - Use the **Best Practice Analyzer** first. If a rule has an easy fix, prefer the generated fix script or apply-fix workflow.
  - Save reusable scripts as macros or custom actions.
  - Do not run untrusted scripts. Tabular Editor scripts can use the full .NET platform.

- **Reflection**
  - If you generated code, reflect before finalizing.
  - Use this exact pattern:

    Here's code intended for task X:
    [previously generated code]

    Check the code carefully for correctness, style, and efficiency, and give constructive criticism for how to improve it. Then take the constructive feedback and output the improved code.

  - Review correctness, edge cases, clarity, naming, type safety, performance, maintainability, and unnecessary dependencies.
  - Fix issues you find.
  - Return the improved code, not just the critique.
  - Keep the final result complete and runnable.
  - Do not invent missing requirements. If a critical input is missing, ask only for that input.

- **Output contract**
  - Return, in this order:
    1. Files to create or change.
    2. Code.
    3. Required packages or commands.
    4. Test steps.
    5. A brief rationale.
  - If multiple valid options exist, choose the one that is simplest, safest, and easiest to maintain.

- **Style**
  - Omit needless words.
  - Prefer the active voice.
  - Make every line serve the task.
  - When uncertain, say so plainly.
