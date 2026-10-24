# ecdecbb3

## Concept
- Fits every pair (train0–2, test0), checked by `work/task/ecdecbb3/check_concept.py` and the probe `work/task/ecdecbb3/probe.py`. Every rule (`keep-input`, `beam`, `hit-cell`, `bracket`) has a relational form: a beam runs between a dot and the nearest full line on its axis, and the bracket is the Chebyshev ring of radius `ring_radius` around the hit cell. No witness has verdict `other`, and the concept file's rules are the generator's rules as stated, so nothing is approximated.
- The pairs fix the layer of a bracket over its own beam (train0 (5,2), train1 (4,4), (4,13), test0 (1,13)). They also fix a stop at the nearest wall on each side (train2 dot (2,8) does not reach row 13), a beam toward both walls when the dot sits between two (train1 dot (4,8), 5 and 6 cells from its walls), and no beam on a side with no wall (train0 dot (2,2) upward).
- The axis of the walls varies by pair (horizontal in train0 and train2, vertical in train1 and test0), so the program reads it from the input and stores no axis.
- Walls of other colors, dots of other colors, and the color-permuted variant tasks they stand for make the two color-deriving branches the expected readings at `variant` plausibility (`walls-other-color`, `dots-other-color`).

## Choice points
- `beam-reach`: which wall on a side stops a beam
    - `concept`: the nearest wall on that side, which the beam does not cross
    - `$BeamThroughWalls`: replaces `beam`, `hit-cell`: the beam crosses every wall on its side and stops at the farthest, with a hit cell and a bracket at each wall it crosses. Parameters: those of the concept. Undefined on no input. Fails Fit at train2: dot (2,8) would reach row 13 and draw a bracket at (13,8).
- `beam-sides`: which sides of a dot get a beam
    - `concept`: each of the two sides across the wall axis that has a wall
        - `no-wall-side`: what a side with no wall gets
            - `concept`: nothing
            - `$BeamToEdge`: replaces `beam`: on a side with no wall, the beam runs to the grid edge, with no hit cell and no bracket. Parameters: those of the concept. Undefined on no input. Fails Fit at train0: dot (2,2) would paint rows 0–1 of col 2.
    - `$NearestSideOnly`: replaces `beam`: only the side whose wall is nearer gets a beam, both on a tie. Parameters: those of the concept. Undefined on no input. Fails Fit at train1: dot (4,8) is 5 cells from col 3 and 6 from col 14, and the output beams to both. The side with no wall gets nothing under this branch whatever `no-wall-side` says, so that point stands under the concept branch.
- `wall-parse`: what stops a beam
    - `concept`: a full-length line of `line_color`
    - `$StopAtLineCell`: replaces `beam`, `hit-cell`: a beam stops at the first `line_color` cell on its path, full line or not, and that cell is the hit cell. Parameters: those of the concept. Undefined on no input. Fits every pair. Witness `partial-wall` (a segment of 8 at row 6 cols 4–8, between the dot (10,6) and the full wall at row 2): breaks no scene claim, since `walls` does not exclude extra cells of `line_color`. Stands at the stored assignment. Plausibility `borderline`, verdict `$StopAtLineCell`. It breaks the invariant that every `line_color` cell lies on a full-length wall.
- `beam-layer`: the layer of a bracket against its dot's beam
    - `concept`: the bracket covers the beam
    - `$BeamOverBracket`: replaces `bracket`: the beam cells between a dot and its hit cell keep `mark_color` over every bracket. Parameters: those of the concept. Undefined on no input. Fails Fit at train0: (5,2) and (7,8) are 8 in the output.
- `hit-layer`: the layer of a hit cell against another hit's bracket
    - `concept`: brackets cover every cell but their own hit cell, the other hit cells included
    - `$CenterOnTop`: replaces `bracket`: every hit cell keeps `mark_color` over every bracket. Parameters: those of the concept. Undefined on no input. Fits every pair. Witness `adjacent-hits` (dots (4,2) and (5,10) hit the wall at col 6 in adjacent cells): breaks no scene claim. Stands at the stored assignment. Plausibility `borderline`, verdict `$CenterOnTop`. It breaks the invariant that no two brackets overlap.
- `dot-layer`: the layer of a dot against a bracket
    - `concept`: a bracket covers a dot
    - `$DotOnTop`: replaces `bracket`: every dot keeps its color over every bracket. Parameters: those of the concept. Undefined on no input. Fits every pair. Witness `dot-beside-wall` (dot (4,5) beside the wall at col 6): breaks scene claim `dots` (at least 3 cells from a wall). Stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every dot is at least 3 cells from every wall.
