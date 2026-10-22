# aee291af

## Concept
- Several framed squares carry a pattern of marks; all show the same pattern but one, and the output is the odd one out.

## Scene
- `field`: a field of `background`, with stray cells of `frame_color` scattered over it, some of them touching a box.
- `boxes`: several disjoint square boxes of one size, each with a 1-wide border of `frame_color` and an interior of `frame_color` and `mark_color` cells, where the marks span the whole interior.
- `one-odd`: every box but one has the same interior pattern, and the one left has another pattern.

## Rules
- `odd-box`: the output is the box whose pattern no other box shares, border included.

## Parameters
- `frame_color`: 8
- `mark_color`: 2

## Scene parameters
- `background`: 1
