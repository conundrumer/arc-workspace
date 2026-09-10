# `GRID_STAMP` — anchored stamp stored as offsets, written as a picture

A GRID_STAMP call stores a mark-anchored stamp as `Shift` offsets: the layout is written as a picture with the anchor cell marked in it, and expansion emits each member cell as its offset from the anchor. The corpus form for this parameter is a grid relation plus a distinguished-cell Position fact, which every consumer must reduce with `displacement` before it can compose at a mark; the macro does that reduction at expansion, so the parameter is the gauge-invariant offset set the pairs exhibit and a determination relation compares directly, with no bounding-box gauge fixing to recover a seat.

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

Not: a shape placed by search over its occurrences, with no distinguished cell (14754a24); a grid registered to a box margin or a corner rather than to a cell (17b866bd, 4522001f, 5b526a93, 3befdf3e, 60b61512); a stored grid whose cells are read in place; `displacement` over derived positions at rule level.

Match: a grid parameter beside a distinguished-cell Position parameter — `seat`, `anchor`, `center_pos`, or derived from a marker color inside the grid — reduced to offsets by `displacement` and composed at a mark. Grep `GRID_MASK|GRID_SPARSE` sites for a companion single-fact Position parameter; the raw-offset form has no lexical signature beyond a `Shift`-typed parameter.

Survey: 2026-09-09 04:55

The survey covered every solver. No solver stores a stamp as raw offsets: the parsed `Shift`- and `Inset`-typed Params declarations, in 11 files, each hold a translation, an inset, or a wallpaper period.

Six callers confirm the motive. `dc1df850`, `4258a5f9`, `d364b489`, and `20fb2937` each run a `BoxFrame` in their Determine for no purpose but turning an offset set back into a picture, and `20fb2937` recovers its seat as `frame.inner($U(), ORIGIN, P)`. `b60334d2` and `a9f96cdd` instead compose the stored seat back onto each offset. All six determinations collapse to emitting the offsets.

Spec questions:

- The code form shows only the unkeyed macro, and the keyed form is in use: `0ca9ddb6` stores two masks under one shared `center_pos`, and `409aa875` and `21897d95` store id-keyed charts with a per-id anchor. The macro takes the leading key arguments the GRID family takes, and its expansion error for zero or several `@` cells is stated per key.
- An offset set drops the picture's blank cells and its extent, which two callers read. `3f23242b` builds a `Frame2D` from the seat's extent and composes over every cell of it, because its `line_cell` tests `!placed(_, P)` across the whole box; `10fcaaa3`'s Determine builds its candidate frame the same way. Either the spec carries an extent readout beside the offsets, or those two keep the grid form.
- Whether the SPARSE anchor may carry a color. `b60334d2` and `31aa019c` both hold `0` at their anchor, which `@_` states; `3f23242b` holds `3`, the mark color itself, at its seat; `dc1df850` and `d364b489` derive the seat as the template cell holding the marker color, which `@` states in the picture.
- Whether `GRID_MASK`'s absent token also moves to `_` for family uniformity.
- Whether `@` may mark a content cell of a shape that `Occurrences` places. The four RIGID sites — `142ca369` (`launch`), `409aa875` (`apex`), `3aa6fb7a` (`gap`), `21897d95` (`center`) — each store a picture beside a distinguished cell in the picture's own frame, so the signature matches, but none uses `displacement`: the placement anchor comes from `Occurrences`, and the distinguished cell composes onto it directly. Their distinguished cell is content, not a seat that lands on a mark. The pose gauge is observable there all the same — `142ca369` and `3aa6fb7a` gauge-fix with `box.inner` in their determinations.

Callers:

