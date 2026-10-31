# faa9f03d

## Concept
- Damaged wires are repaired: each wire is a path of straight runs from grid edge to grid edge, and the output redraws every wire whole, filling its breaks, painting its corner markers in its own color, rerouting it where a turn marker shows it turns the other way, and laying the wires over one another correctly where they cross.

## Scene
- `background`: every cell no wire or marker takes holds `background`.
- `wires`: two or more wires, each of one color other than `corner_color` and `turn_color`, each a path of horizontal and vertical straight runs whose two ends lie on the grid edge; two wires meet only where they cross at right angles.
- `breaks`: a wire may be missing single cells along a run, each a `background` cell between two cells of its run.
- `corner-markers`: some cells of a wire, at its corners and ends, hold `corner_color` in place of the wire's color.
- `turn-marker`: a wire may hold a `turn_color` cell just past one of its corners, on the side away from the run it turns from, at the place of the wire's correct turn; the drawn wire there runs straight on through the corner instead, to its own edge end, and draws nothing past the `turn_color` cell.
- `crossing-shown`: at a crossing the input shows one of the two wires, or `background`.

## Rules
- `redraw-wires`: the output is `background` with each wire drawn whole in its color, breaks filled and `corner_color` cells in the wire's color.
- `reroute-at-turn`: where a `turn_color` cell stands past a corner, the wire's strand that runs straight on from that corner, to its end, is erased, and the wire runs from the corner through the `turn_color` cell straight on to the grid edge.
- `crossing-top`: each crossing shows the wire on top. A wire that a `turn_color` cell extends across another lies on top there. Where the input shows one of the two wires, the shown wire is on top unless one of the two wires carries a `corner_color` marker, and then the other wire is on top. Where the input shows `background`, the wire on top at the two wires' other crossings is on top.

## Parameters
- `background`: 0
- `corner_color`: 2
- `turn_color`: 4

## Scene parameters
none
