# e99362f0

## Concept
- A cross of lines cuts the grid into four equal panels, each drawn in its own color; stack the four panels and, where several panels have a mark at one cell, the color with the highest priority shows.

## Scene
- `divider-cross`: one full row and one full column of the `divider` color cross and cut the grid into four panels of one size.
- `one-color-per-panel`: each panel holds marks of one color on the `background` color, and the four panels have four different colors, placed as `panel_color` gives.

## Rules
- `stack-by-priority`: the output has the size of one panel, and each output cell takes, of the colors that the four panels have at that cell, the one highest in `priority`, and the `background` color where no panel has a mark.

## Parameters
- `priority`: 8 > 7 > 9 > 2
    - the order of the panel colors, highest first
- `divider`: 4
- `background`: 0

## Scene parameters
- `panel_color`: top-left 7, top-right 9, bottom-left 2, bottom-right 8
