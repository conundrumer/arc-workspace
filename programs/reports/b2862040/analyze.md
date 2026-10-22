# b2862040

## Concept
- The concept fits every pair. Each shape is a 4-connected set of `shape_color` cells. A shape that by itself closes off a region from the frame edge, where a region escapes by 4-steps, takes `closed_color` on every cell. Every other cell keeps its input color.
- The rule has a relational form (`Components`, then `Closed` keyed by shape), so the concept file's rule is the rule as the generator applies it.
- No witness has the verdict `other`.
- In every pair, a shape that closes off a region closes off exactly one, and no two shapes touch, not even at a corner. Each hole is 1 to 4 cells of background and stays closed under diagonal steps too. The inputs hold only `background` and `shape_color`, and `background` is the commonest color.

## Choice points
- `shape-connectivity`
    - `concept`: a shape is a 4-connected component of `shape_color`
    - `$Shapes8`: replaces `shapes`: a shape is an 8-connected component of `shape_color`; defined on every input. Fits every pair. Witness `corner-touch`: a dot touches a ring at a corner, and `$Shapes8` recolors the dot with the ring. It breaks no scene claim. Plausibility `borderline`, because it breaks the invariant that no two shapes touch, not even at a corner. Verdict `concept`.
- `escape-adjacency`
    - `concept`: a region escapes to the frame edge by 4-steps through cells outside the shape
    - `$DiagEscape`: replaces `recolor-closed-shapes`: a region escapes by 8-steps, so a hole that meets the outside only at a corner is open; defined on every input. Fits every pair. Witness `cut-corner-ring`: a ring lacks one corner cell, and `$DiagEscape` keeps it as `shape_color`. It breaks no scene claim. Plausibility `borderline`, because it breaks the invariant that every hole stays closed under diagonal steps. Verdict `concept`.
- `enclosing-walls`
    - `concept`: the shape by itself closes off the region
    - `$AllInk`: replaces `recolor-closed-shapes`: the regions that all the `shape_color` ink together closes off are found, and a shape recolors when one of its cells is 4-adjacent to such a region; defined on every input. Fits every pair. Witness `nested-shape`: a dot stands inside a ring's hole, and `$AllInk` recolors the dot with the ring. It breaks no scene claim. Plausibility `borderline`, because it breaks the invariant that every hole is 1 to 4 cells of background. Verdict `concept`.
- `shape-ink`
    - `concept`: the shapes are made of `shape_color` cells
    - `$AnyInk`: replaces `shapes`: a shape is a 4-connected component of the cells that are not `background`, of any color. It reads `background` in place of `shape_color`, and is defined on every input. Fits every pair. Witness `other-color-ring`: a ring of color 2 stands beside a ring of color 1, and `$AnyInk` recolors both. It breaks scene claim `shapes`. Plausibility `borderline`, because it breaks the invariant that the inputs hold only `background` and `shape_color`. Verdict `concept`.
        - `background-source`
            - `concept`: `background` is stored
            - `background=DominantColor`: `background` is derived as the commonest color of the input; undefined on an input with a tie for the commonest color. Fits every pair. Witness `ink-outnumbers-background`: a 3×3 ring fills the grid. The branch takes 1 as the background and gives the input unchanged. It breaks scene claim `background-field`. Plausibility `borderline`, because it breaks the invariant that `background` is the commonest color. Verdict `concept`.
- `shape-color-source`
    - `concept`: `shape_color` is stored
    - `shape_color=RarestColor`: `shape_color` is derived as the rarest color of the input; undefined on an input with a tie for the rarest color. Fits every pair. Witness `ink-outnumbers-background`: the branch takes 9 as the shape color and gives the input unchanged. It breaks scene claim `background-field`. Plausibility `borderline`, because it breaks the invariant that `background` is the commonest color. Verdict `concept`.
    - `shape_color=DominantColor`: `shape_color` is derived as the commonest color of the input. It fails Fit at train0. The background field becomes the shape, and it closes the ink off from the frame edge, so the field takes 8.
    - `shape_color=SharedColor`: `shape_color` is derived as each color present in the input, which is 1 and 9 on every input. It fails Fit at train0, because at the value 9 the output is the failing output of `shape_color=DominantColor`.
- `closed-color-source`
    - `concept`: `closed_color` is stored
    - `closed_color=OutNewColor`: `closed_color` is derived as a color in every train output and in no input. On an input alone, `ex_out` is empty, so the derivation gives no value. It fails Fit at train0, because it is undefined there.
