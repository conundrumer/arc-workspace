+ index: headings

# Keywords
- Keywords index the solvers for a reader who has the headers and not the code.
- A keyword names a task concept or a composition property of the program.
- A keyword is admitted when a variant task can carry the concept it names, and no listed keyword names that concept.
    - A concept narrower than a listed keyword's is admitted when it names a different parse or rule.
- The mechanism its gloss names is one instance of that concept, not the keyword's boundary.

## Setup
- The structure a concept depends on: what the input is and how it decomposes.
- `tile-arrangement` — output arranges transformed copies of the input, or of a piece of it
- `overlay` — content stacks on one frame; panels of a decomposition are one kind of content
- `scale` — content corresponds across a size change
- `decompose` — a separator or division cuts the grid into tiles
- `crop` — a region of the input gives the output its frame or its content, or is the frame the model works in
- `wallpaper` — a periodic pattern covers a region, along one axis or both
- `symmetry` — the model depends on a symmetry of the grid or of a piece of it
- `lines` — the model depends on per-line or per-slice structure
- `objects` — the model depends on discrete pieces of the grid; connected components are one way they are found
- `color-class` — the cells of one color form one unit wherever they lie
- `markers` — designated cells point: they fix a place, direction, extent, or choice, for other content or for the mark itself; a mark may be consumed, and its color may extend along what it designates
- `noise` — stray cells sit among the figure; the model tells them apart, and removes, marks, or ignores them
- `rings` — concentric rings around the frame or a center are the structure, and a cell acts by its ring
- `perimeter` — the grid's border ring is the structure, and content acts by its place along that ring
- `chain` — cells link end to end into one sequence, and the model reads its order along that sequence
- `grow` — the output frame extends the input frame
- `permutation` — elements reorder by a fixed permutation

## Transformation
- The concept the task teaches.
- `lookup` — stored data supplies the output: its content, or where content is read or placed
- `d4` — a D4 transform applies to content
- `congruent` — pieces are identified up to a D4 transform, and the output acts on that identity
- `walk` — stepwise propagation; each step depends on the path or content so far
- `flood` — content spreads from a source through a region until something stops it
- `route` — a fewest-hop route between designated ends through a network of touching pieces
- `cast` — content extends from a source along a line
- `span` — the model depends on an extent delimited by marks
- `bbox` — a unit's bounding box acts as a region: its cells fill, or content places by it
- `depth` — cells act by their distance to the nearest edge of their region
- `enclose` — cells or objects act by whether they are closed off: from the grid edge, from an opening in their wall, or by their neighbors
- `occlude` — content lies in layers, and what shows of a covered thing is a piece of it; the model recovers the hidden part or reads the order of drawing
- `continue` — content leaving one side of a boundary continues on the facing side; the match links the two sides
- `mapping` — a color-to-color relation recolors cells or supplies a fill color
- `count` — a count determines output content, extent, or placement; an extremum over counts is `rank`
- `rank` — an order, a rank, or an extremum determines placement, color, or which piece acts
- `pairwise` — the output holds one entry per pair of the input's items, and the entry says how that pair stands
- `repair` — damaged cells are restored from what the rest of the grid implies; a symmetry or a period gives one set of counterparts
- `classify` — the input, or a part of it, maps to a class; the output renders the class
- `induce` — the input pairs content with the content a rule maps it to, and that rule varies per input; the program reads the rule from those pairs, validates it against them, and applies it beyond them
- `move` — content translates, stacks, or shears within the frame
- `pack` — pieces jointly fill a region exactly
- `stamp` — a footprint stamps at qualifying positions
- `border` — cells act by which side of a border or outline they lie on, or are the drawn outline
- `select` — output keeps or drops a distinguished part of the input
- `parity` — the model depends on even/odd alternation, along a position or along an order
- `cross` — cells where designated lines cross act
- `merge` — like-valued pieces within a task-given proximity fuse into one unit; the output treats the unit as one thing
- `match` — pieces found in the input pair off by a shared property, and the output acts on the pairs; matching against stored data is `lookup`

## Shape
- `latent-canvas` — the program constructs a canvas neither grid fully shows, and the output is determined by that canvas. A canvas is a frame of cells that contains the whole picture in one state.
