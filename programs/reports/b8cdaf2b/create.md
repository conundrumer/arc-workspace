# b8cdaf2b

## Departures
- The record's case names in `programs/witnesses/b8cdaf2b.wit.json` differ from the Analyze file's branch names (for example `$StoredSide & $ToEdge & $CapAnchor`, `$CapAnchor & background=stored`): `record --all` writes each group by the fewest names that cover its cases, and `witness --file work/task/b8cdaf2b/witnesses.json` reports no difference for any branch.
- Under `$CapAnchor`, a case that takes `$RayColorRarest` or `$RayColorBaseCenter` does not need the base-line cells under the cap to share one color, though the probe needs it for every case: those branches replace the inner color, so the cases that take them do not read it. No witness input separates the two readings.

## Judgments
- Concept branch constructors: `StoredSide`, `ToEdge`, `CapColor`, `CapAnchor`, `PaintOver`. The parameters keep the concept file's names (`background`, `base_side`), so the derive branch's name stays `background=DominantColor`.
- `Choice` crosses all five points, which gives 72 bases. With the `background=DominantColor` derive branch on the bases that read `background`, that gives 138 cases. The runner reports 11 of them as witnessed.
- Under `$CapAnchor`, the cap must be one run of one color (the `cap-row` scene: a run of the outer color). The anchor ends exist only then, as in the probe. The outer color, which `$RayLenFlank` reads, is that color.
- `$RayStopAtObstacle` has its own `Ray` instance. That instance has `blocked` as an input, and the instance the other obstacle readings share has no `blocked` input. So the two instances' versions differ in more than the case name.
- The ray casts from the anchor end itself, and the clause drops the end cell with `P != E`. With the mark on that end, a blocked first ray cell stops the `$RayStopAtObstacle` ray at once. A blocked mark would still cast.
- `store` printed `@store` lines to add for `open_edge`, `full_edge.item` and `full_edge.value` under `$BaseSideDerived`. Each stored reading gives one fixed base side, which is the model of `$StoredSide`. So `$BaseSideDerived` with that store branch is equivalent to the concept case and takes more non-concept branches, and it fails Equivalence. Each of them has an `@ignore: store` line.
- `store` printed no `@store` line to add for `ray.dir`, `stop_ray.dir` or `base_dir`: `base_dir` equals the stored `base_side`, and no witness separates the stored `dir` readings.
- `derive` lists only `DominantColor` for `background`, and none for `base_side`.
- Develop step 3: each item under the Analyze report's Not formed fails Fit at every pair, or replaces no claim a rule reads (`square-grid`), so no item adds a case.
- Determine: the sweep gives unique values (`background` 0, `base_side` DIR_B). `determination-plan` lists no actions, so the solver has no `Determine` comp.
- Deletions report, judged item by item:
    - I removed the `impl_choice` atom from the first `out` clause, because every combination of the fields is a case and the clause's other atoms bind every field.
    - I removed `color_count.domain`, because every color the input holds has members.
    - I removed the `inner` atom from the `$CapAnchor` `anchor_end` clause (see Departures).
    - The other reported deletions are guards that the pairs never exercise (split caps, a split middle run, unanimity of colors), or they are `$RayLenFlank` and obstacle structure, which the pairs do not separate from the concept. They stay.
- Lint, `witness` (with and without `--file`) and audit report no findings and no hints.
- Keywords `lines cast rank`: per-line base and cap structure, rays cast from the cap ends, and the rarest-color branch (an extremum over counts sets the color).

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
