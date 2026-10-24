# d22278a0

## Departures
- `$CornerRings` has no constructor and no case. It was written, it fit every pair, and the run showed it as a witnessed case. `witness` then reported that no run shows it defined and differing from `$SeedRings`. No input can show that: the branch is defined only where every seed sits at a corner, and there a cell's distance from the corner's two edges is its Chebyshev distance from the seed, at every `background` and `ring_period`. It fails Subsumption, as `analyze.md` predicted. Without it, `Choice` is the `territory metric` ADT.
- `$EuclideanTerritory` has no constructor: it fails Relational form. Comparing Euclidean distances needs squared offsets, which count nothing the task has, and the program bans that arithmetic. No lib relation states it.
- Witness file: removed the names `$EuclideanTerritory` and `$CornerRings` (`witness` lists no case for either), with the groups only they held. Rewrote the `separates` texts of `wide-grid`, `edge-seed` and `background=DominantColor` to drop them. Removed the empty `assign` objects. Re-recorded every group with `record --all`.
- The `edge-seed` witness line stands under `$RingThenTaxicab` (borderline concept, `@relaxed corner-seeds`), because its other branch, `$CornerRings`, left. `$RingThenTaxicab` gives (0,4), (3,2) and (6,1) 0 on it, where the concept gives 1, 2 and 1.
- `background=SharedColor` has no branch: it fails Fit on train0, and `derive` does not list it.

## Judgments
- `common-subexpr` hint (line 77, `ring` shares `seed`, `in` and `relative` with `taxicab`): I accepted it and factored out `from_seed(O, P, V)`, which is cell P in the frame of seed O. Both distances read it.
- Taxicab distance: `diag_dist(V, Diag, _, K1, K2), K1 >= 0, K2 >= 0, corner_dist(V, Diag, N)` on the seed-relative offset. The two bound comparisons pick the corner P lies away from, which gives the unsigned row and column distances. Chebyshev distance: P is on the outline of the square that reaches K past the seed (`uniform_outset`, `compose`, `box_edge`). This is the form draft b7fb29bc uses. No approved solver encodes either distance, so there is no precedent.
- Ring test: `stride(K, ring_period, 0, _, J)`, with `J = 0` meaning on a ring. The 0 gap and the 0 index are both absences, and no other literal enters.
- Nearest seed: `Extremes` per cell, then `Unanimous` keyed by `[Choice, cell]`. `value` gives the owning seed and `clash` gives the tied cells. With no seed the output is empty, so the concept is undefined there, as `analyze.md` says.
- `deletions`: the `by_ring.low` and `ring` atoms in `$RingThenTaxicab` change no pair, because on a square grid with corner seeds Chebyshev-then-taxicab agrees with taxicab. `wide-grid` shows they matter, so they stay. The `impl_choice(Ch)` atoms in `out` were redundant because `owner` grounds `Ch`, so I removed them. `impl_choice` stays as the case enumerator.
- `@derive DominantColor`: plausibility `variant`, verdict `derived`, `@relaxed square-grid` and `corner-seeds`, as `analyze.md` gives. `store` reported no findings.
- Determine: `background` is the color every train input holds most (`Mode`), the stored value. `ring_period` gets no determination relation (see Unsettled). The sweep gives it the single value 2 at which the model fits every train pair, and the concept does not derive it from the inputs.
- Keywords: `markers` (corner seeds), `rings` (each cell acts by its ring around a seed), `rank` (the nearest seed, an extremum, picks the color), `parity` (alternating rings).
- Develop step 3: no item under Not formed states a model that fits. The stored tie priority fails train1, the quadrants fail train3, and blank seed cells fail every pair. `ring_period` derived is not a choice point.
- Runs: every pair passes for all 3 witnessed cases. Lint is ok, determination is ok (background), and the final audit and witness runs are ok. `witness --file` against `witnesses.json` printed only the missing-case notices for `$EuclideanTerritory` and `$CornerRings`, and no output differences.

## Unsettled
- `determination-plan` still lists `ring_period (SepTileCount narrowed(2))`. That proposer reads a separator tiling of the inputs, which these inputs do not have and which has nothing to do with ring spacing. A determination built on it would claim a dependence the concept denies. A ruling on whether this entry calls for a relation that reads ring spacing from the train outputs would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
