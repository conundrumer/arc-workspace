# d749d46f

## Concept
- A row of solid bars hangs from the top edge of a strip. The output lays the same bars out twice, in the same left-to-right order, on a canvas `output-height` rows tall: along the top edge each bar lies flat, and along the bottom edge each bar stands up.

## Scene
- `two-colors`: the input holds two colors, a background and a bar color.
- `bars-hang-from-top`: each bar is a solid rectangle of the bar color whose side toward `hang-edge` lies on that edge.
- `bars-in-a-row`: the bars stand side by side, separated by `gap` background columns, the first bar starting at the `pack-edge` edge and the last ending at the opposite edge.
- `height-is-tallest-bar`: the input is as tall as its tallest bar.

## Rules
- `bar-color`: the bar color is the color of the top-left cell, the corner of the first bar, and the other color is the background.
- `top-lies-flat`: along the top edge, each bar is turned so that its longer side runs along the row, with its top side on row 0. The bars are packed from col 0, in input order, with `gap` background columns between neighbors.
- `bottom-stands-up`: along the bottom edge, each bar is turned so that its longer side runs down the column, with its bottom side on the last row. The bars are packed from col 0, in input order, with `gap` background columns between neighbors.
- `square-unchanged`: a square bar is the same in both rows.
- `output-size`: the output is `output-height` rows tall, and as wide as the top row of bars: the sum of the bars' longer sides plus `gap` for each space between neighbors.
- `rest-background`: every other cell is the background color, and the bar color is kept.

## Parameters
- `hang-edge`: T
    - the edge the input bars hang from, and the edge the flat row of the output hangs from; the standing row stands on the opposite edge
- `pack-edge`: L
    - the edge each row of bars is packed from
- `output-height`: 10
    - the row count of every output
- `gap`: 1
    - the background columns between neighboring bars, in the input and in each row of bars of the output

## Scene parameters
none
