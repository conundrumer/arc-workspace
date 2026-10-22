# b775ac94

## Departures
- The header has no `@scene marker-colors`: no `@claim` or `@relaxed` line denotes it, no rule text depends on it, and no branch replaces it (Style, Header).
- `mirror-copy` adds "or where an object's markers lie in no key block" to where it is undefined: the Analyze probe's concept is undefined where no key block holds the markers. The `background=DominantColor` witness needs this, since with background 0 the field joins the whole grid into one object whose markers lie in no block.

## Judgments
- Concept parse: the shape's color is the commonest color of its 8-connected object (`Mode`), as `check_concept.py` and `probe.py` read it. The markers are the object's other cells. The key block is the 2×2 block that the shape cell at a corner of the shape's bounding box reaches toward that corner, and it holds every marker. So the Not-formed reading "markers as the object's minority-color cells" is the concept's own parse.
- The copy's transform is the D4 element that keeps each axis and takes the key cell's block corner to the marker's (`quadrant_op`, with `swaps_axes` as the defect relation). This gives the reflection across one center line for a side marker, and the half turn for the diagonal marker. It is applied in the key block's frame through `relative`, `apply`, `compose`, as in 2c181942 and 4c416de3.
- `$BlockMarkers` is added under Develop step 3, from the Not-formed reading "markers as the key block's other cells". It fits every pair, and its claim has a relational form. It differs from the concept only where `key-block` fails.
- Witness `stray-cell` (built): a cell of a third color touches the shape outside the key block. `$ColorMarkers` is undefined, and `$BlockMarkers` keeps the cell and draws the copies. Plausibility `borderline`: it breaks `key-block`, and the generator would produce it only as stray noise. Verdict `$BlockMarkers`: where the generator added such a cell, the block still shows the copies the task teaches.
- `quadrant_op=stored` is the `@store` line on `quadrant_op`, `variant stored`, as the Analyze report gives it, with its witness `quadrant_op=stored`. `store` lists no finding on `quadrant_op`, and the line stands because the Analyze report gives the branch a witness.
- `@derive DominantColor` on `background`: `variant derived`, `@relaxed shapes`, as the Analyze report gives it.
- The single-quadrant ambiguity of one side marker (two 2×2 blocks hold it) does not change the output: both blocks give the same reflection line. The concept picks the block toward the shape's bounding-box corner.
- Deletions: `neighbor` in `block.cell`, `unread`, `stray`, `block_other.c`, `inside(M, B)`, the background test in the `$KeepObject` disjunction and `in(P, _)` in `$CopyOver` stay, because the pairs never instantiate what they guard (a 2×2 block, undefinedness, several corner blocks, off-grid copies). The `key.p` column and the `impl_choice` atoms of the two case clauses are removed, because `copy` grounds the case.
- Lint hints (`common-subexpr` twice) were resolved by factoring `corner_cell` and `block_other`.
- `determination-plan` lists no actions (`background` is covered by `DominantColor exact`), so the solver has no `Determine` comp. `sweep` reports only the stored value.

## Open
- Shape color tie: where a marker color ties with the shape's color in one object, `Mode` gives two shape colors and the concept is not undefined, while `probe.py` is. A witness with a two-cell shape and two markers of one color would settle whether the concept needs a tie test.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-428_task_b775ac94_create.md
