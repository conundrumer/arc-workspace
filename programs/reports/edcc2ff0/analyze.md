# edcc2ff0

## Concept
- Fits every pair, test0 included (probe `work/task/edcc2ff0/probe.py`). Under 4-adjacency, the commonest field color as background, and `panel_color` 0 with `bar_dir` DIR_R, the per-color object counts are: train0 2:4, 8:2, 4:1 (unlisted 1 wiped); train1 4:0 (marker erased), 2:2, 3:3 (unlisted 8 wiped); train2 1:2, 2:2, 4:4 (unlisted 6 and 3 wiped); test0 2:5, 8:0, 3:2 (unlisted 7 and 5 wiped).
- No witness has the verdict `other`. Every rule has a relational form (a count of components, a bar of that length), so the concept file's rules approximate nothing.
- In every input, any two field objects stand at Chebyshev distance 2 or more, so adjacency and object grouping never matter on the pairs.

## Choice points
- `object-adjacency`
    - `concept`: an object is a 4-connected component of one color
    - `$Objects8`: replaces `field-objects` and `tally-bars` so that an object is an 8-connected component of one color. No new parameters, defined on every input. Fits every pair. Witness `corner-touching-objects`: breaks `field-objects`, at the stored assignment, `borderline`, verdict `concept`. Invariant broken: field objects never come within one cell of each other, corners included.
- `object-grouping`
    - `concept`: an object holds one color, and objects of other colors that touch it do not join it
    - `$ObjectsAnyColor`: replaces `tally-bars` so that an object is a 4-connected component of non-background cells of any color, counted once under each color it holds. No new parameters, defined on every input. Fits every pair. Witness `chained-objects`: breaks `field-objects`, at the stored assignment, `borderline`, verdict `concept`. Invariant broken: field objects never touch.
- `count-measure`
    - `concept`: a marker's count is the number of field objects of its color
    - `$CountCells`: replaces `tally-bars` so that the count is the number of field cells of the color. Fails Fit at train0, where 2 has 11 cells and the bar is 4 long.
- `count-scope`
    - `concept`: only field objects are counted
    - `$CountIncludesMarker`: replaces `tally-bars` so that the legend marker itself also counts as an object of its color. Fails Fit at train0, where the 2 bar would be 5 long and the output's is 4.
- `empty-marker`
    - `concept`: a count of zero erases the marker to `panel_color`
    - `$KeepEmptyMarker`: replaces `tally-bars` so that a marker with count zero stays as one cell. Fails Fit at train1, where the 4 marker at (1,0) is erased.
- `unlisted-objects`
    - `concept`: field objects of an unlisted color become field background
    - `$KeepUnlisted`: drops `drop-unlisted`, so those objects stay. Fails Fit at train0, where the 1 block at rows 8–9, cols 1–2 is wiped.
- `bar-direction`
    - `concept`: `bar_dir` is stored (DIR_R)
    - `$BarDirFromEdge`: replaces `tally-bars` so that each bar runs away from the one grid edge its marker lies on. Derived per input, with `bar_dir` gone. Undefined where a marker lies on no edge or on a corner. Fits every pair. Witness `markers-on-right-edge`: breaks `legend-panel` (markers on the edge opposite `bar_dir`), at the stored assignment, `variant` (a left-right mirrored variant task puts the legend there), verdict `$BarDirFromEdge`. Invariant broken: every marker lies on col 0.
- `panel-color`
    - `concept`: `panel_color` is stored (0)
    - `$PanelColorFromCorner`: replaces `legend-panel`'s reading of the panel so that `panel_color` is derived per input as the color of the grid's corner cell at a new parameter `panel_corner`: DIAG_TL. Defined on every input. Fits every pair. Witness `panel-of-another-color`: breaks `legend-panel`, at the stored assignment, `variant` (a color-permuted variant task's panel), verdict `$PanelColorFromCorner`. Invariant broken: the panel's background is 0.
    - `panel_color=DominantColor`: derived per input as that input's commonest color, the field background (3 in train0). Fails Fit at train0.
    - `panel_color=SharedColor`: derived per input as every color of that input, so 0 is not the only value. Fails Fit at train0.
    - `panel_color=RarestColor`: derived per input as the rarest colors, 1 and 4 in train0. Fails Fit at train0.
- `field-background`
    - `concept`: the field background is the commonest color of the field rows (those holding no `panel_color` cell)
    - `$FieldBgFromBoundaryRow`: replaces `field` so that the background is the commonest color of the field row next to the panel. Undefined where that row has a tie or there is no panel. Fits every pair. Witness `listed-color-outnumbers-background`: breaks `field` (the background is the listed color 2 under the concept), at the stored assignment, `foreign`, verdict `$FieldBgFromBoundaryRow`. Invariant broken: background cells make up most of the field, and no object has more than 4 cells.
- `object-adjacency` & `count-measure`, `object-grouping` & `count-measure`: `$CountCells`'s model alone. Counting cells has no objects, so adjacency and grouping do not exist with that branch. Both points stand at the concept, since each exists with `count-measure`'s concept branch.
- `object-adjacency` & `object-grouping`, and every other pair of points: the two branches' changes applied together.

## Open parameters
- none

## Not formed
- A panel/field split by the region of `panel_color` cells, in place of the concept's split by rows that hold a `panel_color` cell: the two split the same way whenever the field holds no `panel_color` cell, which is true of every input. Not formed in this pass, and the witness it would need (a `panel_color` cell inside the field) is `foreign`.
- The field background as the commonest color of the whole grid (DominantColor): wherever it differs from the concept, it names `panel_color`, which no field cell holds, so every field cell would read as an object. That does not read the scene as a field at all.
- A derivation of `bar_dir` by a proposer: no proposer yields a direction. The clause derivation is `$BarDirFromEdge`.
- A bar that leaves the marker cell out, or starts at the far edge: train0's 8 bar at (3,0)–(3,1) starts at the marker and holds it.

## Tickets filed
- none
