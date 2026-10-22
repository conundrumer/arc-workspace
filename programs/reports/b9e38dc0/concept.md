# b9e38dc0

## Concept
- A cup drawn as an outline holds some liquid; the liquid fills the cup and pours out of the cup's open side as a stream that widens along the cup's walls, continued past their ends, to the grid edge, and each other object in the liquid's way blocks it, so that no liquid reaches the cells behind it.

## Scene
- `background`: the most common color fills the rest of the grid.
- `cup`: one outline of one color, the largest object, whose walls are chains of cells joined at sides or corners; it closes off a region on every side but one, where its two walls end on one line across a gap, the mouth.
- `liquid`: one or more cells of one other color lie inside the cup.
- `walls-repeat`: each wall, near the mouth, repeats one step pattern, and has one cell on each line across the flow.
- `obstacles`: other cells of colors other than the cup's and the liquid's lie on the background, some of them inside the cup or in front of the mouth.

## Rules
- `fill-cup`: each background cell the liquid reaches by side steps, without passing a wall or the mouth line, takes the liquid color.
- `flow`: the stream moves straight out of the mouth, away from the cup, to the grid edge.
- `widen`: each wall is continued past its end by repeating its last step pattern, to the grid edge; on each line across the flow, from the mouth line on, the stream holds the cells strictly between the two walls.
- `pour`: a background stream cell takes the liquid color when the cell straight behind it along the flow holds the liquid; where that cell is a wall, drawn or continued, it takes the liquid color when the nearest cell between the walls on the line behind holds the liquid. An obstacle holds no liquid, so it leaves a straight shadow behind it.
- `keep`: every other cell keeps its color.

## Parameters
- none

## Scene parameters
- none
