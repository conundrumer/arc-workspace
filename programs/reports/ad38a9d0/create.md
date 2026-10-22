# ad38a9d0

## Departures
- The solver's cases differ from the Analyze report's branch models. Each non-concept case that takes `$KeyedOnly` (a piece with no key leaves the grid undefined) gives the grid of its `$KeepUnknown` copy wherever it is defined, so it fails Subsumption and leaves. `impl_choice` keeps the concept and every `$KeepUnknown` combination. Under `fg`'s `@derive RarestColor` line, `@ignore: derive $KeyedOnly` drops the concept base read with the derived `fg`. So the cases of `$NonBgCells`, `$PerColorPieces`, `$SizeBoxKey`, `fg=RarestColor` and `bg=DominantColor` keep a piece that has no key. The run against `work/task/ad38a9d0/witnesses.json` shows these differences: `$SizeBoxKey` and `$NonBgCells & bg=stored` keep the 6 field on `fg=RarestColor` and `bg=DominantColor`; `$MixedPieces` keeps the two-color 2×2 piece on `two-color-piece`; `fg=RarestColor` and `$NonBgCells` keep the T on `t-tetromino`. In each of these the Analyze file has undefined. Rests on the Subsumption condition. Neither case changes on any input: `$KeyedOnly` is defined only where every piece has a key under every open value of `shape_sym`, and `$KeepUnknown` then paints the same colors.
- `$SizeBoxKey`'s table is stored as `box_key_size`, `box_key_extent` (one fact per axis) and `box_key_color`, keyed by an `Ident`, in place of the report's (count, height, width) → color. Rests on the D4 action: an `Axis` column transforms under the group, and fixed height and width columns would not.
- The witness file adds the following witnesses beside the Analyze file's five:
    - `plus-majority`: shows `bg=stored` defined and differing from `bg=DominantColor`.
    - `horizontal-domino`: shows that removing `SYM_1` changes the output.
    - `s-tetromino`: shows that removing `SYM_D4` changes the output.
    - `box-0-v` through `box-5-h`: one per `box_key_extent` fact. The seven facts that the piece's count and other extent fix under 4-adjacency use an `assign` of `box_key_size` that holds the one key alone.

## Judgments
- Concept constructor names: `FgPieces` (piece-cells), `MixedPieces` (piece-color-split under `NonBgCells`), `ShapeKey` (shape-key), `KeyedOnly` (unknown-piece). `$Adjacency8`, `$BoxKey`, `$SizeKey`, `fg=DominantColor` and `fg=SharedColor` fail Fit per the report. They get no constructor, and `derive` lists only `fg=RarestColor` and `bg=DominantColor`.
- Not formed:
    - `shape_color` derived: no derivation exists.
    - Rotation and D4 matching: these are open values of `shape_sym`, not branches.
    - Reflection-only and half-turn values of `shape_sym`: kept out. The sweep admits them, but the report judges that no reader takes them.
    - `ChangedColor` and the other output-reading proposers for `fg`, and `CountRankAsc`/`CountRankDesc`: `derive` lists none of them as fitting.
- `shape_sym(SYM_C4)` stays after the audit's fact-removal finding. A reader could take it. Under the open-value join, the colors painted grow with the group (`SYM_1` ⊂ `SYM_C4` ⊂ `SYM_D4`), and the defect turns only on `SYM_1`, so no input at any assignment shows its removal changing a grid.
- `plus-majority` (3×3, a plus of 6 on four corners of 7): plausibility `borderline`, verdict `concept` (the plus painted 3). It breaks no scene claim, but the generator draws 9×9 fields that hold far more 7 than 6.
- `horizontal-domino` and `s-tetromino`: plausibility `variant`, since a variant task can hold a key shape in another orientation. They have no verdict line, because the open values disagree on them.
- The `box-*` witnesses: plausibility `borderline`, verdict `concept` (undefined), since each holds a piece of no keyed shape.
- Parse: one `Parse<Key>` holds the pieces for the program (`Parse<Cells>`) and for Determine (`Parse<Example>`). A `one_color` flag picks per-color components (`FgPieces`, `PerColorPieces`) or mixed components (`MixedPieces`).
- Determine: `shape_sym` keeps each group that neither moves a direction without containing a quarter turn nor carries a determined key onto a key of another color. `shape` and `shape_color` share one `Canon` class per shape. The `box_key_*` relations share one class per (count, extents).
- Deletions: the 17 deletions that change nothing remove structures the pairs never instantiate: the one-color split, open values of `shape_sym`, `$KeepUnknown`, the multi-key defect, and the key-collision test of the `shape_sym` determination. All are kept. `cell_count.domain` and a `size` copy of the tally were removed.
- Lint gave no hint after the first fixes: a reserved name `count`, a long line, and a negated record atom.

## Open
- `shape_sym(SYM_C4)` changes no output on any input under the open-value join: an Analyze or handbook ruling on whether an open value that the join makes redundant stays would settle it.

## Lib
- Cells of each keyed set read in the frame of their bounding box (`Bbox` and then `crop(P, B, P_inner)`): solver-local in `Parse` as `box` and `shape_cell`. Approved sites with the same shape that feed `KeyedSetCompare`: 00dbd492, 0934a4d8, 11852cab, 14754a24, 15113be4, 1fad071e, 228f6490, 2c181942, 3b4c2228, 898e7135, ff28f65a. 0934a4d8 and 898e7135 also compare under `d4_elem(D), apply(D, ...)` as `shape_match` does here.

## Fixes elsewhere
- none

## Tickets filed
- `10-88_task_ad38a9d0_create.md`
