# afe3afe9

## Departures
- Each `$PackTowardUniformHalf` / `$PackTowardColorHalf` case is undefined on an input whose squares' span has an even number of slot lines on either axis, the pack axis included (create). The Analyze report states the same thing ("undefined where an axis spans an even number of slot lines"). The witness `first-cross-line-empty` needs this reading, because in it only the V axis is even. The departure holds.
- Every case is undefined when some unit gets no output cell (`lost`) (create). The Analyze report states this for `$StoredAlongExtent` (a line holds more squares than `along_count`) and for `$ComponentUnit` (pieces off one tiling). For the other branches the guard fires only where a unit lies off the tiling. That input breaks `ring-tiling`, and the Analyze report gives no output for it. The departure holds.
- The witness file holds `along-line-overfull`, which the Analyze file does not hold: train0 with a square of color 2 at rows 2–4, cols 13–15, so the top slot row holds 7 squares. The concept and `$MostRingsExtent` give a 7 by 7 output. `$StoredAlongExtent` is undefined. It breaks `pack-gap-empty`, so the header now has `@scene pack-gap-empty` (a `@relaxed` line denotes it), and the departure of create on the missing scene line no longer applies.

## Judgments
- `along-line-overfull`: plausibility `borderline`, verdict `concept`. The generator leaves the middle slot line on the pack axis empty in every input, so a square there is unusual. A reader who packs each line's cells would pack all 7. It stands under `$StoredAlongExtent` and shows that branch undefined, which settles the open item of create.
- Reconcile: the solver passes every pair with 10 witnessed cases. Lint, the audit, `witness`, and `witness --file` against the Analyze file are clean. `derive` lists the two held `@derive` lines. `store` prints no `@store` line to add.
- Determine: the sweep finds every parameter unique, and the plan lists no action. `along_count` and `ring_gap` are determined.
- Deletions: 16 deletions change nothing on the pairs, and each stays.
    - `filled`, the side check in `square`, `even`, `lost`, and `inside(S, B_a)` state concept or branch claims that the pairs never test (create).
    - `axis_of(E, A)` in `slot_line`: `box_extent` implies the axis only while `ring_side` is more than 1.
    - `middle.a` and `axis_of(D, A)` in `middle`: the column is read by `half` and `even`, and the atom binds the direction for `dist_pair`.
    - `opposite` and the two `nearer` atoms in `Determine`'s `between.item` state "between"; without them the count takes lines outside the two squares.
- Simplify: no change. Prune: no change beyond the new header and witness lines.
- Concept square, tiling, middle line, cases, derivations, Not formed, and keywords: as create gives them (create).

## Open
- none

## Lib
- Order of members by nearness to an edge: `Order` with `before(K, A, B) :- elem(K, A), elem(K, B), <dir D for K>, nearer(D, A, B)`. Here it is `along_order.before`. The grep finds the same shape in 3e6067c3, 72207abc, 7e576d6e, 9473c6fb, 97d7923e, 9968a131, 9f41bd9c, 99306f82, 9aaea919 and a1aa0c1e. The candidate operation is an `Order` whose input is a direction per key in place of `before` (create).

## Fixes elsewhere
- none

## Tickets filed
- none
