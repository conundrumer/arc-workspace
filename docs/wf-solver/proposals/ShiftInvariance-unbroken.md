# `ShiftInvariance.unbroken` — the shifts no cell pair contradicts

A change to `.comp ShiftInvariance<Key, Val>`: expose the exact reading's set under a name, `unbroken(key: Key, a: Axis, k: number)` — the candidate shifts, per key and axis, that no cell pair contradicts.

```
    // The exact reading: the candidate shifts no cell pair contradicts,
    // per key and axis.
    .decl unbroken(key: Key, a: Axis, k: number)
    unbroken(Ky, A, K) :- _pair(Ky, A, K, _, _), !mismatch(Ky, A, K).

    // The exact reading's minimum: the shortest unbroken shift, per key
    // and axis.
    .decl min_period(key: Key, a: Axis, k: number)
    min_period(Ky, A, K) :- unbroken(Ky, A, K).
    min_period(Ky, A, K) <= min_period(Ky, A, K2) :- K > K2.
```

Not: `period`, the damage-tolerant set. Not `min_period`, nor the proposed `shortest` (`ShiftInvariance-shortest.md`): those are the two minima, one over each set, and this is a set.

Match: a rule that negates a `ShiftInvariance` instance's `mismatch`, or negates a helper relation derived from it, and binds that atom's axis and amount from a positive atom, wherever the atoms sit. Match with the parser (`tests/test_ast_match.py`), resolving each negated `mismatch` reference through its qualifier to its instance, and each negated helper back through the rule that derives it.

Survey: 2026-09-11 13:29 — the whole corpus.

Callers:

`29ec7d0e shift` — the `$Shift` case's repair shifts: every candidate shift that no clean-cell pair contradicts, with its delta read off `cand`, feeding the propagation that carries clean values into the noise.
`c3f564a4 out` — the `$Shift` case: a noise cell takes the color of its image under any candidate shift that no clean-cell pair contradicts.
`ca8f78db out` — the `$Shift` case, the same two atoms and the same read.

Each of the three instantiates `ShiftInvariance` on a single `Unit` key, writes `si.cand($U(), A, K, Delta), !si.mismatch($U(), A, K)`, and folds nothing, so each reads the set itself. Sixteen solvers in the corpus instantiate `ShiftInvariance`. The signature matched five rules in four solvers; of the remaining twelve solvers, nine read `min_period` and two read `period`, and the twelfth (`8403a5d5`) reaches `mismatch` positively, through a helper.

Near-misses:

`332efdb3 unbroken.cand` and `ca8f78db unbroken.cand`, both in `Determine`. Each writes `si.cand(_, A, K, _), !si.mismatch(_, A, K)` on an instance keyed by `Example`, so the negation binds no key and the rule keeps the shifts that no example contradicts. The proposed relation is per key. An existential read of it, `si.unbroken(_, A, K)`, holds where one example agrees, which is the opposite quantifier; rebuilding the consensus from the proposed relation takes a defect rule over the keys and then the read, where the negated `mismatch` takes one atom. The operation, as the entry states it, does not serve these two sites.

`8403a5d5 unbroken.cand`, in `Determine`. The same cross-key consensus, restricted to the trail's axis: `broken(K) :- si.mismatch(_, A, K), trail_axis(A)`, then `si.pair(_, A, K, _, _), trail_axis(A), !broken(K)`. Per-key `unbroken` gives neither the consensus nor the axis filter.

The `min_period` readers: `017c7c7b period_at`, `0dfd9992 wp.period`, `1d0a4b61 step`, `484b58aa period_at`, `50a16a69 period_step`, `53b68214 out`, `6a980be1 strip_out`, `7447852a min_period`, and `963e52fc period_at`. Each takes one shift per key and axis, which the entry's `Not` line excludes. `50a16a69 period_step` also joins `cand` for the delta, and `7447852a min_period` reads the per-key minimum under a wildcard key, but both consume a minimum, not a set.

The `period` readers: `135a2760 period.cand` and `53fb4810 shortest.cand`. Both take the damage-tolerant set, which the entry's `Not` line excludes.

Local period sets with no `ShiftInvariance` instance: `3ac3eb23 unbroken.cand`, `97999447 unbroken.cand`, `516b51b7 repeat.cand`, `c1990cce period`, and `3979b1a8 period`. Each writes candidates plus a negated local `mismatch`, and three name the fold `unbroken`. Their domain is a 1D index set — ray step counts, ring depths, diagonal radii — not a keyed valued cell set under axis-aligned shifts, so no instance's relation would serve them.

`47996f11 axis_center` and `981571dc axis_center`. Both take the offsets whose mirror, not whose translation, carries no cell onto a different color.

Spec:

The columns stand as the entry states them. The three callers read one key, one axis, and one amount, and the delta they need stays on `cand`, so nothing in the sites argues for another column.

The entry's caller list should lose `332efdb3 unbroken.cand` and `ca8f78db unbroken.cand`. Those two, and `8403a5d5 unbroken.cand` beside them, fold `mismatch` across keys. That consensus is a different operation from the per-key set, and three sites write it.

On the spec question — candidate-level or witnessed — the sites answer for the witnessed set. Four sites build this shape outside the comp, and every one of them pairs first: `8403a5d5 unbroken.cand` takes its candidates from `si.pair`; `0dfd9992`, in its `Wallpaper` proposal comp, derives `sym` from a `witnessed` relation that requires a cell pair with `P != Q`; `47996f11 axis_center` and `981571dc axis_center` each require a mirrored cell that exists, under a comment naming the defect, that an offset past the frame pairs nothing and would otherwise pass unbroken. No site outside the five matched rules admits a pair-less candidate.

That reading costs the three callers. Each feeds `cell` the clean cells alone, so its set is sparse and carries pair-less candidates that the witnessed reading drops, where the two `Determine` sites feed the whole of `ex_out`. The change is therefore a change to what the three callers admit, and each needs a run to confirm it still repairs every hole.

Reimplementations: none. The matcher ran over the parsed corpus, one pass with `each_solver()`: every `neg` reference named `mismatch` whose qualifier resolves through the file's `.init` chain to `ShiftInvariance`, reported with the rule's positive atoms that bind the negated atom's axis and amount variables. It returned five hits, in `29ec7d0e`, `332efdb3`, `c3f564a4`, and `ca8f78db` twice. The positive and indirect readers came from a `mismatch` grep over `programs/solvers/`, read site by site.


Box (2026-09-11): The comp is `OffsetInvariance`, so the proposed readout is `OffsetInvariance.unbroken`. Its readouts keep their names, and the change the entry proposes is untouched: lib still derives `min_period` from `_pair` and a negated `mismatch` in the comp body, with no named set between them. The callers read `cand` beside a negated `mismatch` as the entry records — `29ec7d0e` `shift` writes `si.cand($U(), A, K, Delta), !si.mismatch($U(), A, K)` — and `cand`'s delta column now types `Offset`. The operation stands. See docs/wf-solver/box.md.
