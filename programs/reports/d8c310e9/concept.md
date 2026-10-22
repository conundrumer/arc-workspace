# d8c310e9

## Concept
- A strip of a repeating pattern starts at one edge and stops partway; continue repeating it until it reaches the far edge.

## Scene
- `background`: every cell outside the pattern is `bg`.
- `segment-at-edge`: the drawn segment starts at the edge opposite `dir` and runs toward `dir`, and every line across the segment (a column, for `dir` right) holds a cell that is not `bg`; past the segment's end every cell is `bg`.
- `segment-on-ground`: the drawn content rests on the `ground` edge, and the line along that edge is not `bg` across the whole segment.
- `segment-periodic`: the segment is periodic along `dir` with a period less than its length, so it holds one whole tile and at least part of a second.
- `segment-short`: the segment stops before the far edge.

## Rules
- `period`: the tile length is the smallest period of the segment along `dir`: the least p ≥ 1 at which each line of the segment equals the line p further along `dir`, wherever both lie in the segment.
- `extend`: each cell of the output takes the cell of the segment that lies a whole number of periods back toward the start edge, so the output is the tile repeated from the start edge to the far edge, cut off at the far edge.

## Parameters
- `bg`: 0
- `dir`: right
    - the direction in which the pattern continues

## Scene parameters
- `ground`: bottom
    - the edge the content rests on
