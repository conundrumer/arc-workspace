# db0c5428

## Departures
- The branch `background=DominantColor` is the `@derive DominantColor` line on `bg`. In the witness file, its name is `bg=DominantColor`: [Witness file](docs/handbook/solver-file.md#witness-file) names a `@derive` branch `<param>=<Proposer>`, and the parameter is `bg`. Because of that name, `witness --file programs/reports/db0c5428/witnesses.json` reports that `background=DominantColor` denotes no case. Every output it gives agrees with `witnesses.json`.
- The witness `background=DominantColor` of `witnesses.json` (a 0 field in place of 8) is removed. `derive` recorded the witness `bg=DominantColor` (train 0 with 8 and 0 swapped) for the same branch, and the analyze witness duplicates it. The verdict `variant derived` and `@relaxed one-square` stay as `analyze.md` gives them.
- `$HalfTurnOut` stores no parameter. The half turn is derived as the flips on both axes together. The half turn is central in D4, so this choice adds no orientation. Without that derivation, the determination plan asked for a pair-reading determination of a stored `D4_HT`.

## Judgments
- Concept branch names: `Across` (outer-copy), `KnightFrame` (hole-center), `Clip` (overhang).
- Choice: `[copy: OuterCopy, center: HoleCenter, overhang: Overhang]`, with every combination in `impl_choice`. All 12 bases fit every pair. The run keeps 6 witnessed cases.
- `$CenterCorner` gets no constructor. `analyze.md` gives it no witness, and it fails Fit at test0.
- No item under Not formed states a model distinct from the concept. Each one is the concept's model, is no model, or is a proposer that gives no field. So Develop step 3 adds no branch.
- `store` gives no line to add. Each relation it lists either stands at another place on each input or varies by an id. `grown.box` has no witness.
- `block` (3) is stored in Params, because literals are banned and the program reads it. Determine reads it from the hole's side on each axis of each train input, so it uses no division of the square's side.
- `$GrowFrame` builds the grown frame from the row and column lines of the input cells and the block places, joined by `compose` on each axis. A cell's output position is its crop to the bbox of those cells. Positions past the grid edge are boxes with negative margins.
- Hint `head-repeat` on `frame_cell`: kept with `@ignore`. Under `Clip`, the output frame is the input frame, so each cell maps to itself. `GrowFrame` maps the same column to another position.
- The square's bbox moved into `Parse<Key>`, which the program and Determine share.
- Deletions:
    - `field(Ky, _)` was removed. The negation `!field(Ky, Col)` with `Ky` bound is enough.
    - `span_cell(P) :- place(P)` stays. It is `$GrowFrame`'s structure, and `edge-overhang` shows it.
    - The `train(E)` atoms and the `bg_defect` and `block_defect` universals in Determine stay. They state "every train input", which the pairs do not separate.
    - The bound enumerators stay, as the run says.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
