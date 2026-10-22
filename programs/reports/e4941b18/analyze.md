# e4941b18

## Concept
- Fits train0, train1, train2 and test0 at the stored assignment (`probe.py`).
- No witness has the verdict `other`.
- The concept file's rule is the rule as the generator applies it on every input the scene allows. Off the scene, at `cell-in-fall-column`, the generator stops the falling mark on the first cell that is not background, which is `$FallUntilBlocked`. The concept's "falls to the grid edge" agrees with that wherever the fall column is background, which `background` gives.
- The concept is undefined where the marks do not stand in the line next to the block on its side away from `gravity`, or where the landing cell is outside the grid.

## Choice points
- `block-identity`
    - `concept`: the block is the cells of `block_color`, one solid rectangle.
    - `$BlockAsNonBackground`: replaces `block`; the block is the bounding box of the cells whose color is none of `background`, `pusher_color`, `pushed_color`; reads no `block_color`; undefined where the concept is. Fits every pair. Witness `stray-cell-beyond-block`: breaks `background`; at the stored assignment; `borderline`; verdict `concept`; breaks the invariant that every input holds only the colors 7, 5, 2 and 8.
- `fall-stop`
    - `concept`: the pushed mark falls to the grid edge toward `gravity`.
    - `$LandOnBlockBase`: replaces `pushed-falls-off`; the pushed mark lands in the line of the block's side toward `gravity`; no other parameter; undefined where the concept is. Fits every pair. Witness `block-above-floor`: breaks `block`; at the stored assignment; `variant`; verdict `concept`; breaks the invariant that the block's bottom row is the grid's bottom row.
    - `$FallUntilBlocked`: replaces `pushed-falls-off`; the pushed mark falls until the next cell toward `gravity` is off the grid or not `background`; no other parameter; undefined where the concept is. Fits every pair. Witness `cell-in-fall-column`: breaks `background`; at the stored assignment; `borderline`; verdict `$FallUntilBlocked`; breaks the invariant that every input holds only the colors 7, 5, 2 and 8, and that the column beside the block is background down to the grid edge.
- `push-side`
    - `concept`: the pushed mark leaves by the block's end in the direction from the pusher toward it.
    - `$NearestEnd`: replaces `pushed-falls-off`; the pushed mark leaves by the block's end nearer to it. Fails test0: the pushed mark at test0 input (9,10) is nearer the block's right end (col 17), and test0 output has the pushed color at (18,0).
- `run-length`
    - `concept`: the pushed mark stops at the first cell past the block's end.
    - `$SlideToGridEdge`: replaces `pushed-falls-off`; the pushed mark slides to the grid edge in the push direction, then falls. Fails train0: it lands at (8,8), and train0 output has the pushed color at (8,6).
- `pusher-destination`
    - `concept`: the pusher takes the cell the pushed mark left.
    - `$PusherToBlockEnd`: replaces `pusher-takes-place`; the pusher moves to the last cell over the block in the push direction. Fails train0: it puts the pusher color at (4,5), and train0 output has it at (4,4).
- `gravity`
    - `concept`: `gravity` is stored.
    - `$GravityFromMarks`: replaces the stored `gravity` in `block` and `marks-on-top`; gravity is the direction from the marks' line toward the block, as the clauses derive it from the side of the block the marks stand on; reads no `gravity`; undefined where the marks stand on no side of the block. Fits every pair. Witness `marks-beside-block` (train1 input turned a quarter turn counterclockwise): breaks `block` and `marks-on-top`; at the stored assignment; `variant`; verdict `$GravityFromMarks`; breaks the invariant that the marks stand above the block.
- `background`
    - `concept`: `background` is stored.
    - `background=DominantColor`: derives `background` as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair (7 is the commonest color in each input). Witness `background=DominantColor`: breaks no scene claim; at the stored assignment; `ordinary`; verdict `concept`.
    - `background=SharedColor`, `background=VanishedColor`: each gives every color of one input, 2, 5, 7 and 8. Fails train0.
    - `background=ChangedColor`, `background=UnchangedColor`, `background=OutNewColor`, `background=AnyOutNewColor`: each reads `ex_out` and gives no value on one input, so the model is undefined on every input. Fails train0.
- `pusher_color`
    - `concept`: `pusher_color` is stored.
    - `pusher_color=RarestColor`: gives 2 and 8 on each input, a tie. Fails train0.
    - `pusher_color=SharedColor`, `pusher_color=VanishedColor`, `pusher_color=DominantColor`: give 2, 5, 7 and 8, or 7. Fails train0.
    - `pusher_color=ChangedColor`, `pusher_color=UnchangedColor`, `pusher_color=OutNewColor`, `pusher_color=AnyOutNewColor`: give no value on one input. Fails train0.
- `pushed_color`
    - `concept`: `pushed_color` is stored.
    - `pushed_color=RarestColor`: gives 2 and 8 on each input, a tie. Fails train0.
    - `pushed_color=SharedColor`, `pushed_color=VanishedColor`, `pushed_color=DominantColor`: give 2, 5, 7 and 8, or 7. Fails train0.
    - `pushed_color=ChangedColor`, `pushed_color=UnchangedColor`, `pushed_color=OutNewColor`, `pushed_color=AnyOutNewColor`: give no value on one input. Fails train0.
- `block_color`, under the concept branch of `block-identity`
    - `concept`: `block_color` is stored.
    - `block_color=DominantColor`: gives 7, whose cells form no solid rectangle. Fails train0.
    - `block_color=RarestColor`, `block_color=SharedColor`, `block_color=VanishedColor`: give 2 and 8, or 2, 5, 7 and 8. Fails train0.
    - `block_color=ChangedColor`, `block_color=UnchangedColor`, `block_color=OutNewColor`, `block_color=AnyOutNewColor`: give no value on one input. Fails train0.
- Each two of `block-identity`, `fall-stop`, `push-side`, `run-length`, `pusher-destination`, `gravity`, `background`, `pusher_color`, `pushed_color`, and `block_color` with each of those but `block-identity`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored push direction: train0 pushes right and train2 pushes left, so no stored direction is a property the pairs leave undetermined.
- The pushed mark's side taken from its place against the block's center: it reads a center, a number that counts nothing the task has, and so has no relational form; its relational counterpart is `$NearestEnd`.
- A pusher or pushed role told by place in place of color: the pusher is left of the pushed mark in train0 and right of it in train2, so only the colors tell the two apart.

## Tickets filed
- none
