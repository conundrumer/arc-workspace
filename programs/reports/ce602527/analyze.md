# ce602527

## Concept
- The concept fits every pair (train0–train3 and test0) and gives one grid on each. Its rules have a relational form, so no rule is approximated. The generator draws two small shapes and an enlarged copy of one of them, cut by the grid edge, and pairs the copied shape. The concept's matching gives that shape. It also gives the other small shape only where the copy's visible part matches both, which `one-match` excludes. No witness has verdict `other`.

## Choice points
- `scale-source`
    - `concept`: the factor is stored (`scale`: 2)
    - `$ScaleDerived`: replaces the stored factor of `enlarged-copy`, and so the `scale` parameter, with a derivation from each input: each factor k ≥ 2 at which a small shape's enlarged form has another shape's cells as its visible part. It is undefined on an input with no such k. It fits every pair. Witness `scale-three-copy`: it breaks `enlarged-copy` and stands at the stored assignment. Plausibility `variant`, verdict `$ScaleDerived`. It breaks the invariant that every input's copy enlarges by 2.
- `scale-axes`
    - `concept`: one factor scales both axes
    - `$ScalePerAxis`: replaces `enlarged-copy`, so each cell scales to a block of one factor down and another across. The parameter `scale_axis` (`AXIS_V` 2, `AXIS_H` 2) replaces `scale`. It is undefined where no small shape matches. It fits every pair. Witness `stretched-copy`: it breaks `enlarged-copy` and stands at `scale_axis` with `AXIS_H` 3. Plausibility `borderline`, verdict `$ScalePerAxis`. It breaks the invariant that every input's copy enlarges both axes by one factor.
- `copy-identity`
    - `concept`: the copy is any shape whose cells are the visible part of another shape's enlarged form
    - `$LargeByCount`: adds the claim that the copy is the shape with the most cells. It is undefined where no other shape's enlarged form matches that shape. It fits every pair. Witness `thin-copy-strip` breaks no scene claim and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that the copy has the most cells in every input (48 against 17, 28 against 9, 16 against 11, 30 against 12, 20 against 9).
    - `$LargeByEdge`: adds the claim that the copy is a shape that touches the grid edge. It is undefined where no such shape matches. It fits every pair. Witness `whole-copy`: it breaks `edge-cut` and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that the copy touches the grid edge in every input.
- `match-symmetry`
    - `concept`: the copy keeps the small shape's orientation
    - `$MatchUpToD4`: replaces `enlarged-copy`, so the copy is a D4 transform of the enlarged shape. It fails Fit at train1: the 3 shape turned a quarter turn is the 4 shape, so the output holds both small shapes.
- `block-placement`
    - `concept`: the copy's blocks start at any offset
    - `$BlockAligned`: replaces `enlarged-copy`, so the copy's blocks start at multiples of the factor from the grid's top-left corner. It fails Fit at train0, where the copy's blocks start at row 9, col 3.
- `shape-unit`
    - `concept`: a shape is every cell of one color (`color-shapes`)
    - `$Components8`: replaces `color-shapes`, so a shape is an 8-connected part of one color. It fails Fit at train0: the 8 copy splits into three parts, and no small shape matches any of them.
- `output-color`
    - `concept`: the output draws the shown shape in its own color
    - `$CopyColor`: replaces the color in `crop-shown-shape` with the copy's color. It fails Fit at train0, where the output is in 8 and the pair's output in 2.
- `shown-shape-pick`
    - `concept`: the shown shape is the one whose enlarged form matches the copy (`pick-shown-shape`)
    - `$PickMoreCells`: replaces `pick-shown-shape` with the small shape that has more cells. It fails Fit at train0, where both small shapes have 17 cells.
    - `$PickFewerCells`: replaces `pick-shown-shape` with the small shape that has fewer cells. It fails Fit at train0, where both small shapes have 17 cells.
    - `$PickNearer`: replaces `pick-shown-shape` with the small shape nearer the copy. It fails Fit at train1, where it picks the 3 shape.
    - `$PickFarther`: replaces `pick-shown-shape` with the small shape farther from the copy. It fails Fit at train0, where it picks the 3 shape.
- `scale-source` & `scale-axes`, `scale-source` & `copy-identity`, `scale-source` & `match-symmetry`, `scale-source` & `block-placement`, `scale-source` & `shape-unit`, `scale-source` & `output-color`, `scale-axes` & `copy-identity`, `scale-axes` & `match-symmetry`, `scale-axes` & `block-placement`, `scale-axes` & `shape-unit`, `scale-axes` & `output-color`, `copy-identity` & `match-symmetry`, `copy-identity` & `block-placement`, `copy-identity` & `shape-unit`, `copy-identity` & `output-color`, `match-symmetry` & `block-placement`, `match-symmetry` & `shape-unit`, `match-symmetry` & `output-color`, `block-placement` & `shape-unit`, `block-placement` & `output-color`, `shape-unit` & `output-color`, `shown-shape-pick` & `shape-unit`, `shown-shape-pick` & `output-color`: the two branches' changes applied together
- `shown-shape-pick` & `scale-source`: the pick branch's model alone, because a pick by a property reads no factor. `scale-source` stands under the concept branch of `shown-shape-pick`.
- `shown-shape-pick` & `scale-axes`: the pick branch's model alone, because a pick by a property reads no factor. `scale-axes` stands under the concept branch of `shown-shape-pick`.
- `shown-shape-pick` & `copy-identity`: the pick branch's model alone, because a pick by a property matches no shape against the copy. `copy-identity` stands under the concept branch of `shown-shape-pick`.
- `shown-shape-pick` & `match-symmetry`: the pick branch's model alone, because a pick by a property matches no shape against the copy. `match-symmetry` stands under the concept branch of `shown-shape-pick`.
- `shown-shape-pick` & `block-placement`: the pick branch's model alone, because a pick by a property places no blocks. `block-placement` stands under the concept branch of `shown-shape-pick`.

## Open parameters
- none

## Not formed
- The output as the copy's visible part, reduced by the factor: the pairs' outputs hold rows that the edge cuts from the copy. The train0 copy shows only rows 0–3 of the 2 shape, and train0 output row 4 is `2 2 2 2 2`. No reading of the pairs takes this claim.
- A stored background color: the background differs between pairs (1, 8, 2, 1, 3). No stored color fits, and the program takes the background from each input.
- The output when both small shapes match the copy: no input shows this, and `one-match` excludes it. The concept gives both grids, and the pairs give no reading that gives another output.

## Tickets filed
- 10-612_task_ce602527_analyze.md
