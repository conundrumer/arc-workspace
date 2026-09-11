# `Divide2D.cell` keyed — each key divides its own frame

The `cell` input of `Divide2D` and `Tile2D` takes the comp's `Key`, so the divided frame is per-key data beside `dim`. `dim` already varies per key, and a key whose frame varies with it has nowhere to put that frame: the instance-level `cell` holds the union of every key's frame, and each key divides that union. A key then produces tiles over cells outside its own frame, and a consumer that does not restrict the cell by key reads them.

Code form, in both comps:

```
.decl cell(key: Key, p: Position)

tile(Ky, P, P_outer, P_inner) :-
    cell(Ky, P), gap(G),
    ...
```

Not: `gap`, which stays instance-level; `DividerFrame`, whose per-key `cell` already exists; a per-key restriction written at the consumer, which leaves the union computed and the contract mismatched.

Match: a `Divide2D` or `Tile2D` instance whose `dim` is keyed by `Choice` or by an object id, and whose `cell` rule reaches its source through an anonymous or otherwise unbound key, so the fed domain is a union over keys. The same shape appears where the source relation is a `Reframe` or `BoxFrame` read (`inner`) and where it is a plain solver relation. Also match a hand-written per-key `divide` or `divide_2d` pair that a keyed `cell` would let a `Divide2D` state. State the shape in prose and match it with the parser.

## Callers

- `6b9890af` — `blocks.cell(P_inner) :- hole.inner(_, _, P_inner).` `dim` is keyed by `Choice`, and the divided frame is the frame color's hole, which each case finds for itself. With a keyed `cell` the rule is `blocks.cell(Ch, P_inner) :- hole.inner(Ch, _, P_inner).`
- `6ecd11f4` — `blocks.cell(P_box) :- shape_id(_, Sh), boxes.inner(Sh, _, P_box).` `dim` is keyed by `Choice`, and the divided frame is the shape's box, which the two cases select differently. With a keyed `cell` the rule binds the case: `blocks.cell(Ch, P_box) :- shape_id(Ch, Sh), boxes.inner(Sh, _, P_box).`
- `57aa92db` — `obj_grid.cell(P_inner) :- obj_box.inner(_, _, P_inner).` `dim` is keyed by `Ident`, and each object divides its own box, so the rule becomes `obj_grid.cell(O, P_inner) :- obj_box.inner(O, _, P_inner).`

The remaining callers key on `Unit`: `103eff5b`, `33067df9`, `363442ee`, `58743b76`, `5833af48` (three instances), `5ad4f10b`, `6aa20dc0`, `7c008303`, `f8b3ba0a`. Each feeds one frame, and migration adds the key: `cell($U(), P)`.
