# b91ae062

## Concept
- Fits every pair: k is 2, 2, 3, 3, 4 on the train pairs and 4 on the test, which is each input's count of distinct non-`background` colors, and each output is its input scaled by k.
- No witness has the verdict `other`. The concept file's rules state the rule as the generator applies it.
- On an input that holds only `background`, k is 0 and the model is undefined. The generator does not produce that input.

## Choice points
- `scale-source`
    - `concept`: k is read from a count over the input.
    - `$ConstScale`: replaces `scale-factor-is-color-count` with one stored k for every input (the `ScaleRatio` proposer's value). Undefined on no input. Fails Fit at train2: the stored k is 2 from train0, and train2 scales by 3.
        - none
    - Under `concept`:
        - `count-to-scale`
            - `concept`: k is the count itself.
            - `$ScaleTable`: replaces `scale-factor-is-color-count` with a stored table `scale_by_count` from count to k, {2→2, 3→3, 4→4}. Undefined on an input whose count has no entry. Fits every pair, because the test count 4 is a train count (train4). Witness `table-entry-off-count`: the input `5 0 0 / 0 8 5 / 0 0 0` at the assignment `scale_by_count` {2→3, 3→3, 4→4}, where the concept gives 6×6 and `$ScaleTable` gives 9×9. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
        - `counted-item`
            - `concept`: content other than `background`.
            - `$AllColorCount`: replaces `scale-factor-is-color-count` with the count of every distinct color in the input, `background` included, and has no `background` parameter (the reading of the peer solver d4b1c2b1). Undefined on no input. Fails Fit at train0: 3 colors, k 2.
            - Under `concept`:
                - `counted-unit`
                    - `concept`: distinct colors.
                    - `$CellCount`: replaces `scale-factor-is-color-count` with the count of non-`background` cells (the reading of the peer solver ac0a08a4). Undefined on an input with no non-`background` cell. Fails Fit at train0: 4 cells, k 2.
                - `background`
                    - `concept`: stored, 0.
                    - `background=DominantColor`: derives `background` on each input as its most common colors, ties included. Undefined on no nonempty input. A derived `background` is always a color that the input holds, so on every input the count is the number of distinct colors less one. Fits every pair. Witness `background=DominantColor`: the input `1 2 1 / 2 1 2 / 1 2 1` at the stored assignment, where the concept gives the input scaled by 2 and this branch gives the input unchanged. It breaks `colored-cells-on-background`. Plausibility `borderline`, verdict `concept`. Invariant of the inputs it breaks: every input holds at least four cells of 0.
                    - `background=SharedColor`: derives `background` on each input as every color that the input holds. The count is the number of distinct colors less one on every input, so its model is equivalent to the model of `background=DominantColor`. Fits every pair. Fails Equivalence, because the two take equal counts of non-concept branches.
                    - `background=RarestColor`: derives `background` on each input as its least common colors, ties included. Same standing as `background=SharedColor`: equivalent to `background=DominantColor`, fails Equivalence.
- `count-to-scale` & `counted-item`, `count-to-scale` & `counted-unit`, `count-to-scale` & `background`, `counted-unit` & `background`: the two branches' changes applied together.
    - `$ScaleTable` & `$AllColorCount` keys the table by the all-color count, {3→2, 4→3, 5→4}. It fits, and it is equivalent to `$ScaleTable` & `background=DominantColor`, whose count is always the all-color count less one. Both take two non-concept branches, so one of them fails Equivalence.
    - `$ScaleTable` & `$CellCount` fails Fit at train2: train0 maps 4 cells to 2, and train2 maps 4 cells to 3.

## Open parameters
- none

## Not formed
- k as a count of same-color objects (4- or 8-adjacency), of all non-`background` objects, or of occupied rows or columns: `work/task/b91ae062/probe_counts.py` shows that none of these counts gives k on every pair. Each count either differs from k on train0 or train1, or gives one value with two different k: the 4-adjacency count is 4 at train1 (k 2) and at train2 (k 3). So neither the identity nor a table fits.

## Tickets filed
- none
