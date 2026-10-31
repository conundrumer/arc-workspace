# e99362f0

## Departures
- `$StoredPanelSize` is not in the solver: it fails Subsumption by `$CenterHalves`, as `analyze.md` gives. Its tiles are fixed by `helpers.tile_pos` in a 2×2 arrangement of 5×4 panels with a one-cell gap, so it is defined only on 11×9 grids, and on those grids the center halves cut the same tiles. `witness` found no run where it was defined and differed from `$CenterHalves`. Its names are gone from the witness file's groups.
- `divider=SharedColor` is not a case. It has the line `@ignore: derive SharedColor` because it fails Subsumption by `$CenterHalves`, as `analyze.md` gives. `witness` reported that no witness separates it from `$CenterHalves`. The witness with the id `divider=SharedColor` stays in the witness file, and it separates the concept case from `$CenterHalves`. Its `separates` text is rewritten to say that.
- `derive` listed `divider=VanishedColor`, which `analyze.md` does not give. It has an `@ignore: derive VanishedColor` line: on one input with no train outputs, it takes every color of the input, as SharedColor does. `witness` found no witness that separates it from `divider=SharedColor`. Its witness, which `derive` wrote, is removed.
- `analyze.md` stores `$CombinationTable`'s table as one relation, `stack_table`, keyed by a set of colors. The solver follows the set-keyed parent/child pattern instead (`stack_member`, `stack_out`, read through `KeyedSetCompare`). The witness file's `intransitive-table` assign is rewritten to those two relations, with the {2, 7, 9} entry set to 9. `witness --file programs/reports/e99362f0/witnesses.json` reports that `stack_table` is not a parameter. That report and the names of the dropped branches above are the only differences from `witnesses.json`.
- The parameter `background` is stored under the name the concept file gives. The witness that `derive` wrote as `bg=DominantColor` repeated `background=DominantColor` from `analyze.md`, so it is removed.
- The `$OrderByPanel` & `$CombinationTable` combination has its own stored table, from the set of panels marked at a cell to the panel shown (`panel_stack_member`, `panel_stack_out`).

## Judgments
- The `cut=stored` branch (from `store`, `@store: variant concept`, `@relaxed one-color-per-panel`): its witness is train0 turned a quarter turn. That is a D4 variant, and it moves each color to another panel, so it breaks `one-color-per-panel`. On it, the stored cut lines give a 3×4 grid. The concept gives the 4×5 stack, so the verdict is `concept`.
- `panels.divider` has `@ignore divider: store`, because the instance's `divider` holds the facts of `cut`, so storing it is `cut=stored`.
- The `orientation literal` hints on `AXIS_V`/`AXIS_H` in the Determine clauses for `panel_count`, `panel_dim` and `panel_gap` were set aside with `@ignore`, because a `Dim` record lists its V extent first. Those relations were removed later with `$StoredPanelSize`.
- The concept parse finds the cross by `Parse.full_cut`, a line drawn in one color, and keeps the lines whose color is `divider`. It cuts the panels with `DividerTiles`, and puts each panel cell in its panel's frame by `Bbox` and `crop`. `Determine` uses the same `Parse` to determine `divider`.
- The concept case is undefined at a cell where a mark has no `priority` entry (`unranked_color`), and `$OrderByPanel` is undefined where a marked panel has no `panel_order` entry (`unranked_panel`). The pairs never reach either guard, so `deletions` reports both as changing nothing. They stay, because they give the undefinedness that `analyze.md` states.
- `deletions` reported `panels.tile_of` in `panel_cell` and in Determine's `mark` as implied by `panel_box.box` and `crop`. Those atoms were removed. The bound-enumerator report on `axis_elem(A)` in `full_cut` stays, as the run says.
- `priority=CountRankDesc` and `priority=CountRankAsc` fail Fit at train0. `derive` did not list them, so they have no line.

## Unsettled
- The `$OrderByPanel` & `$CombinationTable` case: no witness file run separates it from the other cases. `deletions` shows that its `out` clause changes nothing that is checked. A witness that reassigns `panel_stack_out` would settle whether it meets Subsumption, and so would its removal under Subsumption.
- `$CenterHalves` and `divider=SharedColor` are broader in the solver than in `analyze.md`. `DividerTiles` cuts at every full line, so an input with several full lines of the divider color is defined, with more panels. Nothing in the solver checks for one row and one column. A witness with two full rows would show whether the concept case should be undefined there.
- The `audit` run stopped at its 120 s timeout, in its `store` check. Before that, its `witness`, `dropped cases` and `derive` checks gave output, and every one of them was resolved later. A run of the audit with a longer bound would settle it.
- The `sweep` run stopped at its 120 s timeout and gave no output. A run with a longer bound would settle it.
- `determination-plan` listed `stack_member`, `stack_out`, `panel_stack_member` and `panel_stack_out` as undecided. They have no determination relation, because a set-keyed table needs an id for each distinct set of marks seen in the examples. `background` (DominantColor exact) also has no determination relation. Determination relations for these would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
