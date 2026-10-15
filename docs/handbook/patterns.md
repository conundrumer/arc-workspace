+ index: entries
+ budget: 19600
* comment: when editing this doc
    - cite a task by bare id to give a precedent, or by id with a gloss to state the task's facts; write the gloss without the task's internal vocabulary.
    - Include an entry only when the pattern took substantial derivation or user direction to reach. If a session can rederive a pattern cheaply, omit it even when it looks reusable.
    - An entry's first sentence is its index line, read under the entry's title: it stands alone, and criteria and guards start after it.

# Patterns
- This document records patterns observed across `.dl` solvers.
- A pattern records an encoding that worked, and licenses nothing.
- The `.dl` files are the source of truth.

## Multiple modeling forms via ADT `Choice`
- Multiple models are encoded in one solver file as cases of an ADT `Choice` column on `out`.
    - Cases can be more than two, may carry their own per-case data, and may nest, since a case's data can itself be an ADT.
    - Each case fires its own clauses, and the runner emits that case's output grids.
    ```
    .type Choice = CaseA {} | CaseB {}

    .decl out(p: Position, col: Color, ch: Choice)
    out(P, Col, $CaseA()) :- ...
    out(P, Col, $CaseB()) :- ...
    ```
- A record-typed `Choice` represents cases that compose from independent parts:
    ```
    .type Detect = PairExist {} | Count {}
    .type Stage  = PerCell {} | SliceMap {}
    .type Choice = [detect: Detect, stage: Stage]

    .decl out(p: Position, col: Color, ch: Choice)
    out(P, Col, [$PairExist(), $PerCell()]) :- ...
    out(P, Col, [$Count(),     $SliceMap()]) :- ...
    ```
