# de809cff

## Concept
- Two colors paint overlapping filled rectangles, sprinkled with stray pixels. Wipe off the strays, and turn each background pinhole in a rectangle into a `mark_color` cell ringed by the other color.

## Scene
- `background`: the field is `background`.
- `two-colors`: two colors other than `background` and `mark_color` each paint one or more filled axis-aligned rectangles, and rectangles of one color do not touch.
- `overlap`: each rectangle overlaps a rectangle of the other color, and in each overlap one of the two is drawn over the other.
- `pinholes`: some cells of each rectangle's visible part are `background`: lone cells or two adjacent cells, some on the rectangle's edge.
- `rings-apart`: no cell lies within `ring_reach` of pinholes of both colors.
- `strays`: stray cells of the two colors lie outside the rectangles, some touching a rectangle's edge, and a stray of the other color may lie inside a rectangle's visible part.
- `no-mark`: no input cell is `mark_color`.

## Rules
- `clean`: each rectangle's visible part fills with its color, and each cell outside every rectangle becomes `background`.
- `ring`: the box of reach `ring_reach` around each pinhole takes the other color of the two, clipped at the frame, over the rectangles and the field alike.
- `mark`: each pinhole becomes `mark_color`, over any ring.

## Parameters
- `background`: 0
- `mark_color`: 8
- `ring_reach`: 1
    - the Chebyshev distance from the pinhole that the ring reaches

## Scene parameters
- none
