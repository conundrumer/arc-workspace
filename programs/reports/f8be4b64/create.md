# f8be4b64

## Departures
- `bg` is stored in Params under the marker of `$HollowTopAxisOnly`, `$HollowRingsPassable`, `$BackgroundBeamUnblocked` and `$StopAtAnyMark`. `analyze.md` says the program never reads it. Those branches need it: a hollow plus is a center whose color is `bg`, and `$StopAtAnyMark` stops at a non-`bg` cell. The concept case does not read it.
- The `@derive DominantColor: variant concept` line on `bg`, with `@relaxed background`, and its witness `bg=DominantColor` are added. They are not in the Analyze files. `derive` lists DominantColor as a fit for `bg`, and Develop step 4 holds every fitting derivation. The witness is `background-beam-blocked` with 0 recolored to 5. With `bg` stored, the hollow plus there reads as a plus whose center is 5. With `bg` derived, it is hollow, and under `$BackgroundBeamUnblocked` its column beam passes the arm at (8,1) and cuts the 6 row beam at (9,5). Plausibility `variant`: a color-swapped variant, which breaks `background` at the stored 0. Verdict `concept`: the concept reads no `bg`, and its output is the one the generator gives the swapped variant.
- Witness `hollow-row-mark` is added, with a `@witness hollow-row-mark: foreign $StopAtAnyMark` line, `@relaxed background`, under `$HollowTopAxisOnly`. `witness` reported that no run showed `$HollowBothAxes & $HollowRingsPassable` defined and differing from `$HollowTopAxisOnly & $HollowRingsPassable`. The two clauses differ, and the input separates them. That input is a hollow plus with a stray 7 on its row. Under the concept the background row beam paints over the 7. `$HollowTopAxisOnly` and `$StopAtAnyMark` keep it. The verdict follows the judgment on `stray-mark`, where a stray mark stops a beam.
- Concept-branch constructors take these names: `SameAxisClash`, `HollowBothAxes`, `HollowRingsBlock`, `BackgroundBeamBlocked` and `StopAtRingColor`. The witness file needed no rename, because no witness group named a concept branch apart from `concept`.

## Judgments
- The solver has 48 combinations of the five branched points, `[o, ha, hr, bb, bl]`, and DominantColor doubles each combination that reads `bg`, for 92 cases. All of them fit. The run witnesses 9 of them.
- `nearer_lit` (a self-join with `K2 < K`) fired the argmax hint. It is replaced by `ArgExtremes<CellAxis, Color>`.`low`. A tie in two colors gives two shown colors, so the case is undefined there, as `analyze.md` states.
- `$StopAtPlusRing` blocks at an arm of any other plus, `arm(Pc2, Q), Pc2 != Pc`, with no own-arm exclusion. That follows the branch text, "only an arm of another plus stops a beam". The two forms differ only where two pluses share an arm, which `separate-pluses` rules out. `deletions` marked the exclusion as unused.
- In `paint`, `!params.top_axis(A)` in the second disjunct was cut. A top-axis beam is painted by the first disjunct whenever it exists, so the guard changed nothing.
- `deletions` flags that are kept: `!ring(P)` in `center` states the `pluses` scene claim. The `hollow`, `passed` and `casts` structure belongs to the branches, and the pairs do not instantiate it. Each of those branches has a witness. In Determine, `ring_color(C)`, `dir_elem(D)`, `!bg(Cb)`, `ring_color(R)` and `same_line(A, Pa, P)` state the determination's claims.
- The `top_axis` determination reads a crossing of the lines of two filled centers of different colors, and keeps the axis whose center color shows there in the train output. It keeps only V. The determination plan listed it as a fit determined by enumeration. Its last plan run reports no actions.
- `deletions` ran twice. The first run came before the simplification edits that it prompted. The second run came after the last solver edit.
- The `store` check reports `beam.cell` as not checked (over 20000 rows on an input). That set is the frame's cells per key, which is not a candidate stored value.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
