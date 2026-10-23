# e7a25a18

## Concept
- A small square of four colored blocks sits inside a square frame; crop to the frame and blow the small square up so it fills the frame's inside.

## Scene
- `one-frame`: the input holds one square outline of color `frame_color`, one cell thick, on a field of `background`.
- `quad-pattern`: inside the frame, on `background`, lies one solid square pattern made of four equal square blocks in a 2×2 arrangement, each block one color, none of them `frame_color` or `background`.
- `pattern-fits-inside`: the pattern's side divides the side of the frame's inside, by the ratio `interior_ratio`.

## Rules
- `crop-to-frame`: the output is the frame's box, with the frame drawn in `frame_color` on its border.
- `scale-pattern`: the inside of the frame is the pattern scaled up by the ratio of the inside's side to the pattern's side, so each block of the pattern fills the matching quadrant of the inside.

## Parameters
- `frame_color`: 2
- `background`: 0

## Scene parameters
- `interior_ratio`: 2
    - the side of the frame's inside over the side of the pattern
