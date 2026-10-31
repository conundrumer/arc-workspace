# fcb5c309

## Concept
- Several rectangular frames sit among scattered dots; cut out the frame that holds the most dots and redraw its border in the dot color.

## Scene
- `background`: every cell that is neither frame nor dot is `background`.
- `frames`: two or more hollow rectangle outlines, one cell thick, all in one frame color, none touching another.
- `dots`: cells of one dot color, different from the frame color, scattered inside and outside the frames, some touching one another or a frame; no dot sits on a frame's border.
- `unique-most`: exactly one frame holds more dots inside it than every other frame.

## Rules
- `select-most-dots`: the selected frame is the one with the most dots strictly inside its border.
- `crop-frame`: the output is the selected frame's bounding box, border included.
- `recolor-border`: each border cell of the output takes the dot color; each interior cell keeps its input color (dot color or `background`).

## Parameters
- `background`: 0

## Scene parameters
- none
