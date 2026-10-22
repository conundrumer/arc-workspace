# c7f57c3e

## Departures
- The witness that the Analyze file names `$FrameColorsByShape` is `body-color-5` in the solver and in `programs/witnesses/c7f57c3e.wit.json`: a `@witness` id must be a slug, and that branch is a constructor, not a `@derive` branch whose witness takes the branch's name.
- `$OddOneOut` has no constructor in the final solver, and the witness `two-figures-per-pattern` is removed, because it separated `$OddOneOut` alone. In the other two witnesses, `$OddOneOut` is removed from the groups, and the `body-color-5` separates text no longer names it. That case fails Subsumption, as the Analyze report gives (see Judgments).
- `pattern-colors-shared`: under `$FrameColorsByShape`, color 6 also has one shape on every figure (one center cell), so the body takes 2 and 6. The separates text says so. The verdict and the groups are as the Analyze file gives them.
- The model checks `scaled-copies-of-one-body`: where two figures' bodies differ (`body_mismatch`), the cells outside the figures and the body cells get no output, so every case is undefined there. Without this check, `$FrameColorsByShape` on `pattern-colors-shared` takes every figure color into the body, finds no decoration, and gives the input unchanged. The Analyze file gives undefined.

## Judgments
- Scale: a figure's scale is the largest block size at which every block of the figure's bounding box holds one color (`Tile2D` per figure and size, then `Extremes.high`). This reads `every figure's cells are blocks of that scale`. It differs from the claim only where the base figure is itself made of larger blocks. There, every figure's reduced shape is still the same, so the swap gives the same grid.
- The decoration is placed in the frame of the body's box at the figure's scale. A pattern position can fall outside the figure's box (train1 figure at rows 1–4 takes a 6 at row 0). `relative`/`compose` and `concat_2d` carry such negative margins correctly, and all pairs pass.
- `$OddOneOut` fails Subsumption: it was formed as a second choice point (`exchange-rule`), and the audit then reported that no run shows it defined and differing from `$Swap`. That model presupposes one shared pattern on the figures that are not the odd one. Where that holds, the input has exactly two patterns, and the model gives the concept's output. The formed clauses were also defined on three-pattern inputs (two odd figures, or two shared patterns), which the Analyze report gives as undefined. So no witness is built from those inputs, and the case leaves.
- Not formed, `keeping the shared cells and swapping only the differing cells`: this gives the concept's grid wherever either is defined (Analyze report), so it fails Equivalence, and no branch is formed.
- Not formed, `color mapping` and `stored background`: they fail Fit at train0 and across the pairs, so no branch is formed. `A cycle over three or more patterns` states no one model.
- `derive`: no built-in derivation fits. `store`: it printed `tiling.dim[a]` with no witness. That column is every axis on every input, and no `@store` line is added.
- Determine hint `determine prediction` on `frame_color`: kept with `@ignore`. The plan asked for the `UnchangedColor` form. `swap-decorations` keeps the body and changes every other figure cell, so the color that no pair changes is the body's color, read from the pairs.
- Deletions: removed the neighbor restriction in `mixed` (two cells of one block of different colors states the claim directly) and the redundant `!bg` in `col_box.cell`. The other no-change deletions are kept. They are the scene check (`body`, `body_mismatch`), the decoration's exclusion of background and body colors, both directions of `lacks` (one pattern can be a subset of the other), `block.high` and `in(P_grid, _)` in `paint` (the scale, and the grid frame), `figs.label` in the clearing clause (`rest-unchanged`), and `ex_out(E, _, _)` in Determine (the test-input rule).
- Keywords: `objects scale stamp`. The decoration is a footprint stamped at the body's place in each figure.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
