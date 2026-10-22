# c658a4bd

## Concept
- Several square outlines of different sizes lie scattered and overlapping; stack them concentrically, the largest outside and each smaller one just inside the one before, and crop to the largest.

## Scene
- `square-per-color`: each non-`bg` color draws one square: the outline of a square, or a solid square when its side is 1 or 2.
- `distinct-sizes`: the squares have distinct side lengths.
- `sizes-step`: sorted by side, the sides fall by `size_step` from the largest to the smallest, and the smallest side is 1 or 2.
- `partly-hidden`: a square may cross another square, which then covers some of its cells, and a square may run past the grid edge; each square keeps enough cells to show its side.

## Rules
- `output-size`: the output is a square whose side is the largest square's side.
- `concentric-rings`: the output's ring at depth k from its edge takes the color of the square of the k-th largest side, the largest at depth 0.

## Parameters
- `bg`: 0

## Scene parameters
- `size_step`: 2
    - the difference between the sides of two squares adjacent in size order
