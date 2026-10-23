# `LineColor<Key>` — the color a whole line holds

The one color each line of a frame holds throughout, per key: a line whose cells all carry one color pairs with that color, and a line whose cells disagree pairs with nothing. It is how a solver finds a separator, a stripe, a filled row or column, or a painted border edge, before anything reads what that line does. `DividerTiles` consumes cutting lines and leaves the finding to its caller, so every solver that cuts on a drawn line writes the finding itself.

```
.comp LineColor<Key> {
    .decl cell(key: Key, p: Position, col: Color)  // input

    // The axes whose lines are read, per key.
    .decl axis(key: Key, a: Axis)  // input

    .type _KAL = [key: Key, a: Axis, l: Position]

    .init one = Unanimous<_KAL, Color>
    one.item([K, A, L], Col) :- cell(K, P, Col), axis(K, A), split(P, A, L, _).

    // The line at l holds col and nothing else. l is the along component
    // `split` gives, so the line runs perpendicular to a — the convention
    // `DividerTiles.divider` takes.
    .decl line(key: Key, a: Axis, l: Position, col: Color)
    line(K, A, L, Col) :- one.value([K, A, L], Col).

    // The line at l carries more than one color.
    .decl mixed(key: Key, a: Axis, l: Position)
    mixed(K, A, L) :- one.clash([K, A, L]).
}
```

Not: a line that merely holds a color somewhere; the commonest color of a line (`Mode`); a maximal run of one color inside a line (`Runs`); `DividerTiles` (which takes the cutting lines as its input); a uniform region that is not a full line; a per-line test of something other than color agreement.

