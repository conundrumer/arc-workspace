# e45ef808

## Concept
- The concept fits every pair: train0, train1 and test0 come out exact under [probe.py](probe.py).
- No witness has the verdict `other`.
- train1 is the only pair with a tie: cols 7 and 11 both have ground height 5. The output puts the peak line at col 11, which fixes `tie_side` to R. The orientation-free readings `$TieFarFromValley` and `$TieNearEdge` fit train1 as well, so the pairs do not separate them from the concept.
- The concept is undefined where columns tie for the least ground height. The `valley-tie` witness shows such an input, a variant task gives one routinely, and its verdict is `$ValleyTieSide`.
- The concept stores every color and `ground_side`. At a recolored or turned input it returns the input or is undefined, and the derived branches give the verdict output there (`sky-recolored`, `ground-recolored`, `$GroundSideFromBorder`).

## Choice points
- `peak-tie`
    - `concept`: among the columns that tie for the greatest ground height, the one nearest the `tie_side` edge
    - `$TieFarFromValley`: replaces `peak-line`'s tie clause. The tied column farthest from the valley column wins. It reads no `tie_side`. It is undefined where two tied columns are equally far from the valley, or where the valley is undefined. It fits every pair. Witness `peak-tie-valley-right`: breaks no scene claim, stored assignment, `ordinary`, verdict `concept`.
    - `$TieNearEdge`: replaces `peak-line`'s tie clause. The tied column nearest a grid edge wins, whichever edge that is. It reads no `tie_side`. It is undefined where two tied columns are equally near the edges. It fits every pair. Witness `peak-tie-edge`: breaks no scene claim, stored assignment, `ordinary`, verdict `concept`.
    - `$TieAll`: replaces `peak-line`'s tie clause. Every tied column takes the peak line. It fails Fit at train1, where it also paints col 7.
    - `$TieNearValley`: replaces `peak-line`'s tie clause. The tied column nearest the valley column wins. It fails Fit at train1, where it picks col 7.
- `valley-tie`
    - `concept`: none. The concept assumes `one-deepest-valley` and is undefined where columns tie for the least ground height.
    - `$ValleyTieSide`: replaces the scene claim `one-deepest-valley` and adds a tie clause to `valley-line`. Among the tied columns, the one nearest the `tie_side` edge takes the valley line. It reads `tie_side`, one parameter with `peak-line`'s. It is undefined nowhere the concept is defined. It fits every pair. Witness `valley-tie`: breaks `one-deepest-valley`, stored assignment, `variant`, verdict `$ValleyTieSide`. The invariant it breaks is that each input has exactly one column of least ground height.
    - `$ValleyTieAll`: the same replacement, with every tied column taking the valley line. It fits every pair. Witness `valley-tie`, as for `$ValleyTieSide`.
    - `$ValleyTieFarFromPeak`: the same replacement, with the tied column farthest from the peak column taking the valley line. It is undefined where two tied columns are equally far from the peak. It fits every pair. Witness `valley-tie`, as for `$ValleyTieSide`.
- `height-measure`
    - `concept`: ground-based. The rank reads `ground_color` cells.
        - `ground-measure`
            - `concept`: a column's height is the distance from the `ground_side` edge to its farthest `ground_color` cell
            - `$GroundCount`: replaces the height in `peak-line` and `valley-line` with the column's count of `ground_color` cells. It fits every pair. Witness `ground-hole`: breaks `solid-ground`, stored assignment, `foreign`, verdict `$CastFromBorder`. The invariant it breaks is that each column's ground is one run from the bottom edge.
    - `$LowestSky`: replaces the height in `peak-line` and `valley-line` with the distance from the `ground_side` edge to the column's `sky_color` cell nearest that edge. It reads no `ground_color`. It is undefined where no column has a sky cell. It fits every pair. Witness `ground-hole`, as for `$GroundCount`.
- `line-extent`
    - `concept`: each `sky_color` cell of the chosen column takes the line color
    - `$CastFromBorder`: replaces `peak-line`'s and `valley-line`'s fill. The line runs from the border edge toward `ground_side`, paints `sky_color` cells, and stops at the first `ground_color` cell. It fits every pair. Witness `ground-hole`: breaks `solid-ground`, stored assignment, `foreign`, verdict `$CastFromBorder`. The invariant it breaks is the same as for `$GroundCount`.
