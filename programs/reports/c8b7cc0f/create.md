# c8b7cc0f

## Departures
- `$OverflowUndefined` and its choice point `overflow` are not in the solver, and the witness file drops their names: `witness` found no run that shows `$OverflowUndefined` defined and differing from `$FillAll`, and on every input where it is defined its output is the concept's, so it fails Subsumption, as the Analyze report states.
- The `count-fits` scene line is not in the header: after `overflow` left, no `@claim` or `@relaxed` line denotes it.
- The `ten-dots` witness stays, with a new `separates` text: it still separates `$CountObjects` (one ring of dots, `4 0 0 / 0 0 0 / 0 0 0`) from the concept (all nine cells).
- `witness --file work/task/c8b7cc0f/witnesses.json` prints only that `$OverflowUndefined` denotes no case. Every other branch's output matches the Analyze file.

## Judgments
- Constructors: `FrameStored`, `DotGrid`, `BoxInterior` and `CountCells` are my names for the concept branches. `$FrameCommonest`, `$FrameOutline`, `$DotColorInside`, `$Enclosed` and `$CountObjects` keep the report's names. `background=DominantColor` is a `@derive DominantColor: borderline concept` line with `@relaxed scattered-dots`, and the Analyze witness of that id is the branch's witness.
- The branches that fail Fit in the report (`frame_color=DominantColor`, `RarestColor`, `SharedColor`, `$DotColorStored`, `$Adjacency8`, `$Snake`, `$Spiral`, `out_size=ConstOutDim`) have no witness, so they have no constructor. `store` printed no line to add.
- The concept is undefined only where the dot color clashes (two or more candidate colors). Where it finds no dot color, the count is 0 and the output is all `background`. `$DotColorInside` behaves the same way over the inside cells. Every case whose frame color is undefined emits nothing, because each count's `domain` needs a frame color.
- Deletions: `spot.p`, the `interior_cell` atom of `$DotColorInside`, `!dots.clash`, the `outline_defect` rules, the interior test of `outline.item`, and the `domain` rules and their `frame(Fr, _)` atoms change no pair. They stay because each one states a claim that the witnesses or the concept's undefined inputs exercise. The Determine `kept` defect and the `train(E)` scoping of `lost` stay to keep the universal over train pairs. I dropped the `train(E)` atom of `commonest.item` because `not_field` already scopes it.
- Determination: `background` comes from the commonest color of every train input, `frame_color` from the input color that every train pair loses, and `out_size` from the train outputs' extents. The plan lists `fill_corner` and `fill_primary_axis` only as enumerable and pairs-exact, and no proposer gives them, so neither has a relation. The sweep reports a single value for each parameter.
- Keywords `count bbox rank enclose objects`: `enclose` is for `$Enclosed`, `objects` is for `$CountObjects`, and `rank` is for the lexicographic fill order.
- The lint gave no hints. I saw no performance issue: each run takes a few seconds.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
