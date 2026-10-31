# edb79dae

## Concept
- Fits every pair (train0, train1, test0), checked by `work/task/edb79dae/check_concept.py` and `work/task/edb79dae/probe.py`. No witness has verdict `other`. The concept file's rules are the rule as the generator applies it: the output is the frame cut out with its outline; each solid square becomes the stencil drawn in its color outside the frame, placed by bounding box and painted in the target color of the key whose source is the square's color (one step: test0's chain 3→9→2→1→6 paints 3 squares in 9); every other cell is background.
- The concept is undefined where a stencil's bounding box differs from its square's size, where a square's color sources no key or has no stencil, and where no component of `frame_color` stands. `scaled-stencil`, `unkeyed-square` and `recolored-frame` hit these cases.

## Choice points
- `key-source`: which of a key's two colors is the source
    - `concept`: the color whose half pokes one cell into the other's (it holds the cell with three 4-neighbors of the other color); undefined where no cell or both colors hold one
    - `$KeySourceBySide`: replaces `keys`: the source is the color of the key's column on the side `key_side` stores (`key_side`: L); undefined where that column holds both colors or two keys share a source with different targets. Fits every pair. Witness `$KeySourceBySide` (every key mirrored in place, with keys 1→3, 3→2, 2→1 by the poke, so the side reading reverses each): stands at the stored assignment, breaks no scene claim, plausibility `variant`, breaks the invariant "every key's source color stands on its left", verdict `concept`.
    - `$KeySourceByCount`: replaces `keys`: the source is the key color with more cells; undefined where the counts tie. Fits every pair. Witness `wide-keys` (keys 3 by 5, so the poking color has 7 cells to the other's 8): stands at the stored assignment, breaks `keys` (`key_shape`), plausibility `variant`, breaks the invariant "every key is a 3 by 4 block", verdict `concept`.
    - `$KeySourceBySquare`: replaces `keys`: the source is the key color that has squares in the frame; undefined where both or neither do. Fails Fit at test0: key 3→9 has squares of both 3 and 9.
- `map-steps`: how many key steps a square's color takes
    - `concept`: one step
    - `$MapTransitive`: replaces `stamp-stencil`: the paint is the color reached by following keys until a color sources none; undefined on a key cycle. Fails Fit at test0: 3 squares are painted 9 in the output, and the chain gives 6.
- `stencil-parse`: what a color's stencil is
    - `concept`: every cell of that color outside the frame and outside every key, wherever it lies
    - `$StencilByComponent`: replaces `stencils`: a stencil is one 4-connected object, and a color whose cells lie in several parts has none (undefined). Fails Fit at test0: the 8 stencil (rows 1–5, cols 18–22) has a separate part at (1,22), (2,22).
- `stencil-size`: a stencil whose bounding box is not the square's size
    - `concept`: undefined
    - `$StencilScaled`: adds to `stamp-stencil`: the stencil is scaled up by the whole quotient of the square's size by its bounding box; undefined where that quotient is not whole. Fits every pair. Witness `scaled-stencil` (train0's keys and 3 by 3 stencils, with 6 by 6 squares in a 17 by 17 frame): stands at the stored assignment, breaks `stencils` (bounding box k by k), plausibility `borderline`, breaks the invariant "each stencil's bounding box equals the size of the squares of its color", verdict `$StencilScaled`.
- `unkeyed-square`: a square whose color sources no key or has no stencil
    - `concept`: undefined
    - `$KeepUnkeyed`: adds to `stamp-stencil`: such a square keeps its input cells. Fits every pair. Witness `unkeyed-square` (train0 with key 1→4 removed): stands at the stored assignment, breaks `one-key-per-color`, plausibility `borderline`, breaks the invariant "every square color is the source of a key", verdict `$IdentityUnkeyed`.
    - `$IdentityUnkeyed`: adds to `stamp-stencil`: a square whose color sources no key takes its stencil in its own color; undefined where the color has no stencil. Fits every pair. Witness `unkeyed-square`: as for `$KeepUnkeyed`, verdict `$IdentityUnkeyed`.
- `frame-find`: how the frame is found
    - `concept`: the component of the stored `frame_color` (5)
    - `$FrameByOutline`: replaces `frame` and drops `frame_color`: the frame is the one single-color component that is the outline of its bounding box, at least 3 by 3; undefined where there is none or more than one. Fits every pair. Witness `recolored-frame` (train0 with the frame in 6): stands at the stored assignment, breaks `frame` (`frame_color`), plausibility `variant`, breaks the invariant "the frame is 5", verdict `$FrameByOutline`.
- `key-source` & `map-steps`, `key-source` & `stencil-parse`, `key-source` & `stencil-size`, `key-source` & `unkeyed-square`, `key-source` & `frame-find`, `map-steps` & `stencil-parse`, `map-steps` & `stencil-size`, `map-steps` & `unkeyed-square`, `map-steps` & `frame-find`, `stencil-parse` & `stencil-size`, `stencil-parse` & `unkeyed-square`, `stencil-parse` & `frame-find`, `stencil-size` & `unkeyed-square`, `stencil-size` & `frame-find`, `unkeyed-square` & `frame-find`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The stencil chosen by the key's target color: no input has a stencil in any target color of train0 (4, 2), so the model gives no output on train0 and states no reading a person could hold.
- Cropping to the frame's interior: every output keeps the 5 outline.
- Stencil-free cells of a square keeping the square's color: every output has background there.
- `frame_color` derived by a proposer: none gives 5 alone. SharedColor gives every color of an input, DominantColor gives the background, RarestColor and VanishedColor give key or square colors.
- Stencils matched up to a stored D4 transform (`congruent`): every pair places them untransformed, and no variant task turns them, so the transform's values range over the identity alone and the model is equivalent to the concept's.

## Tickets filed
- none
