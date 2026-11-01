# c920a713

## Concept
- Rectangle outlines lie stacked on top of one another; draw the stack as nested square rings, the bottom outline outermost and the top outline at the center.

## Scene
- `background`: every cell that no outline covers is `background`.
- `stacked-outlines`: the input holds several rectangle outlines, one per color, each one cell wide; a cell where two or more outlines meet shows the color of one of them.
- `one-stack`: the order that `layer-order` gives ranks every outline, with no two outlines left unordered and no cycle.

## Rules
- `outline-box`: an outline is the least box with every cell of its color on its border and no background on its border, so a side that lies wholly under other outlines still counts.
- `layer-order`: an outline is above another when some cell on both outlines shows its color and no cell on both shows the other's; the stack is that order closed under transitivity.
- `nested-rings`: the output is a square of side 2n-1 for n outlines; the ring at depth k from the edge, 1 cell wide, takes the color of the outline k-th from the `center` end's opposite end, so the bottom outline is the outer ring and the top outline is the center cell.

## Parameters
- `center`: top
    - the end of the stack whose outline fills the center cell
- `background`: 0

## Scene parameters
- none
