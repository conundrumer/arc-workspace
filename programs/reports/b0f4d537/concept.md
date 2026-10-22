# b0f4d537

## Concept
- A small key draws colored lines and shows which line lies on top at each crossing; a dotted field marks where the lines run. Redraw the key at the field's size, with its lines on the marked rows and columns.

## Scene
- `two-panels`: a full line of `divider` cells, running along `divider_axis`, splits the input into two panels.
- `key-panel`: one panel holds the key at its `key_end` end, and `divider` cells fill the rest of that panel.
- `key-grid`: the key has odd height and odd width; each odd row is a line of one color across the key, each odd column is a line of one color down the key, each cell off both lines is `background`, each crossing cell has the color of one of its two lines, and no key cell is `marker` or `divider`.
- `field`: the other panel is the field, of `background` cells and `marker` cells, with no line at its border and no two lines adjacent.
- `field-markers`: the field has as many line rows and as many line columns as the key; a `marker` cell sits at both ends of each line, on the field border, and at each crossing of a line row with a line column, and nowhere else.

## Rules
- `find-panels`: the field is the panel that holds `marker` cells; the key is the cells of the other panel that are not `divider`.
- `field-lines`: a line row of the field is a row whose two border cells are `marker`; a line column is a column whose two border cells are `marker`.
- `stretch-key`: the output has the field's size; the k-th line row of the field takes the key's k-th line row, each other row takes the key row off the lines that has as many line rows above it as that row has, and columns map the same way; each output cell is the key cell at its mapped row and column.

## Parameters
- `divider`: 5
- `marker`: 4

## Scene parameters
- `background`: 0
- `divider_axis`: the divider is a column, running top to bottom
- `key_end`: top
    - the end of the key panel, along the divider, where the key sits
