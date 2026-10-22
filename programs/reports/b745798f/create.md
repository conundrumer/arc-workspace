# b745798f

## Departures
- The solver has a choice point `ArmSide` with the branches `$ArmShortSide` and `$ArmLongSide`, which the Analyze report lists under Not formed ("One arm length for both edges of a non-square grid"): Develop step 3 forms each Not formed claim. Each reading fits every pair, since every grid is square, and has a relational form: an edge cell and the cell at the same corner distance on the other edge through the corner (`counterpart`) both lie in their own edge's arm (shorter side), or one of them does (longer side).
- The witness file holds a witness `non-square` that the Analyze file does not hold. It is a 9×11 grid of four trominos, with the two left pieces in color 3 and the two right pieces in color 2. On it `$PerEdge`, `$ArmShortSide` and `$ArmLongSide` give three different grids, and each is defined.
- The concept branches take these names: `$Adjacent4`, `$Tromino`, `$ToMiddle` and `$PerEdge`.

## Judgments
- `non-square` is `borderline`, with verdict `concept`: it breaks `square-odd-grid` in the same way `even-side` does, and the concept's arms stop before the middle line of their own edge.
- The reading "the arm length comes from the vertical (or horizontal) side" is not formed: the task distinguishes no axis, so a stored axis would be an orientation the task does not distinguish.
- "The border ring colored by quadrant" (Not formed) fails Equivalence. A border cell strictly nearer both edges of corner g lies on an edge through g, nearer g than the far end of that edge, and the converse also holds wherever a piece exists (a piece needs two rows and two columns). So that model equals `$ToMiddle` on every input, and it has no constructor.
- "A stored arm length", "pieces scaled up into the corners" and "`background` derived by another proposer" (Not formed) fail Fit, for the reasons the Analyze report gives.
- The tromino test is number-free. It uses an elbow (a cell with piece neighbors toward both edges of the opposite corner) and a stray defect (a piece cell outside the elbow and those two neighbors). So the parameterization stays the concept file's, `background` alone, and no stored size 2 or count 3 is needed.
- `$PieceAnyL` reads the piece's `Bbox`: a piece is an L when no cell of the two box edges that meet at corner g lies outside it and no piece cell lies off those edges. An elbow toward g with no such defect can only be the box corner, so the `box_corner` atom was dropped (`deletions` listed it as changing nothing).
- `Components` and `Components8` are two instances: the `step` relation is part of the instance and takes no key.
- The three `case section` lint hints fired on the shared `arm` and `out` clauses, which stood under the `$ArmKeepsGap` marker. I moved those clauses above the markers.
- The other `deletions` entries stay. The pairs never instantiate them (every piece is a tromino, and every grid is square and odd), and the witnesses depend on them. The column `bend.id` was dropped, because no reader uses it.
- `@derive DominantColor` on `background` is the branch `background=DominantColor`, `variant` and `derived`, `@relaxed background-field`, as the Analyze report gives. `store` prints no `@store` line.
- The solver has no Determine comp: `determination-plan` reports that `DominantColor` covers `background` on the examples, and `sweep` reports a unique value of 8.
- Keywords: `objects markers perimeter`. The pieces are objects, each piece's bend points to a corner, and the arms run along the grid's border ring.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
