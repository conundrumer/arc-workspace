# e3721c99

## Departures
- `$DividerByEdge` has no constructor, and the `divider_color=SharedColor` `@derive` branch stands for it. In the witness file, `key-at-grid-edge` and the other groups name `divider_color=SharedColor` in place of `$DividerByEdge`: on one input with `ex_out` empty, SharedColor gives every color of the input, so the divider is every object on the grid edge. That model is equivalent to `$DividerByEdge`, and [Develop](#develop) step 5 removes a branch that is equivalent to a `@derive` branch. Run against `witnesses.json`, the solver reports only that the name `$DividerByEdge` denotes no case.
- The Analyze witness `background=DominantColor` is renamed `shape-outweighs-background`. The id `background=DominantColor` now names the witness that `derive` records for that branch (train0 with 0 and 6 swapped). The Analyze witness stays in the file as a further witness of the branch.
- The concept parameter `background` keeps its concept name in Params.
- `$LargestDivider` is added in Develop step 3 from the Not formed item "a divider found as ... the largest `divider_color` object". The "longest line" reading of the same item is not formed, because "line" does not state one model.

## Judgments
- `@derive DominantColor: variant derived` on `background`: the witness from `derive` is train0 with colors 0 and 6 swapped, which is a color-permuted variant input. There the concept at the stored value 0 is undefined, and the derived branch gives the swapped output, which is the output the generator pairs with that input.
- `@derive SharedColor: variant derived` on `divider_color`: the reason is the same, with train0 and colors 1 and 6 swapped.
- `@ignore: derive VanishedColor` on `divider_color`: with `ex_out` empty, VanishedColor gives every color of the input, as SharedColor does. The two models are equivalent, so VanishedColor fails Equivalence.
- `@ignore: derive $LargestDivider` under the SharedColor line: `$LargestDivider & divider_color=SharedColor` fails Fit on every pair. The largest object of any color is not the divider line, so that line stays a key.
- Witness `key-outweighs-divider` for `$LargestDivider`, `borderline concept`: a key of color 1 with 2 holes has 40 cells, and the divider column has 12. The concept recolors the two-hole shape 1 and erases the solid shape. `$LargestDivider` takes the key as the divider, so the line becomes a key with 0 holes, the solid shape takes 1, and the two-hole shape is erased. The input breaks no scene claim, but every key in the task is far smaller than the divider, so the generator makes such a key only under unusual conditions.
- Hint `chain-join` on `hole_count`: kept with `@ignore`. The rule matches a shape to a key by equal hole counts, so the join on the count is the claim.
- Hint `head-repeat` on `hue`: fixed. `hue` now takes the hole and divider branches in place of the whole `Choice`, and the shape reading comes from the object.
- Hint `determine prediction` on `Determine.divider_color`: kept with `@ignore`. The clause excludes the shape and background colors from the edge colors. Those two colors come from the determination's own `shape_color` and `background` relations, and `shape_color` reads inputs and outputs together.
- `deletions`: 8 deletions change nothing.
    - The rule `divider_size.domain` is removed, because every object has cells.
    - The others stay because each states part of a claim that the pairs do not exercise: the cardinal steps in `joint.item` and in `Determine.background`, the color tests in `object` and in the `$EdgeDivider` divider, and `shape` in `hue`.
- The audit store check skipped `outside.cell` because it has over 20000 rows. That relation is a construction input, not a candidate for a stored value.

## Unsettled
- `deletions` ran before two last edits: the removal of `divider_size.domain` that it reported, and an `@ignore` comment. A run of `deletions` on the final file would settle this.
- `Determine.divider_color` reads values that come from `ex_out`. A determination of `divider_color` from facts of the inputs alone would settle this, such as the edge color whose object runs between two grid edges.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
