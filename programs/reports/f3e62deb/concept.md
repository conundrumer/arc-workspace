# f3e62deb

## Concept
- A hollow square slides all the way to the edge of the grid, and its color says which way: each color goes its own direction.

## Scene
- `one-object`: the grid holds one object of a single color on a field of `background`, and nothing else.
- `object-shape`: the object is a `shape`, a 3×3 ring whose center is `background`, placed clear of every edge.

## Rules
- `slide-to-edge`: the object moves rigidly, unchanged, in the direction `direction_of_color` gives its color, until it touches the grid edge on that side; every other cell is `background`.

## Parameters
- `background`: `0`
- `direction_of_color`: `8` → right, `4` → down, `6` → up, `3` → left
    - one-to-one from the object colors of the evidence to the four directions; the train pairs fix `8`, `4` and `6`, and `3`, seen only in a test input, takes the one direction left over.

## Scene parameters
- `shape`: the 3×3 ring
    ```
    1 1 1
    1 0 1
    1 1 1
    ```
