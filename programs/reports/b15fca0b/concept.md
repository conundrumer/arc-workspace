# b15fca0b

## Concept
- Connect the two endpoint marks by the shortest path through the open background, going around the walls, and paint that path.

## Scene
- `two-endpoints`: the input holds exactly two cells of `endpoint_color`.
- `walls`: every other cell that is not `background` is a wall cell of `wall_color`.
- `connected`: the two endpoints are joined by a 4-adjacent walk whose inner cells are all `background`.
- `unique-shortest`: exactly one such walk has the fewest steps.

## Rules
- `copy`: every cell keeps its input color unless a rule below paints it.
- `shortest-path`: each inner cell of the shortest 4-adjacent walk from one endpoint to the other, through `background` cells only, takes `path_color`.

## Parameters
- `background`: 0
    - the color the path can cross
- `endpoint_color`: 2
- `path_color`: 4

## Scene parameters
- `wall_color`: 1
