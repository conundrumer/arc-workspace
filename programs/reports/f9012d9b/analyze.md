# f9012d9b

## Concept
- Fits all three train pairs and the test pair (probe `work/task/f9012d9b/probe.py`). The least periods are (2,2), (2,2), (3,3) and (3,3), and each hole cell's residue class shows outside the hole.
- No witness has verdict `other`. No rule in the concept file is an approximation: `least-period`, `fill-from-period` and `crop-to-hole` are relational as stated.
- It is undefined where no cell has `hole_color` (witnesses `hole_color=RarestColor`, `hole-in-other-color`) and where the hole covers every copy of a residue class (`hidden-residue`).

## Choice points
- `hole` (which cells are the hole)
    - `concept`: the cells of the stored `hole_color` (0)
    - `hole_color=RarestColor`: replaces the stored `hole_color` with a derived one, the input's rarest color or colors (`one-rectangular-hole` is read at that color). Undefined where the rarest color's cells have no visible cell of their residue class, as when the pattern has a color rarer than the hole. Fits every pair (0 is the rarest color of every input). Witness `hole_color=RarestColor`: the patch is drawn in 4 on the train1 checkerboard. It breaks scene claim `one-rectangular-hole` (no cell is 0). Plausibility `variant`, verdict `hole_color=RarestColor`. Invariant broken: every input's hole is color 0.
    - `hole_color=SharedColor`: replaces the stored `hole_color` with SharedColor's derivation. On one input it gives every color of that input, so the whole grid is hole and the branch is undefined on every input. Fails Fit at train0.
    - `hole_color=VanishedColor`: replaces the stored `hole_color` with VanishedColor's derivation. With `ex_out` empty it gives every color of the input, so it is undefined on every input. Fails Fit at train0.
    - `$HoleByShape`: replaces `hole_color` and `one-rectangular-hole`: the hole is the one color whose cells form a single 4-connected solid rectangle. No parameter. Undefined where no color qualifies, or more than one does. Fits every pair. Witness `hole-in-other-color`: a 3x3-tile pattern with a 4-colored patch, where color 3 is rarer than the patch. It breaks scene claim `one-rectangular-hole` (no cell is 0). Plausibility `variant`, verdict `$HoleByShape`. Invariant broken: every input's hole is color 0.
- `orbit-basis` (what a hole cell's color is read across)
    - `concept`: translations by multiples of the least periods
    - `$FillBySymmetry`: replaces `least-period` and `fill-from-period`: a hole cell takes the color its images have under the grid's D4 reflections, keeping each reflection that the visible cells witness and none contradicts. No parameter. Undefined where a hole cell's images are all hidden or disagree. Fails Fit at train2: only the transpose holds there, and it maps the hole onto itself.
- `orbit-reach` (which period translates a hole cell reads; exists with the concept's period basis)
    - `concept`: every visible cell of its residue class
    - `$PeriodAndSymmetry`: adds to `fill-from-period` the grid reflections the visible cells witness and none contradicts, closed under the periods. Undefined where a cell stays unreached or two sources disagree. Fits every pair. Witness `hidden-residue`: on a 7x7 grid of the 3x3 tile `3 1 1 / 1 2 2 / 1 2 2`, a 4x4 hole hides all four copies of residue (1,1). The branch restores them by mirror, and the concept is undefined. No scene claim broken. Plausibility `borderline`, verdict `$PeriodAndSymmetry`. Invariants broken: every hole cell's residue class shows outside the hole, and the hole is no larger than the period on each axis.
    - `$CopyNeighborTile`: replaces `fill-from-period`: a hole cell takes the color of a visible cell exactly one period away on one axis or both. Undefined where all eight such cells are hidden or off the grid. Fits every pair. Where it is defined it gives the concept's output, so it fails Subsumption (subsumed by the concept case). Witness `hole-beyond-neighbor-tile`: a 5x5 hole in an 8x8 grid of the 2x2 tile `2 1 / 1 1`. Center (3,3) has no visible cell one period away, and the concept fills it from (7,7). No scene claim broken. Plausibility `variant`, verdict `concept`. Invariant broken: the hole is no larger than the period on each axis.
- `period-source` (where the periods come from; exists with the concept's period basis)
    - `concept`: derived per input by `least-period`
    - `$StoredPeriod`: replaces `least-period` with a stored (row, column) period. Undefined where a hole cell's residue class under the stored period is hidden, or holds two colors. Fails Fit at train2 at every stored value. Train0 admits only even periods, which give train2 two colors per class. Train2 admits only multiples of 3, and the least of those that is also even is 6, which has no visible copy in train0's 5x5 grid.
        - `period-value` (how the stored period is had)
            - `concept`: stored
            - `period=Period`: derived by the Period proposer, the least shift per axis under which the whole input repeats. The 0 cells break every shift on every pair, so it gives no period and is undefined. Fails Fit at train0.
- `hole` & `orbit-basis`, `hole` & `orbit-reach`, `hole` & `period-source`, `orbit-reach` & `period-source`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Output the whole repaired grid instead of the hole's crop: every output has the hole's size, so this is not underdetermined. It fails every pair.
- Least period tested per axis (same-row and same-column pairs only) instead of over the 2D lattice: this computes the claim `least-period` and is not another claim. On a fully visible pattern the two give the same periods.
- `period=TileDim`, `period=TileCount`: on one input these proposers give several tile dims per axis (each n and gap that fits), so the hole fills under several periods with conflicting colors. They fail Fit at train0 as `$StoredPeriod` does.
- `hole_color=DominantColor` and the color proposers that read outputs (ChangedColor, UnchangedColor, OutNewColor, AnyOutNewColor): DominantColor never gives 0, since 0 is never an input's commonest color. Under `@derive` the others read one input with `ex_out` empty, so they give every input color or none, and the branch is undefined. Each fails Fit at train0.

## Tickets filed
- none
