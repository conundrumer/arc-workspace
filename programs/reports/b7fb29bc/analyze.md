# b7fb29bc

## Concept
- Fits every pair. Each rule has a relational form: the Chebyshev distance from a cell to the dot is the larger of its row and column offsets, and its parity picks the `ring_colors` entry. No witness has the verdict `other`.
- In every input, the outline is the same 9x9 box (rows 2–10, cols 3–11) and holds a dot of the outline's color. The test dot (5,4) touches the outline on the left, and train2's dot (3,9) touches it at the top.

## Choice points
- `ring-origin`
    - `concept`: `square-rings` measures each inside cell's distance from the dot
        - `metric`
            - `concept`: Chebyshev distance, so the rings are squares
            - `$Diamond`: replaces `square-rings` with Manhattan distance to the dot, so the rings are diamonds; defined where the concept is; fails train0
        - `dot-find`
            - `concept`: the dot is the frame-color cell inside the bounding box of the frame-color cells
            - `$DotComponent`: replaces `one-dot`: the dot is a one-cell 4-connected frame-color component separate from the outline; undefined where the dot touches the outline; fails train2 (the dot (3,9) joins the top wall)
            - `$AnyInkDot`: replaces `one-dot`: the dot is the one non-background cell inside the box, of any color; defined on an input whose dot is not `frame_color`, where the concept is undefined; fits every pair; witness `ink-dot`, breaks `one-dot` (the dot is not `frame_color`), `variant`, verdict `$AnyInkDot`, breaks the invariant that every dot has the outline's color
        - `dot-count`
            - `concept`: one dot; undefined on an input with more than one
            - `$NearestDot`: replaces `one-dot` and `square-rings`: a cell's distance is its Chebyshev distance to the nearest dot, for any number of dots; fits every pair; witness `two-dots`, breaks `one-dot`, `borderline`, verdict `$NearestDot`, breaks the invariant that every box holds exactly one dot
    - `$DepthRings`: replaces `square-rings`: a cell's ring is its depth from the outline (its distance to the nearest side of the box), and no dot is read; fails train1
- `ring-color`
    - `concept`: the color derives from the parity of the distance, through `ring_colors`
    - `dist_color=stored`: replaces the parity derivation in `square-rings` with a stored per-distance color table, 1 to 6 as 4 2 4 2 4 2; undefined on an input with a distance past 6; fits every pair, since no test distance falls outside the train distances; witness `dist_color=stored`, `variant`, verdict `concept`, breaks the invariant that every input's box is the 9x9 outline at rows 2–10, cols 3–11
- `box`
    - `concept`: the box derives from the input as the bounding box of the frame-color cells
    - `box=stored`: replaces that derivation in `box-outline` with a stored box, the outline at rows 2–10, cols 3–11; undefined where its inside holds no single dot; fits every pair; witness `box=stored`, `variant`, verdict `concept`, breaks the invariant that every input's box is the 9x9 outline at rows 2–10, cols 3–11
- `region`
    - `concept`: rings fill the cells inside the outline's bounding box
    - `$EnclosedRegion`: replaces `clip-to-box`: rings fill the background cells that the frame-color cells close off from the grid edge; gives the input unchanged where the outline is broken; fits every pair; witness `broken-outline`, breaks `box-outline`, `foreign`, verdict `concept`, breaks the invariant that every outline is closed on all four sides
- `ring-extent`
    - `concept`: `clip-to-box`, so the rings stop at the outline
    - `$Unclipped`: replaces `clip-to-box`: rings fill every background cell of the grid, outside the box too; fails train0
- `ring-origin` & `ring-color`, `ring-origin` & `box`, `ring-origin` & `region`, `ring-origin` & `ring-extent`, `ring-color` & `box`, `ring-color` & `region`, `ring-color` & `ring-extent`, `box` & `region`, `box` & `ring-extent`, `region` & `ring-extent`, `metric` & `dot-find`, `metric` & `dot-count`, `dot-find` & `dot-count`, and each of `metric`, `dot-find`, `dot-count` with each of `ring-color`, `box`, `region`, `ring-extent`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A color cycle of a stored length, as in a3f84088: with a length of 2 it is the concept's model, and no task of this generator gives another length, so it fails Equivalence.
- Ring colors derived from the input: 4 and 2 appear in no input, so nothing in the input can give them.
- A separate stored `dot_color`: it equals `frame_color` in every input, so it is a redundant value. `$AnyInkDot` is the reading that finds the dot by something other than its color.
- Two-color alternation that starts from the outline (the outermost ring takes a fixed color): `$DepthRings` covers ring depth from the outline, and a stored outermost color fails train2, where the outermost ring (distance 6) is 2 and in train0 (distance 3) is 4.

## Tickets filed
- none
