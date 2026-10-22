# d4a91cb9

## Concept
- The concept case fits every pair, train0–2 and test0 (`probe.py`). Every claim has a relational form: each path cell is a cell between the `start_color` mark and the corner on one line, or between the corner and the `end_color` mark on one line. No witness has verdict `other`.

## Choice points
- `corner`: the corner of the two marks' bounding box at which the path turns
    - `concept`: the cell on the `start_color` mark's line along `start_axis` and the `end_color` mark's line along the other axis (rule `corner`)
        - `start_color`: the color of the mark the first leg leaves
            - `concept`: stored, 8
            - `start_color=RarestColor`: the start color is each color of the input with the fewest cells; replaces the stored value of `start_color`; undefined on no input. Fits every pair, since on every input of the evidence the rarest colors are 8 and 2, and a path from the 2 to itself paints nothing. Witness `start_color=RarestColor`: an 8×8 input with 8 at (1,1), 2 at (6,6) and a third mark 3 at (2,5); the branch also draws a path from the 3 down col 5 to the 2. It breaks the scene claim `two-marks` and the invariant that every input holds exactly two non-background cells; plausibility `borderline`, verdict `concept`.
        - `end_color`: the color of the mark the second leg ends at
            - `concept`: stored, 2
            - `end_color=RarestColor`: the end color is each color of the input with the fewest cells; replaces the stored value of `end_color`; undefined on no input. Fits every pair, by the same reason as `start_color=RarestColor`. Witness `end_color=RarestColor`: an 8×8 input with 8 at (1,1) and two marks 2 at (6,6) and (4,3); the rarest color is 8 alone, so the branch draws no path and gives the input, and the concept joins the 8 to each 2. It breaks the scene claim `two-marks` and the invariant that every input holds exactly two non-background cells; plausibility `borderline`, verdict `concept`.
    - `$StartByPlace`: the first leg, along `start_axis`, leaves the mark nearer the edge `start_edge`, and the second leg ends at the other mark; the mark colors are not read. Replaces `corner` and the mark roles of `l-path`; adds the parameter `start_edge`. Undefined on an input whose non-background cells are not two, and on one whose two marks are equally near `start_edge`. Fails Fit at every value of `start_edge`: top fails train2, left fails train1, bottom and right fail train0.
    - `$CornerByLength`: the first leg from the `start_color` mark runs along the axis on which the two marks are farther apart, or nearer, by a stored choice `first_leg`. Replaces `corner`; adds the parameter `first_leg` in place of `start_axis`. Undefined on an input whose two marks are as far apart on one axis as on the other. Fails Fit at each value: farther fails train0 (rows apart 6, cols apart 8), nearer fails train2 (rows apart 9, cols apart 6).
- `path_color`: the color painted on the path
    - `concept`: stored, 4
    - `path_color=OutNewColor`: the path color is a color in every train output and no input. Replaces the stored value of `path_color`. In a run on one input `ex_out` is empty, so the derivation gives no value and the branch is undefined on every input. Fails Fit at train0.
- `start_color` & `end_color`, `corner` & `path_color`, `start_color` & `path_color`, `end_color` & `path_color`: the two branches' changes applied together. The case of `start_color=RarestColor` & `end_color=RarestColor` joins each rarest-color mark to each, which draws both L paths of a pair's two marks; it fails Fit at train0.

## Open parameters
- none

## Not formed
- `start_axis` horizontal: it is a value of the stored parameter, and the pairs fix it; at horizontal the model fails train0.
- A rule that pairs several marks of one color with several of the other, as by nearness: every input holds one mark of each color, and the concept's rule joins each `start_color` mark to each `end_color` mark, so such a rule replaces no claim of the concept.
- Marks on one row or column (`marks-off-line` broken): the concept's legs give the straight run between the two marks, which is the output a person expects, and no source gives another rule.
- A derivation of `bg`: the program reads no background color.
- A derivation of `start_axis`: no proposer gives an axis from one input of this task; the axis proposers read grid dimensions, which this task does not change.

## Tickets filed
- none
