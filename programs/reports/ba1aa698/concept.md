# ba1aa698

## Concept
- A row of panels shows one shape that moves by the same step from each panel to the next; the output draws the panel that comes next in that row.

## Scene
- `panel-row`: the grid is a row of equal panels along the axis of `extend-dir`, each panel bordered on every side by divider lines of one color.
- `one-shape-per-panel`: each panel holds one copy of one shape on the panel's background, and the shape is the same in every panel.
- `constant-step`: from each panel to the next toward `extend-dir`, the shape moves by the same number of cells across that axis.
- `across-only`: the shape keeps one place along that axis in every panel.
- `next-fits`: the shape moved by one more step still lies inside the panel.

## Rules
- `next-panel`: the output is one panel with its border of divider lines, its background and divider colors as in the input, and the shape at the place one more step past the last panel toward `extend-dir` gives.

## Parameters
- `extend-dir`: R
    - the end of the panel row past which the sequence continues

## Scene parameters
- none
