# f560132c

## Concept
- Four jigsaw pieces lie apart on the background, and one of them holds a 2×2 color key; fit the pieces together into a square, turning the others as needed, and paint each piece with the key color at the corner of the key that matches the corner of the square it fills.

## Scene
- `four-pieces`: four single-color objects of four distinct colors on a field of `background`, each one 4-connected, no two touching, even at a corner.
- `key-piece`: exactly one piece holds a 2×2 block of four distinct colors, none of them `background` or a piece's color, nearest the `key_corner` corner of the piece's box; the key cells count as cells of that piece.
- `pieces-tile-square`: the four pieces, the key piece unturned and each other piece under some rotation, tile a solid square with no gap and no overlap, each piece covering exactly one corner of the square, the key piece the `key_corner` corner.

## Rules
- `assemble`: the output is that square, the key piece placed unturned and each other piece turned by the rotation that makes the four tile it; the program enumerates every rotation of C4 for a piece.
- `color-by-corner`: every cell of a piece, key cells included, takes the key's color at the same corner of the key as the corner of the square the piece covers.

## Parameters
- `background`: 0

## Scene parameters
- `key_corner`: DIAG_TL
    - the corner of the key piece's box the key sits nearest, and the corner of the square the key piece covers
