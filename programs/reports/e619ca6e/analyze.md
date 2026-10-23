# e619ca6e

## Concept
- The concept fits every pair, and `work/task/e619ca6e/probe.py` reproduces each train output and the test output.
- The concept's model reads blocks as 4-connected components of non-`background` cells, and is undefined on an input where a component is not a solid rectangle, or where copies of different colors meet on one cell.
- No witness has the verdict `other`.

## Choice points
- `object-shape`
    - `concept`: each object is a solid rectangle, and the model is undefined on any other object
    - `$AnyShape`: replaces `solid-blocks` and `copy-keeps-block`; an object of any shape copies its own cells, stepped by the height and width of its bounding box; undefined nowhere the concept is defined. Fits every pair. Witness `l-shape`: breaks `solid-blocks`, at the stored assignment, `variant`, verdict `$AnyShape`; it breaks the invariant that every object is a solid rectangle.
        - `copy-content`
            - `concept`: a copy holds the object's own cells
            - `$BboxFill`: replaces `copy-keeps-block`; a copy is the object's bounding box filled in its color; undefined on an object of more than one color. Fits every pair. Witness `l-shape`: breaks `solid-blocks`, at the stored assignment, `variant`, verdict `$AnyShape`; it breaks the invariant that every object is a solid rectangle.
- `adjacency`
    - `concept`: 4-adjacency joins the cells of an object
    - `$Adj8`: replaces `solid-blocks`; 8-adjacency joins them, so blocks that meet at a corner form one object; under the concept branch of `object-shape`, undefined on such an input. Fits every pair. Witness `corner-touch`: the branch's model is undefined there, as it is on every input where it differs from the concept, so it fails Subsumption (the concept's model subsumes it); breaks `solid-blocks`, at the stored assignment, `borderline`, verdict `concept`; it breaks the invariant that blocks do not touch. The case `$AnyShape & $Adj8` is defined on `corner-touch` and differs there from `$AnyShape`.
- `object-color`
    - `concept`: an object is a component of non-`background` cells, of any colors
    - `$PerColor`: replaces `solid-blocks`; an object is a component of the cells of one color. Fits every pair. Witness `two-color-block`: breaks `solid-blocks`, at the stored assignment, `borderline`, verdict `concept`; it breaks the invariant that every input holds the one color `block_color` besides `background`.
- `background`
    - `concept`: stored, `0`
    - `background=DominantColor`: derives `background` as the commonest color of the input; undefined on an input with two commonest colors. Fits every pair. Witness `background=DominantColor`: breaks `solid-blocks`, at the stored assignment, `variant`, verdict `background=DominantColor`; it breaks the invariant that `0` is the field of every input.
- `cast-direction`
    - `concept`: stored, `cast_dirs` = {bottom-left, bottom-right}
    - `$TowardRoom`: derives the vertical part of the cast directions as the side, top or bottom, with more rows between the grid's blocks and the frame edge; undefined where the two counts are equal. Fails Fit at test 0, which has 8 rows above its blocks and 8 below.
    - `$TowardRoomPerBlock`: derives that side per block; undefined for a block with equal counts. Fails Fit at train 0, where the block at rows 13–16 has 13 rows above it and 12 below and casts down.
- `object-shape` & `adjacency`, `object-shape` & `object-color`, `object-shape` & `background`, `object-shape` & `cast-direction`, `adjacency` & `object-color`, `adjacency` & `background`, `adjacency` & `cast-direction`, `object-color` & `background`, `object-color` & `cast-direction`, `background` & `cast-direction`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Copies stepped by any amount other than the block's own height and width: the blocks of the pairs are 2×3, 3×3, 4×2 and 2×5, and every other step fails train 0 or train 1.
- Only the copies that lie wholly inside the grid: train 1 output keeps the clipped copy at rows 13–14, col 0, and train 0 output keeps clipped copies at rows 7–8, col 0.
- A staircase that stops where it meets another block or copy: in train 0, the staircase of the block at rows 3–4 crosses the one of the block at rows 6–8 at (12,16), (12,17), and both go on.
- Each copy casting both diagonals again, which fills the grid with a periodic pattern of copies: train 1 output holds only the two staircases.
- Copies cast up as well as down: no output holds a copy above its block.
- `cast_dirs` stored as one cardinal direction whose two corners give the diagonals: every value the generator gives is a pair of adjacent corners, so that encoding is equivalent to the stored set.
- `SharedColor` and `RarestColor` for `background`: `SharedColor` on one input gives both `0` and `3`, and `RarestColor` gives `3`, so each fails Fit at train 0.
- The color where copies of blocks of different colors meet: every input holds the one block color, so no pair and no variant task gives an order between colors; the concept's model is undefined there.

## Tickets filed
- none
