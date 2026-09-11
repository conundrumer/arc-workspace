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

Survey: 2026-09-09 03:20 — the whole corpus.

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

Survey: 2026-09-11 05:33 — the solvers since 2026-09-09 03:20.

Callers:

8ba14f53 `offset` — the stacking offset of a shape's block: `before` orders the shapes by their nearest cell to `params.order_dir` (the group order), `block_line` holds each shape's lines in reading order along `params.axis` (the member order), and `offset` tallies the lines of every earlier shape so that each block starts on the line where the one before it ended; the flat rank of a line is that offset plus the line's own index in its block, which the solver realizes by jumping each block cell by the offset along `params.stack_dir`.

No second caller. The grep signature `Order<|LexOrder<|OrderFrame<|before\(` matched 15 sites in 13 solvers of the scope (212895b5, 291dc1e1, 5dbc8537, 6cbe9eb8, 85b81ff1, 8698868d, 88bcf3b4, 89565ca0, 8abad3cf, 8ba14f53, 8dae5dfc, 8e1813be, cf98881b); every `Order.before` rule but 8ba14f53's `before` compares one property of a flat domain or a per-key domain, and none reads a group and then a member. The `Tally`, `Ordinal`, and `Excess` instances in the scope (30 sites) count members of one key set; only 8ba14f53 `offset` counts the members of the groups an order puts before a group.

Near-misses:

- 8abad3cf `row` with `edge_off`: the squares are ordered flat by side or by debut, and each square's offset along the row accumulates the side of the square outward of it plus `params.gap`. The step is an extent plus a gap, not a count of items, so there is no flat rank to read; this is the exclusion the 2026-09-09 03:20 result gave for 4acc7107.
- 291dc1e1 `slot` with `reading`: the blocks are ordered flat by `LexOrder`, and each takes one slab of equal extent (`slab.extent` reads `widest.high`), so the stack is a `DirFrame` of slot indices glued by `concat_slab`; the members of a group never enter the order.
- 8dae5dfc `nest`: the object is the instance key, so the layers of each object are ranked in their own frame and no group order exists; the same exclusion as 3a25b0d8 in the 2026-09-09 03:20 result.
- 85b81ff1 `obj_order` with `moved`: `OrderFrame` ranks the objects by their lines, and each object moves into the bounding box of the object at its rank's place; the destination is a box the input already holds, not a rank in a packed sequence, and `OrderFrame` is on the entry's Not line.
- 212895b5 `step_order`: the compared fields are the out and across steps of one arm cell, compared conjunctively, which is the product order the 2026-09-09 03:20 result recorded.
- 8698868d `block_rank`, `piece_rank`: two flat `Order` instances over blocks and pieces, joined on equal rank; neither is a group of the other, and no flat rank forms.
- 89565ca0 `fewer`, 6cbe9eb8 `nest`, 88bcf3b4 `walk`, cf98881b `order`: flat `Order` instances over one domain each, with no second level.

Spec:

8ba14f53 answers the spec question the same way as the three callers of the 2026-09-09 03:20 result: its member order is the line's reading-order index, read from `reading.rank` with no reference to the shape, so `member_before` needs no group column. Two observations rest on this caller alone and are reported as caller-only, not as changes. First, its members are lines rather than cells: the cells of a line place by composing the line's flat rank with the cell's across component, the composition `OrderFrame.pos` describes, so `rank` typed over an opaque `Member` serves it as written. Second, the solver reads only the group-level part of the flat rank (`offset`, the count of items of earlier groups) and lets the block's own geometry carry the member index; a caller in that form reads `rank` at a group's first member, or `rank` directly at each line, and either way the interface needs no separate readout.

Reimplementations: none.

Search method: grep over the scope for `Order<`, `LexOrder<`, `OrderFrame<`, and `before(` (15 hits, 13 solvers); a parser matcher for a head whose derivations split into two branches each holding a strict comparison (1 hit, 8abad3cf `row.before`, which is two case rules); a wider matcher for a rule with a disjunction holding a strict comparison, two strict comparisons, or a strict comparison beside a variable equality (2 hits, 212895b5 `entered` and 89565ca0 `out`, both flat); a listing of `Tally`, `Ordinal`, and `Excess` instances (30 sites) read for a count over an ordered set; and a read of the headers of every scope solver whose concept line carries `rank`, `pack`, `move`, or `count` (37 solvers).
