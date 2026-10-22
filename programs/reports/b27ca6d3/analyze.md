# b27ca6d3

## Concept
- Fits every pair (`check_concept.py`, `probe_branches.py`). No witness has the verdict `other`. As the generator applies it, the rule is: each group of `pair_size` marks joined by shared sides gets a `frame`-colored outline on the background cells that touch it at a side or a corner. For a two-cell bar, those cells are the ring around the bar's box. The concept file's rule states this directly, so it approximates nothing.
- Invariants of the inputs that the scene claims leave out:
    - every input holds at least one pair
    - no mark lies among a pair's eight neighbors
    - the background is the commonest color, and the marks are the rarest
    - every group with more than one cell is a straight bar

## Choice points
- `grouping` (which marks join one group)
    - `concept`: marks that share a side (4-adjacency)
        - `frame-target` (which cells near a pair the frame paints)
            - `concept`: background cells only
            - `$FrameOverMarks`: adds no claim; it replaces `frame` so that every cell that touches the pair and is not in it takes the frame color, a lone mark included. Defined on every input. Fits every pair. Witness `mark-in-frame`: breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks the invariant "no mark lies among a pair's eight neighbors", which holds over 9 pairs with 18–28 marks per grid.
    - `$Join8`: replaces `pick-pairs` so that marks touching at a corner join a group (8-adjacency). Defined on every input. Fails Fit at test0: the corner-touching marks at (9,6), (10,7) and at (15,7), (16,8) would be framed.
- `selection` (which groups get a frame)
    - `concept`: groups of exactly `pair_size` cells
    - `$SizeAtLeast`: replaces `pick-pairs` so that groups of at least `pair_size` cells are framed. Defined on every input. Fits every pair. Witness `three-bar`: breaks scene claim `marks`. Plausibility `variant`, verdict `concept`. It breaks the invariant "every group has one cell or two".
    - `$LargestSize`: replaces `pick-pairs` and the stored `pair_size` with a value derived by clauses: the size of the largest group in the input. Undefined on an input with no marks. Fits every pair. Witness `three-bar`: breaks scene claim `marks`. Plausibility `variant`, verdict `concept`. It breaks the invariant "every group has one cell or two".
    - `$ShapeMatch`: replaces `pick-pairs` and `pair_size` with a stored parameter `footprint`: a group is framed when its shape is the footprint up to D4. The footprint is the two-cell bar. Defined on every input. Fits every pair. Witness `bar-and-l`, at assignment `pair_size` = 3, `footprint` = the three-cell bar: breaks no scene claim at that assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant "every group with more than one cell is a straight bar".
- `frame-cells` (which cells form a group's frame)
    - `concept`: the cells that touch the group at a side or a corner
    - `$BoxRing`: replaces `frame` so that the frame is the ring one cell outside the group's bounding box. Defined on every input. Fits every pair. Witness `l-tromino`, at assignment `pair_size` = 3: breaks no scene claim at that assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant "every group with more than one cell is a straight bar".
    - `$SideNeighbors`: replaces `frame` so that only the cells that share a side with the group take the frame color. Defined on every input. Fails Fit at train0: the corner cells (1,6), (1,8), (4,6), (4,8) stay 0.
- `background` (`@derive` point on `background`)
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input. Defined where one color is commonest. Fits every pair. Witness `background=DominantColor`: breaks no scene claim. Plausibility `foreign`, verdict `concept`. It breaks the invariant "the background is the commonest color".
    - `background=SharedColor`: every color of the input, here 0 and 2. Fails Fit at train0: the pair's own cells touch each other, so they take the frame color.
    - `background=VanishedColor`: with `ex_out` empty, every color of the input, which is the same as `background=SharedColor`. Fails Fit at train0.
- `mark` (`@derive` point on `mark`)
    - `concept`: stored, 2
    - `mark=RarestColor`: the rarest color of the input. Defined on every input. Fits every pair. Witness `mark=RarestColor`: breaks no scene claim. Plausibility `foreign`, verdict `concept`. It breaks the invariant "the marks are the rarest color".
    - `mark=SharedColor`: every color of the input. Every cell is then a mark, the whole grid is one group, and nothing is framed. Fails Fit at train0.
    - `mark=VanishedColor`: with `ex_out` empty, every color of the input, which is the same as `mark=SharedColor`. Fails Fit at train0.
    - `mark=UnchangedColor`: reads `ex_out`, which is empty in a run, so it gives no value and the model is undefined on every input. Fails Fit at train0.
- `frame` (`@derive` point on `frame`)
    - `concept`: stored, 3
    - `frame=OutNewColor`, `frame=AnyOutNewColor`: each reads `ex_out`, which is empty in a run, so it gives no value and the model is undefined on every input. Fails Fit at train0.
- `grouping` & `selection`, `grouping` & `frame-cells`, `grouping` & `background`, `selection` & `frame-cells`, `selection` & `frame-target`, `selection` & `background`, `frame-cells` & `background`, `frame-target` & `background`: the two branches' changes applied together
- `frame-cells` & `frame-target`: the two branches' changes applied together
    - `$SideNeighbors` & `$FrameOverMarks`: the model of `$SideNeighbors` alone. A cell that shares a side with a group is never a mark outside that group.
- `mark` & each other point: the two branches' changes applied together
    - `mark=SharedColor` & any branch, `mark=VanishedColor` & any branch: the model of the `mark` branch alone. The whole grid is one group, so no frame cell lies in the grid.
    - `mark=UnchangedColor` & any branch: the model of `mark=UnchangedColor` alone, undefined on every input.
- `frame` & each other point: the two branches' changes applied together
    - `frame=OutNewColor` & any branch, `frame=AnyOutNewColor` & any branch: the model of the `frame` branch alone, undefined on every input.
- The points under these degenerate derivation branches stay at the concept. Each of those properties exists with the stored branch and with every defined derivation branch of the point, and the degenerate branches all fail Fit.

## Open parameters
none

## Not formed
- `pair_size` derived by a proposer: no proposer in `programs/proposers.dl` gives the size of a group. The only clause derivation, the largest group's size, is formed as `$LargestSize`.
- `background`, `mark`, `frame` derived by `ChangedColor`, `RarestColor`, `DominantColor` and the other color proposers not listed above: with `ex_out` empty, `ChangedColor` gives no value, like `UnchangedColor`. `background=RarestColor` sets the background to 2 and `mark=DominantColor` sets the marks to 0 on every pair, the opposite of the scene, and each fails Fit at train0. The count and dim proposers give no color.
- A frame color chosen by the bar's axis or by any other property of the pair: every frame in the outputs is 3, and nothing in the pairs separates such a reading.
- A frame wider than one cell, or a frame stamped as a stored footprint around each pair: on a two-cell bar the stored ring and the eight-neighbor halo are the same cells at every assignment that `pair_size` reaches. The width has no value but 1 that a reader of the concept could take.

## Tickets filed
- 10-283_task_b27ca6d3_analyze.md
