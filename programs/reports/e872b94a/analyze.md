# e872b94a

## Concept
- Fits every pair: the side-connected parts of the 5 cells number 3, 1, 2, 4 on the train inputs and 2 on the test input, and each output is a column of 0 one cell longer.
- No witness has the verdict `other`. The concept's rules are relational as written, so there is no approximation.
- The pairs do not separate it from any branch below. The side-connected and the corner-connected parts of the 5 cells agree on every input. The background regions number one more than the snakes on every input, because every snake touches two grid edges.

## Choice points
- `snake-cells`
    - `concept`: the cells of the stored `shape_color`
        - `shape_color`
            - `concept`: stored, 5
            - `shape_color=RarestColor`: the snake color is each color with the fewest cells in the input; replaces the stored value of `count-snakes`; defined on every input; fits every pair. Witness `shape_color=RarestColor`: breaks no scene claim; `ordinary`; verdict `concept`.
            - `shape_color=DominantColor`: fails Fit at train0, where the 0 cells give 4 parts and a strip of 5.
            - `shape_color=SharedColor`, `shape_color=VanishedColor`: on one input with no outputs, each gives both 0 and 5, so the whole grid is one part. Each fails Fit at train0 with a strip of 2.
    - `$NonBackground`: replaces `count-snakes`: a snake is a side-connected part of the cells that are not `background`; the program reads `background` (0) and no `shape_color`; defined on every input; fits every pair. Witness `second-color-snake`: breaks `snakes-on-background`; `borderline`; verdict `$NonBackground`. The invariant of the inputs that it breaks: every input holds only the colors 0 and 5.
        - `background`
            - `concept`: stored, 0
            - `background=DominantColor`: the background is each color with the most cells in the input; defined on every input; fits every pair. Witness `background=DominantColor`: breaks no scene claim; `ordinary`; verdict `concept`.
            - `background=RarestColor`: fails Fit at train0, where the 0 cells become the snakes and give a strip of 5.
            - `background=SharedColor`, `background=VanishedColor`: each gives both colors as background, which leaves no snake cell. Each fails Fit at train0.
- `counted-parts`
    - `concept`: the snakes, and the length is their count plus `extra_cells`
    - `$BackgroundRegions`: replaces `count-snakes` and `strip-length`: the length is the number of side-connected parts of the cells that are not snake cells; no `extra_cells`; undefined on an input that has no non-snake cell; fits every pair. Witness `snake-off-edge`: breaks no scene claim; `variant`; verdict `concept`. The invariant of the inputs that it breaks: every snake touches two edges of the grid.
- `adjacency`
    - `concept`: counted parts join through shared sides
    - `$Adjacency8`: replaces `count-snakes`: counted parts also join through corners; defined on every input; fits every pair. Witness `corner-contact`: breaks `snakes-apart`; `borderline`; verdict `$Adjacency8`. The invariant of the inputs that it breaks: every snake is a side-connected path, and no two snakes meet at a corner.
- `strip-form`
    - `concept`: the strip is drawn from `axis`, `strip_width`, `fill_color` and the count
        - `fill_color`
            - `concept`: stored, 0
            - `fill_color=DominantColor`: the fill is each color with the most cells in the input; undefined where two colors tie for the most cells; fits every pair. Witness `fill_color=DominantColor`: breaks no scene claim; `ordinary`; verdict `concept`.
            - `fill_color=RarestColor`: fails Fit at train0, which it fills with 5.
            - `fill_color=SharedColor`, `fill_color=VanishedColor`: each gives two fill colors on one input. Each fails Fit at train0.
            - `fill_color=OutNewColor`, `fill_color=AnyOutNewColor`, `fill_color=ChangedColor`, `fill_color=UnchangedColor`: each needs an output, so each gives no value on one input with no outputs. Each is undefined there and fails Fit at train0.
        - `axis`
            - `concept`: stored, vertical
            - `$AxisFromSnakes`: replaces the stored value of `strip-length`: the axis is each axis that some snake spans from edge to edge; undefined on an input where no snake spans either axis; fits every pair. Witness `sideways-snake`: breaks no scene claim; `variant`; verdict `$AxisFromSnakes`. The invariant of the inputs that it breaks: some snake spans the grid from top to bottom.
    - `$CountTable`: replaces `strip-length` and `strip-fill`: a stored `count_table` gives the output grid for each count, 1 to 4; no `axis`, `strip_width`, `fill_color` or `extra_cells`; undefined on an input whose count is no key of the table; fits every pair, since the test count 2 is a train count. Witness `table-entry-off-form`: stands at the assignment that sets the entry for count 1 to a grid no strip draws; breaks no scene claim; `ordinary`; verdict `$CountTable`.
- `snake-cells` & `counted-parts`, `snake-cells` & `adjacency`, `snake-cells` & `strip-form`, `snake-cells` & `fill_color`, `snake-cells` & `axis`, `counted-parts` & `adjacency`, `counted-parts` & `strip-form`, `counted-parts` & `shape_color`, `counted-parts` & `background`, `counted-parts` & `fill_color`, `counted-parts` & `axis`, `adjacency` & `strip-form`, `adjacency` & `shape_color`, `adjacency` & `background`, `adjacency` & `fill_color`, `adjacency` & `axis`, `strip-form` & `shape_color`, `strip-form` & `background`, `fill_color` & `axis`, `fill_color` & `shape_color`, `fill_color` & `background`, `axis` & `shape_color`, `axis` & `background`: the two branches' changes applied together
- `shape_color` & `background`: no case takes a non-concept branch at both. `shape_color` stands under the concept branch of `snake-cells`, and `background` stands under `$NonBackground`.

## Open parameters
- none

## Not formed
- A derivation of `extra_cells` or of `strip_width`: a number proposer run on one input with no outputs reads no output dimension. The values it gives come from the input's own size or tiling, and the pairs tie none of these to the strip. For example, `ConstInDim` gives 12 at train0, which fails Fit there.
- A count of something other than the snakes or the regions, such as the snake cells, the snake ends on the top edge, or the snakes that touch a given edge: it gives a different number from the output length at train0 (for example, 46 snake cells, or 1 snake on the top edge).
- A strip whose length is the count with a stored offset, under `$BackgroundRegions`: that branch's region count already equals the output length, and its determination keeps an offset of 0, which is the model of `$BackgroundRegions`.

## Tickets filed
- none
