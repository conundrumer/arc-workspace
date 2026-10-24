# f823c43c

## Concept
- A repeating wallpaper pattern has been sprinkled with noise of one color; wipe the noise off by restoring the pattern underneath.

## Scene
- `periodic-pattern`: the grid is a pattern that repeats with one period on each axis: the period shortest on both axes among those at which every two cells not of `noise_color` at the same place of the tile agree; that period varies from input to input (2 by 2, 3 by 3, 3 by 3).
- `noise-overwrites`: some cells of the pattern are overwritten with `noise_color`, scattered with no structure, and `noise_color` is no color of the pattern.
- `phase-visible`: each place of the repeating tile has at least one copy in the grid that the noise leaves showing.

## Rules
- `restore-by-phase`: each output cell takes the color that the cells not of `noise_color` hold at the same place of the repeating tile; the output has the input's size.

## Parameters
- `noise_color`: 6
    - the color of the noise that the output removes

## Scene parameters
none
