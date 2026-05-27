# Proposals

Forward-looking changes to `.dl` style and primitives. None applied yet — this doc is the working draft.

## 3. Primitive proposals

`divide` is the 1D forward primitive already in lib. Add 2D and 1D-passthrough wrappers for the forward direction (`divide_2d`, `divide_1d`). For the inverse, two pieces:

- `concat_sym` — closed-form 1D fast path for uniform tiles. Mirrors `divide`.
- `ConcatPipeline` — component for the general (rectilinear) case. Solver populates the input relation; component derives per-tile bbox offsets; `compose` is the recompose.

Asymmetry vs forward: divide has two distinct orchestrations (two-divides + compose vs divide + passthrough), so it needs `divide_2d` and `divide_1d`. The component's inverse has one orchestration (lookup + compose); `compose`'s shape-agnosticism handles 2D and slab uniformly, so a single `concat` inside the component covers both.

### 3.4 `ConcatPipeline` — inverse component

Solver populates `tile_in` (dim info; values aren't read by the pipeline) and `gap`. The component derives per-row / per-col tile dims, cumulative per-edge offsets, assembles `tile_offset(p_outer, p_off)`, and exposes a one-liner `concat` (lookup + `compose`).

```
.comp ConcatPipeline {
    .decl tile_in(p_outer: Position, p_inner: Position)
    .decl axis_gap(a: Axis, g: number)

    // Tile dim along axis(D), indexed by tile's distance from edge D.
    // Every cell in a rectilinear tile produces the same K — set semantics dedupes.
    .decl axis_dim(d: Dir, i: number, k: number)
    axis_dim(D, I, K) :-
        tile_in(P_outer, P_inner),
        dist(P_outer, D, I),
        opposite(D, D2),
        dist(P_inner, D, Near), dist(P_inner, D2, Far),
        K = Near + Far + 1.

    // Cumulative offset from edge D for the tile at distance I from D.
    .decl edge_off(d: Dir, i: number, off: number)
    edge_off(D, I, OFF) :-
        axis_dim(D, _, _),
        axis_of(D, A), axis_gap(A, G),
        OFF = (sum K : { axis_dim(D, J, K), J < I }) + I*G.

    // Tile bbox offset in grid units, assembled from the four edges.
    .decl tile_offset(p_outer: Position, p_off: Position)
    tile_offset([OT, BO, OL, RO], [T_off, B_off, L_off, R_off]) :-
        edge_off(TOP,    OT, T_off),
        edge_off(BOTTOM, BO, B_off),
        edge_off(LEFT,   OL, L_off),
        edge_off(RIGHT,  RO, R_off).

    // Lookup + compose.
    .decl concat(p_outer: Position, p_inner: Position, p_grid: Position) inline
    concat(P_outer, P_inner, P_grid) :-
        tile_offset(P_outer, P_off),
        compose(P_off, P_inner, P_grid).
}
```

Internals collapse via `Dir`: `axis_dim`, `edge_off`, and `tile_offset` each generalize across edges/axes in a single rule.

Solver usage:

```
.init concat = ConcatPipeline
concat.tile_in(P_outer, P_inner) :- tile_data(P_outer, P_inner, _).
concat.gap(0, 0).

out(P_grid, V) :-
    tile_data(P_outer, P_inner, V),
    concat.concat(P_outer, P_inner, P_grid).
```

Handles all three arrangements via shape-agnostic `compose`:

- **2D**: `P_outer` full 2D → `tile_offset` returns full 2D `P_off` → compose with full 2D `P_inner`.
- **Slab V**: `P_outer` V-only → `tile_offset` returns V-only `P_off` (`left_off(0, 0)` and `right_off(0, 0)` from the single-column `col_width(0, full_width)`) → compose with full 2D `P_inner` passes H through unchanged.
- **Slab H**: symmetric.

Uniform falls out: when all rows share `I_v`, the `sum` aggregations collapse to `OT * (I_v + G_v)` etc. — same rules, no separate fast path needed.

The convention name disappears from lib: solvers name their input relation freely (e.g., `tile_data` above), and connect it to the pipeline via `concat.tile_in(...) :- tile_data(...)`. Lib-side, only the component's internal relation names are fixed.

### 3.5 `SetKeyMatch` — set-keyed pattern match

Pattern: the candidate set at some Key contains every member of pattern Eid (the count-trick from `6-patterns.md`). Inlined today at each use site as two `count : { ... }` clauses. Used by 31d5ba1a (multi-pattern, eid-keyed) and 3618c87e (single pattern, Eid=0). Lift into a component.

```
.comp SetKeyMatch<Key, Member> {
    .decl pattern_member(eid: number, m: Member)
    .decl candidate_member(key: Key, m: Member)
    .decl matched(key: Key, eid: number)
    matched(Key, Eid) :-
        candidate_member(Key, _),
        pattern_member(Eid, _),
        N = count : { pattern_member(Eid, _) },
        N = count : { pattern_member(Eid, M),
                      candidate_member(Key, M) }.
}
```

Solver wiring — 3618c87e (single pattern):

```
.type SliceMember = [p: Position, col: Color]
.init slice_match = SetKeyMatch<Position, SliceMember>

slice_match.pattern_member(0, [P, Col]) :- c.slice_in(P, Col).
slice_match.candidate_member(P_across, [P_inner, Col]) :- slice_cell(P_across, P_inner, Col).

out(P, Col, $SliceMap()) :-
    cell_split(P, _, P_inner, P_across),
    slice_match.matched(P_across, _), c.slice_out(P_inner, Col).
```

Solver wiring — 31d5ba1a (multi-pattern with per-eid output):

```
.type CombineMember = [p: Position, col: Color]
.init combine_match = SetKeyMatch<Position, CombineMember>

combine_match.pattern_member(Eid, [P_outer, C]) :- c.combine_member(Eid, P_outer, C).
combine_match.candidate_member(P_grid_out, [P_tile, C]) :-
    decompose(P_grid_in, P_tile, P_grid_out, _), in(P_grid_in, C).

out(P_grid_out, Col_out) :-
    combine_match.matched(P_grid_out, Eid),
    c.combine_out(Eid, Col_out).
```

**Type parameters + records.** `.comp Foo<T1, T2>` parameterizes the component over Key and Member types. The Member field is record-typed; the schema lives at the type definition rather than in the component body.

**Impedance — flat fact relations vs record-typed component.** Solver-side relations are typically flat (`slice_in(p: Position, col: Color)`); the component sees one Member field. Each connection rule packs flat values into records via the `[P, Col]` literal at the boundary. One extra rule per direction, typically 2-3 per use. Field ordering in the record matters (positional, not named) — definition is the single source of truth.

**Net win.** 31d5ba1a-style multi-pattern absorbs more boilerplate than the boundary packing costs. Single-pattern (3618c87e) is roughly even — the wiring (pattern, candidate, matched-usage) is the same line count as the bare count-trick (cell_split, two `count : { ... }`).

**Macro fallback.** `#define DEFINE_SET_KEY_MATCH(name, key_type, member_type) \ ...` generates per-use components with flat fields. Avoids records at the cost of Souffle's type-checking until expansion.

### 3.6 `Ordinal` — sparse → dense rank

Pattern: turn a sparse numeric set into a dense ordinal-position mapping. `rank(K, R)` where R is the count of elements strictly less than K. For input `{2, 5, 7}` → `{2→0, 5→1, 7→2}`.

```
.comp Ordinal {
    .decl idx_set(k: number)

    .decl rank(k: number, r: number)
    rank(K, R) :-
        idx_set(K),
        R = count : { idx_set(K2), K2 < K }.
}
```

Composes with `DirFrame`: Ordinal does sparse → dense; DirFrame keeps its dense-input contract and places indices in axis-only Positions.

```
.init o = Ordinal
.init col = DirFrame

o.idx_set(K) :- some_sparse_indices(K).
col.dir(TOP).
col.dist_set(R) :- o.rank(_, R).

out(P, ...) :- some_sparse_indices(K), o.rank(K, R), col.pos(R, P).
```

**Direction.** Default is ascending (`K2 < K`). Descending requires upstream negation.

**Ties.** `idx_set` is a set — duplicate K values dedupe. Distinct items mapping to the same K share that K's rank. Useful for grouping; if unique placement is needed, break ties upstream.

**Naming.** "Rank" in pure math means matrix rank / set rank — different concepts. "Ordinal" sidesteps that misappropriation while naming the output (an ordinal position). The operation itself (count of strictly-less-than over a set) matches CS / stats / SQL "dense rank."

### 3.7 Functor-wrapped multi-clause primitives

Multi-clause inline primitives in `lib.dl` multiply Souffle's generated IR. Each call to a primitive with N clauses contributes ×N to the path count of every rule using it: `dist` (×4), `edge_delta` (×4), `apply` (×8), `split` / `divide` / `divide_by_size` / `concat` (×2 each). A rule with three `dist` calls and two `split` calls compiles to 4³ × 2² = 256 IR paths.

Souffle can't prune impossible Dir / Axis / D4 combinations when the dispatch variable comes from a relation lookup (e.g., `c.header_dir(D)`) — the relation could in principle hold any value of its type, so the cross-product survives into IR. A `slab_anchor`-based keep rule with pattern matches on a free `P_out` reached 17,408 IR paths and timed out the interpreter past 60s; the equivalent compose-based rule with no pattern matches on the output record compiled to 1,536 paths and ran in under a second.

The fix is to replace each multi-clause inline with a single-clause inline that destructures the Position and calls a C++ functor; the functor does the dispatch in C++:

```
.functor dist_proj(d: Dir, t: number, b: number, l: number, r: number) : number

.decl dist(p: Position, d: Dir, k: number) inline
dist(P, D, K) :- P = [T, B, L, R], K = @dist_proj(D, T, B, L, R).
```

```cpp
extern "C" RamDomain dist_proj(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case 10: return t;  case 11: return b;
        case 12: return l;  case 13: return r;
    }
    return 0;
}
```

Verified via `souffle --show=transformed-ram`: a rule with three `dist` calls drops from 64 IR paths (4-clause baseline) to 1 path (functor-wrapped). The wrap is fully pruned by Souffle's optimizer regardless of call count.

#### 3.7.1 Branches for record-returning primitives

`split`, `edge_delta`, `apply`, `divide`, `divide_by_size`, `concat` return Position records. Two implementation paths.

**Branch A — stateful + record return.** One functor per primitive. C++ takes `SymbolTable*` + `RecordTable*` as the first two args and uses `pack` / `unpack` against the record table:

```cpp
extern "C" RamDomain flip_lr(SymbolTable*, RecordTable* rt, RamDomain p) {
    const RamDomain* in = rt->unpack(p, 4);
    RamDomain out[4] = {in[0], in[1], in[3], in[2]};
    return rt->pack(out, 4);
}
```

Mixed native-args + record-return sits in a thinly-tested corner of the Souffle FFI (discussion #2062).

**Branch B — flatten + reassemble.** N functors per primitive (one per output slot), each returning a number; the record is reassembled on the Datalog side via a record literal:

```
.functor flip_lr_t(t: number, b: number, l: number, r: number) : number
.functor flip_lr_b(t: number, b: number, l: number, r: number) : number
.functor flip_lr_l(t: number, b: number, l: number, r: number) : number
.functor flip_lr_r(t: number, b: number, l: number, r: number) : number

.decl flip_lr(p: Position, p_out: Position) inline
flip_lr(P, P_out) :- P = [T, B, L, R],
                     P_out = [@flip_lr_t(T, B, L, R), @flip_lr_b(T, B, L, R),
                              @flip_lr_l(T, B, L, R), @flip_lr_r(T, B, L, R)].
```

Pure naive ABI — no stateful, no record table, no `pack` / `unpack`.

|                                  | Branch A     | Branch B             |
|---                               |---           |---                   |
| Functors per primitive           | 1            | N (= 4 for Position) |
| Datalog wrapper verbosity        | Low          | Higher               |
| FFI risk                         | Less-tested  | Most-tested          |
| Generalizes to recursive records | Yes          | No                   |

Position has fixed arity 4 and no recursive records appear in `lib.dl`.

#### 3.7.2 Migration

1. Add `programs/lib_functors.cpp` with branch-B implementations of `dist`, `edge_delta`, `split`, `apply`, `divide`, `divide_by_size`, `concat`.
2. Build to a shared library; `programs/run_dl.py` links it via `-l`.
3. Rewrite each multi-clause inline in `lib.dl` as a single-clause inline wrapping a functor.
4. Solver `.dl` files unchanged — surface API (`dist(P, D, K)`, `split(P, A, _, _)`, etc.) preserved.

Composite primitives (`slab_anchor`, `corner_anchor`, `divide_slab`, `divide_2d`, `divide_by_size_2d`, `concat_slab`, `concat_2d`) inherit the fix via the same surface API; their bodies don't need rewriting.

The "no Position destructure" rule in `4-style.md` continues to apply to solver bodies — destructure lives inside `lib.dl`'s wrappers only.

### 3.8 Equivariance classification for primitives

Primitives that use a specific Position slot (T, B, L, R) in their formula fall into two categories depending on whether the slot choice is observable in the relation's input-output behavior.

**Equivariant.** The relation commutes with D4 transforms: `f(D4(P)) = D4(f(P))`. The formula may use a specific slot internally (e.g., `Ot = T / (Sh+G)`), but the slot choice washes out because the primitive's constraints force the algebra to be symmetric. `divide` and `divide_by_size` are equivariant — flipping the input gives a flipped output.

**Non-equivariant.** The relation does NOT commute with D4. The slot choice produces observably different outputs under different transforms. `wallpaper` (removed) was non-equivariant — for non-divisible frame extents, `T mod period` and `B mod period` give different intile mappings for the same physical cell.

**Diagnostic.** For a primitive `f(P, ...) → (P_out, ...)`: check whether `f(apply(D, P)) = apply(D, f(P))` for all D in D4 and all P in the input domain. Equality → equivariant. Inequality on any (D, P) → non-equivariant.

**Implication for lib design.** Equivariant primitives are safe to use with the apply-sandwich pattern (`apply(D, P, P') → f(P') → apply(D_inv, ...)`) for orientation parameterization. Non-equivariant primitives need an explicit anchor parameter (e.g., `anchor: DiagDir`) or should be avoided in favor of equivariant alternatives.

**Observed instance.** 332efdb3 models a period-2 pattern via `divide_by_size` with K=1 G=1 (equivariant). A non-equivariant `wallpaper` primitive using `T mod period` directly was considered and rejected.

## 4. Process proposals

### 4.1 Lib addition protocol

New primitives follow: task-local → propose → lib.

1. **Task-local.** Write the primitive directly in the solver's Consts or body. Run it; confirm it works in context.
2. **Propose.** Surface the primitive to the user for review. Name it, describe the operation, show the solver-local version.
3. **Lib (on approval).** Move to `programs/lib.dl`. Update callers.

