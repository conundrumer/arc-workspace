# cf5fd0ad

## Concept
- Four turned copies of the input form a pinwheel: each quadrant of the output holds one turn of the input, and that turn repeats two by two across the quadrant.

## Scene
- `square-input`: the input is a square of side `side`.

## Rules
- `quadrant-turn`: the output has four quadrants, and each one takes the input under the turn `quadrant_transform` gives it.
- `quadrant-repeat`: in each quadrant, the turned input repeats `copies` times on each axis, so the output side is 2 × `copies` × `side`.

## Parameters
- `quadrant_transform`: top-left `D4_HT`, top-right `D4_CW`, bottom-left `D4_CC`, bottom-right `D4_ID`
    - the D4 element that each quadrant applies to the input
- `copies`: 2
    - the number of copies of the turned input along each axis of a quadrant

## Scene parameters
- `side`: 3
