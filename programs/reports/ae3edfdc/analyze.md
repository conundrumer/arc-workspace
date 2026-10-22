# ae3edfdc

## Concept
- The concept case fits every train pair and the test pair at the stored assignment (`background` 0, `pair` 2 → 3, 1 → 7). Each of its rules has a relational form: alignment on a row or a column, the cell next to a center toward a direction, and a stored color map.
- No witness has the verdict `other`.
- Where a cell of the input is matched to no center, the concept case paints it `background` (`rest-background`). `$KeepUnmatched` is the reading that keeps it in place.
- The evidence shows these invariants of the inputs, which the witnesses below break: every satellite is in its center's row or column; each side of a center has at most one satellite; each center color has one cell; the field is 0. Every input also has only the colors of `pair`, and the scene does not state this.
- Each center has at least two satellites in the evidence, and no scene claim states it. The witness `centers=RarestColor` gives a center a single satellite and breaks no scene claim.

## Choice points
- `satellite-color`: which non-center cells a center pulls
    - `concept`: the cells of the color `pair` maps the center's color to
        - `pair-source`: where the `pair` relation comes from
            - `concept`: stored, 2 → 3, 1 → 7
            - `$PairFromAlignment`: replaces the stored `pair` with a derivation from the input: c → s holds when c has exactly one cell and s, not `background`, has cells that all lie in a line through that cell, in the directions the case reads. It replaces `one-center-per-color` and `satellites-in-line`. Like the concept, it is undefined where two cells of different colors land on one cell. It fits every pair. Witness `pair-by-alignment`: center 2 and center 1 share a row, so the derivation also gives 2 → 1 and 1 → 2, and a copy of each center lands beside the other. Plausibility `ordinary`, verdict `concept`.
            - `pair=ChangedPairs`: fails Fit at train0. On an input alone, `ex_out` is empty, so it derives no pair, and the case is undefined.
            - `pair=VanishedNewPairs`: fails Fit at train0, for the same reason.
    - `$AnyColorSatellite`: replaces `pair` with a stored center set `centers` = {1, 2}. Each non-`background` cell whose color is not in `centers` and that lies in a line with a center cell is pulled to that center. It replaces `satellites-in-line` and `pull-in`. It is undefined where two cells land on one cell with different colors. It fits every pair. Witness `cross-aligned-satellite`: the 7 at (2,7) lies in the 1's column and in the 2's row, and this reading also pulls a 7 beside the 2. Plausibility `ordinary`, verdict `concept`.
        - `centers`: where the center set comes from
            - `concept`: stored, {1, 2}
            - `centers=RarestColor`: the colors of the input with the lowest cell count, ties included. It fits every pair, because 1 and 2 have one cell each and 3 and 7 have at least two. Witness `centers=RarestColor`: the 2 has a single 3, so the 3 is taken as a center and stays at (2,8). Plausibility `ordinary`, verdict `concept`.
            - `centers=SharedColor`, `centers=DominantColor`, `centers=VanishedColor`: fail Fit at train0. Each gives a set other than {1, 2} on the input alone.
            - `centers=UnchangedColor`, `centers=ChangedColor`, `centers=OutNewColor`, `centers=AnyOutNewColor`: fail Fit at train0. Each reads `ex_out`, which is empty on an input alone, so it gives no value.
- `line-directions`: the directions in which a satellite lies in line with its center
    - `concept`: the four cardinal directions
    - `$EightDirections`: the cardinal and the diagonal directions. A satellite on a center's diagonal moves to the diagonal neighbor. It replaces `satellites-in-line` and `pull-in`. Like the concept, it is undefined where two cells of different colors land on one cell. It fits every pair. Witness `eight-directions`: a 3 at (6,6) is on the 2's diagonal. The concept paints it background, and this reading moves it to (4,4). It breaks `satellites-in-line`. Plausibility `variant`, verdict `$EightDirections`. It breaks the invariant that every satellite is in its center's row or column.
- `same-side-landing`: where several satellites on one side of a center land
    - `concept`: all on the one cell next to the center
    - `$Stack`: the k-th nearest satellite on a side lands k cells from the center. It replaces `pull-in`. It fits every pair. Witness `stack`: two 3s lie left of the 2. The concept gives one 3 at (3,4), and this reading gives 3s at (3,4) and (3,3). It breaks `one-per-side`. Plausibility `variant`, verdict `$Stack`. It breaks the invariant that each side of a center has at most one satellite.
