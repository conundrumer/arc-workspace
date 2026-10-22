# b0f4d537

## Concept
- The concept case fits every pair (train0–train3, test0), and each of its rules has a relational form.
- No witness has the verdict `other`.
- Some witnesses that break `field-markers` or `key-grid` get a branch's output as their verdict:
    - `line-one-end` and `header-edge` go to the line readings by one end.
    - `key-line-marker-color` goes to `$KeyByFill`.
- Some recolored witnesses also get a derived branch's output as their verdict, because the stored colors find no divider, marker or ground on them:
    - `marker-recolored` goes to `$MarkerFromField`.
    - `divider-recolored` goes to `$DividerFromFullLine`.
    - `background=DominantColor` goes to that derivation, and the concept gives the same grid there.
- The concept is stretched by a rule (`stretch-key`). Under the scene claims, every key row off the lines is the same row. Because of that, the rule's choice of gap row (the gap between the same lines) shows only on keys that break `key-grid`.

## Choice points
- `field-lines`: how the field's line rows and line columns are found
    - `concept`: a line row has `marker` at both of its border cells, and a line column has `marker` at both of its border cells
    - `$LineByEitherEnd`: replaces `field-lines`. A line is a row or column with `marker` at either of its border cells. No new parameters. It is undefined on no input that the concept is defined on. It fits every pair.
        - Witness `line-one-end`, at the stored assignment. It breaks `field-markers`, with plausibility `borderline` and verdict `$LineByEitherEnd`. The invariant it breaks: every line has a marker at both ends.
    - `$LineByHeaderEdge`: replaces `field-lines`. A line row has `marker` on the field edge on the side of the corner `header`, and a line column likewise on the other edge of that corner. Its parameter is `header` (a DiagDir), which is open. It fits every pair at all four open values.
        - Witness `header-edge`. That witness stands at `header` = `DIAG_TL`. At the stored open set, the corners disagree on that input and the model gives no grid. It breaks `field-markers`, with plausibility `borderline` and verdict `$LineByHeaderEdge`. The invariant it breaks: every line has a marker at both ends.
    - `$LineByCrossing`: replaces `field-lines`. The lines are the rows and the columns of the `marker` cells off the field border. No new parameters. It fits every pair.
        - Witness `line-ends-only`, at the stored assignment. It breaks `field-markers`, with plausibility `variant` (a variant task marks each line by its two ends alone) and verdict `concept`. The invariant it breaks: every crossing carries a marker.
    - `$LineByAnyMarker`: replaces `field-lines`. A line is any row or column that holds a `marker` cell. It fails Fit on train0, because row 0 holds the top end marker of column 4.
- `line-match`: which key line a field line takes
    - `concept`: the k-th field line takes the k-th key line on its axis
    - `$KeyReversed`: replaces `stretch-key`. The k-th field line takes the k-th key line counted from the far end. It fails Fit on train0.
- `crossing`: the color of a cell where a line row and a line column cross
    - `concept`: the key's cell at that crossing
    - `$CrossByAxis`: replaces `stretch-key` at crossings. The line on the stored axis `over_axis` shows. It fails Fit on train0, where row 1 lies over column 1 and row 3 lies under it.
    - `$CrossByColorOrder`: replaces `stretch-key` at crossings. The color that a stored order over line colors ranks higher shows. It fails Fit on train2, where 1 lies over 3 but train0 has 3 over 1.
