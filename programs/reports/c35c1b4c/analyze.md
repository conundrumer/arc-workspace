# c35c1b4c

## Concept
- The concept case fits every pair. Its blob color is the color of the largest 4-connected single-color region, and the stored `axis` is H.
- No witness has the verdict `other`.
- Every input shares one invariant: each blob cell right of the vertical midline mirrors a blob cell left of it, so the blob's left half is intact and its right half is damaged. The generator likely draws a blob that is symmetric left to right and then erases cells from its right half. On every input of that kind, union with the mirror gives the same output as copying the left half onto the right. The concept's rule has a relational form, so it is not an approximation.

## Choice points
- `blob-color`: which color is the blob
    - `concept`: the color of the largest single-color region (`one-blob`)
    - `$CommonestColor`: replaces the selection in `one-blob`. The blob color is the color with the most cells, and the model is undefined where two colors tie for the most cells. It fits every pair. Witness `count-beats-blob`: train1 with four noise cells changed to 0, so 0 (35 cells) outnumbers 3 (34) while 3 keeps the largest region. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$StoredBlobColor`: stores the blob color as a parameter, which the concept derives per input. It fails Fit at train1: the blob color is 1 in train0, 3 in train1, 2 in train2 and 9 in test0.
- `region-adjacency`: the adjacency that joins a region
    - `concept`: 4-adjacency (`Components`)
    - `$Adj8`: 8-adjacency (`Components8`), so diagonal contacts join a region. It is undefined where two largest regions tie, as the concept is. It fits every pair. Witness `diagonal-noise-chain`: a 24-cell blob of 1 among random noise, where 0 forms a 26-cell region through diagonal contacts, and the largest 4-connected region is the 1 blob. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: the blob has 29 or more cells, and no noise color forms an 8-connected region as large as the blob.
- `mirror-source`: which cells are mirrored
    - `concept`: every cell of the blob color (`mirror-union`)
    - `$BlobOnly`: replaces `mirror-union`. Only the cells of the largest region are mirrored. It fits every pair, because the only blob-color cells outside the region (train1 col 8, rows 3–7) mirror cells that are already blob. Witness `stray-blob-cell`: train0 with a lone 1 at (1,1), off the blob, whose mirror (1,8) is 8. It breaks no scene claim. Plausibility `ordinary`, because train1 shows blob-color cells outside the largest region. Verdict `concept`.
- `copy-direction`: which way the mirror copies
    - `concept`: both ways, as the union of the blob with its mirror
    - `$OneWay`: replaces `mirror-union`. Blob cells on the stored source side are copied to their mirror cells on the other side, with the parameter `source_side`: DIR_L in place of `axis`. It fits every pair. Witness `damaged-left-half`: train0 with (3,2) set to 0, so the right blob cell (3,7) has no blob cell to its left. The concept restores (3,2), and `$OneWay` leaves it as 0. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks this invariant of the inputs: each blob cell right of the vertical midline mirrors a blob cell left of it.
        - `target-cells`: what happens to the blob cells already on the target side
            - `concept`: they are kept
            - `$Replace`: the target side's blob cells become exactly the mirror of the source side's blob cells. The model is undefined where a target-side blob cell has no counterpart on the source side, because no color is given for the cleared cell. It fits every pair. No witness exists where it is defined: on every input where it is defined, the target side lies within the mirror of the source side, so it gives the output of `$OneWay` and of the concept. It is subsumed by `$OneWay`, so it fails Subsumption. Witness `damaged-left-half`, where the model is undefined. Plausibility `variant`, verdict `concept`.
- `mirror-axis`: the axis across which the blob is mirrored
    - `concept`: the stored `axis`, H
    - `$IntactHalf`: derives the axis per input, replacing the stored `axis`. The axis is the single axis that has a side whose blob cells hold the mirror of every blob cell on the other side, and the model mirrors across that axis. It is undefined where no single axis and side meet that condition. It fits every pair. Witness `turned-blob`: train0's input transposed, so the intact half lies above the horizontal midline. The concept mirrors left to right, and `$IntactHalf` mirrors top to bottom. It breaks no scene claim. Plausibility `variant`, verdict `$IntactHalf`. It breaks this invariant of the inputs: the blob's intact half lies left of the vertical midline. `$IntactHalf` is also undefined on `damaged-left-half`.
    - `$NearestAxis`: derives the axis per input as the one whose mirror adds the fewest blob cells, and is undefined on a tie. It fails Fit at train0: the V mirror adds 4 cells and the H mirror adds 6. It also fails at train1 (a tie at 14) and at test0.
    - `$BothAxes`: mirrors across both axes (the LR, TB and half-turn images). It fails Fit at train0: (2,2), (2,7), (3,1) and (3,8) take 1, and the output leaves them unchanged.
- `mirror-line`: where the mirror line lies
    - `concept`: the grid's midline
    - `$BboxMidline`: the midline of the blob's bounding box. It fails Fit at train0: the box spans cols 1–7, so col 8 rows 4–6 stay unchanged, and the output paints them 1.
- `copy-content`: what is copied
    - `concept`: the blob color only, onto the mirror cells of blob cells
    - `$HalfCopy`: the whole source half, in all its colors, overwrites the other half. It fails Fit at train0: (0,5) takes the 8 of (0,4), and the output keeps 0.
- `blob-color` & `mirror-source`, `blob-color` & `copy-direction`, `blob-color` & `mirror-axis`, `blob-color` & `mirror-line`, `blob-color` & `copy-content`, `region-adjacency` & `mirror-source`, `region-adjacency` & `copy-direction`, `region-adjacency` & `mirror-axis`, `region-adjacency` & `mirror-line`, `region-adjacency` & `copy-content`, `mirror-source` & `copy-direction`, `mirror-source` & `mirror-axis`, `mirror-source` & `mirror-line`, `mirror-source` & `copy-content`, `copy-direction` & `mirror-line`, `copy-direction` & `copy-content`, `mirror-axis` & `mirror-line`, `mirror-axis` & `copy-content`, `mirror-line` & `copy-content`: the two branches' changes applied together
- `blob-color` & `region-adjacency`: no region is read when every cell of the commonest color is mirrored
    - `$CommonestColor` & `$Adj8`: the model of `$CommonestColor` alone. When a case also takes `$BlobOnly`, the mirrored region is the largest 8-connected region of the commonest color.
- `copy-direction` & `mirror-axis`: the source side fixes the axis
    - `$OneWay` & `$IntactHalf`: the model of `$IntactHalf` alone. The derived side replaces the stored `source_side`, and because the other side lies within the mirror of the derived side, copying from that side alone gives the union. `$Replace` & `$IntactHalf` gives the same model.
    - `$OneWay` & `$NearestAxis`: the model of `$OneWay` alone, because the stored `source_side` fixes the axis.
    - `$OneWay` & `$BothAxes`: the model of `$OneWay` alone, for the same reason.

## Open parameters
- none

## Not formed
- The blob color as the color of the grid's center cells: a 10-wide grid has no single center cell, and in train1 the four center cells hold two colors, (4,4) 3 and (4,5) 0, so this reading gives no single color.
- Filling the cells the blob encloses: in train1, the cells the output adds, such as (4,5) and (4,6), connect to the grid edge through (3,7) and (2,7), so this reading adds none of them.

## Tickets filed
- none
