# c3fa4749

## Departures
- The `$MouthOnBlockSide` rule line says the branch is undefined where two box pockets share a cell and give it different colors, and analyze.md says the branch is defined on every input: the encoded model gives such a cell two colors when the bounding boxes of two block regions overlap outside both regions. No witness shows it.
- The header has no `noise-field` scene line: Style admits a `@scene` line only where a claim, a `@relaxed` line or a branch refers to it, and nothing refers to `noise-field`. The `blocks` line says the blocks lie in a field of random colors.

## Judgments
- `dead-end-fills` takes the concept file's text, and the program states it. A rule that fills a block-region cell, or a sealed pocket past one, has no support: no pair changes a block-region cell, and train2 keeps its sealed pocket at (2,13) and (3,13).
- `$LeakyFills`, `$KeepBlockColored` and `$StoredPaint` fail Fit (analyze.md), and the two Not formed fill-color readings (the channel's inner-end color, the channel's commonest color) fail Fit at train0. None of them is a constructor.
- `min_block_cells` stays 10 and is not open: the sweep shows 5 to 23 fit every pair and give the same test outputs, and analyze.md judges that a reader of the concept takes no count from the task.
- No Determine comp: the plan lists `min_block_cells` as covered by enumeration over its type (`domain enumerable(31)`), and no clause can read the value from the evidence.
- `@derive ConstInDim` on `min_block_cells` is held as a branch, with witness `min_block_cells=ConstInDim`: a 16x16 grid with a 4x4 block at the top border, cut to a 14-cell region by a two-cell dead-end channel. The concept fills the channel with 9, and the derived branch takes the grid side, 16, as the least block size, finds no block, and keeps the input. Plausibility `ordinary`: a smaller grid with a smaller block breaks no scene claim. Verdict `concept`: the region is a solid block with a dead end.
- `store` reports no derived value to store.
- Deletions report, 7 deletions that change no pair: the `step_dir` atom and its `d` column, both `inside(P, B)` atoms, and the `box_pockets8` node rule, its negation and the `pocket` rule of `$MouthOnBlockSide & $Adjacency8`. All stay: the pairs have no pocket whose wall test depends on a diagonal neighbor, and no box pocket that reaches past its box, and the combination case `$MouthOnBlockSide & $Adjacency8` is not witnessed, so the pairs never run it.
- Lint required the `Choice` field `count` to be renamed (Souffle reserved word, now `mouths`) and the enumerators to be named for their field types. One long-clause finding was fixed by wrapping. No hint fired.
- Keywords `objects noise enclose flood`: blocks are connected regions told apart from the noise field by size, a dead end is a pocket closed off except at its mouth, and the mouth's color spreads through the pocket up to the block walls.

## Open
- Of the 16 cases (8 bases, each with the stored and the `ConstInDim` value of `min_block_cells`), only 5 are witnessed: the concept case and one case for each single branch. The combinations of two or more of `$MouthOnBlockSide`, `$Adjacency8`, `$WalledAnyMouth` and `min_block_cells=ConstInDim` are not run by any check. Witness inputs on which a combination gives an output that none of its parts gives would settle it. The witness report raised none.
- The `$MouthOnBlockSide` undefinedness at overlapping bounding boxes: a witness with two such block regions would settle it.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- 10-671_task_c3fa4749_create.md