- `drawing`: what fills the output
    - `concept`: the key stretched to the field's size, with each output cell the key cell at its mapped row and column
    - `$DrawLines`: replaces `stretch-key`.
        - A cell on one line takes that line's color, which is the one color its key line holds off the crossings.
        - A crossing takes the key's crossing cell.
        - Every other cell is `background`, which becomes a parameter (stored 0).
        - It is undefined where a key line holds more than one color off the crossings. It fits every pair.
        - Witness `key-ground`, at the stored assignment. It breaks `key-grid`, with plausibility `borderline` and verdict `concept`. The invariant it breaks: the key's cells off its lines are 0, the field's ground.
        - `background`: how the ground color is found
            - `concept`: stored, 0
            - `background=DominantColor`: the ground is the input's commonest color. It fits every pair.
                - Witness `background=DominantColor`, at the stored assignment. At the stored ground 0, it breaks `field` and `key-grid`. Its plausibility is `variant` (a color permutation) and its verdict `background=DominantColor`. The invariant it breaks: the ground is 0 in every input.
- `field-panel`: which panel is the field and which is the key
    - `concept`: the field is the panel that holds `marker` cells, and the key is the other panel's cells that are not `divider`
    - `$KeyByFill`: replaces `find-panels`. The key is the cells, not `divider`, of the panel that `divider` cells partly fill, and the field is the other panel. It is undefined where both panels or neither panel holds `divider` cells. It fits every pair.
        - Witness `key-line-marker-color`, at the stored assignment. It breaks `key-grid`, with plausibility `borderline` and verdict `$KeyByFill`. The invariant it breaks: no key line has the marker color.
        - `marker`: how the marker color is found
            - `concept`: stored, 4
            - `$MarkerFromField`: the marker is the field's color other than its commonest color. It is undefined where the field holds more or fewer than two colors. It fits every pair.
                - Witness `marker-recolored`, at the stored assignment. At the stored marker 4, it breaks `field`. Its plausibility is `variant` (a color permutation) and its verdict `$MarkerFromField`. The invariant it breaks: the markers are 4 in every input.
- `divider`: how the divider color is found
    - `concept`: stored, 5
    - `$DividerFromFullLine`: the divider is the color of a full row or column of one color, other than the input's commonest color. It is undefined where no such color, or more than one, exists. It fits every pair.
        - Witness `divider-recolored`, at the stored assignment. It breaks `two-panels`, with plausibility `variant` (a color permutation) and verdict `$DividerFromFullLine`. The invariant it breaks: the divider is 5 in every input.
- `field-lines` & `line-match`, `field-lines` & `crossing`, `field-lines` & `drawing`, `field-lines` & `field-panel`, `field-lines` & `divider`, `line-match` & `crossing`, `line-match` & `drawing`, `line-match` & `field-panel`, `line-match` & `divider`, `crossing` & `drawing`, `crossing` & `field-panel`, `crossing` & `divider`, `drawing` & `field-panel`, `drawing` & `divider`, `field-panel` & `divider`, `marker` & `field-lines`, `marker` & `line-match`, `marker` & `crossing`, `marker` & `drawing`, `marker` & `divider`, `background` & `field-lines`, `background` & `line-match`, `background` & `crossing`, `background` & `field-panel`, `background` & `marker`, `background` & `divider`: the two branches' changes applied together

## Open parameters
- `header`: `DIAG_TL`, `DIAG_TR`, `DIAG_BL`, `DIAG_BR`, under `$LineByHeaderEdge`

## Not formed
- Deriving `marker` under the concept branch of `field-panel`: the concept finds the field by its `marker` cells, so a marker read off the field has no field to read it from. Also, no proposer gives one color on an input alone: SharedColor gives every color, DominantColor gives 0, RarestColor varies, and VanishedColor needs train outputs.
- Deriving `divider` by a proposer: on these inputs DominantColor gives 0, and no other color proposer gives 5 on an input alone.
- Mapping every field gap row to one fixed key gap row (row 0): under `key-grid` every key gap row is the same, and no reader who takes the key as a picture stretches it that way.
- An output frame other than the field: no reading of the pairs gives another frame, since every output has the field's size.
- `divider_axis` and `key_end` as parameters: no rule reads them. The concept finds the divider as a full line on either axis, and finds the key by dropping the `divider` cells of its panel.

## Tickets filed
- none
