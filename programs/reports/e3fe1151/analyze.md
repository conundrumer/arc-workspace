# e3fe1151

## Concept
- Fits every pair, and the test (`check_concept.py`, `probe_models.py`).
- The cross is the center row and the center column of `divider_color`, which split the grid into four equal quadrants. The reference content of a quadrant is the multiset union of the four quadrants' non-blank colors, each color at the highest count it has in one quadrant. Each blank takes the color its quadrant lacks against that union.
- The concept is undefined where a quadrant's missing colors do not match its blanks, one for one in count, or where a quadrant lacks two different colors. The scene claims `blanks` and `shared-multiset` rule these inputs out.
- No witness with verdict `other` exists.
- The rule as the generator applies it: the generator gives the four quadrants one multiset, permutes it in each quadrant, and blanks one cell of each. The multiset union recovers that multiset wherever each of its colors shows its full count in some quadrant, which `shared-multiset` states. Train0 shows that a color can be absent from three quadrants: 5 is missing from TL, TR and BL.

## Choice points
- `reference-multiset`
    - `concept`: the multiset union of the quadrants' non-blank colors, each color at its highest count in one quadrant
    - `$SetUnion`: replaces `fill-missing` with the set of colors that some quadrant holds, and fills a blank with the color of that set that its quadrant does not hold. It is undefined where a quadrant holds every color of the set and has a blank. It fails Fit at train2: TR (rows 0–1, cols 3–4) holds 4, 5 and 3, so its blank at (1,3) gets no color.
    - `$ModalCount`: replaces `fill-missing` with each color at its modal count across the four quadrants. It is undefined where the counts of a color tie. It fails Fit at train0: 5 has count 0 in three quadrants, so TL's blank at (0,0) gets no color. It also fails train1 and train2.
- `blank-color`
    - `concept`: a blank is a cell of `divider_color`, one parameter for the cross and the blanks
    - `$OwnBlankColor`: replaces `blanks` with a parameter `blank_color` (7 in this task), stored apart from `divider_color`. It is undefined where the concept is undefined, at `blank_color` in place of `divider_color`. It fits every pair. Witness `blank-color-apart` stands at `blank_color` = 0, and it breaks the scene claim `blanks` (a blank there is 0 in a 7 cross). Plausibility `variant`, verdict `$OwnBlankColor`. It breaks this invariant of the inputs: every blank has the color of the cross. The concept is undefined there at every assignment.
- `cross-location`
    - `concept`: the center row and the center column, which split the grid into equal quadrants
    - `$LineCross`: replaces `cross` with the one full row and the one full column of `divider_color`. It is undefined where the grid holds no full row or column of that color, or more than one. It fits every pair. Witness `blank-row-across-top` stands at the stored assignment, and it breaks the scene claim `blanks` (`blanks_per_quadrant` is 2 in the top quadrants and 0 in the bottom ones, and the blanks of the two top quadrants form row 0). Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: each quadrant holds exactly one blank. `$LineCross` finds two full rows and is undefined there.
- `blank-color` & `cross-location`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A blank fills from a fixed counterpart cell (a D4 image of the grid, the same cell in another quadrant, or a D4 image within the quadrant): `probe_positional.py` finds no such map that gives the fill at all 16 blanks of the pairs. The best map fits 2 of 4 blanks.
- A reference multiset taken from the other three quadrants alone: a color's count in the union of all four is the higher of its count in the other three's union and its count in the quadrant itself, so the colors a quadrant lacks are the same under both. The model is equivalent to the concept.
- A blank fills with the color whose grid-wide count is short of a multiple of the quadrant count: grid-wide counts do not say which blank takes which short color, so this reading has to fall back to the concept's per-quadrant comparison.
- Which missing color goes to which blank where a quadrant lacks two different colors: the property exists only at `blanks_per_quadrant` above 1, which no input shows, and nothing in the pairs orders the blanks or the colors.
- 7 as a color of the shared multiset: a blank and a 7 of the content cannot be told apart, so no model reads such content.

## Tickets filed
- none
