# `GRID_STAMP` — anchored stamp stored as offsets, written as a picture

A GRID_STAMP call stores a mark-anchored stamp as `Shift` offsets: the layout is written as a picture with the anchor cell marked in it, and expansion emits each member cell as its offset from the anchor. The corpus form for this datum is a grid relation plus a distinguished-cell Position fact, which every consumer must reduce with `displacement` before it can compose at a mark; the macro does that reduction at expansion, so the slot is the gauge-invariant offset set the pairs exhibit and a Fit relation compares directly, with no bounding-box gauge fixing to recover a seat.

Two macros, following the GRID family:

- `GRID_STAMP_HxW(name, tokens...)` — mask tokens; emits `name(delta: Shift)`.
- `GRID_STAMP_SPARSE_HxW(name, tokens...)` — color tokens; emits `name(delta: Shift, col: Color)`.

Tokens: `_` is no cell; `1` in the mask form, or a color digit in the sparse form, is a member cell; an `@` prefix marks the anchor (`@1`, `@4`); `@_` is an anchor that is not itself a member, so a ring stamp emits no zero offset. Expansion errors: zero or several `@` cells; mask tokens under the SPARSE name or color tokens under the mask name.

Alongside, `GRID_SPARSE`'s absent token moves from `0` to `_`, which frees `0` to be stored as a color.

Code form:

```
.decl footprint(delta: Shift)
GRID_STAMP_3x3(footprint,
    1,  1, 1,
    1, @1, 1,
    1,  1, 1)
```

expands to the nine facts `footprint([-1, 1, -1, 1]).` … `footprint([0, 0, 0, 0]).` … `footprint([1, -1, 1, -1]).`

Not: a shape placed by search over its occurrences, with no distinguished cell (14754a24); a grid registered to a box margin or a corner rather than to a cell (17b866bd, 4522001f); a stored grid whose cells are read in place; `displacement` over derived positions at rule level.

Match: a Consts grid relation beside a distinguished-cell Position slot — `seat`, `anchor`, `center_pos`, or derived from a marker color inside the grid — reduced to offsets by `displacement` and composed at a mark. Grep `GRID_MASK|GRID_SPARSE` sites for a companion single-fact Position slot; the raw-offset form has no lexical signature beyond a `Shift`-typed Consts slot.

Spec questions: whether a stamp inside a `RIGID` block carries its anchor through the D4 pose cleanly, which the three RIGID sites need; whether `GRID_MASK`'s absent token also moves to `_` for family uniformity.

No survey dispatched; the callers below are from a corpus sweep (2026-09-02) and stand to be confirmed.

Callers:

- stored mask or sparse grid + anchor Position fact: 0ca9ddb6, 0962bcdd, 31aa019c, 3ac3eb23, 642d658d, 10fcaaa3, a9f96cdd, b60334d2, 3f23242b
- anchor derived from a marker color inside the grid: d364b489, dc1df850, 4258a5f9
- offsets stored raw: 20fb2937
- RIGID-wrapped, pending the RIGID spec question: 409aa875, 142ca369, 3aa6fb7a
- near-miss: 7fe24cdd (the grid's values are D4 elements, not colors)
- `GRID_SPARSE` `_` token change: 10fcaaa3, 21897d95, 3f23242b, 66e6c45b, 68b67ca3, 833966f4, a9f96cdd, b60334d2, d364b489, ca8de6ea
