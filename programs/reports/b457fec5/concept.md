# b457fec5

## Concept
- A square slides one diagonal step at a time and leaves a staircase trail; repaint the trail as if the square painted itself at each step with the next color of the key, cycling through the key, each step painting over the steps before it. The result is a run of nested L-shaped stripes around the corner where the slide starts, cycling through the key colors, and the square at the far end takes one solid color.

## Scene
- `background`: every cell outside the key and the trails is `background`.
- `key-line`: a key: a straight line of cells, one cell thick, along the axis of `key-start`, each cell a different color, none of them `background` or `shape-color`. It lies one line in from the `key-side` edge, and stands apart from every trail.
- `diagonal-trail`: one or more trails of `shape-color`, each the union of the positions of an n×n square that starts at a corner and moves one step along a diagonal for each of T steps (n ≥ 3, T ≥ 1). Trails do not touch each other or the key.
- `whole-cycles`: the number of positions the square takes in each trail, T + 1, is a multiple of the key's length K.
- `head-end`: the start of each trail is its end toward `head-dir`.

## Rules
- `keep-rest`: every cell that is not a trail cell keeps its input color, the key included.
- `key-order`: the key colors, in order from the key's end toward `key-start`, are c0, c1, …, cK-1.
- `step-paint`: in each trail, the square at step t (t = 0 at the head, t = T at the far end) paints its n×n cells with color c(t mod K); a cell takes the color of the last step that covers it. So a cell whose distances from the head square's two outer edges are u and v takes c(min(u, v, T) mod K).

## Parameters
- `background`: 0
- `shape-color`: 5
    - the color of the trail cells in the input
- `key-start`: DIR_L
    - the direction toward the key's end that holds its first color
- `head-dir`: DIR_T
    - the direction toward the end of a trail where the slide starts

## Scene parameters
- `key-side`: DIR_T
    - the grid edge the key lies one line in from
