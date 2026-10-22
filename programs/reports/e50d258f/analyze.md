# e50d258f

## Concept
- The concept fits every pair: the patch with the most `2` cells is unique in each input, and its box is each output (`check_concept.py`).
- The concept reads a patch as a 4-connected component of non-`background` cells, and crops the input over that component's bounding box.
- The generator applies the rule as stated: no number outside the cell counts enters it, so the rule has a relational form and the concept file's rule is no approximation.
- No witness with verdict `other` stands against the concept case.

## Choice points
- `score`: what ranks the patches
    - `concept`: the count of `count_color` cells in the patch, highest wins
    - `$ExcessOverMark`: replaces `pick-most`; the score is the count of `count_color` cells less the count of `minus_color` cells, with a new parameter `minus_color` = `1`; undefined where the concept is; fits every pair
        - witness `mark-excess-differs`, at the stored assignment: breaks no scene claim; plausibility `ordinary`; verdict `concept`
    - `$FewestMark`: replaces `pick-most`; the patch with the fewest `count_color` cells wins, at `count_color` = `1`; fails Fit at train0, where the patches at (0,6) and (1,1) each hold one `1` cell and two grids result
    - `$MarkDensity`: replaces `pick-most`; the patch with the highest share of `count_color` cells among its cells wins; fails Fit at test0, where the patch at rows 6–8, cols 1–4 (3 of 12) outscores the expected patch (4 of 18); a share counts nothing the task has, so the branch also has no relational form
    - `$CountGroups`: replaces `pick-most`; the patch with the most 4-connected groups of `count_color` cells wins; fails Fit at train0, where two patches tie at two groups, and at train1
- `adjacency`: which neighbors join cells into one patch
    - `concept`: the four cardinal neighbors
    - `$DiagJoined`: replaces the patch parse under `rect-patches` and `pick-most`; diagonal neighbors join as well (`Components8`); defined wherever the concept is; fits every pair
        - witness `corner-touching-patches`, at the stored assignment: breaks `rect-patches` (two patches touch at a corner); plausibility `borderline`; verdict `concept`; it breaks the invariant that one blank row or column separates every two patches
- `crop-content`: what fills the output box
    - `concept`: the input cells inside the selected patch's bounding box
    - `$CropOwnCells`: replaces `crop`; the selected patch's own cells, with `background` on every other cell of its box; defined wherever the concept is; fits every pair
        - witness `cell-in-patch-box`, at the stored assignment: breaks `rect-patches` (a ring-shaped patch with a separate cell inside its box); plausibility `foreign`; verdict `any`; it breaks the invariant that each patch is a solid rectangle
- `count_color`: how the counted color is given
    - `concept`: stored, `2`
    - `count_color=RarestColor`: replaces `pick-most` with the count of the input's rarest color; undefined on an input with no cell of any color, which no input is; fails Fit at train0, where the rarest color is `1` and the patch at rows 6–9, cols 3–8 is picked
- `background`: how the field color is given
    - `concept`: stored, `0`
    - `background=DominantColor`: replaces `rect-patches` with the input's commonest color as the field; fails Fit at train0, where `8` (50 cells) outnumbers `0` (40 cells)
- `score` & `adjacency`, `score` & `crop-content`, `score` & `count_color`, `score` & `background`, `adjacency` & `crop-content`, `adjacency` & `count_color`, `adjacency` & `background`, `crop-content` & `count_color`, `crop-content` & `background`, `count_color` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A tiebreak among patches with the same top count: no input holds a tie, and a pick among tied patches is content the task leaves free.
- Patches that share an edge, split back into rectangles: both adjacencies join such patches into one non-rectangular component, and its split into rectangles is not determined by the cells.
- `count_color` determined as the mark color that is neither the field nor the patch body: two mark colors, `1` and `2`, meet that condition in every input, so it determines no value.
- The largest or the smallest patch: the largest fails train0 (rows 6–9, cols 3–8), and the smallest fails train0 (rows 1–4, cols 1–4).
- The patch with the fewest `8` cells: it picks rows 1–4, cols 1–4 in train0 and fails there.

## Tickets filed
- none
