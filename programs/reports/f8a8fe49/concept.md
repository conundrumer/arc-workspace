# f8a8fe49

## Concept
- Two brackets face each other with marks between them; each mark flips out through the back of the bracket it is nearer to, mirrored about that bracket's back line, and the inside is left empty.

## Scene
- `background`: every cell that is not a bracket or a mark is `background` (0).
- `two-facing-brackets`: two brackets of `bracket_color` (2), each a straight base line with a cell of `arm_length` (1) at each end pointing toward the other bracket; the two bases are parallel, on one axis, with their ends aligned.
- `marks-between`: every `mark_color` (5) cell lies strictly between the two brackets' arm lines and within the span of the bases.
- `no-midline`: the lines strictly between the two bases are even in number, so every mark is strictly nearer one base than the other.
- `marks-touch-arm-line`: the marks nearer each bracket include a cell on the line next to that bracket's arm line.
- `mirror-in-frame`: each mark's mirror image across its nearer base lies inside the grid on a background cell.

## Rules
- `brackets-stay`: every bracket cell is kept.
- `marks-mirror-out`: each mark cell is painted `mark_color` at its mirror image across the base line of the bracket it is nearer to: a mark at distance d inside that base lands at distance d outside it.
- `inside-cleared`: each mark's input cell becomes background.

## Parameters
- `bracket_color`: 2
- `mark_color`: 5
- `background`: 0

## Scene parameters
- `arm_length`: 1
    - the length of each bracket's arm, perpendicular to its base
