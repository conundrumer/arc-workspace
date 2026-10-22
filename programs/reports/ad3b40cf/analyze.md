# ad3b40cf

## Concept
- Fits every pair. Every rule has a relational form: the copied color is the shape color whose cell count is least, and its image is its reflection across the drawn line. No witness has verdict `other`.

## Choice points
- `copied-color`: what picks the color that is mirrored
    - `concept`: the shape color with the fewest cells, derived on each input
    - `$ObjectBoxArea`: replaces the count in `mirror-rarer` with the sum of the box areas of the color's 4-connected objects; undefined where two colors tie for the least sum; fits every pair; witness `object-box-order`, at the stored assignment, `ordinary`, verdict `concept`
        - `adjacency`: which cells join into one object
            - `concept`: 4-adjacency
            - `$Adjacency8`: objects also join at a corner; fits every pair; witness `corner-touch`, at the stored assignment, `ordinary`, verdict `concept`
    - `$ColorBoxArea`: replaces the count in `mirror-rarer` with the area of the box of all the color's cells; undefined where two colors tie for the least area; fits every pair; witness `scattered-color`, at the stored assignment, `ordinary`, verdict `concept`
    - `$FewerObjects`: replaces the count in `mirror-rarer` with the count of the color's 4-connected objects; undefined where two colors tie for the least; fails Fit at train0, where each color is one object
    - `$SmallerLargestObject`: replaces the count in `mirror-rarer` with the cell count of the color's largest object; undefined where two colors tie for the least; fails Fit at test0, where it mirrors 4 (largest object 6 cells) in place of 7 (largest object 7 cells)
    - `$StoredColor`: stores the mirrored color in place of the derivation in `mirror-rarer`; fails Fit at train1, which mirrors 6 where train0 mirrors 5
- `competitors`: which colors the count ranges over
    - `concept`: the shape colors, every color other than `background` and `line`
    - `$LineCompetes`: replaces the range in `mirror-rarer` with every color other than `background`, the line included; where the line is the rarest, its image is the line itself and the output is the input; fits every pair; witness `line-rarest`, at the stored assignment, `ordinary`, verdict `concept`
- `ties`: what a tie for the least does
    - `concept`: undefined where two colors tie for the least
    - `$CopyAllLeast`: mirrors every color tied for the least; fits every pair; witness `tie`, breaks `two-colors`, at the stored assignment, `borderline`, verdict `any`; breaks the invariant that the two shape colors differ in cell count
- `mirror-place`: where the mirror stands
    - `concept`: the drawn line: a cell's image is its reflection across the line the `line` cells lie on
    - `$FrameFlip`: the grid's own flip whose fixed line has the drawn line's orientation, through the grid's center; replaces the reflection in `mirror-rarer`; fits every pair; witness `off-center-line`, breaks `mirror-line`, at the stored assignment, `variant`, verdict `concept`; breaks the invariant that the line runs through the grid's center
- `off-grid`: what an image cell outside the grid does
    - `concept`: it is dropped
    - `$OffGridUndefined`: the model is undefined on such an input; adds to `mirror-rarer`; fits every pair; subsumed by the concept case, so it fails Subsumption; witness `image-off-grid`, on which it is undefined, breaks `mirror-line`, at the stored assignment, `borderline`, verdict `concept`; breaks the invariant that the line runs through the grid's center, so every image lands in the grid
- `image-on-ink`: what an image does to a cell that holds the other shape color
    - `concept`: the image paints over it
    - `$PaintBackgroundOnly`: the image paints only `background` cells; replaces the painting in `mirror-rarer`; fits every pair; witness `ink-both-sides`, breaks `one-side`, at the stored assignment, `borderline`, verdict `any`; breaks the invariant that the far side of the line is all `background`
- `background`: the background color
    - `concept`: stored, 8
    - `background=DominantColor`: derived on each input as its most common color; undefined where two colors tie for most common; replaces the stored value read by `one-side`, `two-colors` and `mirror-rarer`; fits every pair; witness `background=DominantColor`, breaks `one-side`, at the stored assignment, `variant`, verdict `background=DominantColor`; breaks the invariant that the background is 8
- `line-color`: the color of the mirror line
    - `concept`: stored, 1
    - `$LineByShape`: derived on each input as the one non-background color whose cells form a straight line from edge to edge; undefined where no color or several colors do; replaces the stored value read by `mirror-line` and `mirror-rarer`; fits every pair; witness `line-recolored`, breaks `mirror-line`, at the stored assignment, `variant`, verdict `$LineByShape`; breaks the invariant that the line is 1
- `mirror-orientation`: the orientation of the mirror line
    - `concept`: derived on each input from the row, column or diagonal the `line` cells share
    - `$StoredAxis`: stores the orientation; fails Fit at train1, whose line is an anti-diagonal where train0's is a column
- `copied-color` & `mirror-place`, `copied-color` & `off-grid`, `copied-color` & `image-on-ink`, `copied-color` & `line-color`, `copied-color` & `mirror-orientation`, `competitors` & `ties`, `competitors` & `mirror-place`, `competitors` & `off-grid`, `competitors` & `image-on-ink`, `competitors` & `background`, `competitors` & `line-color`, `competitors` & `mirror-orientation`, `ties` & `mirror-place`, `ties` & `off-grid`, `ties` & `image-on-ink`, `ties` & `background`, `ties` & `line-color`, `ties` & `mirror-orientation`, `mirror-place` & `off-grid`, `mirror-place` & `image-on-ink`, `mirror-place` & `background`, `mirror-place` & `line-color`, `mirror-place` & `mirror-orientation`, `off-grid` & `image-on-ink`, `off-grid` & `background`, `off-grid` & `line-color`, `off-grid` & `mirror-orientation`, `image-on-ink` & `background`, `image-on-ink` & `line-color`, `image-on-ink` & `mirror-orientation`, `background` & `line-color`, `background` & `mirror-orientation`, `line-color` & `mirror-orientation`, `adjacency` & `competitors`, `adjacency` & `ties`, `adjacency` & `mirror-place`, `adjacency` & `off-grid`, `adjacency` & `image-on-ink`, `adjacency` & `background`, `adjacency` & `line-color`, `adjacency` & `mirror-orientation`: the two branches' changes applied together
- `copied-color` & `competitors`: the measure of the `copied-color` branch, taken over the colors `$LineCompetes` admits
    - `$StoredColor` & `$LineCompetes`: `$StoredColor` alone, which ranges over no colors
- `copied-color` & `ties`: the measure of the `copied-color` branch, with every color tied for its least mirrored
    - `$StoredColor` & `$CopyAllLeast`: `$StoredColor` alone, which has no ties
- `copied-color` & `background`: the measure of the `copied-color` branch, over the shape colors the derived background leaves
    - `$StoredColor` & `background=DominantColor`: `$StoredColor` alone, which reads the background nowhere

## Open parameters
none

## Not formed
- The background counted among the competing colors: the far half of the line is all background, so on every input the scene allows, the background outnumbers the rarer shape color, and no reader of the concept counts the background as a shape.
- A per-object choice of what is mirrored, by shape or by distance to the line: in every pair all objects of one color are mirrored and none of the other, and no shape or distance property separates the two sets (train1 keeps a 3x2 rectangle of 7 and mirrors a 2x2 square of 6; train0's two colors are at the same distance from the line).
- The originals moved in place of copied: every output keeps the originals.

## Tickets filed
none
