# f8f52ecc

## Concept
- The concept fits every pair, and on every color of every pair its route is the only one with the fewest added cells and then the fewest turns (`work/task/f8f52ecc/check_concept.py`, `work/task/f8f52ecc/probe.py`). Background `1` and wall color `8` are stored. `8` is never joined, even where it shows as a 1- or 2-cell piece (test0 `(2,5)`, `(4,8),(4,9)`).
- The concept is undefined on an input where a color's cells cannot all be joined over background cells while avoiding walls, and where two colors' routes would paint one cell.
- No witness has verdict `other`. As the generator applies the rule, each color's dots are the ends and some bends of one hidden polyline that runs around the `8` walls, and the output draws that polyline. The concept file's rule approximates this by the route with the fewest added cells, then the fewest turns, that never doubles back. The approximation and the polyline differ only where a color's dots sit off any one polyline, as at `t-junction`, whose verdict goes to `$SteinerTree`.

## Choice points
- `join-shape`
    - `concept`: one simple route (a path) through all of a color's cells
    - `$SteinerTree`: replaces `join-dots` with the fewest-cell 4-connected tree joining the color's cells, ties broken by fewest straight segments (for a path, segments = turns + 1); same parameters; undefined where the concept is. Fits every pair: the trees with the fewest cells and then the fewest segments are exactly the concept's routes, found by full enumeration inside each color's bounding box grown by one cell (`work/task/f8f52ecc/steiner_enum.py`).
        - witness `t-junction`: dots `(1,3)`, `(6,3)` and `(2,0)` off their line. The concept gives the path up `(1,0)`, along row 1 and down col 3. The branch gives col 3 rows 1–6 plus row 2 cols 0–3. It breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `$SteinerTree`. It breaks the invariant that each color's dots lie on one polyline whose ends are dots.
- `tiebreak-order`
    - `concept`: fewest added cells first, then fewest turns
    - `$TurnsFirst`: replaces `join-dots` with fewest turns first, then fewest added cells; same parameters; undefined where the concept is. Fits every pair.
        - witness `two-walls-snake`: dots `(1,5)`, `(6,4)` with walls at row 3 cols 4–6 and row 5 cols 2–4. The concept winds between the walls (9 cells, 4 turns). The branch goes round by col 1 (11 cells, 2 turns). It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `obstacle`
    - `concept`: a route paints background cells only, so a dot of another color blocks it like a wall
    - `$CrossDots`: replaces `join-dots` (only `wall_color` cells block a route) and `keep-rest` (a dot of another color on a route keeps its color); same parameters; undefined where the concept is. Fits every pair: no pair has another color's dot on a route.
        - `crossed-dot`
            - `concept`: the crossed dot keeps its color
            - `$PaintOver`: the route paints the crossed dot in its own color; replaces `keep-rest`; same parameters, same undefined inputs. Fits every pair.
                - witness `dot-on-line` (shared with `$CrossDots`). Here `$PaintOver` gives row 2 all `2`, and `$CrossDots` keeps the `3` at `(2,2)`. Verdict `$CrossDots`, with the plausibility given below.
        - witness `dot-on-line`: `2` at `(2,0)`, `(2,4)`, a `3` at `(2,2)`, and a wall at row 3 cols 1–3. The concept detours along row 1. `$CrossDots` runs along row 2 and keeps the `3`. It breaks no scene claim and stands at the stored assignment. Plausibility `borderline`, verdict `$CrossDots`. It breaks the invariant that every route in the pairs runs over background cells only.
- `adjacency`
    - `concept`: 4-adjacent steps, turns counted between the 4 directions
    - `$Diagonal8`: replaces `join-dots` with 8-adjacent steps (another orientation type); same parameters; undefined where the concept is. Fails Fit at train0: color 2 has 8 tied diagonal routes, none of them the expected output. It also fails at train1, train2 and test1.
- `background`
    - `concept`: stored `background` = 1
    - `background=DominantColor`: derives `background` per input as its commonest color, replacing the stored value under `background` and `join-dots`; undefined also where the commonest color ties. Fits every pair (1 is the commonest color of every input).
        - witness `background=DominantColor`: a 4×5 input where `2` fills rows 1–3, with a row of `1` on top, `3` at `(1,0)`, `(1,4)` and an `8` at `(3,2)`. The stored model routes the `3`s over row 0. The derived model takes `2` as the field and runs the `3`s along row 1. It breaks the scene claims `background` and `dots` and stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that `1` is the commonest color of every input.
    - `background=RarestColor`: derives `background` as the rarest color of the input. Fails Fit at train0, where it gives `2`.
    - `background=SharedColor`: on one input it gives every color of that input. Fails Fit at train0, which gets three values (`1`, `2`, `8`) and so more than the one expected output.
- `join-shape` & `tiebreak-order`, `join-shape` & `obstacle`, `join-shape` & `adjacency`, `join-shape` & `background`, `tiebreak-order` & `obstacle`, `tiebreak-order` & `adjacency`, `tiebreak-order` & `background`, `obstacle` & `adjacency`, `obstacle` & `background`, `adjacency` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `wall_color` derived: on one input, no proposer gives `8`. `8` is neither the commonest nor the rarest color (train0: `8` has 6 cells, `2` has 4), and SharedColor gives every color of the input. UnchangedColor gives `8` but reads outputs, so it determines the stored value and is no branch.
- A rule for two colors' routes that share a cell: no pair has routes that meet. Settling the shared cell needs an order among colors, and colors have identity and no other property. Joint routing that keeps routes apart has no pair or variant behind it.
- A straight walker that turns only where blocked (the `2dd70a9a` header): it needs a start dot and a heading, and nothing in the input designates one. Its routes also turn where nothing blocks them (train1 turns at `(6,2)` in open field).
- Joining all non-background colors, `8` included: test0 leaves the 1-cell `8` at `(2,5)` and the `8` pair at `(4,8),(4,9)` unjoined, and the pairs fix `8` as the one color never joined.

## Tickets filed
- none
