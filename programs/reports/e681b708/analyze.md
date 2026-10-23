# e681b708

## Concept
- Fits every pair (train0, train1, train2, test0). In every room that holds a dot, one color occurs most often among the markers 8-adjacent to the room, so `clear-majority` holds and the concept is defined on every input.
- No witness with verdict `other`. The rule has a relational form: line runs between markers, 4-connected rooms, and a plurality count over the markers 8-adjacent to a room.
- Every fitting branch's witness has the verdict `concept`.

## Choice points
- `marker-tally`: which markers a room counts, and how they give its color
    - `concept`: the color that occurs most often among the markers 8-adjacent to the room
    - `$SideMarkers`: replaces `dot-recolor`; counts only the markers 4-adjacent to the room, and is undefined where two colors tie. Fails Fit at train0: the rooms rows 0–2, cols 0–9 (2 against 6) and six other rooms tie.
    - `$CornerMarkers`: replaces `dot-recolor`; counts only the markers diagonally adjacent to the room and 4-adjacent to none of its cells, and is undefined where two colors tie. Fails Fit at train0: the rooms rows 4–15, cols 11–22 and rows 10–15, cols 0–9 tie. At train2, the room rows 0–6, cols 6–21 would get 2 where the output has 3.
    - `$StrictMajority`: replaces `dot-recolor`; a color must hold more than half of the room's markers, and the branch is undefined otherwise. Fails Fit at train0: the room rows 17–26, cols 11–16 has 3 3 2 8.
    - `$NearestMarker`: replaces `dot-recolor`; each dot takes the color of the marker of its room that is nearest by taxicab distance, and is undefined where the nearest markers differ in color. Fails Fit at train0: the rooms rows 4–8, cols 0–9 and rows 17–26, cols 0–9 hold a dot equidistant from two colors.
- `room-connectivity`: how non-line cells join into rooms
    - `concept`: 4-adjacency
    - `$Rooms8`: replaces `rooms`; non-line cells join by 8-adjacency, so two walls that touch only at a corner do not close a room. Undefined on the same inputs as the concept. Fits every pair. Witness `diagonal-pinch`: breaks `wall-lines` (the lines from (2,3) and from (3,4) end on neither a grid edge nor another line), stands at the stored assignment, `foreign`, verdict `concept`. It breaks the invariant that every line ends at a grid edge or on another line.
- `dot-parse`: which `line_color` cells are dots
    - `concept`: every `line_color` cell that lies on no straight run of `line_color` cells between two markers in its row or column
    - `$IsolatedDots`: replaces `dot-recolor`'s dot set; only `line_color` cells whose four neighbors are all `background` are dots, and every other off-run `line_color` cell keeps its color. Undefined on the same inputs as the concept. Fits every pair. Witness `domino-dot`: breaks `loose-dots`, stands at the stored assignment, `variant`, verdict `concept`. It breaks the invariant that no two dots are 4-adjacent.
    - `$MarkerFreeParts`: replaces `dot-recolor`'s dot set; the dots are the `line_color` cells whose 4-connected part of non-`background` cells holds no marker. Undefined on the same inputs as the concept. Fits every pair. Witness `dot-touching-wall`: breaks `loose-dots`, stands at the stored assignment, `variant`, verdict `concept`. It breaks the invariant that no dot is 4-adjacent to a line cell.
- `background`: where the background color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` with the commonest color of the input, and is undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: dots fill each room in a checkerboard, so 1 outnumbers 0. It breaks `loose-dots`, stands at the stored assignment, `borderline`, verdict `concept`. It breaks the invariants that 0 is the commonest color of each input and that no dot is 4-adjacent to a line cell.
- `line_color`: where the line and dot color comes from
    - `concept`: stored, 1
    - `line_color=DominantColor`: replaces the stored `line_color` with the commonest color of the input, which is 0 at every pair. Fails Fit at train0.
- `room-connectivity` & `dot-parse`, `room-connectivity` & `background`, `dot-parse` & `background`: the two branches' changes applied together
- `marker-tally` and `line_color` have no branch other than the concept branch that fits, so they combine into no case.

## Open parameters
none

## Not formed
- A rule for a room whose markers tie (`clear-majority`): no pair, solver header, proposer or variant task gives a tie rule, because every room that holds a dot has a clear plurality in every input. The concept is undefined at a tie.
- `background` or `line_color` from SharedColor: on one input alone it gives every color of that input, so it fixes no single value and fails Fit at train0.
- `background` or `line_color` from a proposer that reads train outputs (UnchangedColor, ChangedColor, OutNewColor and the others): with `ex_out` empty it gives no value, so it is undefined at every pair.
- `line_color` from RarestColor: it gives a marker color (6 at train0), so the branch fails Fit at train0.
- A separate dot color: dots and lines take one color in every variant task the color group gives, so the dot color follows from `line_color` and is derived data.
- Rooms as the rectangles of the line tiling: on every input with `wall-lines`, these give the same cells as the 4-connected rooms. Where a line is broken, the model is the concept's or `$Rooms8`'s.
- The solver headers under the keywords `decompose` and `markers` give no other interpretation of this task.

## Tickets filed
none