- `recolored-cells`
    - `concept`: every cell of a closing shape takes `closed_color`
    - `$HoleWallOnly`: replaces `recolor-closed-shapes`: only the shape cells 4-adjacent to a region the shape closes off take `closed_color`. It fails Fit at train0, because it keeps 1 at the ring corners (2,1), (2,3), (5,1) and (5,3).
- `hole-condition`
    - `concept`: a shape recolors when it closes off at least one region
    - `$OneHole`: replaces `recolor-closed-shapes`: a shape recolors when the count of regions it closes off equals a stored count, 1; defined on every input. Fits every pair. Witness `two-hole-shape`: one shape closes off two regions, and `$OneHole` keeps it. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
    - `$HoleCountTable`: replaces `recolor-closed-shapes`: a stored table maps the count of regions a shape closes off to the shape's color, {0: 1, 1: 8}. It is undefined on an input with a shape whose count is not a key. Fits every pair, and every test count is a train key. Witness `two-hole-shape`: the branch is undefined there, and the concept gives 8. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`. No witness exists on which the table is defined at the stored assignment and differs from the concept. The model is subsumed by the concept's, so its case fails Subsumption.
- `shape-connectivity` & `escape-adjacency`, `shape-connectivity` & `enclosing-walls`, `shape-connectivity` & `shape-ink`, `shape-connectivity` & `shape-color-source`, `shape-connectivity` & `closed-color-source`, `shape-connectivity` & `recolored-cells`, `shape-connectivity` & `hole-condition`, `shape-connectivity` & `background-source`, `escape-adjacency` & `enclosing-walls`, `escape-adjacency` & `shape-ink`, `escape-adjacency` & `shape-color-source`, `escape-adjacency` & `closed-color-source`, `escape-adjacency` & `recolored-cells`, `escape-adjacency` & `hole-condition`, `escape-adjacency` & `background-source`, `enclosing-walls` & `shape-ink`, `enclosing-walls` & `shape-color-source`, `enclosing-walls` & `closed-color-source`, `enclosing-walls` & `recolored-cells`, `enclosing-walls` & `hole-condition`, `enclosing-walls` & `background-source`, `shape-ink` & `closed-color-source`, `shape-ink` & `recolored-cells`, `shape-ink` & `hole-condition`, `shape-color-source` & `closed-color-source`, `shape-color-source` & `recolored-cells`, `shape-color-source` & `hole-condition`, `closed-color-source` & `recolored-cells`, `closed-color-source` & `background-source`, `recolored-cells` & `hole-condition`, `recolored-cells` & `background-source`, `hole-condition` & `background-source`: the two branches' changes applied together
- `shape-ink` & `shape-color-source`: the model of `$AnyInk` alone, because `$AnyInk` reads no `shape_color`. The `shape-color-source` point exists only with the concept branch of `shape-ink`, and so it stands at the concept.
- `shape-color-source` & `background-source`: the model of `$AnyInk` & `background=DominantColor` alone, because `background-source` exists only under `$AnyInk`, which reads no `shape_color`
- `hole-condition` & `closed-color-source`: the two branches' changes applied together
    - `$HoleCountTable` & `closed_color=OutNewColor`: the model of `$HoleCountTable` alone, because the table gives the color and the model reads no `closed_color`

## Open parameters
- none

## Not formed
- A `@derive` of `shape_color` by a proposer that reads `ex_out` (`ChangedColor`, `UnchangedColor`, `VanishedColor`, `ChangedPairs`, `VanishedNewPairs`): on an input alone, `ex_out` is empty and the proposer gives no color, so the branch is undefined on every pair and fails Fit at train0. Of these proposers, only `OutNewColor` gives a color this task's rule reads, and it is formed as `closed_color=OutNewColor`.
- `CountRankAsc` and `CountRankDesc` as a source of `shape_color`: they propose (color, rank) rows, and their rank-0 color is the value that `RarestColor` and `DominantColor` give, which are formed.
- A least hole size that a shape must close off: no reading of the pairs, solver header or proposer posits a size threshold. The smallest hole in the pairs is one cell, so the threshold would hold 1 and separate nothing that the concept does not.
- Filling the holes instead of the shapes: every hole cell keeps `background` in every output.

## Tickets filed
- none
