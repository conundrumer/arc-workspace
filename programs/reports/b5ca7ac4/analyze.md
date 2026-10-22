# b5ca7ac4

## Concept
- Fits every pair, train and test (`check_concept.py`, with `Gravity` keyed by frame color). Each rule has a relational form: the stacking is `Gravity` with one key per frame color, and no clause approximates a rule. No witness has the verdict `other`.

## Choice points
- `body-parse`: what moves as one body
    - `concept`: each framed square, the outermost one-cell outline of a heading color around a one-color interior
        - `square-size`: which square sides the parse accepts
            - `concept`: any side
            - `box_size=stored`: replaces `framed-squares` with squares of the stored side `box_size` only (5), and adds the parameter `box_size`. It is undefined on an input with a square of another side. Fits every pair. Witness `box_size=stored`: two squares of side 4 at the stored assignment. The concept slides them, and the branch is undefined there. It breaks the scene claim `framed-squares` (side `box-size`). Plausibility `variant`, verdict `concept`. Invariant of the inputs it breaks: every square has side 5. The branch gives the concept's output wherever it is defined, so it looks subsumed by the concept case.
    - `$FrameComponents`: replaces `framed-squares` for the parse: a body is a 4-connected component of one frame color's cells together with the cells it closes off from the grid edge, and a component inside another body's closed-off cells belongs to that body. Fits every pair. Witness `touching-squares`: two 2-framed squares that share an edge, where the front one meets a stopped square and the rear one does not. The concept stops each square on its own, and `$FrameComponents` moves the joined pair by the lesser travel. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
        - `adjacency`: which cells join one component
            - `concept`: 4-adjacency
            - `$Adjacent8`: replaces 4-adjacency with 8-adjacency, so squares that touch at a corner only join one body. Fits every pair. Witness `corner-touch`: two 2-framed squares that touch at a corner only, each stopped by a different square ahead. The concept and `$FrameComponents` stop each one on its own, and `$Adjacent8` moves the pair by the lesser travel. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$InkComponents`: replaces `framed-squares` for the parse: a body is a 4-connected component of non-background cells, and its heading is the one frame color on its outer cells. It is undefined on a body whose outer cells hold both frame colors. Fails Fit at train2: the 2-framed square at rows 0–4, cols 12–16 touches the 8-framed square at rows 5–9, cols 12–16, and the body they form is undefined (test0 also, at rows 12–13, cols 10–13).
- `blocker`: what stops a sliding square
    - `concept`: the grid edge and the stopped squares of its own frame color. Squares of the other frame color pass through.
    - `$OtherBlocksAtStart`: replaces `stack-per-color`: the squares of the other frame color also block, at their input places. Fails Fit at train0: two squares land on one cell (train2 and test0 also).
    - `$SettleLeftFirst`: replaces `stack-per-color`: the 8-framed squares settle first, then the 2-framed squares fall with the settled 8-framed squares as obstacles. It is undefined where a settled square covers a cell of a square still to move. Fails Fit at train0 (train2 and test0 also).
    - `$SettleRightFirst`: the same with the 2-framed squares first. Fails Fit at train0 (train2 and test0 also).
- `stack-order`: how a square's resting place follows from the squares ahead
    - `concept`: the squares of one frame color fall together as rigid bodies (`Gravity`)
    - `$FarthestFirst`: replaces `stack-per-color`: the squares slide one at a time, farthest from the edge first, each stopping against the squares at their places at that moment. Fails Fit at train0: two squares land on one cell (train1 gives another grid).
    - `$CountAhead`: replaces `stack-per-color`: a square rests one side's length from the edge for each square of its frame color ahead of it that shares a row with it. Fails Fit at train0: the 6-square at rows 13–17 has two such squares, the 9-square and the 4-square, and lands at cols 7–11. The output has it at cols 12–16.
- `heading-source`: where a square's heading comes from
    - `concept`: the stored `heading` row of its frame color
    - `$HeadingOpposite`: replaces `slide-by-frame`: `heading` stores the 8-framed squares' direction, and the 2-framed squares slide the opposite way. Fits every pair. Witness `perpendicular-headings`, at the assignment `heading` = 8 → up, 2 → right: the concept slides the 2-square right, and `$HeadingOpposite` slides it down. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks no invariant of the inputs. The assignment breaks a regularity of the pairs, which is that the two headings lie opposite each other on one axis.
    - `$HeadingByInterior`: replaces `slide-by-frame` with a stored heading per interior color. Fails Fit at train0: interior 3 slides left in the 8-framed square at rows 3–7, cols 15–19, and right in the 2-framed square at rows 7–11, cols 4–8, so no table fits.
    - `$NearestEdge`: replaces `slide-by-frame`: each square slides toward the nearer side edge. It is undefined on a square centered across the grid. Fails Fit at train0: the 8-framed square at rows 3–7, cols 15–19 is nearer the right edge, and the output slides it left.
- `background`: the color of the cells no moved square covers
    - `concept`: the one color outside the squares in the input
    - `$BackgroundDominant`: replaces `background-rest` with the commonest color of the input. It is undefined on a tie. Fits every pair. Witness `crowded`: a 6×11 grid with two 8-framed squares, where 8 has more cells than the background 0. The concept fills the freed cells with 0, and `$BackgroundDominant` fills them with 8. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. Invariant of the inputs it breaks: every input is 22×22, and the background is its commonest color.
- `body-parse` & `blocker`, `body-parse` & `stack-order`, `body-parse` & `heading-source`, `body-parse` & `background`, `blocker` & `stack-order`, `blocker` & `heading-source`, `blocker` & `background`, `stack-order` & `heading-source`, `stack-order` & `background`, `heading-source` & `background`, `square-size` & `blocker`, `square-size` & `stack-order`, `square-size` & `heading-source`, `square-size` & `background`, `adjacency` & `blocker`, `adjacency` & `stack-order`, `adjacency` & `heading-source`, `adjacency` & `background`: the two branches' changes applied together
- `square-size` & `adjacency`: no case takes a non-concept branch at both, because they stand under different branches of `body-parse`

## Open parameters
- none

## Not formed
- A square stops where its bounding box meets another body's: under the concept parse every body fills its bounding box, so this is the concept's model. Under `$FrameComponents` it would be a further point on joined bodies, and no pair shows a joined body whose box differs from its cells.
- A stored background color: the background is 0, 4 and 1 across the train pairs, so no stored value fits. The concept derives it from the input.
- Squares push the squares of the other frame color: in train2 the 8-framed square at rows 5–9 and the 2-framed square at rows 8–12 cross each other's paths, and both reach the places the concept gives.

## Tickets filed
- 10-364_task_b5ca7ac4_analyze.md
