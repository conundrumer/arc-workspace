# c7f57c3e

## Concept
- Several copies of one small figure, at different scales, sit on a plain background. Each copy has the same body of `frame-color` cells, and other colored cells hang off that body. The hanging cells come in two patterns. Each figure trades its pattern for the other one, fitted to its own body and scale.

## Scene
- `plain-background`: one color fills every cell that no figure covers.
- `figures`: each figure is one 8-connected group of non-background cells.
- `scaled-copies-of-one-body`: the `frame-color` cells of every figure are one shape, at an integer scale per figure, with one orientation, and every figure's cells are blocks of that scale.
- `two-decorations`: a figure's cells of other colors than `frame-color`, put in the frame of its body and its scale, form one of exactly two patterns, and each pattern occurs on at least one figure.

## Rules
- `swap-decorations`: each figure keeps its `frame-color` body, loses its own decoration, and takes the other decoration, scaled to its own scale and placed at the same position relative to its body.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `frame-color`: 1
    - the color of the body that is the same on every figure

## Scene parameters
- none
