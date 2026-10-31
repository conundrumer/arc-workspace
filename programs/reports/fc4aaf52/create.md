# fc4aaf52

## Departures
- `$MirrorCut` and the `cut-line` choice point are dropped. The `lopsided` witness is removed, and `$MirrorCut` is removed from the groups of the other witnesses: the case fails Subsumption. `$MirrorCut` is `$Middle` gated on the shape's mirror symmetry across the cut, so wherever it is defined, it gives the concept's output at every assignment. `witness` reported that no run shows it defined and differing. With that case gone, `lopsided` separates nothing.
- The `mirror-halves` scene line is left out of the header: after `lopsided` was removed, no `@claim`, `@relaxed` or rule text refers to it.
- The concept file's `slide_dir: DIR_R` is stored as `slide_sense: SENSE_CW`, and `slide_dir` is derived from it in Params through `turn` from `moved_half`: [Relative orientation](docs/handbook/style.md#params). The family fixes the slide perpendicular to `moved_half`, and it varies only the sense.
- The `slide-to-clear` rule text leaves out the concept file's closing clause "with equal unbroken cut rows that is the cut row's length": that clause describes the generator's likely encoding, and the rule is stated without it.
- The concept branch constructors take names of their own: `Clear` (slide-distance) and `Swap` (recolor). The `Slide` type is named `Distance`, because `Slide` is a lib component.

## Judgments
- No Determine comp is written. `determination-plan` lists `bg` (DominantColor exact), `moved_half` and `slide_sense` (enumerable, pairs-exact, one joint assignment of 8). The concept stores `bg` and derives it from no fact, and the two orientations are covered by enumeration. So a determination relation would only repeat the proposer and the enumeration.
- `bg=DominantColor` is held as `@derive DominantColor: borderline concept`, as `analyze.md` gives it. It breaks no scene claim.
- The layer branches order the shape's colors by their fewest steps from `bg` through touching colors (GraphDistance over the color adjacency), ranked by Order. They are undefined where two colors tie in that order. That condition stands in for `analyze.md`'s "the cells around a layer hold more than one color". On every witness the two conditions agree: in `gapped-cut-row` and `bg=DominantColor`, both colors touch `bg`.
- `slide-to-clear` is encoded through Extremes over the two cut rows (ArgExtremes high and low on the distance to the `slide_dir` edge). The move is the slide-axis component of the offset that takes the moved row's back-most cell one step past the other row's front-most cell. `$CellClear` takes the least forward move that is not a colliding move, with the candidates being one step, or one step past a colliding move. `$CutCount` takes the Tally of the moved cut row.
- An odd extent leaves the middle-row cells uncovered: they are in neither half, and the bg clause covers only `bg` cells and moved-half cells. So every case is undefined there, as the concept file states.
- Deletions: these atoms are kept because the pairs do not exercise them. In `collide` and `move($Clear())`, the `moved_half` and `opposite` atoms name which cut row is which. In `collide`, `nearer(S, V, ZERO)` keeps only forward moves. The `step_offset` disjunct and `farther` give the least clearing move. In the first `out` clause, `in(Q, _)` drops cells that land past the frame. In the bg clause, the `side(P, H)` disjunct keeps the odd-extent case undefined. In `layer.score`, `shape(_, Col)` keeps scores for elements only. These were simplified: the axis atoms in `side` (its readers bind the side) and `impl_choice` in the first `out` clause (`placed` and `recolor` bind the case).
- Every pairs run passes: train0, train1 and test0, 7 witnessed cases. The witness check is ok. The audit is ok. Against `witnesses.json`, each branch's output matches, and the only finding is the dropped `$MirrorCut` name.

## Unsettled
- `deletions` ran before the last two simplifications (the `side` axis atoms and `impl_choice` in the first `out` clause), and it was not run again. The pairs run and the witness check after those edits pass. A `deletions` run on the current file would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
