# 20a9e565

## Concept
- The input shows the first terms of a growing sequence of figures, and two corner marks frame a spot farther along the sequence; the output is what the continued sequence draws inside that frame.

## Scene
- `growing-sequence`: on a `background` field, figures stand one after another along one direction, each separated from the next by background; each term grows from the one before it by the same step, and the term colors repeat a cycle.
- `corner-marks`: two 3-cell L marks of `marker_color`, one at each of the two `marker_corners` of a rectangle, the window; each mark's corner cell is the window's corner cell, and the marks touch no figure.
- `window-ahead`: the window lies past the last shown term, across the place where a later term of the continued sequence stands.

## Rules
- `continue-sequence`: the sequence goes on past its last shown term; each new term takes the growth, the spacing and the alignment that the shown terms follow from one term to the next, and the next color of the cycle.
- `crop-window`: the output is the window, marks included in its extent; each cell takes the color the continued sequence draws there, and `background` where it draws nothing.

## Parameters
- `background`: 0
- `marker_color`: 5
    - the color of the corner marks that frame the window

## Scene parameters
- `marker_corners`: top-left and bottom-right
    - the diagonal on which the two corner marks stand
