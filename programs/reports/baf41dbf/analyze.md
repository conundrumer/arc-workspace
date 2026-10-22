# baf41dbf

## Concept
- Fits every pair (`check_concept.py`, `check_branches.py`). The concept reads the frame's new box as the old box with each side moved to one cell short of the farthest marker beyond that side. That is the same box as the bounding box of the frame and the markers, pulled in by one cell on each side where a marker gives the extreme.
- test0 is the one pair that separates readings of which side a marker pulls: the marker at (11,13) is beyond both the bottom and the right side of the input frame, and is in line with neither. It pulls the right side to col 12, and the marker at (12,6) pulls the bottom side to row 11.
- The concept's rules have a relational form, and no witness has verdict `other`.

## Choice points
- `marker-side`: which sides of the frame a marker pulls
    - `concept`: each side that the marker lies beyond, by its row or its column against the current box, whether or not it is in line with the frame
    - `$InLineMarkers`: replaces `side-moves-to-marker`. A marker pulls only the side it faces while it lies in line with the frame's span on the other axis, and the moves repeat until no side moves, so a side's move can bring a marker in line. No parameter is added, and it is defined on every input. Fits every pair. Witness `diagonal-marker`: test0's input without the marker at (12,6), so the marker at (11,13) is beyond the bottom and the right side and no move brings it in line. The concept moves both sides to it, and this branch leaves both sides. No scene claim breaks. Plausibility `borderline`, verdict `concept`. Invariant broken: each marker in the evidence ends orthogonally next to a side of the stretched frame.
    - `$InLineOnce`: replaces `side-moves-to-marker`. A marker pulls the side it faces only when it is in line with the input frame's span on the other axis, in one round. No parameter is added. Fails test0: the marker at (11,13) is never in line, and the right side stays at col 7.
- `marker-of-several`: which of the markers beyond one side sets that side
    - `concept`: the farthest
    - `$NearestMarker`: replaces `side-moves-to-marker`: the nearest marker beyond a side sets it. No parameter is added. Fails test0: the markers (11,13) and (12,6) are both beyond the bottom side, and the nearest puts the bottom side at row 10.
- `enclosed-marker`: what becomes of a marker that ends inside or on the new box
    - `concept`: it stays (`markers-stay`)
    - `$EnclosedMarkersCleared`: replaces `markers-stay`: a marker inside or on the new box becomes `background`, or `frame_color` where the outline or a divider runs. No parameter is added. Fits every pair, since no marker in the evidence ends inside the new box. Witness `two-markers-one-side`: train1's input with a further marker at (6,4), beyond the bottom side and in line with it. The concept moves the bottom side to row 8 and keeps the marker at (6,4) inside the frame, and this branch clears that marker. No scene claim breaks. Plausibility `borderline`, verdict `concept`. Invariant broken: each side has at most one marker beyond it, and no marker ends inside the stretched frame.
- `divider-place`: where a divider stands in the new box
    - `concept`: it keeps its row or column (`dividers-stretch`)
    - `$DividerKeepsNearSideDistance`: replaces `dividers-stretch`: a divider keeps its distance from the nearer side of the input frame. No parameter is added. Fails train2: the column divider at col 7 lies nearer the right side, which moves from col 9 to col 11, and so it moves to col 9.
- `divider-length`: how far a divider runs
    - `concept`: across the whole new box (`dividers-stretch`)
    - `$DividersKeepLength`: replaces `dividers-stretch`: a divider keeps the extent it has in the input frame. No parameter is added. Fails train2: the row divider at row 5 stops at col 4 and col 9, and the output runs it from col 2 to col 11.
- `old-outline`: what becomes of the input outline's cells off the new outline and the dividers
    - `concept`: they become `background` (`outline-redrawn`)
    - `$OldOutlineKept`: replaces `outline-redrawn`: those cells keep `frame_color`. No parameter is added. Fails train0: the input's right side at col 6 stays in the output.
- `background`: where the background color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input. Undefined on no input in the evidence. Fits every pair. Witness `background=DominantColor`: a 6×7 grid whose 5×5 frame, with two dividers on each axis, has 21 cells against 20 background cells, and one marker at (2,6). The derived background is 3, so the old right side at col 4 stays `frame_color`. No scene claim breaks. Plausibility `borderline`, verdict `concept`. Invariant broken: the background is the commonest color of every input.
    - `background=RarestColor`: the rarest color of the input. Fails train0: it gives 6.
    - `background=SharedColor`: each color of the input. Fails train0: it gives three outputs.
- `marker_color`: where the marker color comes from
    - `concept`: stored, 6
    - `marker_color=RarestColor`: the rarest color of the input, ties included. Undefined on no input in the evidence. Fits every pair. Witness `marker_color=RarestColor`: a 9×9 grid with a 2×2 frame and one marker beyond each side, so 3 and 6 tie at four cells. The derived model gives two grids: the concept's, and the input unchanged from marker color 3. The frame has no inside, and no scene claim breaks. Plausibility `borderline`, verdict `concept`. Invariant broken: each frame has an inside, and its cells outnumber the markers.
    - `marker_color=DominantColor`: the commonest color. Fails train0: it gives 0.
    - `marker_color=SharedColor`: each color of the input. Fails train0: it gives three outputs.
- `frame_color`: where the frame color comes from
    - `concept`: stored, 3
    - `frame_color=DominantColor`: fails train0: it gives 0.
    - `frame_color=RarestColor`: fails train0: it gives 6.
    - `frame_color=SharedColor`: fails train0: it gives three outputs.
- `marker-side` & `marker-of-several`, `marker-side` & `enclosed-marker`, `marker-side` & `background`, `marker-side` & `marker_color`, `marker-of-several` & `enclosed-marker`, `marker-of-several` & `background`, `marker-of-several` & `marker_color`, `enclosed-marker` & `background`, `enclosed-marker` & `marker_color`, `background` & `marker_color`, and each pair of points that holds `divider-place`, `divider-length`, `old-outline` or `frame_color`: the two branches' changes applied together
    - Of these combined cases, only those that leave out `$InLineOnce` and every branch that fails Fit alone fit, and `$InLineMarkers & $NearestMarker` is the one that fits while its non-concept branch `$NearestMarker` fails alone. It fits every pair, because no side has two in-line markers beyond it. In witness `two-markers-one-side` it moves the bottom side to row 5, short of the nearer marker, and so differs from `$InLineMarkers` and from the concept.

## Open parameters
- none

## Not formed
- Content inside the frame other than dividers: no input has any, the scene claim `frame` excludes it, and no source gives a reading of where such content goes as the box grows.
- The frame moves in place of stretching: fails train0, where the left side stays at col 1 and the right side moves from col 6 to col 10.
- A derivation of `marker_gap`: no proposer derives a distance between a marker and a side.
- The proposers that read `ex_out` (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`) as a derivation of a color parameter: with `ex_out` empty they give no value on an input, so every case that takes one is undefined on every pair.

## Tickets filed
- none
