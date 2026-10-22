# d2acf2cb

## Concept
- Two `marker` cells at the two ends of a row or column mark that line, and every cell between them is recoded: `0` becomes `8` and `6` becomes `7`.

## Scene
- `marker-pairs`: each `marker` cell sits on a grid edge, and a `marker` cell faces it on the opposite edge, on the same row or column.
- `one-axis`: in each input, every marked line runs along one axis.
- `recodable-field`: every cell that is not a `marker` has a color that is a key of `recolor`.

## Rules
- `recode-between`: each cell strictly between the two `marker` cells of a marked line takes the color that `recolor` maps its color to.
- `rest-kept`: every other cell keeps its color.

## Parameters
- `marker`: `4`
- `recolor`: `0` to `8`, `6` to `7`
    - the color each cell of a marked line takes, keyed by its input color

## Scene parameters
- none
