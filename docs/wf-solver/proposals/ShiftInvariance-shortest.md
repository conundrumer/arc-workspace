# `ShiftInvariance.shortest` — the shortest period read through damage

A per-key readout on `ShiftInvariance`: the least k that `period` admits,
per key and axis. `min_period` is this over the exact reading, and a set
whose pattern carries damage has none — the damage contradicts every shift
short enough for its own cells to witness, and a longer shift the set's
extent leaves pair-less is unwitnessed. `period` admits both kinds, so its
minimum is the period a caller reads off a damaged set, and off a set too
short to witness its own period at all.

```
    // The damage-tolerant reading's minimum: the shortest period, per key
    // and axis.
    .decl shortest(key: Key, a: Axis, k: number)
    shortest(Ky, A, K) :- period(Ky, A, K).
    shortest(Ky, A, K) <= shortest(Ky, A, K2) :- K > K2.
```

- A pair-less candidate is vacuously a period, so an axis whose set
  witnesses nothing takes the shortest candidate the frame admits, and a
  caller jumping by it leaves the frame at the first step.

Not: `min_period` (the exact reading's minimum); `period` itself (every
admitted k); the set's extent along the axis, which a caller reads from
`Bbox.extent`.

Match: an `Extremes` or `ArgExtremes` instance whose `cand` is
`ShiftInvariance.period`, and any hand-written minimum over it. Grep:
`\.period(`, `Extremes`, `min_period`.

Survey: 2026-09-08 20:51

Callers: 135a2760 `period` with `period.low`, 53fb4810 `shortest` with
`shortest.low`. No third.

- 135a2760 `period` (`135a2760.dl:41`) takes each panel interior's shortest
  period per axis, and the orbit closure at line 51 joins it back to
  `si.pair`. The fold's key is `PanelAxis = [t: Position, a: Axis]`, a record
  the file declares for this fold alone.
- 53fb4810 `shortest` (`53fb4810.dl:73`) takes each band's shortest period
  along its growth axis, and `$Period` reads it as the band's tile. The
  band's axis is fixed by `grow_axis` before the fold, so the key is a bare
  `Ident`.

Negative evidence: `ShiftInvariance` is instantiated in 13 solvers of the
547. Eleven never read `period`: seven read `min_period`, three read `cand`
with `!mismatch`, and 0dfd9992 reads `min_period` into a proposal comp. Of
the 112 `Extremes` and `ArgExtremes` instances in the corpus, two take
`cand` from `period`, and they are the two above. No solver takes the
minimum another way: no subsumption rule over a period relation, no
"nothing shorter" negation, no rank-0 read of `Ordinal` or `Order`.

Near: 017c7c7b `period_at`, 963e52fc `period_at`, 484b58aa `period_at`,
1d0a4b61 `step`, 50a16a69 `period_step`, 53b68214 `out`, and 0dfd9992
`wp.period` each read `min_period`, and each wants the exact reading for
one reason: every one of them removes the damage from `cell` before the
comp sees it, by a stored hole or noise color, or has no damage at all. On
a set whose damage is already gone, a broken pair is a real period
violation, and the tolerant minimum would admit a shorter false period. The
per-line instances (`si_line` in 017c7c7b, 484b58aa, 963e52fc) also depend
on `min_period` requiring a witness: a line with many holes has candidates
that pair nothing, which `period` admits and `min_period` does not. The two
`period` sites cannot strip their damage — 135a2760's panel interiors and
53fb4810's bands carry damaged cells in the pattern's own colors, with no
color naming them — so the split between the two readings tracks whether
damage is identifiable, not which fold a caller prefers.

332efdb3 `unbroken` and ca8f78db `unbroken`, both in `Determine`, rebuild
the exact reading's set by hand as `si.cand(_, A, K, _), !si.mismatch(_, A,
K)` and fold it with `Extremes<Axis>`. They want the exact reading and
cannot use `min_period`: the comp's key is `Example`, and the fold keeps the
candidates no example contradicts, which is a consensus across keys rather
than a minimum within one. Their hand-built set also admits pair-less
candidates, which costs them nothing, because their `cell` is the whole of
`ex_out` and every candidate pairs. 29ec7d0e `shift($Shift(), ...)`,
c3f564a4 and ca8f78db `out(..., $Shift())` read every unbroken shift and
propagate along all of them, with no fold. 47996f11 and 981571dc
`axis_center` fold over mirror-line offsets rather than shifts, and answer
the pair-less caveat by requiring a witnessed image rather than by folding.
20a9e565, 221dfab4, 3ac3eb23, 97999447, 3979b1a8, and c1990cce each fold a
shortest period over a candidate set of their own — growth-step counts,
corridor offsets, ray step counts, diagonal jumps, stripe distances — none
of which is shift invariance of a cell set.

Spec: name both relations for their reading. `min_period` is not the
minimum of `period` — `period` is the wider set, so its minimum is at or
below `min_period`'s, and the two coincide only when nothing is damaged. A
reader at `53fb4810.dl:74` sees `shift.period` folded by hand with
`shift.min_period` sitting unused beside it, and nothing in either name says
why. The corpus already names the readings where it has to: 332efdb3 and
ca8f78db call the exact set `unbroken`, 484b58aa's header calls its value
"the shortest witnessed unbroken shift", 135a2760's calls its own "the
shortest period", and 53fb4810's says "read through damage". The exact
reading has no name in the comp at all, only its minimum, which is why those
two `Determine` comps rebuild it from `cand` and `mismatch`. So the change
the sites argue for is to expose the exact set beside `period` under the
name the callers give it, and to name each minimum after its set.
`shortest` beside `min_period` names one by its fold and the other by
neither, and puts the pair's difference in no name. No site reads both
minima, so nothing in the corpus requires the two to be told apart within
one rule; the demand is on the reader, not on a join.

Box (2026-09-11): The comp is `OffsetInvariance`, so the readout is `OffsetInvariance.shortest`, and both callers instantiate it under that name. The readouts keep theirs — `cand`, `pair`, `mismatch`, `period`, `min_period` — and only `cand`'s delta column retypes, to `Offset`. The `Not:` line's `Bbox.extent` is `box_extent(b, p, a, n)`, which reads the axis extent in the frame of a named cell. The operation and the fold stand. The Spec point stands whole: the rename reached the comp's name and not its readouts, so the exact reading still has no name in the comp, and `period` beside `min_period` still puts the pair's difference in no name. See docs/wf-solver/box.md.
