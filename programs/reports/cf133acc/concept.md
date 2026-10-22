# cf133acc

## Concept
- Broken bars stacked across the grid each have a one-cell gap over a short post that stands on the `post-side` edge; the post grows through the gaps toward the far edge, and past each bar it takes that bar's color, so each bar's color climbs from its gap to the next bar.

## Scene
- `background`: every cell that is not part of a bar or a post has the color `background`.
- `bars`: some lines perpendicular to `post-side`'s axis hold bars: runs of one color, each with a gap in each pole line it spans; runs of different colors can abut in one line.
- `posts`: some lines parallel to `post-side`'s axis, the pole lines, each hold a post: a run of one color from the `post-side` edge toward the far edge that stops before the bar nearest that edge in the line.
- `poles`: every bar's gap lies in a pole line; a gap is a `background` cell whose two neighbors along the bar's line have the bar's color.

## Rules
- `post-grows`: in each pole line, the cells between the post and the gap nearest `post-side` (or the far edge, where the line holds no gap) take the post's color.
- `bar-color-climbs`: in each pole line, each gap in that line, and the cells from it toward the far edge up to the next gap in the line (or up to the far edge), take that bar's color.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `post-side`: bottom
    - the edge the posts stand on; the bar colors climb toward the opposite edge

## Scene parameters
- none
