# cd3c21df

## Concept
- Fits every pair: in each input, five 4-connected objects sit apart on 0, two pairs of objects are translated copies with the same colors, and the fifth object, cropped to its box, is the output (probe `probe.py`).
- No witness with verdict `other` stands against it, and its rule has a relational form.
- Every unmatched object in the evidence fills its box, every repeated object occurs exactly twice, the unmatched object always holds a color no other object holds, and 0 is the commonest color of every input. These invariants are what the branches below part on.

## Choice points
- `odd-object`
    - `concept`: the one object that no other object copies
        - `match`
            - `concept`: two objects are copies when one is a translate of the other, with the same color at each cell
            - `$CongruentCopy`: replaces the copy relation of `one-unique-object` and `others-repeat` with the same shape and colors up to a D4 transform; undefined where no object or more than one object is unmatched. Fits every pair. Witness `rotated-copy`: breaks `one-unique-object` and `others-repeat`; plausibility `variant`, breaking the invariant that each copy is a translate; verdict `any`.
            - `$ColorSetCopy`: replaces the copy relation with holding the same set of colors, whatever the shape; undefined where no object or more than one object is unmatched. Fits every pair. Witness `shared-color-odd`: breaks `one-unique-object`; plausibility `foreign`, breaking the invariant that one object alone lacks a copy; verdict `any`.
            - `$RecolorCopy`: replaces the copy relation with the same shape and the same color pattern up to a renaming of colors; undefined where no object or more than one object is unmatched. Fits every pair. Witness `recolored-copy`: breaks `one-unique-object` and `others-repeat`; plausibility `variant`, breaking the invariant that copies share their colors; verdict `any`.
            - `$ShapeCopy`: replaces the copy relation with the same footprint, colors ignored. Fails Fit at train1, where the 7 block and the two 8/2 checkers share one 2×2 footprint and no object is unmatched (also at train2).
        - `copy-count`
            - `concept`: every other object has one or more copies
            - `$PairedOthers`: replaces `others-repeat` with each other object having exactly one copy, and the output is the one object outside every pair; undefined where an object occurs three or more times. Fits every pair. It fails Subsumption: where it is defined, the one object outside a pair is the one object with no copy, so its output is the concept's. Witness `triple-copies` (the branch is undefined on it, and no witness where it is defined exists): breaks no scene claim; plausibility `variant`, breaking the invariant that each repeated object occurs exactly twice; verdict `concept`.
    - `$OwnColor`: replaces `one-unique-object` and `others-repeat` with picking the one object that holds a color no other object holds; undefined where no object or more than one object holds such a color. Fits every pair. Witness `shared-color-odd`: breaks `one-unique-object`; plausibility `foreign`, breaking the invariant that one object alone lacks a copy; verdict `any`.
- `adjacency`
    - `concept`: an object is a 4-connected group
    - `$Adjacency8`: replaces the 4-connected objects of `objects-on-background` with 8-connected objects. Fits every pair. Witness `diagonal-object`: breaks `objects-on-background` (two 5 cells meet at a corner) and `one-unique-object`; plausibility `variant`, breaking the invariant that every object is 4-connected and no objects meet at a corner; verdict `$Adjacency8`.
- `box-fill`
    - `concept`: the cells of the box outside the object take `background`
    - `$CropInput`: replaces `crop-unique` with the input's cells under the object's box. Fits every pair. Witness `nested-in-box`: breaks no scene claim; plausibility `borderline`, breaking the invariant that the unmatched object fills its box; verdict `concept`.
- `background`
    - `concept`: `background` stored, 0
    - `background=DominantColor`: `background` derived as the commonest color of the input; undefined where it gives no single object without a copy. Fits every pair. Witness `background=DominantColor`: breaks no scene claim; plausibility `borderline`, breaking the invariant that 0 is the commonest color of each input; verdict `concept`.
    - `background=SharedColor`: `background` derived as each color of the input; with every color background there are no objects, so it is undefined on every input. Fails Fit at train0.
    - `background=VanishedColor`: with `ex_out` empty, it derives each color of the input, as `background=SharedColor` does. Fails Fit at train0.
    - `background=RarestColor`: `background` derived as the rarest color of the input. Fails Fit at train0, where it takes 2 as background, and the 0, 5 and 4 cells join into one object whose box is the whole grid.
- `odd-object` & `adjacency`, `odd-object` & `box-fill`, `odd-object` & `background`, `match` & `copy-count`, `match` & `adjacency`, `match` & `box-fill`, `match` & `background`, `copy-count` & `adjacency`, `copy-count` & `box-fill`, `copy-count` & `background`, `adjacency` & `box-fill`, `adjacency` & `background`, `box-fill` & `background`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A rank over object size or color count picks the output: in train0 the objects have 5, 5, 3, 3 and 4 cells, and every object has one color, so no extremum gives the 4-cell 2 bar. No such rule reads these pairs.

## Tickets filed
- 10-604_task_cd3c21df_analyze.md
