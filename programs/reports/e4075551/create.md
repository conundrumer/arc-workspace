# e4075551

## Departures
- The `background=DominantColor` branch is a `@derive DominantColor` line on `background`, not a constructor. Its plausibility and verdict come from `analyze.md` (`borderline`, the derived branch), with `@relaxed five-dots`: this follows from the Write step, which gives no constructor to a branch that derives a parameter by a built-in derivation.
- In the witness file, `record --all` rewrote the groups. The concept's stored-background case is now `background=stored`, and each case that takes `$CenterByPlace` is listed under `$CenterByPlace`: this is the listed name form.

## Judgments
- The concept branch's constructor is `ByColor`, and the `Choice` has the one point `center identification`. No other branch of `analyze.md` fits, so no other branch gets a constructor.
- Side dots are found as the dot strictly nearer an edge than every other dot. That test uses a defect relation, `not_extreme`, with `nearer`. The box is `DirPack` over the side dots' edge distances: these are relational forms of `side-dots` and `inside`.
- The center and the background fill are drawn only where the box exists. This makes each case undefined on an input with no unique extreme dot on some side, such as the field-7 witness, as `witnesses.json` gives. The first run without this guard gave `$CenterByPlace` a total output equal to the input.
- Lint hint `negated-use` on `!extreme(P)`: it was applied. The relation `extreme` was removed, and `!side(_, P, _)` is read in its place.
- Lint hint `common-subexpr` on `not_cross`, and the `determine prediction` hint on `cross_color`: the determination of `cross_color` read inputs and outputs together. It was rewritten to read outputs alone, as the color next to the center cell in every train output, and both hints are gone.
- `center_color` determination: the train inputs share 0, 2 and 6, so "the color every input holds" kept 6 as well. The determination now keeps the color that fills exactly one cell of every train output.
- `deletions`: the guards `box.box($U(), _)` in `drawn` and in the background clause of `out` change no pair, because every pair has a box. They stay, because they give the undefined outputs the witnesses record. The determination defect rules and atoms (`not_background`, `not_center`, `not_cross`, `train(E)`) change no pair, because every train example agrees on each value. They stay, because they state the universal over the train examples. The redundant `!params.corner_axis(A)` in `frame` was removed.
- Not formed items of `analyze.md`: none states a model that fits, so no branch was added from them.
- `store` printed no line to add. `center[col]` equals the stored `center_color` on every input.

## Unsettled
- `corner_axis` has no determination relation. The plan lists it as `domain enumerable(2), pairs-exact: (AXIS_V)`, and the plan reached its cap of 3 runs: a determination relation that reads the corner cells' colors in the train outputs would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
