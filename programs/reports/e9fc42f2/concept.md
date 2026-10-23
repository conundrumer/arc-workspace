# e9fc42f2

## Concept
- Puzzle pieces with colored connectors on their edges snap together: two connectors of one color touch face to face, and the output is the assembled shape.

## Scene
- `field`: a field of `background` holds several pieces, each a 4-connected set of non-`background` cells, with `background` between any two pieces.
- `pieces`: each piece is drawn in `body`, and holds one or more connector cells, each of a color that is neither `body` nor `background`.
- `connector-side`: each connector lies on exactly one edge of its piece's bounding box, and faces out from that edge.
- `connector-pairs`: each connector color occurs once or twice in the input; the two connectors of a pair lie on different pieces and face opposite directions.
- `one-assembly`: the pairs link every piece into one connected assembly with no cycle, and in that assembly no two pieces overlap.

## Rules
- `snap`: each piece moves by translation alone, so that the two connectors of each pair are adjacent cells, each one step past its partner's facing edge.
- `crop`: the output is the bounding box of the assembly; each cell of a piece keeps its color, unpaired connectors included, and every other cell is `background`.

## Parameters
- `background`: 2
- `body`: 1

## Scene parameters
none
