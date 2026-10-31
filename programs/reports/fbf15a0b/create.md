# fbf15a0b

## Departures
- The witness file has no color-swapped witness for `background=DominantColor`. `derive` wrote one under the id `bg=DominantColor` while the parameter was misnamed `bg`. After the rename to `background`, the Analyze witness `background=DominantColor` is the branch's witness, and the swapped one duplicated it, so it left: [Witness](#witness) has each such duplicate removed.

## Judgments
- The concept branch constructors are `$Stored` (point `part-count`) and `$Exact` (point `uneven-cut`). The `Choice` is `[pc: PartCount, uc: UnevenCut]`. The run counts 7 witnessed cases. Every pair passes, lint is ok, and `witness` and `audit` are ok against both the witness file and `witnesses.json`.
- `marker_color=RarestColor` and `background=DominantColor` are `@derive` lines, with the plausibility and verdict that `analyze.md` gives (`borderline concept`). `store` found no stored value to add.
- `$MarkerSpacing` reads the step from a `Ray` cast between markers, using `stop`, the first blocked cell. A ray cast blocked by markers gives "the step to the next marker" without arithmetic.
- `$FloorPart` and `$CeilPart` find the part length with `stride(·, N, 0, K, _)`. K is the number of whole rounds of N lines in the extent for the floor. For the ceiling, K is the round that the far line falls in. These are counts of lines, so this is grounded, and the claim has a relational form.
- The output frame of `$FloorPart` and `$CeilPart` is a `Bbox` of the kept end part keyed by `[Choice, Dir]`. With markers at both ends, the two frames overlap, so the case is undefined there as the claim says.
- Determine: `background` is the commonest color of every input (`Mode`). `marker_color` is the rarest color of every input (`ArgExtremes` over `Mode.tally`). `part_count` is the count that every output extent cuts its input extent into (`tile_size`). The first `marker_color` determination used a vanished-color test, and that test reads inputs and outputs together. The determination-prediction hint flagged it, so the rarest-color form replaced it.
- deletions: `marker_ray.cell` was removed, because `stop` does not read the domain. Other atoms stay. `pair_axis(A)` in the ray's directions states that the spacing is along the pair's line. `dist(Q, D_far, 0)` names the far line, which a union over every Q would leave implicit. The universal tests in Determine state "every input", and these pairs never contradict them.
- `deletions` ran before the last two edits (the removal above and moving the `copy` declaration). The last pairs run and `witness` run came after those edits and passed.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
