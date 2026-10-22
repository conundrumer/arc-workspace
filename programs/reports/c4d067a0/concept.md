# c4d067a0

## Concept
- A small key of single dots shows a pattern, and a few big square blocks show part of that pattern drawn large; complete the large drawing of the whole key, so that each dot of the key becomes a block of its color, placed where the given blocks fix it.

## Scene
- `background`: one color fills most of the grid.
- `key-lattice`: the key is a set of single cells of non-background colors, on a lattice of pitch `key-pitch` along each axis, with a background cell between neighboring dots; a lattice point inside the key's bounding box can hold the background color.
- `key-corner`: the key stands near the `key-corner` corner of the grid.
- `given-blocks`: two solid squares of one size k (k at least 2), each of a non-background color, lie on one line along the axis `blocks-axis`, with the same gap g between neighbors.
- `blocks-match-key`: the given blocks are the large drawing of a run of neighboring key dots, block for dot and color for color, and exactly one such run of the key matches them.
- `fits-grid`: the large drawing of the whole key, placed by that match, lies inside the grid.

## Rules
- `enlarge-key`: each key dot of a non-background color becomes a k×k block of that color, and key dots one lattice step apart become blocks at a pitch of k+g along either axis, with the gap g read from the given blocks used on both axes.
- `anchor-by-match`: the large drawing is placed so that the blocks of the matched run land on the given blocks.
- `background-dot-empty`: a key point of the background color gives no block.
- `keep-input`: every other cell keeps its input color, the key and the given blocks included.

## Parameters
- `key-pitch`: 2
    - the distance between neighboring lattice points of the key

## Scene parameters
- `key-corner`: top-left
- `blocks-axis`: horizontal
