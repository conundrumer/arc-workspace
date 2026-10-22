# d07ae81c

## Concept
- Each lone marker shoots diagonal lines to the grid edges, and at each cell a line takes the color of the markers that sit on the background color it crosses there.

## Scene
- `banded-background`: each marker replaces one cell of a background of `background_colors` colors; that background is full-length row and column bands of one color laid over a field of the other color, so rows of one kind repeat and columns of one kind repeat.
- `lone-markers`: a marker is a single cell of a color that is not a background color, and it sits on the color the bands give the cell it replaces.
- `one-marker-color-per-background`: each background color has markers sitting on it, the markers on one background color all have one color, and the marker colors of different background colors differ.

## Rules
- `marker-color-map`: each background color maps to the color of the markers that sit on it; a marker sits on the color that another row has at the marker's column, where that row equals the marker's row at every column where neither holds a marker, or likewise with columns and rows swapped.
- `diagonal-rays`: from each marker, a line runs toward each of the four diagonal directions, through markers, to the grid edge.
- `recolor-by-background`: each background cell on a line takes the marker color its background color maps to; every other cell keeps its color.

## Parameters
- none

## Scene parameters
- `background_colors`: 2
    - the number of background colors