- A clause for one branch of a field writes that field's constructor and a variable for each other field.
- When only some combinations are cases, the record remains, and `impl_choice` excludes the others, as [Cases](docs/handbook/solver-file.md#cases) states.
- The linter's `choice-tag` finding names two clauses identical but for one head argument, a constructor with no arguments in each, that facts of one relation hold: write the shared clause once, with that argument a variable that relation binds, and each other constructor it holds excluded.

## Choice grounding via `impl_choice`
- If the case column otherwise appears only under negation, a clause shared by all cases needs a positive atom to bind its case variable. An enumeration relation that holds each case provides it.
    ```
    .decl impl_choice(ch: Choice)
    impl_choice($CaseA()). impl_choice($CaseB()).

    out(P, Col, Ch) :- impl_choice(Ch), in(P, _), !covered(Ch, P), params.bg(Col).
    ```

## `GRID_HxW` for grid data
- A GRID call stores a grid as a literal layout, one fact per cell in row-major order: `GRID_HxW` emits every cell with its value; `GRID_MASK_HxW` and `GRID_SPARSE_HxW` emit the cells that hold something; `GRID_STAMP_HxW` and `GRID_STAMP_SPARSE_HxW` emit those cells as offsets from a marked anchor.
    - A cell that holds nothing is an empty cell, and `_` is its token.
    - `GRID_HxW` has no empty cell: every cell of its layout holds a value.
    - Each cell fact's Position is in the call's own H×W frame.
    - The runner expands the call before Souffle sees the file, and GRID is not defined in the lib.
    - H and W are the grid's dims and take any size.
    * comment:
        - A call therefore carries H·W cell values.
    - Cells can hold any per-cell data: colors, labels, transforms.
    - A distinguished cell is a Position fact, not a cell value (27a28665 `center_pos`).
    ```
    .decl template(p: Position, col: Color)
    GRID_3x3(template,
        1, 2, 1,
        2, 0, 2,
        1, 2, 1)
    ```
- Arguments between the relation name and the cell values pass through as leading columns, so one relation can hold several grids keyed by id (995c5fa3 `mapping_member`).
- An empty cell states a modeling claim: the grid holds nothing there. A sparse form reads each other digit as a value, `0` included.
- `GRID_MASK_HxW(rel, ...)` takes `1` for a member cell and emits `rel(p)` for it — membership grids (1818057f `shape`).
- `GRID_SPARSE_HxW(rel, ...)` takes a digit for a cell's value and emits `rel(p, v)` for it — ink templates (21897d95 `bracket_glyph`).
- `GRID_STAMP_HxW(rel, ...)` and `GRID_STAMP_SPARSE_HxW(rel, ...)` store a mark-anchored stamp as `Offset` values.
    - The layout is a picture with one token carrying the `@` prefix, and each member cell is emitted as its offset from that anchor.
    - To choose between a grid and a stamp, ask what locates a cell in the data at hand: a position in a frame whose extent the data fixes takes a grid, and a distance from a mark takes a stamp.
    - `GRID_STAMP_HxW` takes `1` for a member cell and emits `rel(delta)` for it (3ac3eb23 `template`).
    - `GRID_STAMP_SPARSE_HxW` takes a digit for a cell's value and emits `rel(delta, v)` for it (dc1df850 `template`).
    - An empty cell emits no offset.
    - The `@` prefix goes on any token, an empty cell included: 0962bcdd `template_arm` anchors on an empty cell, 0962bcdd `template_center` on a member. A picture anchored on a member emits the zero offset.

## `GRID_HxW` catalogs
- A catalog stores several patterns in one id-keyed relation.
    - Each entry is a keyed GRID call, with the entry's output fact beside its grid.
    ```
    .decl pattern_member(id: Ident, p: Position)
    .decl pattern_out(id: Ident, col: Color)

    GRID_MASK_3x3(pattern_member, 0,
        _, 1, _,
        1, 1, 1,
        _, 1, _)
    pattern_out(0, 3).

    GRID_MASK_3x3(pattern_member, 1,
        1, _, 1,
        _, _, _,
        1, _, 1)
    pattern_out(1, 8).
    ```
- Per-entry relations with derive clauses hold the same data, but a new entry is then new program text rather than new facts.

## `RIGID` — a stored shape and its attached parts, in every orientation
* comment: The user's words, session 129de8fc, 2026-10-15T01:32:56Z to 01:34:03Z: "in rigid.md i noted the gloss may be resulting in solvers not using rigid. let's update the gloss?", and "send", which chose the coordinator's proposed gloss.
- Where a shape the parameters store may stand in more than one orientation, and the task treats each orientation alike, a `RIGID` block stores it once, with each cell, direction or second shape attached to it, and gives each D4 image of the whole, in place of a shape closed over D4 by hand or a stamp stored apart from its direction.
- A `RIGID` block groups parameter relations stated in one shared intrinsic frame and exposes them only as D4 placements that transform them together, so the stored pose is unobservable.
    - Each relation reappears as `<block>_<rel>` with a leading D4 column and every column transformed by that element.
    - Consumers join relations on the element, which is what "the same oriented instance" means.
    - The runner expands the block before Souffle sees the file, like GRID.
    - The block's generated names are unreadable outside the expansion (lint category 'rigid chart').
    ```
    RIGID(marker,
        .decl glyph(p: Position)
        GRID_MASK_2x2(glyph,
            1, 1,
            1, _)
        .decl launch(p: Position) launch([0, 1, 0, 1]).
        .decl aim(d: DiagDir) aim(DIAG_TL).
    )
    ```
- The program reads `params.marker_glyph(D, P)`, `params.marker_launch(D, P_l)`, `params.marker_aim(D, D_aim)`, joined on D (142ca369).
- An id-keyed chart holds one independent assembly per id, the id passing through by identity (150deff5 `piece_member`).
- The transform is type-directed: `Box`, `Position`, and `Offset` via `apply`; `Dir`, `DiagDir`, and `Dir8` via the direction actions; `Axis` and `DiagAxis` via the induced swap; `Color`, `number`, and `Ident` by identity.
- Scope is orientation only: translation freedom stays with `Occurrences` placement anchors, color freedom with instantiation keying.
- The determination writes the chart under its placed name, in a pose of its own, and the runner compares up to pose.
    - An ident-free block must be one joint D4 image of the stored assembly.
    - An id-keyed chart is compared per id, composed with id renaming.

## Position remapping via `GRID` id join
- A position correspondence is stored by joining two GRIDs on an opaque id: `src` labels the domain cells; `dst` gives each target cell the id of its source.
    - The correspondence is visible in the layout, and ids carry identity only.
    - Raw Position-pair facts hold the same data in an unreadable form.
    ```
    .decl src(p: Position, id: Ident)
    GRID_3x3(src,
        0, 1, 2,
        3, 4, 5,
        6, 7, 8)

    .decl dst(p: Position, id: Ident)
    GRID_5x5(dst,
        0, 0, 1, 2, 2,
        0, 0, 1, 2, 2,
        3, 3, 4, 5, 5,
        6, 6, 7, 8, 8,
        6, 6, 7, 8, 8)

    .decl map(p_in: Position, p_out: Position)
    map(P_in, P_out) :- src(P_in, Id), dst(P_out, Id).
    ```
- (e633a9e5 $Map — a nonuniform scale-up as pure data.)

## Tabulated decomposition
- A constant layout is stored as parameter data.
    - The layout's dims are stored in fact parameters, and one relation maps each grid position to its decomposition, built with `helpers.tile_pos` and embedded behind a border with `compose`.
    - The program joins `in` against it and works in decomposed coordinates.
    - A model that derives the decomposition instead uses `divide` or `divide_by_size`.
    - When the layout is the same in every pair, tabulation fits.
    ```
    .decl arr_dim(a: Axis, n: number)
    arr_dim(AXIS_V, 1). arr_dim(AXIS_H, 2).
    .decl tile_dim(n: number) tile_dim(3).
    .decl gap(n: number) gap(1).
    .decl border(n: number) border(1).

    .decl decompose(p_grid: Position, p_tile: Position, p_intile: Position)
    decompose(P_grid, P_tile, P_intile) :-
        arr_dim(AXIS_V, Ov), arr_dim(AXIS_H, Oh), tile_dim(K), gap(G), border(B),
        helpers.tile_pos([Ov, Oh], [K, K], [0, G], P_frame, P_tile, P_intile),
        compose(P_frame, [B, B, B, B], P_grid).
    ```
- (34b99a2b `tile_decompose` — gap only; ed74f2f2 `decompose` — gap and border.)

## Per-tile data keyed by tile position
- Parameter data about one tile of a decomposition is keyed by the tile position that the decomposition produces.
    - The program then joins its `p_outer` against the data directly.
    - A second vocabulary for the same tiles, such as an edge Dir or a corner name, requires a conversion clause, which Indirection flags.
    ```
    .decl combine_member(id: Ident, p_outer: Position, c: Color)
    combine_member(0, [0,0,0,1], 0). combine_member(0, [0,0,1,0], 0).
    ```
- (1b2d62fb, 34b99a2b, dae9d2b5 — per-panel colors in the combine tables, keyed on `p_outer` of the 1×2 divide.)

## Stored total orders as dense ranks
- A total order the output depends on is stored in the parameters as dense rank data and is consumed only by comparison.
    - Ranks state each element's place in the sequence directly, and successor edges state it only through closure.
    - Dense values keep the encoding canonical.
    * comment:
        - A gapped value encodes one order many ways.
    - A store bases its ranks at 0, unless the clause that reads them compares a rank against a value that fixes another base.
    ```
    .decl ink_rank(c: Color, r: number)
    ink_rank(7, 0). ink_rank(4, 1). ink_rank(8, 2). ink_rank(6, 3).

    beaten(P, Col) :-
        ink_at(P, Col), ink_at(P, C2),
        params.ink_rank(C2, R2), params.ink_rank(Col, R), R2 < R.
    ```
- Over a spatial domain, the ranks can be stored as a GRID: a68b268e's `params.prio` shows the precedence in the tile arrangement.

## Set-keyed relations via parent/child tables
- A relation keyed by a multiset of members is represented as two tables joined by an `id`: the parent holds `(id, out-fields)`; the child holds `(id, member-fields)`.
    - The match uses `KeyedSetCompare`: the child table provides `pattern_member`, the observed cells provide `observed_member`, and `covers` / `equals` test containment / equality.
    - The parent table maps the matched `id` to its output.
    ```
    .decl combine_member(id: Ident, p_outer: Position, c: Color)
    .decl combine_out(id: Ident, c_out: Color)

    combine_member(0, [0,1,0,0], 0). combine_member(0, [1,0,0,0], 0). combine_out(0, 2).
    combine_member(1, [0,1,0,0], 9). combine_member(1, [1,0,0,0], 0). combine_out(1, 0).

    .type CombineMember = [p: Position, col: Color]
    .init combine_match = KeyedSetCompare<Position, Ident, CombineMember>
    combine_match.pattern_member(Id, [P_outer, C]) :- params.combine_member(Id, P_outer, C).
    combine_match.observed_member(P_grid_out, [P_tile, C]) :-
        decompose(P_grid_in, P_tile, P_grid_out, _), in(P_grid_in, C).

    out(P_grid_out, Col_out) :-
        params.combine_out(Id, Col_out),
        combine_match.equals(P_grid_out, Id).
    ```
- The observed tiles at a cell are exactly the entry's members, so this example uses `equals`.
- Where the observed set may have members beyond the pattern, `covers` applies.

## `divide_by_size` (K, G) parameter space
- Different (K, G) splits of one step size model the same periodic layout with different tile/gap semantics. The step between tile starts is `K + G`.
- For a frame extent H and effective step S = K + G, divisibility requires `(H + G) % S = 0`.
- Concrete: period-2 pattern over H=7.
    | K | G | Step | Divisibility | Tile semantics |
    |---|---|------|-------------|----------------|
    | 2 | 0 | 2 | `7 % 2 = 1` — fails | — |
    | 1 | 1 | 2 | `8 % 2 = 0` ✓ | bg cell = tile, dot cell = gap |
    | 3 | -1 | 2 | `6 % 2 = 0` ✓ | adjacent tiles overlap by 1 row |
- K=2 G=0, the visual period, fails for odd H.
- K=1 G=1 treats bg as tile and dot as gap.
- K=3 G=-1 uses shared-boundary overlap.
- Existing divide/divide_by_size encodings are checked for a different (K, G) split before a new lib relation is added for a periodic pattern.

## 1D `divide` composed to 2D
- `divide` along V and H separately, composed via `compose`, gives 2D decomposition.
    ```
    divide(P_grid, AXIS_V, Nv, Gv, P_outer_v, P_inner_v),
    divide(P_grid, AXIS_H, Nh, Gh, P_outer_h, P_inner_h),
    compose(P_outer_v, P_outer_h, P_tile),
    compose(P_inner_v, P_inner_h, P_intile).
    ```

## Wide and long layouts
- A relation can lay co-occurring values out wide, as columns of one atom, or long, as one row per member.
- Multiplicity that the concept fixes goes wide: the two axes, a corner's two dirs, the four edge distances. Box is the wide form of per-Dir distance data.
- Multiplicity that the task varies stays long: markers, tiles, ink cells.
- Wide is a single atom.
- A clause that repeats an atom once per member is not a wide layout.
- When those members are a closed domain in one shared role, that clause states a universal by hand, as [Universals via defect negation](docs/handbook/patterns.md#universals-via-defect-negation) describes.
- A solver reads wide data by unification and long data by joins.
- A long encoding of a fixed co-occurrence makes every consumer reassemble it, as a self-join with a distinctness guard that derives each symmetric result twice:
    ```
    edge(D1), edge(D2), D1 != D2, marked(P, D1), marked(P, D2).
    ```
- The reassembly occurs in one place: the domain's pairing relation, or the defining clause of a wide relation.
    - `opposite` is the Dir form of a pairing relation, and each closed domain gets its own.
    - On a domain with identity only, such as colors, the distinctness join is the concept itself.
- Order inside a wide atom is a tag column or a repeated value, never slot position.
- A pairing relation holds all orders as rows, as `opposite` and `turn` do, so which member fills which slot is data.
- A record that orders members by positional convention lacks that property: the convention is unstated data at the call boundary.
- A repeated variable in a wide atom states the diagonal case directly: equal extents for a square, equal distances for a centered cell or one on a corner's diagonal.
- The long encoding needs an agreement join for the same statement.
- A derivation has a long layout.
* comment:
    - A clause that quantifies over an index emits one row per index value, and aggregation computes per index.
    - `Bbox` aggregates `edge_min` per Dir, then packs the four into `box`.
- Widening derived data requires one pairing join at its defining clause.
- A value that already holds the co-occurrence can be widened without another join.

## Universals via defect negation
- "Every member of a closed domain satisfies R" is stated through a defect witness: one clause derives the keys where some member fails, and the universal is its negation.
    - A member missing from the tested relation is a defect, so existence and agreement are one test.
    ```
    broken(P, Col) :- arm(P, _, Col), dir_elem(D), !arm(P, D, Col).
    ring(P, Col)   :- arm(P, _, Col), !broken(P, Col).
    ```
- The enum relation supplies the domain: `dir_elem`, `d4_elem`, `axis_elem`.
- Repeating the tested atom once per member states the same universal by hand: the members become variable positions, and an assembly join must bind one variable per member.

## Open values joined per value
- The program derives the output, or a value the output depends on one-to-one, once per open value, keyed by that value in each case that shares the keyed clauses, and keeps it only where every open value gives the same one, and under tiebreak resolutions the same grid, through any resolution: `Unanimous` over the per-value results, or one `out` clause over every value, where two colors at a cell leave the grid undefined (28a6681f).
    - Neither form makes the output undefined where some open value gives nothing, since the other values' result still stands. A defect clause states it, as in [Universals via defect negation](docs/handbook/patterns.md#universals-via-defect-negation).

## `cell_split` — input cell with its axis decomposition
- `cell_split` pairs an input cell with its along/across split on the task's axis.
    ```
    .decl cell_split(p: Position, col: Color, p_inner: Position, p_across: Position)
    cell_split(P, Col, P_inner, P_across) :- in(P, Col), params.axis(A), split(P, A, P_inner, P_across).
    ```
