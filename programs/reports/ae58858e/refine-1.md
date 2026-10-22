# ae58858e

## Departures
- The `$Diagonal` branch has a `@scene scattered-shapes` line only. The Analyze report says it replaces `scattered-shapes` and `recolor-large`. The text of `recolor-large` refers to "shape" and does not state the adjacency, so its text under `$Diagonal` is the same as the header's. (create.md; holds: the text of `recolor-large` names no adjacency.)
- The witness file has the witness `bg=DominantColor`, which `derive` built. Its input is train0 with 0 and 1 swapped. The Analyze report gives no `bg` derivation: `bg` is a parameter of the `$Foreground` branch, and `derive` finds that `DominantColor` fits it. (create.md; holds: `derive` lists `DominantColor` as a fit for `bg`, and the `witness` run shows `$Foreground & bg=DominantColor` defined and different from `$Foreground` with the stored `bg`.)

## Judgments
- The concept branches take the names `Orthogonal` (adjacency), `StoredColor` (shape cells), `SameColor` (color mixing under `$Foreground`) and `Threshold` (recolor test). `Mixing` is the type of the field of `Foreground`, because the report puts `color-mixing` under `$Foreground`. (create.md)
- `@derive RarestColor: borderline concept` on `shape_color`: the plausibility and verdict are the ones the Analyze report gives. The witness breaks no scene claim, so it has no `@relaxed` line. (create.md)
- `@derive DominantColor: variant derived` on `bg`, with `@relaxed scattered-shapes`: on the witness, the field is 1. A color permutation of the task gives that, so it is `variant`. The scene claim says the field is 0, so the witness breaks it. Where the field is 1, the concept case recolors only the large shapes of color 2, and the derived branch gives the same output. The `$Foreground` case with the stored `bg` (0) turns the field 6. (create.md)
- `store` lists only `color_shapes.node` and `color_shapes8.node`, and gives them no case. So no `@store` branch. (create.md; the `store` run of this pass gives the same.)
- The sweep finds single-row changes to `size_recolor` and `size_keep` that still give every train output. Those tables are the train sizes that `$SizeTable` reads. A reader of the concept does not take any other value, so they are not open parameters. No value was added. (create.md)
- The 4-adjacency and 8-adjacency readings of the per-color shapes use `Components<Color>` and `Components8<Color>` over every input cell, keyed by its color. The `$Multicolor` readings use `Components<Cells>` and `Components8<Cells>` over the non-`bg` cells. A shape under `$Multicolor` has no one color, so the per-color key cannot hold it. (create.md)
- `deletions`: the node clause of `ink_shapes8` and the `member` clause of `$Diagonal & $Multicolor` change nothing on the pairs. They stay, because `$Diagonal & $Multicolor` is a case of the solver. It is not witnessed: both of its branches have only `concept` verdicts, and some cases take one without the other. (create.md; this pass's `deletions` run gives the same two.)
- The open item of create.md on `size_keep` is settled. `Determine` now finds the shape color as the input color of the changed cells, takes the 4-connected shapes of that color in the train pairs, and gives `size_recolor` from the shapes with a changed cell and `size_keep` from the other shapes. The shapes are read only in examples with `ex_out` rows, so the test sizes do not enter `size_keep`. The run reports `determination: ok (shape_color, size_keep, size_recolor)`, and the plan lists no actions. The determination of `size_keep` from `TileDim` was a match of this task's grid sizes and did not state the concept.
- Checks: the solver passes every pair with 9 witnessed cases, lint passes, and the audit, `witness`, and `witness --file work/task/ae58858e/witnesses.json` report ok. No hint fired.
- Simplify and Prune: no change. Each clause states a step of a case, and the header and comments state only the claims and glosses.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
