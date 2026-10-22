# af24b4cc

## Departures
- The branches `tile_size=stored` and `tile_count=stored` are the constructors `$StoredTileSize` and `$StoredTileCount`, and the witness file names them so: the program derives no tile size or count, so neither is a `@store` branch, and a constructor of a branch named in another form takes a name of its own. (create)
- The witnesses `tile_size=stored`, `tile_count=stored` and `out_dims=stored` are `wide-blocks`, `three-block-rows` and `two-block-columns`: a `@witness` id must be a slug. (create)
- `out_dims=stored` is the `@store extent` branch `canvas.extent=stored`. On `two-block-columns` and on train 0 turned a quarter turn, it gives a frame of the stored 4 by 5 extent with every cell bg, where the Analyze file gives undefined: the stored extent's cells are in another frame than the picture's, so no block lands in them and the bg fallback fills them. (create)
- `$Components` places a piece, toward each of the four edges, at the rank of its distance to that edge, with no corner. The Analyze reading ranks the top row and the left column. The task distinguishes no corner, and a top-left rank is an orientation the program would choose by itself ([Orientation](docs/handbook/principles.md#orientation)). The generator lays the blocks out in aligned rows and columns, so no variant task narrows the four edges, and the program enumerates every edge ("Every value"). So `$Components` and `$DiagonalJoin` are undefined on `sparse-block` and `split-block`, where the Analyze file gives grids, and `split-block` is not a witness of `$DiagonalJoin`. (create)

## Judgments
- Reverted the create departure "one parameter, `tile_line`, gives the width of the lattice lines along the edges and between the tiles". The stored lattices now read `tile_edge` (the edge lines, 1) and `tile_gap` (the lines between tiles, 1). Reason: the Analyze report judges `wide-border` (a 2-wide border with 1-wide lines between the blocks) `variant`. So a variant task has an edge width other than its gap width, and by [Stored or derived](docs/handbook/principles.md#stored-or-derived) (Redundant value), the edge width is not derived data of the gap width.
- `@derive` branches after the split, each held with plausibility `variant` and verdict `concept`:
    - `tile_edge=SepThickness`: built, lines 2 wide everywhere around three rows and two columns of 3 by 3 blocks. The tiles straddle the dividers. Relaxed: block-grid, block-size, block-layout.
    - `tile_edge=TileDim`: written by `derive` on the `wide-border` input. I rewrote its separates text. Relaxed: block-grid.
    - `tile_gap=SepThickness`: built, lines 2 wide everywhere around two rows and two columns of 3 by 3 blocks. Every output cell is 0. Relaxed: block-grid, block-size, block-layout.
    - `tile_gap=TileDim`: built, lines 4 wide everywhere around the 2 by 3 layout of 3 by 2 blocks. Relaxed: block-grid.
- `witness` reported three pairs that no run separated: `tile_gap=stored` against `tile_gap=TileDim`, and `tile_edge=SepThickness` and `tile_gap=SepThickness` each against the `TileDim` branch of its parameter. I built `large-two-color-blocks` to separate all three: the 2 by 3 layout of 10 by 8 blocks with 1-wide lines, where `TileDim` has no 1 among its widths. I judge it `variant`, verdict `concept`, relaxed block-size. It has no `@witness` line, since it is a further witness of the `TileDim` branches.
- Removed `tile_line=TileDim`, which is a duplicate of the `tile_edge=TileDim` witness that `derive` recorded. Removed `tile_line=SepThickness` and `large-blocks`, which were built for the `tile_line` branches. After the split their texts were wrong, and `witness` stays ok without them.
- `$StrictMajority` fails Subsumption and leaves: no input shows it defined and differing from the commonest color, because a color that holds more than half the cells is the commonest. `three-color-block` then separated nothing and left, and the `two-colors` scene left the header with it, since nothing denotes it. (create)
- `@derive` branches held: `bg=DominantColor` (Analyze witness, variant concept, relaxed block-size) and `margin=SepThickness` (built: lines 2 wide, block widths 2, 2 and 3 so that only 2 fits; variant concept, relaxed block-grid). (create)
- `@store` branches held: `canvas.extent` (train 0 turned a quarter turn; variant concept, relaxed block-size and block-layout), `inked_line` (built: the stored frame with blocks 1, 2 and 3 columns wide; variant concept, relaxed block-size), `lattice.divider` (built: the 3 by 5 blocks of `wide-blocks`; variant concept, relaxed block-size), `region.box` (built: the `wide-border` input; variant concept, relaxed block-grid). (create)
- `store` reports each other derived value it finds constant on one line as having no witness, and no `@store` line stands on them, so none is held as a branch.
- `@store` points dismissed under Equivalence: `canvas.cell` (the frame of `canvas.extent`), `lattice.part_of` and `tile` (on the stored frame they give the tiles `inked_line=stored` gives, and on another frame they name no input cell, so the case is undefined there as `inked_line=stored` is), `piece.node` and `piece8.node` (the stored pieces are the stored blocks, so the cases equal `$Dividers & inked_line=stored` with one more branch), `region.cell` (its bounding box is `region.box`). (create)
- Witnesses built for pairs `witness` reported, with my judgment where a `@witness` line records it: `offset-pieces` (borderline `$Components`, relaxed block-grid: two pieces of 3 above a piece of 5 that overlaps both of their columns, which a person reads as three pieces in a 2 by 3 picture), `corner-touch` (variant concept, relaxed no-bg-in-block), `diagonal-blocks` (borderline `$Cardinal`, relaxed block-grid: two blocks that touch only at a corner read as two blocks), and, with no `@witness` line, `far-pieces`, `eight-block-columns`, `uneven-margin` (`region.box` reassigned to margins 1, 2, 1, 1) and `irregular-lines` (`inked_line` reassigned to the input's lines). I judge `uneven-margin` borderline with verdict `region.box=stored`, and the others variant with verdict concept. (create)
- `$InputMargin & region.box=stored` stays: `uneven-margin` shows it differs from the stored margin at an assignment no uniform margin agrees with. (create)
- Not formed, kept so: the tiebreak for tied blocks has no reading to form; the stored border color apart from `bg` is a redundant value, which [Stored or derived](docs/handbook/principles.md#stored-or-derived) makes derived data; the output-reading derivations of `bg` and the `DimDiff`-style derivations of `margin` are not among those `derive` lists as fitting. (create)
- The divider lattice maps each run of lines between dividers to one picture line (`OrderFrame` over `DividerTiles` parts), so lines wider than 1 leave no empty output line, as the probe's runs do. The divider parse moved into `Parse`, which `Determine` shares. (create)
- The `case section` hints came from one unkeyed `IdentOf` over tile positions, which every lattice case read. Tagging the value with the parse (`Tile`) cleared them. (create)
- Deletions: the `!params.bg(Col)` of `$NonBgMode` stays, since no pair puts bg in a block; the `train(E)` atoms in `Determine` stay, since a value no example contradicts ranges over examples with outputs. The bound `axis_elem(A)` in `canvas.extent` stays, as the report says. (create, with this pass's run)
- Sweep: the single-row additions to `tile_size` and `tile_count` that also reproduce the pairs are not readings of a stored tile size or count, so the values stay as stored. `tile_edge` and `tile_gap` are unique at 1. (create, with this pass's run)
- Determination plan: no actions. `tile_edge` and `tile_gap` are covered by `SepThickness` on the examples.
- Keywords: `decompose scale rank objects`. (create)

## Open
- none

## Lib
- Rank placement: each member's box, toward each edge, at the rank of its distance to that edge among the members' distances, packed into one cell of a dense picture. Solver-local form: `piece_dist`, `rank = Ordinal<Ranking>` and `piece_slot = DirPack<Block>` in `programs/solvers/af24b4cc.dl`. Sites: `programs/solvers/19bb5feb.dl` (`rank = Ordinal<Dir>`, `place = DirPack<Ident>`), `programs/solvers/58f5dbd5.dl` (draft; `lane = Ordinal<Dir>`, `tile = DirPack<Color>`). (create)

## Fixes elsewhere
- none

## Tickets filed
- none
