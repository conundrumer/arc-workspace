# bb52a14b

## Concept
- The concept case fits every pair (`probe.py`), and every claim it makes has a relational form.
- Fitting branches give no witness with verdict `other`.
- The generator's rule:
    1. The generator draws a 3×3 key of `fill_color` marks and scatter-colored ink.
    2. It places copies of the key's ink, with `background` under the marks, among the scatter cells.
    3. The output fills the marks of each copy.
- The concept file reads the key as the bounding box of the marks. That box is the generator's 3×3 key only when the marks reach all four sides of the 3×3. They do in every pair, and the `key_dim=stored` witness is a key whose marks miss a side.
- Every key box in the evidence holds no `background` cell, and every copy has `background` under each mark offset. In each copy's box, every offset other than the marks holds the key's cell. Scatter cells do touch copies from outside their boxes (train0 input (12,18), (14,18)).
- Of the 35 mark offsets across all copies, none holds a scatter cell. The scatter density is about 0.12, so the generator keeps the copy boxes clear.

## Choice points
- `mark-offset-content`: what a place must hold at the key's mark offsets to count as a copy
    - `concept`: `background` at every mark offset
    - `$AnyUnderMarks`: replaces `bare-copies` and `fill-copies`. A place matches whatever its mark offsets hold, and the fill overwrites them. It needs no parameter of its own and is defined wherever the concept is. It fits every pair.
        - Witness `stray-under-mark`. It breaks `bare-copies`. Plausibility `borderline`, verdict `$AnyUnderMarks`. It breaks this invariant: every occurrence of the key's other cells has `background` at every mark offset.
        - `mark-fill`: what a matched place's mark offsets take when they hold a scatter cell
            - `concept`: `fill_color`, overwriting the scatter cell
            - `$KeepUnderMarks`: replaces `fill-copies`. Only the mark offsets that hold `background` take `fill_color`, and a scatter cell there stays. It is defined wherever its base is. It fits every pair.
                - Witness `stray-under-mark`. It breaks `bare-copies`. Plausibility `borderline`, verdict `$AnyUnderMarks`. It breaks the same invariant as above.
- `blank-offset-content`: what a place must hold at an offset where the key has `background`
    - `concept`: `background`
    - `$InkOnlyMatch`: replaces `fill-copies`. A place needs only the key's ink at the ink's offsets, and any color at the key's `background` offsets. It is defined wherever the concept is. It fits every pair.
        - Witness `stray-in-key-blank`. It breaks `one-key`. Plausibility `variant`, verdict `$InkOnlyMatch`. It breaks this invariant: every cell of the key's box is a mark or ink.
- `copy-orientation`: which transforms of the key a copy may take
    - `concept`: translation only
    - `$CongruentCopies`: replaces `fill-copies`. A copy may be any D4 image of the key's ink, and it is filled with the same image of the marks. It fails Fit at train0: input rows 18–20, cols 19–21 hold a D4 image of the key, and the output leaves it unfilled. Train1 rows 2–4, cols 15–17 and train2 rows 12–14, cols 5–7 also hold such images.
- `copy-surround`: whether cells around a copy matter
    - `concept`: they do not
    - `$IsolatedCopies`: adds a rule that a copy's ring of neighbors is all `background`. It fails Fit at train0: the copy at rows 12–14, cols 19–21 has 8s at (12,18) and (14,18) beside its box.
- `key-extent`: which cells form the key
    - `concept`: the bounding box of the `fill_color` cells
    - `$KeyComponent`: replaces `one-key` and `fill-copies`. The key is the 8-connected component of non-`background` cells that holds the marks, read in its bounding box. It fails Fit at train1: the key's component runs on through (12,6), (12,7), (12,8), (13,8) and (14,5), and the copies have nothing there.
    - `key_dim=stored`: replaces `fill-copies`. It stores the key extent 3×3, and the key is the one 3×3 box that covers every mark and whose other cells are all ink. It is undefined where no such box exists, or more than one. It fits every pair.
        - Witness `key_dim=stored`, at the stored assignment. It breaks no scene claim. Plausibility `borderline`, verdict `key_dim=stored`.
        - The witness breaks two invariants:
            - In every key, the marks reach all four sides of the 3×3 box.
            - No place holds a part of the key's ink without the rest.
        - A key whose marks miss a side alone is likely: about 0.18 per key when 5 of the 9 cells are marks. The divergence also needs a place that holds only part of the key's ink, and only chance among the scatter cells gives one.
- `key-content`: where the key comes from
    - `concept`: read from the input
    - `key=stored`: replaces `one-key` and `fill-copies`. It stores the key's picture. It fails Fit at train1, whose key differs from train0's.
- `fill_color`: the color of the marks and of the fill
    - `concept`: stored, 4
    - `fill_color=RarestColor`: the rarest color of the input. It is undefined where two colors tie for rarest. It fits every pair, since 4 has 4 to 6 cells and each other color has 24 or more.
        - Witness `fill_color=RarestColor`. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks this invariant: `fill_color` is the rarest color of every input.
- `background`: the field color
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input. It is undefined where two colors tie for commonest. It fits every pair.
        - Witness `background=DominantColor`. It breaks `scattered-cells`. Plausibility `foreign`, verdict `concept`. It breaks this invariant: `background` covers more than three quarters of every input.
- `mark-offset-content` & `blank-offset-content`, `mark-offset-content` & `copy-orientation`, `mark-offset-content` & `copy-surround`, `mark-offset-content` & `key-extent`, `mark-offset-content` & `key-content`, `mark-offset-content` & `fill_color`, `mark-offset-content` & `background`, `blank-offset-content` & `copy-orientation`, `blank-offset-content` & `copy-surround`, `blank-offset-content` & `key-content`, `blank-offset-content` & `fill_color`, `blank-offset-content` & `background`, `copy-orientation` & `copy-surround`, `copy-orientation` & `key-extent`, `copy-orientation` & `key-content`, `copy-orientation` & `fill_color`, `copy-orientation` & `background`, `copy-surround` & `key-extent`, `copy-surround` & `key-content`, `copy-surround` & `fill_color`, `copy-surround` & `background`, `key-extent` & `fill_color`, `key-extent` & `background`, `key-content` & `fill_color`, `key-content` & `background`, `fill_color` & `background`: the two branches' changes applied together
- `blank-offset-content` & `key-extent`: `$InkOnlyMatch` & `$KeyComponent` applies both changes
    - `$InkOnlyMatch` & `key_dim=stored`: the model of `key_dim=stored` alone. Its key box holds no `background` cell, so the blank-offset property does not exist under `key_dim=stored`.
- `key-content` & `key-extent`: the model of `key=stored` alone, for each branch of `key-extent`. A stored key has no extent to read from the input, so `key-extent` exists only with the concept branch of `key-content`, and it stands at the concept.

## Open parameters
- none

## Not formed
- `fill_color` derived by `SharedColor`: it proposes every color of the inputs (0, 1, 4 and 8), not one color.
- `fill_color` derived by `OutNewColor`: 4 occurs in every input, so the proposer gives nothing.
- `fill_color` derived by `ChangedColor` or `UnchangedColor`: 0 cells both keep and change their color, and 1, 4 and 8 all keep it. Neither proposer gives one color.
- Copies that overlap each other or the key: no reading the pairs suggest differs here. Every copy box in the evidence is disjoint from the others and from the key.
- A key with no ink, or no marks: the scene places 3 to 5 ink cells and 4 to 6 marks in every key. With no marks there is no key to read, and every case is undefined there alike.

## Tickets filed
- none
