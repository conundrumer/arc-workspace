# e9fc42f2

## Concept
- Fits every pair: one assembly on each, equal to the train outputs and the test outputs (`work/task/e9fc42f2/check_concept.py`).
- Each claim has a relational form: pieces are components, a connector's side is the edge of its piece's bounding box it lies on, and each join is a translation.
- The concept is undefined on the witnesses `connectors-same-side`, `diagonal-cell`, `background=DominantColor` and `pair-on-one-piece`, and each of those has a branch as its verdict. No witness has the verdict `other`.

## Choice points
- `join-placement`
    - `concept`: the two connectors of a pair face opposite sides, and the second sits one step past the first across the first's facing edge (`snap`, `connector-side`).
    - `$NoOverlapJoin`: replaces `snap` and `connector-side`: a pair's second connector sits one step from the first toward any of the four directions at which no two pieces share a cell, and the output holds each such assembly; no new parameter; undefined where no choice of directions keeps the pieces apart. Fits every pair, with one assembly on each. Witness `connector-tip`: breaks no scene claim; plausibility `ordinary`; verdict `concept`. Each 3 there is a tip with background on three sides, as the 3 at train0 input (4,4) is, and the branch gives three assemblies.
        - `connector-facing`
            - `concept`: a connector faces out from the one edge of its piece's bounding box that it lies on (`connector-side`).
            - `$FreeNeighborSide`: replaces `connector-side`: a connector faces the one side where its neighbor is background; no new parameter; undefined where a connector has background on more than one side, or on none. Fails Fit at train0: the 3 at train0 input (7,8) has background above it and below it (the hole at (8,8)), and the 3 at (4,4) has background on three sides.
        - `piece-motion`
            - `concept`: pieces move by translation alone (`snap`), and the two connectors of each pair face opposite directions (`connector-pairs`).
            - `$TurnToFace`: replaces `snap` and the facing condition of `connector-pairs`: the assembly builds out from the piece with the most cells, and where a pair's connectors do not face opposite directions, the piece that joins turns by the quarter turns that make its connector face its partner; no new parameter; undefined where pieces tie for the most cells and the roots give different outputs. Fits every pair, with no turn on any. Witness `connectors-same-side`: breaks `connector-pairs`; plausibility `borderline`; verdict `$TurnToFace`; invariant broken: in every input, the two connectors of each pair lie on opposite edges of their pieces.
- `contact`
    - `concept`: the two connectors of a pair are adjacent cells (`snap`).
    - `$MergeConnectors`: replaces `snap`: the two connectors of a pair land on one cell; no new parameter; undefined where other cells of two pieces then share a place. Fails Fit at train0: the output has two 3 cells, at (4,2) and (5,2), and the branch gives one.
- `unpaired-connectors`
    - `concept`: a connector with no partner keeps its color (`crop`).
    - `$DropUnpaired`: replaces `crop`: a connector with no partner takes `body`; no new parameter; undefined where the concept is. Fails Fit at train0: the 8 at train0 output (6,4) has no partner and stays 8.
- `piece-connectivity`
    - `concept`: a piece is 4-connected (`field`).
    - `$EightConnected`: replaces `field`: a piece is 8-connected; no new parameter; undefined where the concept is, with pieces read under 8-adjacency. Fits every pair. Witness `diagonal-cell`: breaks `one-assembly`, since the concept reads the 1 that meets the upper piece only at a corner as a piece with no connector; plausibility `borderline`; verdict `$EightConnected`; invariant broken: every input has the same pieces under 4- and 8-adjacency.
- `background`
    - `concept`: `background` is stored, 2.
    - `background=DominantColor`: replaces the stored `background` (`field`) with the commonest color of the input; undefined where colors tie for the commonest. Fits every pair. Witness `background=DominantColor`: breaks `field`, since no cell holds 2; plausibility `variant`; verdict `background=DominantColor`; invariant broken: the field is 2 in every input.
- `connector-colors`
    - `concept`: a connector is a cell of any color other than `body` and `background` (`pieces`).
    - `$StoredConnectorColors`: replaces `pieces`: adds the parameter `connector`, 3, 4, 8, and a connector is a cell of a color in `connector`; a cell of any other color other than `body` is a mark of its piece and keeps its color; undefined where the concept is, with connectors read from `connector`. Fits every pair. Witness `pair-on-one-piece`: breaks `connector-pairs`, since the concept reads the two 6 cells as a pair on one piece; plausibility `borderline`; verdict `$StoredConnectorColors`; invariant broken: every connector color is 3, 4 or 8, and no color other than `body` occurs twice on one piece.
- `output-frame`
    - `concept`: the output is the bounding box of the assembly (`crop`).
    - `$InPlace`: replaces `crop`: the piece with the most cells keeps its place in the input frame, and the other pieces snap to it; no new parameter; undefined where an assembled piece leaves the frame. Fails Fit at train0: the output is 8×5, and the input frame is 13×13.
- `join-placement` & `contact`, `join-placement` & `unpaired-connectors`, `join-placement` & `piece-connectivity`, `join-placement` & `background`, `join-placement` & `connector-colors`, `join-placement` & `output-frame`, `contact` & `unpaired-connectors`, `contact` & `piece-connectivity`, `contact` & `background`, `contact` & `connector-colors`, `contact` & `output-frame`, `unpaired-connectors` & `piece-connectivity`, `unpaired-connectors` & `background`, `unpaired-connectors` & `connector-colors`, `unpaired-connectors` & `output-frame`, `piece-connectivity` & `background`, `piece-connectivity` & `connector-colors`, `piece-connectivity` & `output-frame`, `background` & `connector-colors`, `background` & `output-frame`, `connector-colors` & `output-frame`, `connector-facing` & `piece-motion`, `connector-facing` & `contact`, `connector-facing` & `unpaired-connectors`, `connector-facing` & `piece-connectivity`, `connector-facing` & `background`, `connector-facing` & `connector-colors`, `connector-facing` & `output-frame`, `piece-motion` & `contact`, `piece-motion` & `unpaired-connectors`, `piece-motion` & `piece-connectivity`, `piece-motion` & `background`, `piece-motion` & `connector-colors`, `piece-motion` & `output-frame`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Pairing connectors by a property other than color, such as nearness or shape: each connector color occurs at most twice in an input, and the pairs suggest no other pairing.
- Reflection of a piece under `$TurnToFace`: a quarter turn already makes any pair face, and a reflection gives a second assembly that the pairs give no reason for.
- A paint order where assembled pieces overlap: no assembly in the evidence overlaps, and the pairs suggest no order among pieces.
- Connectors that meet at a corner: in every output, the two connectors of a pair are orthogonal neighbors.
- `body` derived, and `background` derived by a proposer other than DominantColor: SharedColor gives several colors on one input, and RarestColor gives a connector color, so no such derivation gives the one body or field color.

## Tickets filed
none
