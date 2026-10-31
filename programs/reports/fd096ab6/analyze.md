# fd096ab6

## Concept
- Fits every pair: train0, train1 and test0 (probe `work/task/fd096ab6/probe.py fit`). In every pair, each fragment lies on exactly one inclusion-maximal translated copy of the template, and painting those copies gives the output.
- How the generator applies the rule: it draws the template, draws a translated copy of it in a new color for each fragment, then erases cells of that copy until what is left is a fragment that one copy alone holds. The concept's rule (for each color, the copies whose held cells of that color no other copy strictly exceeds) approximates "the copy the fragment was cut from".
- No witness with verdict `other` stands for the concept case apart from the one `$AmbiguousUndefined` lists.

## Choice points
- `background`
    - `concept`: `background` stored, 1 (`background-field`)
    - `background=DominantColor`: derives `background` as each input's commonest color, replacing `background-field` with "the grid is a field of its commonest color"; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: train0's input with the field recolored to 0. It breaks `background-field` and stands at the stored assignment. Plausibility `variant`; it breaks the invariant that every input's field is 1. Verdict `background=DominantColor`: the derived background completes every fragment on the 0 field, while the stored background counts 0 as a fragment color and is undefined there.
- `template-identity`
    - `concept`: `template_color` stored, 4 (`one-template`)
    - `template_color=SharedColor`: every color of the input is a template color, which replaces `one-template`. Fails Fit at train0: there is no fragment, and the output equals the input.
    - `template_color=DominantColor`: the template is the background field, which replaces `one-template`. Fails Fit at train0, where it is undefined.
    - `template_color=RarestColor`: the template is the input's least-used colors (6, 8 and 3 at train0), which replaces `one-template`. Fails Fit at train0, where it is undefined.
    - `$TemplateLargestObject`: the template is the largest one-colored 8-connected non-background object, and its color plays the template's part; it replaces `one-template` with "the template is the largest object". Undefined where two objects tie for largest. Fits every pair. Witness `template-in-another-color`: train0's input with 4 and 6 swapped. It breaks `one-template` (the shape in 4 is not whole) and stands at the stored assignment. Plausibility `variant`; it breaks the invariant that the whole shape is drawn in 4 in every input. Verdict `$TemplateLargestObject`.
        - `adjacency`
            - `concept`: 8-adjacency
            - `$Adjacency4`: objects by 4-adjacency. Fails Fit at train0: the template splits into parts of 2, 2 and 1 cells, which tie with the 2-cell fragments, so the model is undefined.
    - `$TemplateLargestColor`: the template is the cells of the color with the most non-background cells, which replaces `one-template`. Undefined on a tie. Fits every pair. Witness `fragment-color-outnumbers-template`: train0's input with two more two-cell fragments of 3, so color 3 has 6 cells against the template's 5. It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$TemplateTopmost`: the template is the object reaching the top row first, which replaces `one-template`. Fails Fit at train1: the template and the 6 fragment both reach row 4, so the model is undefined. At test0 the 8 fragment reaches row 1, above the template.
- `fragment-grouping`
    - `concept`: for each fragment color, the copies whose held cells of that color no other copy strictly exceeds (`fragments`, `complete-fragment`)
    - `$FragmentComponents`: a fragment is an 8-connected one-colored component, completed by every copy that holds it all, which replaces `fragments`. Undefined where no copy holds a component. Fails Fit at train0: the 6 fragment (7,15), (9,15) is two components, and each single cell lies on five copies.
    - `$FragmentColorClass`: each color is one fragment, which replaces `fragments`. Undefined where no copy holds all of a color's cells. Fails Fit at test0, where color 2 has two fragments.
    - `$PlacementMostCells`: per color, only the copies that hold the most cells of the color, which replaces `complete-fragment`. Fails Fit at test0: the 2 fragment (21,21), (21,22) is not completed.
    - `$PlacementTwoCells`: every copy that holds at least two cells of the color, which replaces `complete-fragment`. Fails Fit at train0: the 2 fragment's cells (14,16), (14,17) also lie on the copy at offset (10,10).
- `copy-transform`
    - `concept`: copies are translations of the template (`fragments`, `complete-fragment`)
    - `$CopyD4`: copies are any D4 image of the template, translated, which replaces `fragments` and `complete-fragment`. Fails Fit at train0, where the 2-cell fragments lie on many reflected and rotated copies.
- `copy-overlap`
    - `concept`: undefined where a copy covers a cell of another color (`copies-clear`, `keep-input`)
    - `$CopyOverwrites`: the copy's color replaces the input cell, which replaces `keep-input` and `copies-clear`. Fits every pair. Witness `copy-meets-template`: train0's input with the 8 fragment moved to (6,6), (7,7), so its copy covers template cell (5,8). It breaks `copies-clear` and stands at the stored assignment. Plausibility `borderline`; it breaks the invariant that every fragment's copy lies on background apart from its own cells. Verdict `any`.
    - `$InputKept`: the input cell keeps its color, and the copy is drawn only on background, which replaces `copies-clear`. Fits every pair. Its witness is `copy-meets-template` above: `borderline`, verdict `any`.
- `copy-offgrid`
    - `concept`: draws the part of a copy inside the grid (`copies-clear`)
    - `$OffgridUndefined`: undefined where a copy leaves the grid, which replaces `copies-clear`. Fits every pair. Witness `copy-past-edge`: train0's input with the 8 fragment moved to (11,0), (12,1), so its copy reaches (11,-1). It breaks `copies-clear` and stands at the stored assignment. Plausibility `borderline`; it breaks the invariant that every copy lies inside the grid. Verdict `concept`.
- `ambiguous-fragment`
    - `concept`: draws every copy that holds the fragment's cells alike (`complete-fragment`)
    - `$AmbiguousUndefined`: undefined where a fragment's cells lie on more than one copy alike, which replaces `complete-fragment`. Fits every pair. Witness `fragment-fits-several-copies`: train1's input with a 2 fragment at (20,4), (20,5), which lies on three copies. It breaks `fragments` and stands at the stored assignment. Plausibility `borderline`; it breaks the invariant that every fragment lies on one copy alone. Verdict `other`: the generator pairs one copy, and the judged output takes the one at offset (16,-2).
- `background` & `template-identity`, `background` & `fragment-grouping`, `background` & `copy-transform`, `background` & `copy-overlap`, `background` & `copy-offgrid`, `background` & `ambiguous-fragment`, `background` & `adjacency`, `template-identity` & `fragment-grouping`, `template-identity` & `copy-transform`, `template-identity` & `copy-overlap`, `template-identity` & `copy-offgrid`, `template-identity` & `ambiguous-fragment`, `fragment-grouping` & `copy-transform`, `fragment-grouping` & `copy-overlap`, `fragment-grouping` & `copy-offgrid`, `fragment-grouping` & `ambiguous-fragment`, `fragment-grouping` & `adjacency`, `copy-transform` & `copy-overlap`, `copy-transform` & `copy-offgrid`, `copy-transform` & `ambiguous-fragment`, `copy-transform` & `adjacency`, `copy-overlap` & `copy-offgrid`, `copy-overlap` & `ambiguous-fragment`, `copy-overlap` & `adjacency`, `copy-offgrid` & `ambiguous-fragment`, `copy-offgrid` & `adjacency`, `ambiguous-fragment` & `adjacency`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Copies drawn in the template's color: every copy in every pair takes its own fragment's color, and no reading of the pairs gives another color.
- A stored copy offset or shape for each fragment color (a lookup table): test0's colors 5 and 9 are in no train pair, so such a table has an unseen key and fails Fit.
- Copies of two fragments that meet each other: no pair shows two copies meeting, and nothing in the task orders the fragment colors. Every reading is undefined there, so no branch gives an output to separate.

## Tickets filed
- none
