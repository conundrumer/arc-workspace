# 33067df9

## Concept
- The concept case fits every pair, train0–2 and test0 (`.scratch/33067df9/probe.py`), and no witness has verdict `other`.
- On an input that breaks `counts-fit` (a count that does not divide `out_extent` − `out_line`, such as 5), the concept's `canvas` rule cannot cut equal tiles, so the concept case is undefined there; the witness `five-tiles` shows it.
    - The current `programs/solvers/33067df9.dl` does not match that: its Divide2D decomposes no canvas cell on such an input, and it returns a bare `bg` canvas (`run_dl.py witness 33067df9 --file .scratch/33067df9/witnesses.json`, case concept on `five-tiles`). Its header's "tiles as large as the canvas admits" describes neither that output nor the concept.
- `run_axis` is fixed at H by train0: the 8 tiles at lattice (2,0), (2,1), (3,0) draw as a row run over (2,0)–(2,1) and a lone tile at (3,0) (train0 output rows 14–17 cols 2–23 and rows 20–23 cols 2–11, with rows 18–19 `bg`).

## Choice points
- `join`: whether like-colored neighboring tiles join into one drawn rectangle
    - `concept`: they join
        - `grouping`: how like-colored tiles group into rectangles
            - `concept`: runs along `run_axis` (`join-runs`), then runs across it with the same color and extent (`stack-runs`)
            - `$SingletonStack`: replaces `stack-runs`: runs stack across `run_axis` only when both are single tiles; reads `run_axis`; defined wherever the concept is. Fits every pair. Witness `stack-wide-runs` (a 2×2 lattice of 8): ordinary, breaks no scene claim, verdict `concept` (one 22×22 block; the branch draws two strips).
            - `$RectComponent`: replaces `stack-runs`: a 4-connected like-colored component that fills its bounding box draws as one rectangle, and any other component draws as its runs along `run_axis`, with no stacking; reads `run_axis`; defined wherever the concept is. Fits every pair. Witness `stack-into-l` (lattice rows `8 4`, `8 6`, `8 8`): ordinary, breaks no scene claim, verdict `concept` (the lone 8s in col 0 stack, as the lone 8s of train1 col 0 do; the branch leaves them apart).
            - `$NoStack`: drops `stack-runs`: runs never join across `run_axis`. Fails Fit at train1 (the 8s at lattice (0,0), (1,0) join across rows 12–13).
            - `$BboxJoin`: replaces `join-runs` and `stack-runs`: each 4-connected like-colored component paints its bounding box. Fails Fit at train0 (the 8 component's box covers the 4 at (3,1)).
            - `$ConnectedJoin`: replaces `join-runs` and `stack-runs`: the line between any two like-colored neighbors, on either axis, is painted. Fails Fit at train0 (rows 18–19 cols 2–11 are `bg`, and the branch paints them 8).
            - `$RectOnly`: replaces `join-runs` and `stack-runs`: a component that fills its bounding box draws as one rectangle, and any other component's tiles stay apart. Fails Fit at train0 (the 8s at (2,0), (2,1) join).
            - `$FewestRects`: replaces `join-runs` and `stack-runs`: each component draws as a partition into the fewest rectangles. Fails Fit at train2 (the 8 component takes 3 rectangles, row 0 cols 1–3, col 3 rows 1–3, and (2,2), and the output draws 4).
        - `adjacency`: which like-colored tiles count as neighbors for joining
            - `concept`: tiles in neighboring lattice slots
            - `$SkipEmpty`: replaces the neighbor condition in `join-runs` and `stack-runs`: like-colored tiles on one line join across empty (`bg`) slots between them. Fails Fit at train2 (the 8s at lattice (3,1), (3,3) stay apart, output rows 20–23 cols 12–19 `bg`).
    - `$NoJoin`: drops `join-runs` and `stack-runs`: every tile draws alone. Fails Fit at train0 (the 4s at lattice (0,0), (0,1) join across cols 12–13).
- `border`: the width of the line on each grid's border
    - `concept`: the grid's line width (`in_line`, `out_line`), a line on every side
    - `$SeparateMargin`: replaces the border part of `dot-lattice` and `canvas`: each grid's border takes a width of its own, parameters `in_border` (1) and `out_border` (2); defined wherever the concept is. Fits every pair. Witness `wide-border` (train3's input at `out_border` 4): stands at that assignment, variant, verdict `$SeparateMargin`; it breaks the invariant that every input's border is as wide as its inner lines.
- `tiling`: how the canvas between its lines is cut into tiles
    - `concept`: equal tiles on each axis that fill the canvas; undefined when a count breaks `counts-fit`
    - `$CenteredFloorTiles`: replaces `canvas` on inputs that break `counts-fit`: tiles take the largest whole size that fits, and the leftover cells split evenly between the two borders; defined on every input. Fits every pair. Witness `five-tiles` (a 5×1 lattice `6`, `4`, `3`, `8`, `2`): breaks `counts-fit`, foreign, verdict `$CenteredFloorTiles` (the concept is undefined); it breaks the invariant that every lattice count is 1 to 4 and divides 24.
    - `$SquareTiles`: replaces `canvas`: tiles are square, sized by the larger count. Fails Fit at train0 (tiles 4×10).
- `join` & `border`: `$NoJoin` & `$SeparateMargin` draws every tile alone on a canvas whose border takes its own width.
- `join` & `tiling`: `$NoJoin` with a tiling branch draws every tile alone on that branch's tiles.
- `grouping` & `adjacency`: each grouping branch with `$SkipEmpty` groups as that branch does, with like-colored tiles on one line across empty slots counting as neighbors.
- `grouping` & `border`: each grouping branch with `$SeparateMargin` groups as that branch does on a canvas whose border takes its own width.
- `grouping` & `tiling`: each grouping branch with a tiling branch draws that branch's groups on that tiling's tiles.
- `adjacency` & `border`: `$SkipEmpty` & `$SeparateMargin` joins across empty slots on a canvas whose border takes its own width.
- `adjacency` & `tiling`: `$SkipEmpty` with a tiling branch joins across empty slots on that tiling's tiles.
- `border` & `tiling`: `$SeparateMargin` with a tiling branch cuts that tiling's tiles from the canvas inside its own border width.

## Open parameters
none

## Not formed
- `run_axis` V, runs along columns first: a value of a parameter, not a branch, and train0 fixes it at H.
- `out_extent` derived from the input: no input measure gives 26 (input sizes 3×5 to 9×9 all give 26×26), so it is stored.
- a canvas scaled from the input by a fixed factor: the output is 26×26 for every input size, so no factor exists.

## Issues filed
none