- `path-blocking`: whether cells between a satellite and its center stop it
    - `concept`: no. A satellite passes over every cell in its path.
    - `$SlideBlocked`: a satellite slides toward its center and stops next to the first non-`background` input cell in its path. It replaces `pull-in`. It fits every pair, because no pair has a cell between a satellite and its center. Witness `slide-blocked`: a 7 at (3,6) lies between the 2 and the 3 at (3,9). The concept moves the 3 to (3,4), and this reading stops it at (3,7). Plausibility `ordinary`, verdict `concept`.
- `several-centers`: which centers pull a satellite that lies in line with more than one center it is matched to
    - `concept`: each such center pulls a copy beside itself
    - `$NearestCenter`: only the nearest one, with ties keeping all. It replaces `pull-in`. It fits every pair. Witness `nearest-center`: two 2s share a row, and a 3 lies right of both. The concept puts a 3 beside each 2, and this reading puts one beside the nearer 2 only. It breaks `one-center-per-color`. Plausibility `variant`, verdict `$NearestCenter`. It breaks the invariant that each center color has one cell.
- `unmatched-cells`: what becomes of a non-center cell that no center pulls
    - `concept`: it becomes `background`
    - `$KeepUnmatched`: it stays in place. It replaces `rest-background`. It is undefined where a pulled cell lands on a kept cell with another color. It fits every pair. Witness `keep-unmatched`: a 3 at (6,8) is in line with neither center. The concept paints it background, and this reading keeps it. It breaks `satellites-in-line`. Plausibility `borderline`, verdict `$KeepUnmatched`. It breaks the invariant that every satellite is in its center's row or column.
- `background`: where the field color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input, ties included. It is undefined where two colors tie. It fits every pair. Witness `background=DominantColor`: the field is 5. The concept paints the field 0, and this reading keeps 5. It breaks `single-cells`, read at `background` 0. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the field is 0.
    - `background=SharedColor`, `background=RarestColor`, `background=VanishedColor`: fail Fit at train0. On an input alone, each gives more than one color.
    - `background=OutNewColor`, `background=AnyOutNewColor`, `background=ChangedColor`, `background=UnchangedColor`: fail Fit at train0. Each reads `ex_out`, which is empty on an input alone, so it gives no value.
- `satellite-color` & `line-directions`, `satellite-color` & `same-side-landing`, `satellite-color` & `path-blocking`, `satellite-color` & `several-centers`, `satellite-color` & `unmatched-cells`, `satellite-color` & `background`, `pair-source` & `line-directions`, `pair-source` & `same-side-landing`, `pair-source` & `path-blocking`, `pair-source` & `several-centers`, `pair-source` & `unmatched-cells`, `pair-source` & `background`, `centers` & `line-directions`, `centers` & `same-side-landing`, `centers` & `path-blocking`, `centers` & `several-centers`, `centers` & `unmatched-cells`, `centers` & `background`, `line-directions` & `same-side-landing`, `line-directions` & `path-blocking`, `line-directions` & `several-centers`, `line-directions` & `unmatched-cells`, `line-directions` & `background`, `same-side-landing` & `several-centers`, `same-side-landing` & `unmatched-cells`, `same-side-landing` & `background`, `path-blocking` & `several-centers`, `path-blocking` & `unmatched-cells`, `path-blocking` & `background`, `several-centers` & `unmatched-cells`, `several-centers` & `background`, `unmatched-cells` & `background`: the two branches' changes applied together
- `same-side-landing` & `path-blocking`: each satellite slides toward its center and stops against the first cell in its path at that cell's resting place. That cell is the center, a satellite that came to rest before it on the same side, or another non-`background` cell of the input. This is the `Gravity` reading, taken per center and side.
- `pair-source` & `centers`: no case takes a non-concept branch at both, because the two points stand under different branches of `satellite-color`.

## Open parameters
- none

## Not formed
- Landing distance as a parameter, with the satellite stopping k cells from its center: every pair fixes k at 1, and no reading of the concept leaves it open.
- A fixed step count for each satellite: the distances in train0 are 3, 2, 3 and 4, so it fails Fit.
- Centers moving toward their satellites, or satellites that leave a copy at their start cell: both fail Fit at train0.

## Tickets filed
- none
