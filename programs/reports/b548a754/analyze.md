# b548a754

## Concept
- Fits every pair at the stored assignment (`marker_color` 8, `background` 0). The concept model is undefined where an input breaks one of its scene claims: no cell or more than one cell of `marker_color`, a marker in neither the rows nor the columns of the box, a box that is not a 1-wide frame around a one-color inside, or a field that is not `background`. Each such input the probes found has a branch's verdict, and no witness has the verdict `other`.

## Choice points
- `marker-identity`
    - `concept`: the marker is the cell of the stored `marker_color`.
    - `marker_color=RarestColor`: replaces the stored `marker_color` (read by `marker`) with the one color that has the fewest cells in the input; undefined where that fewest count ties between colors. Fits every pair. Witness `marker_color=RarestColor`: breaks `marker` (the dot is 5); stored assignment; plausibility `variant`; verdict `marker_color=RarestColor`; breaks the invariant that every input's dot is 8.
    - `$LoneMarker`: replaces the color in `marker` and drops the parameter `marker_color`: the marker is the non-background cell with no non-background 4-neighbor; undefined where the dot touches the box, and where there is no such cell or more than one. Fits every pair. Witness `lone-marker`: breaks `marker` (the dot is 5); stored assignment; plausibility `variant`; verdict `$LoneMarker`; breaks the invariant that every input's dot is 8. On that input `marker_color=RarestColor` is undefined, since the box's one-cell interior ties the dot.
- `background`
    - `concept`: the stored `background`.
    - `background=DominantColor`: replaces the stored `background` (read by `framed-box` and `background`) with the one color that has the most cells in the input; undefined where that count ties, and gives the border color where the box outnumbers the field. Fits every pair. Witness `background=DominantColor`: breaks `background` (the field is 5); stored assignment; plausibility `variant`; verdict `background=DominantColor`; breaks the invariant that every input's field is 0.
- `marker-count`
    - `concept`: one marker cell.
    - `$EachMarker`: replaces "one cell" in `marker` with one or more cells, each straight out from a side of the box, and `stretch-to-marker` moves each side that faces a marker out to the line of the farthest marker on that side; undefined where a marker lies in neither the rows nor the columns of the box. Fits every pair. Witness `two-markers`: breaks `marker` (two dots); stored assignment; plausibility `borderline`; verdict `$EachMarker`; breaks the invariant that every input holds one dot. A case that takes it and the concept branch at `marker-placement` fails Subsumption: the case that also takes `$CoverDiagonal` gives its output wherever it is defined, and is defined on `diagonal-marker`, where it is not.
- `marker-placement`
    - `concept`: the marker lies in the rows or the columns of the box, and one side moves.
    - `$CoverDiagonal`: drops "within the box's span on one axis" from `marker`, and `stretch-to-marker` stretches the box on both axes to the bounding box of the box and the marker; no input beyond the concept's other conditions is undefined. Fits every pair. Witness `diagonal-marker`: breaks `marker` (the dot is diagonal from the box); stored assignment; plausibility `foreign`; verdict `$CoverDiagonal`; breaks the invariant that the dot lies straight out from one side. A case that takes it and the concept branch at `marker-count` fails Subsumption: the case that also takes `$EachMarker` gives its output wherever it is defined, and is defined on `two-markers`, where it is not.
- `extension-content`
    - `concept`: the stretched box is redrawn as a 1-wide border with the interior color inside.
    - `$RepeatInnerSlice`: drops "a 1-wide border of one color around an interior of another color" from `framed-box`, and `stretch-to-marker` translates the box's far line to the marker's line, each line between taking a copy of the box's line next to the old far side; undefined where the box is narrower than 3 along the stretch. Fits every pair. Witness `striped-interior`: breaks `framed-box` (the interior holds a stripe of 4); stored assignment; plausibility `borderline`; verdict `$RepeatInnerSlice`; breaks the invariant that the inside of the box is one color.
- `marker-identity` & `background`, `marker-identity` & `marker-count`, `marker-identity` & `marker-placement`, `marker-identity` & `extension-content`, `background` & `marker-count`, `background` & `marker-placement`, `background` & `extension-content`, `marker-count` & `marker-placement`, `marker-count` & `extension-content`, `marker-placement` & `extension-content`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `marker_color` or `background` from another color proposer: on one input with `ex_out` empty, `DominantColor` gives the field as the marker and `RarestColor` gives the dot as the field; `SharedColor` gives every color of the input; `OutNewColor`, `VanishedColor`, `ChangedColor` and `UnchangedColor` read `ex_out` and give none. Each fails Fit.
- The marker cell keeps its color, or the far side stops one line short of it: train0 output (8,3) is 2, the border color.
- The box moves to the marker in place of stretching: train0 output keeps the box's top side at row 1.
- The far side stays and the near side moves, or both sides move: every train output keeps the side opposite the marker in place.
- The marker's color fills the extension: no train output holds the marker color.
- The box found as the non-background object that holds more than one cell, in place of every cell outside `background` and `marker_color`: the two readings part only on inputs that hold content beside the box and the marker, and no claim of the concept or of a branch has such content.

## Tickets filed
- none
