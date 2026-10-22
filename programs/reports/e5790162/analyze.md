# e5790162

## Concept
- Fits every train pair and the test pair (`check_concept.py`, `probe.py`).
- Each rule has a relational form: the walk is a finite set of (cell, heading) states reached from the start, so the concept needs no approximation.
- No witness has the verdict `other`.
- `turn_sense` is a lookup table keyed by marker color. The test uses only 6 and 8, which the train pairs hold, so it has no unseen key.

## Choice points
- `start-heading`
    - `concept`: the stored `start_dir` gives the heading of the first step.
    - `$HeadAwayFromEdge`: replaces `walk`'s stored heading with the heading away from the one frame edge the start cell is on. It has no `start_dir`. It is undefined where the start cell is on no frame edge or on two. It fits every pair. Witness `start-on-top-edge`: it breaks `start-cell`, stands at the stored assignment, has plausibility `variant` and verdict `$HeadAwayFromEdge`, and breaks the invariant that the start cell is in col 0 of every input.
    - `$HeadTowardMarker`: replaces `walk`'s stored heading with the heading toward the nearest marker in line with the start cell. It has no `start_dir`. It is undefined where no marker is in line with the start cell, or where two are nearest at one distance. It fits every pair. Witness `no-marker-in-start-row`: it breaks `every-marker-met`, stands at the stored assignment, has plausibility `borderline` and verdict `concept`, and breaks the invariant that a marker is in the start row, ahead of the start cell, in every input.
- `path-color`
    - `concept`: the stored `path_color` gives the start cell's color and the line's color.
    - `$StartIsNonMarker`: replaces `start-cell`'s stored color with the one color of the input that is not `background` and has no `turn_sense` row. It has no `path_color`, and it reads `background`. It is undefined where the input holds no such color or more than one. It fits every pair. Witness `start-of-another-color`: it breaks `start-cell`, stands at the stored assignment, has plausibility `variant` and verdict `$StartIsNonMarker`, and breaks the invariant that the start cell is 3 in every input.
    - `path_color=SharedColor`: derives `path_color` from each input alone. That gives every color of the input, {0, 3, 6} on train0. It fails Fit at train0.
    - `path_color=RarestColor`: derives `path_color` from each input alone. That gives {3, 6} on train0, so a line also grows from the 6. It fails Fit at train0.
    - `path_color=DominantColor`: derives `path_color` from each input alone. That gives {0} on every input, so no line grows from the 3. It fails Fit at train0.
- `turn-frame`
    - `concept`: a marker's color gives a turn sense relative to the line's heading.
    - `$AbsoluteTurn`: replaces `turn-at-marker` with a fixed heading per marker color (6 → down, 8 → up), stored in place of `turn_sense`. It fails Fit at train1, where the line heads down into the 8 at (6,3) and turns east.
- `blocked-turn`
    - `concept`: after a turn, a marker directly ahead turns the line again.
    - `$StopWhenBlocked`: adds to `turn-at-marker` that the line stops where a marker is directly ahead of it after a turn. It fits every pair. Witness `marker-ahead-after-turn`: it breaks `line-exits`, stands at the stored assignment, has plausibility `borderline` and verdict `concept`, and breaks the invariant that no marker is directly ahead of the line after a turn.
- `trail-meeting`
    - `concept`: the line passes over the cells of its own trail.
    - `$StopAtTrail`: adds to `walk` that the line stops before a cell it has already visited. It fits every pair. Witness `line-crosses-trail`: it breaks `line-exits`, stands at the stored assignment, has plausibility `borderline` and verdict `concept`, and breaks the invariant that the line never meets its own trail.
- `passable-cells`
    - `concept`: the line passes over every cell that is not a marker.
    - `$OnlyBackgroundPassable`: adds to `walk` that the line stops before a cell that is not `background`. It reads `background`. It fits every pair. Witness `other-color-on-line`: it breaks `start-cell`, stands at the stored assignment, has plausibility `foreign` and verdict `any`, and breaks the invariant that every input holds only the colors 0, 3, 6 and 8.
- `start-count`
    - `concept`: each cell of `path_color` grows a line.
    - `$SingleStart`: adds to `start-cell` that the model is undefined unless the input holds exactly one cell of `path_color`. It fits every pair. Where it is defined, its output is the concept's, so it fails Subsumption. No witness exists on which it is defined and differs. Witness `two-start-cells`: it is undefined there, the concept draws two lines, and the witness breaks `start-cell`, stands at the stored assignment, has plausibility `borderline` and verdict `concept`, and breaks the invariant that each input holds one 3 cell.
- `start-heading` & `path-color`, `start-heading` & `turn-frame`, `start-heading` & `blocked-turn`, `start-heading` & `trail-meeting`, `start-heading` & `passable-cells`, `start-heading` & `start-count`, `path-color` & `turn-frame`, `path-color` & `blocked-turn`, `path-color` & `trail-meeting`, `path-color` & `passable-cells`, `path-color` & `start-count`, `turn-frame` & `blocked-turn`, `turn-frame` & `trail-meeting`, `turn-frame` & `passable-cells`, `turn-frame` & `start-count`, `blocked-turn` & `trail-meeting`, `blocked-turn` & `passable-cells`, `blocked-turn` & `start-count`, `trail-meeting` & `passable-cells`, `trail-meeting` & `start-count`, `passable-cells` & `start-count`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Turn senses that alternate from turn to turn, with no reading of the marker color: train0's only turn is clockwise and train3's only turn is counterclockwise, so no stored first sense fits both.
- The line turns toward the next marker: the last turn of train0, train3 and the test has no next marker to turn toward, so the color still gives the sense there. At every other turn of every pair, the next marker is on the side the color gives. The reading is the concept plus a check that `every-marker-met` already states.
- A line color that differs from the start cell's color: the two are one color in every pair, and in every variant task the line color follows from the start color, so it is a redundant value and no second parameter.

## Tickets filed
- none
