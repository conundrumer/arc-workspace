# fe45cba4

## Concept
- Fits every pair: the plug moves by (2,4) in train0, (-1,4) in train1 and (3,9) in test0, and the translation is unique each time (`work/task/fe45cba4/check_concept.py`, `work/task/fe45cba4/probe.out`).
- How the generator applies the rule: it cuts a solid rectangle into a plug (the near column plus the notch filling) and a notched piece, leaves the notched piece where the rectangle was, against the right edge, and puts the plug against the left edge; the output puts the rectangle back together. On every input the generator produces, the concept's rule (the one translation of the left piece that is disjoint from the right piece and makes their union a solid rectangle) gives that output.
- No witness has verdict `other`.
- The side the moving piece lies on is task data (`mover_side`). The only branch that finds the mover without it is `$NotchedStays`, and its witness `lock-on-key-side` has verdict `$NotchedStays`, at plausibility `variant`.

## Choice points
- `background`
    - `concept`: stored `background` 7
    - `background=DominantColor`: derives `background` as the commonest color of the input; replaces `background-field`. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: a 9 block across the top makes 9 the commonest color, so the derived background turns the plug's old cells 9 where the concept turns them 7. Breaks no scene claim; stands at the stored assignment; plausibility `borderline`; verdict `concept`. It breaks the invariant that 7 is the commonest color of every input.
    - `background=SharedColor`: derives every color of the one input it reads, so no non-background cell is left; replaces `background-field`. Undefined on every input. Fails Fit at train0.
    - `background=RarestColor`: derives the rarest color of the input (9 in train0); replaces `background-field`. Fails Fit at train0.
- `mover`
    - `concept`: the piece toward `mover_side` (left) moves and the other piece stays (`key-on-mover-side`)
    - `$NotchedStays`: the piece that stays is the one whose bounding-box gap reaches no corner of its bounding box, and the other piece moves; replaces `key-on-mover-side` and reads no `mover_side`. Undefined where both pieces, or neither, have such a gap. Fits every pair. Witness `lock-on-key-side`: breaks no scene claim; stands at the stored assignment; plausibility `variant`; verdict `$NotchedStays`. It breaks the invariant that every notched piece touches the right edge and every plug the left edge.
    - `$SmallerMoves`: the piece with fewer cells moves; replaces `key-on-mover-side`. Undefined where the two pieces are the same size. Fails Fit at train0, where both pieces have 8 cells.
- `pair-colors`
    - `concept`: exactly one color comes in two pieces, and only that pair is plugged (`one-pair-color`)
    - `$EveryPairColor`: every color that comes in two pieces is plugged; replaces `one-pair-color`. Undefined where a color has more than two pieces. Fits every pair. Witness `two-pair-colors`: breaks `one-pair-color`; stands at the stored assignment; plausibility `variant`; verdict `$EveryPairColor`. It breaks the invariant that exactly one color comes in two pieces.
- `placement`
    - `concept`: the plug is translated onto the lock (`plug-key`)
        - `fit-test`
            - `concept`: the translation is the one at which the union of the plug and the lock is a solid rectangle (`pieces-interlock`)
            - `$FillsNotch`: the translation is the one at which the plug, disjoint from the lock, covers every cell of the lock's bounding-box gap; replaces `pieces-interlock` and `plug-key`. Undefined where the lock has no gap, or where no such translation exists or more than one does. Fits every pair. Witness `key-with-spur`: breaks `pieces-interlock`; stands at the stored assignment; plausibility `borderline`; verdict `$FillsNotch`. It breaks the invariant that the plug and the lock together make a solid rectangle.
        - `translation`
            - `concept`: any translation
            - `$RowAlignedSlide`: the plug only slides along its rows; replaces `plug-key`. Undefined where no translation along the rows interlocks. Fails Fit at train0, where the plug has to move down 2 rows.
    - `$AreaRectangle`: the pair's color is painted as a solid rectangle on the lock's rows, flush with the lock's side away from the plug, as wide as the pair's cell count divided by the lock's height, and the plug is erased; replaces `plug-key`. Undefined where the lock's height does not divide the count, or the rectangle leaves the grid. Fits every pair. Witness `key-caps-lock`: breaks no scene claim; stands at the stored assignment; plausibility `borderline`; verdict `concept`. It breaks the invariant that the plug adds only the rectangle's near column plus the notch filling, so the lock spans the rectangle's full height.
- `key-origin`
    - `concept`: the plug's original cells become `background` (`erase-key`)
    - `$KeyKept`: the plug stays where it was as well as being plugged; replaces `erase-key`. Fails Fit at train0.
- `background` & `mover`, `background` & `pair-colors`, `background` & `placement`, `background` & `fit-test`, `background` & `translation`, `background` & `key-origin`, `mover` & `pair-colors`, `mover` & `placement`, `mover` & `fit-test`, `mover` & `translation`, `mover` & `key-origin`, `pair-colors` & `placement`, `pair-colors` & `fit-test`, `pair-colors` & `translation`, `pair-colors` & `key-origin`, `placement` & `key-origin`, `fit-test` & `translation`, `fit-test` & `key-origin`, `translation` & `key-origin`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `background` derived by OutNewColor, AnyOutNewColor, VanishedColor, ChangedColor, UnchangedColor: each reads train outputs. A `@derive` branch reads one input and no output, so on any input these give no color, or every color of the input, and the model is undefined.
- Several interlocking translations, with the output holding each one: on every input exactly one translation interlocks (`pieces-interlock`), and no reading of the concept chooses among several.
- The notched piece moves onto the plug, with the plug staying put: this is the concept at `mover_side` right. The pairs separate it from left, so it is a value the pairs fix and not a branch.

## Tickets filed
- none
