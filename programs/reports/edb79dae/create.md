# edb79dae

## Departures
- The witness `$KeySourceBySide` is `mirrored-keys` in the solver and the witness file: the lint requires a `@witness` id in slug form.
- `background` names the background as the commonest color: the solver finds it with a `Mode` instance, because the concept file stores no background and the background differs between inputs (8, 1, 4).
- The concept branches take names of my own: `$KeySourceByPoke`, `$StencilExact`, `$UnkeyedUndefined`, `$FrameByColor`. The witness file uses only `concept` for them, so no name there changed.

## Judgments
- `$KeySourceBySquare`, `$MapTransitive` and `$StencilByComponent` have no constructor: each fails Fit at test0, as `analyze.md` gives, and has no witness.
- The Not formed items of `analyze.md` give no branch: each either states no model, fails a pair, or is equivalent to the concept.
- `derive` reports no built-in derivation that fits, and `store` reports no finding, so the solver has no `@derive` or `@store` line.
- Keys, squares, stencils and the frame are all found from one `Components` instance over the cells off the background: a key is an object of two colors, a square is an object inside the frame's box, and a stencil is the cells of one color outside the frame's box and in no key.
- `$StencilExact` takes a stencil cell only where the square's box and the stencil's box share a frame (same size). This keeps the concept undefined on `scaled-stencil`, which the pairs never test.
- `$StencilScaled` cuts the square, one axis at a time, into as many parts as the stencil's box has cells on that axis (`divide`, composed). The cut gives nothing where the quotient is not whole.
- The poke test reads the source cell's neighbor toward a direction and both of its neighbors across that direction. This states "three 4-neighbors of the other color" with no count. A key where both colors poke gives no key map, as `analyze.md` gives.
- Hint `common-subexpr` on the two shared `out` clauses: I merged them into one disjunction.
- Hint `head-repeat` on `paint`: kept, with `@ignore`. `$IdentityUnkeyed` paints a color in itself, so the repeated column is that branch's claim.
- Determination: `frame_color` is derived in `Determine` from the train outputs, as the one color on every output's edge. `key_side` is fixed by fit over the `Dir` values (pairs-exact `DIR_L`), and needs no relation.
- `deletions`: I kept each deletion that changes nothing. Each one either encodes a branch's behavior or an undefined case that only the witnesses reach (stencil size, both-color pokes, mixed side columns, outline gaps, unkeyed squares), or it states the poke's three neighbors. I dropped `key(Id)` from `poke`, because `blob_color(Id, T), T != S` implies it.
- `witness` reports no unseparated pair of cases and no case without a defining run. The audit finds nothing. The 7 witnessed cases are the concept and each single non-concept branch.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/edb79dae/analyze.md`, the `$KeySourceBySide` line: the witness id `$KeySourceBySide` should be a slug, such as `mirrored-keys`, and `witnesses.json` should use the same id.

## Tickets filed
- none
