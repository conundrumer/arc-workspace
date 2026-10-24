# fe45cba4

## Concept
- Two pieces of one color are jigsaw halves: the piece on the left jumps over and plugs into the notch of the piece on the right, and together they make one solid rectangle; every other shape stays put.

## Scene
- `background-field`: every cell outside the shapes holds the `background` color.
- `one-pair-color`: exactly one color has two 4-connected components, the key and the lock; every other non-`background` color is one component.
- `key-on-mover-side`: the key lies wholly toward `mover_side` of the lock, with no column in common.
- `pieces-interlock`: some translation of the key is disjoint from the lock and the union of the two is a solid rectangle, and only one translation does this.

## Rules
- `erase-key`: the key's cells become `background`.
- `plug-key`: the key is painted at the translation at which it fills the lock's notch, so the lock and the key together form a solid rectangle in the pair color.
- `keep-rest`: the lock and every shape of another color are copied unchanged.

## Parameters
- `background`: 7
- `mover_side`: left
    - the side on which the piece that moves lies, relative to the piece that stays

## Scene parameters
- none
