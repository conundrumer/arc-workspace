# c3e719e8

## Concept
- The concept fits every pair: each input has one color strictly most common, and the output copies the input into the blocks whose input cell has that color, `background` `0` elsewhere.
- No witness has the verdict `other`. The concept file's rule is the rule as the generator applies it, with no approximation.
- The concept is undefined on an input where colors tie for the most cells (scene claim `unique-mode`).

## Choice points
- `gate-color`: which input cells gate a copy of the input
    - `concept`: the cells of the color that an extreme of the input's color cell counts picks, derived per input
        - `count-extreme`: which extreme of the counts picks the color
            - `concept`: the most cells
            - `$RarestColor`: replaces `copy-where-mode`; the cells of the color with the fewest cells gate, the color a `@derive RarestColor` line gives; undefined where colors tie for the fewest cells. Fails Fit at train0, where 8, 7 and 9 tie at 2 cells each.
        - `count-tie`: what gates when colors tie at the extreme
            - `concept`: nothing; the model is undefined on a tie
            - `$TiesAllGate`: replaces `unique-mode` and `copy-where-mode`; the cells of every color tied at the extreme gate; defined on every input. Fits every pair. Witness `mode-tie`: breaks `unique-mode`, stands at the stored assignment, `foreign`, verdict `any`; it breaks the invariant that every input has one color strictly more common than every other.
            - `$TiesNoneGate`: replaces `unique-mode` and `copy-where-mode`; a cell gates only where its color has strictly more cells than every other color, so on a tie no block holds a copy and the output is all `background`; defined on every input. Fits every pair. Witness `mode-tie`: breaks `unique-mode`, stands at the stored assignment, `foreign`, verdict `any`; it breaks the same invariant.
    - `gate_color=stored`: replaces `copy-where-mode`; the cells of one stored color gate. Fails Fit: train0 gates 3, and train1 has 3 at a cell whose block is blank and gates 8.
    - `$CountThreshold`: replaces `copy-where-mode`; the cells of every color with at least a stored number of cells gate. Fails Fit: only a threshold of 3 fits the train pairs, and at 3 test0 gates 7 (3 cells) beside 1.
    - `$NonBackgroundGate`: replaces `copy-where-mode`; every cell not of `background` gates (the reading of 007bbfb7 and 5b6cbef5). Fails Fit at train0, whose blocks off the diagonal are blank.
- `block-count`: how many blocks the output arrangement has on each axis
    - `concept`: the input's extent on that axis, derived per input
    - `$StoredBlockCount`: replaces `block-layout`; the arrangement is a stored `block_count` (3) blocks on each axis; undefined on an input whose extent is not `block_count`. Fits every pair. Witness `four-by-four`: breaks `small-grid` at `input_size` 3×3, stands at the stored assignment, `variant`, verdict `concept`; it breaks the invariant that every input is 3×3. No witness exists on which the branch is defined, since wherever it is defined it gives the concept's output; the concept's model subsumes it, so it fails Subsumption.
- `background`: the color of a block that holds no copy
    - `concept`: stored, `0`
    - `background=OutNewColor`: the color in every train output and no input. Fails Fit at train0: on a lone input `ex_out` is empty, the derivation gives no value, and the branch is undefined on every pair.
- `gate-color` & `block-count`, `gate-color` & `background`, `block-count` & `background`, `count-extreme` & `count-tie`, `count-extreme` & `block-count`, `count-extreme` & `background`, `count-tie` & `block-count`, `count-tie` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A fixed input cell whose color gates: no cell carries the gate color in every pair (train0 gates the main diagonal, train2 gates (0,1), (0,2), (2,0), (2,1)).
- The color present in every row of the input: train2's middle row (4 6 8) holds no 9, so it fails Fit at train2, and it is not a reading the pairs suggest.
- `gate_color=DominantColor`: on a lone input the derivation gives every color tied for the most cells, so its model is the model of `$TiesAllGate`, and it fails Equivalence.
- A gated block holding a transformed copy, or a copy keeping only some colors: every gated block in every output is the input unchanged.
- The colors of a blank block: every blank block in every output is all `0`, so no reading other than one fill color applies.

## Tickets filed
- none
