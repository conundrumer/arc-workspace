# b0f4d537

## Departures
- `stretch-key` counts lines from both ends of each axis, and the header's rule says so. The concept file counts them from the top only ("as many line rows above it"). The program enumerates every `Dir`: each field index maps to a key index once per edge of its axis, and one `out` clause ranges over both edges of each axis. Where the two ends give a cell two colors, the grid is undefined. Where an index takes no key index from one end, the defect `untaken` makes the grid undefined. This rests on [Orientation](docs/handbook/principles.md#orientation): "above" is an orientation that the program may not fix. The pairs leave every counting corner open, and an open set that holds every value of an orientation type is enumerated by the program ("Every value"). On every Analyze witness, the concept's output is the one the Analyze file gives (`witness --file` is ok).
- The program reads a new parameter, `key_band` (1). `key-grid` now says that the key's rows and columns alternate between gaps and lines `params.key_band` wide, with a gap at each end. The concept file says "each odd row is a line". The program finds the key's lines by `stride(T, W, W, N, _)`, and a literal width is banned. With an odd key extent, parity is the same from either end, so the reading stays equivariant.
- Two new choice points come from the Analyze report's Not formed items (Develop step 3):
    - `GapRead`, with `$GapToEnd`: each field row off the lines takes the key's gap row at the end it is counted from. The item was "mapping every field gap row to one fixed key gap row". It fits every pair, and `gap_takes` states it. Its witness is `middle-gap`.
    - `Layout`, with `$LayoutStored`: the divider is a full line along the axis of `params.key_end` (`DIR_T`), and the key is the key panel's cells nearer that end than every all-divider line across the panel. The item was "`divider_axis` and `key_end` as parameters". It fits every pair, and `cut_axis`, `unfilled`, `filled_line` and `past_fill` state it. Its witness is `key-line-divider-color`.
- `divider_axis` is not a parameter. `$LayoutStored` derives it as the axis of `key_end`, by [Stored or derived](docs/handbook/principles.md#stored-or-derived) ("Redundant value").
- `$LineByHeaderEdge` has `@witness line-one-end: borderline $LineByEitherEnd` in place of the Analyze report's `@witness header-edge: borderline $LineByHeaderEdge` with `@reassigned header`. A witness whose verdict names its own branch is a witness of the concept case. The concept is defined at the stored assignment and differs there from `$LineByHeaderEdge`, which is undefined, so that witness stands at the stored assignment. Its `assign` then contradicts that, and `witness` reported it.
- The witness `header-edge` keeps `assign` `header` = `DIAG_TL`, and it has no `@witness` line. Its input adds a marker at row 1, col 6, the right end of field row 1 alone. With that marker, `$LineByEitherEnd` reads two line rows where the key has one and gives no grid. `$LineByHeaderEdge` reads row 4 alone and gives the train3 output. Before the change, no run showed `$LineByHeaderEdge` defined and differing from `$LineByEitherEnd`.
- `$LineByHeaderEdge` joins its open `header` values at the line level, in place of the output level. An index that one header value reads as a line and another does not is `undecided`: it is neither line nor gap, its row has no output cells, and the grid is undefined. The two joins differ only where two line sets give the same output, which needs a key line row equal to a key gap row. They agree on every pair and on every witness.

## Judgments
- `middle-gap` is `borderline concept`, `@relaxed key-grid`. The key's middle gap row is `6 1 6` and its end gap rows are `0 1 0`. A generator that draws a key with such a row would stretch that row over the rows between its lines.
- `key-line-divider-color` is `borderline $LayoutStored`, `@relaxed key-grid`. The key's line row is 5 off its crossings. A generator that draws a line in the divider color would draw it in the output, which only `$LayoutStored` does. The concept drops those cells and gives no grid.
- Not formed items that add no case:
    - Deriving `marker` under `$FieldByMarker` has no relational form. The field is found by its markers, so a marker read off the field needs the field it finds. Its clauses would read their own stratum.
    - `derive` lists no built-in derivation of `divider`.
    - An output frame other than the field fails Fit: every output has the field's size, and neither the key nor the input has it.
- `$DrawLines & $GapToEnd` cases fail Equivalence with `$DrawLines`, and `impl_choice` leaves them out. `$DrawLines` reads no gap row's content. A gap index that the count leaves unmapped comes after more field lines than the key has, so a line index is unmapped there too. `dropped cases: ok`.
- The audit's open-values report says that removing any one `header` fact changes no output. The facts stay. A reader can take each corner. The three remaining corners still read both ends of each axis, so they agree exactly where all four agree.
- `deletions`: I kept every atom it lists as changing nothing. Each one serves an input off the pairs (`marker(_, F, V, Y)` in `field_idx` for `$MarkerFromField` on a one-color field, `unmarked_end`, `untaken`, `undecided`, the `key_end` atoms), states an axis tie that `nearer` or `key_gap` already implies (`axis_of` in `before.item`, `key_line`, `gap_takes`), or keeps the band test for `key_band` > 1 (`!key_gap` in `key_line`).
- Determine: `header` keeps each corner that reads no line whose two ends are not both markers, in any example with `ex_out` rows. It takes each example's field as the box of its marker cells. That box is the field under `field-markers`, and the program does not use it. `Parse<Key>` holds the line-end readings, which the program and the determination share.
- Keywords: `decompose crop scale lines markers rank`.
- I read `src/checker/witness.py` and `src/checker/judged.py`. The `stands at the stored assignment` finding cites [Witnesses](docs/handbook/principles.md#witnesses). That section does not say that a witness whose verdict names its own branch is a witness of the concept case. This is a gap in the docs.

## Open
- `store` skipped `takes_cell` (over 20000 rows on an input): a store check that can read a relation that large would settle it.
- `$LineByEitherEnd & $GapToEnd` is a witnessed case only because the runner tells two undefined outputs apart by their missing cells, on `header-edge`: a runner that counts every undefined output as one output would settle it (ticket 10-234).

## Lib
- Full lines of one value: the lines (axis, index) whose cells hold no value other than a given one, or hold one value. Solver-local form: `broken_line(A, X, V) :- divider(_, V), in(P, C), !divider(C, V), axis_elem(A), split(P, A, X, _).`, then `divider_line` takes the cells of a line with no `broken_line`; `mixed_line` does the same with two cells of different colors. The grep found the same shape in `ac6f9922` (`broken_line` over the divider color) and in `a416fc5b` (`parse.line_color.clash` per line). Both are drafts.

## Fixes elsewhere
- none

## Tickets filed
- 10-233_task_b0f4d537_create.md
- 10-234_task_b0f4d537_create.md
