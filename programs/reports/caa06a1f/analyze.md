# caa06a1f

## Concept
- Fits every pair. On test0, with `shift_dir` open at left and up, it gives two grids: left gives the output, and up gives the `rule` alt.
- `extend-pattern` and `shift-one` have a relational form: each output cell takes the block cell in its class modulo the per-axis periods, read one cell over from the cell itself.
- Witnesses with verdict `other`: none.
- The variant task 50a16a69 (period-4 and period-3 patterns at the top-left, with the same band) fits at `shift_dir` left and fails at up, so that task fixes `shift_dir` to left.

## Choice points
- `shift-amount`
    - `concept`: the pattern moves `shift_step` (1) cells.
    - `$ShiftByBlockExtent`: replaces `shift-one`; the pattern moves by the block's extent on the axis of `shift_dir`, so the output continues the pattern from where the block ends; defined wherever the concept is. Fails Fit at test0: with an extent of 12, the period-3 columns and period-2 rows return the unmoved pattern.
    - `$ShiftByBandWidth`: replaces `shift-one`; the pattern moves by the band's width on the axis of `shift_dir`; defined wherever the concept is. Fails Fit at train0: a band width of 4 returns the unmoved checkerboard.
- `recolor-form`
    - `concept`: each output cell takes the pattern color one cell over (a positional move).
    - `$ColorSuccessor`: replaces `shift-one`; each cell of the continued pattern takes the color that follows its own color along a row of the block, derived per input, and reads no `shift_dir`; undefined on an input where a color is followed by two different colors along the rows. Fits every pair, and gives only the left move on test0. It is not equivalent to the concept, which is defined where a color has two successors. It is not subsumed: at `shift_dir` up the concept gives another grid. Witness `three-color-cycle`: breaks no scene claim, at the stored assignment, plausibility `ordinary`, verdict `any`: the generator's output is the left move, which both the concept's two grids and this branch's one grid contain.
- `block-corner`
    - `concept`: `block_corner` is stored (top-left), and the background is the color at the opposite corner.
    - `$DeriveCorner`: replaces the corner in `periodic-block` and `background-band`; the corner is derived per input as the one corner where the color at the opposite corner fills every cell outside a rectangle that sits at that corner; undefined where no corner, or more than one corner, gives that rectangle. Fits every pair. Witness `block-bottom-left`: breaks `periodic-block`, at the stored assignment, plausibility `variant` (a top-bottom mirror of this task puts the block at the bottom-left), verdict `$DeriveCorner`; it breaks the invariant that the block sits at the top-left in every input.
        - `shift-frame`
            - `concept`: `shift_dir` is an absolute direction (left, up).
            - `$ShiftTowardCorner`: replaces `shift-one`; on each axis of `shift_dir` the direction is derived as the one toward the derived corner, so the open values read as toward the corner horizontally and toward it vertically; defined wherever `$DeriveCorner` is. Fits every pair. Witness `block-bottom-right`: breaks `periodic-block`, at the stored assignment, plausibility `variant` (a half turn of this task puts the block at the bottom-right and moves the pattern right and down), verdict `$ShiftTowardCorner`; it breaks the invariant that the block sits at the top-left in every input.
- `shift-amount` & `recolor-form`, `shift-amount` & `block-corner`, `recolor-form` & `block-corner`, `shift-amount` & `shift-frame`, `recolor-form` & `shift-frame`: the two branches' changes applied together.

## Open parameters
- `shift_dir`: left, up. Right and down move the pattern away from the block's corner, so a reader of the concept does not take them. Right also fails test0. Down gives the same test0 grid as up.

## Not formed
- `@derive` of `shift_step`, `shift_dir` or `block_corner`: no proposer in programs/proposers.dl gives a direction or a corner. The proposers that give 1 (`TileDim`, `TileCount`) give it among several values on each input, and the other values give extra outputs on every train pair.
- A stored color-to-color table in place of `shift-one`: the test0 colors 8, 5 and 7 are keys that no train pair contains, so the table fails Fit (Unseen key).
- A swap of the two pattern colors: undefined on test0, which has three pattern colors, so it fails Fit. Where it is defined, it is `$ColorSuccessor` on a two-color pattern.
- The background color from another source, such as the color that fills a whole edge row and a whole edge column: it gives the same color as the opposite corner wherever the block sits at `block_corner`. Where the block sits elsewhere, it is the `block-corner` point.
- Continuation along the pattern's own translation lattice in place of its per-axis periods: the lattice and the per-axis tile give one continuation wherever the block holds two full periods on each axis, as `periodic-block` states.

## Tickets filed
- 10-577_task_caa06a1f_analyze.md
- 10-578_task_caa06a1f_analyze.md
