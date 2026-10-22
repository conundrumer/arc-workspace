# c3e719e8

## Concept
- The input is used as its own stencil: the output is a grid of input-sized blocks, one block per input cell, and a block holds a copy of the input where its cell has the input's most common color, and is blank elsewhere.

## Scene
- `small-grid`: every input is a grid of `input_size` with no cell of color `background`.
- `unique-mode`: one color is strictly more common in the input than every other color.

## Rules
- `block-layout`: the output is the input's height times its height in rows and its width times its width in columns, cut into blocks of the input's size, and block (i, j) stands for input cell (i, j).
- `copy-where-mode`: a block whose input cell has the most common color is a copy of the input.
- `blank-elsewhere`: every other block is filled with `background`.

## Parameters
- `background`: `0`
    - the color of a block whose input cell does not have the most common color

## Scene parameters
- `input_size`: 3×3
