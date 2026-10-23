# e9c9d9a1

## Concept
- The concept fits every train pair and the test pair. The probe `work/task/e9c9d9a1/probe.py` builds it on `DividerTiles`. A divider is a full row or column with no `background` cell. A corner room is the tile whose index toward both edges of its corner is 0. An inner room is a tile whose index toward each of the four edges is above 0.
- The concept is undefined where an axis has no divider. On such an input, the corner tiles coincide and one cell gets two corner colors.
- No witness has verdict `other`.

## Choice points
- `room-parse`: how the rooms are found
    - `concept`: the tiles of the table that the full lines cut
        - `divider-test`: which full lines are dividers
            - `concept`: a full row or column with no `background` cell
            - `$LineColorLines`: a full row or column whose cells are all `line_color`, read as a parameter with value `3`. `line_color` moves from Scene parameters to Parameters. It replaces the divider test under `full-lines`. It is undefined where an axis has no full line of `line_color`. It fits every pair. Witness `third-color-line`: a full column of 5 at col 1 that the 3 lines cross. It breaks `full-lines`, because the input holds a color other than `line_color` and `background`. It stands at the stored assignment. Plausibility `foreign`, because every input holds only 0 and 3. Verdict `$LineColorLines`: the table that the 3 lines cut keeps col 1 inside the left rooms.
    - `$EnclosedRooms`: the rooms are the 4-connected components of `background` cells. An inner room is a component that no walk through `background` reaches from the grid edge (`Closed`). A corner room is the component that holds the grid's corner cell. It replaces `corner-rooms` and `inner-rooms` and drops the use of `full-lines`. It is undefined where one component holds two grid corners, such as where an axis has no line. It fits every pair. Witness `partial-wall`: a wall of 3 at col 1, rows 0–2, splits the top-left room. It breaks `full-lines`. It stands at the stored assignment. Plausibility `foreign`, because every 3 cell in the inputs lies on a full line. Verdict `$EnclosedRooms`: the part that holds the grid corner is the corner room, and the other part is an edge room that stays 0.
- `background`: where the value of `background` comes from
    - `concept`: the stored value `0`
    - `background=DominantColor`: `background` is each color whose cell count in the input is the highest. Where two colors tie, the output holds the model's output at each of them. It fits every pair, because 0 is the commonest color in every input. Witness `background=DominantColor`: lines of 0 on a field of 3. On that witness, the stored assignment finds no divider, so the concept is undefined, and the derived value 3 fills the rooms of 3. It breaks `full-lines`. It stands at the stored assignment. Plausibility `variant`: a 0↔3 color swap of the task gives this input. It breaks the invariant that 0 is the field color and the commonest color. Verdict `background=DominantColor`.
- `room-parse` & `background`, `divider-test` & `background`: the two branches' changes applied together.

## Open parameters
- none

## Not formed
- A derivation of `inner_color` or `corner_color`: an input holds only 0 and 3, and a proposer that reads outputs has none in a run on an input. So no proposer gives 7, or the per-corner colors 2, 4, 1 and 8, and each derived branch fails Fit at train0. No proposer has a column of a corner type for `corner_color`.
- `background=SharedColor` and `background=RarestColor`: SharedColor gives both 0 and 3, and RarestColor gives 3. At 3, no divider exists in a train input, so the corner rooms coincide. Each fails Fit at train0.
- Only the rooms in the middle band of each axis are inner: train2 has a 5×5 table, and the output fills all nine rooms that touch no grid edge with 7.
- A fill for the edge rooms that are not corner rooms: those rooms stay 0 in every pair.
- Corner colors keyed by something other than the corner, such as room size: the colors stay at their corners across pairs whose room sizes differ.

## Tickets filed
- none
