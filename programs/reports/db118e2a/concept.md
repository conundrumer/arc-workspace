# db118e2a

## Concept
- Cut the small picture out of the framed panel, give it a snug frame of the panel's color, and draw two copies of it on a blank canvas, one near the top-left corner and one near the bottom-right corner.

## Scene
- `framed-panel`: the whole input is one panel: a border `frame_width` cells thick of one frame color runs along the grid's edges, the four corner cells are `bg`, and the rest of the panel is `bg` with some marks of any colors, the frame color included.
- `content-extent`: the marks inside the frame have a bounding box of `content_extent`.

## Rules
- `crop-content`: the picture is the bounding box of the marks inside the frame, cut from the input as it stands.
- `snug-frame`: the picture is wrapped in a border `frame_width` cells thick of the input's frame color, with the four corner cells `bg`.
- `two-copies`: the output is a `canvas_size` grid of `bg`, and the framed picture is drawn at each of the two corners on the diagonal `copy_axis`, inset `corner_inset` cells from both edges of that corner.

## Parameters
- `bg`: 7
- `frame_width`: 1
- `canvas_size`: 15 × 15
- `copy_axis`: the main diagonal, top-left to bottom-right
    - the diagonal whose two corners each get a copy
- `corner_inset`: 2
    - the gap between a copy and each of the two edges of its corner

## Scene parameters
- `content_extent`: 3 × 3