Match: a `Unanimous` instance over `Color`, keyed by an axis and a line position that `split` produces from the grid's cells — or the same agreement written by hand, as a clash rule over two cells of one line, or as a defect negation over a color class. Grep signature: `grep -ln 'Unanimous<' programs/solvers/*.dl` intersected with `grep -ln 'split(P, A' programs/solvers/*.dl`, then read the instance's `item` rule; for the hand-written forms, the shape is matched with the parser.

Survey: 2026-09-08 20:07

Survey: 2026-09-08 21:03, over the solvers at or after the first survey's time

The second survey read the eleven solvers whose file time is at or after the first survey's dispatch. It found no caller beyond `247ef758` and `538b439f`, whose edits after the first survey left the operation unchanged, and no near-miss beyond the classes the `Not:` line already names.

Survey: 2026-09-08 22:06, over the solvers at or after the second survey's time

The third survey read the fifteen solvers whose file time is at or after 21:03. It found no caller beyond `54d9e175`, and every near-miss falls in a class the `Not:` line already names; `40f6cd08` `rect_color` over a bounding box and `5614dbcf` `solid` over a tile join the uniform-region class.

Survey: 2026-09-08 22:28, over the solvers at or after the third survey's time

The fourth survey read the five solvers whose file time is at or after 22:06. It found no caller, and every near-miss falls in a class the `Not:` line already names: `5614dbcf` `solid` and `5587a8d0` `patch_color` join the uniform-region class, and `5614dbcf` `vote` and `5521c0d9` `common` the `Mode` class. `55783887` `params.line_color` is a name collision, over the color of two marks.

Survey: 2026-09-09 01:30, over the solvers at or after the fourth survey's time

The fifth survey read the twenty-four solvers whose file time is at or after 22:28. It found no caller beyond `5545f144`, which the entry already records, and no reimplementation of a lib primitive. Every near-miss falls in a class the `Not:` line already names: `5751f35e` `ring_color` and `5833af48` `uni` and `part_color` join the uniform-region class; `5833af48` `band_color` tests a fixed-size block of a line; `58e15b12` `drawn` keys the fold by cell, where a clash means two colors reach it; `5792cb4d` `lone`, `581f7754` `lone` and `sole`, and `409aa875` `lander` agree over `Position` rather than color; `58c02a16` `sep` and `57edb29d` `field` read a color off a line without testing the rest; `465b7d93` `edge_hole` negates a color class; `5a5a2103` `tile_line` and `56dc2b01` `back_line` define a line by which cells carry a color, with no agreement test.

Survey: 2026-09-09 20:58, over the solvers at or after the fifth survey's time

The sixth survey read the 102 solvers whose file time is at or after 01:30, and spot-checked the `Unanimous` instances of the rest of the scope. It found seven callers, listed below, and no reimplementation of a lib primitive. Edits after the fifth survey to `137f0df0`, `22eb0ac0`, `bdad9b1f`, and `409aa875` rewrite a `split` pair as `same_line` and leave the operation unchanged. Every near-miss falls in a class the `Not:` line already names: `4e7e0eb9` `divider`, `5daaa586` `divider`, and `6350f1f4` `content_line` negate a color class over a line that a crossing or noise breaks, so only the membership test passes; `17829a00` `move_dir` reads a color off the border edge without testing the rest; `2bee17df` `widest` and `5b692c0f` `line_pick` pick a line by extremum or `Mode`; `5ad4f10b` `run_color` agrees over a fixed-size segment of a line; `4aab4007`'s stripes run along a diagonal axis, which `split` does not produce; `bdad9b1f` `line` defines a line by two cells with no agreement test; `6350f1f4` `block_color`, `5dbc8537` `panel_ink`, `4e7e0eb9` `ink`, `85c4e7cd` `ring_color`, and `3a25b0d8` `fig_col` and `hole_col` agree over a region that is not a full line; `4e45f183` `tile_line` defines a line by position with nothing testing the rest; `5a5a2103` `legend_line`, `668eec9a` `line_row`, and `89565ca0` `line` are name collisions; `516b51b7` `phase_color`, `97999447` `slot_color`, `1c786137` `color_part`, `4e34c42c` `seam_cell`, `50846271` `owner`, `5b37cb25` `bite`, and `4aab4007` `steady` are `Unanimous` folds over keys that are not lines or values that are not colors.

Survey: 2026-09-09 22:10, over the solvers at or after the sixth survey's time

The seventh survey read the 284 solvers whose file time is at or after 20:58, by every `Unanimous` instance over `Color`, the parser shape, negated line-scoped rules, and the line-uniformity vocabulary. It found no caller beyond `66ac4c3b`, the surfacing solver, and no reimplementation of a lib primitive. Two near-misses fall outside the named classes and beside `58e15b12` `drawn`: `332202d5` `agree` and `45bbe264` `cover_color` fold over colors cast onto a line or a cell, not the line's own cells, so they are plain `Unanimous` uses. Every other near-miss falls in a class the `Not:` line names: `65b59efc` the `divider` of 65b59efc's tiling (a dashed line, never uniform), `4612dd53` `line` (a mark-count threshold), `1e32b0e9` `divider_color` (line by position), `4290ef0e` `line_cell` (`Runs`), `4be741c5` `commonest` (`Mode`), `2c181942` `obj_color`, `3ed85e70` `clue_palette`, `5117e062` `fill` (uniform regions that are not lines), `221dfab4` `phase_color`, `4c7dc4dd` `canvas` and `image`, `54d9e175` `image` (agreement keyed by something other than a line), `195c6913` `field` (no line), `47996f11` `mirror_mismatch` and `351d6448` `change` (agreement between different lines). `16de56c4` `.type LineColor` is a name collision.

## Callers

None of them are family siblings.

`Unanimous<Line, Color>` over both axes of the whole grid — the entry's code form, almost verbatim:

- `0bb8deee` — `line_color`, in `Parse<Key>`: the one full row and one full column of a non-bg color that cut the grid into quadrants.
- `1190e5a7` — `line_color`: a color filling a whole line is a divider color, and the lines carrying none group into bands.
- `135a2760` — `line_color`: a uniform line of any color divides panels.
- `15696249` — `line_color`: gates a cell on whether its line is uniform, or on whether its color is some line's color.
- `1a07d186` — `line_color`: a non-bg uniform line is a target loose cells travel to.
- `1a2e2828` — `line_color`: the whole output is the one uniform line's color.
- `20fb2937` — `line_color`, in `Parse<Key>`: the single-color line cutting the header from the field.
- `2546ccf6` — `line_color`: a line of one drawn color is a tiling cut.
- `272f95fa` — `line_color`, in `Parse<Key>`: a line wholly of `params.line` cuts tiles apart.
- `38007db0` — `line_color`: the one-color lines cut out the tiles.
- `39e1d7f9` — `line_color`: a drawn line spanning the grid is a tiling divider.
- `458e3a53` — `line_color`: a uniform line divides tiles rather than sitting in one.
- `4e7e0eb9` — `line_col`, in `Determine`, keyed by `Example`: a uniform line that is not bg is a cut fed to `DividerFrame.divider`, and the parts' extents determine `params.section`.
- `4c177718` — `line_color`: the divider is the line its stored color runs all the way across.
- `50a16a69` — `line`: the filler color fills whole grid lines, and every other cell is pattern.
- `66ac4c3b` — `line_color`, over the non-bg cells: a line whose ink is one color is a marker-line candidate, and two such lines of distinct colors with the same ink positions are the mirror's frames.
- `538b439f` — `line_color`, the surfacing solver: the divider is the line of one non-field color, and its color paints the span. It reads the axis, the line position, and the color, and applies its exclusion outside.
- `54d9e175` — `line_color`: the cut is the line wholly of `params.separator`, and its position feeds `DividerFrame.divider` under the axis it was split on.
- `5545f144` — `line_color`: a line of one color other than the background cuts the snapshots apart, and its position feeds `DividerFrame.divider` under the axis it was split on.
- `5a719d11` — `line_color`, in `Parse<Key>`: a uniform line of any color cuts panels apart, and its position feeds `DividerFrame.divider` under the axis it was split on.
- `60d73be6` — `line_color`: a full line of one color is a line of the cross, and its position frames the flip that reflects each mark.
- `746b3537` — `line_color`: reads `clash` alone, to pick the axis whose lines are uniform.
- `7491f3cf` — `line_color`, in `Parse<Key>`: a uniform line of any color cuts the strip into panels, and its position feeds `DividerFrame.divider` under the axis it was split on.
- `7c008303` — `line_color`, in `Parse<Key>`: the one full row and one full column of a non-bg color that cut the grid into quadrants, fed to `DividerFrame.divider`.
- `780d0b14` — `line_color`: a line wholly of `params.bg` is a divider, fed to `DividerFrame.divider` under the axis it was split on; each tile then reduces to its one non-bg color.
- `78332cb0` — `line_color`: a line wholly of `params.sep` is a tiling cut, fed to `DividerFrame.divider` under the axis it was split on.
- `7d419a02` — `line_color`: a line wholly of `params.bg` is a band cut, fed to `DividerFrame.divider` under the axis it was split on; a cut off both edges of its axis names the axis the bands stack along.
- `7d7772cc` — `line_color`: the fence is a thin color that fills a whole line; the color is read with the axis and position existentially quantified.
- `81c0276b` — `line_color`: a uniform line of any color is a tiling cut, fed to `DividerFrame.divider` under the axis it was split on, and its color marks the empty slots.

`Unanimous` over `Color` with the axis restricted:

- `25d8a9c8` — `slice_color`, in `Parse<Key>`: each slice along `params.axis` is classed as agreeing or differing; reads `clash` only.
- `2204b7a8` — `line`, keyed by `Dir`: the four border edge lines, and a marker takes the color of the nearer uniform edge.
- `642248e4` — `line`, keyed by `Dir`: the four border edge lines, and a mark grows one cell toward the nearer uniform edge, in its color.
- `247ef758` — `line_color`, keyed by the line position: the separator is the line held by a single color other than bg, on the legend axis. One axis, so the key carries no axis column.
- `5ecac7f7` — `line_color`, in `Parse<Key>`, keyed by the line position: the line wholly of `params.sep` is a cut fed to `DividerFrame.divider` under `params.axis`. One axis, so the key carries no axis column.
- `5daaa586` — `side`, keyed by `Dir`: the four full dividing lines with their crossings removed through the cell input, and a hole cell casts to the line of its own color.
- `758abdf0` — `edge`, keyed by `Dir`: the four border edge lines, and the one wholly of `params.wall` fixes the direction mark runs grow and leave along.
- `508bd3b6` — `open_edge` negated, keyed by `Dir`: the four border edge lines, and the wall covering a whole side turns the beam, in the `$Side` case.
- `7c66cb00` — `ends` and `interior`, keyed by the line position on the gravity axis, each over a domain restriction of the line (the two end cells, and the rest): a band line is one where both agree and the two colors differ. One axis, so the key carries no axis column.

Hand-written, with the color named:

- `18286ef8` — `line_broken` negated: the line is wholly `params.divider`-colored.
- `2e65ae53` — `broken` negated, keyed by `Ident`: ink runs the whole way across a line of one component's bounding box.
- `77fdfe62` — `off_line` negated: every cell of the line is the separator color. Written twice, in the program and in `Determine`.
- `82819916` — `inked` negated, keyed by the line position on `params.axis`: a line with no non-bg cell is blank and passes through. One axis, so the key carries no axis column.
- `2bee17df` — `blocked` negated, over a bounding box's interior: a box line whose every interior cell is `params.open` is painted.

Hand-written blank line, the color pinned to bg — each derives "some non-bg cell lies on this line" and negates it: `0b148d64` `ink_slice`, `137f0df0` `block_line`, `18447a8d` `line_ink`, `1be83260` `inked_line`, `1c0d0a4b` `ink_line`, `42918530` `inked_line`, `4f537728` `inked_line`, `5dbc8537` `inked_line` (bg derived by `Mode`), `c1d99e64` `has_ink`.

## Near-misses

- A line that merely holds a color: `45a5af55` `line_col` (the header states the input is a stack of one-color lines, so the task guarantees what the test would check); `c7d4e6ad` with its sibling `c9f8e694`, `slice_repl` (a second such color would make `out` multi-valued rather than absent).
- The commonest color of a line: `2de01db2` `line_color`, whose main color comes from `Mode`. A name collision only.
- The complement of a color class, not agreement: `469497ad` `broken` — the line holds no bg cell, so a line of two non-bg colors passes.
- Part of a line: `22eb0ac0` `edge_match` compares the line's two end cells.
- Agreement between different lines: `ca8f78db` `pattern_at`, folded over the across position; `af22c60d` with its sibling `3631a71a`, `broken`, under a mirror map.
- A fold keyed by something other than a line: `bdad9b1f` `on_line`, keyed by cell, where a clash means a crossing.
- Agreement over values that are not colors: `2ccd9fef` `line_count` over run counts; `538b439f` `reach` over `Position`, testing whether a component occupies one line.
- A uniform region that is not a full line: `39e1d7f9`, `458e3a53`, `2dc579da`, each `tile_color`.
- The line defined by which cells carry a color, with no agreement test: `2b01abd0` `line_cell`, `0a938d79` `mark_line`; and the line through one marked cell, with nothing testing the rest: `363442ee`, `8597cfd7`, `20981f0e`, each `divider`.
- Selection by an extremum rather than agreement: `1ae2feb7` `sep`, the line of maximum ink count.
- Position agreement, not color: `12997ef3` `off_axis`.
- `22425bda` `line`: full-grid one-color lines, occluded at every crossing, so no line is uniform and the operation would find nothing.

## Spec

The code form above already carries these answers.

- **No background exclusion folded in.** Some callers apply no color filter and want every uniform line, bg ones included (`135a2760`, `38007db0`, `458e3a53`, `1a2e2828`, `15696249`, `2204b7a8`). The rest apply seven distinct filters: `!params.bg`, a named color positively, `!field.mode`, "not any line's color", bg pinned, non-bg pinned, and the modal ink pinned. The blank-line callers want exactly the lines a bg exclusion would remove. No one exclusion serves the set, and the filter is one atom at the call site.
- **The non-uniform side is exposed.** `746b3537` and `25d8a9c8` read the disagreement and never the color; `15696249` reads both. Without `mixed` they reach through `one`, whose key type is comp-internal by the naming convention.
- **Both the color and the position earn their columns.** Some callers consume the color as a value (`538b439f`, `1a07d186`, `1a2e2828`, `50a16a69`, `1190e5a7`, `15696249`, `2204b7a8`); others read the position with the color existentially quantified.
- **The axis is a per-key input, not an internal enumeration.** Most callers want both axes and feed `axis_elem`. But `25d8a9c8` restricts to `params.axis`, `18447a8d` to its band axis, `247ef758` to the legend axis, and `2204b7a8` wants the four edge lines rather than the two axis families. An internal enumeration makes those callers compute and discard the perpendicular family. `Ray.dir`, `Diagonal.corner`, and `OrderFrame.axis` are per-key inputs in lib, so the precedent is on this side.
- **The `a` column names the along convention.** `l` is the along component, so the line runs perpendicular to `a`, which is what `DividerFrame.divider` takes and what most callers feed directly. These sites use the across reading (`15696249`, `1a2e2828`, `746b3537`, `25d8a9c8`, `1c0d0a4b`, `c1d99e64`, `469497ad`, `137f0df0`, `bdad9b1f`). Because the comp emits both axes, an across-convention caller reads the same line under the perpendicular tag, and the two readings differ only in the label — so a caller reading the label the other way silently gets the transposed line, and the doc comment has to fix it.
- **The per-key `cell` input stands.** `2e65ae53` keys by `Ident` and feeds one component's bounding-box interior; `1be83260` and `137f0df0` feed a cropped region; `0bb8deee`, `20fb2937`, `272f95fa`, `25d8a9c8`, and `77fdfe62` key by `Example` to share the derivation with `Determine`.

The hand-written callers write the agreement as a universal by defect negation over a color class, which is a membership test rather than an agreement test.

Survey: 2026-09-10 03:32, over the solvers at or after the previous survey's time

The eighth survey read the 334 solvers in scope by every `Unanimous` instance over `Color`, the parser shape, negated line-scoped rules joined with a color-bearing cell atom, every `DividerFrame.divider` rule, and the line-uniformity vocabulary. The thirty listed callers in scope are unchanged in form. New callers: `7491f3cf` `line_color`, in `Parse<Key>`, the code form verbatim (a uniform line of any color cuts the strip into panels, its position fed to `DividerFrame.divider` under the axis it was split on); `7039b2d7` `line_color`, a `// family: 1190e5a7` sibling, counted under `1190e5a7`; `508bd3b6` `open_edge` negated, keyed by `Dir`, hand-written with the color named (the wall covering a whole side turns the beam, in the `$Side` case); and the surfacing solver `758abdf0` `edge`, keyed by `Dir`. Near-misses all fall in named classes: complement of a color class (`6e4f6532` `line_bg`, `67a423a3` `gapped`, `178fcbfb` `bare`, `52df9849` `unsupported`), a line that merely holds a color (`2601afb7` `bar_color`, `234bbc79` `inked_line`), a color read off a line with no agreement test (`278e5215` `line_color`, `6a980be1` `frame_color`), lines defined by position (`47c1f68c` `line_color`, `6a980be1` `line_cell`, `4a21e3da` `on_cut`, `494ef9d7` `line_of`), agreement over Positions (`67a423a3` `color_line`), uniform regions that are not lines (`6350f1f4` `solid`), and name collisions (`6cdd2623`, `412b6263`, `1e97544e`, `4093f84a`).

Spec: no change forced. Four sites (`758abdf0`, `508bd3b6`, `2204b7a8`, `642248e4`) key the edge lines by `Dir`, which the `(a, l)` interface expresses only as an axis-only position read back through `dist(L, D, 0)`; each of those sites is one hand-written `item` rule, so a `Dir` key is a judgment for the entry's owner, not a forced addition.

Reimplementation: `6e4f6532` `wall_toward` is a `Ray` cast from every wall cell toward the opposite of `d`, keyed by the wall's color, written by hand over `same_line` and `nearer`.

Survey: 2026-09-10 05:34, over the solvers at or after the previous survey's time

The ninth survey read the 353 solvers in scope by every `Unanimous` instance over `Color`, the parser clash shape, every relation read under negation whose defining rule joins a line atom or an edge distance with a color-bearing atom, every `DividerFrame.divider` rule, and the line-uniformity vocabulary. The listed callers in scope are unchanged in form. New callers: `780d0b14` `line_color` and `78332cb0` `line_color`, both the code form verbatim, feeding `DividerFrame.divider` under the split axis with the color filter as one atom at the call site. Near-misses all fall in named classes: complement of a color class (`7837ac64` `gapped_line`, over tiling lines that marks at crossings break), a color read off a line or box with no agreement test (`7837ac64` `line_color` and `corner_color`, `3a301edc` `rect_color`), lines defined by position (`29700607` `header`, `305b1341` `legend`, `5adee1b2` `legend_entry`, `291dc1e1` `border`), a separator defined by which cells carry its color (`6e453dd6` `sep_cell`, `770cc55f` `flow.blocked`, `1acc24af` `wall`) or by a stored distance (`2685904e` `sep_cell`, `1bfc4729` `$StoredLine`), uniform regions that are not lines (`6aa20dc0` `hue`, `6ecd11f4` `obj_col`), agreement keyed by an inner position across examples (`6c434453` `src_read`, `dst_read`), agreement over Positions (`78e78cff` `lone`), and two things on one line with no color agreement (`40853293` `mark_axis`, `50aad11f` and `67636eac` `shared_line`, `291dc1e1` `overlap`).

Spec: no change forced.

Reimplementations: none.

Survey: 2026-09-10 06:13, over the solvers at or after the previous survey's time

The tenth survey read the 363 solvers in scope by every `Unanimous` instance over `Color`, the parser clash shape, every relation read under negation whose defining rule joins a line atom with a color-bearing atom, every `DividerFrame.divider` rule, and the line-uniformity vocabulary, and read in full the twelve solvers whose file time is at or after 05:34. The listed callers in scope are unchanged in form; `7c008303` `line_color`, in `Parse<Key>`, is the code form verbatim, feeding `DividerFrame.divider` under the split axis with `!params.bg` at the call site. New callers: `7d7772cc` `line_color`, the code form verbatim (the fence is a thin color that fills a whole line; the color is read with the axis and position existentially quantified), and `7c66cb00` `ends` and `interior`, keyed by the line position on the gravity axis, each over a domain restriction of the line (the two end cells, and the rest); a band line is one where both agree and the two colors differ. Near-misses all fall in named classes: complement of a color class (`7c8af763` `bg_line`, over tiling lines that marks break), and a line defined by position (`7c66cb00` `line_end`).

Spec: no change forced. `7c66cb00` folds one line under complementary cell domains and joins the two on the line, which the per-key `cell` input already carries.

Reimplementations: none.

Survey: 2026-09-10 07:46, over the solvers at or after the previous survey's time

The eleventh survey read the 380 solvers in scope by every `Unanimous` instance over `Color`, every relation read under negation whose defining rule joins `split` with a color-bearing atom, every `DividerFrame.divider` rule, and the line-uniformity vocabulary, and read in full the twenty-two solvers whose file time is at or after 06:13. The listed callers in scope are unchanged in form; `81c0276b` `line_color` is the code form verbatim, reading `value` with no color filter both to feed `DividerFrame.divider` under the split axis and to take the tiling color as the empty-slot mark. New caller: `82819916` `inked` negated, keyed by the line position on `params.axis`, a hand-written blank line with the color pinned to bg. Near-misses all fall in named classes: complement of a color class over a line that is never uniform (`7e576d6e` `broken`, dividers each broken by a gap; `82819916` `blank`, a multicolored template line), a line defined by which cells carry a color (`759f3fd3` `cross.cell`), a color read off the edge line with no agreement test (`825aa9e9` `floor_color`), agreement over Positions rather than colors (`7ed72f31` `mirror_line`; `80a900e0` `along`, on a diagonal axis by defect negation), a uniform region that is not a line (`810b9b61` `edge_gap`, a box's four edge lines jointly), a line that merely holds a color and agreement between different lines (`80214e03` `line_color` and `content.equals`; also a name collision).

Spec: no change forced. `82819916` joins the one-axis, across-reading sites; `81c0276b` joins the callers that apply no color filter.

Reimplementations: `7e0986d6` `touching` is `Rim<Color>.rim_dir` negated.
