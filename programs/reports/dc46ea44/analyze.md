# dc46ea44

## Concept
- The concept fits every pair, train0–2 and test0, with no `alt` on any pair.
- No witness has the verdict `other`.
- Each rule has a relational form, and the concept file's rules are the rules as the generator applies them, with no approximation.
- `hang_corner` is derived data: the corner of the object's box that lies on the tip is the one away from `lift_dir` and away from `tip_dir`, and in every D4 variant task it follows from those two parameters.
- `hook_shape` is written at `lift_dir` up and `tip_dir` left, and a branch that reads it places it by those two parameters.

## Choice points
- `hook-identity`
    - `concept`: the hook is the cells of the stored color `hook`
    - `$HookByShape`: replaces `hook`; the hook is the object of the stored shape `hook_shape`, placed by `lift_dir` and `tip_dir`, and `hook` is not read; adds the parameter `hook_shape`; undefined where no object or more than one object has that shape. Fits every pair. Witness `hook-color-swapped` (train0's input with 6 and 2 swapped): breaks the scene claim `hook`, at the stored assignment, `variant`, verdict `$HookByShape`; it breaks the invariant that the hook is 6 in every input.
    - `$HookLarger`: replaces `hook`; the hook is the one of the two non-background, non-divider colors of the hook's half with more cells, and `hook` is not read; undefined where the two counts are equal. Fits every pair. Witness `large-object` (a staircase object of six cells beside the hook of five): breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
- `hook-travel`
    - `concept`: `hook-across`, a translation by one half plus the divider
    - `$LiftToEdge`: replaces `hook-across`; the hook slides toward `lift_dir` until it meets the frame edge; undefined nowhere the concept is defined. Fits every pair. Witness `hook-off-divider` (train0's input with the hook one row lower): breaks no scene claim, at the stored assignment, `borderline`, verdict `concept`; it breaks the invariant that the hook's stem starts in the row next to the divider.
    - `$LiftMirror`: replaces `hook-across`; the hook is reflected across the divider. Fails Fit at train0.
- `tip-cell`
    - `concept`: the tip is the hook's cell farthest toward `tip_dir`
    - `$TipByOffset`: replaces the tip in `hang-object`; the tip is the cell two steps toward `lift_dir`'s opposite and two steps toward `tip_dir` from the stem's cell farthest toward `lift_dir`, a stored offset; adds the parameter `tip_offset`. Fits every pair. Witness `hook-long-stem` (train0's input with a stem of four cells): breaks the scene claim `hook` (`hook_shape`), at the stored assignment, `variant`, verdict `concept`; it breaks the invariant that the stem has three cells.
- `layering`
    - `concept`: the object is drawn over the hook
    - `$HookOverObject`: replaces the drawing order in `hang-object`; the hook is drawn over the object. Fails Fit at train0, at (2,8).
- `anchor`
    - `concept`: the corner of the object's bounding box lies on the tip
    - `$AnchorCell`: replaces `hang-object`'s anchor; the object's cell farthest away from `lift_dir`, and of those the one farthest away from `tip_dir`, lies on the tip. Fails Fit at train2.
- `source-half`
    - `concept`: `clear-source`
    - `$CopyAcross`: replaces `clear-source`; the hook's half stays as it is. Fails Fit at train0.
- `background`
    - `concept`: stored, 7
    - `background=DominantColor`: the background is the commonest color of the input; replaces the stored value in `background`. Fits every pair. Witness `background=DominantColor` (train0's input on a 9 field): breaks the scene claim `background`, at the stored assignment, `variant`, verdict `background=DominantColor`; it breaks the invariant that the background is 7 in every input.
- `divider`
    - `concept`: stored, 4
    - `$DividerDerived`: replaces the stored color in `divider`; the divider is the one full row of one color that is not background; undefined where no such row or more than one exists. Fits every pair. Witness `divider-recolored` (train0's input with a 3 divider): breaks the scene claim `divider`, at the stored assignment, `variant`, verdict `$DividerDerived`; it breaks the invariant that the divider is 4 in every input.
- `lift_dir`
    - `concept`: stored, up
    - `$LiftTowardEmpty`: replaces the stored value in `divider` and `hook-across`; `lift_dir` is the direction from the half that holds content to the half that is all background; undefined where both halves or neither are all background. Fits every pair. Witness `content-above` (train0's input flipped top to bottom): breaks the scene claim `divider`, at the stored assignment, `variant`, verdict `$LiftTowardEmpty`; it breaks the invariant that the hook and the object lie below the divider.
- `tip_dir`
    - `concept`: stored, left
    - `$TipSideDerived`: replaces the stored value in `hook` and `hang-object`; `tip_dir` is the side of the stem, the hook's column with the most cells, on which the hook's other cells lie; undefined where they lie on both sides. Fits every pair. Witness `hook-mirrored` (train0's input flipped left to right): breaks the scene claim `hook`, at the stored assignment, `variant`, verdict `$TipSideDerived`; it breaks the invariant that the tip lies left of the stem.
- `hang_corner`
    - `concept`: derived from `lift_dir` and `tip_dir`
    - `hang_corner=stored`: replaces the derived corner in `hang-object`; the corner is stored, bottom-right. Fits every pair. Witness `hang_corner=stored` (train0's input flipped top to bottom): breaks no scene claim at the assignment it stands at, `lift_dir` down, `variant`, verdict `concept`; it breaks the invariant that the hook and the object lie below the divider.
- `hook-identity` & `hook-travel`, `hook-identity` & `tip-cell`, `hook-identity` & `background`, `hook-identity` & `divider`, `hook-identity` & `lift_dir`, `hook-identity` & `tip_dir`, `hook-identity` & `hang_corner`, `hook-travel` & `tip-cell`, `hook-travel` & `background`, `hook-travel` & `divider`, `hook-travel` & `lift_dir`, `hook-travel` & `tip_dir`, `hook-travel` & `hang_corner`, `tip-cell` & `background`, `tip-cell` & `divider`, `tip-cell` & `lift_dir`, `tip-cell` & `tip_dir`, `tip-cell` & `hang_corner`, `background` & `divider`, `background` & `lift_dir`, `background` & `tip_dir`, `background` & `hang_corner`, `divider` & `lift_dir`, `divider` & `tip_dir`, `divider` & `hang_corner`, `lift_dir` & `tip_dir`, `lift_dir` & `hang_corner`, `tip_dir` & `hang_corner`: the two branches' changes applied together
    - Under `$HookByShape` & `$TipSideDerived`, the hook is the object that has `hook_shape` at either side, and `tip_dir` is the side at which it has it.
- `layering`, `anchor` and `source-half` with any other point: no case takes a non-concept branch at them, since each of their non-concept branches fails Fit.

## Open parameters
- none

## Not formed
- A derivation of `hook` by a proposer: no proposer gives 6 alone on an input. `SharedColor` gives every color of the input, `DominantColor` gives 7, and `RarestColor` gives the object's color. `$HookByShape` and `$HookLarger` find the hook by clauses.
- Another orientation type for the divider, a column with `lift_dir` left or right: that is the same `lift_dir` parameter at another value, and needs no change to the program.
- More than one other object in the hook's half: no input shows a second object, and no reading of the pairs says where a second object would hang.

## Tickets filed
- none
