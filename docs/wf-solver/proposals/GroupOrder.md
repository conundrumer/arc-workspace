# `GroupOrder<Key, Group, Member>` — the place an item takes when ordered groups are laid end to end

The rank each item holds when the groups are laid end to end in their own order and every group keeps its members in its own order, per key. A solver that runs several ordered groups together into one sequence — pieces packed into a row, runs written one after another — reads that flat rank from one instance, in place of stating the two-level comparison itself and carrying a group-and-member element through `Order`.

Code form:

```
.comp GroupOrder<Key, Group, Member> {
    .decl item(key: Key, g: Group, m: Member)             // input
    .decl group_before(key: Key, g: Group, g2: Group)     // input
    .decl member_before(key: Key, m: Member, m2: Member)  // input

    // The count of items before this one: every item of an earlier group,
    // and the earlier members of its own group.
    .decl rank(key: Key, g: Group, m: Member, r: number)
}
```

Not: `Order` over a flat domain, one instance per group; `LexOrder`, which orders the positions of one frame by a corner and an axis; `OrderFrame`, which builds a frame from the lines its members hold; two `Order` instances that rank groups and members apart and never form the flat rank.

Match: an `Order` instance whose `before` compares a group property of two elements and, where those groups are equal, orders the two within the group. The group is a record field at two sites and a property of the item at the third. Grep: `before\(.*\[` finds the record form alone.

Survey: 2026-09-09 03:20

Callers:

- 5d588b4d — `seq`: the run index orders the groups, the slot within a run orders the members, and the flat rank feeds `stride` to give each cell its line and its column.
- 4df5b0ae — `row`: cell count orders the shapes, the line index within a box orders one shape's lines, and each shape starts where the one before it ended.
- 3d6c6e23 — `fill`, its `$Sink` case: group size orders the color groups, and `above` orders the pixels inside a group. Its group is the pixel's color, a property of the item.

Near-misses:

- 4acc7107 — `shape_ord` with `color_ord`: the lane index and the slot index stay separate coordinates on two axes, and the layout steps by each piece's own extent, so there is no flat rank to read.
- 3a25b0d8 — `hole_rank`: the group sits in the instance key, so each group is ranked in its own frame and no group order exists.
- 212895b5 — `step_order`: the compared fields are the two coordinates of one cell, compared conjunctively, which is a product order.
- 1da012fc — `reading`, its `$Separated` case: two-level, but the levels are the two axes of one object, which is the order `LexOrder` names.

Spec question: does `member_before` carry the group? Every caller orders members without reading it — two compare a bare index, and the third reads a line that already sits in the instance key — so the code form above drops the column. Dropping it costs a task whose member order varies per group, which would fold the group into `Key` or into `Member`. No corpus site shows that task.