- `bracket-edge`: a bracket that reaches past the grid
    - `concept`: the bracket is clipped to the grid
    - `$WholeBracketOnly`: replaces `bracket`: a bracket is drawn only where all of its cells lie in the grid, and the beam and hit cell are still drawn. Parameters: those of the concept. Undefined on no input. Fits every pair. Witness `bracket-past-edge` (dot (0,8) right of the wall at col 4): breaks no scene claim. Stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `mark-color`: how `mark_color` is determined
    - `concept`: stored, 2
    - `mark_color=RarestColor`: derives `mark_color` on each input as each color whose cell count is lowest there, ties included. Replaces `dots`, `beam`, `hit-cell`. Undefined on no input. Fits every pair, since 2 is the rarest color in train0–2 and test0. Witness `mark_color=RarestColor` (eight dots against a 7-cell wall): breaks no scene claim. Stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that `mark_color` is the rarest color of every input.
    - `$BeamInDotColor`: derives a mark color per dot as its own color, a dot being any cell that is neither `background` nor on a wall. Replaces `dots`, `beam`, `hit-cell`, and reads `background`, which becomes a parameter. Undefined on no input. Fits every pair. Witness `dots-other-color` (two dots of 3 beside a wall of 8): breaks scene claim `dots` (dots of `mark_color`). Stands at the stored assignment. Plausibility `variant`, verdict `$BeamInDotColor`, an output `mark_color=RarestColor` also gives.
- `line-color`: how `line_color` is determined
    - `concept`: stored, 8
    - `$LineColorFromLines`: derives the walls as the full-length lines of any color other than `background`, each bracket taking its wall's color. Replaces `walls`, `beam`, `bracket`, and reads `background`, which becomes a parameter. Undefined on no input. Fits every pair. Witness `walls-other-color` (a wall of 3 with dots of 2): breaks scene claim `walls` (lines of `line_color`). Stands at the stored assignment. Plausibility `variant`, verdict `$LineColorFromLines`.
- `beam-reach` & `beam-sides`, `beam-reach` & `no-wall-side`, `beam-reach` & `wall-parse`, `beam-reach` & `beam-layer`, `beam-reach` & `hit-layer`, `beam-reach` & `dot-layer`, `beam-reach` & `bracket-edge`, `beam-reach` & `mark-color`, `beam-reach` & `line-color`, `beam-sides` & `wall-parse`, `beam-sides` & `beam-layer`, `beam-sides` & `hit-layer`, `beam-sides` & `dot-layer`, `beam-sides` & `bracket-edge`, `beam-sides` & `mark-color`, `beam-sides` & `line-color`, `no-wall-side` & `wall-parse`, `no-wall-side` & `beam-layer`, `no-wall-side` & `hit-layer`, `no-wall-side` & `dot-layer`, `no-wall-side` & `bracket-edge`, `no-wall-side` & `mark-color`, `no-wall-side` & `line-color`, `wall-parse` & `beam-layer`, `wall-parse` & `hit-layer`, `wall-parse` & `dot-layer`, `wall-parse` & `bracket-edge`, `wall-parse` & `mark-color`, `wall-parse` & `line-color`, `beam-layer` & `hit-layer`, `beam-layer` & `dot-layer`, `beam-layer` & `bracket-edge`, `beam-layer` & `mark-color`, `beam-layer` & `line-color`, `hit-layer` & `dot-layer`, `hit-layer` & `bracket-edge`, `hit-layer` & `mark-color`, `hit-layer` & `line-color`, `dot-layer` & `bracket-edge`, `dot-layer` & `mark-color`, `dot-layer` & `line-color`, `bracket-edge` & `mark-color`, `bracket-edge` & `line-color`, `mark-color` & `line-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `ring_radius` derived from the input (for example from a wall's width): every wall is one cell wide and no proposer gives a value that tracks the bracket. A wall wider than one cell needs a different parse of walls, which no claim of the concept makes.
- `line_color` by a proposer: no Color proposer gives 8 alone. 8 is not unchanged (hit cells turn 2), not changed, not dominant, not rarest, and not new. SharedColor gives 0, 2 and 8 together, and CountRankDesc gives a rank, not a color.
- `mark_color=UnchangedColor` and `mark_color=SharedColor`: UnchangedColor reads the outputs, which a `@derive` run on one input lacks. SharedColor gives 0, 2 and 8 together, so the model paints from every cell and fails Fit at train0.
- walls on both axes at once: this breaks scene claim `walls` (one axis), and no reading of the pairs separates a beam along one axis from beams along both.
- a dot with no wall on either side, or a dot on a wall: each breaks scene claim `dots`. On the first, every branch draws nothing. On the second, the line holding the dot is no longer a full line of `line_color`, so it is not a wall, and no claim has a different reading there.
- per-dot drawing order (one dot's bracket under a later dot's beam): no relation of the task orders the dots, so the order has no relational form.

## Tickets filed
- none
