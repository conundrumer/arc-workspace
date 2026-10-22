# e4888269

## Concept
- A two-column legend lists color replacements, one per row; apply them one after another down the legend to every cell outside it, so a cell that one row recolors can be recolored again by a later row.

## Scene
- `background`: the commonest color fills the field.
- `legend`: one solid block of non-background cells, two cells wide and one or more entries long, shares no side with any other non-background cell; it is the one 4-connected group of non-background cells that holds more than one color.
- `legend-entry`: each line of the legend across its width is one entry: the cell on the `source_dir` side holds the source color, and the other cell the target color.
- `marks`: the rest of the grid holds marks and shapes of single colors, and in some inputs a divider line.

## Rules
- `legend-kept`: the legend is unchanged.
- `sequential-replace`: the entries apply in order, from the entry nearest the `order_dir` edge to the farthest; each entry recolors every cell outside the legend that holds its source color at that step to its target color.
- `rest-kept`: a cell whose color no step changes keeps its color.

## Parameters
- `order_dir`: `DIR_T`
    - the edge of the legend whose entry applies first; the legend runs along this direction's axis
- `source_dir`: `DIR_L`
    - the side of each entry that holds the source color, on the axis across the legend

## Scene parameters
- none
