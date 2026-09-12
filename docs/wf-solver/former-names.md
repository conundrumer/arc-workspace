# Former names

On 2026-09-08, the solver vocabulary moved to conventional terms, in the docs, the tooling, lib.dl, and every solver at once. The Definitions section of principles.md defines the current terms.

## Terms

| Former | Current |
| --- | --- |
| body | program (of a solver) |
| body code, body style, body form | program style |
| Consts | parameters |
| slot | parameter |
| Consts shape | parameterization |
| fill (of a slot) | value (of a parameter) |
| fill (of a Consts shape) | assignment |
| refill | reassign |
| refillable | determinable |
| Fit | determination |
| Fit relation | determination relation |
| fitted slot | determined parameter |
| fit pass | determination pass |
| rival model | peer model |
| setup variant | reparameterization (of a setup) |
| settled form | precedent |
| decision point | choice point |
| answer (of a choice point) | branch |
| claim | hypothesis |
| reading | parse |
| data-leaning, ops-leaning | table, rule |
| data case, data peer | stored case, table peer |

NB: reparameterization has been dropped; Same model decides whether an encoding is a peer

## Code and commands

| Former | Current |
| --- | --- |
| `.comp Consts` | `.comp Params` |
| `.init c = Consts`, `c.<rel>` | `.init params = Params`, `params.<rel>` |
| `ConstsHelpers` | `ParamsHelpers` |
| `.comp Fit` | `.comp Determine` |
| `// --- fit ---` | `// --- determination ---` |
| `fit_diff` | `_determination_diff` |
| `fit`, the pass keyword | `determine` |
| `fit-plan` | `determination-plan` |
| fit mode, the runner's | determination mode |
| fill sweep, in `sweep` and `audit` | parameter value sweep |
| `pinned`, the determination plan's verdict | `exact` |

## Headings in principles.md

| Former | Current |
| --- | --- |
| ARC values | ARC types |
| Derived vs stored | Stored or derived |
| Data vs ops | Table or rule |
| Concept vs setup | Prior or setup |

## Box (2026-09-11)

On 2026-09-11, the spatial record took its algebra's names, in lib.dl, the tooling, the docs, and every solver at once.

| Former | Current |
| --- | --- |
| `Position`, the record | `Box`; `Position` is its cell reading |
| `Shift` | `Offset` |
| `Inset` | `Box` |
| `ORIGIN` | `ZERO` |
| `displacement` | `relative` |
| `geq`, `gt` | `inside`, `interior` |
| `edge_delta`, `axis_delta`, `uniform_delta` | `edge_inset`, `axis_inset`, `uniform_inset` |
| `jump_delta`, `step_delta` | `jump_offset`, `step_offset` |
| `Bbox.margin`, `DirPack.pos`, `DrawnRect.rect` | `box` |
| `DrawnRect` | `Outlines` |
| `ShiftInvariance` | `OffsetInvariance` |
| `DividerFrame` | `DividerTiles` |
| `BoxCells`, `BoxFrame`, `MarginFrame`, `Reframe` | retired into `crop`, `box_edge`, `interior`, `relative`, and the constructors |

## Docs

| Former | Current |
| --- | --- |
| `cadence.md` | `procedure.md` |
| `concepts.md` | `keywords.md` |
| `shapes.md` | the Shape section of `keywords.md` |
