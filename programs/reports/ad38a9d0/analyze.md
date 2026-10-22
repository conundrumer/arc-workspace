# ad38a9d0

## Concept
- The concept case fits every pair, at each open value of `shape_sym`. Each test shape occurs in a train pair in the same orientation, so `shape_color` has no unseen key.
- `recolor-by-shape` has a relational form: 4-components of `fg`, each normalized to its bounding box and matched against stored keys. No approximation is needed.
- No witness has the verdict `other`.

## Choice points
- `piece-cells`
    - `concept`: pieces are the 4-components of `fg` cells (`field`)
        - `fg-source`
            - `concept`: `fg` stored as `6`
            - `fg=RarestColor`: replaces `field`. `fg` is derived as the input's rarest color. Undefined where colors tie for rarest, and where a piece has no key. Fits every pair. Witness `fg=RarestColor`: field and piece colors swapped (pieces of 7 on a field of 6). It breaks `field`. Plausibility `variant`, verdict `fg=RarestColor`. It breaks the invariant that every input is a field of 7 with pieces of 6.
            - `fg=DominantColor`: replaces `field`. `fg` is derived as the input's commonest color. Fails Fit at train0: the 7 field becomes one piece with no key.
            - `fg=SharedColor`: replaces `field`. `fg` is derived as each color present in the input. Fails Fit at train0: both 6 and 7 are read as `fg`, and the 7 field is a piece with no key.
    - `$NonBgCells`: replaces `field` and `recolor-by-shape`. Pieces are the 4-components of the cells other than `bg`, whatever their color, and each such cell takes its piece's color. Reads `bg` (now a rule parameter, `7`), `shape_color` and `shape_sym`. It does not read `fg`. Undefined where a piece has no key. Fits every pair. Witness `other-color-piece`: the test input with its plus drawn in 1. The concept leaves the plus 1, and this branch paints it 3. It breaks `field`. Plausibility `borderline`, verdict `$NonBgCells`. It breaks the invariant that every piece has color 6.
        - `piece-color-split`
            - `concept`: a piece may hold cells of several colors
            - `$PerColorPieces`: replaces `field`. Pieces are the 4-components within each color other than `bg`. Undefined where a piece has no key. Fits every pair. Witness `two-color-piece`: the test input with a vertical domino of 1 beside its vertical domino of 6. `$NonBgCells` reads one 2×2 piece with no key and is undefined. This branch paints both dominoes 9, and the concept paints only the 6 domino. It breaks `field`. Plausibility `borderline`, verdict `$PerColorPieces`. It breaks the invariant that every input holds the two colors 6 and 7 alone.
        - `bg-source`
            - `concept`: `bg` stored as `7`
            - `bg=DominantColor`: `bg` is derived as the input's commonest color. Undefined where colors tie for commonest, and where a piece has no key. Fits every pair. Witness `bg=DominantColor`: the same swapped input as `fg=RarestColor`. `$NonBgCells` reads the 6 field as a piece with no key and is undefined. This branch recolors the 7 pieces. It breaks `field`. Plausibility `variant`, verdict `bg=DominantColor`. It breaks the invariant that every input is a field of 7 with pieces of 6.
- `adjacency`
    - `concept`: 4-adjacency
    - `$Adjacency8`: replaces `field`. Pieces are 8-components. Fails Fit at train0: the L at (6,7), (6,8), (7,8) meets the 2×3 block at rows 7–8, cols 4–6 at a corner, (6,7)–(7,6), and the merged piece has no key.
- `shape-key`
    - `concept`: a piece's key is its cell set relative to its bounding box
    - `$SizeBoxKey`: replaces `known-shapes` and `recolor-by-shape`. A piece's key is its cell count with its bounding-box height and width, and `shape_color` is stored on those keys: (5,3,3) → 3, (3,3,1) → 2, (2,2,1) → 9, (3,2,2) → 4, (4,2,3) → 8, (6,2,3) → 5. Under `shape_sym` a rotation swaps height and width. Undefined where a piece's count and extents match no key. Fits every pair. Witness `t-tetromino`: the test input with a T-tetromino in place of its Z. The concept has no key for it and is undefined. This branch paints it 8 (4 cells, 2×3 box). It breaks `known-shapes`. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every piece is one of the six keyed shapes in its one orientation.
    - `$BoxKey`: replaces `known-shapes` and `recolor-by-shape`. A piece's key is its bounding-box height and width. Fails Fit at train0: the Z and the 2×3 block both have a 2×3 box and take 8 and 5.
    - `$SizeKey`: replaces `known-shapes` and `recolor-by-shape`. A piece's key is its cell count. Fails Fit at train0: the L and the line of 3 both have 3 cells and take 4 and 2.
- `unknown-piece`
    - `concept`: a piece with no key leaves the model undefined (`known-shapes`)
    - `$KeepUnknown`: drops `known-shapes` and replaces `recolor-by-shape`. A piece that matches no key keeps `fg`. Undefined only where keys of two colors match one piece under `shape_sym`, which the stored table does not do. Fits every pair. Witness `t-tetromino`: the concept is undefined, and this branch leaves the T-tetromino 6. Plausibility `borderline`, verdict `concept`.
- `piece-cells` & `adjacency`, `piece-cells` & `shape-key`, `piece-cells` & `unknown-piece`, `fg-source` & `adjacency`, `fg-source` & `shape-key`, `fg-source` & `unknown-piece`, `piece-color-split` & `bg-source`, `piece-color-split` & `adjacency`, `piece-color-split` & `shape-key`, `piece-color-split` & `unknown-piece`, `bg-source` & `adjacency`, `bg-source` & `shape-key`, `bg-source` & `unknown-piece`, `adjacency` & `shape-key`, `adjacency` & `unknown-piece`, `shape-key` & `unknown-piece`: the two branches' changes applied together
- `fg-source` & `piece-color-split`, `fg-source` & `bg-source`: no case takes a non-concept branch at both, as they stand under different branches of `piece-cells`

## Open parameters
- `shape_sym`: `SYM_1`, `SYM_C4`, `SYM_D4`. Each train and test shape has the orientation of its key, so the pairs do not separate them. An input with a key shape in another orientation (a horizontal domino, an S-tetromino) separates them. It is read by every branch except `$SizeKey`.

## Not formed
- `shape_color` derived: the colors 3, 2, 9, 4, 8, 5 follow from nothing in the input, and no proposer gives a shape-to-color table.
- Matching a key up to rotation or up to D4 as a branch of `shape-key`: those are values of `shape_sym` with the program unchanged, so they are open values, not branches.
- `shape_sym` values that hold reflections alone (`SYM_LR`, `SYM_TB`, `SYM_DG`, `SYM_AD`, `SYM_HT`, `SYM_BOX`, `SYM_X`): a reader of the concept would not take a matching that admits a mirror and not a rotation.
- `fg` derived by `ChangedColor`, `UnchangedColor`, `VanishedColor`, `OutNewColor`, `AnyOutNewColor` or `ChangedPairs`: these read the train outputs, which a `@derive` run on one input leaves empty, so they give no value that names the piece color.
- `fg` derived by `CountRankAsc` or `CountRankDesc`: they propose a color with its rank, and the rank-0 color of `CountRankAsc` is `fg=RarestColor`'s value on every two-color input.

## Tickets filed
- `10-86_task_ad38a9d0_analyze.md`