- `0962bcdd` — `template_arm` / `template_center` + `center_pos`; two 5x5 role masks paint a plus-shaped marker's rays.
- `0ca9ddb6` — `template` + `center_pos`; a per-mark-color 3x3 mask paints a one-step star.
- `10fcaaa3` — `footprint` + `seat`, reduced to `stamp(off: Shift, col: Color)`; haloes every mark of the arrangement.
- `20fb2937` — `shape` + `seat`, reduced to `stamp_off(delta: Shift)`; grows each field cell into a block.
- `31aa019c` — `shape` + `shape_anchor`; rings the count-selected cell.
- `3ac3eb23` — `template` + `dot`; lays a 6x3 periodic trail from each top-row marker.
- `3f23242b` — `shape` + `seat`; seats a 5x5 bracket on each mark.
- `642d658d` — `fp_cell` + `anchor`, reduced to `fp_off(off: Shift)`; probes the offsets around a center cell for one shared color. The only caller that reads rather than paints.
- `a9f96cdd` — `template` + `seat`; paints the marker's four diagonal neighbors in per-corner colors.
- `b60334d2` — `template` + `seat`; paints a 3x3 ring around each marker.
- `d364b489` — `template` + `seat` derived as the template cell holding `marker`; paints a four-arm halo.
- `dc1df850`, with its family sibling `4258a5f9` — `template` + derived `seat`; paints an eight-neighbor halo.
- `8403a5d5` — `template_bar` / `template_dot` + `seat`; two 10x9 role masks lay the alternating bar-and-dot trail from a bottom-row marker.

Near-misses:

- registered to a box margin or a corner: `17b866bd`, `4522001f`, `5b526a93`, `3befdf3e`, `60b61512`
- a stored picture placed by occurrence search, with no distinguished cell: `14754a24`, `150deff5`, `3d588dc9`, `0607ce86`, `1818057f`, `7e02026e`, `6cf79266`, `2c0b0aff`, `ae4f1146`, `b1fc8b8e`
- a stored grid whose cells are read in place: `27a28665`, `ca8de6ea`, `ed74f2f2`, `d4469b4b`, `0934a4d8`, `269e22fb`
- `displacement` over derived box margins or corners, with no stored anchor: `4c5c2cf0`, `4c177718`, `543a7ed5`, `58f5dbd5`
- `7fe24cdd` — the grid's values are D4 elements, read in place under `apply`
- `137eaa0f` — `anchor` sits beside a frame derived from `frame_dim`, not a stored picture, and it carries input cells into that frame rather than a picture out onto the grid

`GRID_SPARSE` `_` token change: `10fcaaa3`, `21897d95`, `3f23242b`, `66e6c45b`, `68b67ca3`, `833966f4`, `a9f96cdd`, `b60334d2`, `d364b489`, `ca8de6ea`

Survey: 2026-09-10 08:22

Scope: the solvers that postdate the survey above. No new caller: the stored-picture-plus-seat sites in the scope are the four the entry already lists, unchanged in kind. No raw-offset stamp parameter exists in the scope.

Spec:

- Ten solvers derive a stamp from the input in the macro's output form, `(v: Shift[, col])` composed at a mark: `2c737e39`, `3e980e27`, `39e1d7f9`, `414297c0`, `36d67576`, `72322fa7`, `5168d44c`, `4c416de3`, `4938f0c2`, `1b60fb0c`. A stored stamp in the same form shares one consumer with an induced one.
- `7447852a` is a second near-miss that reads the picture's extent (`params.period` via `axis_dim` over `stamp`), beside `3f23242b` and `10fcaaa3` in the extent question.
- `6c434453` `$Stamp` is a fifth site for the "`@` on an `Occurrences`-placed shape" question: its distinguished cell is the anchor a separate replacement picture (`dst`) shares with the placed one.

Near-misses:

- a stored picture placed by occurrence search, with no distinguished cell: `25094a63`, `626c0bcc`, `652646ff`
- registered to a frame corner or edge: `6c434453`, `7447852a`
- a stored grid whose cells are read in place: `5a5a2103`, `794b24be`, `281123b4`, `44f52bb0`, `47c1f68c`, `cf98881b`
- a stamp induced from the input, `displacement` over derived positions at rule level: the ten solvers above

`GRID_SPARSE` `_` token change: `794b24be` joins the list.
