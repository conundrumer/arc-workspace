# faa9f03d

## Concept
- Fits every train and test pair (`work/task/faa9f03d/check_concept.py`, `work/task/faa9f03d/probe.py pairs`).
- Undefined where a crossing that shows `background` has no other crossing of the same two wires, where three wires share a cell, or where a `turn_color` cell does not touch exactly one wire cell.
- No witness has verdict `other`.
- How the generator lays the wires at crossings is the weak point. The pairs show the under wire at every crossing that involves a marked wire (train0 (3,3), (5,4), (8,6); train2 (3,2), (4,9); test (7,1)), and the over wire at the only shown crossing of two unmarked wires (train3 (2,1)). `crossing-top` approximates the generator's layering this way: the depth of a crossing is read from the input cell, and it is inverted when one of the two wires carries a `corner_color` marker. The generator probably keeps a depth order of the wires and draws the under wire at a crossing on damaged wires. The pairs fix no rule for that order (color, orientation, length, turn count and reading order are each contradicted by some pair).

## Choice points
- `crossing-top`
    - `concept`: the shown wire is on top unless one of the two wires carries a `corner_color` marker. The wire a `turn_color` cell extends is on top. A `background` crossing takes the top of the same two wires' other crossings.
    - `$FlipAlways`: replaces `crossing-top`; the input always shows the under wire. No parameters. Undefined where the concept is. Fails Fit at train3: at (2,1) it gives 6 where the output has 1.
    - `$KeepShown`: replaces `crossing-top`; the shown wire is always on top. No parameters. Undefined where the concept is. Fails Fit at train0: at (3,3), (5,4) and (8,6) it gives 3 where the output has 1.
    - `$FlipByGridMarker`: replaces `crossing-top`; every shown crossing is inverted when the grid holds any `corner_color` cell. Parameter `corner_color`. Undefined where the concept is. Fits every pair. Witness `unmarked-crossing-beside-marked-wire`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$FlipBySegmentMarker`: replaces `crossing-top`; a shown crossing is inverted when the straight run of either wire through it ends at a `corner_color` cell. Parameter `corner_color`. Undefined where the concept is. Fits every pair. Witness `unmarked-run-of-marked-wire`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$ExtensionNotOnTop`: replaces the clause of `crossing-top` that puts the extended wire on top; cells the turn extends get the shown-wire rule like any other crossing. No parameters. Undefined where the concept is. Fails Fit at train1: at (2,10) it gives 7 where the output has 3.
- `strand-erased`
    - `concept`: the whole strand that runs straight on from the corner, to its end
    - `$EraseRunOnly`: replaces `reroute-at-turn`; only that strand's first straight run is erased. No parameters. Undefined where the concept is. Fails Fit at test0: col 4 rows 0–3 stay 7 where the output has 0.
- `turn-arm-extent`
    - `concept`: the arm through the `turn_color` cell runs to the grid edge
    - `$TurnStrandLength`: replaces `reroute-at-turn`; the arm takes the length of the erased first run. No parameters. Undefined where the concept is. Fails Fit at train3: the arm stops at row 4 where the output runs to row 11.
- `break-width`
    - `concept`: one-cell breaks are filled
    - `$AnyWidthBreaks`: replaces `breaks` and `redraw-wires`; a break of any width along a run is filled. No parameters. Undefined where the concept is. Fits every pair. Witness `wide-break`: breaks scene claim `breaks`, `variant`, verdict `$AnyWidthBreaks`. It breaks the input invariant that every break is one cell wide.
- `free-ends`
    - `concept`: a wire end that does not reach the edge stays where it is
    - `$ExtendAllEnds`: adds the claim that every free wire end runs straight on to the grid edge, on top at crossings. No parameters. Undefined where the concept is. Fits every pair. Witness `short-wire-end`: breaks scene claim `wires`, `variant`, verdict `$ExtendAllEnds`. It breaks the input invariant that every wire end, apart from one at a turn marker, lies on the grid edge.
