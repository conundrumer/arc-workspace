# e39e9282

## Departures
- The branch `pin_depth=stored` has no case. In the witness file, its name is gone from every group, and the witness `pin_depth=stored` is renamed `keep-box-tall`. That witness still separates the concept from `$PinJumpsEdge` and `$PinNearFarEdge`: `store` reports no derived relation for the middle line's depth, so the `$Middle` clause has no `@store` point. That clause states the middle line directly, as the cells at equal distance from the box's two edges across the pin's line, which is the principled form of `pin-to-middle`, so it carries no `@workaround` line.
- `$PinNearFarEdge` is a branch that `analyze.md` lists only under Not formed: a pin of a `keep_color` box lands on the box cell next to the far edge. Develop step 3 forms each Not formed interpretation that states one model. This one fits every pair and has a relational form. The witness `keep-box-wide` separates it, because on the 5×5 box it lands at col 5. `keep-box-tall` also separates it, at row 4.
- `bg=DominantColor` and `pin=RarestColor` are `@derive` branches that `derive` reports as fitting (Develop step 4). Their witnesses are the ones `derive` recorded, which swap the color with `0` in train0's input.
- The witness `keep-box-wide` now names the far-edge landing at col 5 in its `separates` text. `record --all` regrouped every witness for the new cases.

## Judgments
- `bg=DominantColor` and `pin=RarestColor` are each `variant derived`. They are `@relaxed background` and `@relaxed pins` respectively. Reason: the witness changes the palette, which happens routinely only in a variant task. In that variant task, the generator pairs the output that the derived color gives. At the stored color, the concept case treats the swapped color as foreign ink.
- The `$PinNearFarEdge` witness `keep-box-wide` is `variant concept`. Reason: a 5×5 box breaks `boxes`, which variant tasks routinely do. The concept's middle-line reading is the one a person takes for a larger box.
- On a `keep_color` box that has no middle line, the concept is undefined, as `analyze.md` gives. The program derives a keep-box pin's output cell only from its move, through `moving`. A pin that lands nowhere therefore leaves its cell without an output.
- The cast pins of `$StrayPinCasts` use the side cell the pin faces, which is the first blocked cell of the cast. With that cell, the `pin-grows` and `$PinJumpsEdge` readings apply to a distant pin as they do to an adjacent one.
- `Reach` is renamed `PinReach`: `Reach` is a lib component name, and the lint rejects it.
- `deletions` hints, judged:
    - `params.box_color` stays because it states `boxes`.
    - The `pin.id` column stays because `$Middle` and `$PinNearFarEdge` read the box through it.
    - `moving` stays because it gives the undefined case above.
    - The branch-only clauses (`stray`, `pin_cast`, the `$StrayPinCasts` pins, and the `$UnpinnedBoxKept` and `$StrayPinErased` clearings) stay because the pairs do not instantiate them.
    - `ex_in` in `survives` stays because it states that the cell keeps its color.
- The single-consumer hint on `pinned` led to inlining that relation into the `$UnpinnedBoxKept` clause.
- The Determine comp derives each color from the train pairs:
    - `bg` is the commonest color of every input.
    - `pin` is the rarest color of every input.
    - `erase` is the color all of whose train cells change.
    - `keep` is the color some of whose train cells change, each of them to the pin color.
- `deletions` ran twice. The second run came after the last simplify edits.

## Unsettled
- `pin_depth=stored`: a solver structure in which one derived relation holds the landing depth on every input, with that relation's value the same on every input of the task, would let `store` give it a `@store` point. A per-box depth or a per-box-size table does not give that structure.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
