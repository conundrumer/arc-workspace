# ef135b50

## Concept
- The concept fits every pair: train0, train1, train2 and test0 are reproduced cell for cell by `work/task/ef135b50/probe.py` (no lib run; see `progress-analyze.md`). Every input holds 3 to 5 solid rectangles of 2 on 0, and no two touch, by side or corner.
- No witness of the concept case has verdict `other`. The generator's rule as it applies it: join with 9 every two rectangles that face each other across rows with nothing between them, over the rows they share. The concept file's rule is that rule. It is relational (pieces, shared lines, strips), and it is no approximation.
- The evidence that sets the bridge unit: train2 row 9, cols 4-8, is a clear background run between the rectangle at rows 7-9, cols 0-3 and the one at rows 6-9, col 9. It stays 0 because the middle rectangle (rows 3-8, cols 5-7) stands in their strip on rows 7-8. Train1 row 5, cols 5-6, rules out nearest-neighbour-only pairing.
- One witness off the scene, `l-shaped-piece` (borderline), is judged for `$CellwiseStrip` over the concept.

## Choice points
- `gap-unit`
    - `concept`: a bridge spans the gap between two pieces, over the lines along `bridge-axis` that they share
        - `pair-selection`
            - `concept`: a pair is bridged when its strip holds no cell of `object-color`, and then over the whole strip
            - `$NearestNeighbor`: replaces `bridge-facing-pairs`. Each piece is bridged only to its nearest piece on the far side along `bridge-axis` among those it shares a line with, and the clear-strip test is still applied. Same parameters. Defined on every input. Fails Fit at train1 (5,5), (5,6): the rectangle at rows 5-8, cols 3-4 is nearer to the one at rows 8-9, cols 6-9 than to the one at rows 2-5, cols 7-9, but the output bridges both.
        - `piece-adjacency`
            - `concept`: pieces are the 4-connected components of `object-color`
            - `$DiagonalJoin`: replaces the 4-adjacency in `solid-rectangles` and `bridge-facing-pairs` with 8-adjacency. A piece's extent is its bounding box. Same parameters. Defined on every input. Fits every pair. Witness `corner-touching-rectangles`. It breaks `solid-rectangles` (two rectangles touch at a corner) and stands at the stored assignment. Plausibility `borderline`, since it breaks the input invariant that every two rectangles are at least one cell apart, corners included. Verdict `concept`.
        - `strip-extent`
            - `concept`: the strip on a shared line runs between the two pieces' bounding boxes
            - `$CellwiseStrip`: replaces the strip of `bridge-facing-pairs`. On each shared line the strip runs from the near piece's last cell on that line to the far piece's first cell on it. Same parameters. Defined on every input. Fits every pair. Witness `l-shaped-piece`. It breaks `solid-rectangles` (an L-shaped piece) and stands at the stored assignment. Plausibility `borderline`, since it breaks the input invariant that every piece is a solid rectangle. Verdict `$CellwiseStrip`.
    - `$PerLineRun`: replaces `bridge-facing-pairs`. On each line along `bridge-axis`, each background run between two cells of `object-color` takes `bridge-color`. It reads no pieces. Same parameters. Defined on every input. Fails Fit at train2 (9,4)-(9,8). Its fitting case is `$PerLineRun & $BorderLinesUnbridged`: witness `blocked-pair-open-lines` at the stored assignment, breaking no scene claim, plausibility `ordinary`, verdict `concept`.
- `border-lines`
    - `concept`: lines at the grid border are bridged like any other
    - `$BorderLinesUnbridged`: adds to `keep-rest` that a line along `bridge-axis` at the grid border takes no bridge cell. Same parameters. Defined on every input. Fits every pair, since no bridged line in the pairs is row 0 or row 9. Witness `border-line-bridge` at the stored assignment, breaking no scene claim. Plausibility `ordinary` (train1 and train2 have rectangles on row 0). Verdict `concept`.
- `bridge-axes`
    - `concept`: bridges run along the one axis `bridge-axis` stores
    - `$BothAxes`: replaces the no-cross clause of `keep-rest`, so bridges run along both axes, and `bridge-axis` is not read. Defined on every input. Fails Fit at train1 (6,7)-(7,9), the vertical gap between the rectangles at rows 2-5, cols 7-9 and rows 8-9, cols 6-9.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: derived per input. Fails Fit at train2, where 2 outnumbers 0 (54 to 46).
    - `background=SharedColor`, `background=RarestColor`, and every other derivation from an input alone: each gives 2, or both 0 and 2, on train0. Each fails Fit at train0.
- `object-color`
    - `concept`: stored, 2
    - `object-color=RarestColor`: derived per input. Fails Fit at train2, where 0 is the rarer color.
    - `object-color=SharedColor`, `object-color=DominantColor`, and every other derivation from an input alone: each gives 0, or both 0 and 2, on train0. Each fails Fit at train0.
- `bridge-color`
    - `concept`: stored, 9
    - Every derivation of `bridge-color` from an input alone gives only colors the input holds, never 9, and fails Fit at train0. OutNewColor and AnyOutNewColor give none with `ex_out` empty, so those branches are undefined on every input.
- `gap-unit` & `border-lines`, `gap-unit` & `bridge-axes`, `border-lines` & `bridge-axes`, `pair-selection` & `piece-adjacency`, `pair-selection` & `strip-extent`, `piece-adjacency` & `strip-extent`, each of `pair-selection`, `piece-adjacency`, `strip-extent` & each of `border-lines`, `bridge-axes`, and each of `background`, `object-color`, `bridge-color` & each other point: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Deriving `bridge-axis`: no proposer gives an Axis on its own, and the pairs fix the axis to horizontal, because train1 and train2 leave clear vertical gaps unbridged.

## Tickets filed
- none
