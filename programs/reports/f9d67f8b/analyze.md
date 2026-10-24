# f9d67f8b

## Concept
- The concept fits every pair (probe `work/task/f9d67f8b/probe.py`). Train pairs 0–3 need only the row/column mirrors, with sums 31: the 30×30 grid is a 32×32 two-way mirror picture with its last two rows and columns cut off. Test0 rows 0–1, cols 13–18 have no visible mirror image (each one is covered or outside the grid), and the diagonal fallback restores them correctly. So the diagonal rule is fixed only by the test, and no train pair shows it.
- The picture is diagonal symmetric only on cells that have exactly one coordinate in the band 8–23 (`diag_band`, a scene parameter). It is not diagonal symmetric in the middle band or in the corners.
- Witness `full-orbit-cover` (verdict `other`, plausibility `borderline`): when a covered cell's whole mirror orbit is covered inside the middle band, the concept takes the diagonal image and gets 16 cells wrong. The generator pairs this input with the uncovered picture. The input breaks the invariant that every covered cell has a visible mirror image or a visible diagonal image with exactly one coordinate in the band. It breaks no scene claim.
- The rule as the generator applies it: a covered cell shows the hidden picture cell. The concept's diagonal fallback matches that only on band-edge cells.

## Choice points
- `restore-symmetries` (which images a covered cell restores from)
    - `concept`: the visible row-mirror, column-mirror and half-turn images first, then the diagonal coset about the mirror center; undefined where the images it uses disagree or none is visible
    - `$MirrorsOnly`: replaces `diagonal-restore` with nothing; undefined where a covered cell has no visible mirror image. Fails Fit at test0 (rows 0–1, cols 13–18).
    - `$FullOrbit`: replaces `mirror-restore` and `diagonal-restore` with one rule: take the color that every visible image in the D4 orbit about the center shares; undefined where they disagree. Fails Fit at train0, where it is undefined because the middle band is not diagonal symmetric.
    - `$DiagFirst`: replaces `diagonal-restore` so that the diagonal coset comes before the mirrors. Fails Fit at train0 (wrong cells in the middle band).
    - `$DiagBand`: replaces `diagonal-restore` with a version that applies only when the cell has exactly one coordinate in `diag_band`, which becomes a parameter (8–23); undefined at other covered cells that have no visible mirror image. Fits every pair. Its model is subsumed by the concept's, so it fails Subsumption. It has no witness on which it is defined and differs from the concept. Witness `full-orbit-cover`: it is undefined there, plausibility `borderline`, verdict `other`.
- `mirror-center` (where the mirror sums come from)
    - `concept`: stored `mirror_sum_v` = `mirror_sum_h` = 31
    - `$DerivedCenter`: replaces the stored sums, and the claim `mirror-picture` as a fixed claim, with a derivation: on each axis, the one sum at which the uncovered cells are mirror symmetric. Undefined where no sum or more than one qualifies. It derives 31 on both axes for every pair, so it fits every pair. Witness `shifted-center` stands at the stored assignment: the train0 picture cropped two rows and two columns further in (sums 27). The concept is undefined there. Plausibility `variant`, verdict `$DerivedCenter`. It breaks the scene claim `mirror-picture` at sum 31 and the invariant that the mirror sums are 31.
- `mask-color`
    - `concept`: stored `mask_color` = 9
    - `mask_color=RarestColor`: derives the rarest color of each input. Fails Fit at train1 (rarest is 3).
    - `mask_color=DominantColor`: derives the commonest color of each input. Fails Fit at train0 (6 and 5).
- `restore-symmetries` & `mirror-center`, `restore-symmetries` & `mask-color`, `mirror-center` & `mask-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- An order of precedence between the row mirror and the column mirror when their visible images disagree: the program would have to tell the axes apart, which no task orientation calls for, and the scene claim `mirror-picture` rules out any disagreement. The concept is undefined there.
- `mask_color` derived by SharedColor, VanishedColor, ChangedColor or UnchangedColor under `@derive`: on one input with `ex_out` empty, each of these gives every color of the input or none, so the model is undefined on every pair.
- The mask color derived by clauses as the color whose cells break the mirror symmetry: a covered cell and its visible image break the symmetry together, so no clause that ignores color can tell which of the two is covered.
- A separate diagonal-axis parameter: the diagonal the concept uses passes through the mirror center, and with both mirrors the two diagonals give the same coset, so `mirror_sum_v` and `mirror_sum_h` already fix it.

## Tickets filed
- none
