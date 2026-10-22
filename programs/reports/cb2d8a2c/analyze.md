# cb2d8a2c

## Concept
- Fits every train and test pair (`check_concept.py`). Each wall's clearance is the count of its marks, and the path turns that many free cells before the wall and passes that many free cells beyond the wall's free end. All mark counts 1–4 occur, and both clearances agree on every wall.
- The concept rule is applied as written: at each wall ahead, the path moves to the lane `clearance` cells beyond the wall's free end. Where a wall does not cross the path's line, that move can take the path toward the wall (`short-wall-far`).
- No witness has the verdict `other`.

## Choice points
- `clear-wall`: the path at a wall that does not cross the path's line (breaks `walls-in-order`)
    - `concept`: the path moves to the lane `clearance` cells beyond the wall's free end, at every wall ahead of it
    - `$KeepClearance`: replaces `path`. The path detours only when its line crosses the wall or passes the free end with fewer than `clearance` free cells between them. Otherwise it runs straight on. No new parameters. Defined where the concept is defined. Fits every pair. Witness `short-wall-far` breaks `walls-in-order` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that every wall crosses the path's line. Verdict `$KeepClearance`: a person runs the path straight past a wall that is not in its way.
    - `$PassClearWall`: replaces `path`. The path detours only at a wall that crosses its line. At any other wall it runs straight on, even where that leaves fewer than `clearance` free cells to the free end. No new parameters. Defined where the concept is defined. Fits every pair. Witness `short-wall-near` breaks `walls-in-order` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that every wall crosses the path's line. Verdict `concept`: the marks set a gap that the path keeps from the wall.
- `clearance`: how a wall's clearance comes from its marks
    - `concept`: the count of `mark_color` cells on the wall
    - `$MarkedRunClearance`: replaces `clearance`. The clearance is half the length of the run from the wall's edge cell to its farthest mark, rounded up. No new parameters. Defined where the concept is defined. Fits every pair. Witness `adjacent-marks` breaks `wall-marks` and stands at the stored assignment. Plausibility `foreign`. It breaks the invariant that marks fall on every second cell from the edge. Verdict `concept`.
    - `clearance_of=stored`: replaces `clearance`. A stored table `clearance_of(count, gap)` maps a wall's mark count to its clearance, with the value {1→1, 2→2, 3→3, 4→4}. The model is undefined on a wall whose mark count is not a key. Fits every pair, since every test count (1–4) occurs in train. Witness `clearance_of=stored` is the train0 input, standing at `clearance_of` reassigned to 4→5, where the model is defined and differs. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
- `path_color`: the source color, stored (concept) or derived per input
    - `concept`: stored, 3
    - `path_color=RarestColor`: replaces `source` with the source color taken as each least-frequent color of the input. It gives 3 on every pair. The model is undefined where the mark color ties it, since it then finds two sources. Fits every pair. Witness `path_color=RarestColor` is one wall with one mark, at the stored assignment. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`. Without breaking `source`, no input exists where the derivation gives a single color other than the source's.
    - `path_color=DominantColor`: the derived value is 8. Fails Fit at train0.
    - `path_color=SharedColor`: the derived value is every color of the input. Fails Fit at train0.
- `wall_color`: stored (concept, 2), or derived per input
    - `wall_color=DominantColor` (8), `wall_color=RarestColor` (3), `wall_color=SharedColor` (all colors): each fails Fit at train0.
- `mark_color`: stored (concept, 1), or derived per input
    - `mark_color=DominantColor` (8), `mark_color=RarestColor` (3), `mark_color=SharedColor` (all colors): each fails Fit at train0. The proposers that read the outputs give no value when `ex_out` is empty, so their branches are undefined on every input and fail Fit at train0.
- `clear-wall` & `clearance`, `clear-wall` & `path_color`, `clearance` & `path_color`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Separate clearances before the wall and beyond its free end: on every wall in the pairs, both equal the mark count, and the marks give one number.
- The path returns to its original line after it passes a wall: train0 refutes it, since the path stays on col 1 after the wall.
- The side of the detour: a wall touches one edge, so its free end is the only open side.
- Clearance from the wall's length: train1 wall1 (length 7, gap 1) and train0 (length 7, gap 4) refute it.
- Walls identified by structure in place of the stored `wall_color` and `mark_color`: under every scene claim, it gives the same cells as the stored colors. A person reads the colors.
- `background`: the program does not read it. The walls and the source are found by their own colors, so it is a scene parameter.

## Tickets filed
none
