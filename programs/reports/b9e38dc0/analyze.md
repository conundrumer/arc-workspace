# b9e38dc0

## Concept
- The concept case fits every pair (train0–2 and test0), as `work/task/b9e38dc0/probe.py` shows. It has no witness with verdict `other`.
- It stores no parameter: the background, the cup, the liquid and the flow direction all derive from each input.
- It is undefined where a wall's end shows no repeating step pattern (scene claim `walls-repeat`), and where no cup holds liquid.
- The liquid passes from cell to cell, so an obstacle leaves a straight shadow. A cup that the liquid cannot fill up to the mouth pours nothing.

## Choice points
- `wall-continuation`
    - `concept`: each wall continues past its end by repeating its last step pattern (`widen`).
    - `$DiagonalCone`: replaces `widen`: the stream widens by one cell on each side per line from the mouth. Fails Fit at train2: the walls there step out one column per two rows, and row 1 holds cols 4–10 where the cone gives cols 3–11.
    - `$StraightStream`: replaces `widen`: the stream keeps the mouth's width. Fails Fit at train0: row 11 col 4 is 9.
    - `$LastStepOnly`: replaces `widen`: each wall continues by its last step alone. Fails Fit at train2: the last step is straight up, and row 0 cols 3 and 11 are 3.
- `blocking`
    - `concept`: an obstacle holds no liquid, so it blocks the stream (`pour`).
    - `$NoBlock`: replaces `pour`: every background stream cell takes the liquid color. Fails Fit at train0: rows 12–14 cols 7–8 stay 1.
- `stream-feed`
    - `concept`: a stream cell takes the liquid from the cell straight behind it. A widening cell, whose behind cell is a wall, takes it from the nearest cell between the walls on the line behind (`pour`).
    - `$GeometricStream`: replaces `pour`: every background cell between the walls, from the mouth line on, takes the liquid color, except the cells straight behind an obstacle. This holds whether or not the liquid reaches the cell. It fits every pair. Witness `obstacle-at-stream-edge`: plausibility `ordinary`, verdict `concept`.
    - `$RefillBehind`: replaces `pour`: a stream cell takes the liquid when any of the three cells behind it, straight or diagonal, holds it. Fails Fit at train0: rows 12–14 cols 7–8 stay 1.
- `shadow-start`
    - `concept`: the liquid fills the cup around an obstacle in it (`fill-cup`). A shadow starts only where an obstacle stands in the stream or in the cup's line before the mouth.
    - `$CupShadow`: replaces `fill-cup` and adds to `pour`: each cup or stream cell straight behind an obstacle in the cup keeps its color. It fits every pair. Witness `obstacle-deep-in-cup`: plausibility `ordinary`, verdict `concept`.
- `cup-adjacency`
    - `concept`: the liquid fills the cup by side steps (`fill-cup`).
    - `$Flood8`: replaces `fill-cup`: the liquid also steps across corners. Fails Fit at train0: the liquid leaks through the corner-joined walls, for example from (7,6) to (8,5).
- `colors`
    - `concept`: the background, cup and liquid colors derive from each input (`background`, `cup`, `liquid`).
    - `$StoredColors`: stores those colors in place of deriving them. Fails Fit at train1: each pair has its own colors, and test0's liquid color 2 is in no train pair.
- `wall-continuation` & `blocking`, `wall-continuation` & `stream-feed`, `wall-continuation` & `shadow-start`, `wall-continuation` & `cup-adjacency`, `wall-continuation` & `colors`, `stream-feed` & `shadow-start`, `stream-feed` & `cup-adjacency`, `stream-feed` & `colors`, `shadow-start` & `cup-adjacency`, `shadow-start` & `colors`, `blocking` & `cup-adjacency`, `blocking` & `colors`, `cup-adjacency` & `colors`: the two branches' changes applied together
- `blocking` & `stream-feed`, `blocking` & `shadow-start`: `$NoBlock`'s model alone. No obstacle blocks under `$NoBlock`, so neither property exists with it. Both points stand under the concept branch of `blocking`, which is at the concept.

## Open parameters
- none

## Not formed
- A stream that falls downward whatever way the mouth faces: the liquid leaves leftward in train1 and upward in train2, through the mouth, so no reader of the pairs takes a downward fall.
- A wall continued along a straight line fitted through its cells: a fitted slope counts nothing the task has, so the claim has no relational form. On a wall that repeats a step pattern, it gives the concept's continuation.

## Tickets filed
- none
