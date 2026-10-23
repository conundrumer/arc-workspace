# e6de6e8f

## Concept
- The input is a strip of pipe pieces. Laid end to end in reading order, they make a pipe that runs down from a source at the top center of the output: a straight piece drops two cells, and an L piece steps one cell to the side its foot points to.

## Scene
- `pieces-in-a-strip`: the input is a strip of `input_height` rows holding pieces of `pipe_color` on `background`, with one blank column between each two pieces.
- `three-glyphs`: each piece is one of the glyphs in `piece_segment`: a bar one column wide and `input_height` rows high, or a two-column L whose top row is blank on one side.
- `pipe-fits-frame`: the pipe the pieces make stays inside an output frame of `out_dims`.

## Rules
- `source-mark`: the output is a frame of `out_dims` filled with `background`, and the cell at column `source_col` on the edge opposite `flow_dir` takes `source_color`.
- `read-order`: the pieces are taken in order from the input edge `read_from`.
- `lay-segments`: the first piece starts at the cell next to the source toward `flow_dir`. Each piece paints the cells its `piece_segment` entry gives, relative to its start, in `pipe_color`, and the next piece starts at that entry's exit cell.

## Parameters
- `background`: 0
- `pipe_color`: 2
    - the color of the input pieces and of the output pipe
- `source_color`: 3
- `out_dims`: 8 rows, 7 columns
- `source_col`: 3
    - the source's place along the edge opposite `flow_dir`
- `read_from`: left (DIR_L)
- `flow_dir`: down (DIR_B)
- `piece_segment`: a lookup table from glyph to segment, as offsets (along `flow_dir`, across) from the piece's start
    - bar `2` over `2` → cells (0,0), (1,0); exit (2,0)
    - L `2 0` over `2 2` → cells (0,0), (0,+1); exit (1,+1)
    - L `0 2` over `2 2` → cells (0,0), (0,−1); exit (1,−1)

## Scene parameters
- `input_height`: 2
