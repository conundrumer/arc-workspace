# b9b7f026

## Concept
- Fits every pair: each input holds one rectangle with a background region closed off from the frame edge (4-adjacent walk through `bg` cells) inside its box, and every output is that rectangle's color as a 1×1 grid (`probe.py`).
- An object is a 4-connected component of one non-`bg` color, so the test input's touching rectangles of colors 5 and 8 stay apart.
- Every rule has a relational form (Closed, Components, Bbox), and no witness has the verdict `other`.
- Where no rectangle holds a closed hole, the concept case is undefined; where several do, it gives one grid per color.

## Choice points
- `pick`: which rectangle the output takes its color from
    - `concept`: a rectangle with a cell that a walk closes off from the frame edge
        - `walk-set`: which cells the walk runs through, and how a closed cell picks the rectangle
            - `concept`: the walk runs through `bg` cells, and the rectangle's box holds a closed cell
            - `$HoleNeighbors`: replaces `holed-color`: the rectangle 4-adjacent to a closed `bg` cell. Fits every pair. Witness `hole-neighbors`: a dot of another color inside the hole; breaks no scene claim; `borderline`, verdict `concept`; breaks the invariant that no rectangle lies inside the box of another one.
            - `$OwnEnclosure`: replaces `one-holed`: the walk runs through the cells outside the rectangle, and the rectangle closes off some cell. Fits every pair. Witness `own-enclosure`: a hollow rectangle whose hole another rectangle fills whole; breaks `one-holed`; `borderline`, verdict `$OwnEnclosure`; breaks the invariant that a hole holds `bg` cells. It is not subsumed by `$NotSolid`: with a solid rectangle beside it, a notched rectangle and a holed rectangle make `$OwnEnclosure` give the holed one and `$NotSolid` give both.
        - `walk-adjacency`: the adjacency of the walk
            - `concept`: 4-adjacency
            - `$Walk8`: replaces `one-holed`: the walk also steps diagonally. Fits every pair. Witness `walk8`: an outline whose missing corner meets its hole at a corner, beside a holed rectangle; breaks `rectangles` and `one-holed`; `foreign`, verdict `concept`; breaks the invariant that every shape is a whole rectangle.
    - `$NotSolid`: replaces `one-holed` and `holed-color`: the rectangle whose box holds a cell outside it; no walk; undefined where every rectangle fills its box. Fits every pair. Witness `not-solid`: a rectangle whose hole opens through one wall; breaks `one-holed`; `borderline`, verdict `$NotSolid`; breaks the invariant that the one hole is closed off from the outside. It is not subsumed: on that witness, every other case is undefined.
    - `$CountRank`: replaces `one-holed` and `holed-color`: the rectangle with the most or the fewest cells. Fails Fit at train0: color 6 has 10 cells, color 2 has 15 and color 1 has 4.
- `object`: what one rectangle is
    - `concept`: a 4-connected component of one non-`bg` color
    - `$ColorClass`: replaces `rectangles`: all the cells of one color form one rectangle. Fits every pair. Witness `color-class`: two solid rectangles of one color at opposite corners, whose joint box holds the hole; breaks `rectangles`; `variant`, verdict `concept`; breaks the invariant that no two rectangles share a color.
    - `$Object8`: replaces `rectangles`: the component joins diagonal neighbors (8-adjacency). Fits every pair. Witness `object8`: two solid rectangles of one color that touch at a corner, whose joint box holds the hole; breaks `rectangles`; `borderline`, verdict `concept`; breaks the invariant that no two rectangles share a color.
- `bg`: the background color
    - `concept`: stored, 0
    - `bg=DominantColor`: the commonest color of the input. Fits every pair. Witness `bg=DominantColor`: a solid rectangle with more cells than the background; breaks no scene claim; `borderline`, verdict `concept`; breaks the invariant that `bg` is the commonest color.
    - `bg=RarestColor`: the rarest color of the input. Fails Fit at train0: it takes 1 as background and gives 0.
    - `bg=SharedColor`: each color of the one input. Fails Fit at train0: every cell is background, and it is undefined.
    - `bg=VanishedColor`: each color of the one input, since `ex_out` is empty. Fails Fit at train0: as for `bg=SharedColor`.
- `pick` & `object`, `pick` & `bg`, `object` & `bg`, `object` & `walk-set`, `object` & `walk-adjacency`, `bg` & `walk-set`, `bg` & `walk-adjacency`, `walk-set` & `walk-adjacency`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A rank among several holed rectangles: no pair holds more than one, and the pairs give no order to rank them by.
- An output sized by the hole or the rectangle: every train output is 1×1, and train0's hole is 2×1.

## Tickets filed
- 10-440_task_b9b7f026_analyze.md
- 10-441_task_b9b7f026_analyze.md
