# d56f2372

## Departures
- `symmetry` is stored as `D4_LR`, not as the concept file's `SYM_LR`: the concept describes the parameter as one reflection, "the mirror about the vertical axis of the shape's bounding box", and `D4Map.map` reads a `D4`. A `Sym` would need a `sym_member` step to convert it ([Indirection](docs/handbook/encoding.md#indirection)). A `Sym` value would also give a wider family, for example "kept by every member of `SYM_BOX`".
- Witness file `background=DominantColor`: I added a sentence to `separates`. On this input, with 8-connected pieces and `background` derived as 3, the field piece of 0 at the bottom right is kept by its diagonal mirror. So the `$AnySym` and `$OddSym` cases there are undefined, which `record --all` gives as the group `$Components8 & background=DominantColor` with grid null. `witnesses.json` lists no such group because it gives branch models alone.
- New witness `odd-asymmetric` for `$OddSym`, because `audit` reported that no run showed `$OddSym` defined and differing from `$AnySym`. The input has three shapes each kept only by the vertical mirror, and one shape with no symmetry. The concept and `$AnySym` keep three shapes and are undefined. `$OddSym` crops the asymmetric shape.

## Judgments
- `odd-asymmetric` is `variant $OddSym`, `@relaxed one-symmetric-shape`: this task's generator never makes the input. An odd-one-out variant (pick the shape whose set of symmetries is unique) makes it routinely and pairs it with the asymmetric shape's crop.
- Shapes as color classes use `Canon<Position>` over pairs of cells of one non-background color. It is a construction, and gives an `Ident` per class, so both parses share one `ShapeKey = [p: ShapeParse, id: Ident]` for `Bbox` and `D4Map`. The program treats each class as one thing, so the conversion is justified.
- `$OddSym` compares symmetry sets with `KeyedSetCompare.equals` rather than a hand-written defect relation, which reuses the lib.
- `rivaled`: `deletions` reports that removing it changes no pair, because no pair keeps two shapes. I kept it. It states "the one shape" of the analyze branches. Without it, `$Components8` would be defined on two identical symmetric pieces of one color, whose crops coincide. Under color classes, two kept shapes already conflict because their colors differ.
- Hints `head-repeat` on `sym_differs` and `chosen`: both were valid. `sym_differs` was replaced by `KeyedSetCompare`, and `chosen` is now keyed by the piece `Ident` alone.
- The `Determine` comp derives `background` as the color every train output holds, a fact of the outputs alone. The plan asked for a relation beside the `DominantColor` proposer. `symmetry` is left to the built-in enumeration: no proposer gives it, and 1 of the 8 `D4` values fits.
- `sweep`: under `$GridWindow` the pairs admit `background` values 0, 2, 3, 4 and 7. These are not open values: the concept fixes 0, and 0 serves every case, so `background` has no case column.
- Develop step 3: the Not formed items of `analyze.md` give no model that fits (rank selection, grid-axis symmetry, the other color proposers, a derived `symmetry`), so none is formed.
- Dropped branches: `$Components4` fails Fit at train0, where the 8 shape splits into several symmetric pieces. `background=SharedColor` fails Fit at train0, where at a shape's color the field of 0 becomes a shape.
- No rule is approximated, and no witness has verdict `other`.
- The solver passes every pair (8 witnessed cases of 24). Lint, `witness` against both files, and `audit` are clean.

## Unsettled
- `odd-asymmetric`'s verdict `$OddSym`, against `two-shapes`' verdict `concept` on the same branch: an annotator's review of whether an odd-one-out variant is a variant of this task would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
