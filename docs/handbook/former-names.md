+ budget: 2300
* comment: when editing this doc
    - No tool reads this doc.
    - A row stays only while both conditions hold:
        - The former name is a current name with another referent, or a grep for it over the current docs and lib finds no line that gives its meaning. A name whose current form a grep finds, such as a prefixed one, earns no row.
        - The former name stands in text that a later session reads. That text is `docs/`, `prompts/roles/`, and `programs/`, together with reports and briefs. Grep verifies the repo part alone.

# Former names
- Each row gives the current name for a former one that a reader would otherwise take for something else or fail to find.

## Terms
+ xref: src/cli/survey.py:cmd_determination_plan, programs/lib/box.dl
| Former | Current |
| --- | --- |
| Fit, fit pass, fit-plan | determination, determination pass, `determination-plan` |
| rule (the Datalog sense) | clause |
| Draft (the procedure operation) | Write |
| concept rule | claim |
| lib primitive | lib relation |
| `Position`, the record | `Box`; `Position` is its cell role |
- Fit is the name of the case condition that [Cases](docs/handbook/principles.md#cases) states.
    + xref: docs/handbook/principles.md#cases

## Identifiers
+ xref: programs/lib/box.dl, programs/lib/cells.dl, programs/lib.dl, src/solver/annotations.py:DirectiveWord
| Former | Current |
| --- | --- |
| `Shift` | `Offset` |
| `Inset` | `Box` |
| `ORIGIN` | `ZERO` |
| `displacement` | `relative` |
| `geq`, `gt` | `inside`, `interior` |
| `edge_delta`, `axis_delta`, `uniform_delta` | `edge_inset`, `axis_inset`, `uniform_inset` |
| `jump_delta`, `step_delta` | `jump_offset`, `step_offset` |
| `Bbox.margin`, `DrawnRect.rect` | `box` |
| `DrawnRect` | `Outlines` |
| `ShiftInvariance` | `OffsetInvariance` |
| `DividerFrame` | `DividerTiles` |
| `BoxCells`, `BoxFrame`, `MarginFrame`, `Reframe` | the box algebra in `programs/lib/box.dl` |
| `// family:` | `// @representative:` |
| `percept-shadow` | `approximation` |
| `@unit` | `@singleton-axis` |
| `@deviation` | `@witness` |
| `@invariant` | `@scene` |
| `@addition` | a branch's `@scene` or `@rule` line under a new slug |
| `@rule` above an instance | `@claim` |
| `neither` (verdict) | `other` |
| `open` (verdict) | `any` |
