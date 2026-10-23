# b10624e5

## Concept
- A cross cuts the grid into four quadrants. One quadrant holds a full figure built around a square core, and each other quadrant holds only a core. Each lone core grows the figure around itself, mirrored across the dividers into its quadrant and scaled to its core's size.

## Scene
- `cross`: one full row and one full column of `divider_color` cross at the center and cut the grid into four equal quadrants on a field of `background`.
- `template-quadrant`: the quadrant at `template_corner` holds one figure: a solid square of `core_color` with blocks of other colors attached around it.
- `lone-cores`: each other quadrant holds one solid square of `core_color` and nothing else.
- `scalable`: on each axis, the template figure is constant on blocks of side t / k aligned to the template core, where t is the template core's extent and k a whole number, and k divides each lone core's extent on that axis.

## Rules
- `template`: the template is the one quadrant that holds a color other than `background` and `core_color`.
- `keep-input`: each input cell stays in the output unless a rule below paints it.
- `mirror`: the figure a lone core gets is the template quadrant reflected across each divider that lies between the template quadrant and that core's quadrant: one reflection for a side neighbor, both for the diagonal quadrant.
- `scale`: on each axis, the template's blocks of side u, the largest side whose tiling aligned to the template core leaves the template quadrant constant on each block, number k = t / u across the template core. Each such block becomes a block of side s / k, where s is the lone core's extent on that axis, laid out so that the template core's blocks land on the lone core. The model is undefined where k does not divide s.
- `paint`: each cell of a lone core's quadrant that the scaled figure covers with a block of a color other than `background` takes that color. A block's part outside the quadrant is dropped.

## Parameters
- `background`: 4
- `divider_color`: 1
- `core_color`: 2

## Scene parameters
- `template_corner`: TL
    - the quadrant that holds the full figure
