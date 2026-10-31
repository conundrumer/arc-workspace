# bd14c3bf

## Concept
- The concept case fits every pair (`probe.py pairs`), under each value of `match_group`. It is undefined on an input with no `ref_color` cell.
- No witness has the verdict `other`.
- `stretch-match` has a relational form: the reduction removes each row or column of a shape's box that equals the one before it, and the match compares the reduced grids under the elements of `match_group`. The generator's rule as restated is the concept file's rule, with no approximation.

## Choice points
- `shape-match`: when a mark shape counts as the reference shape
    - `concept`: `stretch-match`, the reduced boxes are equal under `match_group`
    - `$Topology`: replaces `stretch-match` with "a mark shape matches when its box has as many enclosed background parts and as many background parts that reach the box edge as the reference's box", reads no `match_group`, undefined nowhere the concept is defined. Fits every pair. Witness `t-shape`: a train1-like scene with a blue T beside a stretched H. It breaks no scene claim, stands at the stored assignment, `ordinary`, verdict `concept`.
    - `$Congruent`: replaces `stretch-match` with "the boxes are equal under `match_group`, with no reduction". Fails Fit at train0, train1, train2 and test0.
    - `$UniformScale`: replaces `stretch-match` with "the boxes, each shrunk by its largest whole scale factor, are equal under `match_group`". Fails Fit at train0, train1, train2 and test0.
    - `$HoleCount`: replaces `stretch-match` with "the boxes enclose the same number of background parts". Fails Fit at train0 and train1.
    - `$SymmetryType`: replaces `stretch-match` with "the shape has the same symmetry subgroup as the reference, up to conjugation". Fails Fit at train0: the kept `1 0 1 / 1 1 1 / 1 0 1 / 1 0 1` at rows 1–4, cols 12–14 has one mirror axis, as the reference C does.
- `adjacency`: which cells join into one shape
    - `concept`: 4-adjacency
    - `$Adjacency8`: replaces the 4-connected shapes of `mark-shapes` with 8-connected shapes, undefined nowhere the concept is defined. Fits every pair. Witness `corner-touch`: a stretched U that matches the reference C touches a blue H at a corner. It breaks `mark-shapes`, stands at the stored assignment, `borderline`, verdict `concept`. Invariant of the inputs it breaks: no two shapes touch, even at a corner.
- `candidate-shapes`: which shapes are tested against the reference
    - `concept`: the shapes of `mark_color`
    - `$AnyColor`: replaces `mark_color` in `mark-shapes` and `recolor-match` with "each shape of a color other than `background` and `ref_color`", so it reads `background` and no `mark_color`, undefined nowhere the concept is defined. Fits every pair. Witness `green-shape`: a green ring and a blue ring beside the red reference ring. It breaks `mark-shapes`, stands at the stored assignment, `borderline`, verdict `$AnyColor`. Invariant of the inputs it breaks: every non-background cell other than the reference is 1.
        - `background`: how the background is found
            - `concept`: stored `background` (0)
            - `background=DominantColor`: derives `background` as the commonest color of the input, undefined where two colors tie for commonest. Fits every pair (`probe_bg.py`). Witness `background=DominantColor`: blue outnumbers black, and a blue frame encloses a black ring around a lone blue cell. It breaks no scene claim, stands at the stored assignment, `foreign`, verdict `$AnyColor`. Invariant of the inputs it breaks: the background is the commonest color.
- `ref_color`: how the reference color is found
    - `concept`: stored `ref_color` (2)
    - `ref_color=RarestColor`: derives `ref_color` as the input's rarest color, replacing the stored value in `reference-shape`. Undefined where two colors tie for rarest. Fits every pair. Witness `ref_color=RarestColor`: one blue arch, with fewer cells than the red C. It breaks no scene claim, stands at the stored assignment, `borderline`, verdict `concept`. Invariant of the inputs it breaks: the inputs hold more `mark_color` cells than `ref_color` cells.
    - `$CornerReference`: derives `ref_color` as the color of the input's `ref_corner` cell, so the reference is the shape at that corner, replacing the stored value in `reference-shape`. Undefined where that cell is background. Fits every pair. Witness `green-reference`: a green ring at the corner, no red cell, and a stretched blue ring. The concept is undefined there. It breaks `reference-shape`, stands at the stored assignment, `borderline`, verdict `$CornerReference`. Invariant of the inputs it breaks: the reference is red.
- `paint_color`: the color a matching shape takes
    - `concept`: derived, the reference's color `ref_color`
    - `paint_color=stored`: stores `paint_color` (2) apart from `ref_color`, replacing `ref_color` in `recolor-match`. Undefined nowhere the concept is defined. Fits every pair. Witness `paint_color=stored`: a train0-like scene with one stretched U that matches, and `paint_color` reassigned to 3. It breaks no scene claim, `foreign`, verdict `concept`. Invariant it breaks: the input breaks none, and the assignment breaks the tie of the paint to the reference's color.
- `shape-match` & `adjacency`, `shape-match` & `candidate-shapes`, `shape-match` & `ref_color`, `shape-match` & `paint_color`, `adjacency` & `candidate-shapes`, `adjacency` & `ref_color`, `adjacency` & `paint_color`, `candidate-shapes` & `ref_color`, `candidate-shapes` & `paint_color`, `ref_color` & `paint_color`: the two branches' changes applied together

## Open parameters
- `match_group`: `SYM_C4` and `SYM_D4`. Under `SYM_C4`, a mark shape matches when its reduced box is a rotation of the reference's reduced box. Under `SYM_D4`, it matches when its reduced box is a rotation or a reflection of the reference's. The two values give the same output on every pair, and the test output has no alt.

## Not formed
- A derivation of `ref_color` by `SharedColor`, `DominantColor`, `CountRankAsc` or another color proposer other than `RarestColor`: on a single input none of them gives 2 alone (`SharedColor` gives 0, 1 and 2; `DominantColor` gives 0), so none has a reading as the reference color.
- A derivation of `mark_color` by a proposer: no proposer gives 1 alone on an input. The derived form of the candidate set is `$AnyColor`.
- A reference picked by its place rather than its color or corner, such as the smallest shape: in train1 the H at rows 0–2, cols 13–15 is as small as the reference, so that reading has no unique reference.

## Tickets filed
- none
