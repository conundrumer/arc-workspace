# f341894c

## Concept
- Fits every pair: train0, train1, train2 and test0 (probe `work/task/f341894c/probe.py`). An arrow is the two `head_color`/`tail_color` cells next to each other along the line of a `marker_color` cell on the edge. That way of finding arrows splits the clumps correctly: the 2×2 clump in train2 at rows 4–5, cols 8–9, and in test0 the 2×4 block at rows 5–8, cols 8–9, the clump at (9,10),(10,10),(10,11),(11,11), and the 2×2 block at rows 13–14, cols 6–7.
- Corner markers stand on two edges, and only one of their two lines holds an arrow (train1 (0,7), train2 (0,0)). The scene claims `edge-markers` and `one-marker-per-arrow` say so.
- The concept is undefined on an arrow whose line has a marker at both ends. An arrow whose line has no marker stays as it is.
- In every input, the counts of `marker_color`, `head_color` and `tail_color` cells are equal, one marker per arrow.
- There is no witness with verdict `other`. The rule in the concept file is the rule as the generator applies it: on the marker's line, the cell nearer the marker is the head.

## Choice points
- `arrow-parse`
    - `concept`: an arrow is the two adjacent head/tail cells along a marker's line
    - `$ComponentArrow`: replaces `arrows` and `head-toward-marker`. An arrow is a 4-connected component of head/tail cells, mirrored as a whole along the marker's axis so that its head end faces the marker. It is undefined on a component whose rows or columns reach more than one marker. Fails Fit at train2: the component at rows 4–5, cols 8–9 reaches the markers of rows 4 and 5, and mirrored as a whole it would give `1 6 / 6 1` where the output is `1 6 / 1 6`.
- `marker-place`
    - `concept`: the marker is a `marker_color` cell on the edge, at the end of the arrow's line
    - `$MarkerInLine`: replaces `edge-markers`. The marker is the first `marker_color` cell the arrow's line reaches on either side, anywhere in the grid. Undefined where it reaches one on both sides. Fits every pair. Witness `interior-marker`: it breaks `edge-markers`, stands at the stored assignment, plausibility `borderline`, verdict `$MarkerInLine`. It breaks the invariant that every `marker_color` cell is on the border.
- `two-markers`
    - `concept`: an arrow whose line has a marker at each end is undefined
    - `$NearerMarker`: replaces `one-marker-per-arrow`. With a marker at each end, the head turns toward the nearer one, and the model is undefined at equal distance. Fits every pair. Witness `markers-both-ends`: it breaks `one-marker-per-arrow`, stands at the stored assignment, plausibility `borderline`, verdict `$NearerMarker`. It breaks the invariant that each arrow line holds one marker.
- `arrow-parse` & `marker-place`, `arrow-parse` & `two-markers`, `marker-place` & `two-markers`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- head and tail swapped (the tail points away from the marker): this is the concept's own model, so it is no branch.
- the head points to the nearer or the farther grid edge, with no marker: train0 (2,0)–(2,1) has its head away from the nearer edge, and the arrow at (4,4)–(4,5) of the 10-wide grid is the same distance from both edges, so no such rule fits.
- turning the arrow about its tail toward the marker: at train0 (4,4)–(4,5) this would move the head to (4,6), where the output keeps the arrow in place. Turning about the center is the concept's swap.
- an arrow at right angles to its marker's line: no input shows one, and no swap or turn of a two-cell arrow lands its head on that line's marker, so no reading gives an output.
- recoloring a marker line's head/tail cells alternately from the marker, without finding arrows: every marker line in the evidence holds exactly two head/tail cells, and that reading differs only where another arrow's cell crosses the line. No natural statement of the task reads it that way.
- deriving `marker_color`, `head_color` or `tail_color` by a proposer: the three colors have equal counts in every input, so RarestColor proposes all three, and no listed proposer separates them. They stay stored.
- `background` read by the program: the rule keeps every non-arrow cell, so no program reads it.

## Tickets filed
- none
