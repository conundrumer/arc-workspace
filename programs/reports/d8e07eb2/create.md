# d8e07eb2

## Departures
- The solver's relation for `card_slots=stored` is `card_cell`, so the witness file names that branch `card_cell=stored`: the stored relation holds the card slots' cells with their colors, and the name follows the relation.
- `$WholeStatus` is a top-level `StatusPaint` field of `Choice`. It is not nested under `key_side=stored`: that branch is a `@store` line, and a `Choice` constructor cannot stand under a `@store` line. As a result, the runner reads the `$WholeStatus` branch's model as `$WholeStatus & key_side=derived`. That model is equivalent to the concept, because under the derived key side the status panel is empty. `witness` reports that `whole-status` is no witness of `$WholeStatus`, and that no witness separates `$WholeStatus` from `$StatusBackground` under `key_side=derived`. The model that `analyze.md` means, `$WholeStatus & key_side=stored`, is separated by `whole-status`.
- Combinations that fail a train pair are left out of `impl_choice` through `unfit`: `$IgnoreColor & $UpToD4`, `$IgnoreColor & $Collinear` and `$IgnoreColor & $AllOnLine`. Each fails at train0 (and at other pairs) because ignoring color calls extra card slots.
- `divider_color` is the one color of the full non-background lines, found through `Unanimous`. Where those lines have two colors, every case that derives it is undefined. This makes the `background=DominantColor` witness undefined under `background=DominantColor`, as `witnesses.json` gives.
- The cases are undefined where the key holds no slot ink (`key_cell` is empty), and `$HaloTilingCell` is undefined where no two card bands abut after growth. Rationale: `whole-status` is undefined under the concept (both outer panels hold ink), and `key_side=stored` is undefined on the flipped input, as `witnesses.json` gives.
- On `background=DominantColor`, `$HaloTilingCell` is undefined (the card has one slot, so there is no gap between neighboring bands). `witnesses.json` groups it with the concept. The rule text of `$HaloTilingCell` states this undefinedness.
- On `halo-tiling-cell` (14 by 23) and `key_side=stored`, `slot_bands=stored` gives an output, where `witnesses.json` gives undefined or the concept's grid. The stored band boxes are margins from the 30 by 22 frame, and they cut other slots in another frame. The witness file holds the solver's recorded groups.
- Witnesses added beyond `witnesses.json`: `extra-full-line` (card row 7 filled with 5: the derived divider color clashes and is undefined, and the stored color 6 is defined and loses). It shows `divider_color=stored` defined and differing. My judgment is `foreign concept`: the generator draws no full line other than the dividers. Also added: `swapped-background` (train0 with 8 and 4 swapped: the derived background 4 solves it, and the stored 8 is undefined). It shows `background=DominantColor` defined and differing. My judgment is `variant derived`: a color permutation is a variant task.

## Judgments
- Concept parse: `DividerTiles` over the full lines of the divider color gives the panels. The bands are `Components` over axis-only ink lines, each boxed by `Bbox`. A slot is `compose` of a band across the cut and a band along it. Slot contents are compared as sets with `KeyedSetCompare`: `Ink` members for same color, `Position` members for `$IgnoreColor`.
- `$UpToTranslation` and `$UpToD4` frame each slot's ink in its shape's bounding box. `$UpToD4` compares each D4 image of the key shape. The other geometries take the identity alone, written `d4_compose(D, D, D)` so that no `D4_ID` literal is read.
- `$HaloTilingCell`'s growth is the least k at which two card bands on one axis, each grown by k, abut (`abut`, then `Extremes.low`). This states "half the gap between neighboring bands" with no arithmetic.
- `$WithDiagonals` ranks the card bands with `OrderFrame` and places each slot in a 4 by 4 frame. `Diagonal` keyed by each corner gives the two corner diagonals.
- Hint `common-subexpr` on the two `KeyedSetCompare` instances: kept with `@ignore`. The two instances compare one framing under two member types.
- `deletions`: 41 deletions change nothing. They are guards that the pairs never exercise (`!inked_side(O)`, `key_cell(_, _, _)`, `halo_ready(H)`, the `unfit` rules, `$WithDiagonals`/`$AllOnLine` clauses, `abut` edge tests, `outvoted`). Each guard states a claim of a case, or undefinedness that a witness shows, so none was removed. Some axis columns (`mixed_line.a`, `slot_bands.a`, `uncalled_in.a`, `called_off.a`, `card_band.a`) are constant on the pairs, but they are needed for orientation-free use.
- Keywords: decompose, objects, match, bbox, classify (win/lose renders a class), congruent (`$UpToD4`).
- Determination: `background` is the commonest color of every input, `halo_color` and `win_color` are the color in some output and no input, and `lose_color` is an input color that background cells turn to. The plan reports these four as determined.

## Unsettled
- `halo_margin` has no determination relation. The plan run cap (3 runs) was reached with it still listed (`DivisorRatio exact`). A clause that reads the halo ring's width from the outputs would settle it.
- `audit` stopped at `timeout 120` (exit 124). Its findings (dropped cases, open values, stored facts) are unchecked. An audit run with a longer bound would settle it.
- Store points that `store` printed and the solver does not hold: `card_panel`, `card_slot`, `cut_axis`, `divider`, `halo`, `in_band`, `ink_line`, `inked_side`, `key_panel`, `mixed_line`, `outer`, `panels.*`, `runs.node`, `slot`, `status_cell`, `status_panel`, `band_order.member`, `band_order.pos`, `card_band`. The pairs run took about 60 s, so Rules for one long command applies. Each one would be settled by a `@store` line with its witness, or by an `@ignore: store` reason.
- `$WholeStatus & key_side=derived` is equivalent to the concept. It stays only because `$WholeStatus` cannot be nested under the `key_side=stored` branch. A key-side choice point as a `Choice` constructor, with `StatusPaint` nested under its stored branch, would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
