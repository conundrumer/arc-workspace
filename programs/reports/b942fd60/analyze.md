# b942fd60

## Concept
- The concept fails Fit at train 1, and no formed branch fits train 1.
    - In train 1, two rays run left along row 1, from (1,5) and from (1,4), and stop at (1,3) before the 8 at (1,2). The concept branches there: up to (0,3), and down over (2,3) to (3,3) before the 8 at (4,3), then left along row 3 to (3,0) and right to (3,4).
    - The train 1 output has 0 at (0,3), (3,0), (3,1) and (3,3), and agrees with the concept everywhere else. So the line ends at that 8 without branching. This is the defect the task's patch states for another cell ("ends line instead of splitting").
    - Every other pair and the test fit the concept. Every formed branch gives the concept's output on train 1, so "fits" below means fits every other pair.
    - The rule as the generator applies it: the concept's rule, with one stop in train 1 left without its branches.
    - A probe of the reading that an obstacle branches only the first ray that stops before it also fails train 1 (Not formed).
- Witnesses with verdict `other`: none.

## Choice points
- `seed-as-obstacle`
    - `concept`: the seed is no obstacle, and a ray runs over it.
    - `$SeedBlocks`: replaces `scattered-marks`' obstacle set in `ray-stops` with the obstacles and the seed; no new parameter; undefined where the concept is undefined. It fits. Witness `ray-meets-seed`: a ray runs left along the seed's row, and under `$SeedBlocks` it stops at (3,1) and branches down column 1. It breaks no scene claim; plausibility `ordinary`; verdict `concept`.
- `blocked-ray`
    - `concept`: a ray whose first cell is an obstacle stops at its start cell and branches there.
    - `$BlockedRayEnds`: replaces `branch` so that a ray that runs over no cell has no branches; no new parameter; undefined where the concept is undefined. It fits. Witness `seed-next-to-mark`: an 8 sits right next to the seed; the concept draws column 0, and `$BlockedRayEnds` draws nothing. It breaks no scene claim; plausibility `ordinary`; verdict `concept`.
- `start-direction`
    - `concept`: `start-dir` is stored, right.
    - `$StartFromSeedEdge`: replaces `first-ray` with a start direction derived as the direction away from the grid edge the seed lies on; undefined where the seed lies on no edge or on two edges. It fits. Witness `seed-on-top-edge`: the seed lies on the top edge; the concept shoots right along row 0, and `$StartFromSeedEdge` shoots down and branches before the 8. It breaks `one-seed`; it stands at the stored assignment; plausibility `variant`; verdict `$StartFromSeedEdge`; the invariant it breaks: the seed lies in column 0.
- `obstacles`
    - `concept`: every cell that is neither `background` nor `line-color` blocks a ray.
        - `background`
            - `concept`: `background` is stored, 0.
            - `background=DominantColor`: replaces the stored `background` with the commonest color of the input; undefined where two colors tie for commonest. It fits. Witness `background=DominantColor`: 8 outnumbers 0; the derived background is 8, the 0s block, and the rays paint over 8s. It breaks `scattered-marks`; plausibility `borderline`; verdict `concept`; the invariant it breaks: 0 is the commonest color of every input.
    - `$StoredObstacleColors`: replaces the obstacle set in `ray-stops` and `scattered-marks` with the cells whose color is in a stored set `obstacle-colors` (3, 6, 7, 8); a ray paints over a cell of any other color; no `background` parameter; undefined where the concept is undefined. It fits; the test's mark colors all lie in the set. Witness `mark-of-new-color`: a 4 stands in the first ray's path; the concept stops before it and branches, and `$StoredObstacleColors` paints over it and runs to the edge. It breaks no scene claim; plausibility `variant`; verdict `concept`; the invariant it breaks: every mark has one of the colors 3, 6, 7, 8.
- `line-color`
    - `concept`: `line-color` is stored, 2.
    - `line_color=RarestColor`: replaces the stored `line-color` with the color of fewest cells in the input; undefined where two colors tie for fewest. It fails Fit at train 2 (2, 7 and 8 each have one cell), and at trains 3, 4 and 5.
- `turn`
    - `concept`: a stop branches both ways at a right angle.
    - `$TurnOneWay`: replaces `branch` with one new ray that turns in a stored sense `turn-sense` (clockwise or counterclockwise). It fails Fit at train 0 at both senses.
- `edge-stop`
    - `concept`: a ray that stops at the grid edge ends (`edge-ends`).
    - `$EdgeBranches`: replaces `edge-ends` so that a ray that stops at the grid edge branches as at an obstacle. It fails Fit at train 0.
- `crossing`
    - `concept`: rays cross one another.
    - `$RaysStopAtRays`: adds to `ray-stops` that a ray ends, with no branches, before a cell that a ray reaching it in fewer steps from the seed paints. It fails Fit at train 5: the ray down column 1 from (1,1) would end at (2,1), before row 3, and the output paints column 1 to row 7.
- `seed-as-obstacle` & `blocked-ray`, `seed-as-obstacle` & `start-direction`, `seed-as-obstacle` & `obstacles`, `seed-as-obstacle` & `line-color`, `seed-as-obstacle` & `turn`, `seed-as-obstacle` & `edge-stop`, `seed-as-obstacle` & `crossing`, `blocked-ray` & `start-direction`, `blocked-ray` & `obstacles`, `blocked-ray` & `line-color`, `blocked-ray` & `turn`, `blocked-ray` & `edge-stop`, `blocked-ray` & `crossing`, `start-direction` & `obstacles`, `start-direction` & `line-color`, `start-direction` & `turn`, `start-direction` & `edge-stop`, `start-direction` & `crossing`, `obstacles` & `line-color`, `obstacles` & `turn`, `obstacles` & `edge-stop`, `obstacles` & `crossing`, `line-color` & `turn`, `line-color` & `edge-stop`, `line-color` & `crossing`, `turn` & `edge-stop`, `turn` & `crossing`, `edge-stop` & `crossing`, `background` & each point other than `obstacles`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A separate seed color beside `line-color`: the rays take the seed's color in every variant task the concept reads, so it is a redundant value.
- An obstacle branches only the first ray that stops before it: a probe over the pairs fails train 1 as well, under both orders of arrival tried (by ray generation and by cells run), and the order of arrival has no single relational form.
- `line-color` derived by `SharedColor` or `VanishedColor`: on one input alone each gives every color of that input, so the case gives several outputs at train 0 and fails Fit there.
- `line-color` or `background` derived by `OutNewColor`, `AnyOutNewColor`, `ChangedColor` or `UnchangedColor`: each reads `ex_out`, which is empty on one input, so it gives no value and the case is undefined on every pair.
- `background` derived by `RarestColor` or `SharedColor`: `RarestColor` gives 2 (and 7, 8 in train 2), and `SharedColor` gives every color, so each fails Fit at train 0.
- `start-dir` by a proposer: no proposer in `programs/proposers.dl` gives a direction; the derivation is `$StartFromSeedEdge`.
- Diagonal rays, or branches at 45 degrees: another orientation type; every line in the outputs is axis-aligned, so it fails Fit at every pair.

## Tickets filed
- 10-423_task_b942fd60_analyze.md
- 10-424_task_b942fd60_analyze.md
