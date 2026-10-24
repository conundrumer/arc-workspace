# cf133acc

## Departures
- `$PostlessPoleUndefined` is not in the solver. Its constructor, the nested `postless-pole` type and the name are gone from the witness file. In `separates` of `gap-without-post`, "$PostlessPoleUndefined is undefined" is cut: the case fails Subsumption, because on every input where it is defined every pole line holds a post, so it gives `$PolesFromGaps`'s output there. analyze.md says the same, and the audit reported that no run shows it defined and differing from `$PolesFromGaps`.
- In the witness file, `background=DominantColor` is renamed `bg=DominantColor`, and the Analyze witness `background=DominantColor` (0 and 5 swapped) is replaced by the one `derive` recorded (0 and 1 swapped): the parameter is `bg`, and the `@derive` branch is named after it ([Witness file](docs/handbook/solver-file.md#witness-file)). The other witness-file difference is the name `$PostlessPoleUndefined` (see the line above). The only differences `witness --file programs/reports/cf133acc/witnesses.json` prints are these names, which now denote no case. No branch's output differs from the one witnesses.json gives.
- `impl_choice` leaves out every combination of `$PolesFromGaps` and `$OneSidedGap`. These fail Fit on every pair: once pole lines come from gaps, the background cell beside a post is a one-sided gap, so its line turns into a pole line (train0 cols 2, 4, 8, 10 fill). analyze.md lists `pole-lines` & `gap-shape` as a joint change.

## Judgments
- How `$PolesFromGaps` combines with `$GaplessBar`: only background gaps make pole lines. Gapless crossings count only inside those lines. Letting a gapless cell make a pole line would turn every bar cell's line into a pole line. analyze.md does not say which reading holds.
- Encoding: a single `Ray<Choice>` casts each source toward the far edge: each post foot, and each crossing with its bar color. The crossings block the cast, and each source's color fills the clear part of its cast (`@claim post-grows bar-color-climbs`). A pole line's foot is found by `same_dist` on an axis across the post side, with `perp_dir` deriving the bar axis from `post_side`, as analyze.md's Not formed item gives.
- `$PostSideFromInput` uses `Unanimous` to find the one edge that holds ink while its opposite edge holds none (`@claim posts`). No proposer derives a direction, so this branch is a constructor with its own clauses.
- `store` printed `ink_edge`, `lone_edge.item` and `lone_edge.value` under `$PostSideFromInput`. I wrote `@ignore: store` for all three. Storing any of them fixes the post side, so the case's model is equivalent to `$StoredSide`'s, and it fails Equivalence because it takes more non-concept branches.
- `derive` found `bg=DominantColor`. I wrote it as `@derive DominantColor: variant derived`, `@relaxed background`, following analyze.md's judgment of that branch's witness.
- Determination: `bg` has a `Determine` relation: the commonest color of every train input, through `Mode`. The plan still lists `post_side` (enumerable domain, pairs-exact `DIR_B`). No proposer derives it, so the plan's instruction, which covers values a proposer derives, asks for no relation. The sweep reports a single value for each parameter.
- Deletions: there are nine no-op deletions. I kept each because the pairs never exercise the structure it removes. `perp_dir` and `dist(F, D, 0)` pin the line and the foot. `side(_, S)` in `out` keeps `$PostSideFromInput` undefined where no edge qualifies. The `gap_cell` atom is what makes `$PolesFromGaps` select lines. The `$GaplessBar` rule and its `flanked` atom are that branch. `bg_missing` is the universal over train inputs.
- `$ColorFalls` gets no constructor because it fails Fit at train0, as analyze.md gives. `background=RarestColor` and `background=SharedColor` also fail Fit, and `derive` does not list them.
- Keywords `lines cast`: the rule acts line by line along the pole lines, and colors extend from each source along that line.

## Unsettled
- Of the 24 cases, only 6 are witnessed: concept, `$PolesFromGaps`, `$OneSidedGap`, `$GaplessBar`, `$PostSideFromInput`, `bg=DominantColor`. On every input run so far, each combination gives the output of one of its parts. A witness on which a combination differs from all of its parts would pin it.
- Whether `post_side` should get a `Determine` relation through an input fact, the edge whose opposite edge holds no ink, moved into `Parse` because `$PostSideFromInput` derives the same thing: a ruling on whether pairs-exact enumeration counts as determination would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
