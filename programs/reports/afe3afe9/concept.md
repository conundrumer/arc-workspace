# afe3afe9

## Concept
- Hollow squares sit on a tiling beside a line along one edge; each square becomes one cell, and the cells slide together along each slot line toward the side a quarter turn from the line, in sense `turn_sense`.

## Scene
- `edge-line`: one full edge of the grid is a line of color `line_color`; every other cell outside the squares is background `bg_color`.
- `ring-tiling`: hollow squares of side `ring_side` sit on a square tiling of `slot_count` by `slot_count` slots, with a gap of `ring_gap` between neighboring slots; each square has one color.
- `pack-gap-empty`: on the pack axis, the middle slot line holds no square.

## Rules
- `pack-side`: the pack side is the line's side turned a quarter turn in sense `turn_sense`.
- `ring-cell`: each square stands for one cell of its color at its slot.
- `pack-lines`: along each slot line on the pack axis, the cells keep their order and slide to the pack side with no gaps between them.
- `output-extent`: the output has one row or column per slot line across the pack axis, from the first line that holds a square to the last (7), and along the pack axis it holds the slot lines that hold a square (6); the rest is `bg_color`.

## Parameters
- `turn_sense`: clockwise
    - the sense of the quarter turn from the line's side to the pack side
- `line_color`: 1
- `bg_color`: 0
- `ring_side`: 3
- `ring_gap`: 1

## Scene parameters
- `slot_count`: 7
