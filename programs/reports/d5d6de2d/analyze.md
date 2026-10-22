# d5d6de2d

## Concept
- Fits every train and test pair (`probe.py`). No witness has the verdict `other`. The rule has a relational form (`Closed` over the `background` cells), and the generator applies it as the concept file states it: every background cell that the outlines close off from the frame edge takes `fill_color`, and every other cell takes `background`.
- Every witness has the verdict `concept`. Each one breaks a scene claim: `outline-shapes` for all but `background=DominantColor`, which breaks `background-field`.

## Choice points
- `hole-scope`: which closed-off cells fill
    - `concept`: each background cell that no walk through background cells reaches from the frame edge, whichever shapes close it off
    - `$PerObject`: replaces `fill-hole`. Shapes are the edge-connected components of the non-background cells, and a background cell fills where one shape alone closes it off from the frame edge. Reads `background`, `fill_color`. Defined on every input. Fits every pair. Witness `two-corners-missing`, at the stored assignment: it breaks `outline-shapes` and the invariant that every outline is a complete border. Plausibility `borderline`, verdict `concept`.
        - `object-region`: which cells of a shape fill
            - `concept`: the cells the shape closes off alone, as `$PerObject` states
            - `$BboxInterior`: replaces `fill-hole`. The background cells of each shape's bounding box fill. Reads `background`, `fill_color`. Defined on every input. Fits every pair. Witness `l-shaped-outline`, at the stored assignment: it breaks `outline-shapes` and the invariant that every shape is a rectangle. Plausibility `borderline`, verdict `concept`.
            - `$InsetBox`: replaces `fill-hole`. Every cell of each shape's bounding box inset by one fills, the shape's own cells included. Reads `background`, `fill_color`. Defined on every input. Fits every pair: a 2-wide solid block has an empty inset. Witness `solid-block-with-center`, at the stored assignment: it breaks `outline-shapes` and the invariant that every solid block is too thin to hold a hole. Plausibility `borderline`, verdict `concept`.
        - `object-adjacency`: which steps join the cells of a shape
            - `concept`: edge steps
            - `$Objects8`: replaces `fill-hole`. Diagonal steps join the cells of a shape as well, so shapes are the 8-connected components. Reads `background`, `fill_color`. Defined on every input. Fits every pair. Witness `four-corners-missing`, at the stored assignment: it breaks `outline-shapes` and the invariant that every outline is a complete border. Plausibility `borderline`, verdict `concept`. There `$Objects8` gives the concept's output, and `$PerObject` fills nothing.
- `walk-adjacency`: which steps a walk to the frame edge takes
    - `concept`: edge steps
    - `$Enclose8`: replaces `fill-hole`. The walk takes diagonal steps as well, so a hole that touches the outside only at a corner is open. Reads `background`, `fill_color`. Defined on every input. Fits every pair. Witness `missing-corner`, at the stored assignment: it breaks `outline-shapes` and the invariant that every outline is a complete border. Plausibility `borderline`, verdict `concept`.
- `wall-cells`: which cells block the walk
    - `concept`: every non-background cell
    - `$WallOutlineOnly`: replaces `fill-hole`. Only `outline_color` cells block the walk, and every cell of another color that is closed off fills. Reads `outline_color` (stored 2), `background`, `fill_color`. Defined on every input. Fits every pair. Witness `box-of-other-color`, at the stored assignment: it breaks `outline-shapes` and the invariant that every shape is in one color. Plausibility `borderline`, verdict `concept`.
        - `outline_color`: where the outline color comes from
            - `concept`: stored, 2
            - `outline_color=RarestColor`: the input's least common color. It is undefined on an input where two colors tie for the lowest count. Fits every pair. Witness `outline_color=RarestColor`, at the stored assignment: it breaks `outline-shapes` and the invariant that every shape is in one color. Plausibility `borderline`, verdict `concept`.
            - `outline_color=SharedColor`: gives 0 and 2 on one input, and at 0 the red ring of train0 is closed off and fills. Fails Fit at train0.
            - `outline_color=DominantColor`: gives 0. Fails Fit at train0, where the red rings fill.
- `background`: where the background comes from
    - `concept`: stored, 0
    - `background=DominantColor`: the input's commonest color. It is undefined on an input where two colors tie for the highest count. Fits every pair. Witness `background=DominantColor`, at the stored assignment: it breaks `background-field` and the invariant that the background is the commonest color. Plausibility `borderline`, verdict `concept`.
    - `background=SharedColor`: gives 0 and 2, so the output on train0 holds a second grid. Fails Fit at train0.
    - `background=RarestColor`: gives 2. Fails Fit at train0.
- `fill_color`: where the fill color comes from
    - `concept`: stored, 3
    - `fill_color=OutNewColor`: reads the train outputs, which a run on one input does not have, so it gives no value and is undefined. Fails Fit at train0.
- `hole-scope` & `walk-adjacency`, `hole-scope` & `wall-cells`, `hole-scope` & `background`, `hole-scope` & `fill_color`, `hole-scope` & `outline_color`, `walk-adjacency` & `wall-cells`, `walk-adjacency` & `background`, `walk-adjacency` & `fill_color`, `walk-adjacency` & `object-adjacency`, `walk-adjacency` & `outline_color`, `wall-cells` & `background`, `wall-cells` & `fill_color`, `wall-cells` & `object-region`, `wall-cells` & `object-adjacency`, `background` & `fill_color`, `background` & `object-region`, `background` & `object-adjacency`, `background` & `outline_color`, `fill_color` & `object-region`, `fill_color` & `object-adjacency`, `fill_color` & `outline_color`, `object-region` & `object-adjacency`, `object-region` & `outline_color`, `object-adjacency` & `outline_color`: the two branches' changes applied together
- `walk-adjacency` & `object-region`: under `$BboxInterior` or `$InsetBox` no walk finds the region, so the walk's steps do not exist there. `walk-adjacency` stands at the concept, because its property exists with the concept branch of `hole-scope`.
    - `$Enclose8` & `$BboxInterior`: the model of `$BboxInterior` alone
    - `$Enclose8` & `$InsetBox`: the model of `$InsetBox` alone

## Open parameters
- none

## Not formed
- The outline kept in the output: every train output sets each outline cell to the background (train0 input (1,1) is 2, and output (1,1) is 0).
- A fill color that depends on the hole's size or shape: every hole in every pair fills with 3, and the holes take several sizes, from 1 cell to 24 cells, and several shapes.
- A derivation of `fill_color` from the input alone: 3 occurs in no input, so every proposer that reads the inputs alone gives 0 or 2, and fails Fit at train0.

## Tickets filed
- 10-715_task_d5d6de2d_analyze.md
