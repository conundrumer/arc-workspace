# Concepts

Controlled vocabulary for solver `// concept:` lines.

The concept line is a reference for agents. Sessions use their own judgment to pick and revise terms for future agents. They do not ask the user to approve term choices.

A term names a model claim; the mechanism named in its gloss is one instance of that claim. If grep over the body could derive a term, that term is disqualified: primitive names, comp names, and Consts slot names are not concepts. When no term fits, the session broadens a gloss or adds a term here, and reports the change.

## Setup

The structure a claim depends on: what the input is and how it decomposes.

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

The transformation claim: which prior the task teaches.

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
- `induce` — the input demonstrates a rule that varies per input; the body validates it against the demonstration and applies it beyond it
- `move` — content translates, stacks, or shears within the frame
- `pack` — pieces jointly fill a region exactly
- `stamp` — a footprint stamps at qualifying positions
- `border` — cells act by which side of a border or outline they lie on, or are the drawn outline
- `select` — output keeps a distinguished part of the input
- `parity` — the model depends on even/odd position alternation
- `cross` — cells where designated lines cross act
- `merge` — like-valued items fuse under a task-given nearness into one unit; the output treats the unit as one thing
