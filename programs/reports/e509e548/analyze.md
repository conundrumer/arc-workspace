# e509e548

## Concept
- Fits every pair (`work/task/e509e548/probe.py`). Every drawing in the evidence is an L, a U, or a branched drawing with one T junction and one bend. Under this concept, a drawing outside those kinds is red.
- No witness has the verdict `other`, and the rule has a relational form.

## Choice points
- `drawing-class`: what decides a drawing's color
    - `concept`: the drawing's kind: an L (one bend) is blue, a U (two bends that turn the same way) is magenta, and any other drawing is red
    - `$CornerCount`: replaces `three-kinds` and `recolor-by-kind`. The color is looked up in a stored table by the drawing's corner count, which counts, at each cell, the pairs of one vertical and one horizontal neighbor. A T junction counts two. Parameter `corner_color`: 1 → 1, 2 → 6, 3 → 2. Undefined on a drawing whose count has no entry. It fits every pair, and every test count is a train key.
        - witness `t-no-bend`: a T with no bend has two corners, so this branch gives magenta and the concept gives red. It breaks no scene claim, and it breaks the invariant that each branched drawing has one bend besides its junction. Plausibility `variant`, verdict `concept`.
    - `$AnyTwoBends`: replaces `three-kinds` and `recolor-by-kind`. Every unbranched path with two bends is magenta, whichever way the bends turn. Parameters as the concept. Defined everywhere. It fits every pair.
        - witness `z-path`: a Z (two bends that turn opposite ways) is magenta here and red under the concept. It breaks `three-kinds`, and the invariant that the bends of every unbranched drawing turn the same way. Plausibility `variant`, verdict `concept`.
    - `$PathNotL`: replaces `three-kinds` and `recolor-by-kind`. Red marks a drawing with a junction, an L is blue, and every other unbranched drawing is magenta. Parameters as the concept. Defined everywhere. It fits every pair.
        - witness `three-bend-path`: a path with three bends that turn the same way is magenta here and red under the concept. It breaks `three-kinds`, and the invariant that every unbranched drawing has one or two bends. Plausibility `variant`, verdict `concept`.
    - `$SeenKindsOnly`: replaces `recolor-by-kind`. An L is blue, a U is magenta, and a drawing with one T junction is red. Undefined on any other drawing. It fits every pair. It fails Subsumption, because the concept subsumes it.
        - witness `three-bend-path`: this branch is undefined there, and the concept gives red. It breaks `three-kinds`. Plausibility `variant`, verdict `concept`.
    - `$RunCount`: replaces `three-kinds` and `recolor-by-kind`. The color is looked up in a stored table by the count of maximal straight runs. It fails Fit at train0, because the U at (4,12) and the branched drawing at (3,3) both have three runs and take 6 and 2.
    - `$ShapeTable`: replaces `three-kinds` and `recolor-by-kind`. The color is looked up in a stored table by the drawing's shape up to D4. It fails Fit at test0 (unseen key), because the drawings at (0,1), (11,1), (4,6) and (0,12) have shapes that no train drawing has.
- `drawing-adjacency`: which cells join into one drawing
    - `concept`: 4-adjacency, with no two drawings touching, even at a corner
    - `$Corner8`: replaces `thin-drawings`. Cells that touch at a corner join into one drawing (8-adjacency), and each such drawing is classed as the concept classes it. Defined everywhere. It fits every pair, because no two drawings in the evidence touch.
        - witness `corner-contact`: an L and a U that touch at one corner are two drawings, blue and magenta, under the concept. Under this branch they are one drawing of no kind, which is red. It breaks `thin-drawings`, and the invariant that drawings are at least one cell apart, diagonals included. Plausibility `borderline`, verdict `concept`.
- `drawing-class` & `drawing-adjacency`: the two branches' changes applied together. The `drawing-class` branch's classifier classes each 8-connected drawing.

## Open parameters
- none

## Not formed
- Cell count as the class: in train0, drawings of 8 cells are U, L and branched, so no table keyed by size fits.
- Endpoint count alone: an L and a U both have two ends, so this count gives no class that tells them apart. With bends added, it is the concept.
- Mirror class of the drawing, read as in a09f6c25: the L at train0 (13,6) and the U at train0 (15,15) have unequal arms and no mirror, so the reading gives them no class.
- A derived `kind_color`: the colors 1, 6 and 2 are in no input, so no source in the evidence holds them.

## Tickets filed
- none
