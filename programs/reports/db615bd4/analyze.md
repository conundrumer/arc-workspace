# db615bd4

## Concept
- The concept fits every pair, train0–2 and test0, at `gap` = 1. Every claim has a relational form, and no witness has the verdict `other`.
- The concept is undefined where the frame interior is square, where two pieces' spans along the stack axis overlap (`overlapping-spans`), where the blocks' extents across the stack differ (`mixed-cross-extents`), where an odd number of cells is free on an axis, and where no color other than the dot color lies wholly on the dot lattice (`frame-off-lattice`). On `fits-short-axis` it is defined and fills the long axis with no margin, and the verdict there is `$RoomAxis`.
- Subsumption, for the case step: a case that orders by disjoint spans is subsumed by the case that differs from it only in also taking `$OrderByCenter`, because where the spans are disjoint the two orders agree. In the same way, a case that centers the stack as one is subsumed by the case that differs from it only in also taking `$CenterEachBlock`. The concept case is exempt. The case `$SpreadAxis & $OrderAlongSpread` is equivalent to the case `$SpreadAxis` and fails Equivalence.

## Choice points
- `stack-axis`
    - `concept`: the blocks line up along the frame's long axis.
    - `$SpreadAxis`: replaces the axis of `stack-blocks`: the blocks line up along the long side of the joint bounding box of all the pieces. It has no new parameter, and it is undefined where that box is square. It fits every pair. Witness `spread-vs-frame`: it breaks no scene claim, at the stored assignment; plausibility `ordinary`; verdict `concept`.
    - `$RoomAxis`: replaces the axis of `stack-blocks` and `exact-fit`: the blocks line up along the one axis on which they fit, `gap` apart, in the interior less `margin` at each end. It reads `margin` (1), and it is undefined where they fit on both axes or on neither. It fits every pair. Witness `fits-short-axis`: it breaks `exact-fit`, at the stored assignment; plausibility `variant`; verdict `$RoomAxis`; the invariant it breaks is that the stack fits the frame's long axis with one cell at each end in every input.
    - `$StoredAxis`: a parameter `axis` stores the stack axis. It fails Fit: H fails train1, and V fails train0.
- `stack-order`
    - `concept`: the blocks follow the pieces' order along the stack axis. It is undefined where two spans along that axis overlap.
    - `$OrderByCenter`: replaces `pieces-apart` and the order of `stack-blocks`: the blocks follow the order of the pieces' bounding-box centers along the stack axis. It is undefined where two centers tie. It fits every pair. Witness `overlapping-spans`: it breaks `pieces-apart`, at the stored assignment; plausibility `variant`; verdict `$OrderByCenter`; the invariant it breaks is that the pieces' spans along the stack axis are disjoint in every input.
    - `$OrderAlongSpread`: replaces the order of `stack-blocks`: the blocks follow the pieces' order along the long side of the pieces' joint bounding box, and they still line up along the frame's long axis. It is undefined where that box is square or where the spans along its long side overlap. It fits every pair. Witness `order-across-spread`: it breaks no scene claim, at the stored assignment; plausibility `ordinary`; verdict `concept`.
    - `$OrderByColor`: the blocks follow the color values. It fails Fit: in ascending order it fails train1 (8, 9, 3 top to bottom), and in descending order it fails train0 (2 left of 3).
- `cross-placement`
    - `concept`: the stack is centered across as one block. It is undefined where the blocks' extents across the stack differ.
    - `$CenterEachBlock`: replaces `common-cross-extent` and the cross placement of `stack-blocks`: each block is centered across the stack on its own. It is undefined where the interior extent less a block's extent is odd. It fits every pair. Witness `mixed-cross-extents`: it breaks `common-cross-extent`, at the stored assignment; plausibility `variant`; verdict `$CenterEachBlock`; the invariant it breaks is that all pieces have one extent across the stack in every input.
    - `$CrossFromSide`: across the stack, the blocks sit `margin` cells from a stored side of the frame. It fails Fit at train1: the output blocks fill cols 8–10, and a stored side gives cols 7–9 or 9–11.
