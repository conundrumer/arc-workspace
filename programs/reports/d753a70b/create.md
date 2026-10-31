# d753a70b

## Departures
- The concept now reads each shape as the diamond of least radius it fits, which was the reading of `$NearestCenter`. Before, it was undefined wherever a shape fits more than one diamond. The `diamond-outlines` header line says this, and `diamond-choice` is no longer a choice point. This rests on `corner-single-cell`: it has plausibility `ordinary` and verdict `$NearestCenter`, it reassigns nothing, and no open value or approximation disagrees on it. By the Witness step that is a fault in the concept case, and the fix is to make the concept give the judged output.
- `$NearestCenter` is dropped. It fails Equivalence: after the fix its model is the concept's.
- The old reading (undefined when a shape fits two diamonds) is not kept as a branch. It fails Subsumption: it is defined only where the fit is unique, and there it gives the concept's output.
- Witness `corner-single-cell` is removed from the witness file. With `$NearestCenter` gone, every case gives the same output on it, so it separates nothing.
- The names `concept` in `witnesses.json` are rewritten by `record --all`. They now read `$ColorPair`, `$Vanish` and `$Vanish & background=stored`, which are the concept constructors I named and the `@derive` branch forms.
- Running `witness --file witnesses.json` reports these differences, and the fix above accounts for all of them:
    - `$NearestCenter` names no case.
    - On `corner-single-cell`, the concept gives `$NearestCenter`'s grid where `witnesses.json` says it is undefined.
- New witness `background-nine`, a 5x5 field of 9 holding a radius-1 diamond of 2, added because `witness` reported that no run showed `background=DominantColor` defined and differing from `background=stored` at `$ChangeTable`. On the analyze witness, `$ChangeTable & background=DominantColor` is undefined, because 7 becomes a shape color that the table lacks.
    - On `background-nine`, the stored-background cases are undefined: the 9 field is one shape that fits no diamond.
    - The derived background 9 shrinks the diamond to its center.
    - My judgment: plausibility `variant` (a recoloring of the background is a routine variant), verdict `background=DominantColor`.
    - The `@derive` line keeps analyze's `borderline concept`, from its own witness.

## Judgments
- Encoding of diamonds:
    - Taxicab distance follows the draft precedent of `relative` + `diag_dist` + `corner_dist` (aaef0977, d22278a0). It is an inline `taxicab`, so it also measures boxes past the frame.
    - A shape fits a diamond when no shape cell is off the ring (`stray`) and no in-frame ring cell lies outside the shape (`gap`). These are universals via defect negation, over every in-frame center.
- Encoding of the radius change, without arithmetic:
    - The new diamond is found through its vertex toward each direction: `jump(C, D, K)` from the center, then one `neighbor` step in or out (`$ColorPair`), or `jump` by the table's count (`$ChangeTable`).
    - The new radius is the vertex's distance from the center. A vertex past the center (`nearer`) gives no ring under `$Vanish`, and the center cell under `$ShrinkFloor`.
- Encoding of undefinedness: the cells of a shape that the case reads no new diamond for get no `out` fact, so the grid is not total.
    - The concept leaves such a shape where no diamond fits it.
    - `$ChangeTable` also leaves one where the table lacks its color.
    - This is what makes `$ChangeTable` undefined on a color the table lacks, as `analyze.md` states.
- Shapes are `Components8` keyed by `[Key, Color]` inside `Parse`. This follows the `KeyColor` precedent of 0a1d4ef5. One color per component is the `object-unit` concept branch.
- `$MulticolorObjects` is not formed. It fails Fit at train 0, as `analyze.md` states, and `analyze.md` gives it no witness.
- Not formed item "a diamond whose center lies outside the frame" gives no case:
    - For a cell P in the frame, the distance from an off-frame center C is the distance from C's clamp onto the frame plus a constant. So the off-frame clipped ring is the in-frame ring of smaller radius.
    - Under the old unique-diamond reading, it fails Fit at train 2. There the 2 shape is radius 6 around (0,5), and also radius 7 around (-1,5).
    - Under the least-radius concept, it is equivalent to the concept.
- The other Not formed items state no model that meets Fit, or one equivalent to the concept, for the reasons `analyze.md` gives.
- Determine:
    - `background` is the color that has two cells touching along a side, a fact of the inputs alone. No two cells of a diamond do that.
        - My first form kept the color that lies on one side of every changed cell. It drew a `determine prediction` hint, because it read inputs and outputs together, so I replaced it.
    - `shrink_color` and `grow_color` are read from a train input diamond and the same-color output diamond around the same center, by the radius going down or up. This reuses the shared `Parse` over `ex_in` and `ex_out`.
    - `radius_change` is a lookup table. The plan lists it as undecided, and it needs no relation.
    - The sweep found 17 single-row changes of `radius_change` that fit every train output. It is a lookup table and not an open parameter, so nothing was added.
- Hints, each judged and fixed:
    - `common-subexpr`: `past_center` is now the absence of `new_radius`.
    - `single-consumer` on `past_center`: inlined into the `$ShrinkFloor` clause.
    - `single-consumer` on `ring`: inlined as `parse.ring`.
    - `claim` finding: added `@claim diamond-outlines` above `least`.
- Deletions that change nothing on the pairs, all kept:
    - `least.low`, `!nearer`, `unread` and the `$ShrinkFloor` clause handle structure the pairs never have: ambiguous shapes, shrinking past the center, unread shapes and single shrink cells.
    - The two `shape_cell` atoms in `resized` state that the resized diamond keeps its color.
- Simplify:
    - Removed the program wrappers `shape_cell` and `fit` around `parse.*`.
    - Moved the shape color onto `diamond`.
- Keywords `objects rings lookup`. `lookup` is for `$ChangeTable`'s table.

## Unsettled
- The audit skipped the `store` check on `parse.ring`, which has over 20000 rows on an input. It stays open. A store check that handles large relations would settle it.
- Where two output diamonds share a cell, `out` holds two colors there, so the case is undefined. No pair shows this, and a drawing order would need a task that does.
- Ties among least-radius fits draw every tied diamond. No input I know of has one. Proving that in-frame centers never tie at the least radius would settle it.

## Concept faults
- none

## Fixes elsewhere
- `scripts/context.py`, its `section` command: it resolves only handbook docs, so the CLAUDE.md link to `prompts/agents/notes/project-commands.md#project-commands` cannot be printed through it. Either the doc line should say to read the note directly, or the command should accept note links.

## Tickets filed
- none
