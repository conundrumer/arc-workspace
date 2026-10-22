# d6542281

## Concept
- Fits every pair (`probe.py pairs`); every claim has a relational form, so no rule is approximated.
- Undefined where two kept copies give one cell two colors. `close-fragments` is such an input: three ring copies that each cover one dot of two fragments cover sets that no other copy contains, so they are kept and disagree on cells. Its verdict is `$MostDotsPerDot`, which that branch lists.
- No witness with verdict `other`.

## Choice points
- `object-adjacency`
    - `concept`: objects are 8-connected.
    - `$Adjacency4`: replaces `shapes`, `dots`: objects are 4-connected; no parameter; undefined where kept copies conflict. Fails Fit at train0: the 8 at (12,8) of the 3 8 shape meets the rest only at a corner, so it becomes a dot.
- `background`
    - `concept`: the commonest color of the input.
    - `$BackgroundByCorner`: replaces `background`: the color of the top-left cell is the background; no parameter; undefined where kept copies conflict. Fits every pair. Witness `shape-at-corner` (train2 moved up a row, so the shape's 1 sits at (0,0)): breaks no scene claim; at the stored assignment; plausibility `ordinary`; verdict `concept`.
- `shape-test`
    - `concept`: an object of more than one color is a shape, and an object of one color is dots.
    - `$ShapeBySize`: replaces `shapes`, `dots`: an object with at least `shape_min_size` cells is a shape, and a smaller one is dots; parameter `shape_min_size`; undefined where kept copies conflict. Fits every pair at 3, 4 and 5. Witness `two-color-fragment` (train1 with its dots replaced by the touching 4 2 at (10,7), (10,8)): breaks `dots`; at the stored assignment, every open value giving one output; plausibility `variant`; verdict `$ShapeBySize`, which `$ShapeByContainment` shares; invariant broken: every fragment object in the inputs holds one color.
    - `$ShapeByContainment`: replaces `shapes`, `dots`: an object whose translate lies on a larger object's cells, color for color, is dots, and every other object is a shape; no parameter; undefined where kept copies conflict. Fits every pair. Witness `two-color-fragment`: as for `$ShapeBySize`, verdict `$ShapeByContainment`.
- `kept-placements`
    - `concept`: a placement is kept when no other placement covers a proper superset of its dots.
    - `$AllPlacements`: replaces `largest-match`: every placement is kept; no parameter; undefined where kept copies conflict. Fails Fit at train0 (a second copy of the 3 8 shape over the 8 at (4,12) alone) and at train1 (a second copy over the 4 at (9,6) alone).
    - `$GroupByReach`: replaces `largest-match`: dots within `group_reach` cells of each other on both axes join one group, and a group is completed at each placement whose covered dots are exactly that group; parameter `group_reach`; undefined where kept copies conflict. Fits every pair at 2, 3 and 4. Witness `near-groups` (test0 with its lone 4 moved to (21,17), two cells from the 3 3 fragment): breaks no scene claim; at the stored assignment, every open value giving one output; plausibility `variant`; verdict `concept`; invariant broken: every two fragments of an input sit at least 6 cells apart.
    - `$UniqueDotPlacement`: replaces `largest-match`: a dot that exactly one placement covers keeps that placement; no parameter; undefined where kept copies conflict. Fits every pair. Witness `common-color-fragment` (train1 with its dots replaced by 2 2 at (9,7), (9,8), the shape's top row): breaks no scene claim; at the stored assignment; plausibility `variant`; verdict `concept`; invariant broken: no fragment holds a cell of its shape's commonest color.
    - `$MostDotsPerDot`: replaces `largest-match`: each dot keeps the placements that cover it and cover the most dots; no parameter; undefined where kept copies conflict. Fits every pair. Witness `close-fragments` (a 5 ring with a 2 center, and two fragments of three 5s each two columns apart): breaks no scene claim; at the stored assignment; plausibility `variant`; verdict `$MostDotsPerDot`; invariant broken: every two fragments of an input sit at least 6 cells apart.
- `copy-past-edge`
    - `concept`: every cell of a placed shape lands inside the grid.
    - `$PlaceOffGrid`: replaces `placement`, `copies-fit`: a placement may reach past the grid edge, and its copy draws only its cells inside the grid; no parameter; undefined where kept copies conflict. Fits every pair. Witness `copy-past-edge` (train0 with its lone 4 moved to (18,17), on the bottom row): breaks `copies-fit`; at the stored assignment; plausibility `variant`; verdict `$PlaceOffGrid`; invariant broken: every copy fits inside the grid.
- `copy-over-cells`
    - `concept`: every cell of a placed shape lands on background or on a dot of its color.
    - `$PlaceOverAny`: replaces `placement`, `copies-fit`: a placed shape's cells may land on any cell, they cover the dots of their color they land on, and the copy draws only on background; no parameter; undefined where kept copies conflict. Fits every pair. Witness `copy-over-shape` (test1 with its 1 at (11,6) moved to (7,1), where its copy would put an 8 on the 3 at (5,3)): breaks `copies-fit`; at the stored assignment; plausibility `borderline`; verdict `$PlaceOverAny`; invariant broken: every copy lands clear of the shapes and of other fragments.
- `copy-orientation`
    - `concept`: a shape is placed by translation alone.
    - `$MatchUpToD4`: adds to `placement`: each D4 image of a shape is placed too; no parameter; undefined where kept copies conflict. Fails Fit at train0: the lone 4 at (10,14) is covered alone by several turned copies, and they conflict.
- `copy-anchor`
    - `concept`: a placement takes any shape cell onto a dot of its color.
    - `$AnchorByRarestColor`: replaces `placement`: a placement takes a cell of the shape's rarest color onto a dot; no parameter; undefined where kept copies conflict. Fails Fit at train2: the shape's rarest color is 3, and no dot is 3.
- `uncovered-dots`
    - `concept`: a dot that no kept copy covers keeps its color.
    - `$EraseUncovered`: adds to `stamp`: a dot that no kept copy covers turns to background; no parameter; undefined where kept copies conflict. Fits every pair. Witness `stray-dot` (train0 with a 9 at (16,15), a color no shape holds): breaks `dots-from-one-shape`; at the stored assignment; plausibility `borderline`; verdict `concept`; invariant broken: a kept copy covers every dot.
- `object-adjacency` & `background` & `shape-test` & `kept-placements` & `copy-past-edge` & `copy-over-cells` & `copy-orientation` & `copy-anchor` & `uncovered-dots`, each two of them: the two branches' changes applied together.

## Open parameters
- `shape_min_size`: 3, 4, 5, under `$ShapeBySize`
- `group_reach`: 2, 3, 4, under `$GroupByReach`

## Not formed
- Drawing only the cells a copy adds, in place of the whole copy: a copy agrees with every dot it covers and lands elsewhere on background, so the two draw one output on every input.

## Tickets filed
- none
