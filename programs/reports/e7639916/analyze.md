# e7639916

## Concept
- Fits every pair at the stored assignment (`background` 0, `outline-color` 1). The concept outlines the bounding box of every non-background cell and keeps those cells. Each claim has a relational form, so no approximation is needed.
- No witness with verdict `other` was found.

## Choice points
- `mark-set`: which cells are the marks whose box is outlined
    - `concept`: every cell that is not `background`
        - `background`: the field color
            - `concept`: stored, 0
            - `background=DominantColor`: derived as the commonest color of the input; it replaces the stored `background` of `scattered-marks`; it gives one value on every input with no tie for the commonest color. Fits every pair. Witness `background=DominantColor`: breaks `scattered-marks` (field `background` 0), at the stored assignment, `variant`, verdict `background=DominantColor`; the invariant it breaks is "every input's field is 0".
            - `background=SharedColor`: derived as every color of the input; it gives 0 and 8. Fails Fit at train0, where 8 as background makes a second output.
            - `background=RarestColor`: derived as the color of fewest cells; it gives 8. Fails Fit at train0.
    - `$MarkColorStored`: replaces the marks of `bbox-outline` with the cells of a stored `mark-color` (8), which becomes a parameter. The background is not read. On an input with no cell of `mark-color`, the model returns the input. Fits every pair. Witness `mark-color-other`: breaks `scattered-marks` (`mark-color` 8), at the stored assignment, `variant`, verdict `concept`; the invariant it breaks is "every mark is 8".
        - `mark-color`: where the mark color comes from
            - `concept`: stored, 8
            - `mark_color=RarestColor`: derived as the color of fewest cells in the input. It gives one value on every input with no tie for the fewest cells. Fits every pair. Witness `mark_color=RarestColor`: breaks `scattered-marks` (a cell of a second color), at the stored assignment, `borderline`, verdict `$MarkColorStored`; the invariant it breaks is "every input holds only 0 and 8".
            - `mark_color=DominantColor`: gives 0. Fails Fit at train0.
            - `mark_color=SharedColor`: gives 0 and 8 on one input. Fails Fit at train0.
- `outline-color`: the color of the drawn outline
    - `concept`: stored, 1
    - `outline_color=OutNewColor`: derived as a color in every train output and in no input. On an input alone `ex_out` is empty, so it gives no value and the model is undefined on every input. Fails Fit at train0.
    - `outline_color=AnyOutNewColor`: the same as `outline_color=OutNewColor`. Fails Fit at train0.
- `mark-count`: whether the rule needs a fixed number of marks
    - `concept`: the rule reads no count, and outlines the box of any number of marks
    - `$ExactCount`: adds a condition to `bbox-outline` that the number of marks is `mark-count` (3), which becomes a parameter. The model is undefined on an input with a different number of marks. Fits every pair. The model is defined only where it gives the concept's output, so it is subsumed by the concept case and fails Subsumption. No witness exists on which it is defined and differs. Witness `extra-mark`, where it is undefined: breaks `scattered-marks` (`mark-count` 3), at the stored assignment, `variant`, verdict `concept`; the invariant it breaks is "every input holds three marks".
- `mark-set` & `background`: a case that takes `$MarkColorStored` and `background=DominantColor` has the model of `$MarkColorStored` alone, because that branch reads no background. So `background` stands under the concept branch of `mark-set`.
- `mark-color` & `background`: these points stand under different branches of `mark-set`, so no case takes a non-concept branch at both.
- `mark-set` & `mark-count`, `mark-color` & `mark-count`, `background` & `mark-count`, `mark-set` & `outline-color`, `mark-color` & `outline-color`, `background` & `outline-color`, `outline-color` & `mark-count`: the two branches' changes applied together. Each combination with a derived `outline-color` fails Fit at train0.

## Open parameters
- none

## Not formed
- The outline paints over the marks: train0 output (1,3) keeps 8, so the pairs exclude it.
- The box inside is cleared, so a mark strictly inside the box is erased: no reader of the pairs would take this rule, and no input has a mark inside its box.
- The marks must lie on the box edge, and the model is undefined otherwise: in every pair, at least one mark is a corner and every mark lies on the edge. A reader takes this as a fact about the scene, and the concept already gives the same output wherever this branch is defined.
- `background` or `mark-color` derived by `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs` or `VanishedNewPairs`: each one reads train outputs, so on one input it gives no value, and the model is undefined on every input, like `outline_color=OutNewColor`.
- The outline is drawn with 8-adjacency or as a diagonal shape: the box edges in every output are rows and columns.

## Tickets filed
- none
