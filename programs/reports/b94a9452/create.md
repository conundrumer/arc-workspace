# b94a9452

## Departures
- The solver adds the branch `$LoneStays` under `$Swap`, and the witness file adds the witness `one-color` for it. Develop step 3 forms each claim under the Analyze report's Not formed, and "A one-color object stays unchanged" meets Fit and Relational form. Its model is not subsumed: on `three-layers` it gives the concept's output, which no layer case gives, and on `one-color` it gives the square unchanged, where the concept is undefined.
- The witness groups name `$Swap`, `$Partnered`, `$Solid` and `$Swap & background=stored` in place of the Analyze file's `concept`: `record --all` wrote the fewest names for the solver's cases.

## Judgments
- Concept branch names: `$Swap` at `recolor`, `$Solid` at `box-background`, and `$Partnered` at the new point under `$Swap`. The Analyze file names each of these only as `concept`, so the witness file needed no rename.
- Nesting levels of the layer branches: same-colored regions are `Components<Color>` over the object's cells. The seeds are the regions with a cell on the object's `Rim`, and a region's level is its `GraphDistance` from the seeds over the region adjacency graph. Each level must hold one color (`Unanimous`). This matches the Analyze probe's peel from the box edge wherever the box holds no background. With `$KeepBackground`, the rim also takes the cells next to background holes.
- `$LayerReverse` reads the mirrored level through `Ordinal` rank and rank_desc. The shift branches read the next level through `IndexCycle`.
- `one-color` witness: a one-color 3x3 square of 2 on 0. Plausibility `borderline`, because it breaks `nested-squares` (the inner square would be absent). Verdict `$LoneStays`, because a swap with no partner color most plausibly leaves the square as it is.
- Not formed, "The output keeps the input frame": every pair's output is the object's box, so a case that keeps the frame fails Fit at train0. No case was added.
- Not formed, "The object is one connected component, picked from several": the item gives no selection rule, so no claim could be formed from it.
- Not formed, "The outer color is the color on the box's edge": its model is the concept's, so it fails Equivalence. No case was added.
- `$StoredMapping` has no constructor. The Analyze report gives it no witness, and it fails Fit at train2.
- `store` printed no `@store` line to add. For `cycle.*` and `levels.*`, it found no witness on D4 images or color swaps of the train inputs, and the Analyze report gives none. So the solver holds no stored branch.
- `derive` listed `background=DominantColor`, and the solver records it as `@derive DominantColor: variant derived` with `@relaxed one-object`, as the Analyze report gives.
- Determination: the plan lists no actions. The examples cover `background` (DominantColor is exact), so the solver has no Determine comp.
- `deletions`: six deletions change no pair's output. Four of them remove rules for structure the pairs never use: lone colors, background inside the box, and the `$Swap` enumerator row used only by `$KeepBackground`. The other two drop `dir_elem` or `neighbor` in `nesting.edge`, which then joins every pair of regions. The pairs hold two regions each, so they cannot show the difference, but `three-layers` needs adjacency. All six stay.
- Keywords: `crop` and `mapping` are for the concept. `rings` is for the layer cases, where a cell acts by its nesting level.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
