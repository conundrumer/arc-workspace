# e87109e9

## Concept
- A square block shoots a beam toward each of the four sides. A beam runs straight until it meets a rectangle, then turns left or right as the legend says for that rectangle's color, and it ends at the grid edge. The legend strip is dropped from the output.

## Scene
- `legend-strip`: a strip along the `legend_edge` side of the grid, drawn in `legend_frame_color`, holds `legend_box_count` boxes of extent `legend_box_extent`. Each box is `legend_blank_color` except for one full line of one color, the marker, along one of the two box sides perpendicular to `legend_edge`.
- `legend-colors-distinct`: no two legend boxes have the same marker color.
- `field`: the rest of the grid, the scene, is a field of one background color, which differs between inputs.
- `rectangles`: the scene holds solid one-color rectangles. Each rectangle's color is the marker color of a legend box, and no two rectangles touch.
- `block`: the scene holds one solid square of `block_color`, which touches no rectangle.
- `square-hits`: each beam that meets a rectangle meets it with its full width, and after each turn the beam has at least one free step.

## Rules
- `crop-scene`: the output is the scene, the input without the legend strip.
- `beam-each-way`: from the block, a copy of the block slides one cell at a time toward each of the four cardinal directions.
- `turn-at-rectangle`: when the next step of a copy would cover a cell of a rectangle, the copy turns by the sense the legend box of that rectangle's color gives, and slides on from where it stopped. A marker on the box side that a quarter turn in sense s takes `legend_edge` to gives a turn in sense s: with the legend on top, a marker on the left side gives a left turn, and a marker on the right side gives a right turn. A copy whose next step would cover a cell of a color that no legend box holds stops there.
- `exit-at-edge`: a copy stops when its next step would leave the grid.
- `paint-trace`: each cell that a copy covers on its way takes `block_color`. Every other cell keeps its scene color. Beams cross each other and the block freely.

## Parameters
- `legend_edge`: top
    - the side of the grid the legend strip sits on
- `legend_frame_color`: `5`
- `legend_blank_color`: `0`
- `block_color`: `8`
    - the color of the block and of the beams

## Scene parameters
- `legend_box_count`: 4
- `legend_box_extent`: 4
