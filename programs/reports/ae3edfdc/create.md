# ae3edfdc

## Departures
- The solver adds the choice point `landing-gap`, which has the branch `$StoredGap` with parameter `gap` (0). In that branch a satellite stops `gap` empty cells short of the cell it rests against. Its witness `gap` is recorded at `gap` 1, with plausibility `variant` and verdict `$StoredGap`, `@reassigned gap`: Develop step 3 forms the Analyze report's Not formed item "Landing distance as a parameter". The branch fits every pair at `gap` 0 and has a relational form (`jump` by `gap`). At `gap` 1 it agrees with no assignment of the concept case, so it passes Equivalence and Subsumption.
- `impl_choice` leaves out `$AnyColorSatellite & $EightDirections` and `$PairFromAlignment & $EightDirections`: the run shows these cases fail Fit at train 1, train 2 and test 0. All other combinations of the report's branches fit.
- The solver holds three `@store` branches that the Analyze report does not give, each with `ordinary concept`:
    - `partner=stored` under `$AnyColorSatellite`. Its stored value is (1, 3), (1, 7), (2, 3), (2, 7). The witness that `store` built (train 0 with 0 and 4 swapped) was replaced by a grid with a single 4 in the row of the 2. That grid breaks no scene claim, and it isolates the satellite-set difference without a field of another color.
    - `off_line=stored` under `$PairFromAlignment`. Its witness is the `pair-by-alignment` input.
    - `repeated=stored` under `$PairFromAlignment`. Its witness is the `centers=RarestColor` input.
- `partner=stored` under `$PartnerColor` has `@ignore: store $PartnerColor`: the stored rows are the rows of `params.pair`, so these cases are equivalent to the `$StoredPair` cases that take the derived value, which take fewer non-concept branches. They fail Equivalence.

## Judgments
- The `$Stack & $SlideBlocked` reading (the report's `Gravity` reading) is encoded with an anchor and a rank, not with the lib's `Gravity`. `Gravity` takes a cardinal `Dir`, and `$EightDirections & $Stack & $SlideBlocked` slides along diagonals. Each satellite's anchor is the obstacle nearest it on its path (`ArgExtremes` high), and its rank in the pile against that anchor (`Order`) gives its landing cell through `jump`. With `$PassOver` the only obstacle is the center. With `$SameCell & $SlideBlocked` every non-background cell in the path is an obstacle. With `$Stack & $SlideBlocked` every such cell is an obstacle, other than a satellite that the same center pulls.
- Every `@witness` line takes the plausibility and the verdict that the Analyze report gives. `@derive DominantColor: variant derived` (`@relaxed single-cells`) and `@derive RarestColor: ordinary concept` follow the report's witnesses of those branches.
- The witnesses I built (`partner=stored`, `off_line=stored`, `repeated=stored`): each gives the concept case's output and breaks no scene claim, so each is `ordinary concept`. `gap` is `variant $StoredGap`: a variant task can stop the satellites short, and it would give that model's output.
- `satellite_line_choice` has `@ignore: case section`: the enumerator lists the two-field combinations that fit, and it stands with the enumerators.
- Sweep: `pair` has one single-row change that still gives every train output. That change is not an open value, because no reader of the concept takes a pairing other than 2 → 3, 1 → 7. No value was added.
- Determine: `pair` comes from the train examples. A non-background input cell that keeps its color in the output is a center, and the non-background output cells next to it carry its satellite color.
- Deletions: I removed `!center` from the `$KeepUnmatched` clause, because a center is painted in its own color anyway. I also removed the unused center column of `lands_at` and of `pile_base`. I kept the other deletions the report lists:
    - The `!params.background` tests state the claims.
    - The `$SlideBlocked`, `$Stack`, `$KeepUnmatched` and `$PairFromAlignment` clauses state branches that the train pairs do not exercise.
    - The Determine atoms state the center that keeps its cell.
- Keywords `markers move lookup rank`: the centers fix where satellites go, the satellites move, the stored `pair` decides which colors meet, and `$Stack` and `$NearestCenter` read an order or an extremum.
- I did not form the report's other Not formed items, a fixed step count and centers that move or satellites that leave copies: by the report, each fails Fit at train 0.

## Open
- none

## Lib
- Stacking along a line in any of the eight directions (the `$Stack & $SlideBlocked` reading): `Gravity` covers it on cardinal headings only. The solver-local form:
    - `obstacle` lists the cells in a satellite's path.
    - `stop` (`ArgExtremes<Path, Position>`) takes the obstacle nearest the satellite as its anchor.
    - `pile` (`Order<Pile, Position>`) ranks the anchor and the satellites that rest against it by distance from the center.
    - The satellite of rank N lands at `jump(F_base, D, N, X)`.
    - A similar pile ranking is in `a48eeaf7` (`$Stack`, a draft). I made no grep of approved solvers for this shape, so I propose no lib operation.

## Fixes elsewhere
- none

## Tickets filed
- 10-103_task_ae3edfdc_create.md
