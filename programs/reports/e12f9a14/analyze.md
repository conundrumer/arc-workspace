# e12f9a14

## Concept
- The concept fits every pair, train and test (`probe.py fit`). It has no witness with verdict `other`.
- The generator applies the meeting rule at every meeting, bent rays included. That is the `$ChainedMeetings` reading, and it is the verdict of `bent-ray-crossed`. The concept's `meeting` rule bends a ray at its first meeting only. The two rules agree on every scene that keeps `single-meetings`. The level-B patch of train 1 removed the one meeting of a ray with a pair of bent rays that the task had.
- The probe takes a crossing to count only when the two rays are each other's first crossing. In test 0, the straight ray down col 5 would cross the unbent line of the ray from the corner at (13,10), and that ray bends first at its meeting with the ray from (13,7). The expected output runs col 5 straight to the edge.

## Choice points
- `meeting`: what happens where the paths of two rays cross
    - `concept`: both rays stop just short of the crossing and run on in the sum of their directions
        - `meeting-test`: when two rays meet
            - `concept`: their straight paths cross, whatever cell each ray reaches first
            - `$Timed`: replaces `meeting`; the rays advance one cell per step from their gaps at once, and two rays meet only when they reach the crossing at the same step. It fails Fit at train 2: the ray up col 13 from (10,13) passes (6,13) at step 4, while the ray along row 6 from (6,6) is at (6,10), so (6,13) takes 4, where the output keeps it background.
        - `slope-two-steps`: how the sum of a cardinal and a diagonal direction is drawn
            - `concept`: a cardinal step, then a diagonal step, in turn
            - `$DiagonalFirst`: replaces the drawing in `meeting`; the diagonal step comes first. It fails Fit at train 0: the ray from (9,14) goes to (5,18), and the ray up col 18 goes to (5,19), where the output has 1 at (5,17) and 4 at (5,18).
        - `bent-meetings`: whether a ray that has bent meets further rays
            - `concept`: no; a bent ray runs on to the edge
            - `$ChainedMeetings`: replaces `meeting`; the meeting rule applies again, round by round, to each two rays whose paths as they stand cross first with each other, bent paths included. It is undefined where two rays paint different colors on one cell. It fits every pair. Witness `bent-ray-crossed`: it breaks `single-meetings`, at the stored assignment, `variant`, verdict `$ChainedMeetings`. It breaks the invariant of the inputs that no ray meets a second ray, which the upstream train 1 broke before the level-B patch.
    - `$PassThrough`: replaces `meeting`; the rays ignore each other and run straight to the edge. It is undefined where two rays of different colors paint one cell. It fails Fit at train 0: the rays from (9,14) and up col 18 both paint (5,18).
- `ray-block`: what a ray does at a box in its path
    - `concept`: it paints over the box, on to the grid edge
    - `$StopAtBox`: replaces `rays`; a ray stops at its last cell before a non-background cell of another box. It fits every pair. Witness `ray-hits-box`: it breaks `clear-paths`, at the stored assignment, `variant`, verdict `$StopAtBox`. It breaks the invariant of the inputs that no ray's path enters another box.
    - `$PassUnderBox`: replaces `rays`; a ray paints only the background cells of its path and runs on past a box to the grid edge. It fits every pair. Witness `ray-hits-box`: it breaks `clear-paths`, at the stored assignment, `variant`, verdict `$StopAtBox`. It breaks the invariant of the inputs that no ray's path enters another box.
- `core-size`: the side of a box's core
    - `concept`: the stored `core-side`, 2
    - `$CoreSizePerBox`: replaces `boxes`; each box's core is a square of one color, of any side, whose ring cells are wall or background, and its gaps and rays are read from that ring. It reads no `core-side`. It fits every pair. Witness `three-core`: it breaks `boxes`, at the stored assignment, `variant`, verdict `$CoreSizePerBox`. It breaks the invariant of the inputs that every core is 2 × 2.
- `scene-colors`: where the background and wall colors come from
    - `concept`: each input's own background and wall colors
    - `$StoredColors`: replaces `background` and `boxes`; the background (8) and the wall color (3) are stored. It fails Fit at test 0, whose background is 0 and whose wall is 8.
- `corner-gaps`: what a gap at a ring corner does
    - `concept`: it casts a diagonal ray
    - `$NoCornerRays`: replaces `rays`; a corner gap casts nothing. It fails Fit at train 0, whose output paints the diagonals from (9,3), (9,6), (12,3) and (12,6).
- `meeting` & `ray-block`, `meeting` & `core-size`, `meeting` & `scene-colors`, `meeting` & `corner-gaps`, `ray-block` & `core-size`, `ray-block` & `scene-colors`, `ray-block` & `corner-gaps`, `core-size` & `scene-colors`, `core-size` & `corner-gaps`, `scene-colors` & `corner-gaps`, `meeting-test` & `slope-two-steps`, `meeting-test` & `bent-meetings`, `slope-two-steps` & `bent-meetings`, and each of `meeting-test`, `slope-two-steps` and `bent-meetings` with each of `ray-block`, `core-size`, `scene-colors` and `corner-gaps`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A head-on meeting of two rays on one line: the sum of opposite directions is zero, so no direction to continue in follows from it. Each ray's path also runs into the other ray's box. Every reading formed is undefined there.
- A ring cell of a third color, neither wall nor background: no pair shows one, and no reading of the pairs says whether such a cell is wall or gap.
- A ray that starts one cell past its gap: every pair paints each gap cell in its box's core color.
- The wall color as some color other than the color every box's ring shares: the probe finds that color as the commonest color that is not the background. No reading of the pairs names another color for the wall.

## Tickets filed
- none
