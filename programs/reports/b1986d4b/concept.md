# b1986d4b

## Concept
- Count the solid squares of each size, and draw the counts as a row of nested squares: the first stack holds one square of every size, and each later stack drops the sizes that have run out, smallest drawn on top in one shared corner.

## Scene
- `background`: one color fills most of the grid.
- `noise`: scattered cells of one other color, alone or in small clumps, in more pieces than any other color.
- `squares`: every piece of each color other than the background and the noise is a solid square, apart from every other square.
- `color-per-size`: all squares of one size have one color, and different sizes have different colors.

## Rules
- `square-reading`: the background is the commonest color, the noise color is the other color in the most pieces, and the squares are the pieces of the remaining colors.
- `count-per-size`: the number of squares of each size is read from the input, and every square counts.
- `stacks`: stack i, from 0, holds a square of each size whose count is greater than i, so the stacks hold fewer sizes from first to last.
- `nesting`: in a stack, each square sits in the `corner` of the stack, and a smaller square is drawn over a larger one, each in the color its size has in the input.
- `layout`: the stacks are laid in a line along `axis`, starting from the `corner` side, each as wide as its largest square, and each followed by a line of background `gap` wide, the last one included.
- `extent`: the output's extent across `axis` is the largest size plus `gap`, and every cell not in a square is background.

## Parameters
- `corner`: top-left
    - the corner each square sits in within its stack, and the end of the line where the first stack stands
- `axis`: horizontal
    - the axis the stacks are laid along
- `gap`: 1
    - the width of background after each stack, and below the stacks

## Scene parameters
none