- `corner-paint`
    - `concept`: `corner_color` cells take the wire's color
    - `$KeepCornerMarkers`: replaces `redraw-wires`; `corner_color` cells keep `corner_color`. No parameters. Undefined where the concept is. Fails Fit at train0: (3,0), (3,4), (8,4) and (8,9) stay 2.
- `background`
    - `concept`: stored `background` = 0
    - `background=DominantColor`: derives `background` as the commonest color of the input. Undefined where the concept is, and also where colors tie for commonest. Fits every pair. Witness `background=DominantColor`: breaks no scene claim, `foreign`, verdict `concept`. It breaks the input invariants that background is the commonest color and that every grid is 12×12 and mostly background.
- `corner_color`
    - `concept`: stored `corner_color` = 2
    - `corner_color=RarestColor`: derives `corner_color` as the rarest color of the input. Undefined where the concept is, and also on ties. Fails Fit at train3: the rarest color is 4, so 6 counts as marked and (2,1) inverts to 6.
- `turn_color`
    - `concept`: stored `turn_color` = 4
    - `turn_color=RarestColor`: derives `turn_color` as the rarest color of the input. Undefined where the concept is, and also on ties. Fails Fit at train0: the rarest color is 2, and 2 cells with two wire neighbours leave the model undefined.
- `crossing-top` & `strand-erased`, `crossing-top` & `turn-arm-extent`, `crossing-top` & `break-width`, `crossing-top` & `free-ends`, `crossing-top` & `corner-paint`, `crossing-top` & `background`, `crossing-top` & `corner_color`, `crossing-top` & `turn_color`, `strand-erased` & `turn-arm-extent`, `strand-erased` & `break-width`, `strand-erased` & `free-ends`, `strand-erased` & `corner-paint`, `strand-erased` & `background`, `strand-erased` & `corner_color`, `strand-erased` & `turn_color`, `turn-arm-extent` & `break-width`, `turn-arm-extent` & `corner-paint`, `turn-arm-extent` & `background`, `turn-arm-extent` & `corner_color`, `turn-arm-extent` & `turn_color`, `break-width` & `free-ends`, `break-width` & `corner-paint`, `break-width` & `background`, `break-width` & `corner_color`, `break-width` & `turn_color`, `free-ends` & `corner-paint`, `free-ends` & `background`, `free-ends` & `corner_color`, `free-ends` & `turn_color`, `corner-paint` & `background`, `corner-paint` & `corner_color`, `corner-paint` & `turn_color`, `background` & `corner_color`, `background` & `turn_color`, `corner_color` & `turn_color`: the two branches' changes applied together
- `turn-arm-extent` & `free-ends`: the model of `$ExtendAllEnds` alone. The arm that `$TurnStrandLength` leaves short is a free end, and `$ExtendAllEnds` runs it on to the edge. The probe gives the two one output on every pair and witness. So `turn-arm-extent` exists only under the concept branch of `free-ends`, and it stands at the concept.
    - `$TurnStrandLength` & `$ExtendAllEnds`: the model of `$ExtendAllEnds`

## Open parameters
none

## Not formed
- A stored color-pair priority at crossings (lookup table): the test's pair of wires (6, 7) is a key no train pair has (Unseen key), and train2 (6 over 1) and train3 (1 over 6) contradict each other on one key.
- Over-wire by orientation: in train0, 1 is on top both as the vertical wire at (3,3) and as the horizontal wire at (5,4).
- Over-wire by shorter path, by fewer or more turns, or by reading order of its first cell: contradicted, in order, by test0 (the longer 7 is on top), by train1 (3, with 2 turns, beats 7 with 7) against train0 (1, with 6 turns, beats 3 with 3), and by train2 (6 first and on top) against train0 (3 first and under).
- The turn arm as the mirror image of the erased strand: in train3 it stops at row 4 where the output runs to row 11, the same failure as `$TurnStrandLength`.
- Other proposers for `background`, `corner_color` and `turn_color`: SharedColor gives every color of the one input it reads, and the proposers that read outputs give nothing under `@derive`.

## Tickets filed
- none
