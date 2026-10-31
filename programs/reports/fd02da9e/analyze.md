# fd02da9e

## Concept
- Fits every pair (train0–3, test0). Each corner shows up as a marker in train (BL train0, TR train1, BR train2, TL train3), so the pairs fix the whole `corner_stamp` table.
- Three witnesses with verdicts against the concept each break a scene claim, and each has a branch that gives the verdict output. None has verdict `other`:
    - `grid-10x10` (`variant`, breaks `background-field` at `grid_size` 8×8): the generator keeps the face whole and centred (`$CenterPlacement`). The concept anchors each part at its own corner, which splits the smile.
    - `background=DominantColor` (`variant`, breaks `background-field` at `background` 7): the concept reads all four corners of a field of 3 as markers.
    - `stray-cell` (`borderline`, breaks `corner-markers`): the generator keeps a cell that is not a marker. The concept repaints the whole field.
- Restated as the generator applies it, the rule is: draw one fixed 8×8 smiley-face picture in the grid, and give each of its four parts (two eyes, two halves of the smile) the colour of its corner's marker. The concept's corner-relative `face-part` gives this picture exactly on the 8×8 grids of the evidence.

## Choice points
- `placement`: where a stamp cell lands
    - `concept`: at the cell's distances from its own corner's two edges
    - `$CenterPlacement`: replaces `face-part`. The face cells keep their 8×8 offsets from the grid centre. Parameters: `corner_stamp`, `background`. Undefined where H−8 or W−8 is odd, or where a cell falls outside the frame. Fits every pair. Witness `grid-10x10`, which breaks `background-field` (`grid_size` 8×8) at the stored assignment: `variant`, verdict `$CenterPlacement`. Invariant broken: every input is 8×8.
    - `$AnchorPlacement`: replaces `face-part`. The face cells keep their 8×8 coordinates from a stored anchor corner. Parameters: `corner_stamp`, `background`, `anchor_corner` (TL). Undefined where a cell falls outside the frame. Fits every pair. Witness `grid-10x10`, as above: `variant`, verdict `$CenterPlacement`. Invariant broken: every input is 8×8.
- `stamp-source`: what gives the cells a marker paints
    - `concept`: a stored table keyed by corner (`corner_stamp`)
    - `$QuadrantPartition`: replaces `face-part`. A stored face picture `face`, each cell painted by the marker of the corner whose quadrant holds it. Parameters: `face`, `background`. Undefined nowhere. Fits every pair. Witness `nose-cell` at an assignment with `face` reassigned to add (3,3): `variant`, verdict `$QuadrantPartition`. Invariant broken: none of the inputs, since the assignment is not stored.
    - `$StampByColor`: replaces `face-part`. A stored table keyed by marker colour, placed from the marker's corner. Parameters: `color_stamp`, `background`. Undefined on a colour the table lacks. Fails Fit at test0, where colours 2, 5 and 4 are unseen keys and 8 is stored as an eye but marks BL.
- `right-stamps`: whether the right corners' stamps are their own values
    - `concept`: stored per corner
    - `$MirroredHalves`: replaces `face-part`. Derives the TR and BR stamps as the left-right mirrors of TL and BL. Parameters: `corner_stamp` (left corners read), `background`. Undefined nowhere. Fits every pair. Witness `winking-eye` at an assignment with `corner_stamp` TL reassigned to (1,1), (1,2): `variant`, verdict `concept`. Invariant broken: none of the inputs, since the assignment is not stored.
- `background`: the field colour
    - `concept`: stored, 7
    - `background=DominantColor`: replaces `background-field`'s stored colour with the commonest colour of the input. Undefined on a tie. Fits every pair. Witness `background=DominantColor`, which breaks `background-field` (`background` 7) at the stored assignment: `variant`, verdict `background=DominantColor`. Invariant broken: every field is 7.
    - `background=SharedColor`: a single input gives every colour it holds, so a train input gives two grids. Fails Fit at train0.
    - `background=RarestColor`: gives the marker colour 1 as the field. Fails Fit at train0.
- `other-cells`: what a cell that is neither a marker nor a stamp cell becomes
    - `concept`: `background` (`rest-background`)
    - `$KeepStrayCells`: replaces `rest-background`. Every such cell keeps its input colour. Parameters: `corner_stamp`, `background`. Undefined nowhere. Fits every pair. Witness `stray-cell`, which breaks `corner-markers` at the stored assignment: `borderline`, verdict `$KeepStrayCells`. Invariant broken: no cell off the corners differs from 7.
- `marker-cells`: what a marker cell becomes
    - `concept`: `background` (`markers-cleared`)
    - `$KeepMarkers`: replaces `markers-cleared`. The marker keeps its colour. Fails Fit at train0, whose output (7,0) is 7.
- `placement` & `right-stamps`, `placement` & `background`, `placement` & `other-cells`, `placement` & `marker-cells`, `placement` & `stamp-source`, `right-stamps` & `background`, `right-stamps` & `other-cells`, `right-stamps` & `marker-cells`, `stamp-source` & `background`, `stamp-source` & `other-cells`, `stamp-source` & `marker-cells`, `background` & `other-cells`, `background` & `marker-cells`, `other-cells` & `marker-cells`: the two branches' changes applied together
- `stamp-source` & `right-stamps`: with `$QuadrantPartition`, the two changes apply together: the right half of `face` is the mirror of its left half.
    - `$StampByColor` & `$MirroredHalves`: the model of `$StampByColor` alone. A colour-keyed table has no right-corner entries, so the `right-stamps` property does not exist with `$StampByColor`. The point stays at the concept, because the concept branch of `stamp-source` has the property. `$StampByColor` fails Fit, so no case takes both.

## Open parameters
- none

## Not formed
- Bottom stamps derived as the top stamps reflected top to bottom: the pairs pair a 2×2 eye with a three-cell stroke, so no reflection carries one to the other, and nobody reading the task takes it that way.
- Any non-background cell acting as the marker of its nearest corner: no input has a mark off the corners. On inputs that keep the scene it is the concept. The input it would separate, a mark off the corners, is the input `$KeepStrayCells` already separates.
- `background` from UnchangedColor, ChangedColor, VanishedColor and the other output-reading proposers: under `@derive` they read one input and no output, so they propose nothing that names a field colour.

## Tickets filed
- none
