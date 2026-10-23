# e6de6e8f

## Concept
- Fits every pair: the probe `work/task/e6de6e8f/probe.py` reproduces train0–2 and test0. The `piece_segment` lookup table has no unseen key, because the test's glyphs (bar, L with a right foot, L with a left foot) each occur in the train pairs.
- Every rule has a relational form, so the concept case approximates nothing, and no witness has the verdict `other`.
- Every input holds three L pieces and two bars, so the pipe drops seven rows in every pair. The `out_dims` row count 8 and column count 7 are therefore unseparated from derivations from the pipe, and the branches below form those derivations.

## Choice points
- `piece-segment`: how a glyph gives the cells its piece paints and the next piece's start
    - `concept`: the stored lookup table `piece_segment`
    - `piece_segment=derived`: replaces the table in `lay-segments`. A bar (one column, every cell filled) paints a run along `flow_dir` of its height. An L (one full column at one end, a full bottom row, nothing else) paints a run across of its width, toward the side away from its full column, and the next piece starts one step along `flow_dir` from the run's end. Reads no `piece_segment`. Undefined on a glyph that is neither. Fits every pair. Witness `wide-step`, at the stored assignment: it breaks `three-glyphs`; plausibility `variant`; verdict `piece_segment=derived`; it breaks the invariant that every L piece is two columns wide.
        - `segment-length`: the run each glyph paints
            - `concept`: the glyph's extent: a bar's height, an L's width
            - `$FixedLengths`: adds to `lay-segments` that every bar paints a run of two and every L a run of two, whatever its extent. Fits every pair. Witness `wide-step`, at the stored assignment: it breaks `three-glyphs`; plausibility `variant`; verdict `piece_segment=derived`; it breaks the invariant that every L piece is two columns wide.
- `piece-parse`: what a piece is
    - `concept`: a run of columns that hold `pipe_color`, between blank columns, read over the strip's full height
    - `$ComponentPieces`: replaces the parse in `read-order`. A piece is a 4-connected component of `pipe_color`, ordered by its leftmost column, and its glyph is its bounding box. Fits every pair. Witness `diagonal-contact`, at an assignment where `piece_segment` also holds a one-cell bar: it breaks `three-glyphs`; plausibility `foreign`; verdict `$ComponentPieces`; it breaks the invariant that every piece is one of the three glyphs and no two pieces touch.
    - `$Components8`: as `$ComponentPieces`, with 8-connected components. Fits every pair. Witness `gapped-column`, at an assignment where `piece_segment` also holds a one-cell bar and a three-row bar: it breaks `pieces-in-a-strip` (`input_height` 3) and `three-glyphs`; plausibility `foreign`; verdict `$Components8`; it breaks the invariants that every input has two rows and that every piece is one of the three glyphs.
- `out-height`: the output's row count
    - `concept`: the row count of the stored `out_dims`, 8
    - `$HeightFromPipe`: replaces the row count in `source-mark` with one more than the pipe's total drop along `flow_dir`. Reads no row count. Fits every pair. Witness `short-drop`, at the stored assignment: it breaks no scene claim; plausibility `variant`; verdict `$HeightFromPipe`; it breaks the invariant that every input holds three L pieces and two bars, so that the pipe drops seven rows.
    - `$HeightFromInput`: replaces the row count in `source-mark` with `height_ratio` times the input's row count, with `height_ratio` 4 stored, as ScaleRatioAxis gives it. Fits every pair. Witness `tall-strip`, at an assignment where `piece_segment` also holds a three-row bar: it breaks `pieces-in-a-strip` (`input_height` 3); plausibility `variant`; verdict `$HeightFromPipe`; it breaks the invariant that every input has two rows.
    - `$HeightFromInputDiff`: replaces the row count in `source-mark` with the input's row count plus `height_gap`, with `height_gap` 6 stored, as DimDiff gives it. Fits every pair. Witness `tall-strip`, at the same assignment: it breaks `pieces-in-a-strip` (`input_height` 3); plausibility `variant`; verdict `$HeightFromPipe`; it breaks the invariant that every input has two rows.
