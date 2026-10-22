# d687bc17

## Concept
- Fits every pair, the test included (`check_concept.py`, `probe.py`). Every rule has a relational form, and no witness has the verdict `other`.
- The concept reads each wall's color from the input and stores only `background`.
- The concept is undefined where dots of two walls land on one interior corner cell, for example a top-wall dot in col 1 and a left-wall dot in row 1. Such an input breaks `no-landing-clash`, and every branch below is undefined there too.
- On `same-line-clash` the verdict goes to `$Stack`, and on `bent-object` it goes to `$MoveObjects`. Both inputs break a scene claim.

## Choice points
- `landing-clash`
    - `concept`: dots of one color that land on one cell merge into one dot there.
    - `$Stack`: replaces `dot-to-wall`. The dots of one wall's color fall together toward that wall as Gravity bodies, so a later dot in the same line stops against the one already landed. Defined wherever the concept is. Fits every pair. Witness `same-line-clash` breaks `no-landing-clash`, at the stored assignment, plausibility `variant`, verdict `$Stack`. Invariant broken: in every input, no two dots of one wall's color share a line perpendicular to that wall.
- `moving-unit`
    - `concept`: each dot cell moves alone.
    - `$MoveObjects`: replaces `dot-to-wall` and `scattered-dots`. Each one-color 4-connected object moves rigidly toward its wall's color until it touches the wall. Defined wherever the concept is. Fits every pair. Witness `bent-object` breaks `scattered-dots`, at the stored assignment, plausibility `borderline`, verdict `$MoveObjects`. Invariant broken: every non-background interior cell is a single cell with no non-background neighbor, diagonals included.
- `unmatched-dot`
    - `concept`: a dot of no wall's color becomes `background` (`unmatched-dot-erased`).
    - `$KeepUnmatched`: replaces `unmatched-dot-erased`, and a dot of no wall's color stays where it is. Fails Fit at train0, where the 7 at input (4,7) is 0 in the output.
- `obstacles`
    - `concept`: no dot blocks another.
    - `$Blocked`: replaces `dot-to-wall`. A dot stops before the first other input dot on its path. Fails Fit at train0, where the 2 at input (7,11) passes the 4 at (7,9) and lands at output (7,1).
    - `$BlockedByUnmatched`: replaces `dot-to-wall`. A dot stops before the first dot of no wall's color on its path. Fails Fit at test0, where the 2 at input (3,3) passes the 3 at (3,14) and lands at output (3,15).
- `shared-wall-color`
    - `concept`: a dot goes to every wall of its color, one copy per wall.
    - `$NearerWall`: replaces `dot-to-wall`, and drops `distinct-wall-colors`. A dot goes only to the nearer wall of its color. Undefined where two walls of its color are at equal distance from it. Fits every pair. Witness `two-walls-one-color` breaks `distinct-wall-colors`, at the stored assignment, plausibility `borderline`, verdict `$NearerWall`. Invariant broken: the four walls have four different colors.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: derives `background` on each input as its most common color. Undefined on no input. Fits every pair. Witness `background=DominantColor` breaks no scene claim, at the stored assignment, plausibility `borderline`, verdict `concept`. Invariant broken: inputs are at least 10 rows tall and their interior is mostly background, so 0 is the most common color by a wide margin.
    - `background=SharedColor`: derives every color of the input. Fails Fit at train0, where the values other than 0 give outputs that differ from the train output.
    - `background=RarestColor`: derives the least common color of the input. Fails Fit at train0, where it gives 7.
- `landing-clash` & `moving-unit`, `landing-clash` & `unmatched-dot`, `landing-clash` & `obstacles`, `landing-clash` & `shared-wall-color`, `landing-clash` & `background`, `moving-unit` & `unmatched-dot`, `moving-unit` & `obstacles`, `moving-unit` & `shared-wall-color`, `moving-unit` & `background`, `unmatched-dot` & `obstacles`, `unmatched-dot` & `shared-wall-color`, `unmatched-dot` & `background`, `obstacles` & `shared-wall-color`, `obstacles` & `background`, `shared-wall-color` & `background`: the two branches' changes applied together.
    - Example: `$Stack & $MoveObjects` drops the objects of one wall's color together as Gravity bodies. On `bent-object` it gives the `$MoveObjects` output, and on `same-line-clash` it gives the `$Stack` output.

## Open parameters
- none

## Not formed
- The moved dot also stays at its own cell: no reading of the pairs gives it, and every train output clears the cell of every dot.
- Which color takes an interior corner cell that dots of two walls both land on: no pair, and no variant task the evidence suggests, orders the walls. So no model can be stated, and every case is undefined there.
- Walls found anywhere as full-length lines instead of at the grid border: `four-walls` holds on every input, and such a model differs only on inputs whose border is not four walls, where the concept is not stated.

## Tickets filed
- 10-725_task_d687bc17_analyze.md
