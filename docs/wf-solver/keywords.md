# Keywords

Keywords index the solvers by concepts that a grep over the code cannot find.

A keyword names a task concept or a composition property of the program. The mechanism its gloss names is one instance of that concept, not the keyword's boundary.

## Setup

The structure a concept depends on: what the input is and how it decomposes.

- `tile-arrangement` — output arranges transformed copies of the input, or of a piece of it
- `overlay` — content stacks on one frame; panels of a decomposition are one kind of content
- `scale` — content corresponds across a size change
- `decompose` — a separator or division cuts the grid into tiles
- `crop` — a region of the input gives the output its frame or its content
- `wallpaper` — a periodic pattern covers a region, along one axis or both
- `symmetry` — the model depends on a symmetry of the grid or of a piece of it
- `lines` — the model depends on per-line or per-slice structure
- `objects` — the model depends on discrete pieces of the grid; connected components are one way they are found
- `markers` — designated cells point: they fix a place, direction, extent, or choice, for other content or for the mark itself; a mark may be consumed, and its color may extend along what it designates
- `grow` — the output frame extends the input frame
- `permutation` — elements reorder by a fixed permutation

## Transformation

The concept the task teaches.

- `lookup` — stored data supplies the output: its content, or where content is read or placed
- `d4` — a D4 transform applies to content
- `walk` — stepwise propagation; each step depends on the path or content so far
- `cast` — content extends from a source along a line
- `span` — the model depends on an extent delimited by marks
- `enclose` — cells or objects act by whether they are closed off from the grid edge
- `mapping` — a color-to-color relation recolors cells
- `count` — a count determines output content or extent, or which item acts
- `rank` — an order or rank determines placement, color, or which item acts
- `repair` — damaged cells are restored from their counterparts elsewhere in the grid; a symmetry gives one set of counterparts
- `classify` — the input, or a part of it, maps to a class; the output renders the class
- `induce` — the input pairs content with the content a rule maps it to, and that rule varies per input; the program reads the rule from those pairs, validates it against them, and applies it beyond them
- `move` — content translates, stacks, or shears within the frame
- `pack` — items jointly fill a region exactly
- `stamp` — a footprint stamps at qualifying positions
- `border` — cells act by which side of a border or outline they lie on, or are the drawn outline
- `select` — output keeps a distinguished part of the input
- `parity` — the model depends on even/odd alternation, along a position or along an order
- `cross` — cells where designated lines cross act
- `merge` — like-valued items within a task-given proximity fuse into one unit; the output treats the unit as one thing
- `match` — items found in the input pair off by a shared property, and the output acts on the pairs; matching against stored data is `lookup`

## Shape

- `latent-canvas` — the program constructs a canvas neither grid fully shows, and the output is determined by that canvas. A canvas is a frame of cells that contains the whole scene in one state.
- `approximation` — the program runs a weaker rule in place of a concept rule it cannot state. principles.md gives the conditions under which the tag applies.
