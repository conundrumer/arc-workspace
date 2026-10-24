# f0f8a26d

## Concept
- Every straight bar turns a quarter turn about its middle cell.

## Scene
- `background-field`: a field of `background`.
- `one-mark-color`: every non-background cell holds one color, the same across the input.
- `straight-bars`: the marked cells form 4-connected parts, each a straight 1-wide bar along a row or a column, a lone cell included.
- `odd-length`: every bar has an odd length, so it has one middle cell.
- `turn-inside-frame`: every bar's quarter turn about its middle cell lies inside the frame.

## Rules
- `quarter-turn`: each bar is redrawn on the other axis, with the same length and the same middle cell, in the mark color.
- `union`: the output is the background with the union of the turned bars, so bars that cross after the turn share their cell.
- `same-frame`: the output has the input's size, and off the scene, a turned bar's cells past the frame are dropped.

## Parameters
- `background`: 7

## Scene parameters
none
