# `Bbox.flush` — a set's displacement to the frame edge

A per-key readout on `Bbox`: the displacement toward `d` whose size is the set's own margin from edge `d`. Composed with any position, it carries that position as far as the set can travel toward `d` before its leading cell reaches the frame border, so a solver that slides a body flush to an edge states the travel in one atom. The known sites read the margin off the box and turn that number into a jump toward the same direction.

```
// inside Bbox<Key>

.decl flush(key: Key, d: Dir, delta: Shift)
flush(K, D, Delta) :- edge_min(K, D, M), jump_delta(D, M, Delta).
```

Not: `Bbox.advance` (a displacement the size of the set's own extent, which steps the set past its own footprint); `Dock` (a slide that halts at first contact with a stopper set); lib `Slide` (a point mover resting on the last free node of a set); `Settle` (bodies resting against one another); `Bbox.margin` (the four margins as one Position, with no travel); a jump of a stored or counted length; `displacement` onto a named target.

Match: a rule that binds a `Bbox` instance's `edge_min(_, D, M)` and feeds that `M` to `jump` or `jump_delta` toward the same `D`. Grep `edge_min` and `jump` in one rule over `programs/solvers/`. Also prose naming a shape or body slid, pushed, or jumped flush to a grid edge.

Survey: 2026-09-09 05:36

Callers:

- `62593bfd` — `paint`: a blob slides along one axis until its box touches the destination edge, which is `params.paired_dir` for a partnered blob and the opposite edge for a lone one.
- `320afe60` — `paint`: each shape slides until its box touches its class's edge, closed shapes toward `params.closed_dir` and open shapes toward the opposite edge.
- `5623160b` — `ink`: each detached piece travels away from the anchor it touches until its leading cell reaches the grid edge.
- `05a7bcf2` — `push_shift`: the push structure travels its own margin from the far edge, as one body. The rule is the signature verbatim, and this is the one site that consumes the bare `Shift`. It sits under the `$Slide` case; the `$Pack` case of the same solver encodes the task without it.
- `62b74c02` — `copy`: a copy of the ink block is stamped flush at the empty edge, the block's margin standing for the travel.
- `20a9e565` — `drawn`: each drawn stage's cells move so that the stage's trailing box edge lies on the grid's trailing edge, which puts every stage in one scene frame.
- `6ca952ad` — `flush`: each object of at least `params.heavy` cells falls flush to the `params.grav` edge. The rule is the signature verbatim, as a local rule beside the `Bbox` instance.

Near-misses:

- `496994bd` `img` under `$Seat` — reads `block.edge_min($U(), D, M)` but jumps toward `opposite(D)`, and jumps the block's reflection rather than the block. It is a flush of the reflected body, and its margin at the far edge equals the source's margin at `D` through the flip the rule already carries.
- `5ffb2104` `Settle.room`, first branch — every cell offers its own travel to the frame edge and `rest` keeps the least, but the same minimum also ranges over travel that stops behind another body.
- `17829a00`, `11dc524f` — `reach` / `halted`, the slide-until-halted pattern, each halting at a stopper set.
- `4acc7107` `move` — each shape travels by `displacement` onto a computed slot in a lane, a named target rather than the frame edge.
- `4a21e3da` `moved`, `d13f3404` and `feca6190` `seated` — content laid flush into a corner through `corner_anchor` over a box frame or an output frame. The placement fixes two edges at once and crosses frames, so no Dir-keyed travel exists.
- `505fff84` `out` through `shift.inner` — each segment re-expressed from its own bounding frame into a smaller output frame, which is a `Reframe`.
- `1e0a9b12` `fallen`, `3906de3d` and `3618c87e` `landed`, `5e6bbc0b` — content packed against an edge per line. The cells compress by rank or land at `dist(P, D, 0)`, so no set keeps its shape and no margin is read.
- `4522001f` `sq_jump`, `22208ba4`, `447fd412` — a jump the size of the set's own extent, which is `Bbox.advance`.
- `271d71e2` `paint` — the travel is `advance.low`, the lesser of a marker gap and a gauge count.
- `16b78196` `seat_flush` — pieces resting on another body's face.

Spec question:

- **Both readouts.** Should the readout come in both forms, the `Shift` and a position-carrying peer such as `flush_at(key, d, p, q)`? Five of the six callers carry a cell and write `edge_min` plus `jump`, two atoms; with the `Shift` alone they write `flush` plus `compose`, still two. Only `05a7bcf2` consumes the bare delta. Lib carries both readings of a travel elsewhere, as `jump` beside `jump_delta` and `neighbor` beside `step_delta`.
- **`d` stays a `Dir`.** No site asks for a `DiagDir`. The corner sites `4a21e3da`, `d13f3404`, and `feca6190` fix two edges at once through `corner_anchor` and cross frames, so a Dir8 widening would serve none of them.
- **`edge_min` stays exposed.** `20a9e565` reads the same `sbox.edge_min` value twice, once as the travel at `drawn` and once at `slot` as a line offset. `flush` covers the first reading only.

Survey: 2026-09-09 05:57, over the solvers at or after the first survey's time

That pass read `626c0bcc`, `6165ea8f`, `5ffb2104`, and `62593bfd`. It found no new caller. What the entry records about `62593bfd` and `5ffb2104` still holds after their edits.

It adds one reading to the **Both readouts** point. `5ffb2104` `Settle.room` produces a `Shift` that `compose` consumes and that the comp's subsumption compares directly through `nearer`. Were a `Bbox` to stand over its bodies, the first branch would become one `flush` atom in the bare `Shift` form, a second bare-`Shift` consumer beside `05a7bcf2`. That branch sits in a proposal comp rather than a solver rule, and its least is taken jointly with the second branch, so it stays a near-miss.

Survey: 2026-09-10 01:18, over the solvers at or after the second survey's time

That pass read the solvers that `since "2026-09-09 05:57"` lists. It found no new caller: the signature hit only `320afe60`, `5623160b`, and `62593bfd`, unchanged. Every other `edge_min` read in scope is a comparison, a rank key, or a zero test, with no travel.

New near-misses:

- `6ad5bdfd` `Settle.room`, first branch — the same per-cell travel to the frame edge as `5ffb2104`, its least taken jointly with the blocked-cell and body-ahead branches.
- `64a7c07e` `landed`, `5521c0d9` `Parse.moved`, `22233c11` `echo_cell`, `58e15b12` `trace` — a jump the size of the set's own extent, which is `Bbox.advance`.
- `1caeab9d` `slide`, `234bbc79` `slide`, `4c3d4a41` `placed`, `321b1fc6` `shift`, `34cfa167` `shift`, `3ed85e70` `place`, `4c177718` `placement` — `displacement` onto a named target.
- `18447a8d` `landed` — a jump by a stored or induced margin, not the piece's own box margin.
- `20981f0e` `landing` — every translation inside a tile, filtered by a stored margin, `centered`, or a unit step off a wall.
- `05f2a901`, `56dc2b01` — lib `Slide` over shift candidates halted by a stopper set, which is `Dock`.
- `2697da3f` `arm_margin` — a figure seated at margin 0 on a new canvas through `DirPack` and `Reframe`; it crosses frames.
- `25c199f5` `moved`, `3d6c6e23` — per-line packing against an edge by rank.

The spec question stands as recorded: `6ad5bdfd` is a second `Settle` site whose `room` produces the bare `Shift`, and it stays a near-miss for the reason the 05:57 note gives.
