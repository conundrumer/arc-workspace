# e12f9a14

## Departures
- `$ChainedMeetings` is not formed. Its bent paths start at the meetings the `Take` walk gives, and a cast that reads the walk's relations breaks the Recursion rule; a bound on the bends it walks would be a workaround, and a non-concept branch takes none.
- `core_side` has the branch `@derive TileCount` (variant, verdict `derived`, `@relaxed boxes`). `oblong-core` is a further witness of it (create.md). The audit's derive check is ok.
- The concept branches are named `$OverBox` (ray-block) and `$StoredSide` (core-size) (create.md).

## Judgments
- Override applied. The override says: "the lib is expressive enough for this task's concept. A concept fault that rests on the program needing arithmetic, recursion, or an optimization shows a claim that states an implementation, and not a limit of the lib." It also says: "State `meeting` as the relation the task shows, encode it with lib relations, and remove the `@approximated:` line where the encoding runs the claim itself." `meeting` is now a `Take` walk with one key per ray. Each ray walks the stops of its path in order: each crossing, by the cell before it, and then the path's last cell. At a crossing it meets the other ray when the other ray's walk reaches that crossing too. It walks past a crossing when the other ray has left that crossing's path: that ray met a ray earlier on the path. The `@approximated:` line, its `ghost-then-meet` witness line and the concept fault are removed. The concept case gives the judged output of `ghost-then-meet`.
- `ghost-then-meet` is removed from the witness file. With the approximation gone, every witnessed case gives one grid on it, so it separates nothing.
- A walk that reaches a crossing and can neither meet nor walk past it makes its case undefined (`stuck`). That happens where crossings depend on one another in a cycle, such as three rays that each cross the next one's crossing first. The rule decides none of those crossings. A grid with such a three-ray cycle gives no output in every case. The pairs have no such cycle.
- The crossing test is one geometric relation, `steps_cross`: two steps that enter one cell, or two diagonal steps across one 2 × 2 square. The crossings of the path from the gap and those of every walked path both read it.
- Lint hints: `head-repeat` on `seg_path` is kept with `@ignore` (the path from the gap starts at the gap). `common-subexpr` on `skip` came from a skip clause that could never fire, which is deleted. `single-consumer` on `seg_end` is accepted: it is inlined into `along.score`.
- `deletions`: the atoms it lists as changing nothing guard structure the pairs never contain. These are `stuck`, `transverse` (no head-on paths), the obtuse direction sum, `side_defect`, the square test of `$CoreSizePerBox`, and the bg filter of `$PassUnderBox`. They stay. Two atoms of `steps_cross` that bounded the crossing cell to the grid are removed, because `seg_step` already keeps both steps on a path. The report also listed the first `cross` atom of `walk.take` as changing nothing on the pairs. Removing it broke `bent-ray-crossed`, because that atom fixes the ray's own stop. It is kept.
- Keywords: `walk` is added. Whether a ray meets at a crossing depends on the meetings along its path so far. `objects`, `cast` and `rank` stay (create.md).
- `background` and the wall color come from `Mode`, in `Parse<Key>`, shared by the program and `Determine` (create.md).
- A gap's direction comes from its neighbor relation to the core. No ring box is built (create.md).
- The direction sum is written for every pair that is not opposite, the obtuse cardinal-diagonal pair included (create.md).
- `$StopAtBox` clips only the path from the gap. A bent path is not clipped (create.md).
- The audit's store check skipped `steps_cross` ("over 20000 rows on an input"). It is a geometric relation over the grid's cells, not a value stored per case. Open as a skipped check.
- The parameterization is unchanged (`core_side`), and the run reports `determination: ok (core_side)`. The solver runs in about 4 s.

## Unsettled
- Head-on meetings and ring cells of a third color are still not formed, as `analyze.md` gives (create.md).

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
