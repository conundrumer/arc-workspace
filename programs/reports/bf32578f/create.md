# bf32578f

## Departures
- The solver adds the branch `$SpanAny` at `inside`, with the witness `goblet-neck`: Develop step 3 forms the Not formed item "a span along a diagonal axis". Of its interpretations, a span along some row, column or diagonal fits every pair. A check over the pairs showed this.
- The concept branches' constructors are `$Enclosed` at `inside` and `$StoredDir` at `mirror-dir`: the Analyze report names those branches `concept`.
- `bg=DominantColor` is a `@derive DominantColor: variant derived` line with `@relaxed one-shape`. It is not a constructor, because the branch derives `bg` by a built-in derivation.

## Judgments
- The other interpretations of the diagonal-span item fail Fit. A span along some diagonal fails at train2. A span along each diagonal, and a span along each of the four line families, fail at train0.
- `goblet-neck` is `ordinary`, with verdict `concept`. The shape is one open curve whose two ends lie in its column nearest R, so it breaks no scene claim. Its non-convex outline is of the same kind as `top-notch`, which the Analyze report rates `ordinary`. The cells beside the neck are outside the outline, so the concept leaves them `bg`.
- `curl-pocket` has no `@relaxed` line: the invariant it breaks, one run of inside per row and column, is no scene claim.
- No Determine comp. The plan lists `bg` (DominantColor exact) and `mirror_dir` (enumerable, pairs-exact). DominantColor reads the field color, which is the same fact the concept reads `bg` from. `mirror_dir` is fixed by enumeration over `Dir` against the train pairs. The input fact that would give it is the `$MirrorDirFromEnds` branch. This matches the solvers that carry `@derive DominantColor`.
- The mirror image is the shape reflected by `flip_of` of the mirror axis, within the shape's box doubled toward the mirror direction (`box_extent`, `edge_outset`, `compose`). This puts the line just past the edge with no arithmetic.
- `$MirrorDirFromEnds` states "one 8-neighbor" and "two ends" with no count. `threaded` holds for a cell with two distinct shape neighbors. `many_ends` holds for three distinct ends. `sides_tie` holds for two sides that each hold two ends.
- Undefinedness is one gate, `defined(M)`. That gate fails when the image leaves the grid (`room`), and when the non-`bg` cells hold other than one color (`Unanimous`, `one-shape`). When `$MirrorDirFromEnds` gives no direction, there is no `open_dir` fact, so that case is undefined.
- Deletions: 22 deletions change no pair's output, and the solver keeps each one. The pairs do not instantiate those structures. Two examples: the undefinedness gates, and `axis_of` in `image`, whose loss goes unseen because every train shape is symmetric top to bottom. Simplify dropped the unused column `image.p` and made `hue.item` read `shape`.
- No lint hint fired, and no step showed a performance issue.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