- `ground_side`
    - `concept`: stored, B
    - `$GroundSideFromBorder`: derives `ground_side` as the edge opposite the one line that is all `border_color`. It reads `tie_side` as stored. Where `tie_side` lies on the ground axis, no column is nearer it, and the model is undefined at a peak tie. It is undefined where no line, or more than one line, is all `border_color`. It fits every pair. Witness `$GroundSideFromBorder`: breaks `border-row` and `solid-ground`, stored assignment, `variant`, verdict `$GroundSideFromBorder`. The invariant it breaks is that the border is the top row.
- `sky_color`
    - `concept`: stored, 1
    - `sky_color=DominantColor`: derives `sky_color` as the input's commonest color. It is undefined where two colors tie for commonest. It fits every pair. Witness `sky_color=DominantColor`: breaks no scene claim, stored assignment, `ordinary`, verdict `concept`.
    - `$SkyColorFromLayout`: derives `sky_color` as the color of the line next to the border line, on the side toward the ground. It is undefined where that line has more than one color. It fits every pair. Witness `sky-recolored`: breaks `sky-and-ground`, stored assignment, `variant`, verdict `$SkyColorFromLayout`. The invariant it breaks is that the sky is 1 in every input.
    - `sky_color=SharedColor`: derives 0, 1 and 6 on each input. It fails Fit at train0, where the outputs at 0 and 6 are not the pair's output.
- `ground_color`
    - `concept`: stored, 6
    - `$GroundColorFromLayout`: derives `ground_color` as the color of the line at the `ground_side` edge. It is undefined where that line has more than one color. It fits every pair. Witness `ground-recolored`: breaks `sky-and-ground` and `sky-in-every-column`, stored assignment, `variant`, verdict `$GroundColorFromLayout`. The invariant it breaks is that the ground is 6 in every input.
    - `ground_color=SharedColor`: derives 0, 1 and 6 on each input. It fails Fit at train0.
- `peak_color`
    - `concept`: stored, 4
    - `peak_color=OutNewColor`: derives no value on an input alone, because `ex_out` is empty there. It is undefined on every input and fails Fit at train0.
- `valley_color`
    - `concept`: stored, 9
    - `valley_color=OutNewColor`: derives no value on an input alone. It fails Fit at train0.
- `peak-tie` & `valley-tie`, `peak-tie` & `height-measure`, `peak-tie` & `line-extent`, `peak-tie` & `ground_side`, `peak-tie` & `sky_color`, `peak-tie` & `ground_color`, `valley-tie` & `height-measure`, `valley-tie` & `line-extent`, `valley-tie` & `ground_side`, `valley-tie` & `sky_color`, `valley-tie` & `ground_color`, `height-measure` & `line-extent`, `height-measure` & `ground_side`, `height-measure` & `sky_color`, `line-extent` & `ground_side`, `line-extent` & `sky_color`, `line-extent` & `ground_color`, `ground_side` & `sky_color`, `ground_side` & `ground_color`, `sky_color` & `ground_color`, and each of these with `peak_color` or `valley_color`: the two branches' changes applied together
    - `$TieFarFromValley` & `$ValleyTieFarFromPeak`: each tie is broken by the distance from the other line's column. The model is undefined where the peak and the valley both tie.
- `height-measure` & `ground_color`: the two branches' changes applied together
    - `$LowestSky` & `$GroundColorFromLayout`: `$LowestSky`'s model alone, because that model reads no `ground_color`. Under `$LowestSky`, the `ground_color` property exists only with `$CastFromBorder`, and there the two changes apply together.

## Open parameters
- none

## Not formed
- The lines also paint the border row: every train output keeps row 0 as 0, and no reading gives it the line colors.
- A derivation of `tie_side`: no proposer gives a direction from the inputs. Of the readings that give a side from the input, `$TieFarFromValley` is the one that the pairs support.
- A derivation of `border_color`: the program does not read it. It is a scene parameter.
- `peak_color` or `valley_color` derived by `AnyOutNewColor`, `ChangedPairs` or `VanishedNewPairs`: each reads `ex_out`, which is empty on an input alone, so each is undefined like `OutNewColor`.
- Ground as connected objects (4- or 8-adjacency): the ground is one component in every input, and an object reading ranks the same columns, so no different model comes from it.
- A peak tie broken by the shape of the hill around it: in train1, cols 7 and 11 are both one-column summits, and no shape measure of the pairs separates them other than position.

## Tickets filed
- none
