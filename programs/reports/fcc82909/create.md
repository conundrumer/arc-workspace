# fcc82909

## Departures
- `bar_height=stored` is the constructor `$Height_table` of a `Height` point, and its witness id is `height-table`: the branch stores a lookup table (distinct count to row count), so Write makes it a constructor with a name of the pass's own, and the witness file's names are rewritten to it.
- `background=DominantColor` is the `@derive DominantColor` line on `bg`, and the name is `bg=DominantColor` in the witness file. The analyze witness (`5 5 / 5 5 / 0 0`) is the witness that line records, under the id `bg=DominantColor`, at `borderline concept` as analyze.md gives it. `derive` also wrote a witness of its own (train0 with 0 and 1 swapped). That witness was removed, because it duplicates the branch's recorded witness.
- `$Bar_must_fit` and the `bar-leaves-grid` point are removed, and so is the witness `bar-leaves-grid`, which separated nothing else: `witness` showed no input where `$Bar_must_fit` is defined and differs from `$Bar_clipped`. The model fails Subsumption, as analyze.md states.
- Witness `square-dominant` was added (a 6×2 grid of `5 5` over four rows on top of `0 0` over two rows): with no witness, no run showed `$Square_blocks & bg=DominantColor` defined and differing from `$Square_blocks & bg=stored`. Bg 0 hangs a bar under each of two stacked squares, and the dominant bg 5 takes the `0` square, whose bar leaves the grid. The case meets Subsumption and stays. Judged `borderline $Square_blocks`: the blocks touch and the grid is tiny, and a person sees two squares, as in `side-touch`.

## Judgments
- Blocks, bars and heights live in `Parse<Key>`, keyed by `[Key, BlockKey]` with `BlockKey = [BlockParse, Ident]`. The concept parse (4-components) and the bar cast (`Ray` from the bbox's edge toward `params.direction`) are shared with Determine. The other parses add `parse.block` rows from program scope.
- The bar's rows are the `Ray` cells at distances 1..N from the marks. This bounds a distance by the count and uses no arithmetic. Off-grid bar cells drop out because `cast.cell` is the grid.
- `$Square_blocks` finds all-ink `block_size` squares with `Occurrences` over the `Frame2D` square. `CoverForcing` keeps the forced squares that nothing rules out. The case is undefined where an ink cell lies in no kept square.
- Determination: `block_size` is the side of a square 4-component box. `bar_height` reads each train block's row count off its bar in the output. The `determine prediction` hint on `bar_height` is kept with `@ignore`, because the relation reads the value from the pair and keeps no guessed value. For `bg` (DominantColor) and `bar_color` (AnyOutNewColor), the proposers derive the value from the fact the concept reads, so neither has a determination relation. `direction` is pinned by enumeration (pairs-exact `DIR_B`).
- Sweep: the `bar_height` set is not pinned, because 43 single-row changes give every train output. The extra rows are keys that no train block uses. It is a lookup table and not an open parameter, so no value was added.
- `store` gave no line to add. `derive` found no derivation that fits `bar_color`.
- Deletions: the atoms it flagged guard structure the pairs never reach (overlapping squares, bars meeting ink, undefinedness), so they stay. The exception was the `impl_choice` atoms in the three `bar` clauses. They were removed after that run, because `impl_choice` is the full product of the fields and the clause's other atoms bind every field. The final pairs run passed after that edit.
- Hints: the single-consumer hints on `hit`, `unkeyed` and `untiled` were resolved by inlining each into its one use. The case-marker hint was resolved by naming the marker `$Four_blocks, $Column_bars`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
