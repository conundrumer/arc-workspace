# fafd9572

## Concept
- Fits every pair (train0, train1, test0), checked by `work/task/fafd9572/check_concept.py` and `work/task/fafd9572/probe.py`.
- No witness has verdict `other`.
- The rule as the generator applies it: the copies are the key drawn at a larger scale. A key cell at row i, column j of the key's box gives a copy at the copies' corner plus (i, j) × (shape extent + `copy_gap`), and that copy takes the key cell's color. `recolor-copy` approximates this with the copies' row and column ranks. The two agree under the scene claim `key`, which says every row and column of the key's box holds a key cell.

## Choice points
- `slot-correspondence`
    - `concept`: a copy's row rank and column rank among the copies give its key cell's row and column within the key's box (`recolor-copy`)
    - `$LatticeSlot`: replaces `recolor-copy`. A copy's slot is its offset from the copies' top-left corner divided by the period, shape extent + `copy_gap`, on each axis, and the copy takes the key cell at that slot of the key's box. `copy_gap` (1) moves from Scene parameters to Parameters. Undefined where the copies differ in extent, where an offset is not a multiple of the period, or where the slot holds no key cell. Fits every pair. Witness `key-with-gap`: breaks scene claim `key` (a key `2 0 3` whose box has an empty column), at the stored assignment; plausibility `variant`, verdict `$LatticeSlot`. Invariant of the inputs it breaks: every row and column of the key's box holds a key cell.
        - `copy-gap-source`
            - `concept`: `copy_gap` stored (`$LatticeSlot`)
            - `$GapFromSpacing`: on each axis, the period is derived from each input as the least difference between two distinct copy tops, and every copy sits in slot 0 on an axis where all copies share one top. This replaces the stored `copy_gap`. Undefined where `$LatticeSlot` is. Fits every pair. Witness `wide-gap`: breaks scene claim `copies` (two background lines between copies, where `copy_gap` is 1), at the stored assignment; plausibility `variant`, verdict `$GapFromSpacing` (the concept gives the same output, and `$LatticeSlot` is undefined). Invariant of the inputs it breaks: neighboring copies are one background line apart.
    - `$OrderMatch`: replaces `recolor-copy`. The n-th copy in reading order of its top-left cell takes the n-th key cell in reading order, so `layout-matches-key` is not read. Undefined where the copy count differs from the key cell count. Fits every pair. Witness `copies-off-key-layout`: breaks scene claim `layout-matches-key` (a horizontal key `2 3` with two copies stacked vertically), at the stored assignment; plausibility `foreign`, verdict `$OrderMatch`. Invariant of the inputs it breaks: the copies are laid out in the key's pattern.
- `adjacency`
    - `concept`: a copy is an 8-connected part of `shape_color`
    - `$FourConnected`: replaces `copies`, so a copy is a 4-connected part (another orientation type). Fails Fit at train0: each diagonal-joined copy splits in two, giving six row tops against three key rows, so a slot falls outside the key.
- `shape-color-source`
    - `concept`: `shape_color` stored (1)
    - `$ShapeColorByCount`: `shape_color` is derived from each input as its commonest color other than `background`. Undefined where that color ties or no such color exists. Fits every pair. Witness `copies-in-another-color`: breaks scene claim `copies` (train1's input with its copies in 5), at the stored assignment. The concept finds no copy and returns the input. Plausibility `variant`, verdict `$ShapeColorByCount`. Invariant of the inputs it breaks: the copies are color 1.
    - `$ShapeColorByRepetition`: `shape_color` is derived from each input as the one color whose 8-connected parts recur as translates. Undefined where not exactly one color does. Fails Fit at train0: the key's two single `2` cells recur too, so two colors qualify (test0 has the same problem with `3` and `4`).
- `background-source`
    - `concept`: `background` stored (0)
    - `background=DominantColor`: `background` is derived from each input as its commonest color. Undefined where that color ties. Fits every pair. Witness `background=DominantColor`: breaks scene claim `key` (train1's input on a field of 6, which the stored background takes into the key), at the stored assignment. The concept turns the copies 6. Plausibility `variant`, verdict `background=DominantColor`. Invariant of the inputs it breaks: the background is 0.
- `slot-correspondence` & `adjacency`, `slot-correspondence` & `shape-color-source`, `slot-correspondence` & `background-source`, `adjacency` & `shape-color-source`, `adjacency` & `background-source`, `shape-color-source` & `background-source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The key read under a D4 transform of the copies' layout, as a stored `D4` parameter: no pair distinguishes an orientation. A group element transforms the key and the copies together, so no variant task stores a value other than the identity.
- `$ShapeColorByRepetition` limited to parts of more than one cell: a size threshold that only patches the train0 failure, with no evidence behind it.
- The key removed or recolored in the output: every pair keeps the key unchanged.
- The lattice period read from the copies' spacing under the concept: rank ordering reads no period, so the concept has no gap to derive.

## Tickets filed
- none
