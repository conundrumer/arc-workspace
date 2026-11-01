# d35bdbdc

## Departures
- `linked-boxes` states the relational definition of a wire end from analyze.md (Concept, second item), and the scene claim `unhooked-ends` states the inputs on which that definition finds the wire's two ends.

## Judgments
- Continuation: an earlier `create` pass was interrupted during Determine. Its Write and Develop work stands, apart from the Simplify edits below. Before stopping it had replaced a 4-connected `Components<Unit>` parse over all non-background, non-wire cells with `Components8<Color>`. I kept that parse. A box is its outer cells, which are one color and in a plus touch only at corners. Its center may have any color, the background's or the box's own included. With the per-color parse, `background=DominantColor` gives analyze.md's output on its witness, and `self-named-box` (a solid plus) gets its center.
- Constructors: `$SelfLookup` is the only one. analyze.md gives no witness to any other branch: `$AnyOuterCell`, `$DiagonalContact`, `$OneNeighborEnd`, `$AnyWireCell`, `$KeepUnlooked`, `$UnlookedUndefined`, `$ReadsOutputCenter`, `$FollowChain`, `wire_color=RarestColor`, `wire_color=SharedColor`. Each fails Fit at the pair analyze.md names, so none is a case.
- `background=DominantColor` is the `@derive DominantColor: borderline concept` line on `background`, as `derive` printed it, and has no constructor. `store` reported no findings.
- Not formed (Develop step 3): no branch added. Each of these readings fails Fit as analyze.md shows: the readings without the wire (chain heads or alternation, test0), a linked box taking the center of the box at the wire's other end (train0), and an end that touches two boxes linking only one of them. That last reading also states no single model, since no feature picks the box. The other `wire_color` proposers give no value.
- Hints: in `wire_link`, the earlier pass merged the two clauses into one disjunction to resolve common-subexpr. On `wire_end` it kept the relation with `@ignore: single-consumer`, because `linked-boxes` and `unhooked-ends` name it.
- The `determine prediction` hint flagged the earlier pass's `wire_color` determination: a negated test (`open_center`) over a relation that reads inputs and outputs together. I rewrote it with positive joins only. A linked center is a recolored cell whose four sides (`perp_dir`/`opposite`) are kept, and the wire color is the input color two steps beyond a side middle, where it is not the background. That also removed the subsumed-atom finding. The common-subexpr hint between `background` and `linked_center` went away once I factored out a `recolored` relation. `determination-plan` now reports no actions, and both parameters are determined (`background` by DominantColor's fact read from erased cells, `wire_color` as above).
- Simplify (`deletions`): I removed the `id` column and the `piece.label` atom of `adjacent`, the `center` atom of `outer_color` (every consumer joins `center_color`), the `piece.label` atom of `touched` (`center` already makes each in-grid side of the center a piece cell), and `dir_elem` in Determine's `background`. I kept the rest:
    - the `!params.background`/`!params.wire_color` exclusions in `piece.node`, which the scene states;
    - the `C = P` disjunct of `cand`, which the solid plus of `self-named-box` needs;
    - `neighbor` in `cand`, which bounds the candidates;
    - `far.id`, since a cell can touch two pieces;
    - `dir_elem` in `touched`, since a diagonal reading is another model;
    - the four kept sides of `linked_center`. Each one is redundant alone on the pairs, but not all of them together.
- Witness: `record --all` rewrote the groups: `self-named-box` to `concept`/`$SelfLookup`, and `background=DominantColor` to `background=stored`/`background=DominantColor`. `witness` without `--file` reports no unseparated pair and no unshown case. With `--file` on witnesses.json, the only finding is `hooked-wire-end`: the concept case's output is not the judged output. That is expected, since the witness stands under `@approximated:`. The final audit is clean, and it skipped no check.
- I built no witness, so I judged no new plausibility or verdict.
- Keywords `objects markers select match` kept: the boxes are objects, the wire ends point at boxes, unlinked boxes are dropped, and a center pairs with the box whose outer color it shares. No new keyword.
- Performance: every run takes 1–2 s, and `deletions` 14 s. I did not read `src/`.

## Unsettled

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
