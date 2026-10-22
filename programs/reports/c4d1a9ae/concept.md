# c4d1a9ae

## Concept
- The grid is cut into side-by-side panels, each drawn in its own color, and each panel fills its empty cells with the color of the next panel along, the last panel taking the first panel's color.

## Scene
- `background`: one color fills most of the grid and every cell that no panel draws.
- `separator-columns`: full lines of background color, perpendicular to the axis of `source-dir`, cut the grid into `panel-count` panels.
- `one-color-panel`: each panel draws its marks in one color other than the background, and no two panels share a color.

## Rules
- `fill-from-next`: each background cell of a panel takes the color of the panel next to it toward `source-dir`.
- `wrap`: the last panel toward `source-dir` takes the color of the first panel, the panel furthest the other way.
- `keep-rest`: each mark of a panel and each cell of a separator line keeps its color.

## Parameters
- `source-dir`: R
    - the direction, along the line of panels, in which a panel finds the panel whose color it takes

## Scene parameters
- `panel-count`: 3
