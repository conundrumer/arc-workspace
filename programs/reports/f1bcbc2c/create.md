# f1bcbc2c

## Departures
- The header has no `@scene outside` line: no `@claim`, `@relaxed` or rule text denotes it, so Style's header rule leaves it out.
- The concept branch of `plug-test` is named `$PlugTestByWalls`, and the concept branch of `source` is named `$SourceEdge`. The witness file needed no rewrite for these names, because it names the concept base as `concept`.

## Judgments
- Corridor parse: the corridor is the non-wall 4-component that borders two distinct wall components (`walls` and `regions` are `Components` instances). The walk is a `Reach<Choice>` over corridor cells minus each case's blocking plugs, seeded at the case's source cells.
- Undefinedness: each case's `out` is gated on `defined`. The concept is undefined where no corridor cell lies on the `source_edge` edge, `$SourceUpperEnd` where two openings tie for nearest (`ArgExtremes` low with a tie test), and `$FillLongerPart` where two parts tie for largest (`Mode` over part labels with a tie test).
- Base cases: the 6 combinations of `plug-test` × `source`, each with the `plug_color=RarestColor` `@derive` branch. The pairs run reports 5 witnessed cases. The rest take two rejected branches (verdict `concept`) and no witness separates them from the cases that take one of the two.
- `@derive RarestColor` on `plug_color` was added from `derive`, with the plausibility and verdict that analyze.md gives (`variant concept`). It has no `@relaxed`, because analyze.md says the witness breaks no scene claim.
- `fill_color=OutNewColor` gets no line: `derive` does not list it as fitting, and analyze.md gives it no witness.
- `store` reported `nearest.low` as the same on every input, with no witness and no line to add. analyze.md gives that value no witness, so no `@store` branch was held.
- Not formed, the "component whose cells all touch both walls" corridor parse: with 4-adjacency, which is the adjacency the concept's `touches` uses, the outer cell of each bend borders one wall alone (train0 (3,4)). So no component qualifies on train0, and the parse fails Fit. No branch was formed. The plug-component parse fails Fit at train3, as analyze.md states.
- Determination: `fill_color` is the color that the train outputs hold and no input does (AnyOutNewColor). `wall_color` is the input color that no train pair changes (UnchangedColor). The `determine prediction` hint on `wall_color` was kept with `@ignore`: that value is read from the evidence as the color each pair leaves in place. `plug_color` and `source_edge` are pairs-exact in the plan, and no proposer is named for them.
- `deletions` hits:
    - `dir_elem(D)` stays in `touches`, because it keeps 4-adjacency.
    - `corridor(P)` stays in `plug`, because the scene puts the plug in the corridor.
    - `dist(P, D, 0)` stays in `opening`, because it defines an opening.
    - The `bent`/`straight` clauses and the two tie tests stay. They state the branches' "exactly two collinear neighbors" test and their undefinedness, and no pair exercises them.
    - `defined(Ch)` was removed from the fill `out` clause, because `filled` implies it.
    - `lacks` was removed from the `fill_color` determination.
- `deletions` ran a second time, after the edits that its first run led to. A Determine-only lint fix followed that second run.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
