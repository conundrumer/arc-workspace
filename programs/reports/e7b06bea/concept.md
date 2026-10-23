# e7b06bea

## Concept
- A short bar at the top of the left edge sets a run length, and the colored stripes at the right edge are folded into one column next to them: that column takes the stripe colors in turn, each for a run as long as the bar, from the top down.

## Scene
- `background-field`: every cell that is not in the bar or in a stripe is `background`.
- `corner-bar`: one bar of `bar_color` lies along the `bar_edge` edge, starts at the corner of that edge with the `start_edge` edge, and is shorter than that edge.
- `edge-stripes`: two or more adjacent full-length lines parallel to the `stripe_edge` edge fill the grid up to that edge; each stripe is one color, the stripe colors are different from each other, and none is `background` or `bar_color`.
- `stripe-gap`: at least one line of `background` stands between the bar and the line next to the stripes on the bar side.

## Rules
- `keep-bar`: the bar stays as it is.
- `clear-stripes`: each stripe cell becomes `background`.
- `folded-line`: the line next to the stripe block on the bar side takes the stripe colors in turn, starting with the stripe nearest to it and moving toward the `stripe_edge` edge, then starting again; each color fills a run of cells as long as the bar, and the runs start at the `start_edge` edge.

## Parameters
- `background`: 0
- `stripe_edge`: right
    - the edge that the stripes fill up to
- `start_edge`: top
    - the edge where the bar starts and where the first run starts

## Scene parameters
- `bar_color`: 5
- `bar_edge`: left
    - the edge the bar lies along, opposite `stripe_edge`
