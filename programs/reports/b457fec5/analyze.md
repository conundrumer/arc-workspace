# b457fec5

## Concept
- The concept case fits every pair (probe.py), and each of its claims has a relational form. No witness has the verdict `other`. The rule `step-paint` is the rule the generator applies, not an approximation.
- The pairs show two invariants that the concept states as scene claims: the key lies in row 1 (`key-side`), and in each of the five trails the number of square positions T + 1 is a multiple of the key length K (`whole-cycles`).

## Choice points
- `head-end`: which end of a trail the slide starts at
    - `concept`: the end toward the stored `head-dir`
    - `$HeadNearKeyLine`: replaces `head-end`. The head is the end whose square lies nearer the key's line, measured across the key's axis. `head-dir` is dropped. Undefined where the two end squares lie equally near that line, or where the key is no line. Fits every pair.
        - witness `key-below`: breaks `key-line` (the key lies one line in from the bottom edge, not the `key-side` edge). Stored assignment. Plausibility `variant`, verdict `$HeadNearKeyLine`. Invariant broken: the key lies in row 1 of every input.
    - `$HeadNearKey`: replaces `head-end`. The head is the end whose square has the least cell distance (Chebyshev) to a key cell. `head-dir` is dropped. Undefined on a tie. Fails Fit at train2: for the right trail the far square is at distance 7 from the key and the head square at 9, so it starts the slide at the bottom-left. It fails test0 the same way. By Manhattan distance the two ends of train2's right trail tie at 9, so that form is undefined there and fails Fit too.
- `key-order`: the order of the key colors
    - `concept`: from the key's end toward the stored `key-start`
    - `$KeyLexOrder`: replaces `key-order` and the axis part of `key-line`. The key cells are read in reading order (`LexOrder`: rows first, then columns, from the top-left corner), and the corner and primary axis stand in place of `key-start`. Undefined where the key is not a straight line. Fits every pair.
        - witness `vertical-key`: breaks `key-line` (the key is vertical, not along the axis of `key-start`). Stored assignment. The concept is undefined there. Plausibility `variant`, verdict `$KeyLexOrder`. Invariant broken: the key is horizontal in every input.
    - `$KeyFromHeadSide`: replaces `key-order`. For each trail, the key is read from its end on the side of that trail's head corner along the key's axis. `key-start` is dropped. Fails Fit at train1: the head is at the top-right, so it reads 4 3 1, and the output starts at the head with 1.
- `cycle-phase`: where the color cycle is anchored along a trail
    - `concept`: step 0, at the head, takes c0
    - `$CycleFromTail`: replaces `step-paint`. Step t takes c((t + K − 1 − T) mod K), so the far square takes c(K−1). Fits every pair.
        - witness `partial-cycle`: breaks `whole-cycles` (4 positions, K = 3). Stored assignment. Plausibility `borderline`, verdict `concept`. Invariant broken: T + 1 is a multiple of K in every trail.
- `far-square`: how the square at the far end is painted
    - `concept`: the last step paints its whole square in c(T mod K)
    - `$TailLastColor`: replaces `step-paint` at the far square. The far square is solid c(K−1), and every other step is as in the concept. Fits every pair.
        - witness `partial-cycle`: breaks `whole-cycles`. Stored assignment. Plausibility `borderline`, verdict `concept`. Invariant broken: T + 1 is a multiple of K in every trail.
    - `$Unclamped`: replaces `step-paint`. The nested L stripes run on through the far square, so a cell takes c(min(u, v) mod K). Fails Fit at train0: at train0 output (16,13) it gives 1, and the output is 8.
- `background`: the background color
    - `concept`: stored `background` 0
    - `background=DominantColor`: derives `background` as the input's commonest color. Undefined on a tie. Fits every pair.
        - witness `background=DominantColor`: breaks `background` (the background is 7). Stored assignment. The concept is undefined there, because the 7 cells join the key. Plausibility `variant`, verdict `background=DominantColor`. Invariant broken: the background is 0 in every input.
    - `background=SharedColor`: derives `background` as each color of the input. On one input that gives every color the input has, so there is no single background. Fails Fit at train0.
- `shape-color`: the color of the trails
    - `concept`: stored `shape-color` 5
    - `$ShapeColorBulk`: derives `shape-color` as the one non-background color with more than one cell. Undefined where there is not exactly one. Fits every pair.
        - witness `trail-recolored`: breaks `diagonal-trail` (the trail is 6). Stored assignment. The concept is undefined there. Plausibility `variant`, verdict `$ShapeColorBulk`. Invariant broken: the trails are 5 in every input.
    - `shape-color=ChangedColor`: derives `shape-color` from cells that change between input and output. In a run on an input, `ex_out` is empty, so it gives no value and the case is undefined. Fails Fit at train0.
    - `shape-color=SharedColor`: derives `shape-color` as each color of the input. On one input that is every color the input has. Fails Fit at train0.
- `head-end` & `key-order`, `head-end` & `cycle-phase`, `head-end` & `far-square`, `head-end` & `background`, `head-end` & `shape-color`, `key-order` & `cycle-phase`, `key-order` & `far-square`, `key-order` & `background`, `key-order` & `shape-color`, `cycle-phase` & `background`, `cycle-phase` & `shape-color`, `far-square` & `background`, `far-square` & `shape-color`, `background` & `shape-color`: the two branches' changes applied together
- `cycle-phase` & `far-square`: the two branches' changes applied together
    - `$CycleFromTail` & `$TailLastColor`: the model of `$CycleFromTail` alone. Under `$CycleFromTail`, the far square's own step already takes c(K−1).

## Open parameters
none

## Not formed
- Other values of `key-start` and `head-dir`: the pairs separate them. `key-start` DIR_R reads train1's key as 4 3 1. `head-dir` DIR_L puts train1's head at its bottom-left end, DIR_R puts train0's head at its bottom-right end, and DIR_B does both. Each of those puts c0 at a corner where the output does not have it.
- The square's side taken as the key length: train2's left trail is a sweep of a 4×4 square with K = 3.
- `shape-color` or `background` from `DominantColor` or `RarestColor` for the trail color: on every input `DominantColor` gives 0, and `RarestColor` ties among the key colors. Neither gives 5.
- A depth reading (a cell's color from its distance to the trail's edge): train0 row 8, cols 5–8, are all 1, while their distance from the left edge grows from 3 to 6.
- The key erased or changed: every output keeps the key cells as they are.

## Tickets filed
none