- `along-placement`
    - `concept`: the stack is centered along its axis, and `margin` follows from `exact-fit`.
    - `$AnchorStack`: replaces the along-axis centering of `stack-blocks`: the stack starts `margin` cells from the frame edge that `anchor` gives on the stack axis. It reads `margin` (1) and the open parameter `anchor`, and it is undefined where the stack does not fit after that margin. It fits every pair. Witness `slack-along`: it breaks `exact-fit`, at the stored assignment; plausibility `borderline`; verdict `concept`; the invariant it breaks is that the stack fills the interior along its axis less one cell at each end in every input.
    - `$GapFromFit`: derives `gap` in place of storing it, and replaces the along-axis centering of `stack-blocks`: the stack runs from `margin` after one end to `margin` before the other, with gap = (interior extent − 2·`margin` − the blocks' extents) / (blocks − 1). It reads `margin` (1), and it is undefined where that gap is not a whole number ≥ 0, or where there is one piece. It fits every pair. Witness `slack-along`: it breaks `exact-fit`, at the stored assignment; plausibility `borderline`; verdict `concept`; the invariant it breaks is the same as for `$AnchorStack`.
- `frame-parse`
    - `concept`: the frame is the one color, other than the dot color, whose cells all lie on the dot lattice. It is undefined where there is no such color or more than one.
    - `$FrameLargest`: replaces how `frame` identifies the frame: the frame is the color, other than the background and the dot color, with the most cells. It is undefined where two colors tie. It fits every pair. Witness `frame-off-lattice`: it breaks `frame`, at the stored assignment; plausibility `borderline`; verdict `$FrameLargest`; the invariant it breaks is that the frame's dots lie on the dot lattice in every input.
- `block-size`
    - `concept`: a block is the size of its piece's bounding box.
    - `$BlockPerDot`: a block has one cell for each dot of its piece. It fails Fit at train0: the 2 block is 5×3, and the piece holds 3×2 dots.
- `interior`
    - `concept`: `clear-interior`.
    - `$KeepInteriorDots`: the interior lattice dots keep the dot color. It fails Fit at train1: (5,7) keeps 2, and the output has 4.
- `outline`
    - `concept`: `solid-outline`.
    - `$DottedOutline`: the frame stays dotted. It fails Fit at train0: (3,4) stays 8, and the output has 4.
- `pieces`
    - `concept`: `lift-pieces`.
    - `$KeepPieces`: the pieces stay where they are. It fails Fit at train0: (16,6) keeps 2, and the output has 8.
- `stack-axis` & `stack-order`, `stack-axis` & `cross-placement`, `stack-axis` & `frame-parse`, `stack-order` & `cross-placement`, `stack-order` & `along-placement`, `stack-order` & `frame-parse`, `cross-placement` & `along-placement`, `cross-placement` & `frame-parse`, `along-placement` & `frame-parse`, and `block-size`, `interior`, `outline` and `pieces` each with every other point: the two branches' changes applied together
    - `$SpreadAxis` & `$OrderAlongSpread`: the `$SpreadAxis` model. With `$SpreadAxis`, the order axis is the stack axis. The `stack-order` point stays at the concept, because `$OrderByCenter` still differs under `$SpreadAxis`.
- `stack-axis` & `along-placement`: the two branches' changes applied together
    - `$RoomAxis` & `$GapFromFit`: the blocks line up along the one axis on which they fit, one cell apart, in the interior less `margin` at each end. Along that axis, the gap is derived so that the stack runs from `margin` after one end to `margin` before the other. The model is undefined where the blocks fit on both axes or on neither.

## Open parameters
- `anchor`: DIAG_TL, DIAG_TR, DIAG_BL, DIAG_BR, under `$AnchorStack`. Only the corner's edge on the stack axis acts, so the output holds the stack set at each end.

## Not formed
- `gap` as the dot lattice's period less one: no source gives it. Every pair's period is 2, no proposer reads a lattice period (`Period` needs inputs that repeat), and no solver header or lib component ties a gap to a lattice period.
- A side to round an odd free span to: every pair leaves an even number of cells free on both axes, and no source names a rounding side.

## Tickets filed
- 10-788_task_db615bd4_analyze.md
