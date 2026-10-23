# e69241bd

## Concept
- The concept fits every pair: rooms are the 4-connected components of the non-`wall` cells, and every pair holds one seed per seeded room (train0 2 seeds, train1 3, train2 3, test0 3).
- No witness has the verdict `other`. The concept is undefined where one room holds two seeds of different colors, which breaks the scene claim `seeds` (witness `two-seeds-one-room`).

## Choice points
- `connectivity`: the steps that join floor cells into a room
    - `concept`: the 4 cardinal steps
    - `$Adjacency8`: replaces `rooms` with 8-connected components; no parameters; undefined where an 8-connected room holds two seed colors. Fails Fit at train0: the diagonal gaps in the walls join seeded rooms, so a room holds both the 6 and the 8 seed, and the model is undefined. The same holds at train1, train2 and test0.
- `shared-room`: what the floor of a room with two seeds of different colors takes
    - `concept`: no grid; the model is undefined there
    - `$NearestSeed`: replaces `seeds` (it drops "no two seeds share a room") and `seed-fills-room`: each floor cell takes the color of the seed that a fewest-step 4-adjacent walk through the room reaches first; no parameters beyond the concept's; undefined where seeds of two colors tie at a cell. Fits every pair. Witness `two-seeds-one-room`: it breaks `seeds`, stands at the stored assignment, plausibility `borderline`, verdict `$NearestSeed`; the invariant it breaks is "each room of every input holds at most one seed".
- `background-source`: where the value of `background` comes from
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input; undefined where two colors tie for commonest. Fits every pair (0 is the commonest color in each input). Witness `background=DominantColor`: walls outnumber floor, the derived value is 5, and the model finds no floor cell and returns the input. It breaks no scene claim, stands at the stored assignment, plausibility `variant`, verdict `concept`; the invariant it breaks is "floor cells outnumber wall cells in every input".
    - `background=SharedColor`, `background=RarestColor`: on one input they give every color of the input, or the seed colors. Each fails Fit at train0.
    - `background=ChangedColor`, `background=UnchangedColor` and the other proposers that read `ex_out`: they give no value on an input alone, so the model is undefined on every input. Each fails Fit at train0.
- `wall-source`: where the value of `wall` comes from
    - `concept`: stored, 5
    - `wall=SharedColor`: every color of the input is a wall, so no room exists and the model returns the input. Fails Fit at train0.
    - `wall=DominantColor`: gives 0, so the floor is read as wall and the walls 5 as seeds. Fails Fit at train0.
    - `wall=RarestColor`: gives the seed colors. Fails Fit at train0.
    - `wall=UnchangedColor` and the other proposers that read `ex_out`: undefined on every input. Each fails Fit at train0.
- `seed-colors`: which colors seed a room
    - `concept`: every color other than `background` and `wall`
    - `$StoredSeedColors`: replaces `seeds` and `seed-fills-room` with a stored set of seed colors; parameter `seed_colors`: 1, 3, 4, 6, 7, 8; a cell of any other color seeds nothing and keeps its color. Fits every pair: the test seed colors 3, 6 and 8 are all train seed colors. Witness `unseen-seed-color`: a seed of color 2. It breaks no scene claim, stands at the stored assignment, plausibility `ordinary`, verdict `concept`.
- `connectivity` & `shared-room`, `connectivity` & `background-source`, `connectivity` & `wall-source`, `connectivity` & `seed-colors`, `shared-room` & `background-source`, `shared-room` & `wall-source`, `shared-room` & `seed-colors`, `background-source` & `wall-source`, `background-source` & `seed-colors`, `wall-source` & `seed-colors`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Only rooms closed off from the grid edge fill: the room of the 6 seed in train0 touches the top edge and fills, and so does the room of the 1 seed in train1.
- Only floor cells whose eight neighbors lie in the room fill, as in solver 09c534e7: the 1-wide corridors fill in every pair, for example train0 output col 2, rows 0–3.
- A seed is a single cell, with a size test on the non-floor non-wall pieces: every seed in the evidence is one cell, and no reading of the pairs gives a larger piece another role.
- `wall` as the second commonest color: no proposer gives one color by count rank (CountRankDesc gives color and rank pairs), and the program reads `wall` as one color.
- Paint that spreads through doorways into further rooms, as in solver 3ad05f52: the inputs have no doorways, and no fill crosses a wall cell in any pair.

## Tickets filed
- none
