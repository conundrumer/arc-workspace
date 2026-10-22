# dfadab01

## Concept
- Each lone colored dot is a key: it becomes a fixed 4×4 picture whose top-left corner is the dot, and the color of the dot picks the picture. An input can also hold one sample of a picture, with the dot of its key just past its bottom-right corner, and that sample and its dot are wiped.

## Scene
- `markers`: single cells on the `background` field, each of a color that is a key of `stamp`.
- `legend`: at most one sample: the `stamp` of some key drawn in a 4×4 box, with a marker of that key at the cell one step past the box's `key-corner` corner on both axes.
    - A marker can sit in the box of the sample, at a cell where the sample has `background`.
- `stamps-apart`: with the sample's key marker left out, the boxes of two markers' stamps do not overlap, and the box of a marker's stamp does not overlap the box of the sample unless the two boxes coincide.

## Rules
- `stamp-at-marker`: each marker that is not the sample's key marker draws its key's `stamp`, with the stamp's `anchor` corner at the marker; a stamp cell that falls past the grid edge is dropped.
- `wipe-rest`: every other cell of the output is `background`, so the sample and its key marker are wiped.

## Parameters
- `stamp`: 2 → `4` outline square; 3 → `1` ring; 5 → `6` two blocks on the main diagonal; 8 → `7` cross
    - The 4×4 picture each marker color draws:

        ```
        2:       3:       5:       8:
        4 4 4 4  0 1 1 0  6 6 0 0  7 0 0 7
        4 0 0 4  1 0 0 1  6 6 0 0  0 7 7 0
        4 0 0 4  1 0 0 1  0 0 6 6  0 7 7 0
        4 4 4 4  0 1 1 0  0 0 6 6  7 0 0 7
        ```

- `anchor`: top-left
    - The corner of a stamp that sits on its marker.
- `key-corner`: bottom-right
    - The corner of the sample's box that its key marker sits diagonally past.
- `background`: 0

## Scene parameters
- none
