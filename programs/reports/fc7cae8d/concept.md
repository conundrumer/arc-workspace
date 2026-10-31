# fc7cae8d

## Concept
- A picture carries two colored strips on two adjacent sides, and two adjacent edges of the grid are drawn in the same two colors; turn or flip the picture so each strip lands on the grid edge of its color, and give the picture without its strips.

## Scene
- `color-frame`: two adjacent edges of the grid are each a solid line of one color, the two colors different, with stray cells of the line's color just inside it.
- `noise-edges`: the other two edges hold scattered `noise_color` cells on `background`.
- `picture`: one rectangle on the `background` field, clear of the edges, with a one-cell-wide strip outside each of two adjacent sides, as long as that side, one strip in each frame color.
- `picture-colors`: no cell of the picture holds a frame color.

## Rules
- `crop-picture`: the output is the picture's box, the strips left out, each cell copied, `background` cells included.
- `orient-by-color`: the picture is moved by the D4 element that takes the side each strip borders to the grid edge of the strip's color.

## Parameters
none

## Scene parameters
- `background`: 0
- `noise_color`: 5
