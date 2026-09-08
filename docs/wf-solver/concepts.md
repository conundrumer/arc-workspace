# Concepts

Keywords index the solvers by concepts that a grep over the code cannot find.

## Setup

The structure a hypothesis depends on: what the input is and how it decomposes.

- `tile-arrangement` — output arranges transformed copies of the input
- `overlay` — panels stack on one frame
- `scale` — content corresponds across a size change
- `decompose` — a separator or division cuts the grid into tiles
- `crop` — output is a subregion of the input
- `wallpaper` — a periodic pattern covers a region
- `symmetry` — the model depends on a symmetry of the grid
- `lines` — the model depends on per-line or per-slice structure
- `objects` — the model depends on connected components
- `markers` — designated cells point: they fix a place, direction, extent, or choice for content other than themselves; a mark may be consumed, and its color may extend along what it designates
- `grow` — the output frame extends the input frame
- `permutation` — elements reorder by a fixed permutation

## Prior

The transformation hypothesis: which prior the task teaches.

- `lookup` — stored data supplies the output: its content, or where content is read or placed
- `d4` — a D4 transform applies to content
- `walk` — stepwise propagation; each step depends on the path or content so far
- `cast` — content extends from a source along a line
- `span` — the model depends on an extent delimited by marks
- `enclose` — cells act by whether they reach the grid edge
- `mapping` — a color-to-color relation recolors cells
- `count` — a count determines output content or extent
- `rank` — an order or rank determines placement or color
- `repair` — damaged cells restore from symmetric counterparts
- `classify` — the input maps to a class; the output renders the class
- `induce` — the input demonstrates a rule that varies per input; the program validates it against the demonstration and applies it beyond it
- `move` — content translates, stacks, or shears within the frame
- `pack` — pieces jointly fill a region exactly
- `stamp` — a footprint stamps at qualifying positions
- `border` — cells act by which side of a border or outline they lie on, or are the drawn outline
- `select` — output keeps a distinguished part of the input
- `parity` — the model depends on even/odd position alternation
- `cross` — cells where designated lines cross act
- `merge` — like-valued items fuse under a task-given nearness into one unit; the output treats the unit as one thing

## Shape

A composition property of the task. It holds across the file's cases and is recorded for corpus-level analysis.

- `latent-canvas` — the program constructs a canvas neither grid fully shows, and the output is determined by that canvas. A canvas is a frame of cells that holds the whole scene in one state.
- `percept-shadow` — the pairs match content by a resemblance no exact map realizes, and the encoded hypothesis is a strictly weaker consequence of it. The tag applies if and only if a pair breaks the resemblance's exact form while its match still holds, and a configuration exists that the encoded hypothesis accepts and the resemblance rejects. The resemblance is read at the weakest form the pairs exhibit that rejects that configuration.
