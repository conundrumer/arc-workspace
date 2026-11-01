# d35bdbdc

## Concept
- Fits every train and test pair (`probe.py`). Test2's 7-box is cut off by the bottom edge, and test2's wire end (7,2) touches the side middles of both the 2-box and the 7-box; the 2-box's center 4 is no box's outer color, so `linked-boxes` leaves it unlinked, as the output has it. Test1's end (1,6) touches the 4-box and the 2-box, and both are linked.
- Relational form of a wire end: a wire cell with at most one neighbor in the wire graph, where a corner contact between two wire cells counts only when no wire cell touches both of them by a side. With that, train1's end (7,1) has one neighbor, while the corner cells of the wire have two.
- Witness `hooked-wire-end`: verdict `other`, plausibility `variant`. It breaks no scene claim: its wire has two drawn ends, (3,1) and (3,8), each next to the middle cell of a box's side. The end at (3,8) hooks back and also touches (4,7), so the degree test finds one end. It breaks the input invariant that each wire end touches no wire cell except the one before it.
    - The generator's rule: the boxes at the first and last cells of the drawn wire are linked. The degree test approximates that drawing order, and the cell set does not show that order where the wire touches itself near an end.
- Witness `self-named-box` (see `$SelfLookup`) has verdict `$SelfLookup`. There, the "another box" condition in `linked-boxes` erases a linked box that a person keeps.

## Choice points
- `link-contact`: where a wire end touches a box for the box to be linked
    - `concept`: the end is 4-adjacent to the middle cell of one of the box's sides, on the outside
    - `$AnyOuterCell`: replaces `linked-boxes`; the end is 4-adjacent to any outer cell of the box. Defined wherever the concept is. Fails Fit at train1: end (3,8) touches the 3-box's corner (2,8), which links the 3-box, and that box takes 6.
    - `$DiagonalContact`: replaces `linked-boxes`; the end is 8-adjacent to a side-middle cell. Defined wherever the concept is. Fails Fit at train1: end (3,8) is diagonal to the 3-box's bottom middle (2,7).
- `wire-end`: which wire cells are ends
    - `concept`: cells with at most one neighbor in the wire graph, where a corner contact counts only when no wire cell bridges it by sides
    - `$OneNeighborEnd`: replaces `linked-boxes`; cells with exactly one wire 8-neighbor. Defined wherever the concept is. Fails Fit at train1: end (7,1) has the two 8-neighbors (8,1) and (8,2), so the 8-box is erased.
    - `$AnyWireCell`: replaces `linked-boxes`; every wire cell counts as an end. Defined wherever the concept is. Fails Fit at train0: (6,3) is next to the 1-box's top middle, and the 1-box's center 3 names the 3-box, so the 1-box is kept.
- `self-named`: what happens to a box at a wire end whose center color is its own outer color
    - `concept`: it is not linked, since no other box has that outer color, and it is erased
    - `$SelfLookup`: replaces `linked-boxes`; the lookup may return the box itself, so the box is linked and keeps its center. Defined wherever the concept is. Fits every pair. Witness `self-named-box`: the 7-plus of test0 made solid. It breaks no scene claim, and it stands at the stored assignment. Plausibility `borderline`; it breaks the input invariant that no box at a wire end has its own outer color at its center. Verdict `$SelfLookup`.
- `unnamed`: what happens to a box at a wire end whose center color is no box's outer color
    - `concept`: it is erased
    - `$KeepUnlooked`: replaces `linked-boxes` and `erase-others`; the box is linked and keeps its center. Defined wherever the concept is. Fails Fit at test2: the 2-box at end (7,2) is kept.
    - `$UnlookedUndefined`: replaces `linked-boxes`; the box is linked and its new center is missing. Undefined on every input with such a box. Fails Fit at test2, where it is undefined.
- `lookup-source`: which center a linked box reads from the box its center names
    - `concept`: that box's input center
    - `$ReadsOutputCenter`: replaces `center-lookup`; it reads that box's center after the change, which is its new center when that box is linked too. Defined wherever the concept is. Fails Fit at test1: the 4-box reads the 2-box's new center 6, and the output has 3.
    - `$FollowChain`: replaces `center-lookup`; it follows the names from box to box until a center names no box, and takes the last center. Undefined where the names form a cycle. Fails Fit at train0: the 6-box follows 1 → 3 → 4 → 2 and gets 2, and the output has 3.
- `background`: the value of `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the input's commonest color. Undefined on an input whose commonest color is tied. Fits every pair. Witness `background=DominantColor`: a 3×12 input where 6 outnumbers 0. It breaks no scene claim, and it stands at the stored assignment. Plausibility `borderline`; it breaks the input invariants that 0 is the commonest color of every input and that every input is 10×10. Verdict `concept`.
- `wire_color`: the value of `wire_color`
    - `concept`: stored, 5
    - `wire_color=RarestColor`: the input's rarest color. Undefined on an input whose rarest color is tied. Fails Fit at train0: the rarest color is 2, the 4-box's center.
    - `wire_color=SharedColor`: every color of the input is a wire color, so no box exists and the output is the input. Defined on every input. Fails Fit at train0.
- `link-contact` & `wire-end`, `link-contact` & `self-named`, `link-contact` & `unnamed`, `link-contact` & `lookup-source`, `link-contact` & `background`, `wire-end` & `self-named`, `wire-end` & `unnamed`, `wire-end` & `lookup-source`, `wire-end` & `background`, `self-named` & `unnamed`, `self-named` & `lookup-source`, `self-named` & `background`, `unnamed` & `lookup-source`, `unnamed` & `background`, `lookup-source` & `background`: the two branches' changes applied together
- `wire_color` & each other point: the two branches' changes applied together
    - `wire_color=SharedColor` & any branch of another point: the model of `wire_color=SharedColor` alone, since no box exists under it

## Open parameters
- none

## Not formed
- Readings without the wire, where the boxes kept are the heads of the center-to-outer-color chains or alternate along a chain: in test0 the 4-plus heads the chain 4 → 2 → 3 and is erased, while the 2-plus it names is kept. No reading without the wire keeps that set.
- An end that touches two boxes links only one of them: no feature of test1's end (1,6) picks the 4-box or the 2-box, and both are kept.
- A linked box takes the center of the box at the other end of the wire: train0's 3-box would get 1, the 6-box's center, and the output has 2.
- `wire_color` from the other proposers: each one that reads `ex_out` gives no value on an input alone, and the rest give no color that only the wire has.

## Tickets filed
- none
