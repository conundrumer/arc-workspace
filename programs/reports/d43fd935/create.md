# d43fd935

## Departures
- Added the branch `$Square` at the `block` point. The block is the cells of `block_color` when they fill a square of side `block_size`, a parameter stored as 2. Otherwise there is no block and the output is the input. The parameter is stored under the `$Square` marker. This rests on Develop step 3: the last Not formed item, "The block is the 2×2 square of `block_color`", states a model that fits every pair and has a relational form (Bbox of the block-colored cells, `box_extent` against the stored side, and a defect for a hole). `$Square` is not subsumed by `$ByColor`: on `l-block` it gives the input where `$ByColor` paints. Its `@witness l-block` is `borderline concept`, `@relaxed one-block`. It is the first `@witness` line of `l-block`, which `$Box` holds, so by the Style rule the nested `@relaxed` line stays under `$Box` alone.
- `$Square` brings two `@derive` branches on `block_size` that `derive` reports as fitting. Each has a witness I built:
    - `block_size=TileCount`: a 10×10 input with a 3×3 block. TileCount gives tile counts 1, 2, 3, 4, 5 and 10, so the block is a square and the dot casts to it. `$Square` gives the input. Judged `borderline derived`, `@relaxed one-block`: the 3×3 block breaks the scene's 2×2 size, and the generator would paint the line, as the concept and this branch do.
    - `block_size=TileDim`: a 9×9 input with the 2×2 block. TileDim gives sides 1, 3, 4 and 9, so it finds no block and gives the input, while the concept paints. Judged `ordinary concept`: the input breaks no scene claim.
- Witness file:
    - `record --all` rewrote every group into the solver's case names.
    - I rewrote the `separates` text of `background=DominantColor`, which named `$Diagonal`, a branch with no case. It now names `$Square` among the undefined cases.
    - I rewrote the `separates` text of `l-block` to state what `$Square` gives.
    - The two `block_size` witnesses are new.
- Concept-branch constructor names are my own: `Cells` (stopper), `Over` (obstacle), `Every` (casters), `ByColor` (block). No name in the witness file needed rewriting for them, because Analyze used `concept`.

## Judgments
- `$Diagonal` gets no constructor. `analyze.md` gives it no witness, and it fails Fit at train0: it paints (5,4) and (6,5) from the dot at (7,6).
- Not formed items 1 and 2 fail Fit. Item 3 is the concept's own model.
- Encoding:
    - Two `Ray<Stop>` instances, keyed by the stopper and block fields that vary their blocked set. `reach` is blocked by the stoppers alone; it is read by `$Over` and `$PaintToDot`. `obst` is also blocked by every ink cell; it is read by `$StopAtDot` and `$PaintToDot`.
    - A line includes its own dot, the `clear` row at k = 0. This makes the concept undefined where a far dot's line covers a near dot of another color, as `analyze.md` states.
    - Every ink cell is a mark, and `caster` filters the sources per `Casters` branch, so the Ray key does not take the casters field.
- Undefinedness: `$BlockByShape` is undefined when there is no multi-cell object or more than one. `located` gates the keep clause, and `two_blocks` empties the block. `$ByColor` and `$Square` stay defined with no block and give the input. That matches the `other-color-block` groups.
- Hint `common-subexpr` on the four Ray inputs, which repeated `stopper_choice(S), block_choice(Bk)`: resolved by the shared `stop_key` relation. Finding `named-complement` in `unsquare`: resolved by writing `!params.block_size(N)`. A later `common-subexpr` hint: resolved by merging the two `unsquare` tails into one disjunction.
- Deletions:
    - Dropped `impl_choice` from `paint`, because `caster` and `line` bind every field and the cases are every combination.
    - The other changes-nothing items are structures the pairs never instantiate, and each is needed by a branch or a witness: `located`, the `obst.blocked` rows for `$Box` corners, `!joined`, `!two_blocks`, `unsquare`.
    - `!block` in `caster` changes no output, since a block cell's line paints only itself. It stays, because the concept's casters are the non-background cells outside the block.
    - The determination items keep test inputs out, or tie `block_color` to the block's solidity.
- Determine:
    - `background` is the commonest color of every train input.
    - `block_color` is the color of a non-background cell beside a cell of its own color, in every train input.
    - `block_size` is the extent of the block-colored box on both axes, in every train input.
    - The sweep found each parameter unique, and the plan reports no actions.
- Witnessed cases: 10 of 120. These are the concept, the five Analyze branches, `$Square`, and the three `@derive` branches. No witness shows a combination case giving an output that its parts do not give. `witness` and `audit` report nothing open.
- Keywords: `cast` (lines from dots), `span` (the extent between a dot and the block), `objects` (block and dots as pieces; `$BlockByShape` uses components).

## Unsettled
- Whether `$BlockByShape` and `$SingletonsOnly` should count connectivity over any non-background color, as written, or within one color: a witness with a dot touching the block in another color would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
