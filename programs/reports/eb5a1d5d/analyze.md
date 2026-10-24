# eb5a1d5d

## Concept
- Fits every pair: the layers (same-color 4-components) chain by containment from the background inward (train0 8/3/2, train1 5/6, train2 3/8/2/1, test0 2/1/3/8/2), and the output is concentric 1-wide rings in that order with the innermost as the center cell (`work/task/eb5a1d5d/probe.py pairs`).
- Witnesses with verdict `other` that no branch lists: none.
- Rule as the generator applies it: the generator draws solid rectangles on a background, each strictly inside the one before, and pairs the input with the square of concentric rings of their colors, outermost first. The concept's rules have this relational form as they stand, and no approximation stands in for them.
- Test0 shows a color recurring at two depths (2 at depth 0 and depth 4). That rules out every model that takes a layer to be a color class.

## Choice points
- `output-construction`
    - `concept`: the layers are numbered by depth, and the output's ring k takes the color at depth k (`depth-chain`, `concentric-output`)
        - `layer-unit`
            - `concept`: a layer is one same-color 4-connected component
            - `$ColorClassLayers`: replaces `depth-chain`'s layers with color classes (all cells of a color form one layer), chained by bbox containment. No parameters. Undefined where the classes' bboxes do not chain. Fails Fit at test0: color 2 holds both the background and the center, so the model finds 4 layers and gives 7x7 where 9x9 is expected.
            - `$Layers8Connected`: replaces `depth-chain`'s layers with same-color 8-connected components. No parameters. Undefined where they do not chain by containment. Fits every pair. Witness `diagonal-contact`: a 5 cell inside a notched 3 shape touches the background only at a corner. The concept gives 5/3/5 in a 5x5 and this branch gives 5/3 in a 3x3. It breaks `nested-rectangles` and stands at the stored assignment. Plausibility `foreign`, verdict `concept`. It breaks the invariant that every layer is a solid rectangle.
        - `layer-order`
            - `concept`: layers are ordered by containment (`depth-chain`)
            - `$LayersByCellCount`: replaces `depth-chain`'s order with cells counted per layer, descending. No parameters. Undefined where two layers tie on count. Fits every pair. Witness `thin-ring`: a 1-wide 3 ring (24 cells) holds a 2 block (25 cells). The concept gives 5/3/2 and this branch gives 5/2/3. It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
            - `$LayersByBboxArea`: replaces `depth-chain`'s order with bounding-box area per layer, descending, and needs no chain. No parameters. Undefined where two layers tie on area. Fits every pair. Witness `sibling-rectangles`: a 1 rectangle stands beside the 3 rectangle rather than inside it. The concept is undefined there, and this branch gives 5/3/1/2 in a 7x7. It breaks `nested-rectangles` and stands at the stored assignment. Plausibility `foreign`, verdict `any`. It breaks the invariant that every input's layers form one chain by containment.
    - `$CompressRuns`: replaces `depth-chain`, `concentric-output` and `sizes-dropped` with one rule: the output is the input with each run of identical consecutive rows, then of identical consecutive columns, collapsed to one. No parameters. Defined on every input. Fits every pair. Witness `flush-inner`: a 2 rectangle lies flush against the left edge of the 3 rectangle. The concept gives concentric 8/3/2 in a 5x5, and this branch gives a 5x4 grid that lacks the 3 column band on the left. It breaks `nested-rectangles` and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that every rectangle keeps a margin of at least 1 from each edge of its container.
- `layer-unit` & `layer-order`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `ring_width` other than 1: every pair's output draws 1-wide rings, so the pairs fix it and no other value is open.
- Innermost layer kept at its own size or aspect, or rings as wide as the input's margins: every pair refutes it (train0's 6x6 2 block and train2's 3x5 1 block both become one cell, and margins of 1 to 3 all become 1-wide rings), so no model of it fits a pair.

## Tickets filed
- none
