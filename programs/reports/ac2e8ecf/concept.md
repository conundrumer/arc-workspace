# ac2e8ecf

## Concept
- Hollow rectangles float up and crosses sink down; each kind piles against the frame edge and against its own kind, and passes through the other kind.

## Scene
- `objects`: on a `background` field, every input holds several one-colored 4-connected objects, each either a hollow rectangle of 1-cell-thick border or a cross (one horizontal and one vertical straight segment crossing at a cell inside both, so four arms of any lengths).
- `no-final-overlap`: after both kinds settle, no rectangle cell and no cross cell land on the same cell.

## Rules
- `kind`: a shape that by itself closes off a background region from the frame edge (4-adjacency) is a rectangle; every other shape is a cross.
- `rect-rise`: every rectangle moves as a rigid body toward `rect_heading` until one of its cells meets the frame edge or a cell of a rectangle that has stopped ahead of it; rectangles that block each other move together.
- `cross-sink`: every cross moves the same way toward `cross_heading`, stopping at the frame edge or a cross that has stopped ahead of it.
- `kinds-ignore`: a body of one kind is not blocked by a body of the other kind.
- `paint`: the output is the input's frame, `background` everywhere except the settled cells of every body, each in its own color.

## Parameters
- `background`: 0
- `rect_heading`: T
    - the direction hollow rectangles travel
- `cross_heading`: B
    - the direction crosses travel

## Scene parameters
- none
