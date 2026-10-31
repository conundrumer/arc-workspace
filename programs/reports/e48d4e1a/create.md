# e48d4e1a

## Departures
- `$RefusePastEdge` is not in the solver, and its group is removed from the `shift-past-edge` witness: it fails Subsumption. Wherever it is defined it gives the concept's output, and `witness` reported that no run shows it defined and differing from `$DropPastEdge`. `analyze.md` predicts the same result.
- `$TranslateCross` is not formed: it fails Fit at train0, and `analyze.md` gives it no witness.
- `mark_color=VanishedColor`, `mark_color=SharedColor` and `bg=SharedColor` are not formed: they fail Fit at train0, and `derive` did not list them.

## Judgments
- The concept constructors are named `FixedCorner` (shift-direction), `CountAll` (mark-count) and `DropPastEdge` (off-frame). The `Choice` record is `[h: Heading, c: Count, e: Edge]`, with all 8 combinations as cases. 6 of those cases are witnessed.
- `mark_color=RarestColor` and `bg=DominantColor` are `@derive` lines with `variant derived`. They relax `mark-stack` and `full-cross`, as `analyze.md` gives. Their witness-file names were already in the `<param>=<Proposer>` form.
- `store` printed no line to add. `heading` was already stored as `shift_dir`, and `shift` and `wrap.step` have no witness.
- The cross lines come from a `Parse<Key>` comp, a `Unanimous` over each line's colors keyed by `[key, axis, line]`. The program and the determination share it, so `Determine` reads the moved lines in `ex_in` and `ex_out` through the same clauses.
- `shift_dir` determination: the first form kept each corner that no line moved away from. It got the "determine prediction" hint because it read inputs and outputs together in a guess-and-test. I rewrote it to read the value directly: the corner of the two edges toward which an example's input cross lines move in its output.
- `$WrapShift` is a walk around a cycle of lines (`CycleWalk<Dir, Position>`) with a wrap edge from the line on edge D to the line on the opposite edge. The program uses no modulo.
- `$RefusePastEdge` left, so `impl_choice`, `heading_choice` and `edge_choice` are gone: every combination of fields is a case, and the `Choice` is grounded by `shift` and `moved`. `count_choice` remains, because it feeds `marks.domain`, which gives a 0 count when there are no marks.
- `deletions` judgments: the atoms and rules it lists are either structures that the pairs never instantiate (a full `bg` line, zero marks, marks off the edge, a wrap past the edge, a color that some output keeps, a non-dominant `bg`) or atoms implied by another atom (`shift.a` by `dir_of`, `run.seed`'s corner when all marks are on one run, `Determine.mark_edge`'s `dist(P, D, 0)` by `!off_edge(D)`). All stay as they are. The last of these is a needless atom that a later pass can drop.
- Lint hints: the single-consumer hint on `jumped` and on `Determine.moved` was resolved by inlining both relations.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
