# b0722778

## Concept
- Each band of the grid shows three small two-colored squares: a sample, the sample after a change (a mirror flip, a quarter turn, or a recoloring), and a query square. Work out the change from the first two squares and apply it to the query. The output stacks the changed queries in the band layout.

## Scene
- `bands`: the grid is cut into bands of `block-size` rows by blank rows of width `band-gap`, with the bands stacked along the axis across `read-from`; a blank cell holds `background`.
- `three-blocks`: each band holds three solid `block-size`×`block-size` blocks of non-`background` cells, read in order from edge `read-from`: the sample, the sample's image, and the query. Blank columns of width `gap-1` separate the sample from its image, and of width `gap-2` the image from the query.
- `two-colors`: each block holds exactly `colors-per-block` colors.
- `image-of-sample`: the image is the sample under one change: a recoloring that keeps the sample's cell layout, or a mirror flip across a vertical or horizontal axis, or a quarter turn. The image under a recoloring has colors the sample does not, and the query of a recoloring band uses only the sample's colors.

## Rules
- `find-change`: the change is read from the sample and its image, the first that fits in this order: a recoloring, when the image's cell-by-cell color map from the sample is a function; else the mirror flip across a vertical or horizontal axis that takes the sample onto the image; else the quarter turn that does.
- `apply-change`: the query under that change is the band's result: the recoloring maps each query cell's color through the map, and a flip or turn moves the query's cells.
- `stack`: the output is `block-size` wide, as tall as the input, and holds each band's result at the band's rows, with `background` on the blank rows between.

## Parameters
- `background`: 0
- `read-from`: L
    - The edge from which a band's three blocks are read in order: sample, image, query. The bands stack along the axis across this edge's axis.

## Scene parameters
- `block-size`: 2
- `gap-1`: 1
    - Blank columns between the sample and its image.
- `gap-2`: 2
    - Blank columns between the image and the query.
- `band-gap`: 1
    - Blank rows between bands.
- `colors-per-block`: 2
