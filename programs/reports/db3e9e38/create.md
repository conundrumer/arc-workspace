# db3e9e38

## Departures
- `Params` has a parameter that the concept file does not list, `run(1)`, which is the number of columns in each run of one color. The parity of a column's distance is read through `stride(K, W, W, _, _)`. This rests on the literal ban: the period of the alternation must come from Params. The precedent is d406998b (`mark_run`, `keep_run`) and 30f42897 (`stride(T, N, N, _, _)`).
- The staircase excludes the line's own cells (`!lines.label($U(), Q, X)` in `stair`), so keep-rest keeps them. This is needed for `$StoredEvenColor` to give the `witnesses.json` output on `recolored-line`, where the line keeps 3 and the even columns take 7. The first draft painted the line with the stored color, which was an error in the solver. For the concept the change has no effect, because the line's color at d = 0 is its input color.
- The solver has a `@derive RarestColor: variant derived` branch on `even_color` (with `@relaxed hanging-line`). `analyze.md` does not give this branch. It was added because `derive` reports that the derivation fits, and its witness `even_color=RarestColor` (train0 with 7 and 1 swapped) is in the witness file.
- The witness file has a witness that `witnesses.json` does not have, `two-color-line`. On it, a line is 7 with a 3 at its far end. `$LineColor` is undefined there because two even colors conflict. `even_color=RarestColor` paints the even columns 3, and the stored `even_color` paints them 7. It was built because `audit` reported that no run separated `$StoredEvenColor & even_color=RarestColor` from `$LineColor`, and that no run showed it defined and differing. With the witness, the case meets Subsumption and stays.

## Judgments
- `$EdgeFromLine` takes as its anchor each edge that one end of the line touches, with the line straight along that edge's axis. It is undefined where two such edges exist (a line that spans the grid) or none exists. A line that lies along the side edge (for example in col 0) is not undefined, which differs from the literal text of `analyze.md` ("touches no edge or two edges"). This rests on the concept, where the line hangs from the edge that is perpendicular to it.
- `$EdgeFromLine` takes the concept extent (`extent_of($EdgeFromLine(), $LineRows())`), because `stair-extent` stands under the concept branch of `anchor-edge` alone.
- Plausibility of `two-color-line`: `foreign`, because the generator draws each line in one color. Its verdict is `any`: on such an input, no reading of the concept fixes which color the even columns take.
- Plausibility and verdict of the `even_color=RarestColor` derive branch: `variant derived`. On its witness the line is 1, and the rarest color gives the concept's output. That witness breaks `hanging-line` (line color 7).
- The `case section` hints on `hang`, `spine` and `params.anchor_edge` are false positives, and each has `@ignore`. Each of those clauses derives facts only at its own branch's constructor in the `Anchor` or `Extent` column.
- The `head-repeat` hint on `extent_of` has `@ignore`. The stored edge's extent is its own field, so the relation states E in two columns by design.
- `determination-plan`: only `run` needed a determination relation, because its proposer (DivisorRatio) derives it from a fact the concept does not use. `Determine.run` gives the width of the input line, which is the lesser extent of the ink's box, the same in every train input. `background` (DominantColor), `stripe_color` (AnyOutNewColor) and `even_color` (RarestColor) are each derived from the fact the concept names. `anchor_edge` and `stripe_of_line` are covered by enumeration.
- `deletions`: 33 deletions change nothing on the pairs. Each is definedness structure (one line, straightness, edge clashes) or a distinction between branches that only the witnesses exercise, so all stay.
- Only witnessed cases run (9 of 96 combinations). The 96 combinations are 4 anchor/extent values × 2 × 2 × 2 Choice values × 3 values of the derive points on `background` and `even_color`.

## Unsettled
- `$AbsoluteParity` (`parity-origin`) has no constructor. `analyze.md` gives it no witness, and it fails Fit at train0 or train1 under each phase.
- `stripe_color=OutNewColor`, `AnyOutNewColor`, `DominantColor`, `RarestColor`, `SharedColor` and `background=RarestColor`, `SharedColor` fail Fit, as `analyze.md` states. `derive` did not list them, so the solver has no `@ignore: derive` line for them.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
