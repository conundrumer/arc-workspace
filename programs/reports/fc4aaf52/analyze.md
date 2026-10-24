# fc4aaf52

## Concept
- Fits train0, train1 and test0 at `bg` 8, `moved_half` DIR_T, `slide_dir` DIR_R (`work/task/fc4aaf52/check_concept.py`, `work/task/fc4aaf52/probe.py`). Undefined where the shape has an odd extent across the cut, or does not hold exactly two colors.
- `slide-to-clear` is written as the least move after which the moved cut row lies wholly past the other cut row. The generator probably moves the top half right by the length of the middle row. Under `mirror-halves` and `contiguous-cut-row` the two readings agree.
- No witness has verdict `other`.
- Relational form: the swap, the middle cut (Extremes over rows) and the clearing move (Extremes over the columns of the two cut rows) are each relational.

## Choice points
- `slide-distance`
    - `concept`: `slide-to-clear`, the least move that puts the moved cut row past the other cut row's span.
    - `$CellClear`: replaces `slide-to-clear`: the least move at which no cell of the moved cut row stands across the cut from a cell of the other cut row. Same parameters, same undefined inputs. Fits every pair. Witness `gapped-cut-row` (slides 1 where the concept slides 3). It breaks `contiguous-cut-row`, at the stored assignment; `borderline`, verdict `concept`, invariant broken: every input's cut row is one unbroken run.
    - `$CutCount`: replaces `slide-to-clear`: the move is the moved cut row's cell count. Same parameters, same undefined inputs. Fits every pair. Witness `gapped-cut-row` (slides 2). It breaks `contiguous-cut-row`, at the stored assignment; `borderline`, verdict `concept`, invariant broken: every input's cut row is one unbroken run.
    - `$HalfClear`: replaces `slide-to-clear`: the least move that puts the whole moved half past the whole other half. Fails Fit at train0 (it slides 5, the pair slides 3).
    - `$CornerGap`: replaces `slide-to-clear`: one more than the clearing move, so the halves do not touch even at a corner. Fails Fit at train0.
    - `$ShapeWidth`: replaces `slide-to-clear`: the move is the shape's full extent along `slide_dir`. Fails Fit at train0.
- `recolor`
    - `concept`: `swap-colors`, the shape's two colors exchanged.
    - `$LayerReverse`: replaces `swap-colors`: the shape's nested same-colored layers, outermost first, take their colors in reverse order (from the b94a9452 header). Undefined where the cells around a layer hold more than one color; defined on any number of layers. Fits every pair. Witness `three-layers` (outer and inner colors exchanged, middle kept; the concept is undefined there). It breaks `two-colors`, at the stored assignment; `variant`, verdict `$LayerReverse`, invariant broken: every shape holds exactly two colors.
    - `$LayerShiftOut`: replaces `swap-colors`: each layer takes the color of the layer inside it, and the innermost takes the outermost's. Same undefined inputs as `$LayerReverse`. Fits every pair. Witness `three-layers`. It breaks `two-colors`, at the stored assignment; `variant`, verdict `$LayerReverse`, invariant broken: every shape holds exactly two colors.
    - `$LayerShiftIn`: replaces `swap-colors`: each layer takes the color of the layer around it, and the outermost takes the innermost's. Same undefined inputs. Fits every pair. Witness `three-layers`. It breaks `two-colors`, at the stored assignment; `variant`, verdict `$LayerReverse`, invariant broken: every shape holds exactly two colors.
    - `$StoredMapping`: replaces `swap-colors`: a stored color table, 0↔5 and 1↔2. Undefined on a color the table lacks. Fails Fit at test0 (unseen keys 4 and 9).
- `cut-line`
    - `concept`: `cut-at-middle`, between the two middle rows of the shape's extent.
    - `$MirrorCut`: replaces `cut-at-middle`: the cut is the shape's mirror line across the `moved_half` axis. Undefined where the shape has no such mirror line. Fits every pair. It agrees with the concept wherever it is defined, so it is subsumed by the concept and fails Subsumption. Witness `lopsided` (undefined where the concept is defined). It breaks `mirror-halves`, at the stored assignment; `borderline`, verdict `concept`, invariant broken: every input's shape is mirror-symmetric across its middle.
    - `$WidestCut`: replaces `cut-at-middle`: the cut sits between the two adjacent rows of most cells. Fails Fit at train0 (the widest neighbors are tied).
    - `$PinchCut`: replaces `cut-at-middle`: the cut sits between the two adjacent rows of fewest cells. Fails Fit at train0 (tied ends).
- `moved-half-pose`
    - `concept`: the moved half is translated.
    - `$FlipMoved`: adds a reflection of the moved half across the `slide_dir` axis as it moves. Fails Fit at train1 (the lopsided row 7 keeps its orientation).
- `background`
    - `concept`: `bg` stored, 8.
    - `bg=DominantColor`: `bg` derived as the input's commonest color, replacing the stored `bg` in `one-shape`. Undefined where two colors tie for the most cells. Fits every pair. Witness `bg=DominantColor` (a 6×6 input whose outer color 4 outnumbers 8). It breaks no scene claim, at the stored assignment; `borderline`, verdict `concept`, invariants broken: every input is 16×16 and has `bg` as its commonest color.
- `slide-distance` & `recolor`, `slide-distance` & `cut-line`, `slide-distance` & `moved-half-pose`, `slide-distance` & `background`, `recolor` & `cut-line`, `recolor` & `moved-half-pose`, `recolor` & `background`, `cut-line` & `moved-half-pose`, `cut-line` & `background`, `moved-half-pose` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Deriving `moved_half` or `slide_dir` from the shape: the two halves are mirror images, and train0's shape is symmetric left to right too, so nothing in an input marks which half moves or which way it slides.
- Both halves moving apart: the bottom half keeps its place in every pair, so the stored side carries the whole move.
- A middle row for an odd extent: no input has one, and no pair says what a middle row does.
- `bg=SharedColor`, `bg=RarestColor`, `bg=UnchangedColor` and the other color proposers: on one input with `ex_out` empty, they give several colors, a shape color, or nothing, and fail Fit at train0. `bg=DominantColor` is the only derivation that fits.
- Stored per-pair slide distances: the distance changes per input (3, 5, 7), so a stored value fails Fit at test0.

## Tickets filed
- none
