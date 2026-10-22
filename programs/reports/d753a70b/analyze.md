# d753a70b

## Concept
- Fits every pair: `work/task/d753a70b/probe.py` reproduces each train output and the test output.
- No witness has the verdict `other`.
- The rules have a relational form: a diamond is the cells at one taxicab distance from a center, and that distance counts cells.
- The concept is undefined where a shape fits more than one diamond, such as a single cell at a corner of the frame, which is also the clipped diamond of the largest radius around the opposite corner. `corner-single-cell` shows this, and `$NearestCenter` gives the output there.
- The concept is undefined where two output diamonds share a cell, since it gives no drawing order. No pair shows this: in every pair, the output diamonds stand at least two cells apart (Chebyshev distance), and the train 0 input's 2 and 8 diamonds, which touch at (6,12) and (7,11), are apart after the shrink.

## Choice points
- `background-source`
    - `concept`: the stored `background`, 7
    - `background=DominantColor`: the background of each input is that input's commonest color, in place of the stored value of `background`; it gives more than one value where colors tie for commonest. Fits every pair: 7 is the commonest color of each input (219 to 240 of 256 cells). Witness `background=DominantColor`: a 3x4 grid whose commonest color is the shrink color 2. Plausibility `borderline`, verdict `concept`. It breaks the invariant of the inputs that every input is 16x16 and 7 holds most of its cells.
- `change-keying`
    - `concept`: two stored colors, `shrink_color` and `grow_color`; a diamond of any other color keeps its radius
    - `$ChangeTable`: replaces `shrink`, `grow` and `keep` with a stored table `radius_change` from shape color to radius change (2 → −1, 5 → +1, 8 → 0, 9 → 0). It is undefined on an input with a shape color the table lacks. Fits every pair: every test shape color is a key of the table. Witness `third-color-grows`, at the assignment `radius_change` 2 → −1, 5 → +1, 8 → +1, 9 → 0: an 8 diamond that the concept keeps and the table grows. Plausibility `borderline`, verdict `$ChangeTable`. It breaks no invariant of the inputs. Its assignment breaks the regularity of the evidence that in each pair one color alone shrinks and one color alone grows.
- `shrink-past-zero`
    - `concept`: a single cell of the shrink color is removed (radius −1 draws no cell)
    - `$ShrinkFloor`: replaces `shrink`: the new radius is r − 1 but at least 0, so a single cell of the shrink color stays. Fits every pair: no input has a single cell of color 2. Witness `shrink-single-cell`: a single 2 cell. Plausibility `ordinary`, verdict `concept`.
- `diamond-choice`
    - `concept`: a shape is the one diamond whose in-frame cells are its cells, and the concept is undefined where more than one diamond fits
    - `$NearestCenter`: replaces the reading of `diamond-outlines`: of the diamonds a shape fits, the one of least radius. Fits every pair: each shape of the evidence fits one diamond. Witness `corner-single-cell`: a single 5 cell at (0,0), which is the radius-0 diamond around (0,0) and the radius-30 diamond around (15,15). The concept is undefined there, and `$NearestCenter` grows it to (0,1) and (1,0). Plausibility `ordinary`, verdict `$NearestCenter`.
- `object-unit`
    - `concept`: a shape is an 8-connected group of the cells of one color
    - `$MulticolorObjects`: replaces the unit of `diamond-outlines`: a shape is an 8-connected group of all non-background cells. Fails Fit at train 0: the 2 diamond around (3,12) touches the 8 diamond around (8,10) at (6,12) and (7,11), and the merged group is no diamond of one color.
- `background-source` & `change-keying`, `background-source` & `shrink-past-zero`, `background-source` & `diamond-choice`, `background-source` & `object-unit`, `change-keying` & `shrink-past-zero`, `change-keying` & `diamond-choice`, `change-keying` & `object-unit`, `shrink-past-zero` & `diamond-choice`, `shrink-past-zero` & `object-unit`, `diamond-choice` & `object-unit`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A diamond whose center lies outside the frame: every shape of the evidence has a center inside the frame, and no pair needs one outside. A center outside the frame makes more shapes fit more than one diamond, such as a corner segment of any length.
- A stored radius step in place of one: every pair changes a radius by one, and the evidence gives no other step. A step parameter whose only value is one is equivalent to the concept.
- `shrink_color` or `grow_color` derived by a proposer: a proposer that reads `ex_out` gives no value on a lone input, so its branch is undefined on every pair. The color proposers over inputs alone do not give 2 and 5 on every input: 2 outnumbers 5 in train 0 (16 to 4), and 5 outnumbers 2 in train 2 (13 to 12).
- A drawing order where two output diamonds share a cell: no pair shows two output diamonds that meet, so no source gives an order.
- Shapes as 4-connected groups: a diamond of radius 1 or more has no two 4-adjacent cells, so each cell becomes a radius-0 shape, and the model fails Fit at train 0, where the 2 diamond around (3,12) shrinks to radius 2.
- Same-color diamonds that touch (`diamonds-apart`): no input has two diamonds of one color that touch, and no source gives a reading that splits such a group.

## Tickets filed
- none
