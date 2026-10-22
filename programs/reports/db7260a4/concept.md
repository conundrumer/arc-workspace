# db7260a4

## Concept
- A drop of water poured from the top falls straight down. When it lands in a cup with a whole floor, it fills that cup. When the cup's floor has a hole, the water runs out through the hole and keeps falling. Water that falls to the bottom of the grid covers the bottom row.

## Scene
- `drop`: one cell of color `water` on the edge opposite `fall`; every other cell is `background` or `wall`.
- `cups`: the `wall` cells draw cups open toward the drop's edge: two walls along `fall`, joined by a floor across their far ends. Some floors have a one-cell hole, and some walls stand alone.
- `no-landing-on-rim`: the falling water never lands on the top of a wall, only on a floor or on the bottom edge.

## Rules
- `fall`: water falls from the drop toward `fall` until the next cell is `wall` or the grid edge.
- `spread`: when the next cell is `wall`, the water spreads sideways along its line in both directions until it meets a `wall` cell on each side. When a cell it reaches has no `wall` cell beyond it toward `fall`, the water falls from that cell as in `fall`.
- `fill`: when the water spreads to a wall on each side and finds no hole, it fills the cup: every cell between the two walls, from the floor back up to the end of the shorter wall.
- `pool`: when the water reaches the grid edge toward `fall`, every cell that is not `wall` in the `pool-depth` lines at that edge takes `water`.
- `erase-drop`: the drop cell becomes `background`. The cells the water only passes through stay as they are, and a cup the water runs out of stays empty.

## Parameters
- `water`: 1
    - the color of the drop and of the water it draws
- `wall`: 2
- `background`: 0
- `fall`: down
    - the direction the water falls
- `pool-depth`: 1
    - the number of lines the water covers at the edge toward `fall`

## Scene parameters
- none
