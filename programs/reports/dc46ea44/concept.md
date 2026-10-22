# dc46ea44

## Concept
- A hook on one side of a line goes to the same place on the other side, and takes the other object with it: the object hangs from the hook's tip, with the inner lower corner of its box on the tip.

## Scene
- `background`: every cell that is not the divider, the hook or the object has color `background`.
- `divider`: one full line of color `divider`, across `lift_dir`, cuts the grid into two halves of equal size, and the half toward `lift_dir` is all background.
- `hook`: the other half holds one 8-connected object of color `hook`, of shape `hook_shape`: a stem of three cells along `lift_dir`, a foot cell one step past the stem's end away from `lift_dir` and one step toward `tip_dir`, and a tip cell one step from the foot toward `lift_dir` and one step toward `tip_dir`.
- `object`: that half holds one more 8-connected object apart from the hook, of one color that is not `hook`, `divider` or `background`, of any shape.

## Rules
- `clear-source`: every cell of the half that held the hook becomes background.
- `keep-divider`: the divider stays as it is.
- `hook-across`: the hook is translated toward `lift_dir` by the size of one half plus the divider, so that it takes the same place in the other half that it had in its own.
- `hang-object`: the object is translated so that one corner of its bounding box lies on the hook's tip, the hook's cell farthest toward `tip_dir`; that corner is the one away from `lift_dir` and away from `tip_dir`; the object's cells are drawn over the hook.

## Parameters
- `background`: 7
- `divider`: 4
- `hook`: 6
    - the color of the hook
- `lift_dir`: up
    - the direction from the hook's half to the empty half
- `tip_dir`: left
    - the side of the hook's stem that holds its tip

## Scene parameters
- `hook_shape`: the cells (0,0), (1,0), (2,0), (3,-1), (2,-2), relative to the stem's cell farthest toward `lift_dir`, at `lift_dir` up and `tip_dir` left
