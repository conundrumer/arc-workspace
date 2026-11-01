# Rigid implementation

What the [rigid](../arclog/rigid.md) form replaces in the Souffle lib, the evidence for it, and how the Souffle backend builds it.

## What it replaces

- The Souffle `RIGID` block, with its placed names `<block>_<rel>` and the lint category that keeps them out of reach. A stored part that the block's determination does not write is a frame part.
- The runner's comparison of a chart instance with the stored value up to pose. With an `instance` clause, the form also replaces the determination that picks one instance as the chart.

## Evidence

A solver that stores data a task states in a frame of its own keeps it in a Souffle `RIGID` block. `timeout 30 grep -lE RIGID programs/solvers/*.dl` lists the solvers that hold one. A solver without a block is open to conversion when it stores such data in one of these ways:

- It closes a stored shape over D4 or C4 by hand, lists one row of a table per orientation the observed data shows, or searches C4 by hand, because the instances stand in several orientations.
- It stores a stamp and the direction attached to it separately, though every instance in the observed data has one pose. The block makes the two one assembly.

A solver that finds its template in the input it runs on stores no shape in a frame.

Values that look posed and are not:

- A D4 value that is the turn between two placements, such as 291dc1e1's `rot` and 3e980e27's `stamp_d4`.
- A symmetry of the grid, or the transform of a tile in a tile arrangement.
- An orientation the task distinguishes. In 626c0bcc each orientation of the L-triomino paints its own color, and in ed74f2f2 two mirrored keys name different colors.
- A stored shape that is symmetric under D4.

Note from principal: It seems RIGID was not used as often as it should have because its gloss in patterns.md was unclear. 

## Implementation

The Souffle backend takes one instance's reading as each assembly's frame. For each instance, it finds the elements that take the frame's reading onto that instance's reading over every part at once, as `Agreement` does for one cell set with its D4 images as the correspondences. When every instance has such an element, it writes `&marker.<part>` as the closure of the frame's reading over D4, and `&marker.pose` as the elements it found. An element is found for an instance where the image of the frame under it, at the part columns that are the assembly's own Idents, maps onto the instance's reading by one one-to-one renaming of those Idents, the same renaming at every part. The choice of the frame instance is arbitrary, and the Pose type and the own-Ident type of [The pose](../arclog/rigid.md#the-pose) make it unobservable.
