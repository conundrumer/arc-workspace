# dc0a314f

## Concept
- Fits every pair: each covered cell restores from its uncovered images under the eight symmetries of the square about the grid center, and the output is the cover's rectangle (`work/task/dc0a314f/probe.py`).
- `symmetry` is determined by the inputs alone: it is the largest subgroup of D4 under which every input's uncovered cells agree, which is D4 in each input.
- `cover_color` 3 is the one color that is in every input and in no train output.
- The rule has a relational form and is not an approximation.
- The concept is undefined where a covered cell has no uncovered image, or where its uncovered images disagree.
- Witnesses with verdict `other`: none.

## Choice points
- `symmetry-source`
    - `concept`: the group is the stored `symmetry`
    - `$GroupPerInput`: replaces `fill-from-image`: the group is derived on each input as the largest subgroup of D4 under which the uncovered cells agree, and the model is undefined where two subgroups tie for largest. Parameters: `cover_color`. Fits every pair. Witness `two-mirror-axes`, at the stored assignment: breaks `symmetric-pattern`, `variant`, verdict `$GroupPerInput`. It breaks the invariant that every input is symmetric under the two diagonal reflections.
- `center`
    - `concept`: the center of the grid
    - `$CenterStored`: replaces `symmetric-pattern` and `fill-from-image`: the center is a stored point, `center` = the corner shared by cells (7,7) and (8,8). Parameters: `cover_color`, `symmetry`, `center`. Fits every pair. Witness `pattern-overhangs`, at the stored assignment: breaks `symmetric-pattern`, `variant`, verdict `$CenterStored`. It breaks the invariants that every input is 16×16 and that the pattern is centered in the grid.
    - `$CenterFound`: replaces `symmetric-pattern` and `fill-from-image`: the center is found on each input as each point about which the uncovered cells agree under `symmetry` and every covered cell has an uncovered image, and the model is undefined where the found points give different outputs. Parameters: `cover_color`, `symmetry`. Fits every pair (on train1 and train2, two corner points also qualify and give the same output). Witness `off-center`, at the stored assignment: breaks `symmetric-pattern`, `variant`, verdict `$CenterFound`. It breaks the invariant that the pattern is centered in the grid.
- `restore-unit`
    - `concept`: each covered cell restores on its own, from any of its uncovered images
    - `$WholeBlockImage`: replaces `fill-from-image`: the cover restores from the image of its whole rectangle under each non-identity element of `symmetry` whose image lies in the grid and holds no covered cell; those images must agree, and the model is undefined where none exists. Parameters: `cover_color`, `symmetry`. Fits every pair. Witness `stray-cell`, at the stored assignment: breaks `symmetric-pattern`, `borderline`, verdict `any`. It breaks the invariant that every uncovered cell matches each of its uncovered images.
- `image-conflict`
    - `concept`: a covered cell's uncovered images must agree, and the model is undefined where they disagree
    - `$ImageMajority`: replaces `fill-from-image`: a covered cell takes the commonest color among its uncovered images, and the model is undefined at a tie. Parameters: `cover_color`, `symmetry`. Fits every pair. Witness `two-mirror-axes`, at the stored assignment: breaks `symmetric-pattern`, `variant`, verdict `$GroupPerInput`. It breaks the invariant that every input is symmetric under the two diagonal reflections.
- `cover-color-source`
    - `concept`: the stored `cover_color`
    - `cover_color=DominantColor`: replaces `cover-block`: the cover color is the commonest color of the input. Fails Fit at train0 (undefined: no cover rectangle restores).
    - `cover_color=RarestColor`: replaces `cover-block`: the cover color is the rarest color of the input. Fails Fit at train0 (a wrong grid).
    - `cover_color=SharedColor`, `cover_color=VanishedColor`: replace `cover-block`: every color of the input is a cover color. Fail Fit at train0 (undefined: no cell is uncovered).
    - `cover_color=ChangedColor`, `cover_color=UnchangedColor`, `cover_color=OutNewColor`, `cover_color=AnyOutNewColor`: replace `cover-block`: with `ex_out` empty they give no color. Fail Fit at train0 (undefined).
- `output-frame`
    - `concept`: the cover's rectangle
    - `$WholeGrid`: replaces `crop-cover`: the output is the whole restored grid. Fails Fit at train0 (a 16×16 grid in place of a 5×5 one).
- `symmetry-source` & `center`, `symmetry-source` & `restore-unit`, `symmetry-source` & `cover-color-source`, `symmetry-source` & `output-frame`, `center` & `restore-unit`, `center` & `cover-color-source`, `center` & `output-frame`, `restore-unit` & `image-conflict`, `restore-unit` & `cover-color-source`, `restore-unit` & `output-frame`, `image-conflict` & `cover-color-source`, `image-conflict` & `output-frame`, `cover-color-source` & `output-frame`: the two branches' changes applied together
- `symmetry-source` & `image-conflict`: the two branches' changes applied together
    - `$GroupPerInput` & `$ImageMajority`: `$GroupPerInput`'s model alone. Under the derived group, two uncovered images of a covered cell are related by an element of that group, so they always agree.
- `center` & `image-conflict`: the two branches' changes applied together
    - `$CenterFound` & `$ImageMajority`: `$CenterFound`'s model alone. About a found center, two uncovered images of a covered cell always agree.

## Open parameters
- none

## Not formed
- `symmetry` as an open parameter over the other subgroups that fit every pair (the two axis mirrors, the two diagonal mirrors, the four rotations, the half turn alone): every input shows all eight symmetries of the square, so a reader of the concept takes D4. The inputs alone determine D4 as the largest group under which the uncovered cells agree.
- A single-mirror group (the left-right mirror alone, the top-bottom mirror alone, one diagonal mirror alone): the value of `symmetry`, not a branch, and it fails Fit (the top-bottom mirror alone is undefined at train0, the left-right mirror alone at train2).
- A periodic reading (`Wallpaper`): no input is periodic on either axis.
- A cover of some other shape, or several covers: every input has one solid rectangle of the cover color, and the concept restores any covered cell set, so this needs no other program.

## Tickets filed
- `10-811_task_dc0a314f_analyze.md`
