# f83cb3f6

## Concept
- Fits every train and test pair (`work/task/f83cb3f6/check_concept.py`, `work/task/f83cb3f6/probe.py pairs`). Every rule has a relational form: the wall is the line of `wall_color` cells, a perpendicular line meets the wall at a wall cell or at a hole, and the pull is the cell next to that wall cell on the dot's side. No approximation is used. No witness has the verdict `other`. The concept is undefined where the `wall_color` cells are fewer than two or do not lie on one row or one column. Parameters: `wall_color` = 8 and `background` = 0, both stored. The wall's axis and the dots' color come from each input.

## Choice points
- `wall-finding`: how the wall's cells are found
    - `concept`: the cells of the stored `wall_color`
    - `wall_color=RarestColor`: replaces the stored `wall_color` of `one-wall` with the input's rarest color, derived per input. Undefined where the rarest color ties, or where its cells lie on no single row or column. Fits every pair (8 is the rarest color of every input). Witness `wall_color=RarestColor`: a full wall with fewer dots than wall cells. It breaks no scene claim, stands at the stored assignment, and is `ordinary` with verdict `concept`.
    - `$WallByLine`: replaces the stored `wall_color` of `one-wall` with the one non-`background` color whose cells (two or more) all lie on one row or one column. It reads no `wall_color`, and is undefined where no color or more than one color does so. Fits every pair. Witness `wall-recolored`: the wall is drawn in 4. At the stored assignment it breaks `one-wall`, since no line of `wall_color` 8 exists. It is `variant` with verdict `$WallByLine`, and it breaks the invariant that every input's wall is color 8. `wall_color=RarestColor` gives the same output there, and the concept is undefined.
- `background`
    - `concept`: the stored `background`, 0
    - `background=DominantColor`: replaces the stored `background` with the input's commonest color, derived per input. Undefined where the commonest color ties. Fits every pair. Witness `background=DominantColor`: isolated dots in a checkerboard that outnumber the background cells. It breaks no scene claim and stands at the stored assignment. It is `borderline` with verdict `concept`, and it breaks the invariant that dots are sparse and 0 is the commonest color of every input.
- `wall-axis`
    - `concept`: the axis of the wall's line, read from each input
    - `$StoredAxis`: a stored `wall_axis` parameter. Undefined where the wall lies on the other axis. Fails Fit: at H it fails train1 (vertical wall), and at V it fails train0.
- `pile`: what several dots on one line and side give
    - `concept`: one cell against the wall (`pull-to-wall`)
    - `$Stack`: replaces `pull-to-wall`. Each dot keeps its own cell, stacked outward from the wall in order, as rigid single-cell bodies fall. Fails Fit at train0: col 9 above the wall has dots at rows 4 and 7, so the stack puts 5 at (6,9), where the output has 0.
- `pile-color`: which dot of a pile gives its color
    - `concept`: the dot nearest the wall
    - `$FarthestDot`: replaces `pull-to-wall` so that the dot farthest from the wall gives the color. Fits every pair. Witness `two-dot-colors`: col 1 above the wall holds 2 at row 0 and 5 at row 2. It breaks `dots` (one dot color), is `borderline` with verdict `concept`, and breaks the invariant that all dots of an input share one color.
- `hole-dots`: what a dot on a line through a hole gives
    - `concept`: no mark (`hole-drops`)
    - `$HoleKeep`: replaces `hole-drops`. The dot stays where it is. Fails Fit at train1: the dots at (10,0), (11,10) and (11,12) lie on rows 9–11, which are the wall's holes, and the output has 0 there.
    - `$HoleThrough`: replaces `hole-drops`. The dot passes through the hole and lands at the far edge of the other side. Fails Fit at train1: (10,0) would land at (10,13), where the output has 0.
- `dot-color`: the color a pile takes
    - `concept`: copied from the input's dots
    - `$StoredDotColor`: a stored dot-color parameter. Fails Fit: the dot colors are 5, 1, 2 and 3 across the pairs, so 5 fails train1.
- `wall-finding` & `background`, `wall-finding` & `wall-axis`, `wall-finding` & `pile`, `wall-finding` & `pile-color`, `wall-finding` & `hole-dots`, `wall-finding` & `dot-color`, `background` & `wall-axis`, `background` & `pile`, `background` & `pile-color`, `background` & `hole-dots`, `background` & `dot-color`, `wall-axis` & `pile`, `wall-axis` & `pile-color`, `wall-axis` & `hole-dots`, `wall-axis` & `dot-color`, `pile` & `hole-dots`, `pile` & `dot-color`, `pile-color` & `hole-dots`, `hole-dots` & `dot-color`: the two branches' changes applied together
- `pile` & `pile-color`: `$Stack`'s model alone, since a stack keeps every dot's color and no dot of a pile is chosen. The `pile-color` property exists only with the concept branch of `pile`.
    - `$Stack` & `$FarthestDot`: `$Stack`'s model
- `dot-color` & `pile-color`: `$StoredDotColor`'s model alone, since every pile takes the stored color and no dot of a pile is chosen. The `pile-color` property exists only with the concept branch of `dot-color`.
    - `$StoredDotColor` & `$FarthestDot`: `$StoredDotColor`'s model

## Open parameters
none

## Not formed
- `wall_color` or `background` derived by another proposer: on one input, with `ex_out` empty, SharedColor gives every color of that input, which is more than one value. OutNewColor, VanishedColor, ChangedColor, UnchangedColor and the pair proposers read train outputs, which a `@derive` branch does not have. The dimension and tiling proposers give no color.
- A dot that sits in a hole cell: no input has one. The concept drops it as a dot on a hole line, and `$HoleKeep` already covers keeping dots on hole lines. No reading treats the hole cell apart from the rest of its line.
- Shapes pulled rigidly (Gravity over connected pieces): every input's dots are isolated single cells, so this is `$Stack` on these inputs, and `$Stack` fails train0.
- A dot pulled to the nearest wall cell along the wall when its own line meets a hole: fails train2, where (3,9) would put 2 at (6,8) and the output has 0.

## Tickets filed
- none
