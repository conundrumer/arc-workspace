# f0f8a26d

## Concept
- Fits every pair (train0–2, test0), checked by `work/task/f0f8a26d/check.py` and `work/task/f0f8a26d/probe.py pairs`. No turned bar is clipped in any pair.
- No witness has verdict `other`. The generator draws one-color straight bars of odd length that do not touch side to side (27 of 27 bars are odd; test0 has the one diagonal contact, (5,8)–(6,9)). It places each bar so that its turn stays inside the frame, and pairs the input with the union of the turned bars. On the scene the concept's rule is that rule exactly, with no approximation.
- Under the concept, a quarter turn clockwise, a quarter turn counterclockwise and a flip across either diagonal all give the same output for a one-color straight bar, so the concept has no choice point or open parameter there.

## Choice points
- `parts`: what a part of the marked cells is
    - `concept`: a connected part of the marked cells
        - `adjacency`: which neighbors join a part
            - `concept`: 4-adjacency
            - `$Adjacency8`: replaces `straight-bars` by 8-connected parts. No new parameters. Undefined where an 8-part is not a straight bar. Fails Fit at test0: the row-5 bar and the col-9 bar touch at (5,8)–(6,9), so they join into one part that is not straight.
        - `shape-scope`: which parts turn
            - `concept`: straight bars only. Undefined on any other part.
            - `$ObjectD4`: replaces `straight-bars` and `quarter-turn`: every part, of any shape, is redrawn under one D4 element about its box centre. Parameter `obj_turn` (D4), open. Undefined where a part's box height and width differ in parity. Fits every pair. Witness `touching-bars` (breaks `straight-bars`, stands at the stored assignment, `borderline`, verdict `$Runs`; it breaks the input invariant that no two bars touch side to side).
    - `$Runs`: replaces `straight-bars` with maximal row runs and column runs, and lone cells. A cell can lie in two runs, and each run turns about its middle. No new parameters. Undefined where a run has even length. Fits every pair. Witness `touching-bars` (breaks `straight-bars`, stands at the stored assignment, `borderline`, verdict `$Runs`; it breaks the input invariant that no two bars touch side to side).
- `even-bars`: what a bar with no middle cell does
    - `concept`: undefined on a bar of even length
    - `$EvenBarShift`: replaces `odd-length`: an even bar is redrawn on the other axis with the same length, its centre moved half a cell toward one corner. Parameter `even_shift(a: Axis, d: DiagDir)`, open, gives the corner for each axis the bar lies along. Undefined nowhere the concept is defined. Fits every pair. Witness `even-bar` (breaks `odd-length`, stands at the stored assignment, `foreign`, verdict `$EvenBarShift`; it breaks the input invariant that every bar has odd length, 27 of 27).
- `mark-colors`: how many mark colors an input holds
    - `concept`: one mark color per input, read from the input
    - `$PartColors`: replaces `one-mark-color`: the parts are taken per color, and each part turns in its own color. No new parameters. Undefined where two colors land on one cell. Fits every pair. Witness `two-mark-colors` (breaks `one-mark-color`, stands at the stored assignment, `borderline`, verdict `$PartColors`; it breaks the input invariant that every input holds one non-background color).
- `background`: where the background color comes from
    - `concept`: stored, `background` = 7
    - `background=DominantColor`: derived as the color with the most cells in the input, and replaces `background-field`. Undefined where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor` (breaks `background-field`, stands at the stored assignment, `variant`, verdict `background=DominantColor`).
- `frame-edge`: what a turn that reaches past the frame does
    - `concept`: the cells past the frame are dropped
    - `$UndefinedPastFrame`: replaces `same-frame`. No new parameters. Undefined where a turned bar reaches past the frame. Fits every pair. It is subsumed by the concept case's model, which gives the same output wherever this model is defined, so it fails Subsumption. Witness `turn-past-frame` (breaks `turn-inside-frame`, stands at the stored assignment, `borderline`, verdict `concept`; it breaks the input invariant that every turn lies inside the frame, which train0 col 6, train1 row 7, train2 row 2 and test0 row 2 each meet exactly at an edge).
- `parts` & `even-bars`, `parts` & `mark-colors`, `parts` & `background`, `parts` & `frame-edge`, `adjacency` & `shape-scope`, `adjacency` & `even-bars`, `adjacency` & `mark-colors`, `adjacency` & `background`, `adjacency` & `frame-edge`, `shape-scope` & `even-bars`, `shape-scope` & `mark-colors`, `shape-scope` & `background`, `shape-scope` & `frame-edge`, `even-bars` & `mark-colors`, `even-bars` & `background`, `even-bars` & `frame-edge`, `mark-colors` & `background`, `mark-colors` & `frame-edge`, `background` & `frame-edge`: the two branches' changes applied together
    - `$ObjectD4` & `$EvenBarShift`: a part whose box height and width differ in parity takes the even shift. A part of that kind other than a bar stays undefined.

## Open parameters
- `obj_turn`: `D4_CW`, `D4_CC`, `D4_DG`, `D4_AD`, under `$ObjectD4`
- `even_shift`: each of `DIAG_TL`, `DIAG_TR`, `DIAG_BL`, `DIAG_BR` on each of `AXIS_H` and `AXIS_V`, under `$EvenBarShift`

## Not formed
- A turn about an end of the bar in place of its middle: in every pair each bar keeps its middle cell. For example, train0's col-1 bar at rows 0–2 lands on row 1 cols 0–2, and train0 output row 0 is all 7, which no end pivot of that bar gives.
- A stored mark color: the mark color is 5, 2, 8 and 9 in the four pairs, so no stored value fits train0 and train1 both. The color is read from each input.
- A precedence among bars that cross after the turn: an input has one mark color, so a crossing cell has one possible color. Under `$PartColors`, a crossing of two colors is where that model is undefined.
- Clockwise against counterclockwise under the concept: the two give one output for every straight one-color bar, so they are one model. The choice is the open parameter `obj_turn` under `$ObjectD4`.

## Tickets filed
- none
