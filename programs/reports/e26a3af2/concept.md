# e26a3af2

## Concept
- The grid is a set of solid color stripes with noise sprinkled over them, and the output wipes the noise off, so each stripe is back to one color.

## Scene
- `stripes`: the grid is cut, along one axis, into stripes that run the full length of the other axis, and each stripe has one color.
- `adjacent-stripes-differ`: two adjacent stripes have different colors.
- `sparse-noise`: some cells carry a color other than their stripe's color, and in each line across a stripe's length, the stripe's color holds more than half of the cells.

## Rules
- `line-axis`: the stripe axis is the axis on which each line has one color that holds more than half of its cells.
- `line-mode`: each line on the stripe axis is painted whole with its commonest color.

## Parameters
- none

## Scene parameters
- none
