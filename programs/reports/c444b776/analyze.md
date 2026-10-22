# c444b776

## Concept
- Fits every pair: the probe `probe.py` reproduces train0, train1 and test0 with `divider` 4 and `background` 0.
- No witness has the verdict `other`. The rule as the generator applies it is the concept file's `copy-to-every-panel`: the drawn panel's cells, translated by each panel's offset, fill every panel, and the divider lines stay. That rule has a relational form.
- Every input has 9×9 panels and one 1-wide divider line between neighbouring panels. Only `lattice=stored` reads this.

## Choice points
- `background`: how the background color is found
    - `concept`: stored `background` 0
    - `background=DominantColor`: the background is the commonest color of the input (replaces the stored value in `one-drawn-panel`). It is undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: the train1 layout with background 1. It breaks `one-drawn-panel` at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the background is 0 in every input.
    - `background=SharedColor`: the background is each color the input holds. Every cell is then background, so no panel is drawn. Fails Fit at train0.
- `panels`: how the panels are found
    - `concept`: full rows and columns of the stored `divider` color cut the grid
    - `$DividerFromLines`: the divider is the one non-background color that fills a whole row or column (replaces the stored `divider` in `divider-lines`). It is undefined where no such color exists, or where several do. Fits every pair. Witness `divider-color`: the train1 layout with the divider row in 6. It breaks `divider-lines` at the stored assignment, because no line of 4 cuts the grid, so the concept reads one panel and returns the input. Plausibility `variant`, verdict `$DividerFromLines`. It breaks the invariant that the divider lines are 4 in every input.
    - `lattice=stored`: a stored panel size (9 on each axis) and a stored gap (1) cut the grid, and the divider color is not read (replaces how `divider-lines` finds the panels). It is undefined where an axis's extent is not n·9 + (n−1). Fits every pair. Witness `lattice=stored`: a 9×9 grid that 4-lines cut into four 4×4 panels, with the top-left panel drawn. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that every panel is 9×9.
- `source`: what content each panel takes
    - `concept`: the one panel that holds non-background cells. The concept is undefined where no panel or several panels hold such cells.
    - `$Overlay`: the overlay of all panels, where a non-background cell of any panel shows (replaces `one-drawn-panel` in the rule). It is undefined where two panels hold different non-background colors at one cell. Fits every pair. Witness `two-drawn-panels`: train0's input plus a 6 at (2,6) in the top-left panel. It breaks `one-drawn-panel`. Plausibility `borderline`, verdict `$Overlay`. It breaks the invariant that exactly one panel is drawn in every input.
    - `$MostDrawn`: the panel with the most non-background cells (replaces `one-drawn-panel` in the rule). It is undefined on a tie. Fits every pair. Witness `two-drawn-panels`, as for `$Overlay`. There, `$MostDrawn` copies the bottom-left drawing alone.
- `placement`: how the copy lands in a panel
    - `concept`: translated by the panel's offset
    - `$ReflectCopy`: reflected across the dividers between the source panel and the target panel. Fails Fit at train1: input row 1 of the top panel must land on output row 11, but reflection puts it on row 17.
- `targets`: which panels take the copy
    - `concept`: every panel
    - `$SameBandCopy`: only the panels that share a row band or a column band with the drawn panel. Fails Fit at train0: the output's top-right panel (rows 0–8, cols 10–18) holds the copy.
- `background` & `panels`, `background` & `source`, `background` & `placement`, `background` & `targets`, `panels` & `source`, `panels` & `placement`, `panels` & `targets`, `source` & `placement`, `source` & `targets`, `placement` & `targets`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A period of 10 tiled out from the drawn panel, with no stored grid extent: this is `lattice=stored` read with a partial panel at the grid edge. The two differ only on grids whose extent is not a whole number of panels plus gaps, where `lattice=stored` is undefined.
- A copy into panels of a different size, cropped or anchored at a corner: the concept and every branch are undefined where the panels differ in size. A defined reading needs an anchor corner, and no pair or claim points to one.
- `drawing-avoids-divider` replaced: no branch reads it except `$DividerFromLines`. Under that branch, a drawing in the divider color that does not fill a whole line changes nothing.

## Tickets filed
none
