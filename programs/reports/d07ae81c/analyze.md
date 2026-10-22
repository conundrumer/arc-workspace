# d07ae81c

## Concept
- The concept fits every train pair and the test pair (`work/task/d07ae81c/probe.py`). No marker depends on a band-layout reading the pairs leave free: the only marker on a region's edge, train1 input (8,11), has band row 7 above it, and every reading formed here gives it 3.
- The concept is undefined where the repeating band layout gives a marker's cell two colors. Witness `stray-background-cell` shows this, and it breaks `banded-background`.
- The concept has no witness with verdict `other`.

## Choice points
- `ray-color`: the color each ray cell takes
    - `concept`: the background-to-marker color map, derived from where the markers sit in each input
    - `$StoredColorMap`: one background-to-marker color map stored for the task, which replaces `marker-color-map`; parameter `color_map`; defined on every input. It fails Fit: train1 needs 1 to map to 2, and train2 needs 1 to map to 8.
    - `$RayOwnColor`: each ray takes its marker's own color on every background cell, which replaces `marker-color-map` and `recolor-by-background`; no parameters; defined on every input. It fails Fit at train0: the 4 marker's rays turn 1 where they cross 8, for example at train0 output (1,0).
        - `marker-background`: how a marker's background color is read, under the concept branch of `ray-color`
            - `concept`: the color a row that repeats the marker's row (or a column that repeats its column) has at the marker's cell
            - `$FullLineBackground`: the color of a full-length line through the marker's cell whose other cells all have one background color, and the field color when no such line runs through it; replaces the reading in `marker-color-map`; no parameters; undefined where full lines of both colors run through the cell. It fits every pair. Witness `stray-background-cell` breaks `banded-background`. Plausibility `foreign`, verdict `$FullLineBackground`. That input breaks the invariant that every background cell follows the band layout.
            - `$NeighborMajority`: the color most of the marker's eight neighbors carry; replaces the reading in `marker-color-map`; no parameters; undefined on a tie. It fits every pair. Witness `marker-at-field-corner` breaks no scene claim. Plausibility `variant`, verdict `concept`. That input breaks the invariant that every band is at least 2 cells wide.
- `marker-identity`: which cells are markers
    - `concept`: every cell of a color that is not a background color
    - `$SingletonMarkers`: only those cells with no 4-neighbor of their own color, which replaces `lone-markers`; no parameters; defined wherever the concept is. It fits every pair. Witness `adjacent-markers` breaks `lone-markers`. Plausibility `borderline`, verdict `concept`. That input breaks the invariant that no two markers touch.
- `ray-directions`: the directions the rays run
    - `concept`: the four diagonal directions
    - `$EightWayRays`: the four diagonal and the four cardinal directions, which replaces `diagonal-rays`; no parameters; defined wherever the concept is. It fails Fit at train0: the output paints no cell in line with a marker along a row or column, for example train0 output (8,0) stays 8.
- `ray-color` & `marker-identity`, `ray-color` & `ray-directions`, `marker-identity` & `ray-directions`, `marker-background` & `marker-identity`, `marker-background` & `ray-directions`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Rays that stop at the next marker: on any input the stopped ray's continuation runs along the blocking marker's own ray in that direction, so the model is equivalent to the concept.
- Rays that repaint the markers they cross: a marker's background maps to the marker's own color wherever the color map is defined, so the model is equivalent to the concept.
- A background reading from a marker's region as a connected piece or its bounding box: the band color's piece spans the whole grid in train0 and train1, so the reading is ambiguous for every field marker, and the model fails Fit at train0.

## Tickets filed
- none
