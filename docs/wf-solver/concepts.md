# Concepts

Controlled vocabulary for solver `// concept:` lines.

A term names a model claim. A term is disqualified if grep over the body could derive it: primitive names, comp names, and Consts slot names are not concepts. New terms enter like lib additions: reuse an existing term when it fits; add here when none does.

## Setup

The structure every candidate claim stands on: what the input is and how it decomposes. Cases of one file share these.

- `tile-arrangement` — output arranges transformed copies of the input
- `self-tiling` — the input tiled by itself; tile identity comes from input content
- `overlay` — panels stack on one frame
- `scale` — content corresponds across a size change
- `decompose` — a separator or division cuts the grid into tiles
- `crop` — output is a subregion of the input
- `wallpaper` — a periodic pattern covers a region
- `symmetry` — a symmetry of the grid carries the model
- `lines` — per-line or per-slice structure carries the model
- `objects` — connected components carry the model
- `markers` — designated marker cells drive the transformation
- `grow` — the output frame extends the input frame
- `permutation` — elements reorder by a fixed permutation

## Prior

The transformation claim: which prior the task teaches. Rival cases of one file typically differ here, one term per case.

- `lookup` — a stored table or grid supplies output content
- `d4` — a D4 transform applies to content
- `unfold` — reflection tiling seeded at an anchor
- `walk` — stepwise propagation; each step depends on the path or content so far
- `cast` — content extends from a source along a line
- `span` — an extent delimited by marks carries the model
- `enclose` — cells act by whether they reach the grid edge
- `mapping` — a color-to-color relation recolors cells
- `count` — a count determines output content or extent
- `rank` — an order or rank determines placement or color
- `repair` — damaged cells restore from symmetric counterparts
- `classify` — the input maps to a class; the output renders the class
- `move` — content translates, stacks, or shears within the frame
- `pack` — pieces jointly fill a region exactly
- `stamp` — a footprint stamps at qualifying positions
- `border` — cells act by which side of a border or outline they lie on
- `select` — output keeps a distinguished part of the input
- `fold` — per-cell combination of panel contributions
- `parity` — even/odd position alternation carries the model
- `cross` — cells where designated lines cross act
