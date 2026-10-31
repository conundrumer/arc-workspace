# dfadab01

## Departures
- The witness file has a witness that `witnesses.json` does not have, `key-color-past-other-corner`, with a `@witness` line under `$KeyByContact` and `$KeyAnyCorner`: `witness` reported that no run showed `$SampleStamp & $KeyAnyCorner` defined and differing from `$SampleStamp & $PastKeyCorner`. On `marker-past-other-corner`, the two key markers of `$KeyAnyCorner` differ in color, so `$SampleStamp & $KeyAnyCorner` is undefined there. The new witness is train0's input with a 5 marker at (5,0), past the sample's bottom-left corner. That marker has the key's color, so the case is defined there and wipes the marker. Plausibility `ordinary`, verdict `concept`: it breaks no scene claim, and the concept's key marker is the one past the `key_corner` corner alone.
- The concept's parameter names are written as relation names: `key-corner` is `key_corner`. `anchor` is the `@` cell of each `GRID_STAMP_SPARSE_4x4` layout of `stamp`. `$SampleStamp` also reads `anchor(DIAG_TL)` as a `DiagDir` relation under its marker: it places the sample's cells by a corner of the sample's box, and that needs a different form from the stamp layout.

## Judgments
- The sample is the bounding box (`Bbox`) of the non-background cells that are not markers. The key marker is found from a corner of that box, and the solver does not match the box against `stamp`. On `sample-picture` and `background=DominantColor`, this gives the concept outputs that `witnesses.json` gives.
- `$SampleStamp & <key-marker branch>`: `Unanimous` gives the sample's key. Where the key markers differ in color, `clash` makes the case undefined, as `analyze.md` gives.
- `$MarkerBySingleton` is undefined where a marker has a color with no picture under the case. Under `$SampleStamp`, the sample's key has a picture too.
- Twelve `Choice` combinations are cases. Eight are witnessed. `witness` and `audit` report no unseparated pair and no unwitnessed branch.
- `store` reported `picture` with no witness and gave no line to add. The solver holds no `@store` branch.
- `derive` gave `background: DominantColor`. It is the `@derive` line on `background`, with the `background=DominantColor` witness of `witnesses.json`.
- `deletions`: `impl_choice` in `drawn` was redundant because `picture` grounds the case, so it was removed. The other eight deletions that change nothing remove structure that the pairs never instantiate: the undefinedness clauses, the sample-key clauses, `!params.background(K)` for a lone background cell, and `params.key_corner(D)`, without which `$PastKeyCorner` would be `$KeyAnyCorner`. They stay.
- `deletions` ran before that last edit, not after it. The edit only removes an atom that `deletions` reported, and the last pairs run passed after it.
- Determination: `background` takes the input's commonest color (`Mode`), which is the field. The pairs enumeration gives `anchor` and `key_corner` (one value each fits). The plan named no proposer for them that reads another fact.

## Unsettled
- `stamp` has no determination relation. The plan lists it as undecided. Clauses that read it from the evidence would take each key's picture from the sample (train0–2 and test0 each hold one). But they need the box corner that the stamp offsets count from, as a literal or read from Params, and Determine has neither. A ruling on whether Determine may read the `anchor` and `key_corner` values, or a lib comp that gives a picture's offsets from a stated corner of its box, would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