- `out-width`: the output's column count
    - `concept`: the column count of the stored `out_dims`, 7
    - `$WidthFromSteps`: replaces the column count in `source-mark` with one more than twice the total sideways run of the pipe's L segments, so the frame holds the pipe however its steps turn. Undefined where `source_col` falls outside that width. Fits every pair. Witness `five-steps`, at the stored assignment: it breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariant that every input holds three L pieces and two bars.
    - `$WidthFromInputDiff`: replaces the column count in `source-mark` with the input's column count less `width_gap`, with `width_gap` 5 stored, as DimDiff gives it. Undefined where that count is below 1 or `source_col` falls outside it. Fits every pair. Witness `five-steps`, at the stored assignment: it breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariants that every input holds three L pieces and two bars and that every input has 12 columns.
- `source-place`: the source's column
    - `concept`: the stored `source_col`, 3
    - `$SourceCentered`: replaces `source_col` in `source-mark` with the frame's center column. Undefined on a frame of even width. Fits every pair. Witness `wide-frame`, at the assignment `out_dims` 8×9, with train0's input: it breaks no scene claim; plausibility `variant`; verdict `$SourceCentered`; it breaks no invariant of the inputs, and its frame is wider than this task's.
- `background-source`: the value of `background`
    - `concept`: stored, 0
    - `background=RarestColor`: on one input alone it gives 0 wherever the strip starts and ends with a piece, because a strip of the three glyphs always holds two more `2` cells than `0` cells. Fits every pair. Witness `background=RarestColor` (train0's input with a blank column on each side), at the stored assignment: it breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariant that every input starts and ends with a piece.
    - `background=SharedColor`: on one input alone it gives both 0 and 2. Fails Fit at train0.
    - `background=DominantColor`: gives 2. Fails Fit at train0.
- `pipe-color-source`: the value of `pipe_color`
    - `concept`: stored, 2
    - `pipe_color=DominantColor`: on one input alone it gives 2 for every strip of the three glyphs. Fits every pair. Witness `pipe_color=DominantColor` (train0's input with its pieces in 4), at the stored assignment: it breaks `pieces-in-a-strip` (`pipe_color` 2); plausibility `variant`; verdict `pipe_color=DominantColor`; it breaks the invariant that every input's pieces are in 2.
    - `pipe_color=SharedColor`: gives both 0 and 2. Fails Fit at train0.
    - `pipe_color=RarestColor`: gives 0. Fails Fit at train0.
- `source-color-source`: the value of `source_color`
    - `concept`: stored, 3
    - `source_color=OutNewColor`, `source_color=AnyOutNewColor`: with `ex_out` empty, they give no value of 3 on an input alone. Fail Fit at train0.
- `out-dims-source`: the value of `out_dims`
    - `concept`: stored, 8 rows by 7 columns
    - `out_dims=ConstOutDimAxis`: with `ex_out` empty, it gives no value on an input alone, so every case that takes it is undefined. Fails Fit at train0.
- Every two choice points where neither stands under a branch of the other: the two branches' changes applied together.

## Open parameters
- none

## Not formed
- `read_from` right, the pieces read from the right edge: train0 read from the right gives the pieces bar, L right, bar, L left, L right, and a pipe other than train0's output. The pairs fix the parameter.
- `flow_dir` other than down, with the source on another edge: every train output has the source in row 0 and the pipe below it. The pairs fix the parameter.
- An L glyph read as the previous piece's exit cell over its own run, with the L's top cell shared with the piece above: on every input it lays the same cells as `piece_segment`, so it is the concept's model in another wording.
- The size proposers other than ConstOutDimAxis, ScaleRatioAxis and DimDiff (DivisorRatio, ConstInDim and their axis forms): no input dim divides by an output dim to a whole number, and ConstInDim's values 2 and 12 are not the output's 8 and 7.

## Tickets filed
- none
