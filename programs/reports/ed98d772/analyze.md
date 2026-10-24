# ed98d772

## Concept
- Fits every train pair and the test pair (`work/task/ed98d772/check_concept.py`). No witness has verdict `other`. The rule `quadrant-copies` is exact, not an approximation: the generator places the input under a fixed D4 transform in each quadrant of a frame twice its side. The concept is undefined on a non-square input, because a quarter-turned copy could not fill the same quadrant shape. Train0's input has no symmetry, so train0 alone fixes the D4 element of each quadrant: TL `D4_ID`, TR `D4_CC`, BL `D4_HT`, BR `D4_CW`.

## Choice points
- `tile-transforms`: how each quadrant's transform is given
    - `concept`: a stored table `quadrant_transform`, keyed by corner (a payload over DiagDir)
    - `$SuccessiveTurns`: replaces the table in `quadrant-copies`. The quadrants, taken in the order that starts at corner `order_corner` (`DIAG_TL`) with primary axis `order_axis` (`AXIS_V`), which is reading order, each turn one more quarter turn in sense `turn_sense` (`SENSE_CC`) than the quadrant before. Parameters: `order_corner`, `order_axis`, `turn_sense`. Undefined where the concept is undefined (non-square inputs). Standing: fits every pair. Witness `mirror-tile` stands at the assignment that sets `quadrant_transform` BR → `D4_LR`. That assignment changes none of this branch's parameters, and the branch is defined there. It breaks no scene claim. Plausibility `ordinary`: a table entry that no sequence of turns gives breaks no regularity of the inputs. Verdict `concept`.
    - `$StepProduct`: replaces the table in `quadrant-copies`. The quadrant at `anchor` (`DIAG_TL`) holds the input as it is. The quadrant one column over applies `col_step` (`D4_CC`), the quadrant one row over applies `row_step` (`D4_HT`), and the diagonal quadrant applies their composition (`D4_CW`). Parameters: `anchor`, `col_step`, `row_step`. Undefined where the concept is undefined. Standing: fits every pair. Witness `mirror-tile`, at the same assignment: BR → `D4_LR` is not the composition of the two steps. It breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$CornerTurns`: replaces the table in `quadrant-copies`. Each quadrant holds the input under the rotation that carries the anchor corner (TL) to that quadrant's corner, as in 46442a0e: TR `D4_CW`, BR `D4_HT`, BL `D4_CC`. Standing: fails Fit at train0. It puts `9 0 9 / 9 0 9 / 0 0 9` at output rows 0–2, cols 3–5, where the pair has `9 0 0 / 9 0 9 / 9 0 9`, and it also misses at BL and BR. It fails every other pair too.
- `output-frame`: where the output frame and quadrant size come from
    - `concept`: derived. The output side is twice the input side, and each quadrant is the input's size.
    - `$StoredFrame`: replaces the derived frame in `quadrant-copies` with a stored 6×6 frame (ConstOutDim) cut into 3×3 quadrants. Undefined on every input that is not 3×3. Standing: fits every pair. Witness `$StoredFrame`, a 4×4 input, stands at the stored assignment: no reassignment makes the branch defined there and different from the concept. It breaks `square-input` (`n` = 3) and the invariant that every input is 3×3. Plausibility `variant`, verdict `concept`. It fails Subsumption: wherever it is defined its output is the concept's, and it is not equivalent to the concept.
- `tile-transforms` & `output-frame`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A reflection, or any D4 element other than the stored one, at some quadrant: train0's input has no symmetry, so every other element gives a different tile there and fails Fit at train0.
- A stored mark color, or a recoloring of the marks: the output copies the input's colors unchanged. The mark color differs across pairs (9, 3, 3, 8, 7, test 6), so any stored color fails Fit.
- A tile count derived from the input (n by n copies, as in 007bbfb7): with n = 3 this gives a 9×9 output, while every output is 6×6, so it fails Fit at every pair.
- A `@derive` of `quadrant_transform` by TileD4: TileD4 reads train outputs. Run on one input with `ex_out` empty it gives no rows, so the derived branch is undefined on every input and fails Fit (`@ignore: derive`).

## Tickets filed
- none
