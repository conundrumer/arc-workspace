# c6e1b8da

## Concept
- Some rectangles have a thin line sticking out of one side. Each such rectangle slides along its line until its leading side reaches the line's tip, and lies on top of whatever it lands on. The other rectangles stay where they are and show whole again where the sliding ones hid them.

## Scene
- `solid-rectangles`: every input holds solid rectangles on a field of `background`, each rectangle in its own color.
- `tails`: at least one rectangle has a tail: a straight line one cell wide, of the rectangle's color, that goes out from the middle part of one side, perpendicular to that side. The other rectangles have no tail.
- `tailed-on-top`: a tailed rectangle and its tail lie on top of any rectangle they overlap. Only a tailed rectangle or a tail hides part of a rectangle.
- `tailed-apart`: tailed rectangles do not overlap one another, before or after they slide.

## Rules
- `slide-by-tail`: each tailed rectangle moves in the direction its tail points, by as many cells as the tail has, so its leading side ends on the tail's tip. The tail is not drawn.
- `slid-on-top`: a moved rectangle covers any other rectangle where they overlap.
- `restore-whole`: each rectangle with no tail is drawn whole at its place, the cells a tailed rectangle or a tail hid in the input included.
- `vacated-background`: a cell that no rectangle covers in the output is `background`.

## Parameters
- `background`: 0

## Scene parameters
- none
