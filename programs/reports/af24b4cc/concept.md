# af24b4cc

## Concept
- Shrink each block of a grid of blocks to one cell of its commonest color, keeping the background border and dropping the dividers.

## Scene
- `block-grid`: the input is a grid of equal blocks laid out in rows and columns, with a 1-wide line of `bg` along every edge of the input and between each two adjacent blocks.
- `block-size`: each block is `block_h` rows by `block_w` columns.
- `block-layout`: the blocks stand in `block_rows` rows and `block_cols` columns.
- `no-bg-in-block`: no cell of a block is `bg`.
- `two-colors`: each block holds one or two colors.
- `unique-mode`: in each block, one color occurs more often than every other color.

## Rules
- `output-frame`: the output has one row per block row and one column per block column, inside a border of `bg` that is `margin` cells wide.
- `block-mode`: the output cell of a block takes that block's commonest color.

## Parameters
- `bg`: 0
    - the color of the dividers and the border, in the input and in the output
- `margin`: 1
    - the width of the output's border

## Scene parameters
- `block_h`: 3
- `block_w`: 2
- `block_rows`: 2
- `block_cols`: 3
