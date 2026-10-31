# d017b73f

## Departures
- `programs/witnesses/d017b73f.wit.json` has a witness that `witnesses.json` lacks, `column-run`. It is a single color-1 cell and a color-3 bar in neighboring columns that do not touch. The concept keeps them as one band and leaves them in place. Every `$PieceComponent` case splits them and lifts the bar to row 0, and `$PieceComponent & $EndPathEnd` is undefined there. The witness rests on `witness` reporting that no witness separated `$PieceComponent & $Adjacency8 & $AnyColor` from `$Band`. I judged it `borderline` with verdict `$PieceComponent`, since it breaks `strip-of-pieces` and `piece-is-path`. It is a case witness, not a branch witness: the audit showed that `$Adjacency8` and `$Adj4` give the same output on it, so it has no `@witness` line.
- The concept case and every other case place a piece only where its start lands on a row of the strip. Where a moved end leaves the strip, the next piece has no landing, and the case is undefined on that input. The concept would instead go on placing pieces outside the strip and drop their cells, and `$GrowFrame` would grow the frame to hold them. The two differ only where a start lands outside the strip, which breaks `chain-fits`. No witness of the Analyze files shows it (`descending-chain` takes the third piece's start in row 2, inside the strip). This follows the corpus precedent `03560426`, whose `Propagation` landings are also cells of the input.

## Judgments
- The running row shift is computed by `Propagation<Walk, Landing>` over (piece, row its start lands in) nodes, with edges built statically over the strip's rows. The solver bans recursion, and this lib construction is the closure that gives a sum of shifts without it.
- The empty columns are closed up by `OrderFrame<Unit, Position>` over the non-empty columns, and output rows come from cropping each landed cell to the frame box `frame` (`Bbox<Choice>`). That box is the input frame under `$KeepHeight` and the box of input and landed cells under `$GrowFrame`.
- The cases are the full product: 5 piece readings × 3 end readings × 2 overflow readings × stored or derived background. `run_dl` runs 9 witnessed cases. All of them pass every train pair and the test.
- Branches without a constructor: `analyze.md` gives `$EndTop`, `$EndBottom` and `$AnchorLast` no witness, and they fail Fit (train0, train0, train1).
- `derive` listed `background=DominantColor`, which is held as a `@derive DominantColor: variant derived` line with `@relaxed strip-of-pieces`. Its witness `background=DominantColor` is the one `derive` records.
- `store` reported `frame.box` as the same on every input with no witness it could build. Storing the box would give the input frame, which is the `$KeepHeight` model. That branch is equivalent to the concept, so it gets no `@store` line.
- Lint hints, all resolved in code:
    - single-consumer on `end`: inlined into `walk.edge`.
    - common-subexpr on `follows` and `first_piece`: factored into `side_column`.
    - common-subexpr between `walk.edge` and `shared_column`: `shared_column` now compares `ink_column`.
    - head-zero on the `$KeepHeight` frame: replaced by the `frame` Bbox.
    - argmax on `farther`: replaced by `ArgExtremes`.
    - case-section markers: shared code moved above the markers.
- Determination: `Determine.background` keeps the color that is the commonest in every training input (`Mode` per example), per the plan. The plan still lists `chain_dir` as pairs-exact (1 of 4 directions reproduces every train pair). That is determination by the type's values that fit, so it needs no clause.
- Simplify:
    - the walk's nodes became rows rather than cells, because `deletions` showed that the landing's column never reached the output.
    - `piece_side` now ranges over every direction.
    - `farthest.cand` reads `row`.
- `deletions` reports clauses whose removal changes no pair. These are kept, because they encode an undefinedness or branch behaviour that only the witnesses or out-of-scene inputs exercise:
    - `start_tie`, `end_tie` and `stuck`
    - `shared_column`
    - the `$GrowFrame` frame cell and row disjunct
    - `comp8_color`
    - `off_ground`
- Keywords: `objects move walk chain`. Each piece's placement depends on the path so far, which is `walk`. The pieces link end to end into one line, which is `chain`.
- No item under Not formed states a model that meets Fit, so Develop step 3 adds no branch.

## Unsettled
- `$PieceComponent & $Adjacency8 & $OneColor` and some other product cases are not witnessed, so `run_dl` does not run them. A witness on which they differ from every case with fewer non-concept branches would settle whether they stay.
- Where a moved start leaves the strip, the solver is undefined but the concept's intent is not (see Departures). Settling it would need a candidate row domain beyond the strip with no number that the task does not count.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
