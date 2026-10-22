# e5c44e8f

## Concept
- Fits every pair: on train0, train1 and test0 the path meets an obstacle before it leaves the grid, and the probe `probe.py` reproduces each output.
- Undefined where the path leaves the grid before it meets an obstacle, which breaks the scene claim `obstacle-before-edge` (witness `path-leaves-grid`, verdict `$EdgeStop`).
- No witness has verdict `other`.
- The rule as the generator applies it is the concept file's rule: arm lengths count cells, so each claim has a relational form and the concept runs no approximation.

## Choice points
- `edge-exit`: what the path does when it leaves the grid before it meets an obstacle
    - `concept`: the scene claim `obstacle-before-edge` holds, and the model is undefined where it does not
    - `$EdgeStop`: replaces `obstacle-before-edge` and adds to `stop-at-obstacle` that the path also ends at its last cell in the grid; no new parameters; defined on every one-seed input; fits every pair
        - witness `path-leaves-grid`: breaks `obstacle-before-edge`; stored assignment; plausibility `variant`; verdict `$EdgeStop`; invariant broken: in every input the path meets an obstacle before it leaves the grid
    - `$EdgeContinue`: replaces `obstacle-before-edge` and adds that the path goes on outside the grid with the same arms, paints the cells where it re-enters, and ends before its first obstacle in the grid, or after its last cell in the grid when it meets none; no new parameters; defined on every one-seed input; fits every pair
        - witness `path-leaves-grid`: breaks `obstacle-before-edge`; stored assignment; plausibility `variant`; verdict `$EdgeStop`; invariant broken: in every input the path meets an obstacle before it leaves the grid
- `blocking-colors`: which cells end the path
    - `concept`: cells of `obstacle_color`
    - `$AnyColorBlocks`: replaces `scattered-obstacles` and `stop-at-obstacle`: every cell that is neither `background` nor `seed_color` ends the path; reads `background` in place of `obstacle_color`; undefined where `one-seed` fails, as the concept is; fits every pair
        - witness `foreign-color-on-path`: breaks `scattered-obstacles`; stored assignment; plausibility `borderline`; verdict `$AnyColorBlocks`; invariant broken: every input holds only colors 0, 2 and 3
- `seed_color` determination
    - `concept`: stored, 3
    - `seed_color=RarestColor`: derives `seed_color` by the `RarestColor` proposer on the input alone, and replaces `one-seed` with the claim that the seed is the one cell of the input's one rarest color; undefined where two colors tie for rarest, such as an input with one obstacle cell; fits every pair, since 3 is the one rarest color of each input
        - witness `seed_color=RarestColor`: breaks `one-seed` at the stored `seed_color` 3; stored assignment; plausibility `variant`; verdict `seed_color=RarestColor`; invariant broken: the seed is color 3 in every input
- `paint-color`: the color the path takes
    - `concept`: derived, the seed's color (`paint-path`)
    - `paint_color=stored`: stores `paint_color`, 3, in place of `seed_color` in `paint-path`; undefined where the concept is; fits every pair
        - witness `paint_color=stored`: breaks no scene claim; stands at `seed_color` 4; plausibility `variant`; verdict `concept`; invariant broken: the seed is color 3 in every input
- `obstacle-response`: what the path does at its first obstacle
    - `concept`: it ends at the cell before it (`stop-at-obstacle`)
    - `$PassThrough`: replaces `stop-at-obstacle`: the path passes over obstacles, which keep their color; fails train0
    - `$TurnAtObstacle`: replaces `stop-at-obstacle`: the arm ends at the cell before the obstacle and the next arm starts there; fails train0
    - `$StopBeside`: replaces `stop-at-obstacle`: the path ends before its first cell that has an obstacle as a 4-neighbor; fails train0
- `arm-lengths`
    - `concept`: arm k has length (`gap` + 1) · (⌊k/2⌋ + 1)
    - `$ArmGrowth`: replaces `spiral-path`: each arm is one cell longer than the arm before it, from 2; `gap` does not exist with it; fails train0
- `edge-exit` & `blocking-colors`, `edge-exit` & `seed_color` determination, `edge-exit` & `paint-color`, `edge-exit` & `obstacle-response`, `edge-exit` & `arm-lengths`, `blocking-colors` & `seed_color` determination, `blocking-colors` & `paint-color`, `blocking-colors` & `obstacle-response`, `blocking-colors` & `arm-lengths`, `seed_color` determination & `paint-color`, `seed_color` determination & `obstacle-response`, `seed_color` determination & `arm-lengths`, `paint-color` & `obstacle-response`, `paint-color` & `arm-lengths`, `obstacle-response` & `arm-lengths`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived `first_dir`: the first arm goes up in all three inputs, and no property of the inputs selects up. The seed's nearest edge is left of up in train1 and right of up in test0, and the nearest obstacle is not above the seed in any input.
- A derived `turn_sense` or `gap`: no proposer gives a direction sense or a spacing, and both are constant over the pairs.
- A derived `obstacle_color`: no proposer gives 2 alone. `UnchangedColor` gives 2 and 3, and the clause derivation "every other color" is `$AnyColorBlocks`.
- Arms that turn when the cell ahead would touch the previous ring: this gives the same path as the arm-length rule on every input, so the model is equivalent to the concept.
- One spiral for each of several seeds: no pair, solver header or variant task gives how two spirals would meet, so no model could be stated from these sources.

## Tickets filed
- none
