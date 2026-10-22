# ae58858e

## Departures
- The `$Diagonal` branch has a `@scene scattered-shapes` line only. The Analyze report says it replaces `scattered-shapes` and `recolor-large`. The text of `recolor-large` refers to "shape" and does not state the adjacency, so its text under `$Diagonal` is the same as the header's.
- The witness file has the witness `bg=DominantColor`, which `derive` built. Its input is train0 with 0 and 1 swapped. The Analyze report gives no `bg` derivation: `bg` is a parameter of the `$Foreground` branch, and `derive` finds that `DominantColor` fits it.

## Judgments
- The concept branches take the names `Orthogonal` (adjacency), `StoredColor` (shape cells), `SameColor` (color mixing under `$Foreground`) and `Threshold` (recolor test). `Mixing` is the type of the field of `Foreground`, because the report puts `color-mixing` under `$Foreground`.
- `@derive RarestColor: borderline concept` on `shape_color`: the plausibility and verdict are the ones the Analyze report gives. The witness breaks no scene claim, so it has no `@relaxed` line.
- `@derive DominantColor: variant derived` on `bg`, with `@relaxed scattered-shapes`: on the witness, the field is 1. A color permutation of the task gives that, so it is `variant`. The scene claim says the field is 0, so the witness breaks it. Where the field is 1, the concept case recolors only the large shapes of color 2, and the derived branch gives the same output. The `$Foreground` case with the stored `bg` (0) turns the field 6.
- `store` lists only `color_shapes.node` and `color_shapes8.node`, and gives them no case. So no `@store` branch.
- The sweep finds single-row changes to `size_recolor` and `size_keep` that still give every train output. Those tables are the train sizes that `$SizeTable` reads. A reader of the concept does not take any other value, so they are not open parameters. No value was added.
- The determination for `size_recolor` takes the 4-connected components of the cells that change color, and their sizes. It reads no parameter. The recolored shapes of one color cannot touch across a side, so each component is one recolored shape.
- The 4-adjacency and 8-adjacency readings of the per-color shapes use `Components<Color>` and `Components8<Color>` over every input cell, keyed by its color. The `$Multicolor` readings use `Components<Cells>` and `Components8<Cells>` over the non-`bg` cells. A shape under `$Multicolor` has no one color, so the per-color key cannot hold it.
- `deletions`: I removed `impl_choice` from the `out` clause that reads `member`, because every combination of the fields is a case and `member` and `recolor`/`keep` ground the choice. The node clause of `ink_shapes8` and the `member` clause of `$Diagonal & $Multicolor` stay. The case `$Diagonal & $Multicolor` is not witnessed, so no run uses them.
- No hint fired, and lint passes. The run has 9 witnessed cases, and each passes every pair.

## Open
- `determination-plan` says that `TileDim` gives `size_keep` ({1, 2, 3}) exactly. That is a coincidence of this task's tile sizes, so the plan writes no determination relation for `size_keep`. A determination relation for `size_keep`, from the sizes of the shapes that keep their colors, would settle it.

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
