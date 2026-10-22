# d59b0160

## Concept
- A legend in the corner lists some colors; each panel that holds every legend color is erased, and every other panel stays.

## Scene
- `background`: the grid is filled with `background`.
- `legend-corner`: a box at corner `key_corner`, walled off from the rest of the grid by a 1-wide L of `divider` cells, holds a few single cells of distinct colors on `background`: the legend.
- `panels`: away from the legend, rectangles of `panel_fill`, each separated from the others and from the legend by `background`, hold scattered single cells of other colors.

## Rules
- `legend-colors`: the legend colors are the colors in the legend box other than `background`.
- `erase-full-panel`: a panel whose cells hold every legend color becomes `background`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 7
- `divider`: 3
    - the color of the L that walls off the legend
- `key_corner`: TL
    - the corner of the grid that holds the legend

## Scene parameters
- `panel_fill`: 0
    - the color that fills a panel apart from its scattered cells
