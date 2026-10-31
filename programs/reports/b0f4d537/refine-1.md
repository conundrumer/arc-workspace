# b0f4d537

## Departures
- `stretch-key` counts lines from both ends of each axis, and the header's rule says so. The concept file counts them from the top only ("as many line rows above it"). The program enumerates every `Dir`: each field index maps to a key index once per edge of its axis, and one `out` clause ranges over both edges of each axis. Where the two ends give a cell two colors, the grid is undefined. Where an index takes no key index from one end, the defect `untaken` makes the grid undefined. This rests on [Orientation](docs/handbook/principles.md#orientation): "above" is an orientation that the program may not fix. The pairs leave every counting corner open, and an open set that holds every value of an orientation type is enumerated by the program ("Every value"). On every Analyze witness, the concept's output is the one the Analyze file gives (`witness --file` is ok). (create.md; holds)
- The program reads a new parameter, `key_band` (1). `key-grid` now says that the key's rows and columns alternate between gaps and lines `params.key_band` wide, with a gap at each end. The concept file says "each odd row is a line". The program finds the key's lines by `stride(T, W, W, N, _)`, and a literal width is banned. With an odd key extent, parity is the same from either end, so the reading stays equivariant. (create.md; holds)
- Two new choice points come from the Analyze report's Not formed items (Develop step 3). (create.md; holds: each branch fits every pair, and the run shows each one defined and differing on its witness.)
    - `GapRead`, with `$GapToEnd`: each field row off the lines takes the key's gap row at the end it is counted from. The item was "mapping every field gap row to one fixed key gap row". It fits every pair, and `gap_takes` states it. Its witness is `middle-gap`.
    - `Layout`, with `$LayoutStored`: the divider is a full line along the axis of `params.key_end` (`DIR_T`), and the key is the key panel's cells nearer that end than every all-divider line across the panel. The item was "`divider_axis` and `key_end` as parameters". It fits every pair, and `cut_axis`, `unfilled`, `filled_line` and `past_fill` state it. Its witness is `key-line-divider-color`.
- `divider_axis` is not a parameter. `$LayoutStored` derives it as the axis of `key_end`, by [Stored or derived](docs/handbook/principles.md#stored-or-derived) ("Redundant value"). (create.md; holds)

## Judgments
- Simplify: a shared relation `key_panel_cell` now gives the cells of the key panel with their colors. The `$LayoutFree` and `$LayoutStored` `key_cell` clauses, `unfilled`, `filled_line` and `past_fill` read it in place of repeating `key_panel`, `panel.label` and `in`. The pairs and every witness give the same outputs.
- Prune: the gloss of `Cut` now says it is a reading of the divider and of the panel layout; it had named the divider alone.
- `deletions`: I kept every atom and column it lists as changing nothing, for the reasons create.md gives. Also, `takes_cell.d1` and `d2` stay: `$DrawLines` tests each key index as a line or a gap from the edge it was counted from, and a test from either edge reads both on a key of even extent. The run of `split(P, A, X1, X2)` in `takes_cell` timed out, and that atom is needed to bind the two indices. (create.md, extended)
- `middle-gap` is `borderline concept`, `@relaxed key-grid`. The key's middle gap row is `6 1 6` and its end gap rows are `0 1 0`. A generator that draws a key with such a row would stretch that row over the rows between its lines. (create.md)
- `key-line-divider-color` is `borderline $LayoutStored`, `@relaxed key-grid`. The key's line row is 5 off its crossings. A generator that draws a line in the divider color would draw it in the output, which only `$LayoutStored` does. The concept drops those cells and gives no grid. (create.md)
- Not formed items that add no case (create.md):
    - Deriving `marker` under `$FieldByMarker` has no relational form. The field is found by its markers, so a marker read off the field needs the field it finds. Its clauses would read their own stratum.
    - `derive` lists no built-in derivation of `divider`.
    - An output frame other than the field fails Fit: every output has the field's size, and neither the key nor the input has it.
- `$DrawLines & $GapToEnd` cases fail Equivalence with `$DrawLines`, and `impl_choice` leaves them out. `$DrawLines` reads no gap row's content. A gap index that the count leaves unmapped comes after more field lines than the key has, so a line index is unmapped there too. `dropped cases: ok`. (create.md)
- Keywords: `decompose crop scale lines markers rank`. (create.md)
- create.md read `src/checker/witness.py` and `src/checker/judged.py`, because [Witnesses](docs/handbook/principles.md#witnesses) does not say that a witness whose verdict names its own branch is a witness of the concept case. This is a gap in the docs (ticket 10-235, watching). (create.md)

## Open
- `store` skipped `takes_cell` (over 20000 rows on an input): a store check that can read a relation that large would settle it. (create.md)

## Lib
- Full lines of one value: the lines (axis, index) whose cells hold no value other than a given one, or hold one value. Solver-local form: `broken_line(A, X, V) :- divider(_, V), in(P, C), !divider(C, V), axis_elem(A), split(P, A, X, _).`, then `divider_line` takes the cells of a line with no `broken_line`; `mixed_line` does the same with two cells of different colors. The grep found the same shape in `ac6f9922` (`broken_line` over the divider color) and in `a416fc5b` (`parse.line_color.clash` per line). Both are drafts. (create.md)

## Fixes elsewhere
- none

## Tickets filed
- none
