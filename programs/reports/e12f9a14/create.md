# e12f9a14

## Departures
- `$ChainedMeetings` has no constructor, and its name is gone from `ray-hits-box` and `three-core`. The witness `bent-ray-crossed` is removed, because without that branch it separates nothing: the branch fails Relational form. It applies the meeting rule round by round, and each round takes the crossings of the paths as they stand that come first along both rays. Each round reads the bends of the round before it, and it does so under negation ("no earlier crossing"). That needs recursion through negation, which the program bans, and no lib construction gives it (`Propagation` is monotone, and `Take` orders a walk, not crossings along many rays).
- The `meeting` rule has an `@approximated:` line: a crossing counts only where it is the first crossing along each of the two rays. That is the reading the Analyze probe used. The witness `ghost-then-meet` (ordinary, verdict `other`) shows the difference. On it, the col 5 ray first crosses the unbent line of a ray that has already bent, and then crosses the ray from a new box at the bottom left. The rule makes those two rays meet. The approximation runs both straight on, and they paint (26,5) in two colors, so the concept case is undefined there. The judged output comes from a `grid` run on a control grid that has that box's gap closed, with the meeting's cells then set from the rule.
- `core_side` has the branch `@derive TileCount` (variant, verdict `derived`, `@relaxed boxes`). `derive` reported it, and `oblong-core` is a further witness: TileCount gives `core_side` several values from a 9 × 9 extent, so it takes a 2 × 3 core as a box, while the stored side and `$CoreSizePerBox` find no box. That witness answers the audit finding that no witness separated `$CoreSizePerBox & core_side=stored` from `$StoredSide & core_side=TileCount`.
- The concept branches are named `$OverBox` (ray-block) and `$StoredSide` (core-size).

## Judgments
- `background` and the wall color come from `Mode`: the commonest color, and then the commonest color besides it. `analyze.md` says the probe finds the wall color this way too. They are in `Parse<Key>`, and the program and `Determine` both use it.
- A gap's direction comes from its neighbor relation to the core. A cardinal neighbor of a core cell is a side gap and goes straight out. A diagonal neighbor that is not a cardinal neighbor of any core cell of that box is a corner gap and goes diagonally. No ring box is built.
- Crossings are found on straight paths only, in two ways: a shared cell, or two diagonal steps that form the two diagonals of one 2 × 2 square. Each ray's stop cell is the cell before the crossing, and its step count is the order that `ArgExtremes.low` uses for "first".
- I wrote the direction sum for every non-opposite pair. That includes a cardinal against a diagonal whose component on that axis points the other way: the sum is then the diagonal's other cardinal. The concept statement only describes the acute case. The pairs do not use the obtuse clause, and `deletions` confirms this.
- `$StopAtBox` clips only the straight part of a ray. Bent paths are not clipped, because no witness or pair shows a bent path that reaches a box.
- Lint hints: I accepted `common-subexpr` on `gap` (merged into one disjunction) and on `bend_dir`/`bend_slope` (shared `meeting_dirs`), and `single-consumer` on `slope_sum` (inlined into `bend_slope`).
- `deletions`: the atoms it lists as changing nothing guard structure that the pairs never contain. Examples are the obtuse direction sum, `side_defect` (every pair core is 2 × 2), the bg filter of `$PassUnderBox` (no ray in the pairs passes a box), and the transverse and on-path tests inside `cross`. They stay. I removed the redundant `impl_choice` atoms from the three `path` clauses. I ran `deletions` before that edit and once more after it, so that its last output covers the final file.
- Keywords: `objects`, `cast`, and `rank`, because the first crossing along each ray decides which rays meet.

## Unsettled
- The concept's `meeting` rule ("neither ray has bent before that crossing") runs only as an approximation. A lib construction that resolves crossings in order along many rays would let the program state the rule itself.
- Head-on meetings and ring cells of a third color are still not formed, as `analyze.md` gives.

## Concept faults
- e12f9a14 `meeting`: whether a crossing is a meeting depends on whether either ray met another ray earlier. That is recursion through negation, which the program bans.

## Fixes elsewhere
- none

## Tickets filed
- none
