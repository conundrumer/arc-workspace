# e99362f0

## Concept
- Fits every pair, train and test. No witness has the verdict `other`, and the rule `stack-by-priority` is relational, so no approximation stands in for it.
- The pairs fix all of `priority`. Each of the six orders between two of the colors 2, 7, 8 and 9 shows at a cell where only those two panels have a mark.
- The concept case is undefined on two color-permuted variants: a cross that is not drawn in 4 (witness `divider=SharedColor`), and a background that is not 0 (witness `background=DominantColor`). On each of them, a branch at `panel-parse` or at `background-source` gives the stack.
- `$CenterHalves` and `divider=SharedColor` subsume the concept case. The concept case is exempt from Subsumption.

## Choice points
- `stacking-key`: what the stacking order ranks
    - `concept`: the panels' colors (`priority`)
    - `$OrderByPanel`: replaces `stack-by-priority`. A stored order `panel_order` (bottom-right > top-left > top-right > bottom-left) ranks the four panel corners, and each output cell shows the mark of the highest-ranked panel that has a mark there. It is undefined only where the parse is. It fits every pair. Witness `panels-recolored`: the input swaps 7 and 8, so 8 marks the top-left panel and 7 the bottom-right. The witness stands at the stored assignment and breaks `one-color-per-panel` (`panel_color`). Plausibility `variant`, verdict `concept`. The invariant it breaks: each color keeps its own panel (7 top-left, 9 top-right, 2 bottom-left, 8 bottom-right).
- `stacking-form`: how the colors at a cell resolve to one
    - `concept`: a total order on the colors
        - `priority-source`: where the order comes from
            - `concept`: the stored `priority`
            - `priority=CountRankDesc`: `priority` is derived as each color's rank by cell count in the input, commonest first. It is undefined where two mark colors share a rank. It fails Fit at train0: the colors 7, 9, 2 and 8 have 7 cells each and share one rank, so at train0 input (0,0), where 7 and 2 meet, no output is given. The pair's output is 7 there.
            - `priority=CountRankAsc`: the same derivation, rarest first. It fails Fit at train0 for the same reason.
    - `$CombinationTable`: replaces `stack-by-priority`. A stored lookup table `stack_table` maps the set of mark colors at a cell to the color that the cell shows. It is undefined where a cell's set is not a key. It fits every pair: the train pairs hold all 16 subsets of {2, 7, 8, 9}, so no test key is unseen. Witness `intransitive-table`: a table that shows 7 over 9 and 7 over 2, and 9 where 2, 7 and 9 meet, on train0's input. The witness breaks no scene claim. It stands at an assignment that changes one entry of `stack_table`, the {2, 7, 9} entry, to 9. Plausibility `ordinary`, verdict `$CombinationTable`.
- `panel-parse`: how the four panels are found
    - `concept`: the full row and the full column of the `divider` color
    - `divider=SharedColor`: `divider` takes every color of the input, and the cross is the one row and one column that a single color of those draws in full. It is undefined where no single color draws exactly one full row and one full column. It fits every pair. It fails Subsumption by `$CenterHalves`: where it is defined, its cross is centered, because the panels are equal, so the center halves give the same panels. Witness `divider=SharedColor`: train0's input with its cross drawn in 5. The witness stands at the stored assignment and breaks `divider-cross` (`divider` 4). Plausibility `variant`, verdict `divider=SharedColor`. The invariant it breaks: the cross is color 4.
    - `$CenterHalves`: replaces `divider-cross`. The panels are the four quadrants around the center row and the center column, whatever color those lines have, and no divider color is read. It is undefined where a grid dimension is even. It fits every pair. Witness `divider-recolored`: train1's input with its cross drawn in 6. The witness stands at the stored assignment and breaks `divider-cross` (`divider` 4). Plausibility `variant`, verdict `$CenterHalves`. The invariant it breaks: the cross is color 4.
    - `$StoredPanelSize`: replaces `divider-cross`. The panels are the 2×2 tiles of a stored `panel_size` (5×4), one cell apart, and no divider color is read. It is undefined where the grid is not two panels and a one-cell gap on each axis. It fits every pair. It fails Subsumption by `$CenterHalves`: on every grid where it is defined, the center halves cut the same tiles. Witness `divider-recolored`, which gives the same plausibility and verdict as for `$CenterHalves`.
- `background-source`: where the background color comes from
    - `concept`: the stored `background`
    - `background=DominantColor`: `background` is derived as the commonest color of the input. It is undefined where a non-background color has no priority entry. It fits every pair, because 0 is the commonest color of every input. Witness `background=DominantColor`: train0's input with 0 recolored to 5. The witness stands at the stored assignment and breaks `one-color-per-panel` (`background` 0). Plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks: the background is 0.
- `stacking-key` & `stacking-form`, `stacking-key` & `panel-parse`, `stacking-key` & `background-source`, `stacking-form` & `panel-parse`, `stacking-form` & `background-source`, `panel-parse` & `background-source`, `priority-source` & `panel-parse`, `priority-source` & `background-source`: the two branches' changes applied together. For `$OrderByPanel` & `$CombinationTable`, the result is a table from the set of panels that have a mark at a cell to the panel that shows.
- `stacking-key` & `priority-source`: the model of `$OrderByPanel`. A rank of colors does not exist under an order of panels, so `priority-source` stands under the concept branches of both `stacking-key` and `stacking-form`.
    - `$OrderByPanel` & `priority=CountRankDesc`, `$OrderByPanel` & `priority=CountRankAsc`: the model of `$OrderByPanel`

## Open parameters
- none

## Not formed
- A stored output color per panel or per input color: in every pair, each output cell has the color of an input mark at the same cell. A recolor table would be the identity, and no reader of the pairs takes the output to recolor.
- `background` from SharedColor or RarestColor: on train0's input, SharedColor gives every color, so no cell is a mark. RarestColor gives the four mark colors, which tie at 7 cells. Both fail Fit at train0.
- `divider` from DominantColor or RarestColor: DominantColor gives 0 on every input, and RarestColor gives the mark colors. No full row is drawn in either, so both fail Fit at every pair.
- A drawing order, in which panels are painted one after another and a later one covers an earlier one: this is the concept's model with `priority` read in reverse. It is the same model.
- A panel parse from the SepTileCount or TileDim proposers: each gives the same 2×2 cut with a one-cell gap that `$StoredPanelSize` or the concept gives.

## Tickets filed
- none
