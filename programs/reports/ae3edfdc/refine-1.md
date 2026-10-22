# ae3edfdc

## Departures
- The solver adds the choice point `landing-gap`, which has the branch `$StoredGap` with parameter `gap` (0). In that branch a satellite stops `gap` empty cells short of the cell it rests against. Its witness `gap` is recorded at `gap` 1, with plausibility `variant` and verdict `$StoredGap`, `@reassigned gap` (create): Develop step 3 forms the Analyze report's Not formed item "Landing distance as a parameter". The branch fits every pair at `gap` 0 and has a relational form (`jump` by `gap`). At `gap` 1, which a variant task can give, it agrees with no assignment of the concept case, so it passes Equivalence and Subsumption. This departure holds: the run and the audit show these facts.
- `impl_choice` leaves out `$AnyColorSatellite & $EightDirections` and `$PairFromAlignment & $EightDirections` (create): a `witness --every-case` run shows that each dropped case fails Fit. `$PairFromAlignment & $EightDirections` and `$PairFromAlignment & $EightDirections & $Stack` fail at train 1, where the 1 and the 2 lie on one diagonal and so pair with each other. `$AnyColorSatellite & $EightDirections`, `& $Stack` and `& $NearestCenter` fail at train 2, where the 7 at (6,1) lies on a diagonal of the 2 and is pulled. This departure holds.
- The solver holds three `@store` branches that the Analyze report does not give, each with `ordinary concept` (create). Develop step 4 holds each of them, and the audit's `store` check is ok:
    - `partner=stored` under `$AnyColorSatellite`. Its stored value is (1, 3), (1, 7), (2, 3), (2, 7). Its witness is a grid with a single 4 in the row of the 2. That grid breaks no scene claim.
    - `off_line=stored` under `$PairFromAlignment`. Its witness is the `pair-by-alignment` input.
    - `repeated=stored` under `$PairFromAlignment`. Its witness is the `centers=RarestColor` input.
- `partner=stored` under `$PartnerColor` has `@ignore: store $PartnerColor` (create): under either pair source, the stored rows are the rows of `params.pair`. So these cases are equivalent to the `$StoredPair` cases that take the derived value, which take fewer non-concept branches, and they fail Equivalence. This departure holds.

## Judgments
- Reconcile: the solver passes every pair with 25 witnessed cases, and lint, hints and the determination check are clean. The audit (witness, dropped cases, derive, store, open values) is ok. The run against `work/task/ae3edfdc/witnesses.json` gives every branch the output the Analyze file gives, with no difference. `witness` reports no unseparated pair of cases and no unwitnessed case. `determination-plan` lists no actions. So no item of the create report is reverted.
- The `$Stack & $SlideBlocked` reading (the report's `Gravity` reading) is encoded with an anchor and a rank, not with the lib's `Gravity` (create). `Gravity` takes a cardinal `Dir`, and `$EightDirections & $Stack & $SlideBlocked` slides along diagonals. Each satellite's anchor is the obstacle nearest it on its path (`ArgExtremes` high), and its rank in the pile against that anchor (`Order`) gives its landing cell through `jump`.
- Every `@witness` line takes the plausibility and the verdict that the Analyze report gives. `@derive DominantColor: variant derived` (`@relaxed single-cells`) and `@derive RarestColor: ordinary concept` follow the report's witnesses of those branches (create).
- The witnesses that the create pass built (`partner=stored`, `off_line=stored`, `repeated=stored`) each give the concept case's output and break no scene claim, so each is `ordinary concept`. `gap` is `variant $StoredGap`: a variant task can stop the satellites short, and it would give that model's output (create).
- `satellite_line_choice` has `@ignore: case section`: the enumerator lists the two-field combinations that fit, and it stands with the enumerators (create).
- Sweep: `pair` has one single-row change that still gives every train output. That change is not an open value, because no reader of the concept takes a pairing other than 2 → 3, 1 → 7 (create).
- Determine: `pair` comes from the train examples. A non-background input cell that keeps its color in the output is a center, and the non-background output cells next to it carry its satellite color (create).
- Deletions: no deletion is made. Each of the 14 deletions that change no pair states a claim or a branch that the pairs do not exercise:
    - The `!params.background` tests in `line.mark` and `lone` state that only non-background cells cast lines and pair.
    - The `pile_base.d` column is needed at `gap` above 0, where satellites rest against one center from several sides.
    - The `off_line` rule and its negation state the alignment test of `$PairFromAlignment`. The witness `pair-by-alignment` shows it.
    - The `$Stack` obstacle rule, the `pile.before` rule and the `$KeepUnmatched` rule state branches that the train pairs do not exercise.
    - In `pile.before`, either `rest_on` atom alone is redundant, because `Order` ignores rows outside `elem`. Both stay, so that the clause states the pile's members without that reliance.
    - The `rest_on` atom in the `$Stack` `lands_at` keeps the anchor itself from landing. At `gap` above 0, the anchor would otherwise be painted at the pile's base.
    - `dir_elem(D)` in Determine states that the satellites sit next to the center on the four sides.
- Prune: the header and the comments serve the reader as they stand. Nothing is cut.
- Keywords `markers move lookup rank`: the centers fix where satellites go, the satellites move, the stored `pair` decides which colors meet, and `$Stack` and `$NearestCenter` read an order or an extremum (create).
- The report's other Not formed items, a fixed step count and centers that move or satellites that leave copies, are not formed: by the report, each fails Fit at train 0 (create).

## Open
- none

## Lib
- Stacking along a line in any of the eight directions (the `$Stack & $SlideBlocked` reading) (create): `Gravity` covers it on cardinal headings only. The solver-local form:
    - `obstacle` lists the cells in a satellite's path.
    - `stop` (`ArgExtremes<Path, Position>`) takes the obstacle nearest the satellite as its anchor.
    - `pile` (`Order<Pile, Position>`) ranks the anchor and the satellites that rest against it by distance from the center.
    - The satellite of rank N lands at `jump(F_base, D, N, X)`.
    - A similar pile ranking is in `a48eeaf7` (`$Stack`, a draft). No grep of approved solvers for this shape was made, so no lib operation is proposed.

## Fixes elsewhere
- none

## Tickets filed
- none
