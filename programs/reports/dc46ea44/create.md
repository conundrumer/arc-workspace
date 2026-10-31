# dc46ea44

## Departures
- Witness `hook-color-swapped`: the case `$TipSideDerived` is defined, which differs from `witnesses.json` (undefined). With the hook found by color, the 6 object is taken as the hook. Its stem is column 4 and its other cell lies right of it, so the tip side is right and the tip is unique. `witnesses.json` gave this case the concept's output without working out its own tip.
- Witness `hook-color-swapped`: the case `$TipByOffset` is defined, which differs from `witnesses.json` (undefined). The tip read at a fixed offset from the stem's top cell is one cell, so the tie among the 6 object's leftmost cells does not arise. That is the branch's rule as `analyze.md` states it.
- Witness `background=DominantColor`: the concept case (bg 7 on a 9 field) gives a total grid, which differs from `witnesses.json` (undefined). The program draws only the hung cells that land on the frame, so an object that partly leaves the grid is clipped. It does not make the case undefined. The derive run recorded this witness as `bg=DominantColor`, and the copy from `witnesses.json` was removed as a duplicate.
- Witness `hook-mirrored`: the case `$TipByOffset` is defined, which differs from `witnesses.json` (undefined). On that input the offset tip lies off the frame, and the object is placed against that tip and clipped at the frame, as above.
- `$HookByShape & $TipSideDerived` reads the tip side from the hook's stem, as every other `$TipSideDerived` case does. `analyze.md` gives the side at which the stored shape matched. The two give the same side on every object that has the stored shape, because the foot and the tip lie on the tip side of the 3-cell stem.
- The `background=DominantColor` name is written `bg=DominantColor`, the solver's parameter name.

## Judgments
- Hint `head-repeat` on `lifting`: kept with `@ignore`. The `HalfKey` column is the key that `ink`, `comps`, `larger` and `halfbox` are keyed by, and deriving it at each use would repeat the Choice destructuring.
- Hint `chain-join` on `side_cand`: the relation was removed. `$HookByShape` now has one `hook` clause per `Side` branch.
- Hints `single-consumer` on `ready` and `match`: both were inlined.
- `@ignore: store` on `short_of`, `half` and `full_line`: each is fixed by the divider's cells, so storing it is the same interpretation as storing the divider's cells.
- Witness `tip-side-up` (built): it is train0's input with `tip_dir` reassigned to up. It separates `$SideStored & hang_corner=stored`, which takes the stem's top cell as the tip, from `$TipSideDerived`, which takes the leftmost cell. Witness `tip-side-up` resolves the `witness` report that no run showed those two cases differing. It carries no `@witness` line. If it is judged, it is `variant $TipSideDerived` (`@relaxed hook`, `@reassigned tip_dir`): the generator pairs train0's input with train0's output.
- `deletions`: 25 deletions change no pair's output. Each is a uniqueness or undefinedness check (`two_places`, `second_line`, `spare`, the `$LiftTowardEmpty` emptiness tests) or a clause of a case that no pair separates. The pairs never instantiate those structures, and the witnesses do, so all of them stay.
- `$LiftMirror`, `$HookOverObject`, `$AnchorCell` and `$CopyAcross` have no constructor: each fails Fit, as `analyze.md` gives.
- Keywords: `decompose` (the divider), `objects`, `move`, `bbox` (the object's box corner goes on the tip).

## Unsettled
- The `@store` branch for the divider's cells (`store` offers it, with witness train0 turned a quarter turn). The audit rejects a `@store` line on the relation `divider`, because the parameter `divider` has the same name, and the relabeling run failed. The relation is marked `@workaround`. Renaming the relation and running `store` and the audit again would settle it.
- Determination: `sweep` stopped at its 120 s timeout. There is no Determine comp. `determination-plan` lists `tip_offset`, `hook_side`, `hook_up`, `tip_dir`, `hook` and `lift_dir` (over the enumeration limit), `hook_shape` (undecided), and `bg` and `divider` (proposer-covered). A `lift_dir` relation read from the edge lines (blank edge in every input, inked edge in every output) was tried. It fails at witness `hook-off-divider`, where the lifted hook does not reach the edge, so it was removed. A determination per parameter, with `lift_dir` read from the side of the divider that the ink moves to, would settle this.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
