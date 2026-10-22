# bd283c4a

## Concept
- Count the cells of each color, then sort them into a stacked bar: the most common color fills first, from the bottom-left corner up each column and then on to the next column to the right, and each next color in order of count continues where the last one stopped.

## Scene
- `scattered-colors`: every input is a grid of a few colors, each cell one color, with the cells of each color scattered in no shape.
- `distinct-counts`: no two colors of an input have the same cell count.

## Rules
- `same-size`: the output has the input's size.
- `count-order`: the colors are ranked by their cell count in the input, the highest first; colors of equal count take either order, each order one output.
- `raster-fill`: the output cells are taken in a raster order that starts at corner `start_corner`, runs along axis `fill_axis` within a line, and then steps to the next line away from that corner; each color, in rank order, takes as many cells of that order as its input count, after the cells the colors before it took.

## Parameters
- `start_corner`: bottom-left
    - the corner at which the raster order starts, and from which it steps line by line
- `fill_axis`: vertical
    - the axis along which the raster order runs within one line, before it steps to the next line

## Scene parameters
- none
