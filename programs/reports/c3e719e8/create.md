# c3e719e8

## Departures
- The solver has no `$StoredBlockCount` constructor, no `block_count` parameter and no `small-grid` scene line, and the witness file has no `four-by-four` witness. The witness run against the Analyze file prints `four-by-four: the name $StoredBlockCount denotes no case of the solver` for this reason: the branch fails Subsumption, as the Analyze report says. At every `block_count`, the branch is defined only on an input of `block_count` × `block_count`, and there it gives the output of `$PerCell`. After the branch left, no `@claim` or `@relaxed` line denotes `small-grid`, so the header leaves it out.
- `Choice` is the tie ADT itself (`Sole`, `TiesAllGate`, `TiesNoneGate`). It is not a record: once `Blocks` left, the `count-tie` point is the only point the solver encodes. The `gate-color` point is not encoded either, because no other branch of it has a witness.

## Judgments
- The derivations `block_count=ConstInDim` and `block_count=TileCount` were held as `@derive` lines while `$StoredBlockCount` stood, and they left with it.
    - `ConstInDim` fails Equivalence. On every input it gives that input's extents, and only the frame of the input's own shape matches input cells, so its case gives `$PerCell`'s output everywhere.
    - `TileCount` fails Subsumption. Where it is defined, it gives `$PerCell`'s output.
- `$Sole` (the concept case) is undefined on a tie because its `blank` clause tests `!parse.commonest.clash`. `deletions` reports that this atom changes no pair. It stays, because the pairs have no tie, and witness `mode-tie` shows the concept undefined there.
- `Determine.background` reads the color of the output blocks whose input cell is not of the commonest color. The plan asked for this in place of `AnyOutNewColor`. Its atom `parse.commonest.value(E, _)` changes no train pair. It stays, because the concept gives a blank block only where a commonest color exists.
- The shared Mode/Unanimous parse moved into `Parse<Key>`, because `Determine` repeats it per example.
- Not formed items: the fixed gating cell and the every-row color each state one model, but both fail Fit at train0/train2, so they add no case. `gate_color=DominantColor` is equivalent to `$TiesAllGate`. The other two items state no single model.
- `background` has no fitting built-in derivation. `derive` prints "no built-in derivation fits", and `store` reports no findings.
- The keywords are `tile-arrangement stamp rank`. `rank` covers "the commonest color", which is an extremum over counts. `tile-arrangement stamp` follows the precedent of 007bbfb7.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
