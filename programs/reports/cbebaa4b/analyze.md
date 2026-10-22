# cbebaa4b

## Concept
- Fits every pair. On each of `train0`, `train1`, `test0` and `test1`, exactly one placement pairs every `2` dot and keeps the pieces apart inside the grid, and it draws the pair's output (`probe_one.py concept <side> <index>`).
- No witness has the verdict `other`. The generator builds the assembly around the `4` piece and then scatters the other pieces, each by a translation. The concept's search recovers that assembly wherever the placement is unique, which the scene claim `pieces-fit` states.

## Choice points
- `anchor`: which piece stays in place
    - `concept`: the piece of the stored color `anchor` (`4`)
    - `$AnchorSolidBlock`: replaces `one-anchor` and `anchor-stays`. The anchor is derived as the one piece that fills its bounding box, with both extents at least 2. No parameter. Undefined where no piece or more than one piece qualifies. Fits every pair. Witness `anchor-not-solid` (train0 with `4` and `5` swapped, so the `4` piece is a hollow C and the solid block is `5`). It breaks no scene claim. It stands at the stored assignment. Plausibility `borderline`, verdict `concept`. Invariant broken: in every input, the `4` piece is the one solid block.
    - `anchor=RarestColor`: replaces `one-anchor`. The anchor is the piece of the input's rarest color. Undefined where that color is not one piece. Fails Fit at `train0`: the rarest color is `3`, and with the `3` piece fixed, the assembly runs past the grid, so the model is undefined.
- `background`: the field color
    - `concept`: stored `0`
    - `background=DominantColor`: the field is the input's most common color. Undefined where two colors tie for most common. Fits every pair. Witness `background=DominantColor` (train1 with `0` recolored `7`). It breaks the scene claim `pieces` (the field is not `0`). It stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`.
- `connector`: the dot color
    - `concept`: stored `2`
    - `$ConnectorDerived`: replaces `pieces`. The connector is derived as the one non-field color whose cells touch every piece of every other color. No parameter. Undefined where no color, or more than one, qualifies. Fits every pair. Witness `connector-recolored` (train1 with `2` recolored `7`). It breaks the scene claim `pieces` (the dots are not `2`). It stands at the stored assignment. Plausibility `variant`, verdict `$ConnectorDerived`.
- `piece`: what one piece is
    - `concept`: a 4-connected one-color component
    - `$PieceByColor`: replaces `pieces`. All cells of one color form one piece. No parameter. Undefined where a dot touches two pieces. Fails Fit at `test0` (two `8` pieces) and at `test1` (two `3` pieces). The model is undefined on both.
- `overlap`: whether placed pieces may share cells
    - `concept`: no two pieces, and no piece and a dot, share a cell
    - `$OverlapAllowed`: replaces `pieces-fit`, dropping the disjointness condition. No parameter. Undefined where a shared cell would take two colors. Fits every pair. Witness `shared-cell`: the only placement that pairs every dot puts two `1` pieces on one cell. It breaks the scene claim `pieces-fit`. It stands at the stored assignment. Plausibility `foreign`, verdict `$OverlapAllowed`. Invariant broken: every input has a placement in which no two pieces share a cell.
- `bounds`: whether the assembly must lie inside the grid
    - `concept`: every placed cell lies inside the grid
    - `$ClipAssembly`: replaces `pieces-fit` and `assemble`. Placements may reach past the grid, and the output draws the part inside it. No parameter. Fits every pair. Witness `assembly-past-edge` (train1 with the `4` piece and its dots 8 rows higher). It breaks the scene claim `pieces-fit`. It stands at the stored assignment. Plausibility `foreign`, verdict `$ClipAssembly`. Invariant broken: in every input, the assembly around the `4` piece lies inside the grid.
- `join-side`: how two pieces sit at a shared dot
    - `concept`: on any sides of the dot
    - `$FacingJoin`: adds a claim to `pieces-fit`: the two pieces at a shared dot lie straight across it from each other. No parameter. Fails Fit at `test1`, where it is undefined: the `8` piece and the `4` piece meet at the corner dot `test1 output (10,9)`, with `8` above it and `4` to its right.
- `orientation`: how a piece may move
    - `concept`: translation only
    - `$TurnPieces`: replaces `pieces-fit` and `assemble`. Each piece other than the anchor may also take any D4 transform. No parameter. Fails Fit at `train1`, where it gives two grids.
- `pairing`: whether every dot must pair
    - `concept`: each dot lands on exactly one dot of another piece
    - `$LooseDots`: replaces `pieces-fit`. A dot may stay unpaired. No parameter. Fails Fit at `train0`, where it gives more than 40 grids.
- `anchor` & `background`, `anchor` & `connector`, `anchor` & `piece`, `anchor` & `overlap`, `anchor` & `bounds`, `anchor` & `join-side`, `anchor` & `orientation`, `anchor` & `pairing`, `background` & `connector`, `background` & `piece`, `background` & `overlap`, `background` & `bounds`, `background` & `join-side`, `background` & `orientation`, `background` & `pairing`, `connector` & `piece`, `connector` & `overlap`, `connector` & `bounds`, `connector` & `join-side`, `connector` & `orientation`, `connector` & `pairing`, `piece` & `overlap`, `piece` & `bounds`, `piece` & `join-side`, `piece` & `orientation`, `piece` & `pairing`, `overlap` & `bounds`, `overlap` & `join-side`, `overlap` & `orientation`, `overlap` & `pairing`, `bounds` & `join-side`, `bounds` & `orientation`, `bounds` & `pairing`, `join-side` & `orientation`, `join-side` & `pairing`, `orientation` & `pairing`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- connector cells erased once joined: every train output shows `2` on each shared dot.
- output cropped to the assembly: every train output keeps the input's size.
- `anchor` or `connector` derived by `SharedColor`: on one input, the proposer gives every color the input holds, so the parameter takes several values on each pair. `DominantColor` gives `0` for either parameter, and `0` is the field.

## Tickets filed
- none
