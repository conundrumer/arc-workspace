# ac6f9922

## Concept
- Bars of one color, drawn on a background, cut out a grid of windows, and some windows hold a colored mark; the output is a small picture of that grid of windows, one cell per window, colored with the window's mark, or with the background where the window is empty.

## Scene
- `framed-bars`: every input is a field of the background color with bars of one other color on it; the background shows outside the bars, at least along the grid edge.
- `window-grid`: the bars enclose rectangular windows of the background color; the windows fall into rows that share their top and bottom rows of cells, and into columns that share their left and right columns of cells, so each window is at one row and one column of a full grid of windows. The bars between windows can be wider than one cell, and differ in width.
- `one-mark`: a window holds no mark or one mark: a solid rectangle of one color that is neither the background nor the bar color, which touches no edge of the window. Marks differ in size and shape, and two windows can hold marks of one color.

## Rules
- `window-picture`: the output has one row per row of windows and one column per column of windows, in the order of the windows in the input.
- `mark-color`: each output cell takes the color of the mark in its window, and the background color where the window holds no mark.

## Parameters
none

## Scene parameters
none
